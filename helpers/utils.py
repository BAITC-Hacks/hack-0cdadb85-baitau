"""Frozen data contracts and bounded, dependency-free Core fallback."""

import ast
import copy
import json
import logging
import math
import os
import re
import tempfile
import threading
from datetime import date, datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Any

_DIRECTORY = Path(__file__).resolve().parent
_LOGGER = logging.getLogger(__name__)
# A hung external call must not accumulate an unbounded number of workers.
_CORE_SLOTS = threading.BoundedSemaphore(4)
_FLAGS = ("synthetic", "city_imputed", "price_imputed")
_LISTS = ("categories", "event_formats", "languages", "busy_dates")
_FEATURE_PATH = _DIRECTORY / "contractors_feature.json"
_FEATURE_LOCK = threading.RLock()


def _missing(value):
    return value is None or (isinstance(value, float) and math.isnan(value)) or (
        isinstance(value, str) and value.strip().lower() in {"", "null", "none", "nan"})


def parse_list_field(value) -> list:
    """Parse actual lists, JSON lists, Python literal lists, or a single label."""
    if _missing(value):
        return []
    if isinstance(value, list):
        return list(value)
    if not isinstance(value, str):
        raise ValueError("Expected a list or string")
    value = value.strip()
    if value.startswith(("[", "(", "{")):
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            try:
                parsed = ast.literal_eval(value)
            except (ValueError, SyntaxError) as exc:
                raise ValueError("Malformed list field") from exc
        if not isinstance(parsed, list):
            raise ValueError("List field must decode to a list")
        return parsed
    return [item.strip() for item in value.split("|") if item.strip()]


def parse_bool(value) -> bool:
    if _missing(value):
        return False
    if type(value) is bool:
        return value
    if isinstance(value, (str, int, float)):
        token = str(value).strip().lower()
        if token in {"true", "1", "1.0"}:
            return True
        if token in {"false", "0", "0.0"}:
            return False
    raise ValueError("Invalid boolean")


def _integer(value, field):
    if _missing(value) or isinstance(value, bool):
        raise ValueError(f"{field}: missing or invalid number; no value will be invented")
    if isinstance(value, str):
        value = re.sub(r"\s+", "", value)
        if field in {"price_from_kzt", "budget_kzt"}:
            value = re.sub(r"(?:₸|KZT|тг\.?)$", "", value, flags=re.IGNORECASE)
        if not re.fullmatch(r"\d+(?:\.0+)?", value):
            raise ValueError(f"{field}: expected nonnegative integer")
        value = value.split(".")[0]
    if not isinstance(value, (str, int, float)):
        raise ValueError(f"{field}: invalid number")
    if isinstance(value, float) and (not math.isfinite(value) or not value.is_integer()):
        raise ValueError(f"{field}: expected finite integer")
    value = int(value)
    if value < 0:
        raise ValueError(f"{field}: must be nonnegative")
    return value


def _text(value, field, *, allow_empty=False):
    if _missing(value) and allow_empty:
        return ""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: expected nonempty string")
    return value.strip()


def _date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    value = _text(value, "date")
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError("Expected YYYY-MM-DD or DD.MM.YYYY date")


