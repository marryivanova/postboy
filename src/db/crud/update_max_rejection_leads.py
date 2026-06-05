from datetime import datetime

from loguru import logger
from sqlalchemy import case, literal
from sqlalchemy.exc import OperationalError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.db.core import session_scope
from src.db.model import LeadsUser, User, MaxLeadsRejection, MaxUser


@retry(
    stop=stop_after_attempt(8),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OperationalError),
)
def update_max_rejection():
    logger.info(f"Старт ORM версия: {datetime.now()}")

    with session_scope() as session:
        session.query(MaxLeadsRejection).delete()

        expats_subquery = (
            session.query(
                MaxUser.lead_id,
                case(
                    (
                        (LeadsUser.PHONE == None)
                        | (LeadsUser.PHONE.like("8%"))
                        | (LeadsUser.PHONE.like("+7%"))
                        | (LeadsUser.PHONE.like("7%")),
                        literal(0),
                    ),
                    else_=literal(1),
                ).label("expats"),
            )
            .outerjoin(LeadsUser, LeadsUser.ID == MaxUser.lead_id)
            .subquery()
        )

        results = (
            session.query(
                MaxUser.chat_id.label("max_id"),
                User.id_lead.label("lead_id"),
                User.id_contact.label("contact_id"),
                expats_subquery.c.expats,
            )
            .join(User, User.id_lead == MaxUser.lead_id)
            .outerjoin(expats_subquery, expats_subquery.c.lead_id == MaxUser.lead_id)
            .join(LeadsUser, LeadsUser.ID == MaxUser.lead_id)
            .filter(LeadsUser.REJECTION_REASON != None)
            .all()
        )

        records = []
        for result in results:
            record = MaxLeadsRejection(
                max_id=result.max_id,
                lead_id=result.lead_id,
                contact_id=result.contact_id,
                expats=result.expats if result.expats is not None else 1,
            )
            records.append(record)

        if records:
            session.bulk_save_objects(records)

        updated_count = len(records)
        session.flush()
        logger.info(f"Обновлено записей: {updated_count}")

    logger.info(f"Завершено ORM: {datetime.now()}")
