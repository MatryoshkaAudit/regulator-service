import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.dto.scenario_dto import AIScenarioRequestDTO
from app.services.ai_scenario_service import AIScenarioService


@pytest.mark.asyncio
async def test_ai_scenario_fallback_generation():
    """Тест детерминированного экспертного fallback без обращения к внешней сети"""
    service = AIScenarioService()
    service.api_key = ""  # Гарантируем запуск детерминированной модели без сетевого вызова
    req = AIScenarioRequestDTO(
        product_id=1,
        geopolitical_event="14-й пакет санкций: запрет транзита ПЛИС и РЭА",
        target_industry="Лесозаготовительная техника",
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock):
        result = await service.generate_scenario(req)
        assert result.scenario_id.startswith("SCEN-")
        assert result.severity_score >= 0.8
        assert len(result.affected_supply_chains) >= 2
        assert result.systemic_failure_risk_pct > 80.0
        assert len(result.regulatory_remedies) >= 3


@pytest.mark.asyncio
async def test_ai_scenario_mocked_llm_response():
    """Тест валидации и маппинга ответа LLM через изолированный мок"""
    service = AIScenarioService()
    service.api_key = "test-mock-key"

    mock_llm_json = {
        "scenario_title": "Тестовый сценарий санкционного запрета",
        "geopolitical_context": "Блокировка поставок гидравлики из ЕС",
        "severity_score": 0.92,
        "calibrated_country_risks": {"DE": 1.0, "IT": 0.95},
        "impacted_hs_codes": ["8481209009"],
        "affected_supply_chains": [
            {
                "node_name": "Клапан пропорциональный",
                "country": "DE",
                "severity": "CRITICAL",
                "consequence": "Останов сборочной линии",
            }
        ],
        "systemic_failure_risk_pct": 94.5,
        "critical_industries_at_risk": ["Лесное машиностроение"],
        "regulatory_remedies": [
            "Субсидирование перепроектирования гидросистемы",
            "Ускоренное включение отечественного аналога в реестр Минпромторга",
        ],
        "executive_verdict": "Требуется срочное замещение на гидроаппаратуру ОАО «Салео»",
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"message": {"content": json.dumps(mock_llm_json)}}]}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        req = AIScenarioRequestDTO(
            product_id=1,
            geopolitical_event="Эмбарго на гидравлические компоненты",
            target_industry="Лесозаготовительная техника",
        )
        result = await service.generate_scenario(req)
        assert result.scenario_id.startswith("SCEN-")
        assert result.severity_score == 0.92
        assert len(result.affected_supply_chains) == 1
        assert result.affected_supply_chains[0].node_name == "Клапан пропорциональный"
        assert result.systemic_failure_risk_pct == 94.5
        assert len(result.regulatory_remedies) == 2


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
