import atexit
import sys
import time

import requests
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.db.crud import update_max_rejection, update_telegram_rejection
from src.sender.model import UrlForList

scheduler = BackgroundScheduler(job_defaults=dict(coalesce=True, misfire_grace_time=3600, max_instances=1))


def job_listener(event):
    if event.exception:
        logger.error(f"Job {event.job_id} failed: {event.exception}")
    else:
        logger.info(f"Job {event.job_id} executed successfully at {event.scheduled_run_time}")


scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)


def _run_449_list():
    list_url = [
        UrlForList.telegram_no_expath.value,
        UrlForList.max_expath.value,
        UrlForList.max_no_expath.value,
        UrlForList.telegram_expath.value,
    ]

    for url in list_url:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                logger.info(f"✅ Успех: {r.url}")
            else:
                logger.warning(f"⚠️ Статус {r.status_code} для {url}")
        except Exception as e:
            logger.error(f"❌ Ошибка {url}: {e}")

    return


try:
    scheduler.add_job(
        func=update_max_rejection,
        trigger=CronTrigger(hour=6, minute=0),
        id="update_max_rejection",
        name="Update max rejection table 6 am",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        func=_run_449_list,
        trigger=CronTrigger(hour=6, minute=5),
        id="update_list_449",
        name="Update list bx 449 6 am",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        func=update_telegram_rejection,
        trigger=CronTrigger(hour=6, minute=10),
        id="update_telegram_rejection",
        name="Update telegram rejection table 6 am",
        replace_existing=True,
        max_instances=1,
    )
    logger.success(
        "Jobs 'update_max_rejection' and 'update_telegram_rejection' added successfully. Will run daily at 6:00 AM."
    )

except Exception as e:
    logger.error(f"Failed to add job: {e}", exc_info=True)
    raise

try:
    scheduler.start()
    logger.success("BackgroundScheduler started successfully")

    for job_id in ["update_max_rejection", "update_list_449", "update_telegram_rejection"]:
        job = scheduler.get_job(job_id)
        if job and job.next_run_time:
            logger.info(f"Job '{job_id}' next execution at: {job.next_run_time}")
        else:
            logger.warning(f"Job '{job_id}' exists but next run time is not available")

except Exception as e:
    logger.error(f"Failed to start scheduler: {e}", exc_info=True)
    raise


def shutdown_scheduler():
    if scheduler.running:
        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shutdown complete")


atexit.register(shutdown_scheduler)
logger.debug("atexit handler registered for scheduler shutdown")

logger.debug(f"Scheduler running: {scheduler.running}")
logger.debug(f"Registered jobs: {len(scheduler.get_jobs())}")

if __name__ == "__main__":
    logger.info("🔄 Scheduler is now running and will keep the container alive")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("⚠️ Received shutdown signal")
        shutdown_scheduler()
        sys.exit(0)
