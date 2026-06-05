from datetime import datetime

from loguru import logger
from sqlalchemy.exc import OperationalError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.db.core import session_scope
from src.db.model import MaxLeadsRejection


@retry(
    stop=stop_after_attempt(8),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OperationalError),
)
def get_all_max_ids():
    logger.info(f"Забрать все max_id: {datetime.now()}")

    with session_scope() as session:
        records = session.query(MaxLeadsRejection).all()
        max_ids = [record.telegram_id for record in records]
        logger.info(f"Список: {len(max_ids)}")
        return max_ids


@retry(
    stop=stop_after_attempt(8),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OperationalError),
)
def get_rus_max_ids():
    logger.info(f"Забрать все max_id где expats = 0: {datetime.now()}")

    with session_scope() as session:
        results = session.query(MaxLeadsRejection.max_id).filter(MaxLeadsRejection.expats == 0).all()
        max_ids = [result[0] for result in results]
        logger.info(f"Список: {len(max_ids)}")
        return max_ids


@retry(
    stop=stop_after_attempt(8),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OperationalError),
)
def get_expats_max_ids():
    logger.info(f"Забрать все max_id где expats = 1: {datetime.now()}")

    with session_scope() as session:
        results = session.query(MaxLeadsRejection.max_id).filter(MaxLeadsRejection.expats == 1).all()
        max_ids = [result[0] for result in results]
        logger.info(f"Список: {len(max_ids)}")
        return max_ids
