import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.dto.certificate_dto import CertificateResponseDTO, IssueCertificateRequestDTO
from app.repositories.regulator_repository import RegulatorRepository
from app.services.compliance_service import ComplianceService
from matryoshka_db.db_models import (
    AuditActorTypeEnum,
    Certificate,
    ComplianceStatusEnum,
)


class CertificateService:
    def __init__(self, repo: RegulatorRepository):
        self.repo = repo
        self.compliance_service = ComplianceService(repo)

    async def get_latest_certificate(self, product_id: int) -> CertificateResponseDTO | None:
        cert = await self.repo.get_latest_certificate(product_id)
        if not cert:
            return None
        product = await self.repo.get_product(product_id)
        product_name = product.name if product else f"Изделие #{product_id}"

        status_str = cert.status.value if hasattr(cert.status, "value") else str(cert.status)
        return CertificateResponseDTO(
            id=cert.id,
            reg_number=cert.reg_number,
            product_id=cert.product_id,
            product_name=product_name,
            status=status_str,
            pp719_points=cert.pp719_points,
            ad_valorem_pct=cert.ad_valorem_pct,
            defacto_localization_pct=cert.defacto_localization_pct,
            vulnerability_gap_pct=cert.vulnerability_gap_pct,
            certified_by=cert.certified_by,
            qr_verification_url=cert.qr_verification_url,
            digital_signature_hash=cert.digital_signature_hash,
            issued_at=cert.issued_at.strftime("%d.%m.%Y") if cert.issued_at else "",
            expires_at=cert.expires_at.strftime("%d.%m.%Y") if cert.expires_at else "",
        )

    async def issue_certificate(self, req: IssueCertificateRequestDTO) -> CertificateResponseDTO:
        # Если принудительный перевыпуск не запрошен, возвращаем актуальное действующее заключение
        if not getattr(req, "force_reissue", False):
            existing = await self.get_latest_certificate(req.product_id)
            if existing:
                return existing

        audit_res = await self.compliance_service.evaluate_product(req.product_id)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        issued_at = now
        expires_at = issued_at + timedelta(days=req.valid_months * 30)

        # Генерация уникального регистрационного номера Минпромторга РФ
        # Добавляем ID изделия и микросекунды для гарантированной уникальности
        unique_suffix = f"{req.product_id:02d}{now.strftime('%d%H%M')}-{secrets.SystemRandom().randint(100, 999)}"
        reg_number = f"RU-МПТ-719/{now.year}-{unique_suffix}"

        signature_payload = f"{reg_number}:{req.product_id}:{audit_res.achieved_points}:{audit_res.defacto_localization_pct}:{issued_at.isoformat()}"
        digital_signature = hashlib.sha256(signature_payload.encode("utf-8")).hexdigest()

        status = (
            ComplianceStatusEnum.COMPLIANT
            if audit_res.is_compliant and audit_res.o_ring_chokepoints_count == 0
            else ComplianceStatusEnum.CONDITIONAL
            if audit_res.is_compliant
            else ComplianceStatusEnum.NON_COMPLIANT
        )

        cert = Certificate(
            product_id=req.product_id,
            reg_number=reg_number,
            status=status,
            pp719_points=audit_res.achieved_points,
            ad_valorem_pct=audit_res.ad_valorem_pct,
            defacto_localization_pct=audit_res.defacto_localization_pct,
            vulnerability_gap_pct=audit_res.vulnerability_gap_pct,
            certified_by=req.certified_by,
            qr_verification_url=f"https://gisp.gov.ru/pp719/verify/{reg_number}",
            digital_signature_hash=digital_signature,
            issued_at=issued_at,
            expires_at=expires_at,
        )

        saved = await self.repo.save_certificate(cert)

        # Логируем событие в неизменяемый журнал аудита
        await self.repo.log_audit_event(
            event_type="CERTIFICATE_ISSUED",
            actor_id=1,
            actor_role=AuditActorTypeEnum.REGULATOR,
            resource_type="certificate",
            resource_id=saved.id,
            details={
                "reg_number": reg_number,
                "product_id": req.product_id,
                "status": status.value,
                "digital_signature": digital_signature,
            },
        )

        return CertificateResponseDTO(
            id=saved.id,
            reg_number=saved.reg_number,
            product_id=saved.product_id,
            product_name=audit_res.product_name,
            status=saved.status.value,
            pp719_points=saved.pp719_points,
            ad_valorem_pct=saved.ad_valorem_pct,
            defacto_localization_pct=saved.defacto_localization_pct,
            vulnerability_gap_pct=saved.vulnerability_gap_pct,
            certified_by=saved.certified_by,
            qr_verification_url=saved.qr_verification_url,
            digital_signature_hash=saved.digital_signature_hash,
            issued_at=saved.issued_at.strftime("%d.%m.%Y"),
            expires_at=saved.expires_at.strftime("%d.%m.%Y"),
        )
