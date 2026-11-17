import base64
import json
import zipfile
from html import escape
from xml.etree.ElementTree import ParseError

import streamlit as st
from dotenv import load_dotenv

from material_intelligence.frontend.views.project_assessment import assess, show_assessment, show_export
from material_intelligence.frontend.views.project_vision import room_image_materials
from material_intelligence.frontend.workflow import (
    ASSETS,
    PRODUCT_GROUPS,
    display_unit,
    editable_product,
    parse_product_file,
    scoring_product,
    source_matches,
)

STEPS = ("Upload materials", "Verify list", "Assess & improve", "Export")
TEMPLATE = "name,category,link,amount,units\nExample floor,Wood flooring,,18,m2\nExample pendant,Lighting,,2,item\n"


def go_to_step(step: int) -> None:
    st.session_state.step = step


def start_project(rows: list[dict], name: str = "", implied: bool = False) -> None:
    st.session_state.materials = [editable_product(row) for row in rows]
    st.session_state.project_name = name or "Untitled project"
    st.session_state.include_implied = implied
    st.session_state.pop("assessment", None)
    go_to_step(1)
    st.rerun()


def steps_html(current: int) -> str:
    items = []
    for index, label in enumerate(STEPS):
        active = ' aria-current="step"' if index == current else ""
        completed = " completed" if index < current else ""
        items.append(
            f'<li class="mi-step{completed}"{active}><span aria-hidden="true">{index + 1}</span> {escape(label)}</li>'
        )
    return '<ol class="mi-steps" aria-label="Project progress">' + "".join(items) + "</ol>"


def welcome() -> None:
    hero = ASSETS / "interior.webp"
    photo = ""
    if hero.exists():
        data = base64.b64encode(hero.read_bytes()).decode("ascii")
        photo = f'<img src="data:image/webp;base64,{data}" alt="" />'
    st.html(
        '<section class="mi-hero"><div class="mi-hero-copy">'
        '<p class="mi-eyebrow">EcoScore for interiors</p>'
        '<h1>Material Intelligence</h1>'
        '<p>Assess the environmental impact of your interior materials and compare alternatives.</p>'
        f'</div>{photo}</section>'
    )
    with st.container(key="welcome_panel", border=True):
        st.html(steps_html(0))
        import_column, preview = st.columns([1.45, 1], gap="large")
        with import_column:
            upload_tab, image_tab = st.tabs(["Upload a list", "Scan a room image"])
            with upload_tab:
                with st.container(key="upload_materials"):
                    st.subheader("Upload your material list")
                    st.caption("Use a spreadsheet, a delimited text file, or EcoScore project JSON.")
                    source_files = st.file_uploader(
                        "Material list files", type=["xlsx", "csv", "txt", "json"],
                        accept_multiple_files=True, label_visibility="collapsed",
                    )
                    if st.button("Review uploaded materials", disabled=not source_files, type="primary"):
                        try:
                            projects = [parse_product_file(file) for file in source_files]
                            rows = [row for project in projects for row in project["products"]]
                            if not rows:
                                raise ValueError("Add at least one material row.")
                        except (ValueError, KeyError, IndexError, zipfile.BadZipFile, ParseError) as exc:
                            st.error(f"Could not read the material list. {exc}")
                        else:
                            name = projects[0].get("name") or source_files[0].name.rsplit(".", 1)[0]
                            start_project(rows, str(name), any(project.get("add_implied_products") is True for project in projects))
                st.download_button("Download CSV template", TEMPLATE, "material-list-template.csv", "text/csv")
            with image_tab:
                rows = room_image_materials()
                if rows:
                    start_project(rows)
            manual, sample = st.columns(2)
            if manual.button("Add materials manually", icon=":material/add_circle:", width="stretch"):
                start_project([{}])
            if sample.button("Try a sample project", icon=":material/science:", width="stretch"):
                project = json.loads((ASSETS / "example_project.json").read_text(encoding="utf-8"))
                start_project(project["products"], "Example flat · living room and bathroom", project["add_implied_products"])
            if st.session_state.get("materials"):
                st.button("Resume project", on_click=go_to_step, args=(1,))
        with preview:
            st.html(
                '<section class="mi-preview"><h2>What you’ll get</h2>'
                '<div><span aria-hidden="true">◎</span><section><h3>Project EcoScore</h3>'
                '<p>See how the materials in your project perform across five categories.</p></section></div>'
                '<div><span aria-hidden="true">▤</span><section><h3>Material-by-material results</h3>'
                '<p>Review the evidence and see which choices have the largest impact.</p></section></div>'
                '<div><span aria-hidden="true">⇄</span><section><h3>Alternative materials</h3>'
                '<p>Compare replacements and see how they change your project score.</p></section></div></section>'
            )


def store_documents(row: dict, key: str) -> None:
    row["documents"] = list(st.session_state[key])


