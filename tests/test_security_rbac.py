import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.auth import create_jwt_token, require_regulator_admin
from app.dto.scenario_dto import AIScenarioRequestDTO


@pytest.mark.asyncio
async def test_require_regulator_admin_rejects_enterprise_role():
    """Тест RBAC: инженер завода не имеет права менять государственные реестры рисков"""
    engineer_token = create_jwt_token(
        {
            "sub": 1,
            "email": "engineer@factory.ru",
            "full_name": "Инженер",
            "role": "enterprise_engineer",
            "organization": "АО Завод",
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        await require_regulator_admin(authorization=f"Bearer {engineer_token}")

    assert exc_info.value.status_code == 403
    assert "Минпромторга РФ" in exc_info.value.detail


@pytest.mark.asyncio
async def test_require_regulator_admin_rejects_tampered_token():
    """Тест безопасности: поддельный токен возвращает 401 Unauthorized"""
    tampered_header = "Bearer invalid.fake.token"
    with pytest.raises(HTTPException) as exc_info:
        await require_regulator_admin(authorization=tampered_header)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_regulator_admin_accepts_valid_regulator():
    """Тест авторизации: государственный инспектор Минпромторга успешно авторизуется"""
    regulator_token = create_jwt_token(
        {
            "sub": 2,
            "email": "inspector@minpromtorg.gov.ru",
            "full_name": "Лесных Иван Сергеевич",
            "role": "regulator_admin",
            "organization": "Минпромторг РФ",
        }
    )

    user = await require_regulator_admin(authorization=f"Bearer {regulator_token}")
    assert user.role == "regulator_admin"
    assert user.full_name == "Лесных Иван Сергеевич"


def test_scenario_dto_rejects_flooding_event_length():
    """Тест защиты от DoS: промпт события ограничен 1000 символами"""
    oversized_prompt = "A" * 1001
    with pytest.raises(ValidationError):
        AIScenarioRequestDTO(geopolitical_event=oversized_prompt)
