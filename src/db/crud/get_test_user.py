from datetime import datetime

from loguru import logger
from sqlalchemy.exc import OperationalError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.db.core import session_scope
from src.db.model import TestLeadsInRefusal


@retry(
    stop=stop_after_attempt(8),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OperationalError),
)
def get_rus_telegram_ids_test():
    logger.info(f"Забрать все telegram_id где expats = 0: {datetime.now()}")

    with session_scope() as session:
        results = session.query(TestLeadsInRefusal.telegram_id).filter(TestLeadsInRefusal.expats == 0).all()
        telegram_ids = [result[0] for result in results]
        logger.info(f"Список: {len(telegram_ids)}")
        return telegram_ids


@retry(
    stop=stop_after_attempt(8),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OperationalError),
)
def get_expats_telegram_ids_test():
    logger.info(f"Забрать все telegram_id где expats = 1: {datetime.now()}")

    with session_scope() as session:
        results = session.query(TestLeadsInRefusal.telegram_id).filter(TestLeadsInRefusal.expats == 1).all()
        telegram_ids = [result[0] for result in results]
        logger.info(f"Список: {len(telegram_ids)}")
        return telegram_ids


@retry(
    stop=stop_after_attempt(8),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OperationalError),
)
def get_rus_max_ids_test():
    logger.info(f"Забрать все max_id где expats = 0: {datetime.now()}")

    with session_scope() as session:
        results = session.query(TestLeadsInRefusal.max_id).filter(TestLeadsInRefusal.expats == 0).all()
        max_ids = [result[0] for result in results]
        logger.info(f"Список: {len(max_ids)}")
        return max_ids


@retry(
    stop=stop_after_attempt(8),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OperationalError),
)
def get_expats_max_ids_test():
    logger.info(f"Забрать все max_id где expats = 1: {datetime.now()}")

    with session_scope() as session:
        results = session.query(TestLeadsInRefusal.max_id).filter(TestLeadsInRefusal.expats == 1).all()
        max_ids = [result[0] for result in results]
        logger.info(f"Список: {len(max_ids)}")
        return max_ids
