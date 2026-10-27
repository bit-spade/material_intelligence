import streamlit as st
from dotenv import load_dotenv

from material_intelligence.api.chat_recommendation import get_sustainable_recommendations
from material_intelligence.frontend.ui_common import (
    ANSWER_META,
    CATEGORIES,
    LEVELS,
    apply_theme,
    esc,
    run_assessment,
    scale_html,
)


load_dotenv()
apply_theme()


# ----------------------------------------------------------------------------
# State Initialization
# ----------------------------------------------------------------------------
def init_advisor_state():
    if "adv_baseline" not in st.session_state:
        st.session_state.adv_baseline = None
    if "adv_recommendations" not in st.session_state:
        st.session_state.adv_recommendations = None


init_advisor_state()

# ----------------------------------------------------------------------------
# Header Hero
# ----------------------------------------------------------------------------
st.markdown(
    '<div class="mi-hero">'
    '<span class="mi-pill">ECO-SCORE · AI Material Advisor</span>'
    "<h1>Sustainable Material Advisor</h1>"
    "<p>Evaluate your baseline product and discover superior, market-ready green alternatives. "
    "The advisor analyzes unmet criteria and recommends certified commercial replacements.</p>"
    "</div>",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🌿 Material Intelligence")
    st.caption("AI-driven sustainable material sourcing")

    st.markdown("#### Level guide")
    current_level = st.session_state.adv_baseline["level"] if st.session_state.adv_baseline else None
    st.markdown(scale_html(current_level), unsafe_allow_html=True)
    st.caption("Level is based on verified ECO-SCORE questionnaire points.")


# ----------------------------------------------------------------------------
# Step 1: Baseline Product Upload
# ----------------------------------------------------------------------------
st.markdown('<div class="mi-section">1. Specify Baseline Product</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="mi-sub">Upload product sheets or datasheets for the material you currently use or are considering.</div>',
    unsafe_allow_html=True,
)

col1, col2 = st.columns([1, 1])

with col1:
    selected_cat = st.selectbox(
        "Material Category",
        list(CATEGORIES.keys()),
        format_func=lambda k: f"{CATEGORIES[k]['icon']} {CATEGORIES[k]['label']} — {CATEGORIES[k]['hint']}",
        key="adv_cat",
    )
    product_name = st.text_input(
        "Product Name",
        placeholder="e.g. IKEA TIBAST Cotton Curtains",
        key="adv_prod_name",
    )
    designer_priorities = st.text_area(
        "Project Priorities / Constraints (optional)",
        placeholder="e.g. Commercial hotel setting, prioritize high recycled content, OEKO-TEX certification, and high abrasion resistance...",
        height=85,
        key="adv_priorities",
    )

with col2:
    uploaded_files = st.file_uploader(
        "Upload documentation (PDF, TXT, CSV, images)",
        accept_multiple_files=True,
        key="adv_files",
        help="EPDs, technical specifications, brochures, or testing reports.",
    )

can_evaluate = bool(product_name.strip() and uploaded_files)

c_eval, _ = st.columns([2, 5])
with c_eval:
    if st.button("🌿 Evaluate Baseline Product", type="primary", disabled=not can_evaluate, use_container_width=True):
        with st.spinner("Evaluating baseline product against ECO-SCORE criteria..."):
            try:
                baseline_res = run_assessment(
                    category=selected_cat,
                    product=product_name.strip(),
                    notes=designer_priorities,
                    files=uploaded_files,
                )
                st.session_state.adv_baseline = baseline_res
                st.session_state.adv_recommendations = None  # Reset previous recommendations
                st.success(f"Baseline evaluation complete for '{product_name}'!")
                st.rerun()
            except Exception as e:
                st.error(f"Error evaluating baseline product: {e}")

# ----------------------------------------------------------------------------
# Step 2: Baseline Results Display
# ----------------------------------------------------------------------------
baseline = st.session_state.adv_baseline

if baseline:
    st.markdown('<div class="mi-section">Baseline ECO-SCORE Result</div>', unsafe_allow_html=True)

    b_color, b_bg, _ = LEVELS[baseline["level"]]
    b_pct = max(0.0, min(100.0, float(baseline["percentage"])))

    # Summary card
    st.markdown(
        f'<div class="mi-card" style="border-left: 6px solid {b_color}; padding: 22px 26px; margin-bottom: 20px;">'
        f'<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">'
        f'<div>'
        f'<span class="mi-badge" style="background:{b_bg}; color:{b_color}; font-size: 0.85rem; margin-bottom: 6px;">'
        f'{baseline["level"]} Sustainability Tier</span>'
        f'<h3 style="margin: 4px 0 2px 0; font-size: 1.5rem;">{esc(baseline["product"])}</h3>'
        f'<div style="color: var(--muted); font-size: 0.88rem;">{esc(baseline["category_label"])} · {baseline["n_files"]} document(s) analysed</div>'
        f'</div>'
        f'<div style="text-align: right;">'
        f'<div style="font-size: 2.4rem; font-weight: 700; color:{b_color}; font-family: \'Fraunces\', serif; line-height: 1;">{b_pct:.0f}%</div>'
        f'<div style="color: var(--muted); font-size: 0.85rem;"><b>{baseline["points"]}</b> / {baseline["max_points"]} pts</div>'
        f'</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------------
    # Step 3: Find Greener Market Alternatives Trigger
    # ------------------------------------------------------------------------
    st.markdown('<div class="mi-section">2. Discover Greener Market Alternatives</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="mi-sub">Let our AI sourcing engine search for certified commercial materials that fulfill your unmet criteria.</div>',
        unsafe_allow_html=True,
    )

    c_rec, _ = st.columns([2.5, 4.5])
    with c_rec:
        find_button = st.button("🔍 Find Sustainable Alternatives", type="primary", use_container_width=True)

    if find_button:
        with st.spinner("Analyzing unmet criteria and searching market alternatives..."):
            try:
                rec_result = get_sustainable_recommendations(
                    category=baseline["category"],
                    baseline_result=baseline,
                    project_priorities=designer_priorities,
                )
                st.session_state.adv_recommendations = rec_result
                st.success("Found top sustainable alternatives!")
                st.rerun()
            except Exception as e:
                st.error(f"Error fetching recommendations: {e}")

# ----------------------------------------------------------------------------
# Step 4: Display Recommendations
# ----------------------------------------------------------------------------
recs = st.session_state.adv_recommendations

if recs:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="mi-section">Recommended Market Alternatives</div>', unsafe_allow_html=True)

    # Baseline critique & improvement areas
    st.markdown(
        f'<div style="background: #FAF8F2; border: 1px solid var(--line); border-radius: 14px; padding: 18px 22px; margin-bottom: 22px;">'
        f'<h4 style="margin: 0 0 6px 0; color: var(--forest); font-family: \'Fraunces\', serif;">Assessment & Opportunity Analysis</h4>'
        f'<p style="margin: 0 0 10px 0; font-size: 0.94rem; color: var(--ink); line-height: 1.5;">{esc(recs.baseline_summary)}</p>'
        f'<div style="font-size: 0.82rem; font-weight: 600; color: var(--muted); margin-bottom: 6px;">Key criteria to improve upon:</div>'
        f'<div style="display: flex; gap: 6px; flex-wrap: wrap;">'
        + "".join([f'<span style="background: #EAE6DA; color: var(--forest); padding: 3px 10px; border-radius: 999px; font-size: 0.78rem;">📌 {esc(area)}</span>' for area in recs.key_improvement_areas])
        + f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Alternative Cards Grid
    alt_cols = st.columns(len(recs.alternatives))
    for col, alt in zip(alt_cols, recs.alternatives):
        tier_color, tier_bg, _ = LEVELS.get(alt.estimated_level, LEVELS["High"])
        with col:
            certs_html = "".join(
                [f'<span style="background: var(--sage); color: var(--forest); padding: 2px 8px; border-radius: 999px; font-size: 0.74rem; font-weight: 600;">{esc(c)}</span> ' for c in alt.certifications]
            )
            advantages_html = "".join(
                [f'<li style="margin-bottom: 5px;">{esc(adv)}</li>' for adv in alt.sustainable_advantages]
            )

            st.markdown(
                f'<div class="mi-card" style="border-top: 5px solid {tier_color}; padding: 20px; display: flex; flex-direction: column; justify-content: space-between;">'
                f'<div>'
                f'<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">'
                f'<span style="font-size: 0.78rem; font-weight: 600; color: var(--muted); text-transform: uppercase;">{esc(alt.manufacturer)}</span>'
                f'<span style="background:{tier_bg}; color:{tier_color}; padding: 2px 8px; border-radius: 999px; font-size: 0.72rem; font-weight: 600;">Est. {esc(alt.estimated_level)}</span>'
                f'</div>'
                f'<h3 style="margin: 0 0 8px 0; font-size: 1.25rem;">{esc(alt.product_name)}</h3>'
                f'<p style="font-size: 0.88rem; color: var(--muted); margin-bottom: 12px; line-height: 1.45;">{esc(alt.description)}</p>'
                f'<div style="font-size: 0.8rem; font-weight: 600; color: var(--ink); margin-bottom: 6px;">Composition: <span style="font-weight: 400; color: var(--muted);">{esc(alt.material_composition)}</span></div>'
                f'<div style="margin-bottom: 14px; display: flex; flex-wrap: wrap; gap: 4px;">{certs_html}</div>'
                f'<div style="font-size: 0.82rem; font-weight: 600; color: var(--forest); margin-bottom: 6px;">Sustainable Upgrades:</div>'
                f'<ul style="font-size: 0.82rem; color: var(--ink); padding-left: 18px; margin: 0 0 14px 0; line-height: 1.4;">{advantages_html}</ul>'
                f'</div>'
                f'<div style="background: var(--mist); border-radius: 10px; padding: 10px 12px; font-size: 0.8rem; color: var(--forest); line-height: 1.4; border-left: 3px solid var(--forest);">'
                f'<b>Why pick this:</b> {esc(alt.why_recommended)}'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)
    st.info("💡 **Designer Tip**: Request official Environmental Product Declarations (EPD) or swatch samples directly from the manufacturer to verify all sustainability documentation.")