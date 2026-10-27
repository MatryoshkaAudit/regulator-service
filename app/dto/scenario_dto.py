from pydantic import BaseModel, Field


class AIScenarioRequestDTO(BaseModel):
    product_id: int = Field(default=1, ge=1)
    geopolitical_event: str = Field(
        default="США и ЕС ужесточили санкции: блокада транзитных хабов в ОАЭ и Турции, банки Китая заблокировали 70% расчетов за микроэлектронику",
        min_length=3,
        max_length=1000,
    )
    target_industry: str = Field(
        default="Машиностроение и станкостроение",
        min_length=2,
        max_length=255,
    )


class AISupplyChainImpactDTO(BaseModel):
    node_name: str
    country: str
    severity: str  # "CRITICAL" | "HIGH" | "MEDIUM"
    consequence: str


class IndustrySubstitutionAuditDTO(BaseModel):
    industry_name: str
    base_substitution_pct: float
    post_shock_substitution_pct: float
    vulnerability_delta_pct: float
    paralysis_risk_pct: float
    plants_at_risk_count: int
    total_plants_count: int


class StrategicPlantAlertDTO(BaseModel):
    product_id: int
    enterprise_name: str
    product_name: str
    strategic_priority: str  # "CRITICAL" | "HIGH"
    strategic_notes: str
    critical_tier3_chokepoints: list[str]
    days_to_production_halt: int
    financial_loss_rub: float
    urgency_action: str


class AIScenarioResponseDTO(BaseModel):
    scenario_id: str
    scenario_title: str
    geopolitical_context: str
    severity_score: float  # 0.0 .. 1.0
    calibrated_country_risks: dict[str, float] = Field(default_factory=dict)
    impacted_hs_codes: list[str] = Field(default_factory=list)
    affected_supply_chains: list[AISupplyChainImpactDTO] = Field(default_factory=list)
    systemic_failure_risk_pct: float
    industry_audits: list[IndustrySubstitutionAuditDTO] = Field(default_factory=list)
    strategic_plants_at_risk: list[StrategicPlantAlertDTO] = Field(default_factory=list)
    regulatory_remedies: list[str] = Field(default_factory=list)
    executive_verdict: str
    generated_by_model: str
