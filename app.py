"""Smart Contractor Recommendation Engine - Streamlit UI.

HackAlem AI - Laptop 3 (UI / Demo Assembly).
Demonstrates end-to-end happy path and diagnostics in 3-4 clicks.
"""

from copy import deepcopy
from datetime import date, datetime
from html import escape
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
    initial_sidebar_state="collapsed",
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
    render_html("""
    <style>
    .stApp {
        --market-text: var(--text-color, inherit);
        --market-accent: var(--primary-color, #24755e);
        --market-muted: var(--text-color, inherit);
        --market-border: color-mix(in srgb, currentColor 18%, transparent);
        --market-surface: var(--secondary-background-color, color-mix(in srgb, currentColor 5%, transparent));
        --market-tint: color-mix(in srgb, var(--market-accent) 7%, transparent);
        --market-radius: 16px;
    }
    [data-testid="stMainBlockContainer"] {
        max-width: 1120px;
        padding-top: 5rem;
        padding-bottom: 4rem;
    }
    h1 { letter-spacing: -0.045em; line-height: 1.12 !important; padding-top: .35rem; }
    h2, h3 { letter-spacing: -0.025em; }
    [data-testid="stCaptionContainer"] { color: var(--market-muted); opacity: .78; }
    [data-testid="stButton"] button,
    [data-testid="stFormSubmitButton"] button {
        min-height: 48px;
        border-radius: 12px;
        font-weight: 600;
    }
    [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
        background: var(--market-accent) !important; border-color: var(--market-accent) !important;
        color: #fff !important;
    }
    [data-testid="stMultiSelect"] [data-tag] {
        background: var(--market-surface); color: inherit;
        border: 1px solid var(--market-border); border-radius: 8px;
    }
    [data-testid="stMultiSelect"] [data-tag] span,
    [data-testid="stMultiSelect"] [data-tag] button { color: inherit; }
    button:focus-visible { outline: 3px solid var(--market-accent) !important; outline-offset: 3px; }
    .eyebrow {
        color: var(--market-muted); font-size: .75rem; font-weight: 650;
        letter-spacing: .13em; text-transform: uppercase; margin: 0 0 .75rem;
    }
    .st-key-role_customer, .st-key-role_contractor {
        border: 1px solid var(--market-border) !important;
        border-radius: var(--market-radius) !important;
        padding: 1.1rem 1.25rem !important;
        background: var(--background-color, transparent);
    }
    .st-key-role_customer:has(.role-selected),
    .st-key-role_contractor:has(.role-selected) {
        border-color: var(--market-accent) !important;
        background: var(--market-tint);
    }
    .st-key-role_customer button, .st-key-role_contractor button {
        background: transparent !important; color: var(--text-color, inherit) !important;
        border: 0 !important; justify-content: flex-start; padding: 0;
        min-height: 40px;
    }
    .st-key-role_customer button p, .st-key-role_contractor button p {
        font-size: 1.35rem; font-weight: 650; letter-spacing: -.025em;
    }
    .st-key-role_customer button [data-testid="stMarkdownContainer"],
    .st-key-role_contractor button [data-testid="stMarkdownContainer"] { width: 100%; text-align: left; }
    .role-note { color: var(--market-muted); font-size: .8rem; }
    .role-selected { color: var(--text-color, inherit); font-weight: 650; }
    .st-key-customer_form, [data-testid="stForm"] {
        border: 1px solid var(--market-border) !important;
        border-radius: var(--market-radius) !important;
        padding: 1.5rem !important;
    }
    [data-testid="stForm"] hr { margin: .75rem 0; }
    .section-head { margin: .5rem 0 .5rem; }
    .section-head h3 { font-size: 1.1rem; margin: 0; padding: 0; color: var(--text-color, inherit); }
    .section-head p { color: var(--market-muted); margin: .3rem 0 0; font-size: .9rem; }
    .section-number { color: var(--market-muted); margin-right: .6rem; font-size: .85rem; }
    .contractor-card, .empty-state, .success-state {
        border: 1px solid var(--market-border);
        border-radius: var(--market-radius);
        padding: 1.5rem;
        margin: .3rem 0 1rem;
        background: var(--background-color, transparent);
        color: var(--text-color, inherit);
        box-shadow: 0 4px 20px rgba(0,0,0,.035);
        overflow-wrap: anywhere;
    }
    .card-header-row { display: flex; justify-content: space-between; gap: 1.5rem; align-items: flex-start; }
    .contractor-name { font-size: 1.5rem; font-weight: 650; color: var(--text-color, inherit); margin: 0 0 .3rem; padding: 0; }
    .contractor-sub { font-size: .95rem; color: var(--market-muted); margin: 0; }
    .card-price { font-size: 1.35rem; font-weight: 650; letter-spacing: -.025em; white-space: nowrap; }
    .card-price small { font-size: .85rem; font-weight: 400; color: var(--market-muted); }
    .card-tags { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: 1rem; }
    .badge-tag, .badge-synthetic, .fallback-indicator {
        display: inline-block; background: var(--market-surface); color: var(--text-color, inherit);
        border: 1px solid var(--market-border); border-radius: 8px;
        font-size: .78rem; line-height: 1.4; padding: .3rem .6rem;
    }
    .explanation-box {
        margin-top: 1.2rem; padding: 1rem 1.15rem;
        border-radius: 12px; border-left: 3px solid var(--market-accent);
        background: var(--market-tint); color: var(--text-color, inherit);
    }
    .explanation-label { font-size: .86rem; font-weight: 650; margin-bottom: .45rem; }
    .explanation-text { font-size: .95rem; line-height: 1.65; }
    .diagnostics-box { padding: .2rem 0 1rem; color: var(--text-color, inherit); }
    .diagnostics-title { font-size: .9rem; font-weight: 600; margin-bottom: .65rem; }
    .diagnostics-list { display: flex; flex-wrap: wrap; gap: .6rem; list-style: none; padding: 0; margin: 0; }
    .diagnostics-list li { padding: .65rem .85rem; border: 1px solid var(--market-border); border-radius: 10px; font-size: .9rem; }
    .empty-state { background: var(--market-surface); box-shadow: none; }
    .empty-state h3, .success-state h2 { margin: 0 0 .6rem; padding: 0; }
    .empty-state p, .success-state p { margin: 0; color: var(--market-muted); line-height: 1.6; }
    .success-state { background: var(--market-tint); border-left: 3px solid var(--market-accent); }
    @media (max-width: 800px) {
        [data-testid="stMainBlockContainer"] { padding-top: 4.5rem; }
        .card-header-row { flex-wrap: wrap; gap: .8rem; }
        .contractor-card, .empty-state, .success-state { padding: 1.15rem; }
    }
    </style>
    """)


