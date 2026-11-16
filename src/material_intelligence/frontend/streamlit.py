import os
import re
import zipfile

import streamlit as st
from dotenv import load_dotenv

from material_intelligence.api.chat_recommendation import get_sustainable_recommendations
from material_intelligence.frontend.ui_common import CATEGORIES, LEVELS, apply_theme, esc, run_assessment
from material_intelligence.frontend.workflow import (
    parse_product_file,
    product_notes,
    products_to_csv,
    report_to_csv,
)

load_dotenv()
st.set_page_config(page_title="Material Intelligence · ECO-SCORE", layout="wide")
apply_theme()


def reset() -> None:
    for key in (
        "wizard_step",
        "products",
        "source_products",
        "results",
        "recommendations",
        "alternative_scores",
        "final_products",
    ):
        st.session_state.pop(key, None)
    st.rerun()


def go_to_step(step: int) -> None:
    st.session_state.wizard_step = step
    st.rerun()


def init_state() -> None:
    st.session_state.setdefault("wizard_step", 0)
    st.session_state.setdefault("products", [])
    st.session_state.setdefault("results", [])
    st.session_state.setdefault("recommendations", {})
    st.session_state.setdefault("alternative_scores", {})
    st.session_state.setdefault("final_products", [])


def step_header(step: int) -> None:
    labels = ["Import", "Verify", "Score", "Substitute", "Export"]
    st.markdown(
        "  ".join(
            f"**{'●' if index == step else '○'} {index + 1}. {label}**"
            for index, label in enumerate(labels)
        )
    )


def product_label(product: dict) -> str:
    return product["name"] or "Unnamed product"


def numeric_amount(value: str) -> float:
    match = re.search(r"\d+(?:[.,]\d+)?", str(value))
    return float(match.group().replace(",", ".")) if match else 1.0


def weighted_overall(products: list[dict]) -> dict:
    weights = [numeric_amount(product.get("amount", "")) for product in products]
    total_weight = sum(weights) or 1.0
    percentage = sum(product["selected_result"]["percentage"] * weight for product, weight in zip(products, weights)) / total_weight
    max_points = round(sum(product["selected_result"]["max_points"] * weight for product, weight in zip(products, weights)) / total_weight)
    points = round(sum(product["selected_result"]["points"] * weight for product, weight in zip(products, weights)) / total_weight)
    level = "High" if percentage >= 75 else "Medium" if percentage >= 40 else "Low"
    return {"percentage": round(percentage, 2), "points": points, "max_points": max_points, "level": level}


def render_score(result: dict) -> None:
    color, bg, _ = LEVELS[result["level"]]
    st.markdown(
        f'<div class="mi-card" style="border-left:6px solid {color}">'
        f'<span class="mi-badge" style="background:{bg};color:{color}">{result["level"]}</span>'
        f'<h3>{esc(result["product"])}</h3>'
        f'<strong style="font-size:2rem;color:{color}">{result["percentage"]:.0f}%</strong>'
        f' <span>{result["points"]}/{result["max_points"]} points</span></div>',
        unsafe_allow_html=True,
    )


