from sqlalchemy.exc import SQLAlchemyError
from fastapi.testclient import TestClient

from app.db.session import get_db_session
from app.main import app

client = TestClient(app)


class FakeSession:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def execute(self, _statement: object) -> None:
        if self.error is not None:
            raise self.error


def override_db_session() -> object:
    yield FakeSession()


def override_db_session_with_failure() -> object:
    yield FakeSession(SQLAlchemyError("database unavailable"))


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_readiness_endpoint() -> None:
    app.dependency_overrides[get_db_session] = override_db_session

    try:
        response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_endpoint_returns_service_unavailable_when_database_is_down() -> None:
    app.dependency_overrides[get_db_session] = override_db_session_with_failure

    try:
        response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready."}
