import json
from functools import wraps
from typing import List, Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, Field

from src.api.endpoints.helper.method_bx import get_buttons, get_text_list
from src.app_celery.celery_app import celery_app
from src.app_celery.tasks import send_mass_mailing_max, send_mass_mailing_telegram
from src.db.crud import get_expats_max_ids, get_expats_telegram_ids, get_rus_max_ids, get_rus_telegram_ids

router = APIRouter(prefix="/api", tags=["Sender mass message"])


class SendMessageResponse(BaseModel):
    success: bool
    error: Optional[str] = None
    status_code: int
    task_id: Optional[str] = None
    message: Optional[str] = None


class ButtonModel(BaseModel):
    type: str
    text: str
    url: Optional[str] = None
    payload: Optional[str] = None


class SendMassMailingRequest(BaseModel):
    chat_id: str
    text: str
    format_type: str = "html"
    buttons: Optional[List[List[ButtonModel]]] = None


def handle_telegram_errors(func):
    """Декоратор для обработки ошибок при отправке сообщений в Telegram"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except TimeoutError as e:
            logger.error(f"Таймаут: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Превышено время ожидания ответа от Telegram бота"
            )
        except ConnectionError as e:
            logger.error(f"Ошибка соединения: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Сервис Telegram бота временно недоступен"
            )
        except Exception as e:
            logger.error(f"Ошибка: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Внутренняя ошибка сервера: {str(e)}"
            )

    return wrapper


@router.post("/mass-mailing-telegram", response_model=SendMessageResponse, status_code=status.HTTP_200_OK)
@handle_telegram_errors
async def send_mass_telegram(request: SendMassMailingRequest):
    """
     ### Описание
    Эндпоинт принимает запрос на массовую рассылку сообщений в Telegram-чаты.
    Рассылка выполняется асинхронно через Celery для избежания блокировок.

    ### Параметры запроса (SendMassMailingRequest):
    - **chat_id** (str, обязательный): ID чата или список ID через запятую
      * Пример: `"123456789"` или `"123456789,987654321,555555555"`
    - **text** (str, обязательный): Текст сообщения для отправки
      * Поддерживает HTML разметку
      * Максимальная длина: 4096 символов
    - **buttons** (list, опциональный): Инлайн-кнопки для сообщения
      * Формат: `[[{"type": "url", "text": "Кнопка", "url": "https://..."}]]`

    ### Возвращаемый ответ (SendMessageResponse):
    - **success** (bool): Статус выполнения
    - **error** (str|None): Сообщение об ошибке (если есть)
    - **status_code** (int): HTTP статус код
    - **task_id** (str): ID задачи Celery для отслеживания
    - **message** (str): Детальное сообщение о статусе

    ### Примеры запросов:

    **Простая рассылка одному чату:**
    ```json
    {
      "chat_id": "123456789",
      "text": "Привет! Это тестовое сообщение"
    }
    """
    logger.info(f"📨 Запрос на массовую рассылку Telegram")

    if "," in request.chat_id:
        chat_ids = [cid.strip() for cid in request.chat_id.split(",")]
    else:
        chat_ids = [request.chat_id]

    buttons_serialized = None
    if request.buttons:
        buttons_serialized = []
        for row in request.buttons:
            serialized_row = []
            for button in row:
                if hasattr(button, "model_dump"):
                    button_dict = button.model_dump()
                elif hasattr(button, "dict"):
                    button_dict = button.dict()
                else:
                    button_dict = button
                button_dict = {k: v for k, v in button_dict.items() if v is not None}
                serialized_row.append(button_dict)
            buttons_serialized.append(serialized_row)

    task = send_mass_mailing_telegram.delay(chat_ids=chat_ids, message_text=request.text, buttons=buttons_serialized)

    logger.info(f"✅ Задача запущена. Task ID: {task.id}")

    return SendMessageResponse(
        success=True,
        error=None,
        status_code=202,
        task_id=task.id,
        message=f"Рассылка поставлена в очередь. Task ID: {task.id}",
    )


@router.get("/mass-mailing-telegram", response_model=SendMessageResponse, status_code=status.HTTP_200_OK)
@handle_telegram_errors
async def send_mass_telegram_get(
    element_id_451: Optional[str | int] = Query(None, description="Элемент списка его id"),
    element_name_451: Optional[str | int] = Query(None, description="Элемент списка NAME"),
    element_buttons_451: Optional[bool] = Query(False, description="Использовать кнопки из списка (true/false)"),
    expat: bool = Query(..., description="Экспат или нет"),
):
    """
    Отправить массовую рассылку через Telegram бота.
    Использует Celery для асинхронной обработки с оптимизацией производительности.

    ---

    ### Описание
    Эндпоинт для массовых рассылок в Telegram с поддержкой текста и кнопок из предварительно сохранённых списков.
    Автоматически определяет аудиторию (обычные пользователи или экспаты) и нормализует список получателей.
    Обрабатывает ошибки Telegram через декоратор @handle_telegram_errors.

    ### Ключевые особенности:
    - **Гибкий выбор источника**: Текст и кнопки по ID или NAME элемента списка
    - **Аудитория**: Раздельная рассылка обычным пользователям и экспатам в Telegram
    - **Кнопки**: Опциональное добавление инлайн-кнопок из списка
    - **Асинхронность**: Фоновая отправка через Celery без блокировки запроса
    - **Устойчивость**: Обработка различных форматов chat_ids (вложенные списки, строки с разделителями)
    - **Telegram-специфичное**: Автоматическая обработка и логирование ошибок Telegram API

    ### Параметры запроса (Query):
    - **element_id_451** (Optional[str | int]): ID элемента списка для получения текста и кнопок
      * Приоритетный параметр, если указан вместе с element_name_451
      * Пример: `42` или `"telegram_news_123"`

    - **element_name_451** (Optional[str | int]): Название элемента списка для получения текста и кнопок
      * Используется, если element_id_451 не указан
      * Пример: `"welcome_tg_message"` или `"telegram_promo"`

    - **element_buttons_451** (Optional[bool]): Флаг использования кнопок из списка
      * По умолчанию: `false`
      * При `true` кнопки автоматически прикрепляются к сообщению
      * Если кнопки не найдены при `true` — логируется предупреждение
      * Поддерживает Telegram-кнопки: url, callback, web_app

    - **expat** (bool, обязательный): Тип аудитории рассылки
      * `true` — рассылка экспатам
      * `false` — рассылка обычным пользователям (Россия)

    ### Возвращаемое значение (SendMessageResponse):
    - **success** (bool): Успешность постановки задачи в очередь
    - **error** (Optional[str]): Сообщение об ошибке (при неудаче)
    - **status_code** (int): Код статуса (200, 404, 500)
    - **task_id** (Optional[str]): ID задачи в Celery для отслеживания
    - **message** (str): Человекочитаемое описание результата

    ### Примеры запросов:
    ```http
    # Рассылка обычным пользователям по ID элемента
    GET /mass-mailing-telegram?element_id_451=42&expat=false

    # Рассылка экспатам по имени элемента с кнопками
    GET /mass-mailing-telegram?element_name_451=special_offer&expat=true&element_buttons_451=true

    # Минимальный запрос (вызовет ошибку 404)
    GET /mass-mailing-telegram?expat=false

    """
    try:
        logger.info(f"📨 GET запрос на массовую рассылку MAX")

        text = get_text_list(element_id=element_id_451, element_name=element_name_451)

        if not text:
            return SendMessageResponse(
                success=False,
                error="Текст рассылки не найден",
                status_code=404,
                task_id=None,
                message=f"Элемент с ID={element_id_451} или NAME={element_name_451} не найден",
            )

        if not expat:
            chat_id_raw = get_rus_telegram_ids()
        else:
            chat_id_raw = get_expats_telegram_ids()

        if isinstance(chat_id_raw, list):
            chat_ids = []
            for item in chat_id_raw:
                if isinstance(item, list):
                    chat_ids.extend([str(cid).strip() for cid in item if cid])
                else:
                    chat_ids.append(str(item).strip())
        elif isinstance(chat_id_raw, str):
            if "," in chat_id_raw:
                chat_ids = [cid.strip() for cid in chat_id_raw.split(",")]
            else:
                chat_ids = [chat_id_raw.strip()]
        else:
            chat_ids = [str(chat_id_raw).strip()]

        buttons_data = None
        if element_buttons_451:
            buttons_data = get_buttons(element_id=element_id_451, element_name=element_name_451)
            if buttons_data:
                logger.info(f"📎 Кнопки загружены из списка: {buttons_data}")
            else:
                logger.warning("⚠️ Кнопки не найдены в списке, но флаг element_buttons_451=True")

        task = send_mass_mailing_telegram.delay(
            chat_ids=chat_ids,
            message_text=text,
            buttons=buttons_data,
        )

        logger.info(f"✅ GET задача запущена. Task ID: {task.id}")

        return SendMessageResponse(
            success=True,
            error=None,
            status_code=202,
            task_id=task.id,
            message=f"Рассылка поставлена в очередь. Task ID: {task.id}",
        )

    except Exception as e:
        logger.exception(f"Ошибка при создании рассылки: {e}")
        return SendMessageResponse(
            success=False,
            error=str(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            task_id=None,
            message="Внутренняя ошибка сервера",
        )


@router.post("/mass-mailing-max", response_model=SendMessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_mass_max(request: SendMassMailingRequest):
    """
    Отправить массовую рассылку через MAX бота.
    Использует Celery для асинхронной обработки с оптимизацией производительности.

    ---

    ### Описание
    Оптимизированный эндпоинт для массовых рассылок с высокими нагрузками.
    Автоматически разбивает получателей на батчи и обрабатывает их параллельно.

    ### Ключевые особенности:
    - **Параллельная обработка**: Отправка батчей одновременно
    - **Масштабируемость**: Обработка тысяч получателей без блокировок
    - **Отказоустойчивость**: Ошибки отдельных получателей не влияют на остальных
    - **Мониторинг**: Детальная статистика по каждому батчу

    ### Параметры запроса (SendMassMailingRequest):
    - **chat_id** (str, обязательный): ID чата или список ID через запятую
      * Поддерживает Telegram ID, Username (с @), или ссылки-приглашения
      * Пример: `"123456789"` или `"@username1,@username2,123456789"`
      * Максимум: не ограничен (автоматическая батчизация)

    - **text** (str, обязательный): Текст сообщения для отправки
      * Поддерживает HTML и MarkdownV2 форматирование
      * Максимальная длина: 4096 символов
      * Эмодзи и специальные символы: экранируются автоматически

    - **buttons** (list, опциональный): Инлайн-кнопки для сообщения
      * Формат: `[[{"type": "url", "text": "Кнопка", "url": "https://..."}]]`
      * Максимум кнопок: 8 в одной строке, до 10 строк
      * Типы кнопок:
        - `url`: Открывает веб-ссылку
        - `callback`: Отправляет callback data боту
        - `web_app`: Открывает Web App
    """
    logger.info(f"📨 Запрос на массовую рассылку MAX")

    if "," in request.chat_id:
        chat_ids = [cid.strip() for cid in request.chat_id.split(",")]
    else:
        chat_ids = [request.chat_id]

    buttons_json = json.dumps(request.buttons, default=lambda x: x.dict() if hasattr(x, "dict") else str(x))
    task = send_mass_mailing_max.delay(chat_ids=chat_ids, text=request.text, buttons=buttons_json)

    logger.info(f"✅ Задача запущена. Task ID: {task.id}")

    return SendMessageResponse(
        success=True,
        error=None,
        status_code=202,
        task_id=task.id,
        message=f"Рассылка поставлена в очередь. Task ID: {task.id}",
    )


@router.get("/mass-mailing-max", response_model=SendMessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_mass_mailing_max_get(
    element_id_451: Optional[str | int] = Query(None, description="Элемент списка его id"),
    element_name_451: Optional[str | int] = Query(None, description="Элемент списка NAME"),
    element_buttons_451: Optional[bool] = Query(False, description="Использовать кнопки из списка (true/false)"),
    expat: bool = Query(..., description="Экспат или нет"),
):
    """
    Отправить массовую рассылку через MAX бота.
    Использует Celery для асинхронной обработки с оптимизацией производительности.

    ---

    ### Описание
    Эндпоинт для массовых рассылок с поддержкой текста и кнопок из предварительно сохранённых списков.
    Автоматически определяет аудиторию (обычные пользователи или экспаты) и нормализует список получателей.

    ### Ключевые особенности:
    - **Гибкий выбор источника**: Текст и кнопки по ID или NAME элемента списка
    - **Аудитория**: Раздельная рассылка обычным пользователям и экспатам
    - **Кнопки**: Опциональное добавление инлайн-кнопок из списка
    - **Асинхронность**: Фоновая отправка через Celery без блокировки запроса
    - **Устойчивость**: Обработка различных форматов chat_ids (вложенные списки, строки с разделителями)

    ### Параметры запроса (Query):
    - **element_id_451** (Optional[str | int]): ID элемента списка для получения текста и кнопок
      * Приоритетный параметр, если указан вместе с element_name_451
      * Пример: `42` или `"newsletter_123"`

    - **element_name_451** (Optional[str | int]): Название элемента списка для получения текста и кнопок
      * Используется, если element_id_451 не указан
      * Пример: `"welcome_message"` или `"promotion_spring"`

    - **element_buttons_451** (Optional[bool]): Флаг использования кнопок из списка
      * По умолчанию: `false`
      * При `true` кнопки автоматически прикрепляются к сообщению
      * Если кнопки не найдены при `true` — логируется предупреждение

    - **expat** (bool, обязательный): Тип аудитории рассылки
      * `true` — рассылка экспатам
      * `false` — рассылка обычным пользователям (Россия)

    ### Возвращаемое значение (SendMessageResponse):
    - **success** (bool): Успешность постановки задачи в очередь
    - **error** (Optional[str]): Сообщение об ошибке (при неудаче)
    - **status_code** (int): Код статуса (202, 404, 500)
    - **task_id** (Optional[str]): ID задачи в Celery для отслеживания
    - **message** (str): Человекочитаемое описание результата

    ### Примеры запросов:
    ```http
    # Рассылка обычным пользователям по ID элемента
    GET /mass-mailing-max?element_id_451=42&expat=false

    # Рассылка экспатам по имени элемента с кнопками
    GET /mass-mailing-max?element_name_451=special_offer&expat=true&element_buttons_451=true

    # Минимальный запрос (вызовет ошибку 404)
    GET /mass-mailing-max?expat=false
    """
    try:
        logger.info(f"📨 GET запрос на массовую рассылку MAX")

        text = get_text_list(element_id=element_id_451, element_name=element_name_451)

        if not text:
            return SendMessageResponse(
                success=False,
                error="Текст рассылки не найден",
                status_code=404,
                task_id=None,
                message=f"Элемент с ID={element_id_451} или NAME={element_name_451} не найден",
            )

        if not expat:
            chat_id_raw = get_rus_max_ids()
        else:
            chat_id_raw = get_expats_max_ids()

        if isinstance(chat_id_raw, list):
            chat_ids = []
            for item in chat_id_raw:
                if isinstance(item, list):
                    chat_ids.extend([str(cid).strip() for cid in item if cid])
                else:
                    chat_ids.append(str(item).strip())
        elif isinstance(chat_id_raw, str):
            if "," in chat_id_raw:
                chat_ids = [cid.strip() for cid in chat_id_raw.split(",")]
            else:
                chat_ids = [chat_id_raw.strip()]
        else:
            chat_ids = [str(chat_id_raw).strip()]

        buttons_data = None
        if element_buttons_451:
            buttons_data = get_buttons(element_id=element_id_451, element_name=element_name_451)
            if buttons_data:
                logger.info(f"📎 Кнопки загружены из списка: {buttons_data}")
            else:
                logger.warning("⚠️ Кнопки не найдены в списке, но флаг element_buttons_451=True")

        task = send_mass_mailing_max.delay(
            chat_ids=chat_ids,
            text=text,
            buttons=buttons_data,
        )

        logger.info(f"✅ GET задача запущена. Task ID: {task.id}")

        return SendMessageResponse(
            success=True,
            error=None,
            status_code=202,
            task_id=task.id,
            message=f"Рассылка поставлена в очередь. Task ID: {task.id}",
        )

    except Exception as e:
        logger.exception(f"Ошибка при создании рассылки: {e}")
        return SendMessageResponse(
            success=False,
            error=str(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            task_id=None,
            message="Внутренняя ошибка сервера",
        )


@router.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """
    Получить статус выполнения задачи
    """
    task_result = AsyncResult(task_id, app=celery_app)

    response = dict(task_id=task_id, state=task_result.state, status=None, result=None, error=None)

    if task_result.state == "PENDING":
        response["status"] = "Задача ожидает выполнения"

    elif task_result.state == "PROGRESS":
        response["status"] = "Задача выполняется"
        response["result"] = task_result.info

    elif task_result.state == "SUCCESS":
        response["status"] = "Задача выполнена"
        response["result"] = task_result.result

    elif task_result.state == "FAILURE":
        response["status"] = "Ошибка выполнения"
        response["error"] = str(task_result.info)

    return response
