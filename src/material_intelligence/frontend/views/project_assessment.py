import json
import os
from html import escape

import streamlit as st

from material_intelligence.api.ecoscore import EvidenceError, extract_product, suggest_alternatives
from material_intelligence.engine.ecoscore_calculator import (
    CATEGORY_NAMES,
    EcoscoreCalculator,
    level,
    load_reference,
)
from material_intelligence.frontend.workflow import ASSETS, display_unit, products_to_csv, report_to_csv


def _replacement_fields(product: dict) -> dict:
    return {key: product[key] for key in ("id", "product_group", "subtype", "quantity", "unit")}


def assess(name: str, products: list[dict], rows: list[dict], implied: bool) -> dict:
    warnings = {}
    alternative_data = json.loads((ASSETS / "sample_alternatives.json").read_text(encoding="utf-8"))
    sample_products = json.loads((ASSETS / "example_project.json").read_text(encoding="utf-8"))["products"]
    fixture_urls = {row["url"]: (row["id"], row["product_group"]) for row in sample_products}
    project = {"name": name, "products": [], "add_implied_products": implied}
    alternatives = {}
    calculator = EcoscoreCalculator(load_reference())
    with st.status("Assessing the material list…") as status:
        for product, row in zip(products, rows, strict=True):
            st.text(product["name"])
            if "attributes" not in product and "category_scores" not in product:
                try:
                    product, notes = extract_product(product, documents=row["documents"], notes=row["notes"])
                except EvidenceError as exc:
                    notes = [f"{exc} Group defaults were used."]
                if notes:
                    warnings[product["id"]] = notes
            project["products"].append(product)
            sample_id, sample_group = fixture_urls.get(product["url"], (None, None))
            candidates = alternative_data.get(sample_id, [])
            if candidates and sample_group == product["product_group"]:
                alternatives[product["id"]] = _improved_options(
                    product, calculator.score_product(product),
                    [{**_replacement_fields(product), **candidate} for candidate in candidates],
                )
        baseline = calculator.score_project(project)
        status.update(label="Material list assessed", state="complete")
    return {
        "project": project, "baseline": baseline, "warnings": warnings,
        "alternatives": alternatives, "chosen": {}, "shortlist": set(),
    }


def _improved_options(original: dict, baseline: dict, candidates: list[dict]) -> dict:
    calculator = EcoscoreCalculator(load_reference())
    options = {}
    for candidate in candidates:
        if candidate["url"] == original["url"]:
            continue
        score = calculator.score_product(candidate)
        if score["ecoscore"] > baseline["ecoscore"]:
            options[candidate["url"]] = {"product": candidate, "score": score}
    return options


def selected_project(state: dict) -> tuple[dict, dict, list[str]]:
    project = state["project"]
    products = []
    warnings = []
    for original in project["products"]:
        product_id = original["id"]
        choice = state["alternatives"].get(product_id, {}).get(state["chosen"].get(product_id))
        products.append(choice["product"] if choice else original)
        if not choice:
            warnings.extend(f"{original['name']} — {warning}" for warning in state["warnings"].get(product_id, []))
    selected = {**project, "products": products}
    report = EcoscoreCalculator(load_reference()).score_project(selected) if state["chosen"] else state["baseline"]
    return selected, report, warnings


