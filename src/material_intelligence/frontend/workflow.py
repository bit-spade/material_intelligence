import csv
import io
import json
import math
import re
import zipfile
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

from material_intelligence.api.schemas.ecoscore import ExtractedProduct
from material_intelligence.engine.ecoscore_calculator import CATEGORY_NAMES, load_reference


ASSETS = Path(__file__).with_name("assets")
PRODUCT_GROUPS = load_reference()["product_groups"]

FIELD_ALIASES = {
    "name": {"name", "product", "product name", "item", "produkt", "nazwa", "nazwa produktu"},
    "product_group": {"category", "type", "product category", "material category", "product group", "kategoria"},
    "url": {"link", "url", "specification", "specification link", "spec link"},
    "quantity": {"amount", "quantity", "qty", "count", "volume", "ilość", "liczba"},
    "unit": {"unit", "units", "uom", "measurement unit", "jednostka"},
    "subtype": {"subtype", "podtyp"},
    "notes": {"notes", "evidence", "uwagi"},
}
GROUP_ALIASES = {name.casefold(): name for name in PRODUCT_GROUPS} | {
    "textile": "Home textiles",
    "textile_product": "Home textiles",
    "acoustic": "Wall panels and acoustic slats",
    "acoustic_product": "Wall panels and acoustic slats",
    "lighting_product": "Lighting",
}
UNIT_ALIASES = {
    "item": "item", "items": "item", "pcs": "item", "pc": "item", "pieces": "item", "szt": "item",
    "m²": "m2", "m2": "m2", "m^2": "m2", "sqm": "m2",
}


def _normalise_header(value: str) -> str:
    return re.sub(r"[\s_-]+", " ", value.strip().casefold())


def _map_headers(headers: list[str]) -> dict[str, int]:
    mapping = {}
    for index, header in enumerate(headers):
        normalised = _normalise_header(header)
        for field, aliases in FIELD_ALIASES.items():
            if normalised in aliases:
                mapping[field] = index
                break
    return mapping


def _rows_to_products(rows: list[list[str]]) -> list[dict[str, str]]:
    if not rows:
        return []
    headers = rows[0]
    mapping = _map_headers(headers)
    start = 1 if "name" in mapping else 0
    if not start:
        mapping = {"name": 0, "url": 1, "quantity": 2, "unit": 3}

    products = []
    for row in rows[start:]:
        values = {
            field: row[index].strip() if index < len(row) else ""
            for field, index in mapping.items()
        }
        if any(values.values()):
            products.append(values)
    return products


def _xlsx_rows(uploaded_file) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(uploaded_file.getvalue())) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            shared = [
                "".join(node.itertext())
                for node in root.findall("x:si", ns)
            ]
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
        relationships = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in rels.findall("r:Relationship", rel_ns)
        }
        main_ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        first_sheet = workbook.find("x:sheets/x:sheet", main_ns)
        if first_sheet is None:
            return []
        relation_id = first_sheet.attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        target = relationships[relation_id]
        target = target.lstrip("/")
        sheet_path = target if target.startswith("xl/") else f"xl/{target}"
        sheet = ElementTree.fromstring(archive.read(sheet_path))
        rows = []
        for row in sheet.findall(".//x:sheetData/x:row", main_ns):
            values = []
            for cell in row.findall("x:c", main_ns):
                column = 0
                for letter in cell.attrib.get("r", ""):
                    if not letter.isalpha():
                        break
                    column = 26 * column + ord(letter.upper()) - ord("A") + 1
                values.extend([""] * max(0, column - 1 - len(values)))
                value = cell.find("x:v", main_ns)
                raw = "" if value is None else value.text or ""
                if cell.attrib.get("t") == "s" and raw:
                    raw = shared[int(raw)]
                elif cell.attrib.get("t") == "inlineStr":
                    raw = "".join(node.text or "" for node in cell.findall(".//x:t", main_ns))
                values.append(raw)
            rows.append(values)
        return rows


def parse_product_file(uploaded_file) -> dict:
    """Parse a project JSON or the first sheet of a material list."""
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".json":
        project = json.loads(uploaded_file.getvalue().decode("utf-8-sig"))
        if not isinstance(project, dict) or not isinstance(project.get("products"), list):
            raise ValueError("A project JSON must contain a products list.")
        if not all(isinstance(product, dict) for product in project["products"]):
            raise ValueError("Each JSON product must be an object.")
        return project
    if suffix == ".xlsx":
        rows = _xlsx_rows(uploaded_file)
    else:
        text = uploaded_file.getvalue().decode("utf-8-sig")
        sample = text[:4096]
        if not sample.strip():
            return {"products": []}
        if "\t" in sample:
            delimiter = "\t"
        else:
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=",;|").delimiter
            except csv.Error:
                delimiter = ","
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    return {"products": _rows_to_products(rows)}