def render_form_section(number: str, title: str, hint: str = "") -> None:
    render_html(f'<div class="section-head"><h3><span class="section-number">{escape(number)}</span>'
                f'{escape(title)}</h3><p>{escape(hint)}</p></div>')


def render_card(contractor: dict) -> None:
    """Show identity, price and factual explanation before secondary metadata."""
    name = escape(str(contractor.get("name") or contractor.get("anon_name") or "Подрядчик"))
    category = escape(str(contractor.get("category", "")))
    city = escape(str(contractor.get("city", "")))
    price = escape(format_kzt(contractor.get("price_from_kzt", 0)))
    maximum = contractor.get("max_hours")
    hours = f"до {maximum:g} ч" if maximum is not None else "Лимит часов не указан"
    tags = "".join(f'<span class="badge-tag">{escape(str(lang))}</span>'
                   for lang in contractor.get("languages", []))
    tags += f'<span class="badge-tag">{escape(hours)}</span>'
    if contractor.get("synthetic"):
        tags += '<span class="badge-synthetic">Синтетический профиль</span>'
    render_html(f"""
    <article class="contractor-card">
        <div class="card-header-row">
            <div><h3 class="contractor-name">{name}</h3>
                <p class="contractor-sub">{category} · {city}</p></div>
            <div class="card-price"><small>от</small> {price}</div>
        </div>
        <div class="explanation-box">
            <div class="explanation-label">Почему подходит</div>
            <div class="explanation-text">{escape(str(contractor.get('explanation', '')))}</div>
        </div>
        <div class="card-tags">{tags}</div>
    </article>
    """)
    if contractor.get("city_imputed") or contractor.get("price_imputed"):
        with st.expander("О данных профиля", expanded=False):
            if contractor.get("city_imputed"):
                st.caption("Город восстановлен при подготовке каталога.")
            if contractor.get("price_imputed"):
                st.caption("Начальная цена восстановлена при подготовке каталога.")


