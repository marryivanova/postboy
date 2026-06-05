from sqlalchemy import BigInteger, Column, Integer, String

from src.db.core import Base


class TgCustomerLink(Base):
    __tablename__ = "tg_customer_links"

    chat_id = Column(BigInteger, primary_key=True, nullable=False)
    lms_id = Column(Integer)
    lead_id = Column(Integer)
    contact_id = Column(Integer)
    kid_id = Column(Integer)
