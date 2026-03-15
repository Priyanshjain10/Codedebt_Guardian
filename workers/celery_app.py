"""
CodeDebt Guardian — Celery Application Configuration
Redis-backed task queue for background analysis, embedding, and PR generation.
"""

from celery import Celery
from config import settings
from utils.logger import setup_structured_logging

setup_structured_logging()

celery_app = Celery(
    "codedebt",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,  # 5 min soft limit
    task_time_limit=600,       # 10 min hard limit
    task_routes={
        "workers.tasks.run_scan_analysis": {"queue": "analysis"},
        "workers.tasks.generate_embeddings": {"queue": "embeddings"},
        "workers.tasks.create_fix_pr": {"queue": "pr"},
        "workers.pr_tasks.process_pr_event": {"queue": "pr"},
    },
    beat_schedule={
        "scheduled-scans": {
            "task": "workers.tasks.run_scheduled_scans",
            "schedule": 3600.0,  # Every hour
        },
    },
)

celery_app.autodiscover_tasks(["workers"])
