from collections import OrderedDict
from datetime import datetime, timedelta
from time import sleep
from typing import Any, Dict, Optional, Union

import requests
from loguru import logger

from settings import settings


class SimpleCache:

    def __init__(self, max_size: int = 100, ttl: int = 300):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
        value, timestamp = self.cache[key]
        if datetime.now() - timestamp > timedelta(seconds=self.ttl):
            del self.cache[key]
            return None
        self.cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any):
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = (value, datetime.now())

    def invalidate(self, key: str):
        if key in self.cache:
            del self.cache[key]


class BitrixSDK:
    """Bitrix bot SDK для работы с Bitrix24 REST API"""

    def __init__(self, bitrix_user_id: str, bitrix_token: str, bx_domain: str = "https://hwschool.bitrix24.ru") -> None:
        self.bx_domain = bx_domain or settings.bitrix_bots.bx_domain
        if self.bx_domain:
            if "/rest/" in self.bx_domain:
                self.bx_domain = self.bx_domain.split("/rest/")[0]
            if not self.bx_domain.startswith(("http://", "https://")):
                self.bx_domain = f"https://{self.bx_domain}"
            self.bx_domain = self.bx_domain.rstrip("/")
        self.bx_domain = bx_domain or settings.bitrix_bots.bx_domain
        self.token = bitrix_token
        self.user_id = bitrix_user_id
        self.webhook_url = f"{self.bx_domain}/rest/{self.token}"
        self.cache = SimpleCache(max_size=100, ttl=300)

        logger.info(f"BitrixSDK инициализирован: domain={self.bx_domain}, user_id={self.user_id}")
        logger.debug(f"Webhook URL: {self.webhook_url[:50]}...")

    def call_method(self, method: str, params: Dict = None, timeout: int = 30) -> Dict:
        """
        Universal method for calling Bitrix API
        """
        if params is None:
            params = {}

        domain = self.bx_domain
        if domain and not domain.startswith(("http://", "https://")):
            domain = f"https://{domain}"

        url = f"{domain}/rest/{self.token}/{method}"

        logger.debug(f"Вызов {method} с параметрами: {params}")

        try:
            response = requests.post(url, json=params, timeout=timeout)
            response.raise_for_status()
            result = response.json()

            if result.get("error"):
                logger.error(f"Ошибка API {method}: {result.get('error_description', result.get('error'))}")

            sleep(0.5)
            return result

        except requests.exceptions.Timeout:
            logger.error(f"Таймаут {timeout}с при вызове {method}")
            return dict(error="timeout", error_description=f"Превышен таймаут {timeout} секунд")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса к {method}: {e}")
            return dict(error="request_error", error_description=str(e))
        except Exception as e:
            logger.error(f"Неизвестная ошибка при вызове {method}: {e}", exc_info=True)
            return dict(error="unknown_error", error_description=str(e))

    def add_comment(self, entity_id: Union[int, str], entity_type: str, comment: str) -> bool:
        """Add comment to lead/contact/deal"""
        response = self.call_method(
            "crm.timeline.comment.add",
            {"fields": {"ENTITY_ID": int(entity_id), "ENTITY_TYPE": entity_type.upper(), "COMMENT": comment}},
            timeout=25,
        )
        return response.get("result", False) if response else False

    def send_comment(self, user_bitrix_id: Union[int, str], user_bitrix_type: str, comment: str) -> Dict[str, Any]:
        """Send comment to user"""
        logger.info(f"Отправка комментария для {user_bitrix_type} {user_bitrix_id}")
        try:
            success = self.add_comment(user_bitrix_id, user_bitrix_type, comment)
            if success:
                return dict(success=True, result=success, message="Комментарий отправлен")
            else:
                return dict(success=False, error="Неизвестная ошибка", response=None)
        except Exception as e:
            logger.error(f"Ошибка отправки комментария: {e}")
            return dict(success=False, error=str(e))

    def create_list_element(self, params_for_create: dict) -> Optional[Dict]:
        """Create element of list (lists.element.add)"""
        response = self.call_method(method="lists.element.add", params=params_for_create, timeout=30)
        logger.debug(f"create element {response}")
        return response.get("result")

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Normalize phone number"""
        if not phone:
            return ""

        digits = "".join(filter(str.isdigit, phone))

        if digits.startswith("8") and len(digits) == 11:
            return "+7" + digits[1:]
        if digits.startswith("9") and len(digits) == 10:
            return "+7" + digits
        if digits.startswith("7") and len(digits) == 11:
            return "+" + digits

        return phone


class BxBots:
    mailman: BitrixSDK = None

try:
    BxBots.mailman = BitrixSDK(
        bitrix_user_id=settings.bitrix_bots.bx_id,
        bitrix_token=f"{settings.bitrix_bots.bx_id}/{settings.bitrix_bots.bx_token}",
        bx_domain=settings.bitrix_bots.bx_domain,
    )
    logger.info("BxBots.max успешно инициализирован")
except Exception as e:
    logger.error(f"Ошибка инициализации BxBots.max: {e}", exc_info=True)
    raise
