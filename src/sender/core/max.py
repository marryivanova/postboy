import requests
from loguru import logger

from settings import settings
from src.sender.core.helper_save_info import save_error_ids_to_csv
from src.sender.model import ServiceUrl


def _get_token(login=settings.admin_username, password=settings.admin_password):
    body = dict(username=login, password=password)
    r = requests.post(ServiceUrl.login_max.value, json=body)
    token = r.json()["access_token"]
    return token


def get_message(chat_id, text, button_type, button_text, button_link):
    error_ids = []
    try:
        auth_token = _get_token()
        headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        formatted_text = f"""{text}"""

        buttons_list = []
        if button_type and button_text and button_link:
            buttons_list = [[{"type": button_type, "text": button_text, "url": button_link}]]

        data = dict(
            chat_id=chat_id,
            text=formatted_text,
            format_type="html",
            auth_token=auth_token,
            buttons=buttons_list,
        )

        response = requests.post(ServiceUrl.sender_max.value, json=data, headers=headers, timeout=30)

        if response.status_code != 200:
            error_ids.append(chat_id)
            save_error_ids_to_csv(error_ids=error_ids, filename="error_max_ids")
            logger.error(f"Ошибка отправки. Статус: {response.status_code}, текст: {response.text}")

        logger.debug(f"Request data: {data}")
        logger.debug(f"Response status: {response.status_code}")

        return response.status_code

    except requests.exceptions.RequestException as e:
        logger.error(f"Исключение при отправке: {e}")
        error_ids.append(chat_id)
        save_error_ids_to_csv(error_ids)
        return 500
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        return 500
