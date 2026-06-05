from enum import Enum


class ChatId(Enum):

    notif_chat = ""


class ServiceUrl(Enum):

    login_max = ""
    sender_max = ""


class UrlForList(Enum):

    telegram_expath = ""
    telegram_no_expath = ""
    max_expath = ""
    max_no_expath = ""
