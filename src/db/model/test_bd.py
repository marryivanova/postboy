from sqlalchemy import BigInteger, Boolean, Column, Integer, Text

from src.db.core import Base


class TestLeadsInRefusal(Base):
    __tablename__ = "test_leads_in_refusal"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False)
    max_id = Column(BigInteger, nullable=False)
    lead_id = Column(Integer, nullable=True)
    contact_id = Column(Integer, nullable=True)
    expats = Column(Boolean, default=False)

    def __repr__(self):
        return f"TestLeadsInRefusal(id={self.id}, telegram_id={self.telegram_id}, expats={self.expats})"
