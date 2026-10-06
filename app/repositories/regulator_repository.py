from datetime import datetime
import hashlib
import json
from sqlalchemy import select, update
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

    async def get_all_products(self) -> list[Product]:
        query = select(Product).order_by(Product.id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_product_with_components(self, product_id: int) -> list[Component]:
        query = (
            select(Component)
            .where(Component.product_id == product_id)
            .options(selectinload(Component.supplier), selectinload(Component.analogs))
            .order_by(Component.tier, Component.id)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_all_components(self) -> list[Component]:
        query = (
            select(Component)
            .options(
                selectinload(Component.product),
                selectinload(Component.supplier),
                selectinload(Component.parent),
                selectinload(Component.analogs),
            )
            .order_by(Component.product_id, Component.tier)
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

    async def get_all_countries(self) -> list[CountryRisk]:
        query = select(CountryRisk).order_by(CountryRisk.risk_factor, CountryRisk.country_name)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_country(self, country_code: str) -> CountryRisk | None:
        query = select(CountryRisk).where(CountryRisk.country_code == country_code.upper())
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_country(
        self,
        country_code: str,
        risk_factor: float,
        is_unfriendly: bool | None = None,
        sanctions_regime: str | None = None,
    ) -> CountryRisk:
        country = await self.get_country(country_code)
        if not country:
            country = CountryRisk(
                country_code=country_code.upper(),
                country_name=country_code.upper(),
                risk_factor=risk_factor,
                is_unfriendly=is_unfriendly if is_unfriendly is not None else (risk_factor >= 0.7),
                sanctions_regime=sanctions_regime,
            )
            self.session.add(country)
        else:
            country.risk_factor = risk_factor
            if is_unfriendly is not None:
                country.is_unfriendly = is_unfriendly
            if sanctions_regime is not None:
                country.sanctions_regime = sanctions_regime

        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(country)
        return country

    async def create_country(
        self,
        country_code: str,
        country_name: str,
        risk_factor: float,
        is_unfriendly: bool,
        sanctions_regime: str | None = None,
    ) -> CountryRisk:
        country = CountryRisk(
            country_code=country_code.upper(),
            country_name=country_name,
            risk_factor=risk_factor,
            is_unfriendly=is_unfriendly,
            sanctions_regime=sanctions_regime,
        )
        self.session.add(country)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(country)
        return country

    async def set_product_strategic_status(
        self,
        product_id: int,
        is_strategic: bool,
        strategic_priority: str = "CRITICAL",
        strategic_notes: str | None = None,
    ) -> Product | None:
        product = await self.get_product(product_id)
        if not product:
            return None
        product.is_strategic = is_strategic
        product.strategic_priority = strategic_priority
        if strategic_notes is not None:
            product.strategic_notes = strategic_notes
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def save_certificate(self, cert: Certificate) -> Certificate:
        self.session.add(cert)
        await self.session.flush()
        await self.session.commit()
        return cert

    async def get_latest_certificate(self, product_id: int) -> Certificate | None:
        query = (
            select(Certificate)
            .where(Certificate.product_id == product_id)
            .order_by(Certificate.id.desc())
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def record_audit_log(
        self,
        event_type: str,
        resource_id: int,
        details: dict,
    ) -> AuditLog:
        payload = json.dumps(details, sort_keys=True)
        hash_val = hashlib.sha256(payload.encode()).hexdigest()

        log_entry = AuditLog(
            event_type=event_type,
            actor_id=1,
            actor_role=AuditActorTypeEnum.REGULATOR,
            resource_type="product",
            resource_id=resource_id,
            details=details,
            hash_sha256=hash_val,
        )
        self.session.add(log_entry)
        await self.session.flush()
        await self.session.commit()
        return log_entry
