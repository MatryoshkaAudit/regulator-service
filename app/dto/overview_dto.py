from pydantic import BaseModel, Field


class PlantOverviewItemDTO(BaseModel):
    product_id: int
    product_name: str
    article: str
    category: str
    target_industry: str
    enterprise_name: str
    enterprise_inn: str | None
    enterprise_city: str | None
    total_cost_rub: float
    is_strategic: bool
    strategic_priority: str
    strategic_notes: str | None
    paper_localization_pct: float
    defacto_localization_pct: float
    vulnerability_gap_pct: float
    chokepoints_count: int
    o_ring_stop_risk_pct: float
    days_to_halt: int
    status_label: str


class CountryRiskItemDTO(BaseModel):
    country_code: str
    country_name: str
    risk_factor: float
    is_unfriendly: bool
    sanctions_regime: str | None = None


class UpdateCountryRiskDTO(BaseModel):
    risk_factor: float = Field(ge=0.0, le=1.0)
    is_unfriendly: bool | None = None
    sanctions_regime: str | None = None


class CreateCountryRiskDTO(BaseModel):
    country_code: str = Field(min_length=2, max_length=3)
    country_name: str = Field(min_length=2, max_length=100)
    risk_factor: float = Field(default=0.5, ge=0.0, le=1.0)
    is_unfriendly: bool = False
    sanctions_regime: str | None = Field(default=None, max_length=100)


class SetStrategicStatusDTO(BaseModel):
    is_strategic: bool
    strategic_priority: str = Field(default="CRITICAL", max_length=50)  # "CRITICAL", "HIGH", "NORMAL"
    strategic_notes: str | None = Field(default=None, max_length=500)


class HiddenImportItemDTO(BaseModel):
    component_id: int
    product_id: int
    product_name: str
    enterprise_name: str
    is_strategic: bool
    component_name: str
    article: str
    tier: int
    hs_code: str
    country_code: str
    country_name: str
    country_risk: float
    unit_cost_rub: float
    quantity: float
    total_cost_rub: float
    analog_status: str
    cfi_score: float
    is_chokepoint: bool
    parent_assembly_name: str
    concealment_notes: str
