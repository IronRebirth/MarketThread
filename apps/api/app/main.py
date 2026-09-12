from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="MarketThread API",
    version="0.1.0",
    description=(
        "Backend API for the MarketThread financial intelligence platform."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return the basic health status of the API."""
    return {"status": "healthy"}


@app.get("/ready", tags=["system"])
async def readiness() -> dict[str, str]:
    """Return the readiness status of the API."""
    return {"status": "ready"}