def _number(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _project_summary(baseline: dict, report: dict, swap_count: int) -> None:
    change = report["ecoscore"] - baseline["ecoscore"]
    delta = f"{change:+.2f} points" if change else "No score change"
    swap_label = "swap" if swap_count == 1 else "swaps"
    projection = (
        f'<span class="mi-delta">{delta} with {swap_count} {swap_label}</span>'
        f'<p>Projected score <b>{_number(report["ecoscore"])}/100</b></p>' if swap_count else ""
    )
    footprint = report["footprint_kg_co2e_per_year"]
    footprint_label = f'{_number(footprint)} kg CO₂e/year' if footprint is not None else "Unavailable"
    categories = []
    for code, name in CATEGORY_NAMES.items():
        result = report["categories"][code]
        value = _number(result["score"]) if result else "N/A"
        bar = (
            f'<div class="mi-track {result["colour"]}"><i style="--score: {result["score"]}%"></i></div>'
            if result else ""
        )
        categories.append(f'<div class="mi-category"><div><span>{name}</span><b>{value}</b></div>{bar}</div>')
    st.html(
        f'<section class="mi-impact"><h2>Your project’s environmental impact</h2>'
        f'<div class="mi-impact-grid"><div class="mi-score-area">'
        f'<div class="mi-score-ring {baseline["colour"]}" style="--score:{baseline["ecoscore"]}%">'
        f'<div><strong>{_number(baseline["ecoscore"])}</strong><small> / 100</small></div></div>'
        f'<b>Baseline project score</b><p>Weighted by {_number(baseline["total_mass_kg"])} kg of materials</p>'
        f'{projection}</div><div class="mi-categories">{"".join(categories)}'
        f'<div class="mi-footprint">Annual climate footprint <b>{footprint_label}</b></div>'
        '</div></div></section>'
    )


def _score_details(original: dict, score: dict) -> None:
    with st.expander("Evidence and score details"):
        mass = f"{_number(score['mass_kg_total'])} kg · {score['mass_share']:.1%} of baseline project mass"
        st.caption(f"{mass} · {score['mass_source']}")
        if score["capped"]:
            st.caption("A category in the red band capped the EcoScore at 66.")
        questions = score.get("questions")
        if questions:
            evidence_label = {0: "Default", 1: "Declared", 2: "Verified", None: "N/A"}
            st.dataframe([
                {
                    "Question": key,
                    "Score": item["score"],
                    "Evidence": evidence_label[item["level"]],
                    "Basis": item["note"],
                }
                for key, item in questions.items()
            ], hide_index=True)
        for key, value in original.get("attributes", {}).items():
            if isinstance(value, dict) and value.get("text"):
                st.text(f"{key.split('_', 1)[0]} · {value['text']}")
        url = original.get("url", "")
        if url.startswith(("https://", "http://")):
            st.link_button("Open specification", url)


def _search_alternatives(state: dict, priorities: str) -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.info("The example project includes sample alternatives. Live sourcing requires GEMINI_API_KEY.")
        return
    scores = {score["id"]: score for score in state["baseline"]["products"]}
    with st.status("Checking alternative product specifications…") as status:
        for original in state["project"]["products"]:
            product_id = original["id"]
            if product_id not in state["shortlist"]:
                continue
            score = scores[product_id]
            st.text(original["name"])
            try:
                matches = suggest_alternatives(original, score, priorities, api_key)
            except EvidenceError as exc:
                st.warning(str(exc))
                continue
            candidates = []
            for match in matches:
                if match.url == original["url"] or not match.url.startswith(("https://", "http://")):
                    continue
                try:
                    candidate, _ = extract_product(
                        {**_replacement_fields(original), "name": match.name, "url": match.url}, api_key=api_key
                    )
                except EvidenceError:
                    continue
                if any(level(value) for value in candidate.get("attributes", {}).values()):
                    candidates.append(candidate)
            better = _improved_options(original, score, candidates)
            state["alternatives"].setdefault(product_id, {}).update(better)
            if not better:
                st.caption("No higher-scoring option with readable evidence was found.")
        status.update(label="Alternative search finished", state="complete")


def _shortlist_changed(state: dict, product_id: str, key: str) -> None:
    if st.session_state[key]:
        state["shortlist"].add(product_id)
    else:
        state["shortlist"].discard(product_id)


def _choose_alternative(state: dict, product_id: str, key: str) -> None:
    url = st.session_state[key]
    if url:
        state["chosen"][product_id] = url
    else:
        state["chosen"].pop(product_id, None)


def _material_row(state: dict, product: dict, score: dict, hotspot_rank: int) -> None:
    product_id = product["id"]
    key = f"shortlist_{product_id}"
    options = state["alternatives"].get(product_id, {})
    with st.container(key=f"material_compare_{product_id}", border=True):
        check, current, proposed = st.columns([0.35, 3, 3], vertical_alignment="top")
        check.checkbox(
            f"Shortlist {product['name']}", value=product_id in state["shortlist"],
            key=key, label_visibility="collapsed",
            on_change=_shortlist_changed, args=(state, product_id, key),
        )
        with current:
            st.html(
                f'<div class="mi-product"><div><b>{escape(product["name"])}</b>'
                f'<p>{escape(product["product_group"])} · {_number(product["quantity"])} {display_unit(product["unit"])}</p>'
                f'</div><span class="mi-score-badge {score["colour"]}">{_number(score["ecoscore"])}/100</span></div>'
            )
            if hotspot_rank <= 3:
                st.caption(f"Hotspot {hotspot_rank} · {score['mass_share']:.1%} of baseline mass")
            _score_details(product, score)
        with proposed:
            if not options:
                st.caption("Shortlist this material to search for alternatives.")
                return
            urls = [None, *sorted(options, key=lambda url: options[url]["score"]["ecoscore"], reverse=True)]
            choice_key = f"alternative_{product_id}"
            chosen = st.selectbox(
                f"Replacement for {product['name']}", urls, index=urls.index(state["chosen"].get(product_id)),
                format_func=lambda url: options[url]["product"]["name"] if url else "Keep current product",
                key=choice_key, on_change=_choose_alternative, args=(state, product_id, choice_key),
                label_visibility="collapsed",
            )
            candidate = options[chosen or urls[1]]
            alt_score = candidate["score"]
            delta = alt_score["ecoscore"] - score["ecoscore"]
            label = "Alternative EcoScore" if chosen else escape(candidate["product"]["name"])
            st.html(
                f'<div class="mi-product"><b>{label}</b>'
                f'<span class="mi-score-badge {alt_score["colour"]}">{_number(alt_score["ecoscore"])}/100</span></div>'
            )
            st.caption(f"+{_number(delta)} product points")
            st.link_button("Open alternative source", candidate["product"]["url"])


def show_assessment(state: dict, go_to_step) -> None:
    baseline = state["baseline"]
    _, report, warnings = selected_project(state)
    _project_summary(baseline, report, len(state["chosen"]))
    if baseline["warnings"] or warnings or report["warnings"]:
        if any("placeholders" in note for note in baseline["warnings"] + report["warnings"]):
            st.caption("Prototype scores use placeholder reference factors and are for testing.")
        with st.expander("Scoring notes"):
            for warning in sorted(set(baseline["warnings"] + report["warnings"] + warnings)):
                st.text(warning)

    with st.container(key="improve_materials", border=True):
        heading, actions = st.columns([3, 2], vertical_alignment="center")
        heading.subheader("Improve your materials")
        heading.caption("Shortlist products to find alternatives. Choose a replacement to update the project score.")
        selected_only = actions.checkbox(f"Show only shortlisted ({len(state['shortlist'])})", key="only_shortlisted")
        find, export = actions.columns(2)
        export.button(
            "Export report", icon=":material/download:", type="primary",
            width="stretch", on_click=go_to_step, args=(3,),
        )
        if find.button(
            "Find alternatives", icon=":material/auto_awesome:", disabled=not state["shortlist"], width="stretch",
        ):
            _search_alternatives(state, st.session_state.get("sourcing_priorities", ""))
        with st.expander("Sourcing preferences"):
            st.text_input("Priorities for replacements", placeholder="Low emissions or easier repair",
                          key="sourcing_priorities")
        products = {product["id"]: product for product in state["project"]["products"]}
        scores = {score["id"]: score for score in baseline["products"]}
        _, current, next_option = st.columns([0.35, 3, 3])
        current.markdown("**Current option**")
        next_option.markdown("**Greener alternative**")
        for rank, hotspot in enumerate(baseline["hotspots"], start=1):
            product_id = hotspot["id"]
            if product_id in products and (not selected_only or product_id in state["shortlist"]):
                _material_row(state, products[product_id], scores[product_id], rank)
        if selected_only and not state["shortlist"]:
            st.info("Shortlist a material to see it here.")
        if any(score["implied"] for score in baseline["products"]):
            with st.expander("Estimated installation materials"):
                for score in report["products"]:
                    if score["implied"]:
                        st.text(f"{score['name']} · {_number(score['mass_kg_total'])} kg")
    st.button("Back to verification", on_click=go_to_step, args=(1,))


def show_export(state: dict, go_to_step) -> None:
    selected, report, warnings = selected_project(state)
    st.subheader("Export your project")
    st.write(
        f"Final EcoScore **{_number(report['ecoscore'])}/100** · "
        f"**{len(selected['products'])}** materials · **{len(state['chosen'])}** replacements"
    )
    if report["warnings"] or warnings:
        st.caption("The score report includes the reference and evidence notes.")
    materials, scores = st.columns(2)
    materials.download_button(
        "Download final material list", products_to_csv(selected["products"]),
        "material-intelligence-materials.csv", "text/csv", icon=":material/download:", type="primary",
    )
    scores.download_button(
        "Download EcoScore report", report_to_csv(report, warnings),
        "material-intelligence-ecoscore.csv", "text/csv", icon=":material/download:",
    )
    st.button("Back to assessment", on_click=go_to_step, args=(2,))
