import os

import streamlit as st
from dotenv import load_dotenv

from material_intelligence.frontend.ui_common import (
    ANSWER_META,
    CATEGORIES,
    LEVELS,
    apply_theme,
    esc,
    rows_to_csv,
    run_assessment,
    scale_html,
)

load_dotenv()
apply_theme()


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