def render_diagnostics(meta: dict, req: dict) -> None:
    """Present existing diagnostic counts without technical field names."""
    diagnostics = meta.get("diagnostics", {})
    labels = {
        "over_budget": "выше бюджета",
        "busy_on_date": "заняты на выбранную дату",
        "unsupported_format": "не работают с этим форматом",
        "unsupported_language": "не поддерживают нужный язык",
        "duration_too_long": "не подходят по длительности",
    }
    items = "".join(f'<li><strong>{escape(str(diagnostics.get(key, 0)))}</strong> {label}</li>'
                    for key, label in labels.items() if diagnostics.get(key, 0) > 0)
    if items:
        render_html(f'<div class="diagnostics-box"><div class="diagnostics-title">Что не совпало с запросом</div>'
                    f'<ul class="diagnostics-list">{items}</ul></div>')
        st.caption("Один подрядчик может не подойти по нескольким условиям.")


def render_result(result: dict, original_req: dict) -> None:
    """Render the existing statuses and disclose the demo response when used."""
    status = result.get("status")
    if result.get("fallback"):
        st.info("Показываем демо-подборку: сейчас не удалось получить ответ на ваш запрос.")
    if status == "matched":
        candidates = result.get("results", [])
        st.markdown(f"### {format_plural_results(len(candidates))}")
        query = result.get("query") or original_req
        st.caption(f"{query.get('city', '')} · {query.get('date', '')} · "
                   f"{query.get('event_format', '')} · бюджет {format_kzt(query.get('budget_kzt', 0))}")
        if not candidates:
            st.info("Нет подходящих кандидатов для отображения.")
            return
        for contractor in candidates[:3]:
            render_card(contractor)
    elif status == "no_category_in_city":
        city = escape(str(original_req.get("city", "")))
        category = escape(str(original_req.get("category", "")))
        render_html(f'<section class="empty-state"><div class="eyebrow">Пока нет вариантов</div>'
                    f'<h3>В городе {city} пока нет подрядчиков категории «{category}»</h3>'
                    '<p>Выберите другой город или категорию и повторите подбор.</p></section>')
    elif status == "no_eligible_candidates":
        render_html('<section class="empty-state"><div class="eyebrow">Попробуем другие условия</div>'
                    '<h3>Подрядчики есть, но никто не подходит под текущие условия</h3>'
                    '<p>Попробуйте увеличить бюджет, изменить дату или дополнительные параметры.</p></section>')
        render_diagnostics(result.get("meta", {}), original_req)
    else:
        st.error("Не удалось получить рекомендации. Попробуйте повторить подбор.")


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

    st.subheader("Расскажите о событии")
    st.caption("Укажите условия — мы проверим доступность и предложим до 3 подходящих вариантов.")
    with st.container(border=True, key="customer_form"):
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
                "Формат мероприятия",
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
            st.caption("Сравним с начальной стоимостью услуг.")

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
                    "Язык общения",
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
    """Two explicit role choices; callbacks update the existing navigation state."""
    if "current_role" not in st.session_state:
        st.session_state.current_role = "Заказчик"

    def select_role(role: str):
        st.session_state.current_role = role
        st.session_state.role_radio_select = (
            "Заказчик (подбор специалистов)" if role == "Заказчик"
            else "Подрядчик (регистрация профиля)"
        )

    st.subheader("Кто вы?")
    columns = st.columns(2, gap="medium")
    choices = [("Заказчик", "Я заказчик", "Найти подходящих подрядчиков", "customer"),
               ("Подрядчик", "Я подрядчик", "Добавить свой профиль", "contractor")]
    for column, (role, label, hint, key) in zip(columns, choices):
        with column, st.container(border=True, key=f"role_{key}"):
            active = role == st.session_state.current_role
            marker = 'role-note role-selected' if active else 'role-note'
            render_html(f'<div class="{marker}">{"Выбрано" if active else "Выбрать роль"}</div>')
            st.button(label, key=f"choose_{key}", use_container_width=True,
                      on_click=select_role, args=(role,))
            st.caption(hint)
    return st.session_state.current_role


