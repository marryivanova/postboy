from typing import Dict, List, Optional, Tuple

from loguru import logger
from telegram_hws import TelegramSDK
from telegram_hws.choices import TgButtonType, TgParseMode, TgStatus
from telegram_hws.dto import TgButtonDTO, TgMediaPhotoDTO, TgMessageDTO

from settings import settings
from src.sender.core.helper_save_info import save_error_ids_to_csv
from src.sender.model.tg_model import MessageModel


class TelegramSendMessageService:
    """Service for send message to telegram."""

    _message: MessageModel
    _token: str
    _url: str

    def __init__(self, message: MessageModel) -> None:

        self._message = message
        self.telegram = TelegramSDK(telegram_token=settings.telegram.token)

    def work(self) -> Tuple[bool, str]:
        """Send message. Returns (success, message)"""
        try:
            self._create_telegram_message()
        except ValueError as error:
            return False, str(error)

        status = self.telegram.send(message=self.telegram_message)

        if status != TgStatus.SEND.value:
            error_msg = f"Send failed with status: {status}"
            logger.error(error_msg)
            return False, error_msg

        logger.success("Message sent successfully to telegram")
        return True, "Отправлено через Telegram"

    def _create_telegram_message(self) -> None:
        self.telegram_message = TgMessageDTO(
            chat_id=self._message.telegram_id,
            message_text=self._message.message_text,
            buttons=self._get_buttons(),
            parse_mode=TgParseMode.HTML.value,
        )

        if self._message.telegram_media:
            telegram_media = []
            for media in self._message.telegram_media:
                telegram_media.append(
                    TgMediaPhotoDTO(
                        media=media.get("media"),
                        caption=media.get("caption", ""),
                    )
                )
            self.telegram_message.media = telegram_media

        if self._message.telegram_photo:
            self.telegram_message.photo = self._message.telegram_photo

    def _get_buttons(self) -> list:
        telegram_buttons = []

        if not self._message.telegram_buttons:
            return telegram_buttons

        for button in self._message.telegram_buttons:
            logger.debug(button)
            if isinstance(button, list):
                button = button[0]
            logger.debug(button)

            if isinstance(button, dict):
                tg_button = TgButtonDTO(
                    button_text=button.get("text"),
                    button_type=button.get("button_type", TgButtonType.CALLBACK.value),
                    data=button.get("callback_data"),
                )
                telegram_buttons.append(tg_button)
            else:
                logger.warning(f"Неизвестный формат кнопки: {type(button)}")

        return telegram_buttons


def send_telegram_mailing(
    list_id: List[str | int],
    message_text: str,
    buttons: Optional[list] = None,
) -> Tuple[int, int, List[str], List[str]]:
    """
    Отправляет рассылку в Telegram по chat_id
    Возвращает: (success_count, error_count, blocked_ids, other_error_ids)
    """
    blocked_ids = []
    other_error_ids = []
    success_count = 0
    error_count = 0

    for i, chat_id in enumerate(list_id, 1):
        print(f"\n[{i}/{len(list_id)}] Обработка chat_id: {chat_id}")

        message_model = MessageModel(
            bitrix_type_client="telegram",
            telegram_id=chat_id,
            message_text=message_text,
            telegram_buttons=buttons,
            telegram_media=None,
            telegram_photo=None,
            messenger="telegram",
            client_name="Клиент",
        )

        try:
            service = TelegramSendMessageService(message_model)
            success, result = service.work()

            if success:
                success_count += 1
                logger.debug(f"  ✓ Отправлено chat_id: {chat_id}")
            else:
                error_count += 1
                if "bot_blocked" in str(result).lower():
                    blocked_ids.append(chat_id)
                else:
                    other_error_ids.append(chat_id)
                logger.debug(f"  ✗ Ошибка {chat_id}: {result}")

        except Exception as e:
            error_count += 1
            other_error_ids.append(chat_id)
            logger.debug(f"  ✗ Исключение {chat_id}: {e}")

    logger.debug("\n" + "=" * 50)
    logger.debug("📊 СТАТИСТИКА РАССЫЛКИ")
    logger.debug("=" * 50)
    logger.debug(f"📁 Всего ID: {len(list_id)}")
    logger.debug(f"✅ Успешно отправлено: {success_count}")
    logger.debug(f"❌ Ошибок всего: {error_count}")
    logger.debug(f"   ├─ Бот заблокирован: {len(blocked_ids)}")
    logger.debug(f"   └─ Другие ошибки: {len(other_error_ids)}")

    if list_id and len(list_id) > 0:
        logger.debug(f"📈 Процент успеха: {success_count / len(list_id) * 100:.1f}%")
    else:
        logger.debug("📈 Процент успеха: 0%")
    logger.debug("=" * 50)

    if blocked_ids:
        csv_file = save_error_ids_to_csv(blocked_ids, filename="error_telegram_blocked")
        logger.info(f"📄 Заблокировавшие бота ID сохранены в: {csv_file}")

    if other_error_ids:
        csv_file = save_error_ids_to_csv(other_error_ids, filename="error_telegram_other")
        logger.info(f"📄 Другие ошибки ID сохранены в: {csv_file}")

    return success_count, error_count, blocked_ids, other_error_ids


def send_batch_telegram_messages(batch: List[str], message_text: str, buttons: list) -> Dict:
    """Отправляет батч Telegram сообщений - ВСЕХ ЗА ОДИН РАЗ"""
    success, error, blocked, other = send_telegram_mailing(
        list_id=batch, message_text=message_text, buttons=buttons if buttons else None
    )
    return dict(
        batch_size=len(batch), success=success, error=error, blocked_count=len(blocked), other_errors_count=len(other)
    )
