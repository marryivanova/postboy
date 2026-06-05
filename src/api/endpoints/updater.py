from datetime import datetime

from fastapi import APIRouter, Query, status
from loguru import logger

from settings import settings
from src.bitrix import BitrixSDK, BxBots, MessengerType, SegmentConfig, SegmentId, SegmentType, UpdaterListResponse
from src.db.crud import (
    get_expats_max_ids,
    get_expats_max_ids_test,
    get_expats_telegram_ids,
    get_expats_telegram_ids_test,
    get_rus_max_ids,
    get_rus_max_ids_test,
    get_rus_telegram_ids,
    get_rus_telegram_ids_test,
)

router = APIRouter(prefix="/api", tags=["Updater list bitrix"])


SEGMENT_CONFIGS = {
    (MessengerType.TELEGRAM, SegmentType.EXPATS): SegmentConfig(
        name="telegram_expats",
        get_ids_func=get_expats_telegram_ids,
        segment_id_value=SegmentId.tg_expats.value,
        list_name_template="Telegram Expats {timestamp}",
        message_template="Длина списка expats: {length}",
    ),
    (MessengerType.TELEGRAM, SegmentType.RUS): SegmentConfig(
        name="telegram_rus",
        get_ids_func=get_rus_telegram_ids,
        segment_id_value=SegmentId.tg_rus.value,
        list_name_template="Telegram RUS {timestamp}",
        message_template="Длина списка rus: {length}",
    ),
    (MessengerType.MAX, SegmentType.RUS): SegmentConfig(
        name="max_rus",
        get_ids_func=get_rus_max_ids,
        segment_id_value=SegmentId.max_rus.value,
        list_name_template="MAX RUS {timestamp}",
        message_template="Длина списка rus: {length}",
    ),
    (MessengerType.MAX, SegmentType.EXPATS): SegmentConfig(
        name="max_expats",
        get_ids_func=get_expats_max_ids,
        segment_id_value=SegmentId.max_expats.value,
        list_name_template="MAX expats {timestamp}",
        message_template="Длина списка expats: {length}",
    ),
    (MessengerType.TEST_MAX, SegmentType.EXPATS): SegmentConfig(
        name="test_max_expats",
        get_ids_func=get_expats_max_ids_test,
        segment_id_value=SegmentId.max_test.value,
        list_name_template="MAX TEST expats {timestamp}",
        message_template="Длина списка expats: {length}",
    ),
    (MessengerType.TEST_MAX, SegmentType.RUS): SegmentConfig(
        name="test_max_rus",
        get_ids_func=get_rus_max_ids_test,
        segment_id_value=SegmentId.max_test.value,
        list_name_template="MAX TEST rus {timestamp}",
        message_template="Длина списка: {length}",
    ),
    (MessengerType.TEST_TELEGRAM, SegmentType.EXPATS): SegmentConfig(
        name="test_telegram_expats",
        get_ids_func=get_expats_telegram_ids_test,
        segment_id_value=SegmentId.tg_test.value,
        list_name_template="Telegram test Expats {timestamp}",
        message_template="Длина списка expats: {length}",
    ),
    (MessengerType.TEST_TELEGRAM, SegmentType.RUS): SegmentConfig(
        name="test_telegram_rus",
        get_ids_func=get_rus_telegram_ids_test,
        segment_id_value=SegmentId.tg_test.value,
        list_name_template="Telegram test rus {timestamp}",
        message_template="Длина списка: {length}",
    ),
}


