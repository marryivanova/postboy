from datetime import datetime

from loguru import logger
from sqlalchemy.exc import OperationalError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.db.core import session_scope
from src.db.model import TelegramLeadsRejection


@retry(
    stop=stop_after_attempt(8),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OperationalError),
)
def get_all_telegram_ids():
    logger.info(f"Забрать все telegram_id: {datetime.now()}")

    with session_scope() as session:
        records = session.query(TelegramLeadsRejection).all()
        telegram_ids = [record.telegram_id for record in records]
        logger.info(f"Список: {len(telegram_ids)}")
        return telegram_ids


@retry(
    stop=stop_after_attempt(8),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OperationalError),
)
def get_rus_telegram_ids():
    logger.info(f"Забрать все telegram_id где expats = 0: {datetime.now()}")

    with session_scope() as session:
        results = session.query(TelegramLeadsRejection.telegram_id).filter(TelegramLeadsRejection.expats == 0).all()
        telegram_ids = [result[0] for result in results]
        logger.info(f"Список: {len(telegram_ids)}")
        return telegram_ids


@retry(
    stop=stop_after_attempt(8),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OperationalError),
)
def get_expats_telegram_ids():
    logger.info(f"Забрать все telegram_id где expats = 1: {datetime.now()}")

    with session_scope() as session:
        results = session.query(TelegramLeadsRejection.telegram_id).filter(TelegramLeadsRejection.expats == 1).all()
        telegram_ids = [result[0] for result in results]
        logger.info(f"Список: {len(telegram_ids)}")
        return telegram_ids
