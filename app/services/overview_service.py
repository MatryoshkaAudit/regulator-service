import logging
from app.repositories.regulator_repository import RegulatorRepository
from app.dto.overview_dto import (
    PlantOverviewItemDTO,
    HiddenImportItemDTO,
    CountryRiskItemDTO,
)

logger = logging.getLogger(__name__)


class OverviewService:
    def __init__(self, repo: RegulatorRepository):
        self.repo = repo

    async def get_monitoring_overview(self) -> list[PlantOverviewItemDTO]:
        """Сводный мониторинг всех поданных спецификаций от предприятий с оценкой риска останова"""
        products = await self.repo.get_all_products()
        country_risks = await self.repo.get_country_risks()
        overview_list: list[PlantOverviewItemDTO] = []

        for p in products:
            components = await self.repo.get_product_with_components(p.id)
            if not components:
                overview_list.append(
                    PlantOverviewItemDTO(
                        product_id=p.id,
                        product_name=p.name,
                        article=p.article,
                        category=p.category,
                        target_industry=p.target_industry,
                        enterprise_name=p.enterprise_name,
                        enterprise_inn=p.enterprise_inn,
                        enterprise_city=p.enterprise_city,
                        total_cost_rub=p.total_cost_rub,
                        is_strategic=p.is_strategic,
                        strategic_priority=p.strategic_priority,
                        strategic_notes=p.strategic_notes,
                        paper_localization_pct=85.0,
                        defacto_localization_pct=85.0,
                        vulnerability_gap_pct=0.0,
                        chokepoints_count=0,
                        o_ring_stop_risk_pct=5.0,
                        days_to_halt=180,
                        status_label="СПЕЦИФИКАЦИЯ ФОРМИРУЕТСЯ",
                    )
                )
                continue

            # Синхронизация страновых рисков
            for c in components:
                if c.country_code in country_risks:
                    c.country_risk = country_risks[c.country_code]
                c.cfi_score = float(c.criticality) * float(c.country_risk) * (1.0 - float(c.analog_availability))
                c.is_chokepoint = c.cfi_score >= 0.70

            # Поиск листьев дерева
            parent_ids = {c.parent_id for c in components if c.parent_id is not None}
            leaves = [c for c in components if c.id not in parent_ids]
            total_leaf_cost = sum(c.unit_cost_rub * c.quantity for c in leaves) or p.total_cost_rub or 1.0

            # 1. Динамическая бумажная локализация по Tier-1
            tier1 = [c for c in components if c.tier == 1]
            if tier1:
                tot_t1 = sum(c.unit_cost_rub * c.quantity for c in tier1)
                eaeu_t1 = sum(c.unit_cost_rub * c.quantity for c in tier1 if c.country_code in ("RU", "BY", "KZ", "AM", "KG"))
                paper_loc = round((eaeu_t1 / tot_t1) * 100.0, 1) if tot_t1 > 0 else 100.0
            else:
                top_level = [c for c in components if c.parent_id is None]
                tot_top = sum(c.unit_cost_rub * c.quantity for c in top_level) or 1.0
                eaeu_top = sum(c.unit_cost_rub * c.quantity for c in top_level if c.country_code in ("RU", "BY", "KZ", "AM", "KG"))
                paper_loc = round((eaeu_top / tot_top) * 100.0, 1) if components else 100.0

            # 2. Непрерывная де-факто локализация (листья + аналоговые коэффициенты)
            weighted_safe = sum(
                ((c.unit_cost_rub * c.quantity) / total_leaf_cost)
                * (1.0 - c.country_risk)
                * (1.0 if c.analog_status == "FULL_COMPATIBLE" else (0.7 if c.analog_status == "REQUIRES_REWORK" else (1.0 if c.country_code in ("RU", "BY") else 0.0)))
                for c in leaves
            )
            raw_defacto_pct = round(weighted_safe * 100.0, 1)

            # 3. Мультипликативный O-Ring риск остановки конвейера
            chokepoints = [c for c in leaves if c.is_chokepoint or c.cfi_score >= 0.70]
            chokepoints_count = len(chokepoints)

            o_ring_multiplier = 1.0
            for choke in chokepoints:
                o_ring_multiplier *= (1.0 - 0.25 * float(choke.cfi_score))

            defacto_loc = round(raw_defacto_pct * o_ring_multiplier, 1)
            gap_pct = max(0.0, round(paper_loc - defacto_loc, 1))

            # Вероятность останова конвейера P_halt = 1 - prod(1 - Risk_j)
            if chokepoints:
                prod_safe = 1.0
                for choke in chokepoints:
                    prod_safe *= (1.0 - float(choke.country_risk))
                stop_risk_pct = round((1.0 - prod_safe) * 100.0, 1)
                days_to_halt = min((getattr(c, "lead_time_days", None) or (14 if c.country_risk >= 0.9 else 28)) for c in chokepoints)
            else:
                stop_risk_pct = 5.0
                days_to_halt = 360

            if chokepoints_count >= 2 or stop_risk_pct >= 80.0:
                status_label = "КРИТИЧЕСКИЙ РИСК ОСТАНОВА"
            elif chokepoints_count >= 1 or stop_risk_pct >= 50.0:
                status_label = "УМЕРЕННЫЙ РИСК (ЗАВИСИМОСТЬ)"
            else:
                status_label = "ЧЕСТНЫЙ СУВЕРЕНИТЕТ"

            overview_list.append(
                PlantOverviewItemDTO(
                    product_id=p.id,
                    product_name=p.name,
                    article=p.article,
                    category=p.category,
                    target_industry=p.target_industry,
                    enterprise_name=p.enterprise_name,
                    enterprise_inn=p.enterprise_inn,
                    enterprise_city=p.enterprise_city,
                    total_cost_rub=p.total_cost_rub,
                    is_strategic=p.is_strategic,
                    strategic_priority=p.strategic_priority,
                    strategic_notes=p.strategic_notes,
                    paper_localization_pct=paper_loc,
                    defacto_localization_pct=defacto_loc,
                    vulnerability_gap_pct=gap_pct,
                    chokepoints_count=chokepoints_count,
                    o_ring_stop_risk_pct=stop_risk_pct,
                    days_to_halt=days_to_halt,
                    status_label=status_label,
                )
            )

        return overview_list

    async def get_hidden_imports(self) -> list[HiddenImportItemDTO]:
        """Выявление скрытого критического импорта на 3-м уровне (Tier-3)"""
        components = await self.repo.get_all_components()
        countries_dict = {c.country_code: c.country_name for c in await self.repo.get_all_countries()}
        hidden_items: list[HiddenImportItemDTO] = []

        for c in components:
            # Отбираем узлы 3-го уровня или узлы с риском страны > 0
            if c.tier == 3 or (c.country_risk > 0.1 and c.country_code not in ("RU", "BY")):
                prod = c.product
                parent_name = c.parent.name if c.parent else "Корневой агрегат"
                country_name = countries_dict.get(c.country_code, c.country_code)

                concealment_notes = (
                    f"Узел замаскирован в спецификации внутри «{parent_name}» (Tier-{c.parent.tier if c.parent else 1}). "
                    f"При санкциях на {country_name} выпуск изделия «{prod.name}» невозможен."
                )

                hidden_items.append(
                    HiddenImportItemDTO(
                        component_id=c.id,
                        product_id=prod.id,
                        product_name=prod.name,
                        enterprise_name=prod.enterprise_name,
                        is_strategic=prod.is_strategic,
                        component_name=c.name,
                        article=c.article,
                        tier=c.tier,
                        hs_code=c.hs_code or "8542",
                        country_code=c.country_code,
                        country_name=country_name,
                        country_risk=c.country_risk,
                        unit_cost_rub=c.unit_cost_rub,
                        quantity=c.quantity,
                        total_cost_rub=round(c.unit_cost_rub * c.quantity, 2),
                        analog_status=c.analog_status or "NO_ANALOGS",
                        cfi_score=c.cfi_score,
                        is_chokepoint=c.is_chokepoint,
                        parent_assembly_name=parent_name,
                        concealment_notes=concealment_notes,
                    )
                )

        # Сортируем: сначала самые опасные chokepoints и компоненты стратегических предприятий
        hidden_items.sort(key=lambda x: (x.is_strategic, x.is_chokepoint, x.cfi_score), reverse=True)
        return hidden_items

    async def get_countries_list(self) -> list[CountryRiskItemDTO]:
        """Список всех юрисдикций с весами рисков для административной панели"""
        countries = await self.repo.get_all_countries()
        return [
            CountryRiskItemDTO(
                country_code=c.country_code,
                country_name=c.country_name,
                risk_factor=c.risk_factor,
                is_unfriendly=c.is_unfriendly,
                sanctions_regime=c.sanctions_regime,
            )
            for c in countries
        ]
