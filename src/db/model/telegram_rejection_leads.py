from sqlalchemy import BigInteger, Boolean, Column, Integer

from src.db.core import Base


class TelegramLeadsRejection(Base):
    __tablename__ = "telegram_leads_rejection"

    id = Column(BigInteger, primary_key=True)
    telegram_id = Column(BigInteger, nullable=True)
    lead_id = Column(Integer, nullable=True)
    contact_id = Column(Integer, nullable=True)
    expats = Column(Boolean, nullable=True)

    def __repr__(self):
        return (
            f"telegram_leads_rejection(telegram_id={self.max_id}, lead_id={self.lead_id}, contact_id={self.contact_id})"
        )
