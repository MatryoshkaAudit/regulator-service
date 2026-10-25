import logging

from app.dto.compliance_dto import (
    ChokepointDetailDTO,
    OperationBreakdownDTO,
    PP719AuditResponseDTO,
)
from app.repositories.regulator_repository import RegulatorRepository

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

        # 1. Формальные технологические операции заявителя по ПП РФ № 719
        cat_lower = (product.category or "").lower()
        if "станк" in cat_lower or "робот" in cat_lower:
            operations = [
                OperationBreakdownDTO(
                    operation_name="Механическая обработка чугунной станины и направляющих",
                    points_awarded=28,
                    evidence_doc="Акт ТПП № СТ-102/2026",
                ),
                OperationBreakdownDTO(
                    operation_name="Монтаж и юстировка шпиндельного узла и сервоприводов",
                    points_awarded=22,
                    evidence_doc="Техпроцесс ТП-СТАНКОМАШ-08",
                ),
                OperationBreakdownDTO(
                    operation_name="Сборка шкафа электроавтоматики и ЧПУ в РФ",
                    points_awarded=20,
                    evidence_doc="Протокол заводских испытаний ПЗИ-ЧПУ",
                ),
                OperationBreakdownDTO(
                    operation_name="Монтаж защитных ограждений и кабинетной защиты",
                    points_awarded=15,
                    evidence_doc="Паспорт сборочной единицы",
                ),
            ]
        elif "сельхоз" in cat_lower or "комбайн" in cat_lower:
            operations = [
                OperationBreakdownDTO(
                    operation_name="Раскрой, гибка и сварка несущей рамы и бункера",
                    points_awarded=25,
                    evidence_doc="Акт ТПП № АГРО-411",
                ),
                OperationBreakdownDTO(
                    operation_name="Установка отечественного дизельного двигателя (ЯМЗ)",
                    points_awarded=20,
                    evidence_doc="Сертификат СТ-1 силового агрегата",
                ),
                OperationBreakdownDTO(
                    operation_name="Сборка молотильно-сепарирующего устройства (МСУ)",
                    points_awarded=18,
                    evidence_doc="Техпроцесс завода",
                ),
                OperationBreakdownDTO(
                    operation_name="Монтаж и калибровка кабины с климатической системой",
                    points_awarded=17,
                    evidence_doc="Акт входного контроля",
                ),
            ]
        else:
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
        achieved_points = sum(op.points_awarded for op in operations)

        # 2. Динамический расчет де-юре (бумажной) адвалорной доли по нормам ПП РФ № 719 / СТ-1
        tier1_components = [c for c in components if c.tier == 1]
        if tier1_components:
            tot_t1 = sum(c.unit_cost_rub * c.quantity for c in tier1_components)
            if tot_t1 > 0:
                eaeu_t1 = sum(c.unit_cost_rub * c.quantity for c in tier1_components if c.country_code in ("RU", "BY", "KZ", "AM", "KG"))
                paper_localization_pct = round((eaeu_t1 / tot_t1) * 100.0, 1)
            else:
                paper_localization_pct = 100.0
        else:
            top_level = [c for c in components if c.parent_id is None]
            tot_top = sum(c.unit_cost_rub * c.quantity for c in top_level) or 1.0
            eaeu_top = sum(c.unit_cost_rub * c.quantity for c in top_level if c.country_code in ("RU", "BY", "KZ", "AM", "KG"))
            paper_localization_pct = round((eaeu_top / tot_top) * 100.0, 1) if components else 100.0

        ad_valorem_pct = paper_localization_pct

        # 3. Выявление критических O-Ring узлов (CFI >= 0.70)
        critical_components: list[ChokepointDetailDTO] = []
        for c in components:
            if c.is_chokepoint or c.cfi_score >= 0.70:
                critical_components.append(
                    ChokepointDetailDTO(
                        component_id=c.id,
                        component_name=c.name,
                        tier=c.tier,
                        country=c.country_code,
                        cost_rub=c.unit_cost_rub * c.quantity,
                        cfi_score=c.cfi_score,
                        risk_reason=f"Страна происхождения: {c.country_code} (риск {c.country_risk:.2f}), доступность аналога: {c.analog_availability * 100:.0f}%",
                        potential_paralysis_scope="Полная остановка функционирования узла и сборочной линии",
                    )
                )

        # 4. Непрерывный расчет де-факто суверенитета по теории O-Ring Кремера (без хардкода)
        parent_ids = {c.parent_id for c in components if c.parent_id is not None}
        leaves = [c for c in components if c.id not in parent_ids]
        total_leaf_cost = sum(c.unit_cost_rub * c.quantity for c in leaves) or product.total_cost_rub or 1.0

        weighted_safe_sum = 0.0
        for c in leaves:
            cost = c.unit_cost_rub * c.quantity
            status = getattr(c, "analog_status", "") or "NO_ANALOGS"
            analog_w = 1.0 if status == "FULL_COMPATIBLE" else (
                0.7 if status == "REQUIRES_REWORK" else (
                    0.2 if status == "POORLY_COMPATIBLE" else (
                        1.0 if c.country_code in ("RU", "BY") else 0.0
                    )
                )
            )
            safe_factor = (1.0 - float(c.country_risk)) * analog_w
            weighted_safe_sum += (cost / total_leaf_cost) * safe_factor

        raw_defacto_pct = round(weighted_safe_sum * 100.0, 1)

        # Мультипликатор надежности Кремера по критическим точкам
        o_ring_multiplier = 1.0
        for choke in critical_components:
            o_ring_multiplier *= (1.0 - 0.25 * float(choke.cfi_score))

        defacto_localization_pct = round(raw_defacto_pct * o_ring_multiplier, 1) if leaves else 100.0
        vulnerability_gap = max(0.0, round(paper_localization_pct - defacto_localization_pct, 1))

        is_compliant = (
            achieved_points >= rule.min_points_required
            and ad_valorem_pct >= rule.min_ad_valorem_pct
        )

        if critical_components and is_compliant:
            status_decision = "ФОРМАЛЬНО СООТВЕТСТВУЕТ (ВЫСОКИЙ СКРЫТЫЙ РИСК)"
            verdict = (
                f"Изделие успешно набрало {achieved_points} баллов (порог {rule.min_points_required}) "
                f"и имеет официальную адвалорную долю {ad_valorem_pct}%. "
                f"ОДНАКО глубокий аудит выявил разрыв суверенитета в {vulnerability_gap}% и "
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
