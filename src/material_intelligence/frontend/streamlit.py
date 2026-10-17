import csv
import html
import io
import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from material_intelligence.api.chat import ask_llm
from material_intelligence.api.utils import load_questionnaire
from material_intelligence.engine.calculator import (
    calculate_score_and_level,
    get_product_config,
)

load_dotenv()

st.set_page_config(
    page_title="Material Intelligence · ECO-SCORE",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------------
# Configuration
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
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# State
# ----------------------------------------------------------------------------
def init_state() -> None:
    st.session_state.setdefault("result", None)  # latest assessment (dict)
    st.session_state.setdefault("history", [])  # list of past assessment dicts


init_state()


# ----------------------------------------------------------------------------
# HTML helpers
# ----------------------------------------------------------------------------
def esc(value: object) -> str:
    return html.escape(str(value))


def render_hero() -> None:
    st.markdown(
        '<div class="mi-hero">'
        '<span class="mi-pill">ECO-SCORE · Greener interiors</span>'
        "<h1>Material Intelligence</h1>"
        "<p>Upload product documentation and get an evidence-based sustainability "
        "rating for textile, acoustic and lighting products in minutes.</p>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_how_it_works() -> None:
    steps = [
        ("1", "Pick a category", "Choose Textile, Acoustic or Lighting. Each has its own ECO-SCORE questionnaire."),
        ("2", "Add evidence", "Upload datasheets, certificates, EPDs or photos. The more evidence, the fewer unknowns."),
        ("3", "Name your product", "Enter the product name and any notes (materials, origin, certifications)."),
        ("4", "Read the result", "Get a High / Medium / Low level plus a full question-by-question breakdown."),
    ]
    cols = st.columns(4)
    for col, (num, title, text) in zip(cols, steps):
        col.markdown(
            f'<div class="mi-card"><div class="mi-step-num">{num}</div>'
            f"<h4>{title}</h4><p>{text}</p></div>",
            unsafe_allow_html=True,
        )


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


def render_result(res: dict) -> None:
    color, bg, _ = LEVELS[res["level"]]
    pct = max(0.0, min(100.0, float(res["percentage"])))
    radius, circ = 62, 2 * 3.14159 * 62
    dash = circ * pct / 100

    ring = (
        '<div class="mi-ring">'
        '<svg width="150" height="150" viewBox="0 0 150 150">'
        f'<circle cx="75" cy="75" r="{radius}" fill="none" stroke="#E6ECE3" stroke-width="12"/>'
        f'<circle cx="75" cy="75" r="{radius}" fill="none" stroke="{color}" stroke-width="12" '
        f'stroke-linecap="round" stroke-dasharray="{dash:.1f} {circ:.1f}"/>'
        "</svg>"
        f'<div class="mi-ring-label"><b style="color:{color}">{pct:.0f}%</b>'
        f'<span>{esc(res["points"])} / {esc(res["max_points"])} pts</span></div>'
        "</div>"
    )

    stats = "".join(
        f'<div class="mi-stat" style="background:{ANSWER_META[k][3]};color:{ANSWER_META[k][2]}">'
        f'<b>{res["counts"][k]}</b>{ANSWER_META[k][1]}</div>'
        for k in ("supported", "contradicted", "unknown")
    )

    st.markdown(
        '<div class="mi-result">'
        f"{ring}"
        '<div class="mi-result-body">'
        f'<span class="mi-badge" style="background:{bg};color:{color}">{res["level"]} sustainability</span>'
        f'<h3>{esc(res["product"])}</h3>'
        f'<div class="mi-meta">{esc(res["category_label"])} · {esc(res["time"])} · '
        f'{res["n_files"]} document(s) analysed</div>'
        f'<div class="mi-stats">{stats}</div>'
        "</div>"
        f"{scale_html(res['level'])}"
        "</div>",
        unsafe_allow_html=True,
    )


def render_rows(rows: list[dict], flt: str) -> None:
    shown = [r for r in rows if flt == "All" or r["state"] == flt.lower()]
    if not shown:
        st.info("No questions match this filter.")
        return
    out = []
    for r in shown:
        icon, label, fg, bg = ANSWER_META[r["state"]]
        pts = f'+{r["points"]}' if r["state"] == "supported" else "0"
        out.append(
            f'<div class="mi-q" style="border-left-color:{fg}">'
            f'<div class="mi-q-id">{esc(r["id"])}</div>'
            f'<div class="mi-q-text">{esc(r["text"])}</div>'
            f'<span class="mi-q-tag" style="background:{bg};color:{fg}">{icon} {label}</span>'
            f'<div class="mi-q-pts" style="color:{fg}">{pts}</div>'
            "</div>"
        )
    st.markdown("".join(out), unsafe_allow_html=True)


def rows_to_csv(res: dict) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "question", "answer", "points_awarded", "points_possible"])
    for r in res["rows"]:
        awarded = r["points"] if r["state"] == "supported" else 0
        writer.writerow([r["id"], r["text"], r["state"], awarded, r["points"]])
    return buf.getvalue()


