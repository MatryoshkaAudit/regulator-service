import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthenticatedUser, require_regulator_admin
from app.database import get_db_session
from app.dto.certificate_dto import CertificateResponseDTO, IssueCertificateRequestDTO
from app.dto.compliance_dto import PP719AuditResponseDTO
from app.dto.overview_dto import (
    CountryRiskItemDTO,
    CreateCountryRiskDTO,
    HiddenImportItemDTO,
    PlantOverviewItemDTO,
    SetStrategicStatusDTO,
    UpdateCountryRiskDTO,
)
from app.dto.sanctions_dto import SanctionsShockRequestDTO, SanctionsShockResultDTO
from app.dto.scenario_dto import AIScenarioRequestDTO, AIScenarioResponseDTO
from app.repositories.regulator_repository import RegulatorRepository
from app.services.ai_scenario_service import AIScenarioService
from app.services.certificate_service import CertificateService
from app.services.compliance_service import ComplianceService
from app.services.overview_service import OverviewService
from app.services.sanctions_service import SanctionsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/regulator", tags=["Regulator Control Center & Sanctions Audit"])


def get_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RegulatorRepository:
    return RegulatorRepository(session)


@router.get("/overview", response_model=list[PlantOverviewItemDTO])
async def get_plants_monitoring_overview(
    repo: Annotated[RegulatorRepository, Depends(get_repo)],
) -> list[PlantOverviewItemDTO]:
    """Сводный мониторинг всех поданных спецификаций от предприятий (реальная картина vs бумажная)"""
    service = OverviewService(repo)
    return await service.get_monitoring_overview()


@router.get("/hidden-imports", response_model=list[HiddenImportItemDTO])
async def get_hidden_imports(
    repo: Annotated[RegulatorRepository, Depends(get_repo)],
) -> list[HiddenImportItemDTO]:
    """Выявление скрытого критического импорта на 3-м уровне вложений (Tier-3)"""
    service = OverviewService(repo)
    return await service.get_hidden_imports()


@router.get("/countries", response_model=list[CountryRiskItemDTO])
async def list_country_risks(
    repo: Annotated[RegulatorRepository, Depends(get_repo)],
) -> list[CountryRiskItemDTO]:
    """Справочник стран и установленные государством санкционные веса рисков"""
    service = OverviewService(repo)
    return await service.get_countries_list()


@router.put("/countries/{country_code}", response_model=CountryRiskItemDTO)
async def update_country_risk(
    country_code: str,
    payload: UpdateCountryRiskDTO,
    repo: Annotated[RegulatorRepository, Depends(get_repo)],
    _user: Annotated[AuthenticatedUser, Depends(require_regulator_admin)],
) -> CountryRiskItemDTO:
    """Обновление санкционного веса риска страны (правила диктует Минпромторг РФ)"""
    country = await repo.update_country(
        country_code=country_code,
        risk_factor=payload.risk_factor,
        is_unfriendly=payload.is_unfriendly,
        sanctions_regime=payload.sanctions_regime,
    )
    return CountryRiskItemDTO(
        country_code=country.country_code,
        country_name=country.country_name,
        risk_factor=country.risk_factor,
        is_unfriendly=country.is_unfriendly,
        sanctions_regime=country.sanctions_regime,
    )


@router.post("/countries", response_model=CountryRiskItemDTO, status_code=status.HTTP_201_CREATED)
async def create_country_risk(
    payload: CreateCountryRiskDTO,
    repo: Annotated[RegulatorRepository, Depends(get_repo)],
    _user: Annotated[AuthenticatedUser, Depends(require_regulator_admin)],
) -> CountryRiskItemDTO:
    """Добавление новой юрисдикции в государственный реестр рисков"""
    country = await repo.create_country(
        country_code=payload.country_code,
        country_name=payload.country_name,
        risk_factor=payload.risk_factor,
        is_unfriendly=payload.is_unfriendly,
        sanctions_regime=payload.sanctions_regime,
    )
    return CountryRiskItemDTO(
        country_code=country.country_code,
        country_name=country.country_name,
        risk_factor=country.risk_factor,
        is_unfriendly=country.is_unfriendly,
        sanctions_regime=country.sanctions_regime,
    )


