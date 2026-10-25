from pydantic import BaseModel


class IssueCertificateRequestDTO(BaseModel):
    product_id: int
    certified_by: str = "Департамент машиностроения Минпромторга РФ"
    valid_months: int = 12
    force_reissue: bool = False


class CertificateResponseDTO(BaseModel):
    id: int
    reg_number: str
    product_id: int
    product_name: str
    status: str
    pp719_points: int
    ad_valorem_pct: float
    defacto_localization_pct: float
    vulnerability_gap_pct: float
    certified_by: str
    qr_verification_url: str
    digital_signature_hash: str
    issued_at: str
    expires_at: str
