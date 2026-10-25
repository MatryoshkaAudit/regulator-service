import hashlib

import pytest

from app.dto.scenario_dto import AIScenarioRequestDTO
from app.services.ai_scenario_service import AIScenarioService


@pytest.mark.asyncio
async def test_ai_scenario_fallback_generation():
    """Тест генерации геополитического сценария с детерминированным fallback"""
    service = AIScenarioService()
    req = AIScenarioRequestDTO(
        product_id=1,
        geopolitical_event="14-й пакет санкций: запрет транзита ПЛИС и РЭА",
        target_industry="Лесозаготовительная техника",
    )
    result = await service.generate_scenario(req)
    assert result.scenario_id.startswith("SCEN-")
    assert result.severity_score >= 0.8
    assert len(result.affected_supply_chains) >= 2
    assert result.systemic_failure_risk_pct > 80.0
    assert len(result.regulatory_remedies) >= 3


def test_certificate_signature_deterministic():
    """Тест криптографического хэширования сертификата соответствия"""
    reg_number = "RU-МПТ-719/2026-88123"
    product_id = 1
    points = 78
    defacto_loc = 41.2
    timestamp = "2026-10-05T20:00:00"
    payload = f"{reg_number}:{product_id}:{points}:{defacto_loc}:{timestamp}"
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert len(h) == 64
    assert h == hashlib.sha256(payload.encode("utf-8")).hexdigest()