def create_bitrix_record(bitrix_instance, list_length: int, list_name: str, segment_id: int) -> dict:
    """Создание записи в Bitrix"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    element_code = f"record_{timestamp}"

    return bitrix_instance.call_method(
        "lists.element.add",
        params=dict(
            IBLOCK_TYPE_ID="lists",
            IBLOCK_ID=449,
            ELEMENT_CODE=element_code,
            FIELDS=dict(
                NAME=list_name,
                PROPERTY_2297=str(list_length),
                PROPERTY_2299=str(segment_id),
            ),
        ),
    )


def get_segment_config(messenger: str, expath: bool) -> SegmentConfig:
    """Получение конфигурации сегмента по параметрам"""
    segment_type = SegmentType.EXPATS if expath else SegmentType.RUS

    try:
        messenger_enum = MessengerType(messenger)
    except ValueError:
        raise ValueError(f"Неподдерживаемый мессенджер: {messenger}")

    config_key = (messenger_enum, segment_type)

    if config_key not in SEGMENT_CONFIGS:
        raise ValueError(f"Нет конфигурации для messenger={messenger}, expath={expath}")

    return SEGMENT_CONFIGS[config_key]


@router.get("/updater-list", response_model=UpdaterListResponse, status_code=status.HTTP_200_OK)
async def updater_list_bx(
    messenger: str = Query(..., description="Мессенджер: telegram или max (test_telegram или test_max)"),
    expath: bool = Query(..., description="True - expats, False - rus"),
):
    """
    Получение актуальной длины списка пользователей и сохранение в Bitrix.

    Эндпоинт предназначен для интеграции с Bitrix24. Он получает количество пользователей
    в зависимости от указанного мессенджера и сегмента (экспаты или резиденты РФ),
    после чего сохраняет эту информацию в специальный список Bitrix24.

    **Параметры запроса:**
    - **messenger** (str, обязательный): Тип мессенджера
        * `telegram` - пользователи Telegram
        * `max` - пользователи другой системы (MAX)
    - **expath** (bool, обязательный): Тип сегмента пользователей
        * `true` - экспаты (пользователи не из РФ)
        * `false` - резиденты РФ

    **Возможные комбинации параметров:**
    1. `messenger=telegram&expath=true` - Telegram экспаты
    2. `messenger=telegram&expath=false` - Telegram резиденты РФ
    3. `messenger=max&expath=true` - MAX экспаты
    4. `messenger=max&expath=false` - MAX резиденты РФ

    **Логика работы:**
    1. Инициализация подключения к Bitrix24 через SDK
    2. Получение соответствующей функции для извлечения ID пользователей
    3. Подсчет количества пользователей
    4. Создание записи в Bitrix24 (инфоблок с ID=449) с данными:
        - Название: `{Тип списка} {дата}`
        - PROPERTY_2297: длина списка (количество пользователей)
        - PROPERTY_2299: ID сегмента (из SegmentId)
    5. Возврат ответа с результатом операции
    """

    BxBots.mailman = BitrixSDK(
        bitrix_user_id=settings.bitrix_bots.bx_id,
        bitrix_token=f"{settings.bitrix_bots.bx_id}/{settings.bitrix_bots.bx_token}",
        bx_domain=settings.bitrix_bots.bx_domain,
    )

    try:
        config = get_segment_config(messenger, expath)

        user_ids = config.get_ids_func()
        list_length = len(user_ids)

        segment_name = "expats" if expath else "rus"
        logger.info(f"Получено {list_length} {messenger} {segment_name} ID")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        list_name = config.list_name_template.format(timestamp=timestamp)

        result = create_bitrix_record(
            bitrix_instance=BxBots.mailman,
            list_length=list_length,
            list_name=list_name,
            segment_id=config.segment_id_value,
        )

        logger.info(f"Результат сохранения в Bitrix: {result}")

        return UpdaterListResponse(
            success=True,
            status_code=status.HTTP_200_OK,
            messenger=messenger,
            len_list=list_length,
            message=config.message_template.format(length=list_length),
        )

    except ValueError as e:
        logger.warning(f"Ошибка валидации параметров: {e}")
        return UpdaterListResponse(
            success=False, status_code=status.HTTP_400_BAD_REQUEST, messenger=messenger, message=str(e), error=str(e)
        )

    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}", exc_info=True)
        return UpdaterListResponse(
            success=False,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            messenger=messenger,
            message="Внутренняя ошибка сервера",
            error=str(e),
        )
