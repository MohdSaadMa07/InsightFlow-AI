"""Product Health Monitor — Behavioral anomaly detection service.

This service builds project-level time-windowed behavior features from
ClickHouse event data and scores them with a dense autoencoder when a trained
checkpoint is available. Until training artifacts are generated, it falls
back to a stable heuristic score so the dashboard and batch pipeline can
still run.

Enriched output includes:
- Severity (Normal / Low / Medium / High / Critical) based on score/threshold ratio
- Expected vs Actual: decoded reconstruction as the "expected" values
- Feature contributions: per-feature absolute reconstruction error (%)
- Rule-based recommendations from top features
- System status card
"""

import json
import logging
import os
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import torch
from torch import nn

from django.conf import settings

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = os.path.join(settings.BASE_DIR, 'ml', 'models', 'artifacts')
MODEL_DIR = os.path.join(ARTIFACTS_DIR, 'anomaly_autoencoder_v1')
MODEL_PATH = os.path.join(MODEL_DIR, 'model.pth')
SCORE_TABLE = 'anomaly_scores'
MODEL_VERSION = 'anomaly_autoencoder_v1'
FEATURE_VERSION = 'behavior_window_v1'

# Human-readable business labels for ML feature columns
FEATURE_LABELS = {
    'event_count': 'Event Count',
    'session_count': 'Session Count',
    'click_count': 'Click Count',
    'login_count': 'Login Count',
    'purchase_count': 'Purchase Count',
    'error_count': 'Error Count',
    'distinct_event_types': 'Distinct Event Types',
    'active_hours': 'Active Hours',
    'avg_gap_seconds': 'Average Gap (s)',
    'max_gap_seconds': 'Max Gap (s)',
    'inactive_hours': 'Inactive Hours',
    'events_per_session': 'Events / Session',
    'error_rate': 'Error Rate',
    'weekend_event_count': 'Weekend Activity',
    'day_of_week': 'Day of Week',
    'is_weekend': 'Weekend',
    'event_count_roll3': '3-Day Avg Events',
    'session_count_roll3': '3-Day Avg Sessions',
    'click_count_roll3': '3-Day Avg Clicks',
    'purchase_count_roll3': '3-Day Avg Purchases',
    'error_count_roll3': '3-Day Avg Errors',
    'dau': 'Daily Active Users',
    'revenue': 'Revenue',
}

# Features that are internal to the model and shouldn't appear in the UI
ENGINEERED_FEATURES = {'day_of_week', 'is_weekend', 'avg_gap_seconds', 'max_gap_seconds', 'inactive_hours'}

# Business-friendly grouping for related features
FEATURE_GROUPINGS = {
    'weekend_event_count': 'Weekend Activity',
}

PRODUCT_DESCRIPTIONS = {
    'session_count': 'The anomaly was primarily driven by a sharp change in session activity compared to expected behavior',
    'session_count_roll3': 'The anomaly was primarily driven by a sustained change in session activity over the past 3 days',
    'purchase_count': 'A significant change in purchase behavior contributed to this anomaly',
    'purchase_count_roll3': 'A sustained shift in purchase patterns over the past 3 days contributed to this anomaly',
    'event_count': 'A notable change in overall event volume was detected',
    'event_count_roll3': 'Event volume has deviated from normal patterns over the past 3 days',
    'error_count': 'A spike in error rates was detected as a contributing factor',
    'error_count_roll3': 'Error rates have been elevated over the past 3 days',
    'click_count': 'Click activity deviated from expected patterns',
    'click_count_roll3': 'Click patterns have shifted over the past 3 days',
    'login_count': 'Login activity showed unusual patterns',
    'active_hours': 'User active hours deviated from normal patterns',
    'error_rate': 'Error rate was a significant contributing factor',
    'weekend_event_count': 'Unusual weekend usage patterns contributed to the anomaly',
    'distinct_event_types': 'The variety of user actions changed compared to normal behavior',
    'events_per_session': 'Event density per session changed significantly',
}

