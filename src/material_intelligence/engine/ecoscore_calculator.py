#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interior ecoscore calculator
============================

Computes product and project ecoscores (0-100) following the interior ecoscore
methodology (README.md, ecoscore_methodology.xlsx):

  1. attributes A01-A18 of each product    (JSON, e.g. produced with prompt_extract_attributes.md)
  2. 13 questions CH1-CE4                   (0-100 each, with a verification level 2 / 1 / 0)
  3. five CMF category scores                (CH, HH, EH, SE, CE)
  4. product ecoscore                        (equal-weight mean of the categories, with the cap)
  5. project score                           (mass-weighted category scores, same rule) and hotspots

Usage
  python ecoscore_calculator.py project.json                  # text report
  python ecoscore_calculator.py project.json --details        # report with every question
  python ecoscore_calculator.py project.json --json out.json  # also write the full result as JSON
  python ecoscore_calculator.py project.json --reference my_reference.json

Project file (see example_project.json)
  {"name": "...", "add_implied_products": true, "products": [ {...}, {...} ]}

Each product is given in one of two ways:
  * with "attributes" (A01-A18), as returned by the extraction prompt - the full pipeline is run;
  * with "category_scores" ({"CH": 75, "HH": 70, ...}) and "mass_kg_total" - only steps 4-5 are run.
    This is useful for testing and for products scored by hand (see example_readme.json).

Reference data (emission factors, country indices, product-group defaults, anchors, parameters) are in
ecoscore_reference.json. Many values there are placeholders: they make the calculator run end to end,
but the resulting numbers are not meaningful until the reference data are replaced with sourced values.

Conventions
  * Verification level of an attribute: 2 = verified (EPD in a registry, certificate with a number),
    1 = declared (stated by the seller or manufacturer), 0 = missing. "?" is read as 0.
  * Missing information never removes a question: the question falls back to a cautious default.
  * "n/a" follows from the product group only (Product groups sheet of the methodology).
  * Colour bands and the cap are applied to scores rounded to whole numbers (half up).
