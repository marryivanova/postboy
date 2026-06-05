import json
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field
from sendgrid import SendGridAPIClient

from settings import settings

sg = SendGridAPIClient(api_key=settings.sendgrid_token)


class Email(BaseModel):
    email: str
    verdict: str
    status_code: int


class ValidateResponse(BaseModel):
    success: bool
    error: Optional[str] = None
    status_code: int
    verdict: Optional[str] = None


def formated_data(email: str):
    return dict(
        email=email,
        source="signup",
    )


def validate_email(data):
    format_data = formated_data(data)
    response = sg.client.validations.email.post(request_body=format_data)

    logger.debug(f"Статус: {response.status_code}")
    logger.debug(f"Тело: {response.body}")

    if isinstance(response.body, bytes):
        response_data = json.loads(response.body.decode("utf-8"))
    else:
        response_data = response.body

    result = response_data.get("result")

    if not result:
        raise Exception("Нет result в ответе от SendGrid")

    return Email(
        email=result.get("email"),
        verdict=result.get("verdict"),
        status_code=response.status_code,
    )
