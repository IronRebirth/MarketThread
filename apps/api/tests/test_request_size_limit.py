from httpx import AsyncClient


async def test_request_body_limit_rejects_oversized_content(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        content=b"x" * (1024 * 1024 + 1),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large."}


async def test_request_body_limit_allows_normal_health_request(
    client: AsyncClient,
) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
