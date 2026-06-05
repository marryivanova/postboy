from typing import Any, Dict, List, Optional

from loguru import logger

from settings import settings
from src.bitrix import BitrixSDK
from src.sender.model.url import ChatId


class AlertNotifier:

    def __init__(self) -> None:
        self.albus: BitrixSDK = BitrixSDK(
            bitrix_token=f"{settings.bitrix_bots.bx_id}/{settings.bitrix_bots.bx_token}",
            bitrix_user_id=settings.bitrix_bots.bx_id,
        )

    def send_to_chat(self, chat_id: str, message: str, system: Optional[str] = None):
        if system:
            message = f"[{system}]\n{message}"

        try:
            response = self.albus.call_method("im.message.add", {"DIALOG_ID": f"{chat_id}", "MESSAGE": message})
            if response and response.get("result"):
                logger.info(f"Сообщение отправлено в чат {chat_id}")
            else:
                logger.error(f"Ошибка отправки в чат {chat_id}: {response}")
        except Exception as e:
            logger.error(f"Исключение при отправке в чат {chat_id}: {e}")

    @staticmethod
    def build_message(
        error: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        parts = [
            "\n[B]⚠️ ВЫПОЛНЕНА РАССЫЛКА ⚠️[/B]\n",
        ]

        if error:
            parts.append(f"\n❌ Ошибка: {error}\n")

        if additional_info:
            total_users = additional_info.get("total_users", 0)
            success_count = additional_info.get("success_count", 0)
            error_count = additional_info.get("error_count", 0)
            blocked_count = additional_info.get("blocked_count", 0)
            other_errors_count = additional_info.get("other_errors_count", 0)

            parts.append("\n📊 СТАТИСТИКА РАССЫЛКИ:\n")
            parts.append(f"  • 👥 Всего пользователей: {total_users}")
            parts.append(f"  • ✅ Успешно доставлено: {success_count}")
            parts.append(f"  • ❌ Кол-во заблокировавших: {error_count}")

            if blocked_count > 0:
                parts.append(f"     ├─ Бот заблокирован: {blocked_count}")
            if other_errors_count > 0:
                parts.append(f"     └─ Другие ошибки: {other_errors_count}")

            if total_users > 0:
                success_rate = (success_count / total_users) * 100
                parts.append(f"  • 📈 Процент успеха: {success_rate:.1f}%")

            other_info = {
                k: v
                for k, v in additional_info.items()
                if k
                not in [
                    "total_users",
                    "success_count",
                    "error_count",
                    "blocked_count",
                    "other_errors_count",
                ]
            }

            if other_info:
                parts.append("\n📋 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ:")
                for key, value in other_info.items():
                    parts.append(f"  • {key}: {value}")

        return "\n".join(parts)


def send_mailing_notification(
    system: str,
    list_id: List[str | int],
    success_count: int,
    error_count: int,
    blocked_ids: List[str | int],
    other_error_ids: List[str | int],
    additional_context: Optional[Dict] = None,
):
    """Отправляет уведомление о результате рассылки"""

    notifier = AlertNotifier()

    additional_info = dict(
        total_users=len(list_id),
        success_count=success_count,
        error_count=error_count,
        blocked_count=len(blocked_ids),
        other_errors_count=len(other_error_ids),
    )

    if additional_context:
        additional_info.update(additional_context)

    message = AlertNotifier.build_message(error=None, additional_info=additional_info)

    notifier.send_to_chat(chat_id=ChatId.notif_chat.value, message=message, system=system)
