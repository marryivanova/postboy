from datetime import datetime

from loguru import logger
from sqlalchemy import and_, case, literal, or_, text
from sqlalchemy.exc import OperationalError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.db.core import session_scope
from src.db.model import LeadsUser, User, TelegramLeadsRejection
from src.db.model.tg_link import TgCustomerLink


@retry(
    stop=stop_after_attempt(8),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(OperationalError),
)
def update_telegram_rejection():
    logger.info(f"Старт ORM версия: {datetime.now()}")

    try:
        with session_scope() as session:
            session.execute(text("SET SESSION SQL_BIG_SELECTS = 1"))
            session.query(TelegramLeadsRejection).delete()

            results = (
                session.query(
                    TgCustomerLink.chat_id.label("telegram_id"),
                    User.id_lead.label("lead_id"),
                    User.id_contact.label("contact_id"),
                    case(
                        (
                            or_(
                                and_(
                                    LeadsUser.PHONE.isnot(None),
                                    or_(
                                        LeadsUser.PHONE.like("8%"),
                                        LeadsUser.PHONE.like("+7%"),
                                        LeadsUser.PHONE.like("7%"),
                                    ),
                                ),
                                User.timezone == "Europe/Moscow",
                            ),
                            literal(0),
                        ),
                        else_=literal(1),
                    ).label("expats"),
                )
                .join(TgCustomerLink, User.id_lead == TgCustomerLink.lead_id)
                .join(LeadsUser, LeadsUser.ID == User.id_lead)
                .filter(
                    User.id_contact.is_(None),
                    LeadsUser.REJECTION_REASON != None,
                )
                .all()
            )

            records = []
            for result in results:
                record = TelegramLeadsRejection(
                    telegram_id=result.telegram_id,
                    lead_id=result.lead_id,
                    contact_id=result.contact_id,
                    expats=result.expats,
                )
                records.append(record)

            if records:
                session.bulk_save_objects(records)
            session.flush()

            expats_count = sum(1 for r in records if r.expats == 1)
            non_expats_count = sum(1 for r in records if r.expats == 0)
            logger.info(f"Экспатов: {expats_count}, Не экспатов: {non_expats_count}")

    except Exception as e:
        logger.error(f"ОШИБКА: {type(e).__name__}: {e}")
        import traceback

        logger.error(f"Трассировка:\n{traceback.format_exc()}")
        raise

    logger.info(f"Завершено ORM: {datetime.now()}")


if __name__ == "__main__":
    update_telegram_rejection()
