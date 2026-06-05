from celery import Celery
from kombu import Exchange, Queue
from loguru import logger

from settings import settings

celery_app = Celery(
    "app_celery",
    broker=settings.celery.celery_broker_url,
    backend=settings.celery.celery_redis_url,
    include=["src.app_celery.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
)

celery_app.conf.update(
    task_time_limit=8 * 60 * 60,
    task_soft_time_limit=8 * 60 * 60,
)

celery_app.conf.update(
    broker_connection_retry=True,
    broker_connection_max_retries=100,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.update(
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("high_priority", Exchange("high_priority"), routing_key="high_priority"),
        Queue("low_priority", Exchange("low_priority"), routing_key="low_priority"),
    ),
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
    task_routes={
        "send_message_task": {"queue": "high_priority"},
        "schedule_message_task": {"queue": "default"},
        "heavy_computation_task": {"queue": "low_priority"},
    },
)

celery_app.conf.update(
    task_send_sent_event=True,
    task_send_received_event=True,
    task_send_started_event=True,
    task_send_success_event=True,
    task_send_failure_event=True,
    task_send_retry_event=True,
    task_send_revoked_event=True,
    flower_port=settings.flowers.flower_port,
    flower_basic_auth=settings.flowers.flower_auth,
)

logger.info(f"Celery app configured with broker: {settings.celery.celery_broker_url}")
logger.info(f"Queues configured: {[q.name for q in celery_app.conf.task_queues]}")
