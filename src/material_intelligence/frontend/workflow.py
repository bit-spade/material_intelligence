import csv
import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree


FIELD_ALIASES = {
    "name": {"name", "product", "product name", "product_name", "item"},
    "category": {"category", "type", "product category", "material category"},
    "link": {"link", "url", "specification", "specification link", "spec link"},
    "amount": {"amount", "quantity", "qty", "count", "volume"},
    "units": {"unit", "units", "uom", "measurement unit"},
}


def _normalise_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().replace("-", " "))


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
    start = 1 if mapping else 0
    if not mapping:
        mapping = {"name": 0}
        if len(headers) > 1:
            mapping["link"] = 1
        if len(headers) > 2:
            mapping["amount"] = 2
        if len(headers) > 3:
            mapping["units"] = 3

    products = []
    for row in rows[start:]:
        values = {
            field: row[index].strip() if index < len(row) else ""
            for field, index in mapping.items()
        }
        if any(values.values()):
            products.append(
                {
                    "name": values.get("name", ""),
                    "category": values.get("category", ""),
                    "link": values.get("link", ""),
                    "amount": values.get("amount", ""),
                    "units": values.get("units", ""),
                }
            )
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
        sheet_path = f"xl/{target}" if not target.startswith("xl/") else target
        sheet = ElementTree.fromstring(archive.read(sheet_path))
        rows = []
        for row in sheet.findall(".//x:sheetData/x:row", main_ns):
            values = []
            for cell in row.findall("x:c", main_ns):
                value = cell.find("x:v", main_ns)
                raw = "" if value is None else value.text or ""
                if cell.attrib.get("t") == "s" and raw:
                    raw = shared[int(raw)]
                values.append(raw)
            rows.append(values)
        return rows


def parse_product_file(uploaded_file) -> list[dict[str, str]]:
    """Parse a CSV, TXT, or XLSX product list into editable product records."""
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".xlsx":
        rows = _xlsx_rows(uploaded_file)
    else:
        text = uploaded_file.getvalue().decode("utf-8-sig")
        sample = text[:4096]
        if not sample.strip():
            return []
        if "\t" in sample:
            delimiter = "\t"
        else:
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=",;|").delimiter
            except csv.Error:
                delimiter = ","
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    return _rows_to_products(rows)


def product_notes(product: dict[str, str]) -> str:
    return (
        f"Product name: {product['name']}\n"
        f"Specification link: {product['link'] or 'not supplied'}\n"
        f"Project amount: {product['amount'] or 'not supplied'} {product['units']}".strip()
    )


def products_to_csv(products: list[dict[str, str]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output, fieldnames=["name", "category", "link", "amount", "units"]
    )
    writer.writeheader()
    writer.writerows(
        {key: product.get(key, "") for key in writer.fieldnames} for product in products
    )
    return output.getvalue()


def report_to_csv(products: list[dict], overall: dict) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Green-score-3000 report"])
    writer.writerow(["Overall percentage", overall["percentage"]])
    writer.writerow(["Overall points", overall["points"]])
    writer.writerow(["Overall maximum points", overall["max_points"]])
    writer.writerow(["Overall level", overall["level"]])
    writer.writerow([])
    writer.writerow(["Product", "Selected option", "Percentage", "Points", "Level"])
    for product in products:
        result = product["selected_result"]
        writer.writerow(
            [
                product["name"],
                product.get("selected_option", product["name"]),
                result["percentage"],
                result["points"],
                result["level"],
            ]
        )
    return output.getvalue()