def render_contractor_form(available_categories: list[str]) -> None:
    """Render structured registration form for event professionals."""
    if st.session_state.get("contractor_registered"):
        last = st.session_state.get("last_contractor", {})
        render_html('<section class="success-state"><div class="eyebrow">Готово</div>'
                    '<h2>Профиль создан</h2><p>Профиль уже участвует в подборе заказчиков.</p></section>')
        name = escape(str(last.get("anon_name", "")))
        categories_text = escape(", ".join(last.get("categories", [])))
        city_text = escape(str(last.get("city", "")))
        price = escape(format_kzt(last.get("price_from_kzt", 0)))
        render_html(f"""
        <article class="contractor-card">
            <div class="card-header-row">
                <div><h3 class="contractor-name">{name}</h3>
                    <p class="contractor-sub">{categories_text} · {city_text}</p></div>
                <div class="card-price"><small>от</small> {price}</div>
            </div>
            <div class="explanation-box"><div class="explanation-label">О ваших услугах</div>
                <div class="explanation-text">{escape(str(last.get('description', '')))}</div></div>
        </article>
        """)
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            def switch_to_customer():
                st.session_state.current_role = "Заказчик"
                st.session_state.role_radio_select = "Заказчик (подбор специалистов)"
                st.session_state.contractor_registered = False

            st.button("Перейти к поиску как заказчик", type="primary",
                      use_container_width=True, on_click=switch_to_customer)
        with col_b2:
            if st.button("Добавить ещё один профиль", type="secondary", use_container_width=True):
                st.session_state.contractor_registered = False
                st.rerun()
        return

    st.subheader("Расскажите о своих услугах")
    st.caption("Заполните профиль, чтобы заказчики могли найти вас по условиям мероприятия.")

    with st.form("contractor_registration_form"):
        render_form_section("01", "Основная информация", "Как к вам обращаться и где вы работаете.")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Название компании или имя *", value="Nova Photo",
                                 placeholder="Например: Nova Photo")
        with col2:
            city = st.selectbox("Город *", options=CITIES, index=0)

        st.divider()
        render_form_section("02", "Что вы предлагаете", "Можно выбрать несколько категорий и форматов.")
        default_cat = ["Фотограф"] if "Фотограф" in available_categories else [available_categories[0]]
        categories = st.multiselect("Категории услуг *", options=available_categories, default=default_cat)
        event_formats = st.multiselect("Форматы мероприятий *", options=EVENT_FORMATS, default=["свадьба"])

        st.divider()
        render_form_section("03", "Условия работы", "Эти параметры помогут подобрать подходящие заказы.")
        col3, col4 = st.columns(2)
        with col3:
            price_from_kzt = st.number_input("Цена от (₸) *", min_value=1000, max_value=20000000,
                                             value=180000, step=10000, format="%d",
                                             help="Минимальная стоимость заказа.")
        with col4:
            languages = st.multiselect("Языки общения *", options=["русский", "казахский", "английский"],
                                       default=["русский"])
        no_hour_limit = st.checkbox("Работа не привязана к присутствию на площадке", value=False)
        if not no_hour_limit:
            max_hours = st.number_input("Максимум часов на заказ *", min_value=1, max_value=24, value=8, step=1,
                                        help="Если отмечено отсутствие привязки к площадке, лимит при сохранении не учитывается.")
        else:
            max_hours = None

        st.divider()
        render_form_section("04", "Описание", "Расскажите о специализации, стиле работы и типичных мероприятиях.")
        description = st.text_area("О ваших услугах *", value="Свадебная и репортажная фотография",
                                   placeholder="Какие события вы снимаете, оформляете или проводите?", height=120)
        st.caption("* Обязательные поля. При создании у профиля нет занятых дат — он участвует в подборе на любую дату.")
        submitted = st.form_submit_button("Создать профиль", type="primary", use_container_width=True)

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
    render_html('<div class="eyebrow">Умный подбор подрядчиков</div>')
    st.title("Подрядчики для вашего события")
    st.caption("Найдите подходящих специалистов или расскажите о своих услугах.")

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
        st.markdown("### Сценарии для демо")
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
        st.markdown("### Информация о приложении")
        core_ready = run_pipeline is not None
        st.write(
            f"**Подбор:** {'доступен' if core_ready else 'демо-режим'}"
        )
        st.write(f"**Активная роль:** {role}")
        st.write(f"**Всего подрядчиков в базе:** {len(contractors)}")
        new_count = len(st.session_state.get("feature_contractors", []))
        if new_count > 0:
            st.write(f"**Новых профилей (сессия):** +{new_count}")

        debug_mode = st.toggle("Данные ответа для проверки", value=False)
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