def render_overall_score(overall: dict) -> None:
    color, bg, _ = LEVELS[overall["level"]]
    percentage = max(0.0, min(100.0, float(overall["percentage"])))
    radius = 52
    circumference = 2 * 3.14159 * radius
    dash = circumference * percentage / 100
    st.markdown(
        f"""
        <div class="mi-result" style="margin: 18px 0;">
            <div class="mi-ring">
                <svg width="132" height="132" viewBox="0 0 132 132">
                    <circle cx="66" cy="66" r="{radius}" fill="none"
                        stroke="#E6ECE3" stroke-width="12"/>
                    <circle cx="66" cy="66" r="{radius}" fill="none"
                        stroke="{color}" stroke-width="12" stroke-linecap="round"
                        stroke-dasharray="{dash:.1f} {circumference:.1f}"
                        transform="rotate(-90 66 66)"/>
                </svg>
                <div class="mi-ring-label">
                    <b style="color:{color}">{percentage:.0f}%</b>
                    <span>overall</span>
                </div>
            </div>
            <div class="mi-result-body">
                <span class="mi-badge" style="background:{bg};color:{color}">
                    {overall["level"]} sustainability
                </span>
                <h3>Overall project score</h3>
                <div class="mi-meta">
                    Weighted by product amount · {overall["points"]} / {overall["max_points"]} points
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def score_recommendation_alternatives(index: int, recommendation) -> None:
    scores = []
    for alternative in recommendation.alternatives:
        evidence = "\n".join(
            [
                f"Alternative product: {alternative.product_name}",
                f"Manufacturer: {alternative.manufacturer}",
                f"Description: {alternative.description}",
                f"Material composition: {alternative.material_composition}",
                f"Certifications: {', '.join(alternative.certifications)}",
                f"Sustainable advantages: {', '.join(alternative.sustainable_advantages)}",
            ]
        )
        with st.spinner(f"Scoring alternative {alternative.product_name}..."):
            scores.append(
                run_assessment(
                    st.session_state.results[index]["category"],
                    alternative.product_name,
                    evidence,
                    [],
                )
            )
    st.session_state.recommendations[index] = recommendation
    st.session_state.alternative_scores[index] = scores


init_state()
with st.sidebar:
    st.markdown("### Material Intelligence")
    st.caption("Green-score-3000 product workflow")
    if st.button("Start over", use_container_width=True):
        reset()

st.markdown(
    '<div class="mi-hero"><span class="mi-pill">GREEN-SCORE-3000 · Product workflow</span>'
    "<h1>Material Intelligence</h1>"
    "<p>Upload your product list, verify the details, compare ECO-SCORES, "
    "and choose sustainable alternatives in one guided workflow.</p></div>",
    unsafe_allow_html=True,
)
step_header(st.session_state.wizard_step)

if st.session_state.wizard_step == 0:
    st.markdown("## 1. Import project products")
    st.write(
        "Upload one or more CSV, TXT, or Excel spreadsheets. Each row represents one product. "
        "Use columns for name, category, link, amount, and units."
    )
    st.markdown("**Example product list file:**")
    st.code(
        """name,category,link,amount,units
Eco Recycled Fabric,Textile,https://example.com/fabric,10,m2
Acoustic Wool Panel,Acoustic,https://example.com/acoustic,24,pcs
Modular LED Luminaire,Lighting,https://example.com/lighting,8,pcs""",
        language="csv",
    )
    st.download_button(
        "Download CSV template",
        data=(
            "name,category,link,amount,units\n"
            "Product name,Textile,https://example.com/product,1,pcs\n"
        ),
        file_name="green-score-3000-product-template.csv",
        mime="text/csv",
    )
    uploaded_files = st.file_uploader(
        "Product list files",
        type=["csv", "txt", "xlsx"],
        accept_multiple_files=True,
        help="You can select multiple product-list files. Their rows will be combined.",
    )
    if uploaded_files and st.button("Load products", type="primary"):
        try:
            products = []
            for uploaded_file in uploaded_files:
                products.extend(parse_product_file(uploaded_file))
            if not products:
                st.error("No product rows were found. Add at least one product row.")
            else:
                st.session_state.products = products
                st.session_state.wizard_step = 1
                st.rerun()
        except (ValueError, KeyError, zipfile.BadZipFile) as exc:
            st.error(f"Could not read the product list: {exc}")
    st.info(
        "A header row is recommended in every file. TXT files may be comma-, tab-, semicolon-, or pipe-separated. "
        "Product documentation is attached to each row on the next step."
    )

