from pydantic import BaseModel, Field


class AIScenarioRequestDTO(BaseModel):
    product_id: int = 1
    geopolitical_event: str = "14-й пакет санкций ЕС: полный запрет на реэкспорт микроэлектроники и систем ЧПУ через страны ЕАЭС"
    target_industry: str = "Лесозаготовительное машиностроение"


class AISupplyChainImpactDTO(BaseModel):
    node_name: str
    country: str
    severity: str  # "CRITICAL" | "HIGH" | "MEDIUM"
    consequence: str


class AIScenarioResponseDTO(BaseModel):
    scenario_id: str
    scenario_title: str
    geopolitical_context: str
    severity_score: float # 0.0 .. 1.0
    affected_supply_chains: list[AISupplyChainImpactDTO] = Field(default_factory=list)
    systemic_failure_risk_pct: float
    regulatory_remedies: list[str] = Field(default_factory=list)
    executive_verdict: str
    generated_by_model: str