# Rule-based recommendations keyed on feature name (ordered by priority)
FEATURE_RECOMMENDATIONS = {
    'session_count': {
        'title': 'Session Count Drop',
        'causes': [
            'Login flow may be broken',
            'CDN or DNS outage reducing traffic',
            'Tracking SDK stopped firing session events',
            'Marketing campaign ended — organic traffic dropped',
        ],
    },
    'session_count_roll3': {
        'title': '3-Day Avg Sessions Declining',
        'causes': [
            'Sustained traffic decline — check acquisition channels',
            'Login or authentication issues',
            'SDK misconfiguration introduced in a recent deploy',
        ],
    },
    'purchase_count': {
        'title': 'Purchase Count Drop',
        'causes': [
            'Payment gateway failure or timeout',
            'Checkout page bug (JS error, broken form)',
            'Pricing or promo code issue',
            'Inventory or stock-out problem',
        ],
    },
    'purchase_count_roll3': {
        'title': '3-Day Avg Purchases Declining',
        'causes': [
            'Sustained drop in conversion — review funnel',
            'Recent UI change breaking checkout flow',
            'Payment provider reliability issue',
        ],
    },
    'event_count': {
        'title': 'Event Volume Drop',
        'causes': [
            'Analytics SDK stopped sending events',
            'Event pipeline or Kafka consumer issue',
            'Production deployment may have broken event tracking',
            'Ad blocker uptick removing client-side events',
        ],
    },
    'event_count_roll3': {
        'title': '3-Day Avg Event Volume Low',
        'causes': [
            'Analytics SDK misconfiguration',
            'Ingestion pipeline backlog or failure',
            'User engagement dropping — review content or features',
        ],
    },
    'error_count': {
        'title': 'Error Rate Spike',
        'causes': [
            'Production deployment introduced a regression',
            'Third-party API or service is failing',
            'Database or cache connection issues',
            'Frontend JavaScript errors spiking',
        ],
    },
    'error_count_roll3': {
        'title': '3-Day Avg Errors Elevated',
        'causes': [
            'Ongoing backend stability issue',
            'Memory leak or resource exhaustion',
            'Infrastructure scaling problem',
        ],
    },
    'error_rate': {
        'title': 'Error Rate Elevated',
        'causes': [
            'High-frequency error from a specific endpoint',
            'External dependency degraded',
            'Load spike exposing latency bugs',
        ],
    },
    'login_count': {
        'title': 'Login Activity Anomaly',
        'causes': [
            'Authentication service issue',
            'Credential stuffing or brute-force attack',
            'SSO provider outage',
            'Session expiry misconfiguration',
        ],
    },
    'active_hours': {
        'title': 'Active Hours Pattern Changed',
        'causes': [
            'Time-zone or daylight saving time issue in event timestamps',
            'User behavior shift (e.g., new region coming online)',
            'Scheduled maintenance window unexpectedly long',
        ],
    },
    'click_count': {
        'title': 'Click Activity Anomaly',
        'causes': [
            'UI element rendering issue hiding interactive components',
            'A/B test variant removing clickable elements',
            'Bot or click-fraud traffic change',
        ],
    },
    'click_count_roll3': {
        'title': '3-Day Avg Clicks Changed',
        'causes': [
            'Feature rollout affecting user interaction patterns',
            'Navigation redesign reducing required clicks',
        ],
    },
}


class AnomalyAutoencoder(nn.Module):
    def __init__(self, input_dim, hidden_dims=None):
        super().__init__()
        hidden_dims = hidden_dims or [64, 32, 16]
        encoder_layers = []
        dims = [input_dim, *hidden_dims]
        for left, right in zip(dims[:-1], dims[1:]):
            encoder_layers.extend([nn.Linear(left, right), nn.ReLU()])
        decoder_dims = [*hidden_dims[::-1], input_dim]
        decoder_layers = []
        for left, right in zip(decoder_dims[:-1], decoder_dims[1:]):
            decoder_layers.extend([nn.Linear(left, right), nn.ReLU()])
        if decoder_layers:
            decoder_layers.pop()
        self.encoder = nn.Sequential(*encoder_layers)
        self.decoder = nn.Sequential(*decoder_layers)

    def forward(self, x):
        return self.decoder(self.encoder(x))