# ----------------------------------------------------------------------------
# Assessment logic
# ----------------------------------------------------------------------------
def run_assessment(category: str, product: str, notes: str, files: list) -> dict:
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


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🌿 Material Intelligence")
    st.caption("Assessing materials for greener interiors")

    st.markdown("#### Level guide")
    st.markdown(
        scale_html(st.session_state.result["level"] if st.session_state.result else None),
        unsafe_allow_html=True,
    )
    st.caption("Level is based on the share of ECO-SCORE points the evidence supports.")

    with st.expander("💡 Tips for better results"):
        st.markdown(
            "- Upload **EPDs, eco-labels and certificates** – they carry the most weight.\n"
            "- Add **material composition** and **country of origin** in notes.\n"
            "- Many *Unknown* answers usually mean missing documentation, not a bad product.\n"
            "- Supported formats: PDF, PNG, JPG, TXT, CSV."
        )

    st.divider()
    if st.button("↺ Reset everything", use_container_width=True):
        st.session_state.result = None
        st.session_state.history = []
        st.rerun()


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
render_hero()

tab_assess, tab_history, tab_guide = st.tabs(["🔍 Assessment", "🕘 History", "📖 How to use"])

# ---- Assessment tab ----------------------------------------------------------
with tab_assess:
    if st.session_state.result is None:
        render_how_it_works()

    st.markdown('<div class="mi-section">New assessment</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="mi-sub">Fill in the form below, then press <b>Run assessment</b>.</div>',
        unsafe_allow_html=True,
    )

    with st.form("assessment_form", clear_on_submit=False):
        category = st.radio(
            "1 · Product category",
            options=list(CATEGORIES.keys()),
            format_func=lambda k: f'{CATEGORIES[k]["icon"]}  {CATEGORIES[k]["label"]}  –  {CATEGORIES[k]["hint"]}',
            horizontal=True,
        )

        files = st.file_uploader(
            "2 · Product documentation (optional but recommended)",
            accept_multiple_files=True,
            type=["pdf", "png", "jpg", "jpeg", "txt", "csv"],
            help="Datasheets, certificates, EPDs, product images.",
        )

        c1, c2 = st.columns([1, 1])
        product = c1.text_input(
            "3 · Product name *",
            placeholder="e.g. IKEA MAJGULL curtain",
        )
        notes = c2.text_area(
            "Extra notes",
            placeholder="Materials, certifications, origin, anything not in the documents…",
            height=100,
        )

        submitted = st.form_submit_button("Run assessment", type="primary")

    if submitted:
        if not os.getenv("GEMINI_API_KEY"):
            st.error("`GEMINI_API_KEY` is missing. Add it to your environment or `.env` file and restart the app.")
        elif not product.strip():
            st.warning("Please enter a product name to continue.")
        else:
            try:
                with st.status(f"Assessing {CATEGORIES[category]['label'].lower()} product…", expanded=True) as status:
                    st.write("📄 Reading documentation")
                    st.write("🧠 Answering the ECO-SCORE questionnaire")
                    res = run_assessment(category, product.strip(), notes, list(files or []))
                    st.write("🧮 Calculating score and level")
                    status.update(label="Assessment complete", state="complete", expanded=False)
                st.session_state.result = res
                st.session_state.history.insert(0, res)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Assessment failed: {exc}")
                st.caption("Check your API key, network connection and uploaded files, then try again.")

    res = st.session_state.result
    if res:
        st.markdown('<div class="mi-section">Result</div>', unsafe_allow_html=True)
        render_result(res)

        st.markdown('<div class="mi-section">Questionnaire breakdown</div>', unsafe_allow_html=True)
        left, right = st.columns([3, 1])
        flt = left.radio(
            "Filter",
            ["All", "Supported", "Contradicted", "Unknown"],
            horizontal=True,
            label_visibility="collapsed",
            key="flt_current",
        )
        right.download_button(
            "⬇ Download CSV",
            data=rows_to_csv(res),
            file_name=f"eco_score_{res['category']}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        render_rows(res["rows"], flt)
    else:
        st.markdown(
            '<div class="mi-empty"><div class="big">🌱</div><h4>No assessment yet</h4>'
            "<p>Your score, level and detailed breakdown will appear here.</p></div>",
            unsafe_allow_html=True,
        )

# ---- History tab -------------------------------------------------------------
with tab_history:
    hist = st.session_state.history
    if not hist:
        st.markdown(
            '<div class="mi-empty"><div class="big">🕘</div><h4>Nothing here yet</h4>'
            "<p>Completed assessments in this session will be listed here.</p></div>",
            unsafe_allow_html=True,
        )
    else:
        for i, h in enumerate(hist):
            color, bg, _ = LEVELS[h["level"]]
            title = f'{h["product"]} · {h["category_label"]} · {h["percentage"]:.0f}% · {h["level"]}'
            with st.expander(title, expanded=False):
                st.caption(f'{h["time"]} · {h["points"]}/{h["max_points"]} pts · {h["n_files"]} document(s)')
                if st.button("Show as current result", key=f"load_{i}"):
                    st.session_state.result = h
                    st.rerun()
                render_rows(h["rows"], "All")

# ---- Guide tab ---------------------------------------------------------------
with tab_guide:
    g1, g2 = st.columns(2)
    with g1:
        st.markdown('<div class="mi-section">What is ECO-SCORE?</div>', unsafe_allow_html=True)
        st.markdown(
            "ECO-SCORE is a questionnaire-based method for rating the environmental performance of "
            "interior products. Every question is worth a number of points. Your documents are checked "
            "against each question, and the share of points earned decides the sustainability level."
        )
        st.markdown('<div class="mi-section">Answer types</div>', unsafe_allow_html=True)
        st.markdown(
            "- ✅ **Supported** – the documents confirm the criterion; points are awarded.\n"
            "- ❌ **Contradicted** – the documents show the criterion is not met; no points.\n"
            "- ⚪ **Unknown** – no evidence found; no points. Upload more documents to resolve."
        )
    with g2:
        st.markdown('<div class="mi-section">Sustainability levels</div>', unsafe_allow_html=True)
        st.markdown(scale_html(None), unsafe_allow_html=True)
        st.markdown('<div class="mi-section">Quick start</div>', unsafe_allow_html=True)
        st.markdown(
            "1. Open the **Assessment** tab and choose a category.\n"
            "2. Upload datasheets, certificates or EPDs.\n"
            "3. Enter the product name and optional notes.\n"
            "4. Press **Run assessment** and review the score.\n"
            "5. Filter the breakdown, export it as CSV, or compare runs in **History**."
        )
    st.info("Results are AI-assisted and depend on the documents provided. Verify key claims before publishing.")