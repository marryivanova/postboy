from typing import Optional

from pydantic import BaseModel, validator


class MessageModel(BaseModel):
    """Model for send message."""

    bitrix_type_client: str
    telegram_id: Optional[int]
    message_text: str
    telegram_buttons: Optional[list]
    messenger: Optional[str]
    client_name: Optional[str]
    telegram_media: Optional[list]
    telegram_photo: Optional[str]