elif st.session_state.wizard_step == 1:
    st.markdown("## 2. Verify extracted products")
    st.write("Correct values and assign the appropriate category to each product before scoring.")
    if st.button("← Back to import", key="back_to_import"):
        go_to_step(0)
    edited = []
    header = st.columns([2, 2, 3, 1, 1, 2])
    for column, label in zip(
        header,
        ["Product name", "Category", "Specification link", "Amount", "Units", "Documentation"],
    ):
        column.caption(label)
    for index, product in enumerate(st.session_state.products):
        columns = st.columns([2, 2, 3, 1, 1, 2])
        raw_category = str(product.get("category", "")).strip().lower()
        category_options = list(CATEGORIES)
        category = next(
            (key for key, details in CATEGORIES.items()
             if raw_category in {key.lower(), details["label"].lower()}),
            category_options[0],
        )
        edited.append(
            {
                "name": columns[0].text_input(
                    "Product name",
                    value=product.get("name", ""),
                    key=f"verify_name_{index}",
                    label_visibility="collapsed",
                ),
                "category": columns[1].selectbox(
                    "Category",
                    category_options,
                    index=category_options.index(category),
                    format_func=lambda key: CATEGORIES[key]["label"],
                    key=f"verify_category_{index}",
                    label_visibility="collapsed",
                ),
                "link": columns[2].text_input(
                    "Specification link",
                    value=product.get("link", ""),
                    key=f"verify_link_{index}",
                    label_visibility="collapsed",
                ),
                "amount": columns[3].text_input(
                    "Amount",
                    value=product.get("amount", ""),
                    key=f"verify_amount_{index}",
                    label_visibility="collapsed",
                ),
                "units": columns[4].text_input(
                    "Units",
                    value=product.get("units", ""),
                    key=f"verify_units_{index}",
                    label_visibility="collapsed",
                ),
                "documents": columns[5].file_uploader(
                    "Product documentation",
                    type=["pdf", "docx"],
                    accept_multiple_files=True,
                    key=f"verify_documents_{index}",
                    label_visibility="collapsed",
                    help="Only these documents will be used to score this product.",
                ),
            }
        )
    available_products = [
        str(row.get("name", "")).strip() for row in edited if str(row.get("name", "")).strip()
    ]
    score_selection = st.multiselect(
        "Products to score",
        list(range(len(available_products))),
        default=list(range(len(available_products))),
        format_func=lambda index: available_products[index],
        key="score_selection",
        help="Select one or more products. Leave all products selected to score the complete list.",
    )
    if st.button("Continue to scoring", type="primary"):
        products = [dict(row) for row in edited if str(row.get("name", "")).strip()]
        if not products:
            st.error("Add at least one product with a name.")
        elif not score_selection:
            st.error("Select at least one product to score.")
        elif score_selection:
            st.session_state.products = [
                product for index, product in enumerate(products) if index in score_selection
            ]
            st.session_state.source_products = products
            st.session_state.wizard_step = 2
            st.rerun()
        else:
            st.session_state.products = products
            st.session_state.source_products = products
            st.session_state.wizard_step = 2
            st.rerun()

elif st.session_state.wizard_step == 2:
    st.markdown("## 3. Score the product list")
    st.write("Each product is assessed against the existing ECO-SCORE questionnaire.")
    if st.button("← Back to verification", key="back_to_verification"):
        go_to_step(1)
    if not os.getenv("GEMINI_API_KEY"):
        st.error("`GEMINI_API_KEY` is missing. Add it to your environment or `.env` before scoring.")
    if not st.session_state.results and st.button(
        "Score all products", type="primary", disabled=not os.getenv("GEMINI_API_KEY")
    ):
        progress = st.progress(0)
        results = []
        for index, product in enumerate(st.session_state.products):
            try:
                with st.status(f"Scoring {product_label(product)}", expanded=False):
                    result = run_assessment(
                        product["category"],
                        product_label(product),
                        product_notes(product),
                        product.get("documents", []),
                    )
            except Exception as exc:
                st.error(f"Scoring failed for {product_label(product)}: {exc}")
                st.stop()
            result["link"] = product.get("link", "")
            result["amount"] = product.get("amount", "")
            result["units"] = product.get("units", "")
            results.append(result)
            progress.progress((index + 1) / len(st.session_state.products))
        st.session_state.results = results
        st.session_state.final_products = [
            {**product, "selected_result": result, "selected_option": product_label(product)}
            for product, result in zip(st.session_state.products, results)
        ]
        st.rerun()
    if st.session_state.results:
        overall = weighted_overall(st.session_state.final_products)
        render_overall_score(overall)
        for result in st.session_state.results:
            render_score(result)
        st.markdown("### Export without substitute recommendations")
        export_columns = st.columns(2)
        with export_columns[0]:
            st.download_button(
                "Download current product list",
                products_to_csv(st.session_state.final_products),
                "green-score-3000-products.csv",
                "text/csv",
                use_container_width=True,
            )
        with export_columns[1]:
            st.download_button(
                "Download current report",
                report_to_csv(st.session_state.final_products, overall),
                "green-score-3000-report.csv",
                "text/csv",
                use_container_width=True,
            )
        if st.button("Continue to substitute recommendations", type="primary"):
            st.session_state.wizard_step = 3
            st.rerun()

