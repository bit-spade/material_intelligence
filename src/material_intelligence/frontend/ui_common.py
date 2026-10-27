import csv
import html
import io
from datetime import datetime

import streamlit as st

from material_intelligence.api.chat import ask_llm
from material_intelligence.api.utils import load_questionnaire
from material_intelligence.engine.calculator import (
    calculate_score_and_level,
    get_product_config,
)


# ----------------------------------------------------------------------------
# Constants & Taxonomy
# ----------------------------------------------------------------------------
CATEGORIES = {
    "Textile_product": {
        "label": "Textile",
        "icon": "🧵",
        "hint": "Curtains, upholstery, sofas, carpets",
    },
    "Acoustic_product": {
        "label": "Acoustic",
        "icon": "🔇",
        "hint": "Ceiling tiles, wall panels, baffles",
    },
    "Lighting_product": {
        "label": "Lighting",
        "icon": "💡",
        "hint": "Luminaires, lamps, street lights",
    },
}

# level -> (color, soft background, range label)
LEVELS = {
    "High": ("#1E7B45", "#E3F1E7", "≥ 75%"),
    "Medium": ("#C98A0B", "#FBF1D9", "40 – 74%"),
    "Low": ("#C0392B", "#F9E3E0", "< 40%"),
}

# answer state -> (icon, label, fg, bg)
ANSWER_META = {
    "supported": ("✓", "Supported", "#1E7B45", "#E3F1E7"),
    "contradicted": ("✕", "Contradicted", "#C0392B", "#F9E3E0"),
    "unknown": ("?", "Unknown", "#6B7280", "#EEF0F2"),
}

# ----------------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap');

:root {
  --forest: #1F4D3A;
  --moss: #3F7A58;
  --sage: #DCE8DC;
  --mist: #EEF3EA;
  --cream: #F7F4EC;
  --clay: #B5651D;
  --ink: #1D2A24;
  --muted: #5F6F66;
  --line: #D9E1D6;
}

html, body, [class*="css"], .stApp { font-family: 'Inter', sans-serif; color: var(--ink); }
.stApp { background: var(--cream); }
.block-container { padding-top: 1.6rem; max-width: 1180px; }
h1, h2, h3, .mi-serif { font-family: 'Fraunces', Georgia, serif !important; color: var(--forest); letter-spacing: -0.01em; }
header[data-testid="stHeader"] { background: transparent; }

/* Sidebar */
section[data-testid="stSidebar"] { background: var(--mist); border-right: 1px solid var(--line); }
section[data-testid="stSidebar"] * { color: var(--ink); }

