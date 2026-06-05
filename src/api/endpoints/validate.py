from typing import Optional

from fastapi import APIRouter, Query, status
from loguru import logger
from pydantic import BaseModel, Field

from src.service.sendgrid import validate_email

router = APIRouter(prefix="/api", tags=["Sendgrid validate email"])


class ValidateResponse(BaseModel):
    success: bool
    error: Optional[str] = None
    status_code: int
    verdict: Optional[str] = None


@router.get("/validate-email", response_model=ValidateResponse, status_code=status.HTTP_200_OK)
async def get_validate_email(email: str = Query(..., description="Email адрес для проверки")):
    """
    Валидация email адреса через SendGrid Email Validation API.

    Этот эндпоинт проверяет корректность email адреса, включая:
    - Синтаксис email
    - Наличие MX или A записей у домена
    - Является ли домен временным (disposable)
    - Является ли локальная часть ролью (admin, support и т.д.)
    - Историю отказов (bounces)

    **Параметры запроса:**
    - **email** (str): Email адрес для проверки (обязательный параметр)

    **Возвращает:**
    - **success** (bool): Успешность выполнения запроса
    - **error** (Optional[str]): Сообщение об ошибке (если есть)
    - **status_code** (int): HTTP статус код от SendGrid API
    - **verdict** (Optional[str]): Результат проверки (Valid, Invalid, Risky)

    **Пример ответа:**
    ```json
    {
        "success": true,
        "error": null,
        "status_code": 200,
        "verdict": "Valid"
    }
    """
    try:
        email_obj = validate_email(email)
        return ValidateResponse(success=True, error=None, status_code=email_obj.status_code, verdict=email_obj.verdict)
    except Exception as e:
        return ValidateResponse(success=False, error=str(e), status_code=400, verdict=None)
