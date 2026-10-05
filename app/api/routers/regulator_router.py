from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_manager, get_db_session
from app.repositories.regulator_repository import RegulatorRepository
from app.services.compliance_service import ComplianceService
from app.services.sanctions_service import SanctionsService
from app.services.ai_scenario_service import AIScenarioService
from app.services.certificate_service import CertificateService
from app.dto.compliance_dto import PP719AuditResponseDTO
from app.dto.sanctions_dto import SanctionsShockRequestDTO, SanctionsShockResultDTO
from app.dto.scenario_dto import AIScenarioRequestDTO, AIScenarioResponseDTO
from app.dto.certificate_dto import IssueCertificateRequestDTO, CertificateResponseDTO

router = APIRouter(prefix="/api/v1/regulator", tags=["Regulator Control Center"])


def get_repo(session: AsyncSession = Depends(get_db_session)) -> RegulatorRepository:
    return RegulatorRepository(session)


@router.get("/audit/{product_id}", response_model=PP719AuditResponseDTO)
async def get_compliance_audit(
    product_id: int,
    repo: RegulatorRepository = Depends(get_repo),
):
    """Официальный аудит изделия по критериям ПП РФ № 719 и детекция O-Ring уязвимостей"""
    try:
        service = ComplianceService(repo)
        return await service.evaluate_product(product_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка аудита: {str(e)}")


@router.post("/simulate-shock", response_model=SanctionsShockResultDTO)
async def simulate_sanctions_shock(
    payload: SanctionsShockRequestDTO,
    repo: RegulatorRepository = Depends(get_repo),
):
    """Смоделировать каскадный санкционный шок и рассчитать дни до останова конвейера"""
    try:
        service = SanctionsService(repo)
        return await service.simulate_shock(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка симуляции: {str(e)}")


@router.post("/ai-scenario", response_model=AIScenarioResponseDTO)
async def generate_ai_scenario(
    payload: AIScenarioRequestDTO,
):
    """Сгенерировать ИИ-сценарий геополитического стресс-теста (OpenRouter LLM Pipeline)"""
    service = AIScenarioService()
    return await service.generate_scenario(payload)


@router.post("/issue-certificate", response_model=CertificateResponseDTO)
async def issue_compliance_certificate(
    payload: IssueCertificateRequestDTO,
    repo: RegulatorRepository = Depends(get_repo),
):
    """Выдать цифровое заключение Минпромторга с цифровой подписью SHA-256 и QR-кодом"""
    try:
        service = CertificateService(repo)
        return await service.issue_certificate(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка выдачи сертификата: {str(e)}")
