"""Inspect and convert the organizer's CSV/JSONL/JSON catalog.

Usage: python -m helpers.prepare_data path/to/catalog.csv
No prices, cities, profiles, or busy dates are invented.
"""

import argparse
import csv
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path


def read_source(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        if path.suffix.lower() == ".csv":
            sample = source.read(8192)
            source.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            rows = list(csv.DictReader(source, dialect=dialect))
        elif path.suffix.lower() == ".jsonl":
            rows = [json.loads(line) for line in source if line.strip()]
        elif path.suffix.lower() == ".json":
            rows = json.load(source)
        else:
            raise ValueError("Expected CSV, JSONL, or JSON; HTML needs explicit column mapping")
    if not isinstance(rows, list) or not rows or not all(isinstance(x, dict) for x in rows):
        raise ValueError("Source must contain a nonempty list of profile objects")
    print("Source columns:", sorted(set().union(*(row.keys() for row in rows))))
    for field in ("categories", "event_formats", "languages", "busy_dates"):
        print(f"{field} source types:", dict(Counter(type(row.get(field)).__name__ for row in rows)))
    return rows


def build_mock(contractors):
    from .utils import validate_output

    query = dict(city="Алматы", date="2026-11-14", event_format="свадьба",
                 category="Фотограф", budget_kzt=400000, duration_hours=8, language="русский")
    eligible = [c for c in contractors if c["city"] == query["city"]
                and query["category"] in c["categories"]
                and query["event_format"] in c["event_formats"]
                and c["price_from_kzt"] <= query["budget_kzt"]
                and query["language"] in c["languages"]
                and (c["max_hours"] is None or c["max_hours"] >= 8)]
    if not eligible:
        raise ValueError("CONTRACT ISSUE: no real profiles qualify for the requested demo scenario")
    start = date.fromisoformat(query["date"])
    for offset in range(366):
        query["date"] = (start + timedelta(days=offset)).isoformat()
        free = [c for c in eligible if query["date"] not in c["busy_dates"]]
        if free:
            break
    else:
        raise ValueError("No free demo date found in the next year")
    results = []
    for index, c in enumerate(sorted(free, key=lambda c: (c["price_from_kzt"], c["id"]))[:3]):
        card = {k: v for k, v in c.items() if k not in {"anon_name", "categories", "busy_dates"}}
        card.update(name=c["anon_name"], category=query["category"], score=1.0)
        hours = f"до {c['max_hours']} ч" if c["max_hours"] is not None else "лимит часов не указан"
        details = [f"Минимальная цена среди свободных подходящих профилей: {c['price_from_kzt']} ₸; {hours}.",
                   f"Свободен {query['date']}, работает со свадьбами в Алматы; цена от {c['price_from_kzt']} ₸.",
                   f"Русский язык, цена от {c['price_from_kzt']} ₸ в рамках бюджета; {hours}."]
        card["explanation"] = f"{c['anon_name']}: {details[index]}"
        results.append(card)
    mock = dict(status="matched", query=query.copy(), results=results, fallback=True,
                meta=dict(catalog_candidates=sum(c["city"] == query["city"] and query["category"] in c["categories"] for c in contractors),
                          eligible_candidates=len(free), returned=len(results), diagnostics={}))
    assert validate_output(mock)
    return mock


def main():
    from .utils import normalize_contractor, validate_contractor

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    raw = read_source(args.source)
    contractors = []
    errors = []
    for index, row in enumerate(raw, 1):
        try:
            contractors.append(normalize_contractor(row))
        except (ValueError, TypeError) as exc:
            errors.append(f"Row {index}: {exc}")
    print("Total contractors:", len(raw))
    print("Cities:", dict(Counter(c["city"] for c in contractors)))
    print("Categories:", dict(Counter(cat for c in contractors for cat in c["categories"])))
    print("Synthetic:", sum(c["synthetic"] for c in contractors))
    print("Missing prices:", sum(row.get("price_from_kzt") is None or str(row.get("price_from_kzt")).strip().lower() in {"", "nan", "null", "none"} for row in raw))
    print("Missing cities:", sum(not str(row.get("city") or "").strip() for row in raw))
    print("Invalid busy dates:", sum("busy_dates" in error for error in errors))
    print("Invalid records:", len(errors))
    if errors:
        raise ValueError("CONTRACT ISSUE: normalization failed\n" + "\n".join(errors))
    assert len(contractors) == 66, "Expected exactly 66 organizer profiles"
    assert len({c["id"] for c in contractors}) == len(contractors), "Duplicate IDs"
    assert all(validate_contractor(c) for c in contractors)
    target = Path(__file__).resolve().parent
    (target / "contractors.json").write_text(json.dumps(contractors, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DATA READY: helpers/contractors.json (66 profiles)")
    mock = build_mock(contractors)
    (target / "mock_data.json").write_text(json.dumps(mock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("MOCK READY: helpers/mock_data.json")


if __name__ == "__main__":
    main()