@router.put("/products/{product_id}/strategic-status", response_model=dict)
async def set_product_strategic_status(
    product_id: int,
    payload: SetStrategicStatusDTO,
    repo: Annotated[RegulatorRepository, Depends(get_repo)],
    _user: Annotated[AuthenticatedUser, Depends(require_regulator_admin)],
) -> dict:
    """Присвоение предприятию/изделию статуса стратегической важности (ОПК / КИИ)"""
    product = await repo.set_product_strategic_status(
        product_id=product_id,
        is_strategic=payload.is_strategic,
        strategic_priority=payload.strategic_priority,
        strategic_notes=payload.strategic_notes,
    )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Изделие не найдено")
    return {
        "success": True,
        "product_id": product.id,
        "enterprise_name": product.enterprise_name,
        "is_strategic": product.is_strategic,
        "strategic_priority": product.strategic_priority,
        "strategic_notes": product.strategic_notes,
    }


@router.get("/audit/{product_id}", response_model=PP719AuditResponseDTO)
async def get_compliance_audit(
    product_id: int,
    repo: Annotated[RegulatorRepository, Depends(get_repo)],
) -> PP719AuditResponseDTO:
    """Официальный аудит изделия по критериям ПП РФ № 719 и детекция O-Ring уязвимостей"""
    try:
        service = ComplianceService(repo)
        return await service.evaluate_product(product_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception("Ошибка аудита ПП РФ № 719 для изделия #%s", product_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервиса при проведении регуляторного аудита",
        ) from e


@router.post("/simulate-shock", response_model=SanctionsShockResultDTO)
async def simulate_sanctions_shock(
    payload: SanctionsShockRequestDTO,
    repo: Annotated[RegulatorRepository, Depends(get_repo)],
) -> SanctionsShockResultDTO:
    """Смоделировать каскадный санкционный шок и рассчитать дни до останова конвейера"""
    try:
        service = SanctionsService(repo)
        return await service.simulate_shock(payload)
    except Exception as e:
        logger.exception("Ошибка симуляции санкционного шока для изделия #%s", payload.product_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервиса при моделировании санкционного шока",
        ) from e


@router.post("/ai-scenario", response_model=AIScenarioResponseDTO)
async def generate_ai_scenario(
    payload: AIScenarioRequestDTO,
    repo: Annotated[RegulatorRepository, Depends(get_repo)],
) -> AIScenarioResponseDTO:
    """ИИ-агент геополитического стресс-моделирования (OpenRouter LLM + Отраслевой аудит + Алерт ОПК)"""
    service = AIScenarioService(repo)
    return await service.generate_scenario(payload, repo=repo)


@router.get("/certificates/{product_id}", response_model=CertificateResponseDTO)
async def get_product_certificate(
    product_id: int,
    repo: Annotated[RegulatorRepository, Depends(get_repo)],
) -> CertificateResponseDTO:
    """Получить действующее цифровое заключение Минпромторга для изделия"""
    try:
        service = CertificateService(repo)
        cert = await service.get_latest_certificate(product_id)
        if not cert:
            cert = await service.issue_certificate(IssueCertificateRequestDTO(product_id=product_id))
        return cert
    except Exception as e:
        logger.exception("Ошибка получения цифрового заключения для изделия #%s", product_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервиса при получении цифрового заключения",
        ) from e


@router.post("/issue-certificate", response_model=CertificateResponseDTO)
async def issue_compliance_certificate(
    payload: IssueCertificateRequestDTO,
    repo: Annotated[RegulatorRepository, Depends(get_repo)],
    _user: Annotated[AuthenticatedUser, Depends(require_regulator_admin)],
) -> CertificateResponseDTO:
    """Выдать цифровое заключение Минпромторга с цифровой подписью SHA-256 и QR-кодом"""
    try:
        service = CertificateService(repo)
        return await service.issue_certificate(payload)
    except Exception as e:
        logger.exception("Ошибка выдачи цифрового заключения для изделия #%s", payload.product_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервиса при выпуске цифрового заключения",
        ) from e
