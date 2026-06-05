from sqlalchemy import Column, DateTime, Integer, String

from src.db.core import Base


class LeadsUser(Base):
    __tablename__ = "leads"

    ID = Column(Integer, primary_key=True, autoincrement=True)
    STATUS_ID = Column(Integer, nullable=True)
    EMAIL = Column(String(255), nullable=True)
    PHONE = Column(String(50), nullable=True)
    DATE_CREATE = Column(DateTime, nullable=True)
    TIME_CREATE = Column(DateTime, nullable=True)
    TITLE = Column(String(255), nullable=True)
