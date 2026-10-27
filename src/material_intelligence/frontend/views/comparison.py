import csv
import io

import streamlit as st
from dotenv import load_dotenv

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
def init_comparison_state():
    if "cmp_num_products" not in st.session_state:
        st.session_state.cmp_num_products = 2
    if "cmp_results" not in st.session_state:
        st.session_state.cmp_results = None


init_comparison_state()


# ----------------------------------------------------------------------------
# Helper: CSV Generation for Comparison Matrix
# ----------------------------------------------------------------------------
def comparison_matrix_to_csv(results: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)

    # Header: id, question, points_possible, Product1, Product2, ...
    header = ["id", "question", "points_possible"]
    for res in results:
        header.append(f"{res['product']} (Answer)")
        header.append(f"{res['product']} (Points)")
    writer.writerow(header)

    num_rows = len(results[0]["rows"])
    for idx in range(num_rows):
        sample_row = results[0]["rows"][idx]
        row_data = [sample_row["id"], sample_row["text"], sample_row["points"]]
        for res in results:
            r = res["rows"][idx]
            awarded = r["points"] if r["state"] == "supported" else 0
            row_data.append(r["state"])
            row_data.append(awarded)
        writer.writerow(row_data)

    return buf.getvalue()


# ----------------------------------------------------------------------------
# Header Hero
# ----------------------------------------------------------------------------
st.markdown(
    '<div class="mi-hero">'
    '<span class="mi-pill">ECO-SCORE · Comparison Matrix</span>'
    "<h1>Product Comparison</h1>"
    "<p>Compare 2 or more products of the same category side-by-side using the ECO-SCORE methodology. "
    "Identify key differences in recycled content, certifications, chemical safety, and overall sustainability.</p>"
    "</div>",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🌿 Material Intelligence")
    st.caption("Side-by-side material evaluation")

    st.markdown("#### Level guide")
    st.markdown(scale_html(None), unsafe_allow_html=True)
    st.caption("Level is based on the share of ECO-SCORE points supported by documentation.")


# ----------------------------------------------------------------------------
# Step 1: Category Selection
# ----------------------------------------------------------------------------
st.markdown('<div class="mi-section">1. Select Material Category</div>', unsafe_allow_html=True)
st.markdown('<div class="mi-sub">All products compared together must share the same category questionnaire.</div>', unsafe_allow_html=True)

cat_options = list(CATEGORIES.keys())
selected_cat = st.selectbox(
    "Category",
    cat_options,
    format_func=lambda k: f"{CATEGORIES[k]['icon']} {CATEGORIES[k]['label']} — {CATEGORIES[k]['hint']}",
    label_visibility="collapsed",
)


# ----------------------------------------------------------------------------
# Step 2: Dynamic Product Cards
# ----------------------------------------------------------------------------
st.markdown('<div class="mi-section">2. Upload Products for Comparison</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="mi-sub">Upload documentation for at least 2 {CATEGORIES[selected_cat]["label"].lower()} products.</div>',
    unsafe_allow_html=True,
)

col_ctrl1, col_ctrl2, _ = st.columns([1.5, 1.5, 5])
with col_ctrl1:
    if st.button("➕ Add Product", use_container_width=True):
        if st.session_state.cmp_num_products < 6:
            st.session_state.cmp_num_products += 1
            st.rerun()
        else:
            st.warning("Maximum 6 products at once.")

with col_ctrl2:
    if st.button("➖ Remove Product", use_container_width=True):
        if st.session_state.cmp_num_products > 2:
            st.session_state.cmp_num_products -= 1
            st.rerun()
        else:
            st.info("Minimum 2 products required for comparison.")

# Render Product Cards using tabs
prod_tabs = st.tabs([f"📦 Product {i + 1}" for i in range(st.session_state.cmp_num_products)])

products_data = []
all_valid = True

for i, tab in enumerate(prod_tabs):
    with tab:
        p_col1, p_col2 = st.columns([1, 1])
        with p_col1:
            prod_name = st.text_input(
                "Product name",
                value=f"Product {chr(65 + i)}",
                key=f"cmp_name_{i}",
                placeholder=f"e.g. Wool Felt Panel {chr(65 + i)}",
            )
            prod_notes = st.text_area(
                "Additional notes (optional)",
                key=f"cmp_notes_{i}",
                placeholder="Manufacturer, composition, claimed certifications...",
                height=95,
            )
        with p_col2:
            prod_files = st.file_uploader(
                "Product documentation (PDF, images, TXT, CSV)",
                accept_multiple_files=True,
                key=f"cmp_files_{i}",
                help="EPD, technical datasheet, certificates, or testing reports.",
            )

        if not prod_files:
            st.caption("⚠️ Please upload at least one document for this product.")
            all_valid = False

        products_data.append(
            {
                "index": i,
                "name": prod_name.strip() or f"Product {i + 1}",
                "notes": prod_notes,
                "files": prod_files or [],
            }
        )

st.markdown("<br>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Run Assessment Action
# ----------------------------------------------------------------------------
run_button = st.button("⚖️ Run Side-by-Side Comparison", type="primary", disabled=not all_valid)

if run_button:
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, prod in enumerate(products_data):
        status_text.markdown(f"**Analyzing {idx + 1} of {len(products_data)}:** *{esc(prod['name'])}*...")
        try:
            res = run_assessment(
                category=selected_cat,
                product=prod["name"],
                notes=prod["notes"],
                files=prod["files"],
            )
            results.append(res)
        except Exception as e:
            st.error(f"Error evaluating '{prod['name']}': {e}")
            results = None
            break

        progress_bar.progress((idx + 1) / len(products_data))

    status_text.empty()
    progress_bar.empty()

    if results:
        st.session_state.cmp_results = results
        st.success(f"Successfully evaluated all {len(results)} products!")
        st.rerun()


# ----------------------------------------------------------------------------
# Comparison Results Section
# ----------------------------------------------------------------------------
cmp_res = st.session_state.cmp_results

if cmp_res:
    st.markdown('<div class="mi-section">Comparison Results</div>', unsafe_allow_html=True)

    # 1. Summary Cards Row
    score_cols = st.columns(len(cmp_res))
    for col, res in zip(score_cols, cmp_res):
        color, bg, _ = LEVELS[res["level"]]
        pct = max(0.0, min(100.0, float(res["percentage"])))
        with col:
            st.markdown(
                f"""
                <div class="mi-card" style="border-top: 5px solid {color}; text-align: center; padding: 20px 14px;">
                    <span class="mi-badge" style="background:{bg}; color:{color}; font-size:0.8rem; margin-bottom: 8px;">
                        {res["level"]} Sustainability
                    </span>
                    <h3 style="margin: 6px 0; font-size: 1.3rem;">{esc(res["product"])}</h3>
                    <div style="font-size: 2.2rem; font-weight: 700; color: {color}; font-family: 'Fraunces', serif;">
                        {pct:.0f}%
                    </div>
                    <div style="color: var(--muted); font-size: 0.88rem; margin-bottom: 12px;">
                        <b>{res["points"]}</b> / {res["max_points"]} pts
                    </div>
                    <div style="display: flex; justify-content: center; gap: 6px; font-size: 0.78rem;">
                        <span style="background:{ANSWER_META['supported'][3]}; color:{ANSWER_META['supported'][2]}; padding: 3px 8px; border-radius: 999px;">
                            ✓ {res["counts"]["supported"]}
                        </span>
                        <span style="background:{ANSWER_META['contradicted'][3]}; color:{ANSWER_META['contradicted'][2]}; padding: 3px 8px; border-radius: 999px;">
                            ✕ {res["counts"]["contradicted"]}
                        </span>
                        <span style="background:{ANSWER_META['unknown'][3]}; color:{ANSWER_META['unknown'][2]}; padding: 3px 8px; border-radius: 999px;">
                            ? {res["counts"]["unknown"]}
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Controls: Filter & Export
    st.markdown('<div class="mi-section">Detailed Comparison Matrix</div>', unsafe_allow_html=True)
    c_left, c_mid, c_right = st.columns([2.5, 2.5, 2])

    with c_left:
        diff_only = st.checkbox("🔍 Show differences only", value=False, help="Display only questions where the products have different answers.")

    with c_mid:
        state_flt = st.radio(
            "Filter state",
            ["All", "Supported", "Contradicted", "Unknown"],
            horizontal=True,
            label_visibility="collapsed",
            key="cmp_state_flt",
        )

    with c_right:
        st.download_button(
            "⬇ Download Matrix CSV",
            data=comparison_matrix_to_csv(cmp_res),
            file_name=f"comparison_{cmp_res[0]['category']}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # 3. Render Matrix Rows
    num_questions = len(cmp_res[0]["rows"])
    rendered_count = 0

    for q_idx in range(num_questions):
        q_id = cmp_res[0]["rows"][q_idx]["id"]
        q_text = cmp_res[0]["rows"][q_idx]["text"]
        q_pts = cmp_res[0]["rows"][q_idx]["points"]

        product_states = [res["rows"][q_idx]["state"] for res in cmp_res]

        # Apply Differences filter
        if diff_only and len(set(product_states)) <= 1:
            continue

        # Apply Answer State filter
        if state_flt != "All" and state_flt.lower() not in product_states:
            continue

        rendered_count += 1

        # Product result columns
        badge_html_list = []
        for res in cmp_res:
            st_val = res["rows"][q_idx]["state"]
            icon, lbl, fg, bg = ANSWER_META[st_val]
            pts_str = f"+{q_pts}" if st_val == "supported" else "0"
            badge_html_list.append(
                f'<div style="flex: 1; min-width: 140px; background: #FAFBF9; border: 1px solid var(--line); border-radius: 10px; padding: 10px 14px; margin: 2px;">'
                f'<div style="font-size: 0.8rem; font-weight: 600; color: var(--forest); margin-bottom: 4px;">{esc(res["product"])}</div>'
                f'<div style="display: flex; align-items: center; justify-content: space-between;">'
                f'<span style="background:{bg}; color:{fg}; padding: 3px 10px; border-radius: 999px; font-size: 0.78rem; font-weight: 600;">'
                f'{icon} {lbl}'
                f'</span>'
                f'<span style="font-size: 0.88rem; font-weight: 600; color:{fg};">'
                f'{pts_str} pts'
                f'</span>'
                f'</div>'
                f'</div>'
            )

        card_html = (
            f'<div style="background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 16px 20px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(31,77,58,0.04);">'
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">'
            f'<span style="font-family: ui-monospace, monospace; font-size: 0.82rem; color: var(--muted); font-weight: 600;">{esc(q_id)}</span>'
            f'<span style="font-size: 0.8rem; font-weight: 600; color: var(--forest); background: var(--sage); padding: 3px 10px; border-radius: 999px;">Max: {q_pts} pts</span>'
            f'</div>'
            f'<div style="font-size: 0.95rem; font-weight: 500; color: var(--ink); margin-bottom: 12px; line-height: 1.45;">'
            f'{esc(q_text)}'
            f'</div>'
            f'<div style="display: flex; gap: 10px; flex-wrap: wrap;">'
            f'{"".join(badge_html_list)}'
            f'</div>'
            f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

    if rendered_count == 0:
        st.info("No questions match the current filter selection.")

else:
    st.markdown(
        '<div class="mi-empty"><div class="big">⚖️</div><h4>No comparison yet</h4>'
        "<p>Upload documentation for 2 or more products above and click 'Run Side-by-Side Comparison'.</p></div>",
        unsafe_allow_html=True,
    )