from datetime import datetime
import hashlib
import json
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from matryoshka_db.db_models import (
    Product,
    Component,
    PolicyRule,
    CountryRisk,
    Certificate,
    AuditLog,
    AuditActorTypeEnum,
)


class RegulatorRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_product(self, product_id: int) -> Product | None:
        query = select(Product).where(Product.id == product_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_product_with_components(self, product_id: int) -> list[Component]:
        query = (
            select(Component)
            .where(Component.product_id == product_id)
            .options(selectinload(Component.supplier))
            .order_by(Component.tier, Component.id)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_policy_rule(self, industry_code: str = "28.3") -> PolicyRule | None:
        query = select(PolicyRule).where(PolicyRule.industry_code == industry_code)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_country_risks(self) -> dict[str, float]:
        query = select(CountryRisk)
        result = await self.session.execute(query)
        risks = result.scalars().all()
        return {r.country_code: r.risk_factor for r in risks}

    async def save_certificate(self, cert: Certificate) -> Certificate:
        self.session.add(cert)
        await self.session.flush()
        return cert

    async def get_latest_certificate(self, product_id: int) -> Certificate | None:
        query = (
            select(Certificate)
            .where(Certificate.product_id == product_id)
            .order_by(Certificate.id.desc())
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def log_audit_event(
        self,
        event_type: str,
        actor_id: int,
        actor_role: AuditActorTypeEnum,
        resource_type: str,
        resource_id: int,
        details: dict,
    ) -> AuditLog:
        payload = f"{event_type}:{actor_id}:{resource_type}:{resource_id}:{datetime.utcnow().isoformat()}"
        hash_sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        log_entry = AuditLog(
            event_type=event_type,
            actor_id=actor_id,
            actor_role=actor_role,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            hash_sha256=hash_sha256,
        )
        self.session.add(log_entry)
        await self.session.flush()
        return log_entry