/* Hero */
.mi-hero {
  background: linear-gradient(135deg, #1F4D3A 0%, #3F7A58 60%, #7FA886 100%);
  border-radius: 20px; padding: 34px 38px; color: #fff; position: relative; overflow: hidden;
  box-shadow: 0 10px 30px rgba(31,77,58,.18); margin-bottom: 22px;
}
.mi-hero::after {
  content: "🌿"; position: absolute; right: 28px; top: -6px; font-size: 150px; opacity: .13; transform: rotate(14deg);
}
.mi-hero h1 { color: #fff !important; font-size: 2.3rem; margin: 0 0 6px 0; padding: 0; }
.mi-hero p { color: #E6F1E8; font-size: 1.05rem; margin: 0; max-width: 640px; line-height: 1.55; }
.mi-pill {
  display: inline-block; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.28);
  padding: 3px 12px; border-radius: 999px; font-size: .78rem; margin-bottom: 12px; letter-spacing: .04em; text-transform: uppercase;
}

/* Cards */
.mi-card {
  background: #fff; border: 1px solid var(--line); border-radius: 16px; padding: 20px 22px;
  box-shadow: 0 1px 2px rgba(31,77,58,.05); height: 100%;
}
.mi-step-num {
  width: 32px; height: 32px; border-radius: 50%; background: var(--forest); color: #fff;
  display: inline-flex; align-items: center; justify-content: center; font-weight: 600; margin-bottom: 10px;
}
.mi-card h4 { margin: 0 0 4px 0; font-family: 'Fraunces', serif; color: var(--forest); font-size: 1.08rem; }
.mi-card p { margin: 0; color: var(--muted); font-size: .92rem; line-height: 1.5; }

.mi-section { font-family: 'Fraunces', serif; color: var(--forest); font-size: 1.25rem; font-weight: 600; margin: 22px 0 4px; }
.mi-sub { color: var(--muted); font-size: .92rem; margin-bottom: 10px; }

/* Result */
.mi-result {
  display: flex; gap: 28px; align-items: center; flex-wrap: wrap;
  background: #fff; border: 1px solid var(--line); border-radius: 20px; padding: 24px 28px;
  box-shadow: 0 4px 16px rgba(31,77,58,.07);
}
.mi-ring { position: relative; width: 150px; height: 150px; flex: 0 0 auto; }
.mi-ring svg { transform: rotate(-90deg); }
.mi-ring-label { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.mi-ring-label b { font-family: 'Fraunces', serif; font-size: 2rem; line-height: 1; }
.mi-ring-label span { font-size: .75rem; color: var(--muted); margin-top: 4px; }
.mi-result-body { flex: 1 1 280px; }
.mi-badge { display: inline-block; padding: 4px 14px; border-radius: 999px; font-weight: 600; font-size: .9rem; }
.mi-result-body h3 { margin: 8px 0 2px 0; font-size: 1.5rem; }
.mi-meta { color: var(--muted); font-size: .9rem; margin-bottom: 14px; }
.mi-stats { display: flex; gap: 10px; flex-wrap: wrap; }
.mi-stat { border-radius: 12px; padding: 8px 14px; font-size: .85rem; font-weight: 500; }
.mi-stat b { font-size: 1.15rem; margin-right: 4px; }

/* Scale */
.mi-scale { display: flex; flex-direction: column; gap: 6px; }
.mi-scale-row { display: flex; align-items: center; gap: 10px; }
.mi-scale-bar {
  height: 26px; color: #fff; font-weight: 600; font-size: .8rem; display: flex; align-items: center; padding-left: 10px;
  clip-path: polygon(0 0, calc(100% - 10px) 0, 100% 50%, calc(100% - 10px) 100%, 0 100%); opacity: .3;
}
.mi-scale-bar.on { opacity: 1; box-shadow: 0 2px 6px rgba(0,0,0,.18); }
.mi-scale-hint { font-size: .78rem; color: var(--muted); }
.mi-scale-hint.on { color: var(--ink); font-weight: 600; }

/* Question rows */
.mi-q {
  display: flex; gap: 14px; align-items: flex-start; background: #fff; border: 1px solid var(--line);
  border-left-width: 5px; border-radius: 12px; padding: 12px 16px; margin-bottom: 8px;
}
.mi-q-id { font-family: ui-monospace, monospace; font-size: .75rem; color: var(--muted); min-width: 44px; padding-top: 3px; }
.mi-q-text { flex: 1; font-size: .93rem; line-height: 1.45; }
.mi-q-tag { font-size: .75rem; font-weight: 600; padding: 3px 10px; border-radius: 999px; white-space: nowrap; }
.mi-q-pts { font-weight: 600; min-width: 42px; text-align: right; font-size: .95rem; }

/* Empty state */
.mi-empty {
  border: 2px dashed #B9CDBB; border-radius: 18px; padding: 34px; text-align: center; background: rgba(255,255,255,.6);
}
.mi-empty .big { font-size: 2.6rem; }
.mi-empty h4 { font-family: 'Fraunces', serif; color: var(--forest); margin: 6px 0 4px; }
.mi-empty p { color: var(--muted); margin: 0; }

/* Streamlit widgets */
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
  border-radius: 12px; font-weight: 600; border: 1px solid var(--forest); transition: all .15s;
}
.stFormSubmitButton > button[kind="primaryFormSubmit"], .stButton > button[kind="primary"] {
  background: var(--forest); color: #fff; padding: .6rem 1.4rem;
}
.stFormSubmitButton > button[kind="primaryFormSubmit"]:hover, .stButton > button[kind="primary"]:hover {
  background: var(--moss); border-color: var(--moss); color: #fff; transform: translateY(-1px);
}
.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { font-weight: 600; color: var(--muted); }
.stTabs [aria-selected="true"] { color: var(--forest); }
div[data-testid="stForm"] { background: #fff; border: 1px solid var(--line); border-radius: 18px; padding: 22px; }
.stTextInput input, .stTextArea textarea { border-radius: 10px; }
</style>
"""

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def esc(value: object) -> str:
    return html.escape(str(value))


def apply_theme() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def scale_html(selected: str | None) -> str:
    rows = []
    for level, (color, _bg, rng) in LEVELS.items():
        on = level == selected
        width = {"High": 170, "Medium": 135, "Low": 100}[level]
        rows.append(
            '<div class="mi-scale-row">'
            f'<div class="mi-scale-bar {"on" if on else ""}" style="background:{color};width:{width}px">{level}</div>'
            f'<span class="mi-scale-hint {"on" if on else ""}">{"◀ " if on else ""}{rng}</span>'
            "</div>"
        )
    return f'<div class="mi-scale">{"".join(rows)}</div>'


def rows_to_csv(res: dict) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "question", "answer", "points_awarded", "points_possible"])
    for r in res["rows"]:
        awarded = r["points"] if r["state"] == "supported" else 0
        writer.writerow([r["id"], r["text"], r["state"], awarded, r["points"]])
    return buf.getvalue()


def run_assessment(category: str, product: str, notes: str, files: list) -> dict:
    """Run full assessment pipeline for a single product."""
    extra_notes = product if not notes.strip() else f"{product}\n\n{notes.strip()}"
    answers = ask_llm(category=category, files=files, extra_notes=extra_notes)

    score = calculate_score_and_level(category, answers)
    questionnaire = load_questionnaire(category)
    config = get_product_config(category)

    rows = []
    for q, criterion, ans in zip(questionnaire["questions"], config.criteria, answers):
        state = "supported" if ans is True else "contradicted" if ans is False else "unknown"
        rows.append(
            {
                "id": q.get("id", ""),
                "text": q.get("text", ""),
                "state": state,
                "points": criterion.points,
            }
        )

    counts = {k: sum(1 for r in rows if r["state"] == k) for k in ANSWER_META}
    return {
        "product": product,
        "category": category,
        "category_label": CATEGORIES[category]["label"],
        "level": score["level"],
        "points": score["points"],
        "max_points": score["max_points"],
        "percentage": score["percentage"],
        "counts": counts,
        "rows": rows,
        "n_files": len(files),
        "time": datetime.now().strftime("%d %b %Y, %H:%M"),
    }