def normalize_contractor(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Contractor must be a dict")
    result = {field: _text(raw.get(field), field) for field in ("id", "anon_name", "city")}
    result["price_from_kzt"] = _integer(raw.get("price_from_kzt"), "price_from_kzt")
    result["max_hours"] = None if _missing(raw.get("max_hours")) else _integer(raw["max_hours"], "max_hours")
    result["description"] = _text(raw.get("description"), "description", allow_empty=True)
    for field in _LISTS:
        try:
            values = parse_list_field(raw.get(field))
            result[field] = [_date(v) if field == "busy_dates" else _text(v, field) for v in values]
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{field}: {exc}") from exc
    result.update({field: parse_bool(raw.get(field)) for field in _FLAGS})
    if not validate_contractor(result):
        raise ValueError("Invalid normalized contractor")
    return result


def normalize_request(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError("Request must be a dict")
    result = {field: _text(request.get(field), field) for field in ("city", "event_format", "category")}
    result["date"] = _date(request.get("date"))
    result["budget_kzt"] = _integer(request.get("budget_kzt"), "budget_kzt")
    if result["budget_kzt"] == 0:
        raise ValueError("budget_kzt must be positive")
    duration = request.get("duration_hours")
    if _missing(duration):
        result["duration_hours"] = None
    else:
        if isinstance(duration, bool):
            raise ValueError("Invalid duration_hours")
        duration = float(duration)
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("duration_hours must be positive and finite")
        result["duration_hours"] = int(duration) if duration.is_integer() else duration
    result["language"] = None if _missing(request.get("language")) else _text(request["language"], "language")
    return result


def _strings(value):
    return isinstance(value, list) and all(isinstance(x, str) and bool(x.strip()) for x in value)


def _nonnegative_int(value):
    return type(value) is int and value >= 0


def validate_contractor(contractor: dict[str, Any]) -> bool:
    if not isinstance(contractor, dict):
        return False
    if not all(isinstance(contractor.get(k), str) and contractor[k].strip() for k in ("id", "anon_name", "city")):
        return False
    if not all(_strings(contractor.get(k)) for k in _LISTS) or not contractor["categories"]:
        return False
    if not _nonnegative_int(contractor.get("price_from_kzt")):
        return False
    if "max_hours" not in contractor or (contractor["max_hours"] is not None and not _nonnegative_int(contractor["max_hours"])):
        return False
    if not isinstance(contractor.get("description"), str) or not all(type(contractor.get(k)) is bool for k in _FLAGS):
        return False
    try:
        return all(date.fromisoformat(v).isoformat() == v for v in contractor["busy_dates"])
    except (ValueError, TypeError):
        return False


def validate_output(result: dict[str, Any]) -> bool:
    if not isinstance(result, dict):
        return False
    status, cards, meta = result.get("status"), result.get("results"), result.get("meta")
    if status not in ("matched", "no_category_in_city", "no_eligible_candidates"):
        return False
    if not isinstance(result.get("query"), dict) or not isinstance(cards, list) or not isinstance(meta, dict):
        return False
    try:
        query = result["query"]
        if normalize_request(query) != query:
            return False
        json.dumps(result, allow_nan=False)
    except (ValueError, TypeError, OverflowError, RecursionError):
        return False
    if len(cards) > 3 or (status == "matched") != bool(cards):
        return False
    if "fallback" in result and type(result["fallback"]) is not bool:
        return False
    if not all(_nonnegative_int(meta.get(k)) for k in ("catalog_candidates", "eligible_candidates", "returned")):
        return False
    if not isinstance(meta.get("diagnostics"), dict):
        return False
    if not (meta["catalog_candidates"] >= meta["eligible_candidates"] >= meta["returned"] == len(cards)):
        return False
    if status == "no_category_in_city" and meta["catalog_candidates"] != 0:
        return False
    if status != "matched" and meta["eligible_candidates"] != 0:
        return False
    ids = set()
    for card in cards:
        if not isinstance(card, dict):
            return False
        if not all(isinstance(card.get(k), str) and card[k].strip() for k in ("id", "name", "category", "city", "explanation")):
            return False
        if card["id"] in ids:
            return False
        ids.add(card["id"])
        record = dict(card, anon_name=card["name"], categories=[card["category"]], busy_dates=[])
        if not validate_contractor(record):
            return False
        score = card.get("score")
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            return False
    return True


def load_contractors() -> list[dict[str, Any]]:
    """Load and check the full catalog independently of the working directory."""
    with (_DIRECTORY / "contractors.json").open(encoding="utf-8") as source:
        rows = json.load(source)
    if not isinstance(rows, list) or len(rows) != 66:
        raise ValueError("CONTRACT ISSUE: expected 66 contractor records")
    contractors = [normalize_contractor(row) for row in rows]
    if len({c["id"] for c in contractors}) != len(contractors):
        raise ValueError("CONTRACT ISSUE: duplicate contractor IDs")
    return contractors


def _validate_feature_contractor(contractor: dict) -> None:
    """Apply the existing contract and stricter user-submission requirements."""
    if not validate_contractor(contractor):
        raise ValueError("Invalid feature contractor contract")
    identifier = contractor["id"]
    if not re.fullmatch(r"USR-[0-9]{5,}", identifier):
        raise ValueError("Feature ID must use USR-00001 format")
    number = int(identifier[4:])
    if number < 1 or identifier != f"USR-{number:05d}":
        raise ValueError("Invalid feature ID number")
    if contractor["price_from_kzt"] <= 0:
        raise ValueError("price_from_kzt must be positive")
    if not contractor["event_formats"] or not contractor["languages"]:
        raise ValueError("event_formats and languages must not be empty")
    if not contractor["description"].strip():
        raise ValueError("description must not be empty")
    if contractor["max_hours"] is not None and contractor["max_hours"] <= 0:
        raise ValueError("max_hours must be positive or None")


def load_feature_contractors() -> list[dict]:
    """Read user profiles; missing/blank storage is empty, corruption raises ValueError.

    Errors never reset or overwrite the file. UI should display the error message.
    """
    with _FEATURE_LOCK:
        try:
            content = _FEATURE_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        except (OSError, UnicodeError):
            raise ValueError("Cannot read feature contractor storage") from None
        if not content.strip():
            return []
        try:
            rows = json.loads(content)
            if not isinstance(rows, list):
                raise ValueError("Expected list")
            ids = set()
            for row in rows:
                _validate_feature_contractor(row)
                if row["id"] in ids:
                    raise ValueError("Duplicate ID")
                ids.add(row["id"])
                if (row["synthetic"], row["city_imputed"], row["price_imputed"]) != (True, False, False):
                    raise ValueError("Invalid user profile flags")
        except (ValueError, TypeError, RecursionError):
            raise ValueError("Feature contractor storage is invalid; file was not changed") from None
        return rows


def generate_feature_id() -> str:
    """Return max persisted USR number + 1; this does not reserve the ID.

    Concurrent forms can receive the same suggestion; save rejects duplicates.
    """
    rows = load_feature_contractors()
    number = max((int(row["id"][4:]) for row in rows), default=0) + 1
    return f"USR-{number:05d}"


def save_feature_contractor(contractor: dict) -> dict:
    """Validate and append a user profile, atomically replacing feature storage.

    A lock serializes writes within one application process. Original catalog
    and caller inputs are never modified; multiple writer processes are unsupported.
    """
    _validate_feature_contractor(contractor)
    saved = copy.deepcopy(contractor)
    saved.update(synthetic=True, city_imputed=False, price_imputed=False)
    with _FEATURE_LOCK:
        rows = load_feature_contractors()
        if any(row["id"] == saved["id"] for row in rows):
            raise ValueError(f"Duplicate feature contractor ID: {saved['id']}")
        rows.append(saved)
        content = json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=_FEATURE_PATH.parent,
                                             prefix=".contractors_feature-", suffix=".tmp", delete=False) as target:
                temporary = Path(target.name)
                target.write(content)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, _FEATURE_PATH)
        except OSError:
            raise ValueError("Cannot save feature contractor; storage was not replaced") from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return saved


