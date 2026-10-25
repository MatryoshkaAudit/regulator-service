from pydantic import BaseModel, Field

from app.dto.compliance_dto import ChokepointDetailDTO


class SanctionsShockRequestDTO(BaseModel):
    product_id: int = 1
    shock_name: str = "Пакет санкций / Блокировка транзита"
    blocked_countries: list[str] = Field(default_factory=lambda: ["CH", "DE", "US", "FR"])
    blocked_categories: list[str] = Field(default_factory=lambda: ["микроконтроллеры", "топливная аппаратура"])
    secondary_sanctions_applied: bool = True


class SanctionsShockResultDTO(BaseModel):
    product_id: int
    product_name: str
    scenario_title: str
    paralysis_risk_pct: float
    blocked_components_count: int
    total_blocked_value_rub: float
    estimated_days_to_halt: int
    blocked_chokepoints: list[ChokepointDetailDTO] = Field(default_factory=list)
    impact_analysis: str
    recommended_mitigation: str
