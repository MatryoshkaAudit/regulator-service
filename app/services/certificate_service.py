from datetime import datetime, timedelta
import hashlib
import random

from app.repositories.regulator_repository import RegulatorRepository
from app.services.compliance_service import ComplianceService
from app.dto.certificate_dto import IssueCertificateRequestDTO, CertificateResponseDTO
from matryoshka_db.db_models import Certificate, ComplianceStatusEnum, AuditActorTypeEnum


class CertificateService:
    def __init__(self, repo: RegulatorRepository):
        self.repo = repo
        self.compliance_service = ComplianceService(repo)

    async def issue_certificate(self, req: IssueCertificateRequestDTO) -> CertificateResponseDTO:
        audit_res = await self.compliance_service.evaluate_product(req.product_id)

        reg_number = f"RU-МПТ-719/{datetime.utcnow().year}-{random.randint(10000, 99999)}"
        issued_at = datetime.utcnow()
        expires_at = issued_at + timedelta(days=req.valid_months * 30)

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
