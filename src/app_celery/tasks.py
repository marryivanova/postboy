import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from celery import Task, chain, chord, group
from celery.result import GroupResult
from loguru import logger
from pydantic import BaseModel, model_validator

from src.sender.core import get_message
from src.sender.core.telegram import send_batch_telegram_messages

from ..bitrix.bitrix_notifier import send_mailing_notification
from .celery_app import celery_app


class Button(BaseModel):
    type: Optional[str] = None
    text: Optional[str] = None
    link: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def parse_messy_data(cls, data: Any) -> dict:
        if not data:
            return {}

        if isinstance(data, str):
            try:
                import json

                data = json.loads(data)
            except json.JSONDecodeError:
                return {}

        try:
            if isinstance(data, list) and data:
                first_item = data[0]
                if isinstance(first_item, list) and first_item:
                    button_data = first_item[0]
                    if isinstance(button_data, dict):
                        return button_data
        except (IndexError, TypeError):
            pass

        return data if isinstance(data, dict) else {}


class MailingTask(Task):
    """Базовый класс для задач рассылки с обработкой ошибок"""

    autoretry_for = (Exception,)
    retry_kwargs = dict(max_retries=3, countdown=60)
    retry_backoff = True
    retry_backoff_max = 600

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Задача {task_id} провалилась: {exc}")

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"Задача {task_id} выполнена успешно: {retval}")


@celery_app.task(base=MailingTask, bind=True, name="tasks.mailing_tasks.send_single_message")
def send_single_message(
    self, chat_id: str, text: str, button_type: str = None, button_text: str = None, button_link: str = None
) -> Dict:
    """
    Отправить одно сообщение (базовая единица работы)
    Используется внутри массовых рассылок
    """
    logger.debug(f"Отправка сообщения в {chat_id}")

    try:
        status_code = get_message(
            chat_id=chat_id,
            text=text,
            button_type=button_type,
            button_text=button_text,
            button_link=button_link,
        )
        return dict(chat_id=chat_id, status="success", code=status_code, timestamp=datetime.now().isoformat())
    except Exception as e:
        logger.error(f"Ошибка отправки в {chat_id}: {e}")
        raise e


@celery_app.task(base=MailingTask, bind=True, name="tasks.mailing_tasks.send_batch_messages")
def send_batch_messages(
    self, batch: List[str], text: str, button_type: str = None, button_text: str = None, button_link: str = None
) -> Dict:
    """Отправить батч сообщений"""

    normalized_batch = []
    for chat in batch:
        if isinstance(chat, list):
            normalized_batch.extend([str(c).strip() for c in chat if c])
        else:
            normalized_batch.append(str(chat).strip())

    normalized_batch = list(set(normalized_batch))

    logger.info(f"Обработка батча из {len(normalized_batch)} сообщений")
    logger.debug(f"Параметры кнопок: type={button_type}, text={button_text}, link={button_link}")

    results = []
    success_count = 0
    error_count = 0

    for chat_id in normalized_batch:
        try:
            status_code = get_message(
                chat_id=chat_id, text=text, button_type=button_type, button_text=button_text, button_link=button_link
            )
            success_count += 1
            results.append(dict(chat_id=chat_id, status="success", code=status_code))
        except Exception as e:
            error_count += 1
            results.append({"chat_id": chat_id, "status": "error", "error": str(e)})
            logger.error(f"Ошибка для {chat_id}: {e}")

        time.sleep(0.033)

    return dict(
        batch_size=len(normalized_batch),
        success=success_count,
        error=error_count,
        results=results,
        timestamp=datetime.now().isoformat(),
    )


@celery_app.task(base=MailingTask, bind=True, name="tasks.mailing_tasks.send_mass_mailing_max")
def send_mass_mailing_max(self, chat_ids: List[str], text: str, buttons: list = None) -> Dict:
    """МАССОВАЯ РАССЫЛКА MAX"""
    logger.info(f"🚀 Старт рассылки для {len(chat_ids)} чатов")

    button = Button.model_validate(buttons)
    button_type, button_text, button_link = button.type, button.text, button.link

    if all([button_type, button_text, button_link]):
        logger.info(f"✅ Кнопки загружены: {button_text} -> {button_link}")
    else:
        logger.warning(f"⚠️ Кнопки НЕ загружены")

    BATCH_SIZE = 50
    batches = [chat_ids[i : i + BATCH_SIZE] for i in range(0, len(chat_ids), BATCH_SIZE)]

    batch_tasks = [
        send_batch_messages.s(
            batch=batch, text=text, button_type=button_type, button_text=button_text, button_link=button_link
        )
        for batch in batches
    ]

    callback = collect_max_results.s(total_recipients=len(chat_ids), original_task_id=self.request.id)

    chord_result = chord(batch_tasks)(callback)

    return dict(
        task_id=self.request.id,
        chord_id=chord_result.id,
        total_recipients=len(chat_ids),
        batches=len(batches),
        status="started",
    )


