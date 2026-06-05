import json

from settings import settings
from src.bitrix import BitrixSDK, BxBots

bitrix_instance = BxBots.mailman = BitrixSDK(
    bitrix_user_id=settings.bitrix_bots.bx_id,
    bitrix_token=f"{settings.bitrix_bots.bx_id}/{settings.bitrix_bots.bx_token}",
    bx_domain=settings.bitrix_bots.bx_domain,
)


def get_text_list(element_id=None, element_name=None):

    if element_id:
        response = bitrix_instance.call_method(
            "lists.element.get", params=dict(IBLOCK_TYPE_ID="lists", IBLOCK_ID=451, ELEMENT_ID=element_id)
        )
    elif element_name:
        response = bitrix_instance.call_method(
            "lists.element.get", params=dict(IBLOCK_TYPE_ID="lists", IBLOCK_ID=451, FILTER=dict(NAME=element_name))
        )
    else:
        return None

    if response and response.get("result"):
        result = response["result"]
        element = result[0] if isinstance(result, list) else result
        text_raw = element.get("PROPERTY_2295") or element.get("FIELDS", {}).get("PROPERTY_2295")
        return list(text_raw.values())[0] if isinstance(text_raw, dict) else text_raw

    return None


def get_text_by_id(element_id):
    response = bitrix_instance.call_method(
        "lists.element.get", params=dict(IBLOCK_TYPE_ID="lists", IBLOCK_ID=451, ELEMENT_ID=element_id)
    )

    if response and response.get("result"):
        result = response["result"]
        if isinstance(result, list) and len(result) > 0:
            element = result[0]
        elif isinstance(result, dict):
            element = result
        else:
            return None

        text = element.get("PROPERTY_2295") or element.get("FIELDS", {}).get("PROPERTY_2295")
        return dict(id=element.get("ID"), name=element.get("NAME"), text=text)
    return None


def get_buttons(element_id=None, element_name=None):
    """
    Получить параметры кнопок из списка 451

    Returns:
        dict: Словарь с полями type, text, link или None
    """
    if element_id:
        response = bitrix_instance.call_method(
            "lists.element.get", params=dict(IBLOCK_TYPE_ID="lists", IBLOCK_ID=451, ELEMENT_ID=element_id)
        )
    elif element_name:
        response = bitrix_instance.call_method(
            "lists.element.get", params=dict(IBLOCK_TYPE_ID="lists", IBLOCK_ID=451, FILTER=dict(NAME=element_name))
        )
    else:
        return None

    if response and response.get("result"):
        result = response["result"]
        element = result[0] if isinstance(result, list) else result
        buttons_raw = element.get("PROPERTY_2301") or element.get("FIELDS", {}).get("PROPERTY_2301")

        if isinstance(buttons_raw, dict):
            buttons_str = list(buttons_raw.values())[0] if buttons_raw else None
        else:
            buttons_str = buttons_raw

        if not buttons_str:
            return None

        try:
            buttons_json = json.loads(buttons_str)
            if isinstance(buttons_json, list) and len(buttons_json) > 0:
                first_row = buttons_json[0]
                if isinstance(first_row, list) and len(first_row) > 0:
                    button = first_row[0]
                    if isinstance(button, dict):
                        return dict(
                            type=button.get("type"),
                            text=button.get("text"),
                            link=button.get("url") or button.get("payload"),
                        )
        except json.JSONDecodeError as e:
            return None

    return None
