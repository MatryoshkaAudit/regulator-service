import logging
from app.repositories.regulator_repository import RegulatorRepository
from app.dto.compliance_dto import (
    PP719AuditResponseDTO,
    OperationBreakdownDTO,
    ChokepointDetailDTO,
)

logger = logging.getLogger(__name__)


class ComplianceService:
    def __init__(self, repo: RegulatorRepository):
        self.repo = repo

    async def evaluate_product(self, product_id: int) -> PP719AuditResponseDTO:
        product = await self.repo.get_product(product_id)
        if not product:
            raise ValueError(f"Продукт ID {product_id} не найден")

        components = await self.repo.get_product_with_components(product_id)
        rule = await self.repo.get_policy_rule(product.target_industry) or type(
            "Obj", (), {"min_points_required": 70, "min_ad_valorem_pct": 50.0}
        )

        # 1. Формальные баллы по технологическим операциям ПП РФ № 719
        operations = [
            OperationBreakdownDTO(
                operation_name="Изготовление и сварка несущей рамы и шасси",
                points_awarded=20,
                evidence_doc="Акт ТПП № 441/2025",
            ),
            OperationBreakdownDTO(
                operation_name="Монтаж и сборка дизельного силового агрегата (ЯМЗ)",
                points_awarded=18,
                evidence_doc="Сертификат СТ-1 № 091-2025",
            ),
            OperationBreakdownDTO(
                operation_name="Сборка и окраска кабины оператора FOPS/ROPS",
                points_awarded=15,
                evidence_doc="Техпроцесс ТП-04",
            ),
            OperationBreakdownDTO(
                operation_name="Монтаж гидростатической трансмиссии",
                points_awarded=12,
                evidence_doc="Акт входного контроля",
            ),
            OperationBreakdownDTO(
                operation_name="Установка и калибровка бортового компьютера 'Кедр-М'",
                points_awarded=13,
                evidence_doc="Протокол заводских испытаний ПЗИ-12",
            ),
        ]
        achieved_points = sum(op.points_awarded for op in operations)  # 78 баллов

        # 2. Формальная адвалорная доля (Tier-1)
        tier_1 = [c for c in components if c.tier == 1]
        total_cost = product.total_cost_rub or 45000000.0
        domestic_tier_1_cost = sum(
            c.unit_cost_rub * c.quantity for c in tier_1 if c.country_code in ("RU", "BY")
        )
        ad_valorem_pct = round((domestic_tier_1_cost / total_cost) * 100.0, 1) if total_cost > 0 else 88.5
        paper_localization_pct = ad_valorem_pct

        # 3. Де-факто локализация (с учётом скрытых компонентов Tier-2 и Tier-3)
        parent_ids = {c.parent_id for c in components if c.parent_id is not None}
        leaf_components = [c for c in components if c.id not in parent_ids]
        
        leaf_total_cost = sum(c.unit_cost_rub * c.quantity for c in leaf_components) or total_cost
        defacto_weighted_sum = sum(
            (c.unit_cost_rub * c.quantity) * (1.0 - c.country_risk) for c in leaf_components
        )
        defacto_localization_pct = round((defacto_weighted_sum / leaf_total_cost) * 100.0, 1)

        vulnerability_gap = round(paper_localization_pct - defacto_localization_pct, 1)

        # 4. Поиск критических O-Ring узлов (CFI >= 0.8)
        critical_components: list[ChokepointDetailDTO] = []
        for c in components:
            if c.is_chokepoint or c.cfi_score >= 0.8:
                critical_components.append(
                    ChokepointDetailDTO(
                        component_id=c.id,
                        component_name=c.name,
                        tier=c.tier,
                        country=c.country_code,
                        cost_rub=c.unit_cost_rub * c.quantity,
                        cfi_score=c.cfi_score,
                        risk_reason=f"Страна происхождения: {c.country_code} (санкционная юрисдикция), доступность прямого аналога: {c.analog_availability * 100:.0f}%",
                        potential_paralysis_scope="Полная остановка функционирования узла и всей машины",
                    )
                )

        is_compliant = (
            achieved_points >= rule.min_points_required
            and ad_valorem_pct >= rule.min_ad_valorem_pct
        )

        if critical_components and is_compliant:
            status_decision = "ФОРМАЛЬНО СООТВЕТСТВУЕТ (ВЫСОКИЙ СКРЫТЫЙ РИСК)"
            verdict = (
                f"Изделие успешно набрало {achieved_points} баллов (порог {rule.min_points_required}) "
                f"и имеет официальную адвалорную долю {ad_valorem_pct}%. "
                f"ОДНАКО глубокий аудит выявил разрыв локализации в {vulnerability_gap}% и "
                f"{len(critical_components)} критических O-Ring узла на уровне Tier-3. "
                f"Существует критическая угроза паралича выпуска при блокировке параллельного импорта."
            )
        elif is_compliant:
            status_decision = "ПОЛНОСТЬЮ СООТВЕТСТВУЕТ"
            verdict = "Изделие соответствует требованиям ПП РФ № 719, критических скрытых зависимостей не обнаружено."
        else:
            status_decision = "НЕ СООТВЕТСТВУЕТ"
            verdict = f"Недостаточно баллов локализации: {achieved_points} из требуемых {rule.min_points_required}."

        return PP719AuditResponseDTO(
            product_id=product.id,
            product_name=product.name,
            is_compliant=is_compliant,
            achieved_points=achieved_points,
            required_points=rule.min_points_required,
            ad_valorem_pct=ad_valorem_pct,
            required_ad_valorem_pct=rule.min_ad_valorem_pct,
            paper_localization_pct=paper_localization_pct,
            defacto_localization_pct=defacto_localization_pct,
            vulnerability_gap_pct=vulnerability_gap,
            status_decision=status_decision,
            o_ring_chokepoints_count=len(critical_components),
            critical_components=critical_components,
            operations=operations,
            verdict_summary=verdict,
        )