@celery_app.task(name="tasks.mailing_tasks.collect_max_results")
def collect_max_results(results: list, total_recipients: int, original_task_id: str) -> Dict:
    """
    Собирает результаты всех батчей и отправляет нотификацию
    """
    total_success = 0
    total_error = 0
    blocked_ids = []
    other_error_ids = []
    problematic_ids = []

    for batch_result in results:
        if isinstance(batch_result, dict):
            total_success += batch_result.get("success", 0)
            total_error += batch_result.get("error", 0)
            blocked_ids.extend(batch_result.get("blocked_ids", []))
            other_error_ids.extend(batch_result.get("other_error_ids", []))
            problematic_ids.extend(batch_result.get("problematic_ids", []))

    try:
        send_mailing_notification(
            system="MAX Mailing",
            list_id=list(range(total_recipients)),
            success_count=total_success,
            error_count=total_error,
            blocked_ids=blocked_ids,
            other_error_ids=other_error_ids,
        )
        logger.info("✅ Нотификация отправлена")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки нотификации: {e}")

    logger.info(f"🏁 Рассылка MAX завершена. Успешно: {total_success}, Ошибок: {total_error}")

    return dict(
        task_id=original_task_id,
        total_recipients=total_recipients,
        success=total_success,
        error=total_error,
        completed_at=datetime.now().isoformat(),
    )


@celery_app.task(base=MailingTask, bind=True, name="tasks.mailing_tasks.send_mass_mailing_telegram")
def send_mass_mailing_telegram(self, chat_ids: List[str], message_text: str, buttons: list = None) -> Dict:
    """
    МАССОВАЯ РАССЫЛКА TELEGRAM
    Отдельная очередь для Telegram бота
    """
    logger.info(f"🚀 Старт массовой рассылки Telegram для {len(chat_ids)} чатов")
    logger.info(f"📝 Параметры: chat_ids={chat_ids}, message_text={message_text[:50]}...")

    if isinstance(buttons, str):
        try:
            buttons = json.loads(buttons)
            logger.info("✅ Кнопки распарсены из JSON строки")
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга кнопок: {e}")
            buttons = None

    formatted_buttons = None
    if buttons and isinstance(buttons, list) and len(buttons) > 0:
        formatted_buttons = []
        for row in buttons:
            button_row = []
            for button in row:
                if isinstance(button, dict):
                    button_text = button.get("text", "")
                    button_type = button.get("type", "")
                    button_url = button.get("url", "")

                    if button_type == "link" and button_url:
                        button_row.append(dict(type=button_type, text=button_text, url=button_url))
                    else:
                        button_row.append(dict(type=button_type, text=button_text, url=button_url))

                elif hasattr(button, "text") and hasattr(button, "type"):
                    button_text = button.text
                    button_type = button.type
                    button_url = getattr(button, "url", "") or getattr(button, "payload", "")

                    button_row.append({"type": button_type, "text": button_text, "url": button_url})
            if button_row:
                formatted_buttons.append(button_row)

    BATCH_SIZE = 30
    BATCH_DELAY = 1

    batches = [chat_ids[i : i + BATCH_SIZE] for i in range(0, len(chat_ids), BATCH_SIZE)]
    logger.info(f"Разбито на {len(batches)} батчей по {BATCH_SIZE} сообщений")

    results = []
    total_success = 0
    total_error = 0
    all_blocked_ids = []
    all_other_error_ids = []
    all_problematic_ids = []

    for batch_index, batch in enumerate(batches):
        logger.info(f"Обработка батча {batch_index + 1}/{len(batches)}")

        batch_result = send_batch_telegram_messages(batch, message_text, formatted_buttons)

        total_success += batch_result["success"]
        total_error += batch_result["error"]

        all_blocked_ids.extend(batch_result.get("blocked_ids", []))
        all_other_error_ids.extend(batch_result.get("other_error_ids", []))
        all_problematic_ids.extend(batch_result.get("problematic_ids", []))

        results.append(batch_result)

        if batch_index < len(batches) - 1:
            logger.debug(f"Задержка {BATCH_DELAY} сек перед следующим батчем")
            time.sleep(BATCH_DELAY)

    try:
        send_mailing_notification(
            system="Telegram Mailing",
            list_id=list(range(len(chat_ids))),
            success_count=total_success,
            error_count=total_error,
            blocked_ids=all_blocked_ids,
            other_error_ids=all_other_error_ids,
        )
        logger.info("✅ Итоговое уведомление отправлено")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки итогового уведомления: {e}")

    logger.info(f"🏁 Рассылка Telegram завершена. Успешно: {total_success}, Ошибок: {total_error}")
    logger.info(f"🚫 Заблокировали бота: {len(all_blocked_ids)}")
    logger.info(f"⚠️ Другие ошибки: {len(all_other_error_ids)}")

    return dict(
        task_id=self.request.id,
        total_recipients=len(chat_ids),
        batches=len(batches),
        success=total_success,
        error=total_error,
        blocked_count=len(all_blocked_ids),
        other_error_count=len(all_other_error_ids),
        results=results,
        completed_at=datetime.now().isoformat(),
    )
