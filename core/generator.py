"""Dependency-free, deterministic recommendation pipeline.

Inputs follow the prepared-catalog contract; matching is exact and case-sensitive.
Invalid requests raise ValueError (they are not an empty search result).
The MVP uses factual explanations without an external API or credentials.
"""

from copy import deepcopy
from datetime import date
from math import isfinite
from typing import Any


DIAGNOSTIC_KEYS = (
    "busy_on_date", "over_budget", "unsupported_format",
    "unsupported_language", "duration_too_long",
)


def validate_request(request: dict[str, Any]) -> None:
    """Validate required fields without coercing or mutating user input."""
    if not isinstance(request, dict):
        raise ValueError("request must be a dictionary")
    for key in ("city", "date", "event_format", "category"):
        value = request.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
    try:
        parsed = date.fromisoformat(request["date"])
    except ValueError as exc:
        raise ValueError("date must be a valid YYYY-MM-DD date") from exc
    if parsed.isoformat() != request["date"]:
        raise ValueError("date must use YYYY-MM-DD format")
    budget = request.get("budget_kzt")
    if type(budget) is not int or budget <= 0:
        raise ValueError("budget_kzt must be a positive integer")
    duration = request.get("duration_hours")
    if duration is not None and (
        type(duration) not in (int, float)
        or not isfinite(duration) or duration <= 0
    ):
        raise ValueError("duration_hours must be a finite positive number or None")
    language = request.get("language")
    if language is not None and (
        not isinstance(language, str) or not language.strip()
    ):
        raise ValueError("language must be a non-empty string or None")


def get_city_category_pool(contractors: list[dict], request: dict) -> list[dict]:
    return [
        c for c in contractors
        if c["city"] == request["city"] and request["category"] in c["categories"]
    ]


def diagnose_candidate(contractor: dict, request: dict) -> list[str]:
    """Return all failures for a candidate in the city/category pool."""
    duration = request.get("duration_hours")
    language = request.get("language")
    checks = {
        "busy_on_date": request["date"] in contractor["busy_dates"],
        "over_budget": contractor["price_from_kzt"] > request["budget_kzt"],
        "unsupported_format": request["event_format"] not in contractor["event_formats"],
        "unsupported_language": language is not None and language not in contractor["languages"],
        "duration_too_long": duration is not None
        and contractor["max_hours"] is not None
        and contractor["max_hours"] < duration,
    }
    return [key for key, failed in checks.items() if failed]


def filter_candidates(contractors: list[dict], request: dict) -> tuple[list[dict], dict]:
    """Filter the catalog; diagnostics count failures only in the city/category pool."""
    diagnostics = dict.fromkeys(DIAGNOSTIC_KEYS, 0)
    eligible = []
    for contractor in get_city_category_pool(contractors, request):
        reasons = diagnose_candidate(contractor, request)
        for reason in reasons:
            diagnostics[reason] += 1
        if not reasons:
            eligible.append(contractor)
    return eligible, diagnostics


def calculate_score(contractor: dict, request: dict) -> float:
    """Score a previously validated, eligible candidate using MVP weights."""
    budget_fit = 1 - contractor["price_from_kzt"] / request["budget_kzt"]
    language = request.get("language")
    language_fit = float(language is None or language in contractor["languages"])
    duration = request.get("duration_hours")
    maximum = contractor["max_hours"]
    duration_fit = 1.0 if duration is None or maximum is None else min(maximum / duration, 1.5) / 1.5
    return 0.55 * budget_fit + 0.25 * language_fit + 0.20 * duration_fit


def rank_candidates(candidates: list[dict], request: dict) -> list[dict]:
    """Return scored copies; do not round before comparing scores."""
    scored = [dict(c, score=calculate_score(c, request)) for c in candidates]
    return sorted(scored, key=lambda c: (-c["score"], c["price_from_kzt"], c["id"]))


def build_verified_facts(contractor: dict, request: dict) -> dict:
    """Separate verified facts from their presentation; None means not assessed."""
    duration = request.get("duration_hours")
    language = request.get("language")
    return {
        "available_on_date": request["date"] not in contractor["busy_dates"],
        "budget_margin_kzt": request["budget_kzt"] - contractor["price_from_kzt"],
        "event_format_match": request["event_format"] in contractor["event_formats"],
        "language_match": None if language is None else language in contractor["languages"],
        "duration_match": None if duration is None or contractor["max_hours"] is None
        else contractor["max_hours"] >= duration,
        "description": contractor["description"],
    }


def _money(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def build_fallback_explanation(contractor: dict, request: dict) -> str:
    """Two factual sentences for an eligible contractor, with optional constraints."""
    facts = build_verified_facts(contractor, request)
    first = (
        f'По календарю профиля свободен {request["date"]}; '
        f'город — {contractor["city"]}, категория — «{request["category"]}», '
        f'формат — «{request["event_format"]}».'
    )
    details = [
        f'Стоимость от {_money(contractor["price_from_kzt"])} ₸ '
        f'при бюджете {_money(request["budget_kzt"])} ₸ '
        f'(запас к начальной цене — {_money(facts["budget_margin_kzt"])} ₸)'
    ]
    if request.get("language") is not None:
        details.append(f'указан нужный язык — {request["language"]}')
    if request.get("duration_hours") is not None:
        if contractor["max_hours"] is None:
            details.append("почасовой лимит в профиле не указан")
        else:
            details.append(
                f'лимит {contractor["max_hours"]:g} ч покрывает '
                f'запрошенные {request["duration_hours"]:g} ч'
            )
    return first + " " + "; ".join(details) + "."


def generate_explanation(contractor: dict, request: dict) -> str:
    """Offline MVP: API availability cannot affect ranking or explanations."""
    return build_fallback_explanation(contractor, request)


def run_pipeline(request: dict, contractors: list[dict]) -> dict:
    """Return one of the three contracted statuses for a valid request/catalog.

    Optional request fields may be absent. Catalog rows must follow the prepared
    schema, including unique IDs and all provenance flags. No inputs are mutated.
    """
    validate_request(request)
    query = deepcopy(request)
    query.setdefault("duration_hours", None)
    query.setdefault("language", None)
    pool = get_city_category_pool(contractors, query)
    output = {
        "status": "no_category_in_city", "query": query, "results": [],
        "meta": {"catalog_candidates": len(pool), "eligible_candidates": 0,
                 "returned": 0, "diagnostics": {}},
    }
    if not pool:
        return output
    eligible, diagnostics = filter_candidates(pool, query)
    output["meta"]["eligible_candidates"] = len(eligible)
    if not eligible:
        output["status"] = "no_eligible_candidates"
        output["meta"]["diagnostics"] = diagnostics
        return output
    output["status"] = "matched"
    fields = (
        "id", "city", "price_from_kzt", "event_formats", "languages", "max_hours",
        "description", "synthetic", "city_imputed", "price_imputed", "score",
    )
    for contractor in rank_candidates(eligible, query)[:3]:
        result = {key: deepcopy(contractor[key]) for key in fields}
        result.update(name=contractor["anon_name"], category=query["category"],
                      explanation=generate_explanation(contractor, query))
        output["results"].append(result)
    output["meta"]["returned"] = len(output["results"])
    return output
