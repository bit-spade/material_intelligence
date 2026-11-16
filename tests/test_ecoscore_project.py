import io
import json
import unittest
import zipfile
from unittest.mock import patch

from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

from material_intelligence.api.ecoscore import extract_product
from material_intelligence.api.schemas.ecoscore import ExtractedProduct
from material_intelligence.engine.ecoscore_calculator import CATEGORY_NAMES, EcoscoreCalculator, load_reference
from material_intelligence.frontend.workflow import ASSETS, editable_product, parse_product_file, scoring_product


class ProjectScoringTests(unittest.TestCase):
    def test_readme_calculation_preserves_cap_and_mass_weighting(self):
        source = [
            ("floor", "Wood flooring", 150, [75, 70, 70, 70, 65]),
            ("rug", "Rugs", 10, [80, 85, 80, 30, 75]),
            ("sofa", "Upholstered furniture", 40, [45, 25, 50, 40, 35]),
        ]
        products = [
            {
                "id": name, "name": name, "product_group": group, "mass_kg_total": mass,
                "category_scores": dict(zip(CATEGORY_NAMES, scores, strict=True)),
            }
            for name, group, mass, scores in source
        ]
        result = EcoscoreCalculator(load_reference()).score_project({
            "products": products,
            "add_implied_products": False,
        })
        self.assertEqual(result["total_mass_kg"], 200)
        self.assertEqual(result["categories"]["CH"]["score"], 69.25)
        self.assertEqual(result["ecoscore"], 63.8)
        self.assertEqual(result["products"][1]["ecoscore"], 66)
        self.assertTrue(result["products"][1]["capped"])
        self.assertEqual([row["id"] for row in result["hotspots"]], ["floor", "sofa", "rug"])

    def test_builtin_fixture_keeps_evidence_and_scores(self):
        project = json.loads((ASSETS / "example_project.json").read_text(encoding="utf-8"))
        project["products"] = [scoring_product(editable_product(product)) for product in project["products"]]
        result = EcoscoreCalculator(load_reference()).score_project(project)
        self.assertEqual(result["total_mass_kg"], 373.92)
        self.assertEqual(result["ecoscore"], 55.56)
        self.assertEqual(len(result["products"][0]["questions"]), 13)
        self.assertTrue(any("placeholders" in warning for warning in result["warnings"]))

    def test_installation_materials_are_counted_once(self):
        result = EcoscoreCalculator(load_reference()).score_project({"products": [
            {"id": "tile", "product_group": "Tiles", "quantity": 4},
            {"id": "glue", "product_group": "Installation materials", "subtype": "tile_adhesive", "quantity": 4},
        ]})
        self.assertEqual([row["id"] for row in result["products"]], ["tile", "glue", "IMPL-grout"])

    def test_editing_material_identity_invalidates_imported_evidence(self):
        row = editable_product({
            "name": "Flooring A", "product_group": "Wood flooring", "quantity": 18,
            "attributes": {"A02_mass": {"level": 1, "kg_per_unit": 8.64}},
        })
        row["quantity"] = "17,5"
        self.assertEqual(scoring_product(row)["quantity"], 17.5)
        self.assertIn("attributes", scoring_product(row))
        row["name"] = "Flooring B"
        self.assertNotIn("attributes", scoring_product(row))
        row["unit"] = "pieces"
        with self.assertRaisesRegex(ValueError, "m²"):
            scoring_product(row)
        row["unit"] = "m2"
        row["quantity"] = "-2"
        with self.assertRaisesRegex(ValueError, "positive"):
            scoring_product(row)

    def test_xlsx_preserves_sparse_columns_and_inline_strings(self):
        spreadsheet = io.BytesIO()
        spreadsheet.name = "materials.xlsx"
        with zipfile.ZipFile(spreadsheet, "w") as archive:
            archive.writestr("xl/workbook.xml", """
                <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
                  <sheets><sheet name="Materials" sheetId="1" r:id="rId1"/></sheets>
                </workbook>
            """)
            archive.writestr("xl/_rels/workbook.xml.rels", """
                <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                  <Relationship Id="rId1" Target="/xl/worksheets/sheet1.xml"/>
                </Relationships>
            """)
            archive.writestr("xl/worksheets/sheet1.xml", """
                <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
                  <sheetData>
                    <row r="1">
                      <c r="A1" t="inlineStr"><is><t>Name</t></is></c>
                      <c r="B1" t="inlineStr"><is><t>Link</t></is></c>
                      <c r="C1" t="inlineStr"><is><t>Amount</t></is></c>
                    </row>
                    <row r="2">
                      <c r="A2" t="inlineStr"><is><t>Oak boards</t></is></c>
                      <c r="C2"><v>18.5</v></c>
                    </row>
                  </sheetData>
                </worksheet>
            """)
        self.assertEqual(parse_product_file(spreadsheet)["products"], [
            {"name": "Oak boards", "url": "", "quantity": "18.5"},
        ])

    def test_extraction_preserves_inputs_and_validates_verification(self):
        with self.assertRaises(ValidationError):
            ExtractedProduct.model_validate({"attributes": {"A02_mass": {"level": 2, "kg_per_unit": 2}}})
        evidence = ExtractedProduct.model_validate({"attributes": {
            "A02_mass": {"level": 1, "kg_per_unit": 2},
            "A06_chemical_safety": {"type": "certificate", "level": 2, "name": "OEKO-TEX"},
        }})
        product = {"name": "Curtain", "url": "", "quantity": 3, "unit": "m2", "product_group": "Window treatments"}
        with patch("material_intelligence.api.ecoscore._invoke", return_value=evidence) as invoke:
            extracted, warnings = extract_product(product, notes="Declared net weight", api_key="test")
        self.assertEqual({key: extracted[key] for key in product}, product)
        self.assertEqual(extracted["attributes"]["A06_chemical_safety"]["level"], 1)
        self.assertEqual(len(extracted["attributes"]), 18)
        self.assertEqual(invoke.call_args.args[2]["sources"][0]["text"], "Declared net weight")
        self.assertEqual(warnings, [])

    def test_streamlit_sample_swap_and_export(self):
        app = AppTest.from_file(str(ASSETS.parent / "streamlit.py")).run()

        def click(label):
            next(button for button in app.button if button.label == label).click().run()
            self.assertFalse(app.exception)

        click("Try a sample project")
        click("Calculate project score")
        self.assertEqual(app.session_state.assessment["baseline"]["ecoscore"], 55.56)
        select = next(box for box in app.selectbox if box.label.startswith("Replacement for "))
        sigma = next(option for option in select.options if option.startswith("Sigma Daisy"))
        select.select(sigma).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state.assessment["chosen"]), 1)
        click("Export report")
        self.assertEqual(len(app.get("download_button")), 2)
        click("Back to assessment")
        self.assertEqual(len(app.session_state.assessment["chosen"]), 1)
