from app.news.intelligence.entities import (
    extract_entities,
    extract_sectors,
)


def test_extracts_known_company() -> None:
    matches = extract_entities(
        "Apple reports stronger iPhone demand.",
    )

    assert len(matches) == 1
    assert matches[0].name == "Apple"
    assert matches[0].ticker == "AAPL"


def test_extracts_multiple_companies() -> None:
    matches = extract_entities(
        "Microsoft and NVIDIA announce a new AI partnership.",
    )

    assert {match.ticker for match in matches} == {
        "MSFT",
        "NVDA",
    }


def test_does_not_match_unknown_company() -> None:
    matches = extract_entities(
        "A local company reports strong quarterly results.",
    )

    assert matches == ()


def test_extracts_multiple_sectors() -> None:
    matches = extract_sectors(
        "Banks and semiconductor manufacturers benefit from cloud demand.",
    )

    assert {match.name for match in matches} == {
        "Financials",
        "Technology",
    }


def test_extracts_plural_sector_terms() -> None:
    matches = extract_sectors(
        "Banks and insurers face higher interest rates.",
    )

    assert {match.name for match in matches} == {
        "Financials",
    }


def test_extracts_no_sector_for_unrelated_text() -> None:
    matches = extract_sectors(
        "A local cultural exhibition opens this weekend.",
    )

    assert matches == ()