"""
import argparse
import json
import math
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATEGORIES = ["CH", "HH", "EH", "SE", "CE"]
CATEGORY_NAMES = {"CH": "Climate Health", "HH": "Human Health", "EH": "Ecosystem Health",
                  "SE": "Social Health & Equity", "CE": "Circular Economy"}
QUESTIONS = ["CH1", "HH1", "HH2", "EH1", "EH2", "EH3", "EH4", "SE1", "SE2", "CE1", "CE2", "CE3", "CE4"]
FSC_FAMILY = {"fsc_100", "fsc_recycled", "fsc_mix"}


@lru_cache(maxsize=1)
def load_reference():
    return json.loads((HERE / "ecoscore_reference.json").read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------------------------- helpers
def half_up(x):
    return int(math.floor(x + 0.5))


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def level(attr):
    """Verification level of an attribute dict: 2, 1 or 0 ('?' and missing count as 0)."""
    if not isinstance(attr, dict):
        return 0
    v = attr.get("level", 0)
    return {2: 2, "2": 2, 1: 1, "1": 1}.get(v, 0)


def interpolate(x, points):
    """Piecewise-linear interpolation over [[x, score], ...] sorted by x."""
    if x <= points[0][0]:
        return float(points[0][1])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return float(points[-1][1])


def q(score, lvl, note=""):
    return {"score": None if score is None else round(float(score), 2), "level": lvl, "note": note}


NA = {"score": None, "level": None, "note": "n/a for this product group"}


# ----------------------------------------------------------------------------------------------- calculator
class EcoscoreCalculator:
    def __init__(self, reference):
        self.ref = reference
        self.par = reference["parameters"]
        self.warnings = []
        self.placeholders = "PLACEHOLDER" in reference.get("_status", "")

    # ------------------------------------------------------------------ product-group defaults
    def defaults(self, product):
        group = product.get("product_group")
        if group not in self.ref["product_groups"]:
            raise ValueError(f"{product.get('id')}: unknown product group {group!r}")
        d = dict(self.ref["product_groups"][group])
        sub = product.get("subtype")
        if sub and sub in d.get("subtypes", {}):
            d.update(d["subtypes"][sub])
        return d

    def applies(self, question, product, d):
        if question in d.get("questions_na", []):
            return False
        if question == "EH1":
            return bool(self.attr(product, "A18_forest_material_present", False))
        if question == "EH4":
            return product["product_group"] == "Sanitaryware and taps"
        return True

    @staticmethod
    def attr(product, key, default=None):
        return product.get("attributes", {}).get(key, default)

    # ------------------------------------------------------------------ basic product facts
    def materials(self, product, d):
        """Normalised [(material, share)], and whether the composition was stated."""
        a1 = self.attr(product, "A01_composition")
        mats = []
        if level(a1) >= 1:
            for m in a1.get("materials") or []:
                key = m.get("material")
                if key not in self.ref["materials"]:
                    self.warnings.append(f"{product.get('id')}: material {key!r} not in reference, counted as 'other'")
                    key = "other"
                share = m.get("share")
                mats.append((key, None if share is None else float(share)))
            # materials listed without a share get an equal part of what the stated shares leave
            missing = [i for i, (_, s) in enumerate(mats) if s is None]
            if missing:
                rest = max(0.0, 1.0 - sum(s for _, s in mats if s is not None))
                for i in missing:
                    mats[i] = (mats[i][0], rest / len(missing))
        total = sum(s for _, s in mats)
        if total <= 0:
            return [(k, float(s)) for k, s in d["default_materials"].items()], False
        return [(k, s / total) for k, s in mats], True

    def mass_per_unit(self, product, d):
        a2 = self.attr(product, "A02_mass")
        if level(a2) >= 1 and not a2.get("implausible") and (a2.get("kg_per_unit") or 0) > 0:
            return float(a2["kg_per_unit"]), True
        return float(d["mass_per_unit_kg"]), False

    def country(self, product):
        a3 = self.attr(product, "A03_country")
        if level(a3) >= 1 and a3.get("iso2"):
            return a3["iso2"].upper()
        return None

    def mat(self, key, field):
        return self.ref["materials"][key][field]

    def service_life_factor(self, product, d):
        """CE2: X = service life relative to the product-group average, from guarantee and durability class."""
        ce = self.par["ce"]
        signals, lvl, notes = [], 0, []
        a9 = self.attr(product, "A09_guarantee")
        if level(a9) >= 1 and a9.get("years") is not None:
            stat = ce["statutory_warranty_years"]
            g, g_typ = max(float(a9["years"]), stat), max(float(d["typical_guarantee_years"]), stat)
            signals.append(math.sqrt(g / g_typ))
            lvl = 1
            notes.append(f"guarantee {a9['years']} y vs typical {d['typical_guarantee_years']} y")
        a10 = self.attr(product, "A10_durability")
        if level(a10) >= 1 and a10.get("class") in ce["durability_class_factors"]:
            signals.append(ce["durability_class_factors"][a10["class"]])
            lvl = 1
            notes.append(f"durability {a10['class']}")
        x = math.exp(sum(math.log(s) for s in signals) / len(signals)) if signals else 1.0
        lo, hi = ce["service_life_factor_range"]
        return clamp(x, lo, hi), lvl, "; ".join(notes) or "no guarantee or durability data, group average"

    # ------------------------------------------------------------------ CH1
    def transport(self, mass_kg, iso2):
        t = self.par["transport"]
        zone = self.ref["countries"].get(iso2, {}).get("zone") if iso2 else None
        z = t["zones"][zone or t["unknown_country_zone"]]
        return mass_kg / 1000 * (z["truck_km"] * t["truck_kg_co2e_per_tkm"] + z["sea_km"] * t["sea_kg_co2e_per_tkm"])

    def use_phase(self, product, d):
        """kg CO2e per functional unit per year of use (lighting energy, hot water for taps)."""
        u = self.par["use_phase"]
        if product["product_group"] == "Lighting":
            a14 = self.attr(product, "A14_use_energy")
            w = a14.get("watts") if level(a14) >= 1 and a14.get("watts") is not None else d.get("default_power_w", 0)
            return w * u["lighting_hours_per_year"] / 1000 * u["grid_kg_co2e_per_kwh"]
        if product["product_group"] == "Sanitaryware and taps":
            flow, unit = self.water(product, d)
            if unit == "l/min":
                litres = flow * u["tap_minutes_per_day"] * 365
                kwh = litres * u["hot_water_share"] * 4.186 * u["hot_water_delta_t_k"] / 3600
                return kwh * u["heat_kg_co2e_per_kwh"]
        return 0.0

    def water(self, product, d):
        a15 = self.attr(product, "A15_use_water")
        if level(a15) >= 1 and a15.get("value") and a15.get("unit") in ("l/min", "l/flush"):
            return float(a15["value"]), a15["unit"]
        dw = d.get("default_water") or {"value": None, "unit": None}
        return dw["value"], dw["unit"]

    def ch1_typical(self, d, product):
        """Footprint per unit and year of the product group's default product, estimated the same way as a
        product without an EPD (with the estimate surcharge), so that a typical product scores 50."""
        mats = d["default_materials"].items()
        mass = d["mass_per_unit_kg"]
        emb = mass * sum(s * self.mat(k, "ef_kg_co2e_per_kg") for k, s in mats)
        zone_iso = next((k for k, c in self.ref["countries"].items()
                         if c["zone"] == self.par["ch1"]["typical_zone"]), None)
        emb += self.transport(mass, zone_iso)
        emb *= 1 + self.par["ch1"]["surcharge_estimate"]
        typical_product = {"product_group": product["product_group"], "attributes": {}}
        return emb / d["service_life_years"] + self.use_phase(typical_product, d)

    def score_ch1(self, product, d, mats, mats_known, x):
        p = self.par["ch1"]
        mass, mass_known = self.mass_per_unit(product, d)
        iso2 = self.country(product)
        a4 = self.attr(product, "A04_epd")
        gwp = a4.get("gwp_kg_co2e_per_unit") if level(a4) >= 1 else None
        if gwp is not None:
            embodied = float(gwp)
            if (a4.get("modules") or "A1-A3").upper() == "A1-A3":
                embodied += self.transport(mass, iso2)
            lvl = level(a4)
            surcharge = 0.0 if lvl == 2 else p["surcharge_estimate"]
            note = "EPD" if lvl == 2 else "related EPD"
        else:
            embodied = mass * sum(s * self.mat(k, "ef_kg_co2e_per_kg") for k, s in mats) + self.transport(mass, iso2)
            lvl = 1 if (mass_known and mats_known) else 0
            surcharge = p["surcharge_estimate"] if lvl else p["surcharge_default"]
            note = "estimate from mass and composition" if lvl else "product-group defaults for missing mass or composition"
            if level(a4) >= 1:
                note += " (EPD mentioned, GWP value not available)"
        per_year = embodied * (1 + surcharge) / (d["service_life_years"] * x) + self.use_phase(product, d)
        anchors = d.get("ch1_anchors_kg_co2e_per_unit_year")
        if not anchors:
            typ = self.ch1_typical(d, product)
            f = p["anchor_factors_when_no_reference_set"]
            anchors = [typ * f["p10"], typ * f["p50"], typ * f["p90"]]
        p10, p50, p90 = anchors
        score = interpolate(per_year, [[p10, 100], [p50, 50], [p90, 0]])
        return q(score, lvl, f"{note}; {per_year:.2f} kg CO2e per {d['functional_unit']} per year"), per_year

    # ------------------------------------------------------------------ Human Health
    def score_hh1(self, product, d, mats):
        a5 = self.attr(product, "A05_indoor_emissions") or {}
        t, lvl = a5.get("type", "none"), level(a5)
        if t == "third_party_label" and lvl >= 1:
            return q(100, lvl, f"emission label {a5.get('label') or ''}".strip())
        if self.attr(product, "A16_inherently_non_emitting", False):
            return q(100, 1, "inherently non-emitting materials")
        if product.get("condition") == "second_hand":
            return q(75, 1, "second-hand product")
        if t == "voc_content" and lvl >= 1 and a5.get("voc_g_per_l") is not None and a5.get("voc_limit_g_per_l"):
            far = a5["voc_g_per_l"] <= self.par["hh1"]["voc_far_below_limit_fraction"] * a5["voc_limit_g_per_l"]
            return q(75 if far else 50, 1, f"VOC {a5['voc_g_per_l']} g/l vs limit {a5['voc_limit_g_per_l']} g/l")
        if t in ("a_plus", "no_added_formaldehyde") and lvl >= 1:
            return q(75, 1, t.replace("_", " "))
        if t == "e1_or_compliance" and lvl >= 1:
            return q(50, 1, "legal compliance declared")
        emitting = any(self.mat(k, "emitting") for k, _ in mats)
        if emitting and product.get("channel") == "marketplace":
            return q(25, 0, "emitting materials, marketplace channel, no data")
        return q(50, 0, "no data: legal minimum assumed")

    def risk_flags(self, product, mats):
        flags = {f: self.ref["risk_flags"].get(f, "typical") for f in self.attr(product, "A17_risk_flags", []) or []}
        for k, _ in mats:
            rf = self.mat(k, "risk_flag")
            if rf:
                flags.setdefault(rf, self.ref["risk_flags"].get(rf, "typical"))
        return flags

    def score_hh2(self, product, mats):
        a6 = self.attr(product, "A06_chemical_safety") or {}
        t, lvl = a6.get("type", "none"), level(a6)
        flags = self.risk_flags(product, mats)
        if t == "svhc_confirmed":
            return q(0, max(lvl, 1), "substance of very high concern confirmed")
        if not flags:
            return q(100, 2 if (t == "certificate" and lvl == 2) else 1, "no risk flags")
        names = ", ".join(sorted(flags))
        if t == "certificate" and lvl == 2:
            return q(100, 2, f"flags ({names}) closed by certificate {a6.get('name') or ''}".strip())
        if t in ("certificate", "free_of_declaration") and lvl >= 1:
            return q(70, 1, f"flags ({names}); declaration or certificate without number")
        if "high" in flags.values():
            return q(25, 0, f"high-risk flags ({names}), no information")
        return q(50, 0, f"risk flags ({names}), no information")

    # ------------------------------------------------------------------ Ecosystem Health
    def score_eh1(self, product):
        a7 = self.attr(product, "A07_forest_material") or {}
        cert, lvl = a7.get("certificate", "none"), level(a7)
        numbered = lvl == 2 and bool(a7.get("number"))
        if cert == "reclaimed" and lvl >= 1:
            return q(100, 1, "reclaimed wood")
        if cert in ("fsc_100", "fsc_recycled") and lvl >= 1:
            return q(100, 2, cert) if numbered else q(60, 1, f"{cert} claimed without number")
        if cert in ("fsc_mix", "pefc") and lvl >= 1:
            return q(85, 2, cert) if numbered else q(60, 1, f"{cert} claimed without number")
        if cert == "declaration" and lvl >= 1:
            return q(60, 1, "responsible-sourcing declaration")
        origin = a7.get("species_origin", "unknown")
        if origin == "european":
            return q(50, 1, "European species, no certificate")
        if origin == "tropical":
            return q(15, 1, "tropical species, no certificate")
        return q(15, 0, "unknown species or origin, no certificate")

    def score_eh2(self, mats, mats_known):
        s = sum(share * self.mat(k, "eh2_score") for k, share in mats)
        return q(s, 1 if mats_known else 0, "mass-weighted material scores" + ("" if mats_known else " (group default mix)"))

    def score_eh3(self, iso2):
        dflt = self.par["missing_data_defaults"]["EH3"]
        if not iso2:
            return q(dflt, 0, "country not stated: default")
        c = self.ref["countries"].get(iso2, {})
        if c.get("epi_ecosystem_vitality") is None:
            return q(dflt, 1, f"{iso2} not in the reference table: default")
        n = self.par["eh3_normalisation"]
        s = 100 * (c["epi_ecosystem_vitality"] - n["min"]) / (n["max"] - n["min"])
        return q(clamp(s, 0, 100), 1, f"{iso2}, EPI ecosystem vitality {c['epi_ecosystem_vitality']}")

    def score_eh4(self, product, d):
        a15 = self.attr(product, "A15_use_water") or {}
        value, unit = a15.get("value"), a15.get("unit")
        if level(a15) < 1 or not value or unit not in self.par["eh4_anchors"]:
            return q(self.par["missing_data_defaults"]["EH4"], 0, "water use not stated: default")
        return q(interpolate(value, self.par["eh4_anchors"][unit]), 1, f"{value} {unit}")

    # ------------------------------------------------------------------ Social Health & Equity
    def score_se1(self, iso2):
        dflt = self.par["missing_data_defaults"]["SE1"]
        if not iso2:
            return q(dflt, 0, "country not stated: default")
        rating = self.ref["countries"].get(iso2, {}).get("ituc_rating")
        if rating is None:
            self.warnings.append("ITUC ratings missing from the reference data: SE1 uses the default value.")
            return q(dflt, 1, f"{iso2}: ITUC rating not in the reference table: default")
        return q(self.par["se1_ituc_scores"][str(rating)], 1, f"{iso2}, ITUC rating {rating}")

    def score_se2(self, product):
        a13 = self.attr(product, "A13_social") or {}
        t, lvl = a13.get("type", "none"), level(a13)
        if t == "certificate" and lvl == 2 and a13.get("number"):
            return q(100, 2, f"social certificate {a13.get('name') or ''}".strip())
        if t in ("certificate", "audited_supplier_code") and lvl >= 1:
            return q(70, 1, f"{a13.get('name') or t} (no certificate number)")
        if t == "declaration" and lvl >= 1:
            return q(40, 1, "general declaration")
        a7 = self.attr(product, "A07_forest_material") or {}
        if a7.get("certificate") in FSC_FAMILY and level(a7) == 2 and a7.get("number"):
            return q(70, 2, "FSC certificate (covers core labour rights in forestry)")
        return q(None, 0, "no social verification: SE = SE1")

    # ------------------------------------------------------------------ Circular Economy (MCI)
    def mci(self, v, w, x):
        lfi = (v + w) / 2
        return clamp(1 - lfi * 0.9 / x, 0.0, 1.0), lfi

    def circularity(self, product, d, mats, mats_known, x, x_lvl, x_note):
        ce = self.par["ce"]
        out = {}
        # CE1: virgin share V
        a8 = self.attr(product, "A08_recycled_content") or {}
        rec_avg = sum(s * self.mat(k, "recycled_share_market_avg") for k, s in mats)
        if product.get("condition") == "second_hand":
            recycled, reuse, lvl, note = 0.0, 1.0, 1, "second-hand product: 100% reuse"
        elif level(a8) >= 1:
            share = a8.get("share")
            recycled = ce["recycled_share_when_claim_has_no_share"] if share is None else float(share)
            reuse, lvl = 0.0, level(a8)
            note = f"recycled share {recycled:.0%}" + (" (claim without share)" if share is None else "")
        else:
            recycled, reuse, lvl, note = rec_avg, 0.0, 0, f"market average {rec_avg:.0%}"
        v = clamp(1 - recycled - reuse, 0, 1)
        out["CE1"] = q(None, lvl, f"{note}; virgin share V = {v:.2f}")
        # CE2: service life factor X
        out["CE2"] = q(None, x_lvl, f"{x_note}; X = {x:.2f}")
        # CE4: end of life from composition, CE3: repair and take-back
        collected = sum(s * self.mat(k, "eol_collected_share") for k, s in mats)
        out["CE4"] = q(None, 1 if mats_known else 0, f"collected for reuse or recycling {collected:.0%}")
        if self.applies("CE3", product, d):
            a11 = self.attr(product, "A11_repair") or {}
            a12 = self.attr(product, "A12_take_back") or {}
            bonus, notes = 0.0, []
            if level(a11) >= 1 and a11.get("repairable"):
                bonus += ce["repair_collection_bonus"]
                notes.append("repairable or disassemblable")
            if level(a12) >= 1 and a12.get("take_back"):
                bonus += ce["take_back_collection_bonus"]
                notes.append("take-back or buy-back")
            lvl3 = 1 if (level(a11) >= 1 or level(a12) >= 1) else 0
            collected = min(1.0, collected + bonus)
            out["CE3"] = q(None, lvl3, ", ".join(notes) or ("no repair features" if lvl3 else "no data"))
        else:
            out["CE3"] = dict(NA)
        w = 1 - collected
        m, lfi = self.mci(v, w, x)
        # typical product of the group -> 50
        dm = d["default_materials"].items()
        v_typ = 1 - sum(s * self.mat(k, "recycled_share_market_avg") for k, s in dm)
        w_typ = 1 - sum(s * self.mat(k, "eol_collected_share") for k, s in dm)
        m_typ, _ = self.mci(v_typ, w_typ, 1.0)
        if m <= m_typ:
            score = 50 * m / m_typ if m_typ > 0 else 50
        else:
            score = 50 + 50 * (m - m_typ) / (1 - m_typ)
        return out, score, {"V": round(v, 3), "W": round(w, 3), "X": round(x, 3), "LFI": round(lfi, 3),
                            "MCI": round(m, 3), "MCI_typical": round(m_typ, 3)}

    # ------------------------------------------------------------------ product
    def score_product(self, product):
        d = self.defaults(product)
        qty = float(product.get("quantity", 1))
        res = {"id": product.get("id"), "name": product.get("name"), "product_group": product.get("product_group"),
               "quantity": qty, "unit": d["functional_unit"], "implied": product.get("implied", False)}

        if "category_scores" in product:                     # scores given directly
            cats = {c: product["category_scores"].get(c) for c in CATEGORIES}
            res["mass_kg_total"] = float(product["mass_kg_total"])
            res["mass_source"] = "given"
            res["questions"] = None
            res["footprint_kg_co2e_per_year"] = None
            return self.finish_product(res, cats)

        if self.placeholders:
            self.warnings.append("Reference data contain placeholders: scores are for testing, not for publication.")
        mats, mats_known = self.materials(product, d)
        mass_unit, mass_known = self.mass_per_unit(product, d)
        iso2 = self.country(product)
        x, x_lvl, x_note = self.service_life_factor(product, d)
        qs = {}
        qs["CH1"], per_year = self.score_ch1(product, d, mats, mats_known, x)
        qs["HH1"] = self.score_hh1(product, d, mats) if self.applies("HH1", product, d) else dict(NA)
        qs["HH2"] = self.score_hh2(product, mats) if self.applies("HH2", product, d) else dict(NA)
        qs["EH1"] = self.score_eh1(product) if self.applies("EH1", product, d) else dict(NA)
        qs["EH2"] = self.score_eh2(mats, mats_known)
        qs["EH3"] = self.score_eh3(iso2)
        qs["EH4"] = self.score_eh4(product, d) if self.applies("EH4", product, d) else dict(NA)
        qs["SE1"] = self.score_se1(iso2)
        qs["SE2"] = self.score_se2(product)
        ce_q, ce_score, ce_detail = self.circularity(product, d, mats, mats_known, x, x_lvl, x_note)
        qs.update(ce_q)

        def vals(*ids):
            return [qs[i]["score"] for i in ids if qs[i]["score"] is not None]

        hh, eh, se = vals("HH1", "HH2"), vals("EH1", "EH2", "EH3", "EH4"), vals("SE1", "SE2")
        cats = {"CH": qs["CH1"]["score"], "HH": min(hh) if hh else None, "EH": sum(eh) / len(eh) if eh else None,
                "SE": max(se) if se else None, "CE": ce_score}
        res["mass_kg_total"] = mass_unit * qty
        res["mass_source"] = "product data" if mass_known else "product-group default"
        res["footprint_kg_co2e_per_year"] = round(per_year * qty, 2)
        res["questions"] = {k: qs[k] for k in QUESTIONS}
        res["mci"] = ce_detail
        levels = [qs[k]["level"] for k in QUESTIONS if qs[k]["level"] is not None]
        res["verification"] = {"verified": levels.count(2), "declared": levels.count(1), "missing": levels.count(0)}
        return self.finish_product(res, cats)

    def aggregate(self, cats):
        """Equal-weight mean of the applicable categories, with the cap."""
        w = self.par["category_weights"]
        app = {c: s for c, s in cats.items() if s is not None}
        mean = sum(w[c] * s for c, s in app.items()) / sum(w[c] for c in app)
        cap = self.par["cap"]
        capped = any(half_up(s) <= cap["category_at_or_below"] for s in app.values()) and mean > cap["ecoscore_at_most"]
        return mean, (min(mean, cap["ecoscore_at_most"]) if capped else mean), capped

    def colour(self, score):
        b = self.par["colour_bands"]
        s = half_up(score)
        return "red" if s <= b["red_max"] else "orange" if s <= b["orange_max"] else "green"

    def finish_product(self, res, cats):
        mean, eco, capped = self.aggregate(cats)
        res["categories"] = {c: (None if s is None else {"score": round(s, 2), "colour": self.colour(s)})
                             for c, s in cats.items()}
        res["mean"] = round(mean, 2)
        res["ecoscore"] = round(eco, 2)
        res["colour"] = self.colour(eco)
        res["capped"] = capped
        return res

    # ------------------------------------------------------------------ project
    def implied_products(self, products):
        out = []
        specified = {p.get("subtype") for p in products if p.get("product_group") == "Installation materials"}
        for rule in self.ref.get("implied_products", []):
            if rule.get("subtype") in specified:
                continue
            area = sum(float(p.get("quantity", 0)) for p in products if p.get("product_group") in rule["for_groups"]
                       and not p.get("implied"))
            if area > 0:
                out.append({"id": "IMPL-" + rule["name"].split(" (")[0].replace(" ", "-").lower(),
                            "name": rule["name"], "product_group": "Installation materials",
                            "subtype": rule.get("subtype"), "quantity": area,
                            "implied": True, "channel": "retailer",
                            "attributes": {
                                "A01_composition": {"level": 1, "materials": [{"material": k, "share": s}
                                                                              for k, s in rule["materials"].items()]},
                                "A02_mass": {"level": 1, "kg_per_unit": rule["kg_per_m2"]}}})
        return out

    def score_project(self, project):
        self.warnings.clear()
        products = list(project["products"])
        if project.get("add_implied_products", True):
            products += self.implied_products(products)
        scored = [self.score_product(p) for p in products]
        total_mass = sum(r["mass_kg_total"] for r in scored)
        if not math.isfinite(total_mass) or total_mass <= 0:
            raise ValueError("The project needs a positive total mass.")
        for r in scored:
            r["mass_share"] = r["mass_kg_total"] / total_mass
        cats = {}
        for c in CATEGORIES:
            pairs = [(r["mass_share"], r["categories"][c]["score"]) for r in scored if r["categories"][c] is not None]
            den = sum(wt for wt, _ in pairs)
            cats[c] = sum(wt * s for wt, s in pairs) / den if den else None
        mean, eco, capped = self.aggregate(cats)
        hotspots = sorted(({"id": r["id"], "name": r["name"], "mass_share": round(r["mass_share"], 4),
                            "ecoscore": r["ecoscore"],
                            "hotspot_index": round(r["mass_share"] * (100 - r["ecoscore"]), 2)} for r in scored),
                          key=lambda h: -h["hotspot_index"])
        footprints = [r["footprint_kg_co2e_per_year"] for r in scored if r["footprint_kg_co2e_per_year"] is not None]
        return {
            "project": project.get("name", "project"),
            "categories": {c: (None if s is None else {"score": round(s, 2), "colour": self.colour(s)})
                           for c, s in cats.items()},
            "mean": round(mean, 2), "ecoscore": round(eco, 2), "colour": self.colour(eco), "capped": capped,
            "total_mass_kg": round(total_mass, 2),
            "footprint_kg_co2e_per_year": round(sum(footprints), 2) if footprints else None,
            "hotspots": hotspots, "products": scored, "warnings": sorted(set(self.warnings)),
        }


# ----------------------------------------------------------------------------------------------- report
def fmt(s):
    return "  –" if s is None else f"{half_up(s):3d}"


def report(result, details=False):
    lines = [f"Project: {result['project']}", ""]
    hdr = f"{'ID':<16}{'Product':<44}{'kg':>8}{'share':>7}  " + " ".join(f"{c:>3}" for c in CATEGORIES) + \
          f"{'mean':>6}{'eco':>5}  colour"
    lines += [hdr, "-" * len(hdr)]
    for r in result["products"]:
        cats = " ".join(fmt(None if r["categories"][c] is None else r["categories"][c]["score"]) for c in CATEGORIES)
        lines.append(f"{str(r['id'])[:15]:<16}{str(r['name'])[:43]:<44}{r['mass_kg_total']:>8.1f}"
                     f"{r['mass_share']:>7.0%}  {cats}{half_up(r['mean']):>6}{half_up(r['ecoscore']):>5}  "
                     f"{r['colour']}{' (capped)' if r['capped'] else ''}")
        if details and r["questions"]:
            for qid, qq in r["questions"].items():
                if qq["level"] is None:
                    lines.append(f"{'':16}{qid}: n/a")
                else:
                    sc = "  " if qq["score"] is None else f"{half_up(qq['score']):3d}"
                    lines.append(f"{'':16}{qid}: {sc}  level {qq['level']}  {qq['note']}")
            lines.append(f"{'':16}MCI: {r['mci']}")
    lines += ["-" * len(hdr)]
    cats = " ".join(fmt(None if result["categories"][c] is None else result["categories"][c]["score"])
                    for c in CATEGORIES)
    lines.append(f"{'PROJECT':<16}{'':<44}{result['total_mass_kg']:>8.1f}{1:>7.0%}  {cats}"
                 f"{half_up(result['mean']):>6}{half_up(result['ecoscore']):>5}  {result['colour']}"
                 f"{' (capped)' if result['capped'] else ''}")
    if result["footprint_kg_co2e_per_year"] is not None:
        lines.append(f"\nCarbon footprint (information): {result['footprint_kg_co2e_per_year']:.1f} kg CO2e per year")
    lines += ["", "Hotspots (mass share × (100 − ecoscore)):"]
    for h in result["hotspots"][:5]:
        lines.append(f"  {h['hotspot_index']:6.1f}  {h['name']}")
    if result["warnings"]:
        lines += ["", "Warnings:"] + [f"  - {w}" for w in result["warnings"]]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Interior ecoscore calculator")
    ap.add_argument("project", help="project JSON file")
    ap.add_argument("--reference", default=str(HERE / "ecoscore_reference.json"), help="reference data JSON")
    ap.add_argument("--json", help="write the full result to this JSON file")
    ap.add_argument("--details", action="store_true", help="show every question in the report")
    a = ap.parse_args(argv)
    ref = load_reference() if a.reference == str(HERE / "ecoscore_reference.json") else json.loads(
        Path(a.reference).read_text(encoding="utf-8")
    )
    with open(a.project, encoding="utf-8") as f:
        project = json.load(f)
    result = EcoscoreCalculator(ref).score_project(project)
    print(report(result, a.details))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
