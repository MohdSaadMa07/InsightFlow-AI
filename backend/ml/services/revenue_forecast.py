"""
Revenue Forecast Service — Generates daily revenue forecasts with
uncertainty bounds using a hybrid approach: TFT model if available,
otherwise an enhanced heuristic with lag features, trend anchoring,
and growing asymmetric confidence intervals.
"""
import json
import logging
import math
import os
from time import perf_counter
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from django.conf import settings

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = os.path.join(settings.BASE_DIR, 'ml', 'models', 'artifacts')
MODEL_PATH = os.path.join(ARTIFACTS_DIR, 'revenue_tft_v1.pt')
FORECAST_CACHE_PATH = os.path.join(ARTIFACTS_DIR, 'revenue_forecast_cache.json')

# Quantile indices from TFT output (7 quantiles: [0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.98])
QIDX_MEDIAN = 3
QIDX_LOWER = 1
QIDX_UPPER = 5


class RevenueForecastService:
    """Singleton service for revenue forecasting.

    Uses TFT model when available, falls back to heuristic.
    """

    _instance = None
    _model = None
    _dataset_meta = None  # Saved dataset config for inference

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, model_dir=None):
        """Load the TFT model from a saved checkpoint directory."""
        if self._model is not None:
            return True

        # Scan artifacts for a saved TFT model directory
        if model_dir is None:
            candidates = sorted(
                d for d in os.listdir(ARTIFACTS_DIR)
                if d.startswith('revenue_tft_v1_') and
                os.path.isdir(os.path.join(ARTIFACTS_DIR, d))
            )
            if candidates:
                model_dir = os.path.join(ARTIFACTS_DIR, candidates[-1])

        if model_dir is None or not os.path.isdir(model_dir):
            logger.info('No TFT model directory found (will use heuristic)')
            return False

        try:
            from pytorch_forecasting import TemporalFusionTransformer
            ckpt_path = os.path.join(model_dir, 'model.ckpt')
            if not os.path.exists(ckpt_path):
                logger.warning('No checkpoint found in %s', model_dir)
                return False
            self._model = TemporalFusionTransformer.load_from_checkpoint(ckpt_path)
            logger.info('TFT model loaded from %s', ckpt_path)

            meta_path = os.path.join(model_dir, 'dataset_meta.json')
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    self._dataset_meta = json.load(f)
                logger.info('Dataset metadata loaded')
            return True
        except Exception as e:
            logger.error('Failed to load TFT model: %s', e)
            self._model = None
            return False

    @property
    def loaded(self):
        return self._model is not None

    def _get_revenue_data(self, project_id, days=365):
        """Fetch daily revenue metrics from ClickHouse, fall back to PostgreSQL."""
        from analytics.clickhouse_revenue import get_revenue_time_series
        try:
            data = get_revenue_time_series(project_id, days=min(days, 90))
            if data:
                has_revenue = any(r.get('total_revenue', 0) != 0 for r in data)
                if has_revenue:
                    return data
        except Exception:
            logger.warning('ClickHouse revenue query failed, falling back to PG')

        from analytics.models import DailyRevenue
        end = date.today()
        start = end - timedelta(days=days)
        qs = DailyRevenue.objects.filter(project_id=project_id, date__gte=start).order_by('date')
        pg_data = [
            {
                'date': r.date.isoformat(),
                'total_revenue': float(r.total_revenue),
                'mrr': float(r.mrr),
                'dau': r.dau,
                'session_count': r.session_count,
                'transaction_count': r.transaction_count,
                'subscription_count': r.subscription_count,
                'refund_count': r.refund_count,
            }
            for r in qs
        ]
        if pg_data:
            return pg_data
        return data or None

    def _df_from_data(self, data, add_known_future=True):
        """Convert raw revenue data to DataFrame with time features."""
        df = pd.DataFrame(data)
        if df.empty:
            return df
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        df['day_of_week'] = df['date'].dt.dayofweek
        df['day_of_month'] = df['date'].dt.day
        df['month'] = df['date'].dt.month
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        df['time_idx'] = range(len(df))
        df['group_id'] = 0

        # Lag features (for heuristic + feature importance)
        df['revenue_lag1'] = df['total_revenue'].shift(1)
        df['revenue_lag7'] = df['total_revenue'].shift(7)
        df['revenue_lag14'] = df['total_revenue'].shift(14)
        df['revenue_lag28'] = df['total_revenue'].shift(28)
        df['rolling_mean_7'] = df['total_revenue'].rolling(window=7, min_periods=1).mean().shift(1)
        df['rolling_std_7'] = df['total_revenue'].rolling(window=7, min_periods=1).std().shift(1).fillna(0)
        df['rolling_mean_28'] = df['total_revenue'].rolling(window=28, min_periods=1).mean().shift(1)
        df['rolling_std_28'] = df['total_revenue'].rolling(window=28, min_periods=1).std().shift(1).fillna(0)
        if 'dau' in df.columns and 'session_count' in df.columns:
            df['sessions_per_user'] = (df['session_count'] / df['dau'].clip(lower=1)).shift(1)
        if 'transaction_count' in df.columns:
            df['transactions_lag1'] = df['transaction_count'].shift(1)
            df['transactions_rolling7'] = df['transaction_count'].rolling(7, min_periods=1).mean().shift(1)

        df = df.fillna(0)

        if add_known_future:
            self._df_cache = df
        return df

    def _mrr_from_df(self, df):
        return df['mrr'].values if 'mrr' in df.columns else np.zeros(len(df))

    def _recent_growth_signal(self, df):
        """Estimate short-term revenue growth from recent actuals.

        Used only to keep the forward forecast conservative when no strong
        growth signal exists in the observed data.
        """
        revenue = df['total_revenue'].values if 'total_revenue' in df.columns else np.array([])
        if len(revenue) < 28:
            return 0.0

        recent_14 = float(np.mean(revenue[-14:]))
        prev_14 = float(np.mean(revenue[-28:-14]))
        if prev_14 <= 0:
            return 0.0

        growth = (recent_14 - prev_14) / prev_14
        return float(np.clip(growth, -0.03, 0.06))

    def _apply_conservative_cap(self, df, forecasts, horizon):
        """Scale daily forecasts so the horizon total stays near recent actuals.

        This prevents optimistic totals when the model is trained on mostly
        repeating patterns or when the future features do not include explicit
        growth drivers like campaigns or step-change DAU changes.
        """
        if not forecasts:
            return forecasts

        recent_30 = df['total_revenue'].tail(min(30, len(df)))
        recent_total = float(recent_30.sum()) if len(recent_30) else 0.0
        if recent_total <= 0:
            return forecasts

        growth_signal = self._recent_growth_signal(df)
        # Keep the projection close to recent behavior unless the data itself
        # shows a meaningful upward trend.
        allowed_growth = np.clip(growth_signal * 0.35, -0.02, 0.04)
        allowed_total = recent_total * (1 + allowed_growth)

        forecast_total = float(sum(f.get('predicted_revenue', 0.0) for f in forecasts))
        if forecast_total <= 0 or forecast_total <= allowed_total:
            return forecasts

        scale = allowed_total / forecast_total
        adjusted = []
        for item in forecasts:
            lower = max(0.0, item['lower_bound'] * scale)
            upper = max(lower, item['upper_bound'] * scale)
            adjusted.append({
                **item,
                'predicted_revenue': round(max(0.0, item['predicted_revenue'] * scale), 2),
                'lower_bound': round(lower, 2),
                'upper_bound': round(upper, 2),
            })

        return adjusted

    def _forecast_mrr_snapshot(self, df):
        """Forecast month-end MRR as a snapshot rather than summing daily MRR."""
        if 'mrr' not in df.columns or df.empty:
            return 0.0

        mrr = df['mrr'].values.astype(float)
        current = float(mrr[-1])
        if len(mrr) < 28:
            return round(max(0.0, current), 2)

        recent_14 = float(np.mean(mrr[-14:]))
        prev_14 = float(np.mean(mrr[-28:-14]))
        if prev_14 <= 0:
            return round(max(0.0, current), 2)

        mrr_growth = np.clip((recent_14 - prev_14) / prev_14, -0.02, 0.03)
        return round(max(0.0, current * (1 + mrr_growth)), 2)

    # ---- TFT inference ----

    def _tft_predict(self, project_id, df, horizon=30):
        """Generate forecast using the loaded TFT model."""
        from pytorch_forecasting import TimeSeriesDataSet

        meta = self._dataset_meta or {}
        encoder_length = meta.get('encoder_length', 90)
        max_prediction_length = meta.get('max_prediction_length', horizon)

        last_date = df['date'].max()
        future_rows = []
        for i in range(horizon):
            d = last_date + timedelta(days=i + 1)
            future_rows.append({
                'date': d,
                'day_of_week': d.dayofweek,
                'day_of_month': d.day,
                'month': d.month,
                'is_weekend': int(d.dayofweek >= 5),
                'time_idx': df['time_idx'].max() + i + 1,
                'group_id': 0,
                'total_revenue': 0.0,
                'mrr': 0.0,
                'dau': 0,
                'session_count': 0,
                'transaction_count': 0,
                'subscription_count': 0,
                'refund_count': 0,
            })

        pred_df = pd.concat([df, pd.DataFrame(future_rows)], ignore_index=True)

        # Convert categorical columns to string type (required by pytorch_forecasting)
        for col in ['day_of_week', 'month', 'day_of_month']:
            if col in pred_df.columns:
                pred_df[col] = pred_df[col].astype(str)

        # Clip unseen categorical values to the max observed in training data
        # to prevent embedding index out-of-range errors at inference time
        for col in ['month', 'day_of_month']:
            if col in df.columns and col in pred_df.columns:
                known_vals = set(df[col].astype(str).unique())
                pred_df.loc[len(df):, col] = pred_df.loc[len(df):, col].apply(
                    lambda x: x if x in known_vals else list(known_vals)[-1]
                )

        # Build dataset on full data so encoder sees all categories
        full_dataset = TimeSeriesDataSet(
            pred_df,
            time_idx='time_idx',
            target='total_revenue',
            group_ids=['group_id'],
            max_encoder_length=encoder_length,
            max_prediction_length=max_prediction_length,
            static_categoricals=meta.get('static_categoricals', []),
            static_reals=meta.get('static_reals', []),
            time_varying_known_categoricals=meta.get(
                'time_varying_known_categoricals',
                ['day_of_week', 'month', 'day_of_month'],
            ),
            time_varying_known_reals=meta.get(
                'time_varying_known_reals',
                ['time_idx', 'is_weekend'],
            ),
            time_varying_unknown_categoricals=meta.get('time_varying_unknown_categoricals', []),
            time_varying_unknown_reals=meta.get(
                'time_varying_unknown_reals',
                ['total_revenue', 'mrr', 'dau', 'session_count',
                 'transaction_count', 'subscription_count', 'refund_count'],
            ),
            add_relative_time_idx=True,
            add_target_scales=True,
            add_encoder_length=True,
            allow_missing_timesteps=True,
        )

        pred_dataset = TimeSeriesDataSet.from_dataset(
            full_dataset, pred_df, predict=True, stop_randomization=True,
        )
        pred_dl = pred_dataset.to_dataloader(train=False, batch_size=1, num_workers=0)

        raw = self._model.predict(pred_dl, mode='quantiles', return_x=True)
        predictions = raw.output if hasattr(raw, 'output') else raw
        if isinstance(predictions, (list, tuple)):
            predictions = predictions[0]
        if not torch.is_tensor(predictions):
            predictions = torch.as_tensor(predictions)

        # Some pytorch_forecasting versions can return a 2D tensor for scalar
        # predictions; the current model is trained with QuantileLoss, so we
        # normalize to the expected [batch, horizon, quantiles] layout.
        if predictions.dim() == 2:
            predictions = predictions.unsqueeze(-1)

        if predictions.dim() != 3:
            raise ValueError(f'Unexpected TFT prediction shape: {tuple(predictions.shape)}')

        forecasts = []
        for i in range(horizon):
            d = last_date + timedelta(days=i + 1)
            quantile_count = predictions.size(-1)
            median_idx = min(QIDX_MEDIAN, quantile_count - 1)
            lower_idx = min(QIDX_LOWER, quantile_count - 1)
            upper_idx = min(QIDX_UPPER, quantile_count - 1)
            median = float(predictions[0, i, median_idx])
            lower = float(predictions[0, i, lower_idx])
            upper = float(predictions[0, i, upper_idx])
            forecasts.append({
                'forecast_date': d.isoformat(),
                'predicted_revenue': round(max(0, median), 2),
                'lower_bound': round(max(0, lower), 2),
                'upper_bound': round(max(0, upper), 2),
            })

        return forecasts

    # ---- Heuristic ----

    def _heuristic_predict(self, df, horizon=30):
        """Generate forecast using the enhanced heuristic."""
        recent_revenue = df['total_revenue'].values

        if len(recent_revenue) < 14:
            return None

        last_known = float(recent_revenue[-1])
        last_known_7d_avg = float(np.mean(recent_revenue[-7:])) if len(recent_revenue) >= 7 else last_known
        last_28 = recent_revenue[-28:]
        dow_sums = np.zeros(7)
        dow_counts = np.zeros(7)
        for i in range(28):
            dow = df['day_of_week'].values[-(28 - i)]
            dow_sums[dow] += last_28[i]
            dow_counts[dow] += 1
        dow_avg = np.divide(dow_sums, dow_counts, where=dow_counts > 0,
                            out=np.full(7, float(np.mean(last_28))))

        last_dow = int(df['day_of_week'].values[-1])
        dow_scale = last_known / dow_avg[last_dow] if dow_avg[last_dow] > 0 else 1.0
        dow_avg_scaled = dow_avg * dow_scale

        recent_14 = recent_revenue[-14:]
        x_14 = np.arange(14)
        slope, intercept = np.polyfit(x_14, recent_14, 1)
        mean_30d = float(np.mean(recent_revenue[-30:])) if len(recent_revenue) >= 30 else float(np.mean(recent_revenue))
        slope = np.clip(slope, -mean_30d * 0.05, mean_30d * 0.05)

        dow_fitted = np.array([dow_avg_scaled[int(d)] for d in df['day_of_week'].values[-28:]])
        residuals = last_28 - dow_fitted
        recent_volatility = float(np.std(residuals)) if len(residuals) > 1 else mean_30d * 0.05

        last_date = df['date'].max()
        forecasts = []

        for i in range(horizon):
            d = last_date + timedelta(days=i + 1)
            dow = d.dayofweek
            seasonal = float(dow_avg_scaled[dow])

            blend_ratio = min(1.0, i / 7.0)
            lag_anchor = last_known * (1 - blend_ratio) + last_known_7d_avg * blend_ratio

            trend_decay = math.exp(-i / (horizon * 0.4))
            trend_contrib = slope * trend_decay

            raw = seasonal * (1 - blend_ratio * 0.3) + lag_anchor * (blend_ratio * 0.3) + trend_contrib
            pred = max(0, raw)

            ci_width = recent_volatility * (0.5 + 0.5 * math.sqrt(i + 1))
            lower_margin = ci_width * 0.8
            upper_margin = ci_width * 1.2 * (1 + i / horizon)

            forecasts.append({
                'forecast_date': d.isoformat(),
                'predicted_revenue': float(round(pred, 2)),
                'lower_bound': float(round(max(0, pred - lower_margin), 2)),
                'upper_bound': float(round(pred + upper_margin, 2)),
            })

        return forecasts

    # ---- Main ----

    def predict(self, project_id, horizon=30, encoder_length=90):
        """Generate revenue forecast.

        Tries TFT model first; falls back to heuristic if unavailable.
        """
        started_at = perf_counter()
        data = self._get_revenue_data(project_id, days=365)
        df = self._df_from_data(data)
        if df.empty:
            return None

        recent_revenue = df['total_revenue'].values
        recent_mrr = self._mrr_from_df(df)

        if len(recent_revenue) < 14:
            return None

        self.load()  # lazy-load TFT

        model_version = 'heuristic_v2'
        feat_imp = self._compute_feature_importance(df)
        feat_imp_source = 'correlation_fallback'

        last_date = df['date'].max()

        # Try TFT first
        if self.loaded:
            try:
                tft_forecasts = self._tft_predict(project_id, df, horizon=horizon)
                if tft_forecasts:
                    tft_forecasts = self._apply_conservative_cap(df, tft_forecasts, horizon)
                    model_version = self._dataset_meta.get('model_version', 'revenue_tft_v1') if self._dataset_meta else 'revenue_tft_v1'
                    forecasts = tft_forecasts

                    # Try loading TFT feature importance
                    if self._dataset_meta:
                        imp_dir = os.path.join(ARTIFACTS_DIR, *self._dataset_meta.get('model_version', '').split('_')[-1:] or [])
                        # Try common paths
                        for candidate in os.listdir(ARTIFACTS_DIR):
                            if candidate.startswith('revenue_tft') and os.path.isdir(os.path.join(ARTIFACTS_DIR, candidate)):
                                imp_path = os.path.join(ARTIFACTS_DIR, candidate, 'feature_importance.json')
                                if os.path.exists(imp_path):
                                    with open(imp_path) as f:
                                        feat_imp = json.load(f)
                                    feat_imp_source = 'tft_interpretation'
                                    break
                    logger.info('Used TFT model for forecast')
            except Exception as e:
                logger.warning('TFT prediction failed, falling back to heuristic: %s', e)
                forecasts = self._heuristic_predict(df, horizon=horizon)
        else:
            forecasts = self._heuristic_predict(df, horizon=horizon)

        if forecasts is None:
            return None

        # MRR forecast
        forecast_mrr = self._forecast_mrr_snapshot(df)
        mrr_forecasts = []
        for i in range(horizon):
            d = last_date + timedelta(days=i + 1)
            mrr_forecasts.append({
                'forecast_date': d.isoformat(),
                'predicted_mrr': float(forecast_mrr),
            })

        trained_at = None
        if self._dataset_meta:
            trained_at = self._dataset_meta.get('trained_at')

        model_name = 'Temporal Fusion Transformer' if self.loaded else 'Heuristic Revenue Forecaster'
        model_version_label = self._dataset_meta.get('model_version', model_version) if self._dataset_meta else model_version
        explanation_label = 'Temporal Fusion Transformer Variable Importance' if feat_imp_source == 'tft_interpretation' else 'Model Feature Importance'

        result = {
            'project_id': project_id,
            'snapshot_date': date.today().isoformat(),
            'horizon': horizon,
            'model_version': model_version,
            'model_metadata': {
                'model': model_name,
                'version': model_version_label,
                'prediction_horizon_days': horizon,
                'last_trained': trained_at,
                'inference_ms': round((perf_counter() - started_at) * 1000, 1),
                'explanation': explanation_label,
            },
            'forecasts': forecasts,
            'mrr_forecasts': mrr_forecasts,
            'historical': [
                {
                    'date': row['date'] if isinstance(row['date'], str) else str(row['date']),
                    'total_revenue': float(row['total_revenue']),
                    'mrr': float(row.get('mrr', 0)),
                }
                for row in data[-180:]
            ] if data else [],
            'feature_importance': feat_imp,
            'feature_importance_source': feat_imp_source,
        }
        return result

    def _compute_feature_importance(self, df):
        """Estimate feature importance from correlation with revenue."""
        candidates = {
            'day_of_week': pd.Categorical(df['day_of_week']).codes,
            'is_weekend': df['is_weekend'].values,
            'dau': df['dau'].values if 'dau' in df.columns else None,
            'session_count': df['session_count'].values if 'session_count' in df.columns else None,
            'transaction_count': df['transaction_count'].values if 'transaction_count' in df.columns else None,
            'subscription_count': df['subscription_count'].values if 'subscription_count' in df.columns else None,
            'revenue_lag1': df['revenue_lag1'].values,
            'revenue_lag7': df['revenue_lag7'].values,
            'rolling_mean_7': df['rolling_mean_7'].values,
        }

        revenue = df['total_revenue'].values
        scores = {}
        for name, vals in candidates.items():
            if vals is None:
                continue
            try:
                mask = ~np.isnan(vals) & ~np.isnan(revenue)
                if mask.sum() > 2:
                    corr = abs(float(np.corrcoef(vals[mask], revenue[mask])[0, 1]))
                    if not np.isnan(corr):
                        scores[name] = round(corr, 4)
            except Exception:
                pass

        if not scores:
            return {'seasonal_pattern': 1.0}

        total = sum(scores.values())
        if total > 0:
            scores = {k: round(v / total, 4) for k, v in scores.items()}
        return scores

    def explain(self, project_id):
        """Return feature importance from TFT attention."""
        if not self.loaded:
            return {'error': 'Model not loaded, train TFT first'}
        return {'note': 'TFT model is active for attention-based explanations'}

    # ------------------------------------------------------------------
    # Cache helpers (nightly precomputation)
    # ------------------------------------------------------------------

    def load_from_cache(self, project_id):
        """Return cached forecast for a project, or None if stale/missing."""
        try:
            if not os.path.exists(FORECAST_CACHE_PATH):
                return None
            with open(FORECAST_CACHE_PATH) as f:
                cache = json.load(f)
            entry = cache.get(str(project_id))
            if not entry:
                return None
            cached_date = entry.get('snapshot_date')
            if cached_date != date.today().isoformat():
                return None
            return entry['data']
        except Exception as exc:
            logger.warning('Forecast cache read failed: %s', exc)
            return None

    def save_to_cache(self, project_id, result):
        """Persist forecast result to JSON cache."""
        if not result:
            return
        try:
            cache = {}
            if os.path.exists(FORECAST_CACHE_PATH):
                with open(FORECAST_CACHE_PATH) as f:
                    cache = json.load(f)
            cache[str(project_id)] = {
                'snapshot_date': date.today().isoformat(),
                'cached_at': datetime.now().isoformat(),
                'data': result,
            }
            os.makedirs(os.path.dirname(FORECAST_CACHE_PATH), exist_ok=True)
            with open(FORECAST_CACHE_PATH, 'w') as f:
                json.dump(cache, f, indent=2, default=str)
            logger.info('Forecast cached for project %s', project_id)
        except Exception as exc:
            logger.warning('Forecast cache write failed: %s', exc)


revenue_forecast = RevenueForecastService()
