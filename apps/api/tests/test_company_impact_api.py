from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.db.models.company_impact import CompanyImpactRecord
from app.db.models.event import EventRecord
from app.events.models import MarketEvent
from app.events.persistence import EventPersistenceService
from app.events.types import EventCatalyst, EventType
from app.main import app
from app.news.intelligence.models import ImpactDirection, MarketRelevance


def make_event() -> MarketEvent:
    timestamp = datetime.now(UTC).replace(microsecond=0)

    return MarketEvent(
        event_id=uuid4(),
        event_type=EventType.TRADE_POLICY,
        title="New semiconductor trade restrictions announced",
        summary="New trade restrictions affect the semiconductor industry.",
        catalyst=EventCatalyst.TARIFF,
        market_relevance=MarketRelevance.HIGH,
        impact_direction=ImpactDirection.NEGATIVE,
        affected_entities=("NVIDIA", "Microsoft"),
        affected_sectors=("Technology",),
        source_article_ids=(uuid4(),),
        first_seen_at=timestamp,
        last_seen_at=timestamp,
        confidence=0.84,
    )


async def cleanup(
    db_session,
    event_id: UUID,
) -> None:
    await db_session.execute(
        delete(CompanyImpactRecord).where(
            CompanyImpactRecord.event_id == event_id,
        ),
    )
    await db_session.execute(
        delete(EventRecord).where(
            EventRecord.id == event_id,
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_create_get_and_list_company_impacts(
    db_session,
) -> None:
    event = make_event()

    await EventPersistenceService().persist(
        db_session,
        event,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/company-impacts/from-event/{event.event_id}",
        )

        assert response.status_code == 201

        payload = response.json()

        assert len(payload) == 2
        assert {item["company_name"] for item in payload} == {
            "NVIDIA",
            "Microsoft",
        }

        impact_id = UUID(payload[0]["impact_id"])

        get_response = await client.get(
            f"/company-impacts/{impact_id}",
        )

        assert get_response.status_code == 200
        assert get_response.json()["impact_id"] == str(impact_id)

        list_response = await client.get(
            "/company-impacts",
            params={
                "event_id": str(event.event_id),
                "direction": "negative",
            },
        )

        assert list_response.status_code == 200
        assert len(list_response.json()) == 2

    await cleanup(
        db_session,
        event.event_id,
    )


@pytest.mark.asyncio
async def test_create_company_impacts_is_idempotent(
    db_session,
) -> None:
    event = make_event()

    await EventPersistenceService().persist(
        db_session,
        event,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        first_response = await client.post(
            f"/company-impacts/from-event/{event.event_id}",
        )
        second_response = await client.post(
            f"/company-impacts/from-event/{event.event_id}",
        )

        assert first_response.status_code == 201
        assert second_response.status_code == 201
        assert first_response.json() == second_response.json()

        records = (
            (
                await db_session.execute(
                    select(CompanyImpactRecord).where(
                        CompanyImpactRecord.event_id == event.event_id,
                    ),
                )
            )
            .scalars()
            .all()
        )

        assert len(records) == 2

    await cleanup(
        db_session,
        event.event_id,
    )


@pytest.mark.asyncio
async def test_missing_event_returns_404() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/company-impacts/from-event/{uuid4()}",
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_missing_company_impact_returns_404() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/company-impacts/{uuid4()}",
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reversed_event_time_range_returns_422() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/company-impacts",
            params={
                "start_at": "2027-01-02T00:00:00Z",
                "end_at": "2027-01-01T00:00:00Z",
            },
        )

    assert response.status_code == 422