def load_all_contractors() -> list[dict]:
    """Return the original 66 profiles followed by persisted feature profiles."""
    base = load_contractors()
    feature = load_feature_contractors()
    return base + feature


def load_mock_data() -> dict[str, Any]:
    """Load the real demo, or return an explicit empty emergency response."""
    try:
        with (_DIRECTORY / "mock_data.json").open(encoding="utf-8") as source:
            result = json.load(source)
        if not validate_output(result):
            raise ValueError("Invalid mock")
        result["fallback"] = True
        return result
    except (OSError, ValueError, TypeError, RecursionError):
        _LOGGER.warning("[FALLBACK] Demo data missing or invalid")
        return {
            "status": "no_category_in_city",
            "query": normalize_request(dict(city="Алматы", date="2026-11-14", event_format="свадьба", category="Фотограф", budget_kzt=400000)),
            "results": [], "fallback": True,
            "meta": {"catalog_candidates": 0, "eligible_candidates": 0, "returned": 0,
                     "diagnostics": {"fallback_reason": "demo_data_unavailable"}},
        }


def safe_pipeline_call(pipeline_fn, request: dict[str, Any],
                       contractors: list[dict[str, Any]], *, timeout_seconds: float = 15.0) -> dict[str, Any]:
    """Run Core with a time limit; always return a validated UI response.

    A daemon worker limits UI waiting, but cannot cancel underlying network I/O.
    Core should also set its own HTTP timeout. At most four calls run concurrently.
    """
    try:
        query = normalize_request(request)
        if not isinstance(contractors, list) or not all(validate_contractor(c) for c in contractors):
            raise ValueError("Invalid contractor input")
        if isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Invalid timeout")
        # Isolate UI inputs from mutation by a worker that outlives this call.
        call_query, call_contractors = copy.deepcopy(query), copy.deepcopy(contractors)
        if not _CORE_SLOTS.acquire(blocking=False):
            raise RuntimeError("Core worker capacity exhausted")
        output = Queue(maxsize=1)

        def invoke():
            try:
                output.put((True, pipeline_fn(call_query, call_contractors)))
            except BaseException:
                output.put((False, None))
            finally:
                _CORE_SLOTS.release()

        try:
            threading.Thread(target=invoke, daemon=True, name="contractor-core").start()
        except BaseException:
            _CORE_SLOTS.release()
            raise
        ok, result = output.get(timeout=timeout_seconds)
        if not ok or not validate_output(result):
            raise ValueError("Core failed or returned invalid output")
        # Reject a structurally valid response for a different query.
        if result["query"] != query:
            raise ValueError("Core query mismatch")
        return dict(result, fallback=False)
    except Exception as exc:
        # Exception text may contain API credentials; log only its type.
        _LOGGER.warning("[FALLBACK] Core unavailable (%s)", "Timeout" if isinstance(exc, Empty) else type(exc).__name__)
        return load_mock_data()
