from pydantic import BaseModel, Field


class OperationBreakdownDTO(BaseModel):
    operation_name: str
    points_awarded: int
    verified: bool = True
    evidence_doc: str = ""


class ChokepointDetailDTO(BaseModel):
    component_id: int
    component_name: str
    tier: int
    country: str
    cost_rub: float
    cfi_score: float
    risk_reason: str
    potential_paralysis_scope: str


class PP719AuditResponseDTO(BaseModel):
    product_id: int
    product_name: str
    standard_name: str = "ПП РФ № 719"
    is_compliant: bool
    achieved_points: int
    required_points: int
    ad_valorem_pct: float
    required_ad_valorem_pct: float
    paper_localization_pct: float
    defacto_localization_pct: float
    vulnerability_gap_pct: float
    status_decision: str
    o_ring_chokepoints_count: int
    critical_components: list[ChokepointDetailDTO] = Field(default_factory=list)
    operations: list[OperationBreakdownDTO] = Field(default_factory=list)
    verdict_summary: str
