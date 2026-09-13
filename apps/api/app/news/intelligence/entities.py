import re
from dataclasses import dataclass


@dataclass(frozen=True)
class EntityMatch:
    """Detected company or organization entity."""

    name: str
    ticker: str | None = None


@dataclass(frozen=True)
class SectorMatch:
    """Detected market sector."""

    name: str


ENTITY_PATTERNS: tuple[tuple[str, str | None, tuple[str, ...]], ...] = (
    (
        "Apple",
        "AAPL",
        ("apple", "iphone", "ipad", "macbook"),
    ),
    (
        "Microsoft",
        "MSFT",
        ("microsoft", "windows", "azure"),
    ),
    (
        "NVIDIA",
        "NVDA",
        ("nvidia", "geforce", "cuda"),
    ),
    (
        "Tesla",
        "TSLA",
        ("tesla", "model 3", "model y"),
    ),
    (
        "Alphabet",
        "GOOGL",
        ("alphabet", "google", "youtube"),
    ),
)

SECTOR_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Technology",
        (
            "software",
            "cloud",
            "semiconductor",
            "semiconductors",
            "technology",
            "technologies",
            "chip",
            "chips",
        ),
    ),
    (
        "Financials",
        (
            "bank",
            "banks",
            "banking",
            "insurance",
            "insurers",
            "interest rate",
            "interest rates",
            "lending",
        ),
    ),
    (
        "Energy",
        (
            "oil",
            "gas",
            "energy",
            "crude",
            "opec",
        ),
    ),
    (
        "Healthcare",
        (
            "healthcare",
            "hospital",
            "hospitals",
            "drug",
            "drugs",
            "pharma",
            "pharmaceutical",
            "pharmaceuticals",
            "biotech",
        ),
    ),
    (
        "Consumer",
        (
            "retail",
            "consumer",
            "consumers",
            "ecommerce",
            "e-commerce",
            "shopping",
        ),
    ),
    (
        "Industrials",
        (
            "manufacturing",
            "factory",
            "factories",
            "industrial",
            "industrials",
            "machinery",
        ),
    ),
)


def _contains_term(text: str, term: str) -> bool:
    """Check whether text contains a complete term or phrase."""

    return bool(
        re.search(
            rf"(?<!\w){re.escape(term)}(?!\w)",
            text,
        )
    )


def extract_entities(text: str) -> tuple[EntityMatch, ...]:
    """Extract known company entities from normalized text."""

    normalized_text = text.lower()

    matches: list[EntityMatch] = []

    for name, ticker, patterns in ENTITY_PATTERNS:
        if any(_contains_term(normalized_text, pattern) for pattern in patterns):
            matches.append(
                EntityMatch(
                    name=name,
                    ticker=ticker,
                ),
            )

    return tuple(matches)


def extract_sectors(text: str) -> tuple[SectorMatch, ...]:
    """Extract known market sectors from normalized text."""

    normalized_text = text.lower()

    matches: list[SectorMatch] = []

    for sector, patterns in SECTOR_PATTERNS:
        if any(_contains_term(normalized_text, pattern) for pattern in patterns):
            matches.append(SectorMatch(name=sector))

    return tuple(matches)
