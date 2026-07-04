"""
Pre-compute churn predictions and cache to disk.

Usage:
    python manage.py update_churn_cache --project_id 14
"""

import json
import os
import time
from datetime import datetime

from django.core.management.base import BaseCommand
from django.conf import settings

from ml.services.churn_risk import churn_risk


class Command(BaseCommand):
    help = 'Pre-compute churn predictions and cache to file'

    def add_arguments(self, parser):
        parser.add_argument('--project_id', type=int, default=14)

    def handle(self, *args, **options):
        project_id = options['project_id']
        t0 = time.time()

        self.stdout.write('Loading model...')
        if not churn_risk.load():
            self.stderr.write('ERROR: Model not available')
            return

        self.stdout.write(f'Generating predictions for project {project_id}...')
        predictions = churn_risk.predict_all(project_id)
        if not predictions:
            self.stderr.write('ERROR: No predictions generated')
            return

        overview = churn_risk.get_overview(predictions)
        timeline = churn_risk.get_churn_timeline(predictions)
        recommendations = churn_risk.get_recommendations(predictions, project_id)

        cache = {
            "overview": overview,
            "predictions": predictions[:500],
            "timeline": timeline,
            "recommendations": recommendations,
            "generated_at": datetime.now().isoformat(),
        }

        cache_path = os.path.join(settings.BASE_DIR, 'ml', 'models', 'artifacts', 'churn_cache.json')
        with open(cache_path, 'w') as f:
            json.dump(cache, f, indent=2, default=str)

        elapsed = time.time() - t0
        self.stdout.write(f'Cached {len(predictions)} predictions to {cache_path}')
        self.stdout.write(f'  High: {overview["high_risk"]} Med: {overview["medium_risk"]} Low: {overview["low_risk"]}')
        self.stdout.write(f'  Avg risk: {overview["avg_risk_probability"]}')
        self.stdout.write(f'  Predicted churn 30d: {timeline["next_30_days"]}')
        self.stdout.write(f'  Recommendations: {len(recommendations["recommendations"])}')
        self.stdout.write(f'Completed in {elapsed:.1f}s')
