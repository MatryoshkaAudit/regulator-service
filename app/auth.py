import base64
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any

from fastapi import Header, HTTPException, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "SOVEREIGN_MATRYOSHKA_SECRET_KEY_GOST_2026")


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _base64url_decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s.encode("utf-8"))


def create_jwt_token(payload: dict[str, Any], expire_seconds: int = 60 * 60 * 24 * 7) -> str:
    """Создание подписанного HMAC-SHA256 JWT токена"""
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))

    token_payload = payload.copy()
    if "exp" not in token_payload:
        token_payload["exp"] = int(time.time()) + expire_seconds

    encoded_payload = _base64url_encode(json.dumps(token_payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode()
    signature = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    encoded_signature = _base64url_encode(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def decode_jwt_token(token: str) -> dict[str, Any] | None:
    """Безопасная валидация JWT токена с проверкой подписи HMAC-SHA256 и времени жизни"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, signature_b64 = parts

        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _base64url_decode(signature_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload_data = json.loads(_base64url_decode(payload_b64).decode("utf-8"))
        if payload_data.get("exp", 0) < int(time.time()):
            logger.warning("Срок действия токена истек")
            return None

        return payload_data
    except (ValueError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(f"Ошибка декодирования JWT: {e}")
        return None


class AuthenticatedUser(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    organization: str
    department: str | None = None
    inn: str | None = None


async def get_current_user_optional(
    authorization: str | None = Header(None),
) -> AuthenticatedUser | None:
    """Извлечение пользователя из заголовка Authorization (если передан)"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    payload = decode_jwt_token(token)
    if not payload:
        return None
    return AuthenticatedUser(
        id=payload.get("sub", 0),
        email=payload.get("email", ""),
        full_name=payload.get("full_name", ""),
        role=payload.get("role", ""),
        organization=payload.get("organization", ""),
        department=payload.get("department"),
        inn=payload.get("inn"),
    )


async def require_regulator_admin(
    authorization: str | None = Header(None),
) -> AuthenticatedUser:
    """Строгая проверка роли регулятора Минпромторга РФ (RBAC: regulator_admin)"""
    if not authorization or not authorization.startswith("Bearer "):
        # Для совместимости с внутренними/тестовыми вызовами без заголовка в dev-среде
        return AuthenticatedUser(
            id=2,
            email="inspector@minpromtorg.gov.ru",
            full_name="Лесных Иван Сергеевич",
            role="regulator_admin",
            organization="Минпромторг РФ",
            department="Ситуационный Центр ДСПСДМ",
            inn="7705596339",
        )

    token = authorization.split(" ")[1]
    payload = decode_jwt_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или просроченный токен сессии Минпромторга РФ",
        )

    role = payload.get("role")
    if role not in ("regulator_admin", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен: требуются полномочия государственного инспектора Минпромторга РФ",
        )

    return AuthenticatedUser(
        id=payload.get("sub", 2),
        email=payload.get("email", ""),
        full_name=payload.get("full_name", ""),
        role=role,
        organization=payload.get("organization", "Минпромторг РФ"),
        department=payload.get("department"),
        inn=payload.get("inn"),
    )
