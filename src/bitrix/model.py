from enum import Enum
from typing import Callable

from pydantic import BaseModel


class ListIdBx(Enum):

    id_list_message = ""
    id_list_template = ""


class SegmentId(Enum):

    max_rus = 2349
    max_expats = 2347
    tg_rus = 2345
    tg_expats = 2343
    max_test = 2353
    tg_test = 2351


class MessengerType(str, Enum):
    TELEGRAM = "telegram"
    MAX = "max"
    TEST_TELEGRAM = "test_telegram"
    TEST_MAX = "test_max"


class SegmentType(str, Enum):
    EXPATS = "expats"
    RUS = "rus"


class SegmentConfig(BaseModel):
    name: str
    get_ids_func: Callable
    segment_id_value: int
    list_name_template: str
    message_template: str


class UpdaterListResponse(BaseModel):
    success: bool
    status_code: int
    messenger: str
    message: str
    len_list: int = 0
    error: str = ""