class AnomalyDetectionService:
    """Product Health Monitor — Behavioral anomaly detection service.

    This service builds project-level time-windowed behavior features from
    ClickHouse event data and scores them with a dense autoencoder when a trained
    checkpoint is available. Until training artifacts are generated, it falls
    back to a stable heuristic score so the dashboard and batch pipeline can
    still run.

    Enriched output includes:
    - Severity (Normal / Low / Medium / High / Critical) based on score/threshold ratio
    - Expected vs Actual: decoded reconstruction as the "expected" values
    - Feature contributions: per-feature absolute reconstruction error (%)
    - Rule-based recommendations from top features
    - System status card
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._reset_state()
        return cls._instance

    def _reset_state(self):
        self._model = None
        self._feature_columns = None
        self._feature_mean = None
        self._feature_scale = None
        self._threshold = None
        self._checkpoint = None

    @property
    def loaded(self):
        return self._model is not None

    def load(self, model_path=None):
        if self._model is not None:
            return True

        checkpoint_path = model_path or MODEL_PATH
        if not os.path.exists(checkpoint_path):
            logger.info('No product health checkpoint found at %s', checkpoint_path)
            return False

        try:
            checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
            feature_columns = checkpoint.get('feature_columns', [])
            if not feature_columns:
                logger.warning('Anomaly checkpoint is missing feature columns')
                return False

            hidden_dims = checkpoint.get('hidden_dims', [64, 32, 16])
            model = AnomalyAutoencoder(len(feature_columns), hidden_dims=hidden_dims)
            model.load_state_dict(checkpoint['model_state_dict'])
            model.eval()

            self._model = model
            self._feature_columns = feature_columns
            self._feature_mean = np.asarray(checkpoint.get('feature_mean', []), dtype=np.float32)
            self._feature_scale = np.asarray(checkpoint.get('feature_scale', []), dtype=np.float32)
            self._threshold = float(checkpoint.get('threshold', 0.0) or 0.0)
            self._checkpoint = checkpoint
            logger.info('Anomaly model loaded from %s', checkpoint_path)
            return True
        except Exception as exc:
            logger.exception('Failed to load anomaly model: %s', exc)
            self._reset_state()
            return False

    # ------------------------------------------------------------------
    # Enrichment helpers
    # ------------------------------------------------------------------

    def _severity_from_ratio(self, ratio):
        """Map reconstruction_error / threshold → severity label."""
        if ratio < 1.0:
            return 'normal'
        elif ratio < 1.2:
            return 'low'
        elif ratio < 1.5:
            return 'medium'
        elif ratio < 2.0:
            return 'high'
        else:
            return 'critical'

    def _label_feature(self, feature_name):
        return FEATURE_LABELS.get(feature_name, feature_name.replace('_', ' ').title())

    def _feature_contributions(self, feature_errors, feature_columns):
        """
        Return top contributing features with percentages summing to 100%.
        Filters out engineered features (day_of_week, is_weekend, etc.)
        and groups related features (e.g. weekend_event_count → Weekend Activity).
        """
        grouped = {}
        remaining = []
        for i, name in enumerate(feature_columns):
            if name in ENGINEERED_FEATURES:
                continue
            error_val = float(feature_errors[i])
            if name in FEATURE_GROUPINGS:
                group_name = FEATURE_GROUPINGS[name]
                grouped[group_name] = grouped.get(group_name, 0.0) + error_val
            else:
                remaining.append((name, error_val))

        all_items = [(name, error) for name, error in remaining]
        for group_name, error in grouped.items():
            all_items.append((group_name, error))

        all_items.sort(key=lambda x: x[1], reverse=True)
        top_items = all_items[:5]

        total = sum(error for _, error in top_items)
        if total == 0:
            return []

        contributions = []
        for name, error in top_items:
            pct = round(error / total * 100, 1)
            label = FEATURE_LABELS.get(name, name.replace('_', ' ').title())
            contributions.append({
                'feature': name,
                'label': label,
                'contribution_pct': pct,
                'error': round(error, 4),
            })

        return contributions

    def _expected_vs_actual(self, actual_row, reconstruction_row, feature_columns, mean, scale):
        """
        Build expected-vs-actual comparison.
        'Expected' = autoencoder decoder output de-normalised back to original scale.
        'Actual'   = raw feature value.
        Excludes engineered features from output.
        """
        result = []
        for i, name in enumerate(feature_columns):
            if name in ENGINEERED_FEATURES:
                continue
            actual_val = float(actual_row[i])
            expected_val = float(reconstruction_row[i]) * float(scale[i]) + float(mean[i])
            delta = actual_val - expected_val
            delta_pct = round((delta / max(abs(expected_val), 1e-6)) * 100, 1)
            direction = '↓' if delta < 0 else '↑' if delta > 0 else '→'
            label = FEATURE_LABELS.get(name, name.replace('_', ' ').title())
            result.append({
                'feature': name,
                'label': label,
                'actual': round(actual_val, 2),
                'expected': round(expected_val, 2),
                'delta_pct': abs(delta_pct),
                'direction': direction,
            })
        result.sort(key=lambda x: x['delta_pct'], reverse=True)
        return result[:8]

    def _generate_recommendations(self, top_features):
        """
        Rule-based recommendations derived from top contributing feature names.
        Returns a list of {title, causes, fixes} dicts.
        """
        recommendations = []
        
        def get_suggestions_and_fixes_for_feature(feature_name, direction=""):
            """Get detailed suggestions and specific fixes for a feature."""
            suggestions_map = {
                'session_count': {
                    'title': 'Session Count Drop',
                    'description': 'Analyze user session patterns and identify barriers to engagement',
                    'suggestions': [
                        'Login flow may be broken',
                        'CDN or DNS outage reducing traffic',
                        'Tracking SDK stopped firing session events',
                        'Marketing campaign ended — organic traffic dropped',
                    ],
                    'fixes': [
                        'Audit login forms for errors and improve UX',
                        'Check CDN status and deploy to backup if needed',
                        'Restart analytics/tracking SDK services',
                        'Diversify traffic sources and review marketing channels',
                    ],
                },
                'session_count_roll3': {
                    'title': '3-Day Avg Sessions Declining',
                    'description': 'Investigate sustained traffic trends and user engagement patterns',
                    'suggestions': [
                        'Sustained traffic decline — check acquisition channels',
                        'Login or authentication issues',
                        'SDK misconfiguration introduced in a recent deploy',
                    ],
                    'fixes': [
                        'Review acquisition channels for user drop-off',
                        'Test authentication flows and restore if broken',
                        'Deploy SDK fixes and verify event tracking',
                    ],
                },
                'purchase_count': {
                    'title': 'Purchase Count Drop',
                    'description': 'Identify barriers in the conversion funnel',
                    'suggestions': [
                        'Payment gateway failure or timeout',
                        'Checkout page bug (JS error, broken form)',
                        'Pricing or promo code issue',
                        'Inventory or stock-out problem',
                    ],
                    'fixes': [
                        'Test payment gateways and enable fallback payments',
                        'Audit checkout forms, fix JS errors, and simplify fields',
                        'Verify pricing and promo code systems',
                        'Check inventory and fix stock-out alerts',
                    ],
                },
                'purchase_count_roll3': {
                    'title': '3-Day Avg Purchases Declining',
                    'description': 'Analyze long-term conversion trends and recent changes',
                    'suggestions': [
                        'Sustained drop in conversion — review funnel',
                        'Recent UI change breaking checkout flow',
                        'Payment provider reliability issue',
                    ],
                    'fixes': [
                        'Analyze conversion funnel drop-off points',
                        'Revert or fix recent UI/checkout changes',
                        'Contact payment provider and have backup options',
                    ],
                },
                'event_count': {
                    'title': 'Event Volume Drop',
                    'description': 'Diagnose event pipeline and analytics issues',
                    'suggestions': [
                        'Analytics SDK stopped sending events',
                        'Event pipeline or Kafka consumer issue',
                        'Production deployment may have broken event tracking',
                        'Ad blocker uptick removing client-side events',
                    ],
                    'fixes': [
                        'Restart analytics SDK services and check logs',
                        'Inspect event pipeline status and fix consumers',
                        'Rollback breaking deployments or fix tracking bugs',
                        'Provide user guidance on ad blocker exceptions',
                    ],
                },
                'event_count_roll3': {
                    'title': '3-Day Avg Event Volume Low',
                    'description': 'Evaluate analytics infrastructure and user engagement',
                    'suggestions': [
                        'Analytics SDK misconfiguration',
                        'Ingestion pipeline backlog or failure',
                        'User engagement dropping — review content or features',
                    ],
                    'fixes': [
                        'Verify SDK configuration and event sampling',
                        'Monitor and scale event ingestion infrastructure',
                        'Review content, features, and user feedback',
                    ],
                },
                'error_count': {
                    'title': 'Error Rate Spike',
                    'description': 'Address system stability and reliability issues',
                    'suggestions': [
                        'Production deployment introduced a regression',
                        'Third-party API or service is failing',
                        'Database or cache connection issues',
                        'Frontend JavaScript errors spiking',
                    ],
                    'fixes': [
                        'Deploy rollback or hotfix for recent changes',
                        'Check third-party APIs and configure fallbacks',
                        'Verify database and cache connectivity',
                        'Audit frontend for JS errors and fix critical bugs',
                    ],
                },
                'login_count': {
                    'title': 'Login Activity Anomaly',
                    'description': 'Review authentication system and security events',
                    'suggestions': [
                        'Authentication service issue',
                        'Credential stuffing or brute-force attack',
                        'SSO provider outage',
                        'Session expiry misconfiguration',
                    ],
                    'fixes': [
                        'Check authentication service health',
                        'Implement rate limiting and account lockouts',
                        'Verify SSO configuration and connectivity',
                        'Adjust session timeouts and renewal policies',
                    ],
                },
            }
            
            return suggestions_map.get(feature_name, {
                'title': FEATURE_RECOMMENDATIONS.get(feature_name, {}).get('title', feature_name.replace('_', ' ').title()),
                'description': 'Investigate this metric for abnormal behavior',
                'suggestions': FEATURE_RECOMMENDATIONS.get(feature_name, {}).get('causes', []),
                'fixes': ['Review system logs and identify root cause'],
            })
        
        # Process top features in order of importance
        for item in top_features[:3]:
            feature_name = item['feature']
            
            # Skip if we've already handled this feature type
            if any(rec['title'].replace('3-Day Avg ', '') in feature_name or rec['title'] == feature_name.replace('_', ' ').title() 
                   for rec in recommendations):
                continue
            
            # Get suggestions and fixes
            rec_data = get_suggestions_and_fixes_for_feature(feature_name, item.get('direction', ''))
            
            # Add direction to title if provided
            title = rec_data['title']
            if item.get('direction'):
                title = f"{title} {item['direction']}"
            
            recommendations.append({
                'title': title,
                'description': rec_data['description'],
                'suggestions': rec_data['suggestions'],
                'fixes': rec_data['fixes'],
            })
            
            break  # Only return top recommendation
        
        # Fallback to generic recommendations if no specific ones found
        if not recommendations:
            for item in top_features[:2]:
                feature_name = item['feature']
                
                # Get suggestions and fixes for fallback
                rec_data = get_suggestions_and_fixes_for_feature(feature_name, item.get('direction', ''))
                
                title = rec_data['title']
                if item.get('direction'):
                    title = f"{title} {item['direction']}"
                
                recommendations.append({
                    'title': title,
                    'description': rec_data['description'],
                    'suggestions': rec_data['suggestions'],
                    'fixes': rec_data['fixes'],
                })
        
        return recommendations

    def _describe_anomaly(self, contributions, score, threshold):
        """
        Build a short human-readable reason string for an anomaly.
        Uses top contributing features so description aligns with the UI.
        """
        if not contributions:
            return 'Unusual behavioral pattern detected.'
        top_feature = contributions[0]['feature']
        base_desc = PRODUCT_DESCRIPTIONS.get(top_feature, 'A notable behavioral anomaly was detected')
        parts = []
        for item in contributions[:3]:
            label = item['label']
            pct = item['contribution_pct']
            parts.append(f"{label} {pct:.0f}%")
        ratio = score / max(threshold, 1e-9)
        suffix = f' (score/threshold ratio: {ratio:.2f})'
        return f"{base_desc}, with top contributors: {', '.join(parts)}.{suffix}"

    # ------------------------------------------------------------------
    # ClickHouse helpers
    # ------------------------------------------------------------------

    def _ensure_table(self):
        from events.clickhouse import ch

        if not ch.available:
            return False

        client = ch.get_client()
        if not client:
            return False

        ref = f'{ch._database}.{SCORE_TABLE}'
        client.command(f'''
            CREATE TABLE IF NOT EXISTS {ref} (
                project_id UInt32,
                user_id String,
                window_start Date,
                window_end Date,
                anomaly_score Float32,
                anomaly_confidence Float32,
                is_anomaly UInt8,
                threshold Float32,
                top_features String,
                feature_version String,
                model_version String,
                computed_at DateTime64(6)
            ) ENGINE = ReplacingMergeTree(computed_at)
            ORDER BY (project_id, window_end, anomaly_score, user_id)
        ''')
        return True

    def _query_events(self, project_id, days=60):
        from events.clickhouse import ch

        start_date = date.today() - timedelta(days=days)
        try:
            client = ch.get_client()
            if client:
                rows = client.query(
                    '''
                    SELECT
                        timestamp,
                        event_name,
                        JSONExtractString(properties, '$session_id') AS session_id,
                        properties
                    FROM insightflow.events
                    WHERE project_id = %(pid)s AND toDate(timestamp) >= %(start)s
                    ORDER BY timestamp
                    ''',
                    parameters={'pid': project_id, 'start': start_date.isoformat()},
                )
                if rows and rows.result_rows:
                    return pd.DataFrame(
                        rows.result_rows,
                        columns=['timestamp', 'event_name', 'session_id', 'properties'],
                    )
        except Exception as exc:
            logger.warning('ClickHouse anomaly query failed: %s', exc)

        try:
            from events.models import Event

            qs = Event.objects.filter(project_id=project_id, timestamp__date__gte=start_date).order_by('timestamp')
            records = []
            for row in qs:
                properties = row.properties or {}
                records.append({
                    'timestamp': row.timestamp,
                    'event_name': row.event_name,
                    'session_id': properties.get('$session_id', ''),
                    'properties': json.dumps(properties),
                })
            return pd.DataFrame(records)
        except Exception as exc:
            logger.warning('PostgreSQL anomaly query failed: %s', exc)
            return pd.DataFrame()

    def _build_feature_frame(self, df):
        if df.empty:
            return df

        frame = df.copy()
        frame['timestamp'] = pd.to_datetime(frame['timestamp'], errors='coerce')
        frame = frame.dropna(subset=['timestamp'])
        if frame.empty:
            return frame

        frame['window_start'] = frame['timestamp'].dt.floor('D')
        frame['event_name'] = frame['event_name'].fillna('').astype(str)
        frame['session_id'] = frame['session_id'].fillna('').astype(str)

        rows = []
        for window_start, group in frame.groupby('window_start', sort=True):
            ordered = group.sort_values('timestamp')
            timestamps = ordered['timestamp']
            diffs = timestamps.diff().dt.total_seconds().dropna()
            event_names = ordered['event_name'].str.lower()
            session_count = int(ordered['session_id'].replace('', np.nan).nunique(dropna=True))
            event_count = int(len(ordered))
            error_count = int(event_names.str.contains('error|fail|exception|500', regex=True, na=False).sum())
            click_count = int(event_names.str.contains('click', regex=False, na=False).sum())
            login_count = int(event_names.str.contains('login|sign_in', regex=True, na=False).sum())
            purchase_count = int(event_names.str.contains('purchase|checkout|order|subscribe|upgrade', regex=True, na=False).sum())
            distinct_event_types = int(ordered['event_name'].nunique())
            active_hours = int(ordered['timestamp'].dt.hour.nunique())
            avg_gap_seconds = float(diffs.mean()) if not diffs.empty else 0.0
            max_gap_seconds = float(diffs.max()) if not diffs.empty else 0.0
            inactive_hours = float((pd.Timestamp(window_start) + pd.Timedelta(days=1) - ordered['timestamp'].max()).total_seconds() / 3600.0)
            weekend_event_count = int(ordered['timestamp'].dt.dayofweek.isin([5, 6]).sum())
            day_of_week = int(pd.Timestamp(window_start).dayofweek)
            is_weekend = int(day_of_week in (5, 6))
            events_per_session = float(event_count / max(session_count, 1))
            error_rate = float(error_count / max(event_count, 1))

            rows.append({
                'window_start': pd.Timestamp(window_start).date(),
                'event_count': event_count,
                'session_count': session_count,
                'click_count': click_count,
                'login_count': login_count,
                'purchase_count': purchase_count,
                'error_count': error_count,
                'distinct_event_types': distinct_event_types,
                'active_hours': active_hours,
                'avg_gap_seconds': avg_gap_seconds,
                'max_gap_seconds': max_gap_seconds,
                'inactive_hours': inactive_hours,
                'events_per_session': events_per_session,
                'error_rate': error_rate,
                'weekend_event_count': weekend_event_count,
                'day_of_week': day_of_week,
                'is_weekend': is_weekend,
            })

        feature_frame = pd.DataFrame(rows).sort_values(['window_start']).reset_index(drop=True)
        if feature_frame.empty:
            return feature_frame

        rolling_columns = [
            'event_count', 'session_count', 'click_count', 'purchase_count', 'error_count',
        ]
        for column in rolling_columns:
            feature_frame[f'{column}_roll3'] = feature_frame[column].shift(1).rolling(3, min_periods=1).mean().fillna(0.0)

        feature_frame = feature_frame.fillna(0)
        return feature_frame

    def _feature_columns_for_frame(self, frame):
        if self._feature_columns:
            return [column for column in self._feature_columns if column in frame.columns]

        numeric_columns = [
            'event_count', 'session_count', 'click_count', 'login_count', 'purchase_count',
            'error_count', 'distinct_event_types', 'active_hours', 'avg_gap_seconds',
            'max_gap_seconds', 'inactive_hours', 'events_per_session', 'error_rate',
            'weekend_event_count', 'day_of_week', 'is_weekend', 'event_count_roll3',
            'session_count_roll3', 'click_count_roll3', 'purchase_count_roll3',
            'error_count_roll3',
        ]
        return [column for column in numeric_columns if column in frame.columns]

    def _score_frame(self, frame):
        feature_columns = self._feature_columns_for_frame(frame)
        if not feature_columns:
            return frame, []

        matrix = frame[feature_columns].to_numpy(dtype=np.float32)
        if self._feature_mean is not None and len(self._feature_mean) == len(feature_columns):
            mean = self._feature_mean
        else:
            mean = matrix.mean(axis=0)

        if self._feature_scale is not None and len(self._feature_scale) == len(feature_columns):
            scale = self._feature_scale.copy()
        else:
            scale = matrix.std(axis=0)
        scale = np.where(scale == 0, 1.0, scale)

        normalized = (matrix - mean) / scale

        if self._model is not None:
            with torch.no_grad():
                tensor = torch.tensor(normalized, dtype=torch.float32)
                reconstruction_normalized = self._model(tensor).cpu().numpy()
            feature_errors = np.abs(normalized - reconstruction_normalized)
            scores = np.mean((normalized - reconstruction_normalized) ** 2, axis=1)
            score_source = 'autoencoder'
        else:
            # Heuristic: reconstruction is the column mean (normalised → 0)
            reconstruction_normalized = np.zeros_like(normalized)
            feature_errors = np.abs(normalized)
            scores = np.mean(feature_errors, axis=1)
            score_source = 'heuristic'

        threshold = self._threshold or float(np.percentile(scores, 95))
        threshold = max(threshold, 1e-6)

        results = []
        for index, row in frame.iterrows():
            score = float(scores[index])
            row_errors = feature_errors[index]
            ratio = score / threshold

            # Severity
            severity = self._severity_from_ratio(ratio)

            # Top features (by per-feature reconstruction error)
            top_indices = np.argsort(row_errors)[::-1][:5]
            top_features_raw = []
            for fi in top_indices:
                fname = feature_columns[fi]
                top_features_raw.append({
                    'feature': fname,
                    'label': self._label_feature(fname),
                    'error': round(float(row_errors[fi]), 4),
                    'value': round(float(matrix[index][fi]), 4),
                })

            # Feature contributions (%)
            contributions = self._feature_contributions(row_errors, feature_columns)

            # Expected vs Actual (decoder output de-normalised)
            ev_actual = self._expected_vs_actual(
                actual_row=matrix[index],
                reconstruction_row=reconstruction_normalized[index],
                feature_columns=feature_columns,
                mean=mean,
                scale=scale,
            )

            # Recommendations
            recs = self._generate_recommendations(contributions[:3])

            # Description / reason (uses contributions to stay aligned)
            description = self._describe_anomaly(contributions, score, threshold)

            results.append({
                'user_id': row.get('user_id', ''),
                'window_start': row['window_start'].isoformat(),
                'anomaly_score': round(score, 6),
                'reconstruction_error': round(score, 6),
                'threshold': round(float(threshold), 6),
                'ratio': round(ratio, 4),
                'severity': severity,
                'is_anomaly': bool(score >= threshold),
                'top_features': top_features_raw,
                'feature_contributions': contributions,
                'expected_vs_actual': ev_actual,
                'recommendations': recs,
                'description': description,
                'feature_version': FEATURE_VERSION,
                'model_version': MODEL_VERSION,
                'score_source': score_source,
            })

        return results, feature_columns

    # ------------------------------------------------------------------
    # Aggregation / summary
    # ------------------------------------------------------------------

    def _system_status(self, anomalies, scores):
        """Return a single status card for the top of the dashboard."""
        if not anomalies:
            days_clean = len(scores)
            return {
                'status': 'healthy',
                'label': '🟢 Healthy',
                'message': f'No anomalies detected in the last {days_clean} days.',
            }
        latest = anomalies[-1]
        sev = latest.get('severity', 'low')
        sev_icon = {'low': '🟡', 'medium': '🟡', 'high': '🔴', 'critical': '⚫'}.get(sev, '🔴')
        return {
            'status': 'incident',
            'label': f'{sev_icon} Incident Active',
            'message': f'{sev.capitalize()}-severity anomaly detected on {latest["window_start"]}. {latest.get("description", "")}',
            'severity': sev,
            'latest_date': latest['window_start'],
        }

    def _aggregate_summary(self, scores):
        if not scores:
            return {
                'total_scored': 0,
                'anomaly_count': 0,
                'anomaly_rate': 0.0,
                'threshold': 0.0,
                'top_features': [],
                'system_status': {
                    'status': 'healthy',
                    'label': '🟢 Healthy',
                    'message': 'No data available yet.',
                },
            }

        anomalies = [row for row in scores if row['is_anomaly']]

        feature_totals = {}
        for row in anomalies:
            for item in row['feature_contributions']:
                key = item['feature']
                if key in ENGINEERED_FEATURES:
                    continue
                feature_totals[key] = feature_totals.get(key, 0.0) + item['error']

        top_total = sum(feature_totals.values())
        top_features = [
            {
                'feature': feature,
                'label': self._label_feature(feature),
                'score': round(total / top_total * 100, 1) if top_total > 0 else 0,
            }
            for feature, total in sorted(feature_totals.items(), key=lambda item: item[1], reverse=True)[:6]
        ]

        return {
            'total_scored': len(scores),
            'anomaly_count': len(anomalies),
            'anomaly_rate': round(len(anomalies) / len(scores), 4),
            'threshold': round(float(scores[0]['threshold']), 6),
            'top_features': top_features,
            'system_status': self._system_status(anomalies, scores),
        }

    def _build_timeline(self, scores):
        """Daily anomaly counts and scores for the timeline chart."""
        daily = {}
        for row in scores:
            d = row['window_start']
            if d not in daily:
                daily[d] = {
                    'date': d,
                    'anomaly_count': 0,
                    'max_score': 0.0,
                    'severity': 'normal',
                }
            if row['is_anomaly']:
                daily[d]['anomaly_count'] += 1
                if row['anomaly_score'] > daily[d]['max_score']:
                    daily[d]['max_score'] = round(row['anomaly_score'], 4)
                    daily[d]['severity'] = row['severity']
        return sorted(daily.values(), key=lambda x: x['date'])

    def _build_recent_anomalies(self, scores):
        """Return enriched anomaly rows for the incident table."""
        anomalies = [row for row in scores if row['is_anomaly']]
        # Sort most-recent first
        anomalies.sort(key=lambda x: x['window_start'], reverse=True)
        result = []
        for row in anomalies[:20]:
            result.append({
                'date': row['window_start'],
                'severity': row['severity'],
                'description': row['description'],
                'anomaly_score': row['anomaly_score'],
                'reconstruction_error': row['reconstruction_error'],
                'threshold': row['threshold'],
                'ratio': row['ratio'],
                'expected_vs_actual': row['expected_vs_actual'][:5],
                'feature_contributions': row['feature_contributions'][:5],
                'recommendations': row['recommendations'],
                'score_source': row['score_source'],
            })
        return result

    def _build_incident_log(self, project_id, scores):
        """
        Persist new anomaly incidents to DB and return the recent incident log.
        Uses get_or_create so re-runs don't duplicate rows.
        """
        try:
            from dashboard.models import AnomalyIncident

            for row in scores:
                if not row['is_anomaly']:
                    continue
                window_date = row['window_start']
                if isinstance(window_date, str):
                    from datetime import date as dt_date
                    window_date = dt_date.fromisoformat(window_date)

                incident, created = AnomalyIncident.objects.get_or_create(
                    project_id=project_id,
                    window_start=window_date,
                    defaults={
                        'severity': row['severity'],
                        'score': row['anomaly_score'],
                        'threshold': row['threshold'],
                        'description': row['description'],
                        'top_features': row['feature_contributions'][:5],
                        'recommendations': row['recommendations'],
                        'status': 'open',
                    },
                )
                # Update score/severity if anomaly got worse on a re-run
                if not created and row['anomaly_score'] > incident.score:
                    incident.severity = row['severity']
                    incident.score = row['anomaly_score']
                    incident.description = row['description']
                    incident.save(update_fields=['severity', 'score', 'description'])

            # Return most-recent incidents for this project
            qs = AnomalyIncident.objects.filter(project_id=project_id).order_by('-window_start')[:20]
            return [
                {
                    'id': inc.id,
                    'date': str(inc.window_start),
                    'severity': inc.severity,
                    'score': inc.score,
                    'description': inc.description,
                    'status': inc.status,
                    'resolved_at': str(inc.resolved_at) if inc.resolved_at else None,
                    'created_at': str(inc.created_at),
                }
                for inc in qs
            ]
        except Exception as exc:
            logger.warning('Incident log error: %s', exc)
            return []

    def _store_scores(self, project_id, scores):
        from events.clickhouse import ch

        if not scores:
            return

        if not self._ensure_table():
            return

        client = ch.get_client()
        if not client:
            return

        ref = f'{ch._database}.{SCORE_TABLE}'
        now_dt = datetime.now()
        batch = []
        for row in scores:
            window_start = pd.to_datetime(row['window_start']).date()
            top_features = json.dumps(row.get('top_features', []), default=str)
            batch.append((
                int(project_id),
                '',
                window_start,
                window_start,
                float(row['anomaly_score']),
                float(row['ratio']),
                int(bool(row['is_anomaly'])),
                float(row['threshold']),
                top_features,
                row['feature_version'],
                row['model_version'],
                now_dt,
            ))

        client.insert(
            ref,
            batch,
            column_names=[
                'project_id', 'user_id', 'window_start', 'window_end',
                'anomaly_score', 'anomaly_confidence', 'is_anomaly', 'threshold',
                'top_features', 'feature_version', 'model_version', 'computed_at',
            ],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_batch(self, project_id, days=60, store=True):
        raw = self._query_events(project_id, days=days)
        frame = self._build_feature_frame(raw)
        if frame.empty:
            return None

        scores, feature_columns = self._score_frame(frame)
        if not scores:
            return None

        if store:
            self._store_scores(project_id, scores)

        summary = self._aggregate_summary(scores)
        summary.update({
            'project_id': int(project_id),
            'window_days': int(days),
            'feature_version': FEATURE_VERSION,
            'model_version': MODEL_VERSION,
            'score_source': scores[0]['score_source'],
            'feature_columns': feature_columns,
            'generated_at': datetime.now().isoformat(),
        })

        return {
            'summary': summary,
            'scores': scores,
        }

    def get_summary(self, project_id, days=14, store_incidents=True):
        """
        Returns a production-grade structured response:
        {
            summary: {...},
            recent_anomalies: [...],
            timeline: [...],
            incident_log: [...],
        }
        """
        result = self.run_batch(project_id, days=days, store=False)
        if not result:
            return None

        scores = result['scores']
        summary = result['summary']

        recent_anomalies = self._build_recent_anomalies(scores)
        timeline = self._build_timeline(scores)
        incident_log = self._build_incident_log(project_id, scores) if store_incidents else []

        return {
            'summary': summary,
            'recent_anomalies': recent_anomalies,
            'timeline': timeline,
            'incident_log': incident_log,
        }


anomaly_detection = AnomalyDetectionService()