def editable_product(source: dict) -> dict:
    group = str(source.get("product_group", source.get("category", "")) or "").strip()
    quantity = source.get("quantity", source.get("amount"))
    return {
        "id": uuid4().hex,
        "name": str(source.get("name") or ""),
        "product_group": GROUP_ALIASES.get(group.casefold()),
        "url": str(source.get("url", source.get("link", "")) or ""),
        "quantity": "1" if quantity in (None, "") else str(quantity),
        "unit": str(source.get("unit", source.get("units", "")) or ""),
        "subtype": str(source.get("subtype") or "") or None,
        "notes": str(source.get("notes") or ""),
        "documents": [],
        "source": source if "attributes" in source or "category_scores" in source else None,
    }


def source_matches(row: dict) -> bool:
    source = row["source"]
    if source is None:
        return False
    return all((source.get(key) or "") == (row.get(key) or "").strip()
               for key in ("name", "url", "product_group", "subtype"))


def positive_quantity(value) -> float:
    try:
        number = float(str(value).strip().replace(",", "."))
    except ValueError:
        number = 0
    if number <= 0 or not math.isfinite(number):
        raise ValueError("Enter a positive numeric quantity.")
    return number


def scoring_product(row: dict) -> dict:
    name = row["name"].strip()
    if not name:
        raise ValueError("Enter a material name.")
    group = row["product_group"]
    if group not in PRODUCT_GROUPS:
        raise ValueError("Choose a product group.")
    defaults = PRODUCT_GROUPS[group]
    subtype = row["subtype"] or None
    if subtype is not None and subtype not in defaults.get("subtypes", {}):
        raise ValueError("Choose a subtype for this product group.")
    expected_unit = defaults["functional_unit"]
    raw_unit = row["unit"].strip().casefold().rstrip(".")
    if raw_unit and UNIT_ALIASES.get(raw_unit) != expected_unit:
        raise ValueError(f"{group} must be measured in {display_unit(expected_unit)}.")
    product = {
        "id": row["id"], "name": name, "product_group": group, "subtype": subtype,
        "url": row["url"].strip(), "quantity": positive_quantity(row["quantity"]), "unit": expected_unit,
    }
    if row["documents"] or row["notes"].strip() or not source_matches(row):
        return product

    source = row["source"]
    if "attributes" in source:
        try:
            evidence = ExtractedProduct.model_validate(source).model_dump(by_alias=True)
        except ValueError as exc:
            raise ValueError("Imported attributes do not match the EcoScore schema.") from exc
        return {**product, **evidence}

    try:
        scores = {
            code: None if source["category_scores"].get(code) is None else float(source["category_scores"][code])
            for code in CATEGORY_NAMES
        }
        if not any(score is not None for score in scores.values()) or any(
            score is not None and not 0 <= score <= 100 for score in scores.values()
        ):
            raise ValueError
        original_quantity = positive_quantity(source.get("quantity", 1))
        mass = positive_quantity(source["mass_kg_total"]) * (product["quantity"] / original_quantity)
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        raise ValueError("Imported scores need categories between 0 and 100 and a positive mass.") from exc
    return {**product, "category_scores": scores, "mass_kg_total": mass}


def display_unit(unit: str) -> str:
    return "m²" if unit == "m2" else unit


def _csv_text(value: str) -> str:
    # Spreadsheet apps interpret formula prefixes in untrusted names and notes.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def products_to_csv(products: list[dict]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "category", "link", "amount", "units", "subtype"])
    for product in products:
        writer.writerow([
            _csv_text(product["name"]), product["product_group"], _csv_text(product.get("url", "")),
            product["quantity"], product["unit"], product.get("subtype"),
        ])
    return output.getvalue()


def report_to_csv(report: dict, warnings: list[str]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Material Intelligence EcoScore report", _csv_text(report["project"])])
    writer.writerow(["Project EcoScore (0–100)", report["ecoscore"], report["colour"]])
    writer.writerow(["Total material mass (kg)", report["total_mass_kg"]])
    writer.writerow(["Climate footprint (kg CO2e per year)", report["footprint_kg_co2e_per_year"]])
    for code, result in report["categories"].items():
        writer.writerow([CATEGORY_NAMES[code], result["score"] if result else None])
    for warning in sorted(set(report["warnings"] + warnings)):
        writer.writerow(["Note", _csv_text(warning)])
    writer.writerow([])
    writer.writerow([
        "Product", "Product group", "Quantity", "Unit", "EcoScore (0–100)", "Colour", "Capped",
        "Mass (kg)", "Mass source", "Mass share", "Climate footprint (kg CO2e per year)",
        *CATEGORY_NAMES.values(), "Verified questions", "Declared questions", "Missing questions",
    ])
    for product in report["products"]:
        writer.writerow([
            _csv_text(product["name"]), product["product_group"], product["quantity"], product["unit"],
            product["ecoscore"], product["colour"], product["capped"], product["mass_kg_total"],
            product["mass_source"], product["mass_share"], product["footprint_kg_co2e_per_year"],
            *(category["score"] if category else None for category in product["categories"].values()),
            *(product.get("verification", {}).get(level) for level in ("verified", "declared", "missing")),
        ])
    return output.getvalue()
