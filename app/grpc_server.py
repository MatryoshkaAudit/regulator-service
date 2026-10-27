import logging

import grpc

from app.database import db_manager
from app.dto.certificate_dto import IssueCertificateRequestDTO
from app.dto.sanctions_dto import SanctionsShockRequestDTO
from app.dto.scenario_dto import AIScenarioRequestDTO
from app.repositories.regulator_repository import RegulatorRepository
from app.services.ai_scenario_service import AIScenarioService
from app.services.certificate_service import CertificateService
from app.services.compliance_service import ComplianceService
from app.services.sanctions_service import SanctionsService
from protos.audit import audit_service_pb2, audit_service_pb2_grpc
from protos.policy import policy_service_pb2, policy_service_pb2_grpc

logger = logging.getLogger(__name__)


class PolicyServiceServicer(policy_service_pb2_grpc.PolicyServiceServicer):
    async def EvaluatePP719(self, request, context):
        async with db_manager.get_session() as session:
            service = ComplianceService(RegulatorRepository(session))
            try:
                res = await service.evaluate_product(request.product_id)
                return policy_service_pb2.EvaluatePP719Response(
                    product_id=res.product_id,
                    is_compliant=res.is_compliant,
                    achieved_points=res.achieved_points,
                    required_points=res.required_points,
                    ad_valorem_pct=res.ad_valorem_pct,
                    required_ad_valorem_pct=res.required_ad_valorem_pct,
                    operation_breakdown=[
                        policy_service_pb2.PointBreakdown(
                            operation_name=o.operation_name,
                            points_awarded=o.points_awarded,
                            verified=o.verified,
                            evidence_doc=o.evidence_doc,
                        )
                        for o in res.operations
                    ],
                    status_decision=res.status_decision,
                    certificate_recommendation=res.verdict_summary,
                )
            except ValueError as e:
                logger.warning("gRPC EvaluatePP719 not found: %s", e)
                context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            except Exception:
                logger.exception("gRPC EvaluatePP719 error for product #%s", request.product_id)
                context.abort(grpc.StatusCode.INTERNAL, "Внутренняя ошибка сервиса при аудите ПП РФ № 719")

    async def SimulateSanctionsShock(self, request, context):
        async with db_manager.get_session() as session:
            service = SanctionsService(RegulatorRepository(session))
            try:
                dto = SanctionsShockRequestDTO(
                    product_id=request.product_id,
                    shock_name="gRPC Sanctions Shock",
                    blocked_countries=list(request.blocked_countries),
                    blocked_categories=list(request.blocked_categories),
                    secondary_sanctions_applied=request.enforce_secondary_sanctions,
                )
                res = await service.simulate_shock(dto)
                return policy_service_pb2.SimulateSanctionsShockResponse(
                    product_id=res.product_id,
                    shock_name=res.scenario_title,
                    production_paralysis_risk_pct=res.paralysis_risk_pct,
                    blocked_components_count=res.blocked_components_count,
                    blocked_value_rub=res.total_blocked_value_rub,
                    blocked_items=[
                        policy_service_pb2.ChokepointItem(
                            component_id=c.component_id,
                            component_name=c.component_name,
                            tier=c.tier,
                            country=c.country,
                            cost_rub=c.cost_rub,
                            cfi_score=c.cfi_score,
                            risk_reason=c.risk_reason,
                            potential_paralysis_scope=c.potential_paralysis_scope,
                        )
                        for c in res.blocked_chokepoints
                    ],
                    estimated_days_until_stockout=res.estimated_days_to_halt,
                    mitigation_roadmap=res.recommended_mitigation,
                )
            except ValueError as e:
                logger.warning("gRPC SimulateSanctionsShock not found: %s", e)
                context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            except Exception:
                logger.exception("gRPC SimulateSanctionsShock error for product #%s", request.product_id)
                context.abort(grpc.StatusCode.INTERNAL, "Внутренняя ошибка сервиса при симуляции санкционного шока")

    async def GenerateGeopoliticalScenario(self, request, context):
        service = AIScenarioService()
        try:
            dto = AIScenarioRequestDTO(
                product_id=request.product_id,
                geopolitical_event=request.event_description,
                target_industry=request.target_industry,
            )
            res = await service.generate_scenario(dto)
            return policy_service_pb2.GenerateGeopoliticalScenarioResponse(
                scenario_id=res.scenario_id,
                scenario_title=res.scenario_title,
                ai_executive_summary=res.executive_verdict,
                dynamic_policy_json=res.model_dump_json(),
                calculated_impact_severity=res.severity_score,
                affected_supply_chains=[f"{c.node_name} ({c.severity})" for c in res.affected_supply_chains],
                recommended_urgent_actions=res.regulatory_remedies,
            )
        except Exception:
            logger.exception("gRPC GenerateGeopoliticalScenario error for event: %s", request.event_description)
            context.abort(grpc.StatusCode.INTERNAL, "Внутренняя ошибка сервиса при ИИ-генерации сценария")


class AuditServiceServicer(audit_service_pb2_grpc.AuditServiceServicer):
    async def IssueCertificate(self, request, context):
        async with db_manager.get_session() as session:
            service = CertificateService(RegulatorRepository(session))
            try:
                dto = IssueCertificateRequestDTO(
                    product_id=request.product_id,
                    certified_by=request.certified_by or "Минпромторг РФ",
                    valid_months=request.valid_months or 12,
                )
                res = await service.issue_certificate(dto)
                return audit_service_pb2.IssueCertificateResponse(
                    is_issued=True,
                    certificate_number=res.reg_number,
                    qr_verification_url=res.qr_verification_url,
                    issued_at=res.issued_at,
                    expires_at=res.expires_at,
                    certified_defacto_loc=res.defacto_localization_pct,
                    certified_points=res.pp719_points,
                    digital_signature_hash=res.digital_signature_hash,
                )
            except Exception:
                logger.exception("gRPC IssueCertificate error for product #%s", request.product_id)
                context.abort(grpc.StatusCode.INTERNAL, "Внутренняя ошибка сервиса при выдаче цифрового заключения")


async def serve_grpc(port: int = 50052) -> grpc.aio.Server:
    server = grpc.aio.server()
    policy_service_pb2_grpc.add_PolicyServiceServicer_to_server(PolicyServiceServicer(), server)
    audit_service_pb2_grpc.add_AuditServiceServicer_to_server(AuditServiceServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    await server.start()
    logger.info(f"gRPC Regulator server запущен на порту {port}")
    return server