elif st.session_state.wizard_step == 3:
    st.markdown("## 4. Select substitute recommendations")
    st.write("Keep products you are happy with, or request alternatives only for selected products.")
    if st.button("← Back to scoring", key="back_to_scoring"):
        go_to_step(2)
    selected = []
    for index, result in enumerate(st.session_state.results):
        if st.checkbox(f"Find alternatives for **{result['product']}** ({result['percentage']:.0f}%)", key=f"recommend_{index}"):
            selected.append(index)
    if not selected:
        st.caption("No products selected. Continue to export the original list.")
    if st.button("Find alternatives", type="primary"):
        if not selected:
            st.session_state.wizard_step = 4
            st.rerun()
        for index in selected:
            result = st.session_state.results[index]
            with st.spinner(f"Searching alternatives for {result['product']}..."):
                recommendation = get_sustainable_recommendations(
                    result["category"], result
                )
                score_recommendation_alternatives(index, recommendation)
        st.session_state.wizard_step = 4
        st.rerun()

elif st.session_state.wizard_step == 4:
    st.markdown("## 5. Final selection and export")
    st.write("Choose the original product or one suggested substitute for each row.")
    if st.button("← Back to recommendations", key="back_to_recommendations"):
        go_to_step(3)
    final_products = []
    for index, original in enumerate(st.session_state.products):
        result = st.session_state.results[index]
        recommendation = st.session_state.recommendations.get(index)
        alternative_scores = st.session_state.alternative_scores.get(index, [])
        options = [product_label(original)]
        if recommendation:
            options.extend(alt.product_name for alt in recommendation.alternatives)
        original_col, substitute_col = st.columns(2)
        with original_col:
            st.markdown("**Original product**")
            st.write(f"{product_label(original)} · {original.get('amount', '')} {original.get('units', '')}")
            if original.get("link"):
                st.markdown(f"[Specification]({original['link']})")
            st.caption(f"{result['percentage']:.0f}% · {result['level']}")
        with substitute_col:
            st.markdown("**Suggested substitutes**")
            if recommendation:
                for alternative, alternative_score in zip(
                    recommendation.alternatives, alternative_scores
                ):
                    st.write(
                        f"**{alternative.product_name}** — "
                        f"{alternative_score['percentage']:.0f}% ({alternative_score['level']}) — "
                        f"{alternative.description}"
                    )
            else:
                st.caption("No substitute search requested.")
        choice = st.radio(
            "Final choice",
            options,
            key=f"choice_{index}",
        )
        selected_result = result
        if recommendation and choice != product_label(original):
            alternative_index = next(
                (
                    alt_index
                    for alt_index, alternative in enumerate(recommendation.alternatives)
                    if alternative.product_name == choice
                ),
                None,
            )
            if alternative_index is not None and alternative_index < len(alternative_scores):
                selected_result = alternative_scores[alternative_index]
        final_products.append({**original, "selected_option": choice, "selected_result": selected_result})
        if recommendation:
            st.caption(recommendation.baseline_summary)
            refinement = st.text_area(
                "Refine search for this product",
                placeholder="For example: only products with an EPD, at least 80% recycled content, and availability in Europe.",
                key=f"refinement_{index}",
            )
            if st.button("Refine alternatives", key=f"refine_{index}"):
                if not refinement.strip():
                    st.warning("Enter at least one search requirement.")
                else:
                    with st.spinner(f"Refining alternatives for {product_label(original)}..."):
                        refined = get_sustainable_recommendations(
                            result["category"],
                            result,
                            project_priorities=refinement,
                        )
                    score_recommendation_alternatives(index, refined)
                    st.rerun()
    st.session_state.final_products = final_products
    overall = weighted_overall(final_products)
    st.markdown(f"### Final overall score: {overall['percentage']:.0f}% · {overall['level']}")
    st.download_button(
        "Download final product list",
        products_to_csv(final_products),
        "green-score-3000-final-products.csv",
        "text/csv",
        type="primary",
    )
    st.download_button(
        "Download green-score-3000 report",
        report_to_csv(final_products, overall),
        "green-score-3000-report.csv",
        "text/csv",
    )