def clear_documents(row: dict) -> None:
    row["documents"] = []
    row["upload_version"] = row.get("upload_version", 0) + 1


def material_editor(row: dict) -> bool:
    key = f"verify_{row['id']}"
    with st.container(border=True):
        name, group, quantity, unit = st.columns([3, 3, 1, 1.35])
        row["name"] = name.text_input("Product name", row["name"], key=f"{key}_name")
        row["product_group"] = group.selectbox(
            "Product group", list(PRODUCT_GROUPS), index=None if not row["product_group"] else
            list(PRODUCT_GROUPS).index(row["product_group"]), key=f"{key}_group",
            placeholder="Select product group",
        )
        defaults = PRODUCT_GROUPS.get(row["product_group"], {})
        expected_unit = display_unit(defaults.get("functional_unit", ""))
        row["quantity"] = quantity.text_input("Quantity", row["quantity"], key=f"{key}_quantity")
        row["unit"] = unit.text_input("Unit", row["unit"], key=f"{key}_unit", placeholder=expected_unit)
        subtypes = defaults.get("subtypes", {})
        if subtypes:
            row["subtype"] = st.selectbox(
                "Subtype", list(subtypes),
                index=list(subtypes).index(row["subtype"]) if row["subtype"] in subtypes else None,
                key=f"{key}_{row['product_group']}_subtype",
                placeholder="Use group default",
                format_func=lambda value: value.replace("_", " ").capitalize(),
            )
        else:
            row["subtype"] = None
        with st.expander("Specification and documents"):
            row["url"] = st.text_input("Specification URL", row["url"], key=f"{key}_url")
            row["notes"] = st.text_area(
                "Evidence notes", row["notes"], key=f"{key}_notes",
                placeholder="Paste relevant specifications, such as net mass, composition or a certificate number.",
            )
            upload_key = f"{key}_documents_{row.get('upload_version', 0)}"
            st.file_uploader(
                "Product documentation", type=["pdf", "docx", "txt"], accept_multiple_files=True,
                key=upload_key, on_change=store_documents, args=(row, upload_key),
            )
            if row["documents"]:
                st.text("Attached · " + ", ".join(document.name for document in row["documents"]))
                st.button("Clear documents", key=f"{key}_clear", on_click=clear_documents, args=(row,))
            if source_matches(row) and not (row["notes"].strip() or row["documents"]):
                st.caption("This product includes pre-extracted evidence or scores.")
            return st.button("Remove material", key=f"{key}_remove", icon=":material/delete_outline:")


def verify() -> None:
    st.subheader("Verify your materials")
    st.caption("Check each product group and quantity. A blank unit uses the product group’s unit.")
    project_name = st.text_input("Project name", key="project_name")
    materials = st.session_state.materials
    removed = [row for row in materials if material_editor(row)]
    if removed:
        st.session_state.materials = [row for row in materials if row not in removed]
        st.rerun()
    if st.button("Add a material", icon=":material/add_circle:"):
        materials.append(editable_product({}))
        st.rerun()
    implied = st.checkbox("Estimate tile adhesive, grout and underlay where applicable", key="include_implied")
    back, calculate = st.columns(2)
    back.button("Back to upload", on_click=go_to_step, args=(0,))
    if not calculate.button("Calculate project score", disabled=not materials, type="primary"):
        return
    products = []
    for index, row in enumerate(materials, start=1):
        try:
            products.append(scoring_product(row))
        except ValueError as exc:
            st.error(f"Material {index} ({row['name'] or 'unnamed'}) · {exc}")
    if len(products) == len(materials):
        try:
            st.session_state.assessment = assess(project_name.strip() or "Untitled project", products, materials, implied)
        except ValueError as exc:
            st.error(str(exc))
        else:
            go_to_step(2)
            st.rerun()


load_dotenv()
st.set_page_config(page_title="Material Intelligence · EcoScore", layout="wide", initial_sidebar_state="auto")
st.html(ASSETS / "project.css")
st.session_state.setdefault("step", 0)

with st.sidebar:
    st.html('<div class="mi-brand">eco-score<br>3000</div>')
    st.button("New project", icon=":material/add_circle:", type="primary", width="stretch",
              on_click=st.session_state.clear)
    with st.expander("Help & methodology"):
        st.write(
            "EcoScore combines five environmental category scores on a 0–100 scale. "
            "Each material contributes to the project according to its mass. "
            "A category in the red band caps the overall score at 66."
        )
        st.caption("The current reference factors are provisional.")

step = st.session_state.step
if step == 0:
    welcome()
else:
    if step >= 2:
        st.html(f'<h1 class="mi-project-title">{escape(st.session_state.assessment["project"]["name"])}</h1>')
    st.html(steps_html(step))
    if step == 1:
        verify()
    elif step == 2:
        show_assessment(st.session_state.assessment, go_to_step)
    else:
        show_export(st.session_state.assessment, go_to_step)
