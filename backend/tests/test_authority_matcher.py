"""The routing rules, tested without a database (plain Authority objects)."""

from app.modules.authorities.matcher import match_authorities
from app.modules.authorities.models import Authority


def dept(
    name: str,
    categories: list[str],
    *,
    city: str | None = "Demo City",
    state: str | None = "Demo State",
    country: str = "XX",
    level: str = "CITY",
    email: str | None = "x@dept.example",
    active: bool = True,
) -> Authority:
    return Authority(
        name=name,
        jurisdiction=city or state or country,
        jurisdiction_level=level,
        city=city,
        state=state,
        country=country,
        supported_categories=categories,
        official_email=email,
        is_demo=True,
        active=active,
    )


ROADS = dept("Roads", ["ROAD_POTHOLE"])
WATER = dept("Water Board", ["WATERLOGGING", "OPEN_DRAIN"])
DRAINS = dept("Drains Cell", ["WATERLOGGING", "OPEN_DRAIN"])
STATE_PWD = dept("State PWD", ["ROAD_POTHOLE"], city=None, level="STATE")
OTHER_CITY = dept("Other City Roads", ["ROAD_POTHOLE"], city="Other City")
NATIONAL = dept("National Highways", ["ROAD_POTHOLE"], city=None, state=None, level="NATIONAL")
ALL = [ROADS, WATER, DRAINS, STATE_PWD, OTHER_CITY, NATIONAL]


def run(
    category: str,
    city: str | None = "Demo City",
    state: str | None = "Demo State",
    country: str | None = "XX",
    authorities: list[Authority] = ALL,
):
    return match_authorities(
        authorities,
        category=category,
        city=city,
        state=state,
        country=country,
        category_label=category.replace("_", " ").title(),
    )


def names(result) -> list[str]:
    return [m.authority.name for m in result.matches]


def test_single_city_department_is_exact() -> None:
    result = run("ROAD_POTHOLE")
    assert result.confidence == "EXACT"
    assert names(result) == [
        "Roads",
        "State PWD",
        "National Highways",
    ]  # city, then state, then national
    assert "Covers Demo City" in " ".join(result.matches[0].reasons)


def test_several_equal_departments_need_a_choice() -> None:
    result = run("WATERLOGGING")
    assert result.confidence == "PARTIAL"
    assert set(names(result)) == {"Water Board", "Drains Cell"}
    assert all("Please choose one" in " ".join(m.reasons) for m in result.matches)


def test_only_state_level_match_is_partial() -> None:
    result = run("ROAD_POTHOLE", city="Small Town")
    assert result.confidence == "PARTIAL"
    assert names(result) == ["State PWD", "National Highways"]


def test_nothing_handles_it() -> None:
    result = run("BROKEN_STREETLIGHT")
    assert (result.confidence, result.matches) == ("NONE", [])


def test_other_country_never_matches() -> None:
    assert run("ROAD_POTHOLE", country="IN").confidence == "NONE"


def test_unknown_country_still_matches_by_city() -> None:
    assert run("ROAD_POTHOLE", country=None).confidence == "EXACT"


def test_department_for_another_city_is_excluded() -> None:
    assert "Other City Roads" not in names(run("ROAD_POTHOLE"))


def test_matching_ignores_case_and_spaces() -> None:
    assert run("ROAD_POTHOLE", city="  demo   CITY ", state="demo state").confidence == "EXACT"


def test_inactive_and_escalation_only_offices_are_excluded() -> None:
    inactive = dept("Old Roads Dept", ["ROAD_POTHOLE"], active=False)
    escalation = dept("Commissioner", [])
    result = run("ROAD_POTHOLE", authorities=[inactive, escalation])
    assert result.confidence == "NONE"


def test_department_with_email_wins_a_tie_and_missing_email_is_explained() -> None:
    no_email = dept("Roads (no email)", ["ROAD_POTHOLE"], email=None)
    result = run("ROAD_POTHOLE", authorities=[no_email, ROADS])
    assert names(result) == ["Roads", "Roads (no email)"]
    assert result.confidence == "EXACT"
    assert "No public email" in " ".join(result.matches[1].reasons)
