"""Smart Contractor Recommendation Engine - Streamlit UI.

HackAlem AI - Laptop 3 (UI / Demo Assembly).
Demonstrates end-to-end happy path and diagnostics in 3-4 clicks.
"""

from copy import deepcopy
from datetime import date, datetime
import json
import os
import sys
from textwrap import dedent
from typing import Any, Optional

import streamlit as st

# Configure page metadata and layout
st.set_page_config(
    page_title="Умный подбор event-подрядчиков",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# -----------------------------------------------------------------------------
# Module Imports & Defensive Fallbacks
# -----------------------------------------------------------------------------
try:
    from helpers.utils import (
        load_contractors as helpers_load_contractors,
        load_all_contractors as helpers_load_all_contractors,
        save_feature_contractor as helpers_save_feature_contractor,
        generate_feature_id as helpers_generate_feature_id,
        safe_pipeline_call as helpers_safe_pipeline_call,
        load_mock_data as helpers_load_mock_data,
    )
except ImportError:
    helpers_load_contractors = None
    helpers_load_all_contractors = None
    helpers_save_feature_contractor = None
    helpers_generate_feature_id = None
    helpers_safe_pipeline_call = None
    helpers_load_mock_data = None

try:
    from core.generator import run_pipeline
except ImportError:
    run_pipeline = None


# -----------------------------------------------------------------------------
# Default Constants (Task Specifications)
# -----------------------------------------------------------------------------
CITIES = ["Алматы", "Астана", "Зарубежье"]

EVENT_FORMATS = [
    "свадьба",
    "той",
    "корпоратив",
    "конференция",
    "юбилей",
    "день рождения",
]

CATEGORIES = [
    "Банкетный зал",
    "Ведущий",
    "Ведущий церемонии",
    "Видеограф",
    "Декоратор",
    "Загородная площадка",
    "Инструменталист",
    "Лайв-бэнд",
    "Национальный ансамбль",
    "Отель",
    "Подарки и сувениры",
    "Ресторан",
    "Танцевальный коллектив",
    "Флорист",
    "Фото и видеобудки",
    "Фотограф",
    "Шоу-программа",
]

# Stable demo scenario used for final presentation:
# Алматы / 2026-11-14 / свадьба / Фотограф / 400000 / 8 ч / русский
DEFAULT_DATE = date(2026, 11, 14)
MIN_DATE = date(2026, 9, 23)
MAX_DATE = date(2026, 12, 31)

# Default Contractors Catalog for standalone testing & fallback
DEFAULT_CONTRACTORS = [
    {
        "id": "HK-101",
        "anon_name": "Сацуки Кусакабэ",
        "city": "Алматы",
        "categories": ["Фотограф"],
        "price_from_kzt": 200000,
        "event_formats": ["свадьба", "той", "юбилей"],
        "languages": ["русский", "казахский"],
        "max_hours": 10,
        "busy_dates": ["2026-11-15", "2026-12-05"],
        "description": "Свадебная и семейная репортажная съемка",
        "synthetic": False,
        "city_imputed": False,
        "price_imputed": False,
    },
    {
        "id": "HK-102",
        "anon_name": "Айдар Беков",
        "city": "Алматы",
        "categories": ["Фотограф"],
        "price_from_kzt": 280000,
        "event_formats": ["свадьба", "корпоратив", "той"],
        "languages": ["русский"],
        "max_hours": 12,
        "busy_dates": ["2026-11-20", "2026-12-12"],
        "description": "Художественная свадебная фотография и love story",
        "synthetic": False,
        "city_imputed": False,
        "price_imputed": False,
    },
    {
        "id": "HK-103",
        "anon_name": "Данияр Сабитов",
        "city": "Алматы",
        "categories": ["Фотограф"],
        "price_from_kzt": 350000,
        "event_formats": ["свадьба", "той", "день рождения", "юбилей"],
        "languages": ["русский", "казахский", "английский"],
        "max_hours": 8,
        "busy_dates": ["2026-11-18"],
        "description": "Премиальная свадебная съемка с ассистентом",
        "synthetic": True,
        "city_imputed": False,
        "price_imputed": False,
    },
    {
        "id": "HK-104",
        "anon_name": "Алишер Омаров",
        "city": "Алматы",
        "categories": ["Фотограф"],
        "price_from_kzt": 220000,
        "event_formats": ["свадьба", "корпоратив"],
        "languages": ["русский", "казахский"],
        "max_hours": 9,
        "busy_dates": ["2026-11-14", "2026-11-25"],  # Busy on 14.11, free on 15.11
        "description": "Динамичные кадры и быстрая цветокоррекция",
        "synthetic": False,
        "city_imputed": False,
        "price_imputed": False,
    },
    {
        "id": "HK-105",
        "anon_name": "Елена Ким",
        "city": "Алматы",
        "categories": ["Фотограф"],
        "price_from_kzt": 450000,  # Over 400 000 KZT budget
        "event_formats": ["свадьба", "конференция"],
        "languages": ["русский", "английский"],
        "max_hours": 10,
        "busy_dates": [],
        "description": "Авторская фотография с журнальной ретушью",
        "synthetic": False,
        "city_imputed": False,
        "price_imputed": False,
    },
    {
        "id": "HK-106",
        "anon_name": "Нурлан Сериков",
        "city": "Алматы",
        "categories": ["Фотограф"],
        "price_from_kzt": 320000,
        "event_formats": ["корпоратив", "конференция"],  # No wedding
        "languages": ["русский"],
        "max_hours": 6,
        "busy_dates": [],
        "description": "Репортажи масштабных событий",
        "synthetic": False,
        "city_imputed": False,
        "price_imputed": False,
    },
    {
        "id": "HK-107",
        "anon_name": "Арман Искаков",
        "city": "Алматы",
        "categories": ["Ведущий"],
        "price_from_kzt": 300000,
        "event_formats": ["свадьба", "той", "корпоратив"],
        "languages": ["русский", "казахский"],
        "max_hours": 7,
        "busy_dates": ["2026-11-14"],
        "description": "Интеллигентный конферанс и современная программа",
        "synthetic": False,
        "city_imputed": False,
        "price_imputed": False,
    },
    {
        "id": "HK-108",
        "anon_name": "Flora & Decor Studio",
        "city": "Алматы",
        "categories": ["Декоратор"],
        "price_from_kzt": 250000,
        "event_formats": ["свадьба", "той", "юбилей"],
        "languages": ["русский", "казахский"],
        "max_hours": None,
        "busy_dates": [],
        "description": "Оформление президиума и фотозон живыми цветами",
        "synthetic": False,
        "city_imputed": False,
        "price_imputed": False,
    },
    {
        "id": "HK-109",
        "anon_name": "Almaty Soul Band",
        "city": "Алматы",
        "categories": ["Лайв-бэнд"],
        "price_from_kzt": 380000,
        "event_formats": ["свадьба", "корпоратив", "той"],
        "languages": ["русский", "казахский", "английский"],
        "max_hours": 4,
        "busy_dates": [],
        "description": "Живой звук, каверы мировых и казахстанских хитов",
        "synthetic": False,
        "city_imputed": False,
        "price_imputed": False,
    },
    {
        "id": "HK-110",
        "anon_name": "Астана Фото Про",
        "city": "Астана",
        "categories": ["Фотограф"],
        "price_from_kzt": 250000,
        "event_formats": ["свадьба", "той", "корпоратив"],
        "languages": ["русский", "казахский"],
        "max_hours": 10,
        "busy_dates": [],
        "description": "Свадебная съемка в столице",
        "synthetic": False,
        "city_imputed": False,
        "price_imputed": False,
    },
]


# -----------------------------------------------------------------------------
# Data Loader and Pipeline Wrapper
# -----------------------------------------------------------------------------
def load_contractors() -> list[dict]:
    """Load contractors catalog from Laptop 2 helpers, local files, or defaults."""
    if helpers_load_contractors is not None:
        try:
            data = helpers_load_contractors()
            if data and isinstance(data, list):
                return data
        except Exception:
            pass

    for rel_path in ("helpers/contractors.json", "data/contractors.json"):
        full_path = os.path.join(PROJECT_ROOT, rel_path)
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                pass

    return DEFAULT_CONTRACTORS


def generate_feature_id() -> str:
    """Generate unique ID adhering to dataset conventions."""
    if helpers_generate_feature_id is not None:
        try:
            return helpers_generate_feature_id()
        except Exception:
            pass
    import random
    return f"USR-{random.randint(1, 99999):05d}"


def save_feature_contractor(contractor: dict) -> dict:
    """Save contractor via helpers API if present, otherwise into session_state."""
    if helpers_save_feature_contractor is not None:
        return helpers_save_feature_contractor(contractor)

    if "feature_contractors" not in st.session_state:
        st.session_state.feature_contractors = []
    st.session_state.feature_contractors.insert(0, contractor)
    return contractor


def load_all_contractors() -> list[dict]:
    """Load all contractors: base catalog + newly created feature contractors."""
    if helpers_load_all_contractors is not None:
        try:
            data = helpers_load_all_contractors()
            if data and isinstance(data, list):
                return data
        except Exception:
            pass

    base = load_contractors()
    feature = st.session_state.get("feature_contractors", [])
    seen_ids = set()
    combined = []
    for c in feature + base:
        if c.get("id") not in seen_ids:
            seen_ids.add(c.get("id"))
            combined.append(c)
    return combined


def load_mock_data(req: Optional[dict] = None) -> dict:
    """Load mock output contract from helpers or embedded dataset."""
    if helpers_load_mock_data is not None:
        try:
            return helpers_load_mock_data()
        except Exception:
            pass

    mock_json_path = os.path.join(PROJECT_ROOT, "helpers", "mock_data.json")
    if os.path.exists(mock_json_path):
        try:
            with open(mock_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Built-in fallback mock matching the exact contract
    effective_req = req or {
        "city": "Алматы",
        "date": "2026-11-14",
        "event_format": "свадьба",
        "category": "Фотограф",
        "budget_kzt": 400000,
        "duration_hours": 8,
        "language": "русский",
    }
    return {
        "status": "matched",
        "fallback": True,
        "query": effective_req,
        "results": [
            {
                "id": "HK-101",
                "name": "Сацуки Кусакабэ",
                "category": effective_req.get("category", "Фотограф"),
                "city": effective_req.get("city", "Алматы"),
                "price_from_kzt": 200000,
                "event_formats": ["свадьба", "той"],
                "languages": ["русский", "казахский"],
                "max_hours": 10,
                "description": "Свадебная и семейная репортажная съемка",
                "synthetic": False,
                "city_imputed": False,
                "price_imputed": False,
                "score": 0.85,
                "explanation": (
                    f"По календарю профиля свободен {effective_req['date']}; "
                    f"город — {effective_req['city']}, категория — «{effective_req['category']}», "
                    f"формат — «{effective_req['event_format']}». "
                    f"Стоимость от 200 000 ₸ при бюджете 400 000 ₸ (запас к начальной цене — 200 000 ₸); "
                    f"указан нужный язык — русский; лимит 10 ч покрывает запрошенные 8 ч."
                ),
            },
            {
                "id": "HK-102",
                "name": "Айдар Беков",
                "category": effective_req.get("category", "Фотограф"),
                "city": effective_req.get("city", "Алматы"),
                "price_from_kzt": 280000,
                "event_formats": ["свадьба", "корпоратив", "той"],
                "languages": ["русский"],
                "max_hours": 12,
                "description": "Художественная свадебная фотография и love story",
                "synthetic": False,
                "city_imputed": False,
                "price_imputed": False,
                "score": 0.74,
                "explanation": (
                    f"По календарю профиля свободен {effective_req['date']}; "
                    f"город — {effective_req['city']}, категория — «{effective_req['category']}», "
                    f"формат — «{effective_req['event_format']}». "
                    f"Стоимость от 280 000 ₸ при бюджете 400 000 ₸ (запас к начальной цене — 120 000 ₸); "
                    f"указан нужный язык — русский; лимит 12 ч покрывает запрошенные 8 ч."
                ),
            },
            {
                "id": "HK-103",
                "name": "Данияр Сабитов",
                "category": effective_req.get("category", "Фотограф"),
                "city": effective_req.get("city", "Алматы"),
                "price_from_kzt": 350000,
                "event_formats": ["свадьба", "той", "день рождения", "юбилей"],
                "languages": ["русский", "казахский", "английский"],
                "max_hours": 8,
                "description": "Премиальная свадебная съемка с ассистентом",
                "synthetic": True,
                "city_imputed": False,
                "price_imputed": False,
                "score": 0.65,
                "explanation": (
                    f"По календарю профиля свободен {effective_req['date']}; "
                    f"город — {effective_req['city']}, категория — «{effective_req['category']}», "
                    f"формат — «{effective_req['event_format']}». "
                    f"Стоимость от 350 000 ₸ при бюджете 400 000 ₸ (запас к начальной цене — 50 000 ₸); "
                    f"указан нужный язык — русский; лимит 8 ч покрывает запрошенные 8 ч."
                ),
            },
        ],
        "meta": {
            "catalog_candidates": 3,
            "eligible_candidates": 3,
            "returned": 3,
            "diagnostics": {},
        },
    }


def safe_pipeline_call(pipeline_func, request_dict: dict, catalog: list[dict]) -> dict:
    """Defensive wrapper preventing any UI crashes from pipeline or backend failures."""
    if helpers_safe_pipeline_call is not None:
        try:
            return helpers_safe_pipeline_call(pipeline_func, request_dict, catalog)
        except Exception as exc:
            pass

    if pipeline_func is None:
        return load_mock_data(request_dict)

    try:
        return pipeline_func(request_dict, catalog)
    except Exception as exc:
        fallback_res = load_mock_data(request_dict)
        fallback_res["fallback"] = True
        fallback_res.setdefault("meta", {})["error"] = str(exc)
        return fallback_res


# -----------------------------------------------------------------------------
# Formatting Helpers
# -----------------------------------------------------------------------------
def format_kzt(amount: int) -> str:
    """Format integer into readable Kazakhstani Tenge string."""
    try:
        return f"{amount:,}".replace(",", " ") + " ₸"
    except Exception:
        return f"{amount} ₸"


def format_plural_results(count: int) -> str:
    """Russian pluralization for matched results."""
    if count == 1:
        return f"Найден **1** подходящий вариант"
    elif count in (2, 3, 4):
        return f"Найдено **{count}** подходящих варианта"
    else:
        return f"Найдено **{count}** подходящих вариантов"


def render_html(html_str: str) -> None:
    """Render HTML safely without triggering Markdown indentation code-blocks."""
    clean_html = dedent(html_str).strip()
    if hasattr(st, "html"):
        st.html(clean_html)
    else:
        st.markdown(clean_html, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# UI CSS Styling
# -----------------------------------------------------------------------------
def inject_custom_styles():
    styles = """
    <style>
    /* Card Container - Adaptive for Light and Dark themes */
    .contractor-card {
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        background-color: var(--secondary-background-color, #ffffff);
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
        transition: all 0.2s ease;
    }
    .contractor-card:hover {
        box-shadow: 0 6px 14px rgba(0, 0, 0, 0.08);
        border-color: rgba(59, 130, 246, 0.4);
    }

    /* Card Header */
    .card-header-row {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 8px;
    }
    .contractor-name {
        font-size: 1.35rem;
        font-weight: 700;
        color: var(--text-color, #0f172a);
        margin: 0;
    }
    .contractor-sub {
        font-size: 0.95rem;
        color: var(--text-color, #64748b);
        opacity: 0.8;
        margin-bottom: 12px;
    }

    /* Badges */
    .badge-synthetic {
        display: inline-block;
        background: rgba(139, 92, 246, 0.15);
        color: #8b5cf6;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 6px;
        letter-spacing: 0.02em;
        border: 1px solid rgba(139, 92, 246, 0.3);
    }
    .badge-tag {
        display: inline-block;
        background: rgba(148, 163, 184, 0.18);
        color: var(--text-color, #475569);
        font-size: 0.85rem;
        padding: 3px 10px;
        border-radius: 6px;
        margin-right: 6px;
        margin-bottom: 6px;
    }
    .badge-price {
        display: inline-block;
        background: rgba(16, 185, 129, 0.15);
        color: #10b981;
        font-weight: 700;
        font-size: 1rem;
        padding: 4px 10px;
        border-radius: 6px;
        border: 1px solid rgba(16, 185, 129, 0.3);
        margin-bottom: 12px;
    }

    /* Primary Explanation Block (The Hero of the Card) */
    .explanation-box {
        background-color: rgba(59, 130, 246, 0.08);
        border-left: 4px solid #3b82f6;
        border-radius: 0 8px 8px 0;
        padding: 14px 16px;
        margin-top: 14px;
        margin-bottom: 10px;
    }
    .explanation-label {
        font-size: 0.8rem;
        font-weight: 800;
        color: #3b82f6;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .explanation-text {
        font-size: 0.95rem;
        line-height: 1.5;
        color: var(--text-color, #1e293b);
    }

    /* Diagnostics List */
    .diagnostics-box {
        background-color: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-radius: 10px;
        padding: 16px 20px;
        margin-top: 16px;
    }
    .diagnostics-title {
        font-weight: 700;
        color: #d97706;
        font-size: 1.05rem;
        margin-bottom: 8px;
    }
    .diagnostics-list {
        margin: 0;
        padding-left: 20px;
        color: var(--text-color, #78350f);
        font-size: 0.95rem;
        line-height: 1.6;
    }

    /* Fallback demo mode badge */
    .fallback-indicator {
        display: inline-block;
        background: rgba(245, 158, 11, 0.15);
        color: #d97706;
        font-size: 0.75rem;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
        margin-left: 8px;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    </style>
    """
    render_html(styles)


# -----------------------------------------------------------------------------
# Result Rendering Functions
# -----------------------------------------------------------------------------
def render_card(contractor: dict) -> None:
    """Render single contractor card focusing prominently on the explanation."""
    name = contractor.get("name") or contractor.get("anon_name") or "Подрядчик"
    category = contractor.get("category", "")
    city = contractor.get("city", "")
    price_from = contractor.get("price_from_kzt", 0)
    languages = contractor.get("languages", [])
    max_hours = contractor.get("max_hours")
    explanation = contractor.get("explanation", "")
    synthetic = contractor.get("synthetic", False)
    city_imputed = contractor.get("city_imputed", False)
    price_imputed = contractor.get("price_imputed", False)

    # Format tags
    lang_str = ", ".join(languages) if languages else "любой"
    hours_str = f"до {max_hours:g} часов" if max_hours else "без лимита по часам"

    synthetic_badge_html = (
        '<span class="badge-synthetic">🤖 Синтетический профиль</span>'
        if synthetic
        else ""
    )

    card_html = dedent(f"""
    <div class="contractor-card">
        <div class="card-header-row">
            <div>
                <h3 class="contractor-name">{name}</h3>
                <div class="contractor-sub">{category} · {city}</div>
            </div>
            <div>
                {synthetic_badge_html}
            </div>
        </div>
        <div>
            <span class="badge-price">от {format_kzt(price_from)}</span>
        </div>
        <div>
            <span class="badge-tag">🗣️ {lang_str}</span>
            <span class="badge-tag">⏱️ {hours_str}</span>
        </div>
        <div class="explanation-box">
            <div class="explanation-label">ПОЧЕМУ ЭТОТ ПОДРЯДЧИК ПОДХОДИТ</div>
            <div class="explanation-text">{explanation}</div>
        </div>
    </div>
    """).strip()
    render_html(card_html)

    # Secondary metadata in collapsed expander
    if city_imputed or price_imputed:
        with st.expander("Подробнее о данных профиля", expanded=False):
            if city_imputed:
                st.caption("ℹ️ Город подрядчика был восстановлен или уточнен.")
            if price_imputed:
                st.caption("ℹ️ Базовая стоимость была рассчитана на основе медианы категории.")


def render_diagnostics(meta: dict, req: dict) -> None:
    """Render failure state diagnostics without showing 0-count items."""
    diagnostics = meta.get("diagnostics", {})
    date_str = req.get("date", "выбранную дату")
    budget_str = format_kzt(req.get("budget_kzt", 0))
    format_str = req.get("event_format", "")
    language_str = req.get("language")
    duration = req.get("duration_hours")

    bullet_points = []

    busy = diagnostics.get("busy_on_date", 0)
    if busy > 0:
        bullet_points.append(f"**{busy}** заняты на дату {date_str}")

    over = diagnostics.get("over_budget", 0)
    if over > 0:
        bullet_points.append(f"**{over}** начинаются выше вашего бюджета ({budget_str})")

    unsupported_fmt = diagnostics.get("unsupported_format", 0)
    if unsupported_fmt > 0:
        bullet_points.append(f"**{unsupported_fmt}** не работают с форматом «{format_str}»")

    unsupported_lang = diagnostics.get("unsupported_language", 0)
    if unsupported_lang > 0 and language_str:
        bullet_points.append(f"**{unsupported_lang}** не поддерживают язык «{language_str}»")

    duration_long = diagnostics.get("duration_too_long", 0)
    if duration_long > 0 and duration:
        bullet_points.append(
            f"**{duration_long}** имеют лимит длительности меньше запрошенных {duration:g} ч"
        )

    # Render diagnostics box
    list_items = "".join(f"<li>{pt}</li>" for pt in bullet_points)
    diag_html = dedent(f"""
    <div class="diagnostics-box">
        <div class="diagnostics-title">Почему никто не подошел:</div>
        <ul class="diagnostics-list">
            {list_items}
        </ul>
    </div>
    """).strip()
    render_html(diag_html)


def render_result(result: dict, original_req: dict) -> None:
    """Visually differentiate all three contract statuses and render recommendations."""
    status = result.get("status")

    # Matched State
    if status == "matched":
        candidates = result.get("results", [])
        total_returned = len(candidates)

        col_title, col_info = st.columns([3, 1])
        with col_title:
            st.markdown(f"### {format_plural_results(total_returned)}")
        with col_info:
            if result.get("fallback"):
                render_html('<div style="text-align:right;"><span class="fallback-indicator">Демо-режим</span></div>')

        if not candidates:
            st.info("Нет подходящих кандидатов для отображения.")
            return

        # Render up to 3 cards
        for contractor in candidates[:3]:
            render_card(contractor)

    # No Category in City State
    elif status == "no_category_in_city":
        city = original_req.get("city", "")
        category = original_req.get("category", "")
        st.warning(f"В городе **{city}** нет подрядчиков категории **«{category}»**.")
        st.info("💡 Рекомендация: выберите другой город или смените категорию.")

    # No Eligible Candidates State
    elif status == "no_eligible_candidates":
        city = original_req.get("city", "")
        category = original_req.get("category", "")
        st.warning(
            f"В городе **{city}** есть подрядчики категории **«{category}»**, "
            "но под условия заказа сейчас никто не подходит."
        )
        meta = result.get("meta", {})
        render_diagnostics(meta, original_req)
        st.info("💡 Рекомендация: попробуйте увеличить бюджет или выбрать другую дату.")

    # Fallback or Unexpected Error
    else:
        st.error(
            "Не удалось получить рекомендации. Попробуйте изменить параметры поиска."
        )


# -----------------------------------------------------------------------------
# Form Builder
# -----------------------------------------------------------------------------
def build_request_form(contractors: list[dict]) -> tuple[dict, bool]:
    """Render search form with 3-column primary grid and collapsed advanced options."""
    # Determine unique categories
    existing_categories = set()
    for c in contractors:
        existing_categories.update(c.get("categories", []))
    available_categories = (
        sorted(list(existing_categories)) if existing_categories else CATEGORIES
    )

    # Determine default category index
    default_cat_idx = (
        available_categories.index("Фотограф")
        if "Фотограф" in available_categories
        else 0
    )

    with st.container():
        # Row 1: City, Date, Event Format
        col1, col2, col3 = st.columns(3)
        with col1:
            city = st.selectbox("Город", options=CITIES, index=0)
        with col2:
            event_date = st.date_input(
                "Дата мероприятия",
                value=DEFAULT_DATE,
                min_value=MIN_DATE,
                max_value=MAX_DATE,
                help="Календарь датасета ограничен диапазоном с 23.09.2026 по 31.12.2026",
            )
        with col3:
            event_format = st.selectbox(
                "Тип мероприятия",
                options=EVENT_FORMATS,
                index=0,
            )

        # Row 2: Category, Budget
        col4, col5 = st.columns([1, 1])
        with col4:
            category = st.selectbox(
                "Категория подрядчика",
                options=available_categories,
                index=default_cat_idx,
            )
        with col5:
            budget_kzt = st.number_input(
                "Бюджет (₸)",
                min_value=10000,
                max_value=20000000,
                value=400000,
                step=50000,
                format="%d",
                help="Укажите максимальный бюджет в тенге",
            )
            st.caption(f"Выбранный бюджет: **{format_kzt(budget_kzt)}**")

        # Row 3: Optional Parameters (Collapsed)
        duration_val = None
        language_val = None
        with st.expander("Дополнительные параметры", expanded=False):
            exp_col1, exp_col2 = st.columns(2)
            with exp_col1:
                use_duration = st.checkbox("Указать длительность (часов)", value=True)
                if use_duration:
                    duration_val = st.slider(
                        "Длительность",
                        min_value=1,
                        max_value=16,
                        value=8,
                        step=1,
                    )
                else:
                    duration_val = None

            with exp_col2:
                selected_lang = st.selectbox(
                    "Язык ведения / общения",
                    options=["Любой", "русский", "казахский", "английский"],
                    index=1,  # Default: русский
                )
                language_val = None if selected_lang == "Любой" else selected_lang

        submitted = st.button(
            "Подобрать подрядчиков",
            type="primary",
            use_container_width=True,
        )

    # Format Date as ISO String YYYY-MM-DD
    date_iso = (
        event_date.strftime("%Y-%m-%d")
        if isinstance(event_date, (date, datetime))
        else str(event_date)
    )

    request_payload = {
        "city": city,
        "date": date_iso,
        "event_format": event_format,
        "category": category,
        "budget_kzt": int(budget_kzt),
        "duration_hours": duration_val,
        "language": language_val,
    }

    return request_payload, submitted


# -----------------------------------------------------------------------------
# Role Selector & Marketplace Flows
# -----------------------------------------------------------------------------
def render_role_selector() -> str:
    """Render toggle between Customer and Contractor roles."""
    if "current_role" not in st.session_state:
        st.session_state.current_role = "Заказчик"

    col_role, _ = st.columns([1, 1])
    with col_role:
        st.write("**Выберите вашу роль на платформе:**")
        role_options = ["Заказчик (подбор специалистов)", "Подрядчик (регистрация профиля)"]
        default_label = (
            role_options[0]
            if st.session_state.current_role == "Заказчик"
            else role_options[1]
        )
        if "role_radio_select" not in st.session_state:
            st.session_state.role_radio_select = default_label

        selected = st.radio(
            "Роль пользователя",
            options=role_options,
            horizontal=True,
            label_visibility="collapsed",
            key="role_radio_select",
        )
        role = "Заказчик" if "Заказчик" in selected else "Подрядчик"
        st.session_state.current_role = role
        return role


def render_contractor_form(available_categories: list[str]) -> None:
    """Render structured registration form for event professionals."""
    if st.session_state.get("contractor_registered"):
        last = st.session_state.get("last_contractor", {})
        st.success(f"✅ Профиль «{last.get('anon_name')}» успешно добавлен!")

        tags_str = ", ".join(last.get("categories", []))
        langs_str = ", ".join(last.get("languages", []))
        price_str = format_kzt(last.get("price_from_kzt", 0))
        hours_str = f"до {last['max_hours']} ч" if last.get("max_hours") else "без привязки ко времени"

        card_html = dedent(f"""
        <div class="contractor-card">
            <div class="card-header-row">
                <div>
                    <h3 class="contractor-name">{last.get('anon_name')}</h3>
                    <div class="contractor-sub">{tags_str} · {last.get('city')}</div>
                </div>
                <div>
                    <span class="badge-synthetic">🤖 Новый профиль</span>
                </div>
            </div>
            <div>
                <span class="badge-price">от {price_str}</span>
            </div>
            <div>
                <span class="badge-tag">🗣️ {langs_str}</span>
                <span class="badge-tag">⏱️ {hours_str}</span>
                <span class="badge-tag">🆔 {last.get('id')}</span>
            </div>
            <div style="margin-top: 10px; font-size: 0.95rem; color: var(--text-color, #1e293b);">
                {last.get('description')}
            </div>
        </div>
        """).strip()
        render_html(card_html)

        col_b1, col_b2 = st.columns([1, 1])
        with col_b1:
            def switch_to_customer():
                st.session_state.current_role = "Заказчик"
                st.session_state.role_radio_select = "Заказчик (подбор специалистов)"
                st.session_state.contractor_registered = False

            st.button("🔍 Перейти к подбору как заказчик", type="primary",
                      use_container_width=True, on_click=switch_to_customer)
        with col_b2:
            if st.button("➕ Добавить ещё одного подрядчика", type="secondary", use_container_width=True):
                st.session_state.contractor_registered = False
                st.rerun()
        return

    st.subheader("Регистрация профиля подрядчика")
    st.caption("Укажите данные о ваших услугах, чтобы участвовать в AI-подборе для заказчиков")

    with st.form("contractor_registration_form"):
        name = st.text_input(
            "Название компании / Имя мастера*",
            value="Nova Photo",
            placeholder="Например: Nova Photo",
        )

        col1, col2 = st.columns(2)
        with col1:
            city = st.selectbox("Город базирования*", options=CITIES, index=0)
        with col2:
            price_from_kzt = st.number_input(
                "Стоимость услуг от (₸)*",
                min_value=1000,
                max_value=20000000,
                value=180000,
                step=10000,
                format="%d",
            )
            st.caption(f"Будет показано как: **{format_kzt(price_from_kzt)}**")

        default_cat = ["Фотограф"] if "Фотограф" in available_categories else [available_categories[0]]
        categories = st.multiselect(
            "Категории услуг*",
            options=available_categories,
            default=default_cat,
        )

        col3, col4 = st.columns(2)
        with col3:
            event_formats = st.multiselect(
                "Форматы мероприятий*",
                options=EVENT_FORMATS,
                default=["свадьба"],
            )
        with col4:
            languages = st.multiselect(
                "Языки ведения / общения*",
                options=["русский", "казахский", "английский"],
                default=["русский"],
            )

        no_hour_limit = st.checkbox("Работа не привязана к присутствию на площадке", value=False)
        if not no_hour_limit:
            max_hours = st.number_input(
                "Максимум часов на заказ (длительность)*",
                min_value=1,
                max_value=24,
                value=8,
                step=1,
            )
        else:
            max_hours = None

        description = st.text_area(
            "Описание услуг и специализации*",
            value="Свадебная и репортажная фотография",
            placeholder="Опишите опыт, стиль и ключевые преимущества...",
        )

        st.info("ℹ️ Календарь занятости можно будет настроить позже. При создании профиль считается доступным на все даты.")

        submitted = st.form_submit_button("Зарегистрировать подрядчика", type="primary", use_container_width=True)

    if submitted:
        # Strict validation UX
        errors = []
        if not name or not name.strip():
            errors.append("Укажите название или имя подрядчика.")
        if not city:
            errors.append("Выберите город.")
        if not categories:
            errors.append("Выберите хотя бы одну категорию услуг.")
        if price_from_kzt <= 0:
            errors.append("Стоимость услуг должна быть больше нуля.")
        if not event_formats:
            errors.append("Выберите хотя бы один формат мероприятий.")
        if not languages:
            errors.append("Выберите хотя бы один рабочий язык.")
        if not description or not description.strip():
            errors.append("Укажите описание услуг.")
        if not no_hour_limit and (max_hours is None or max_hours < 1):
            errors.append("Укажите корректный лимит часов или отметьте отсутствие привязки к площадке.")

        if errors:
            for err in errors:
                st.error(f"⚠️ {err}")
            return

        new_contractor = {
            "id": generate_feature_id(),
            "anon_name": name.strip(),
            "categories": list(categories),
            "city": city,
            "price_from_kzt": int(price_from_kzt),
            "event_formats": list(event_formats),
            "languages": list(languages),
            "max_hours": int(max_hours) if max_hours is not None else None,
            "busy_dates": [],
            "description": description.strip(),
            "synthetic": True,
            "city_imputed": False,
            "price_imputed": False,
        }

        try:
            saved_profile = save_feature_contractor(new_contractor)
            st.session_state.contractor_registered = True
            st.session_state.last_contractor = saved_profile
            st.rerun()
        except Exception as exc:
            st.error(f"⚠️ Ошибка при сохранении профиля: {exc}")
            return


def render_contractor_flow(available_categories: list[str]) -> None:
    """Render contractor flow screen."""
    render_contractor_form(available_categories)


def render_customer_flow(contractors: list[dict]) -> None:
    """Render customer flow screen: structured search and recommendation display."""
    request_data, submitted = build_request_form(contractors)

    if submitted:
        with st.spinner("Проверяем доступность и подбираем варианты..."):
            result = safe_pipeline_call(run_pipeline, request_data, contractors)
            st.session_state.result = result
            st.session_state.last_request = request_data

    if st.session_state.result is not None:
        st.divider()
        render_result(st.session_state.result, st.session_state.last_request)


# -----------------------------------------------------------------------------
# Main Application Entrypoint
# -----------------------------------------------------------------------------
def main():
    inject_custom_styles()

    # Session State Initialization
    if "result" not in st.session_state:
        st.session_state.result = None
    if "last_request" not in st.session_state:
        st.session_state.last_request = None
    if "feature_contractors" not in st.session_state:
        st.session_state.feature_contractors = []
    if "current_role" not in st.session_state:
        st.session_state.current_role = "Заказчик"
    if "contractor_registered" not in st.session_state:
        st.session_state.contractor_registered = False

    # Always reload combined catalog for instant live refresh without restart
    contractors = load_all_contractors()

    # Header
    st.title("Умный подбор event-подрядчиков")
    st.caption("Двухсторонняя платформа: умный подбор для клиентов и регистрация исполнителей")

    # Role Selector
    role = render_role_selector()
    st.divider()

    # Dynamic categories from catalog
    existing_categories = set()
    for c in contractors:
        existing_categories.update(c.get("categories", []))
    available_categories = (
        sorted(list(existing_categories)) if existing_categories else CATEGORIES
    )

    # Sidebar: Demo scenarios guide & debug info
    with st.sidebar:
        st.markdown("### 🎯 Сценарии для жюри")
        st.markdown(
            """
            **1. Happy Path (Заказчик):**
            - Алматы, 14 ноября, Свадьба, Фотограф, 400 000 ₸.
            - Нажмите «Подобрать».
            - Результат: 3 карточки с обоснованиями.

            **2. WOW-эффект (проверка занятости):**
            - Измените только дату на **15 ноября** или **18 ноября**.
            - Нажмите «Подобрать».
            - Выдача меняется из-за занятости конкретных мастеров!

            **3. Marketplace Flow (Новый подрядчик):**
            - Перейдите в режим **«Подрядчик»**.
            - Создайте: **Nova Photo**, Алматы, Фотограф, 180 000 ₸, свадьба, 8 ч.
            - Переключитесь в **«Заказчик»**.
            - Запрос на бюджет 200 000 ₸ — Nova Photo сразу в выдаче!

            **4. Диагностика отказа:**
            - Установите бюджет **50 000 ₸**.
            - Система покажет точные причины, почему никто не подошел.
            """
        )
        st.markdown("---")
        st.markdown("### ⚙️ Статус системы")
        core_ready = run_pipeline is not None
        st.write(
            f"**Core Engine:** {'🟢 Подключен' if core_ready else '🟡 Режим Mock'}"
        )
        st.write(f"**Активная роль:** {role}")
        st.write(f"**Всего подрядчиков в базе:** {len(contractors)}")
        new_count = len(st.session_state.get("feature_contractors", []))
        if new_count > 0:
            st.write(f"**Новых профилей (сессия):** +{new_count}")

        debug_mode = st.toggle("Режим отладки (Debug)", value=False)
        if debug_mode and st.session_state.result is not None:
            st.markdown("#### Сырой ответ (JSON):")
            st.json(st.session_state.result)

    # Flow Routing
    if role == "Заказчик":
        render_customer_flow(contractors)
    else:
        render_contractor_flow(available_categories)


if __name__ == "__main__":
    main()
