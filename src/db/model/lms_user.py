from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, String

from src.db.core import Base


class User(Base):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(String(100), nullable=False)
    phone = Column(String(100), nullable=True, index=True)
    email = Column(String(100), nullable=True)
    messenger = Column(BigInteger, nullable=True)

    next_lesson_date = Column(DateTime, nullable=True, index=True)
    last_lesson_date = Column(Date, nullable=True)
    date_update = Column(Date, nullable=True)

    is_study = Column(Integer, nullable=False, default=False)
    timezone = Column(String(32), nullable=True, default="Europe/Moscow")

    balance = Column(Integer, nullable=True, default=0)
    balance_user = Column(Integer, nullable=True, default=0)