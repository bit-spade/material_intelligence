from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat, model_validator


Share = Annotated[float, Field(ge=0, le=1)]


class Evidence(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    level: Literal[0, 1, 2] = 0
    text: str | None = None


class DeclaredEvidence(Evidence):
    level: Literal[0, 1] = 0


class MaterialShare(BaseModel):
    material: str
    share: Share


class Composition(DeclaredEvidence):
    materials: list[MaterialShare] = Field(default_factory=list)
    shares_estimated: bool = False


class Mass(DeclaredEvidence):
    kg_per_unit: PositiveFloat | None = None
    implausible: bool = False


class Country(DeclaredEvidence):
    iso2: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")


class EPD(Evidence):
    gwp_kg_co2e_per_unit: float | None = None
    modules: Literal["A1-A3", "A1-A4"] | None = None


class IndoorEmissions(Evidence):
    type: Literal[
        "third_party_label", "a_plus", "no_added_formaldehyde", "e1_or_compliance",
        "voc_content", "none",
    ] = "none"
    label: str | None = None
    voc_g_per_l: NonNegativeFloat | None = None
    voc_limit_g_per_l: PositiveFloat | None = None


class ChemicalSafety(Evidence):
    type: Literal["certificate", "free_of_declaration", "svhc_confirmed", "none"] = "none"
    name: str | None = None
    number: str | None = None

    @model_validator(mode="after")
    def require_number_for_verification(self):
        if self.level == 2 and (self.type != "certificate" or not (self.number or "").strip()):
            self.level = 1
        return self


class ForestMaterial(Evidence):
    certificate: Literal[
        "fsc_100", "fsc_recycled", "fsc_mix", "pefc", "reclaimed", "declaration", "none",
    ] = "none"
    number: str | None = None
    species_origin: Literal["european", "tropical", "unknown"] = "unknown"


class RecycledContent(Evidence):
    share: Share | None = None


class Guarantee(DeclaredEvidence):
    years: NonNegativeFloat | None = None


class Durability(DeclaredEvidence):
    durability_class: Literal["below_typical", "typical", "above_typical", "top"] | None = Field(
        default=None, alias="class"
    )


class Repair(DeclaredEvidence):
    repairable: bool = False


class TakeBack(DeclaredEvidence):
    take_back: bool = False


class Social(Evidence):
    type: Literal["certificate", "audited_supplier_code", "declaration", "none"] = "none"
    name: str | None = None
    number: str | None = None


class UseEnergy(DeclaredEvidence):
    watts: NonNegativeFloat | None = None


class UseWater(DeclaredEvidence):
    value: PositiveFloat | None = None
    unit: Literal["l/min", "l/flush"] | None = None


class ProductAttributes(BaseModel):
    A01_composition: Composition = Field(default_factory=Composition)
    A02_mass: Mass = Field(default_factory=Mass)
    A03_country: Country = Field(default_factory=Country)
    A04_epd: EPD = Field(default_factory=EPD)
    A05_indoor_emissions: IndoorEmissions = Field(default_factory=IndoorEmissions)
    A06_chemical_safety: ChemicalSafety = Field(default_factory=ChemicalSafety)
    A07_forest_material: ForestMaterial = Field(default_factory=ForestMaterial)
    A08_recycled_content: RecycledContent = Field(default_factory=RecycledContent)
    A09_guarantee: Guarantee = Field(default_factory=Guarantee)
    A10_durability: Durability = Field(default_factory=Durability)
    A11_repair: Repair = Field(default_factory=Repair)
    A12_take_back: TakeBack = Field(default_factory=TakeBack)
    A13_social: Social = Field(default_factory=Social)
    A14_use_energy: UseEnergy = Field(default_factory=UseEnergy)
    A15_use_water: UseWater = Field(default_factory=UseWater)
    A16_inherently_non_emitting: bool = False
    A17_risk_flags: list[str] = Field(default_factory=list)
    A18_forest_material_present: bool = False


class ExtractedProduct(BaseModel):
    channel: Literal["manufacturer", "retailer", "marketplace"] = "retailer"
    condition: Literal["new", "second_hand"] = "new"
    attributes: ProductAttributes


class AlternativeCandidate(BaseModel):
    name: str
    url: str


class AlternativeCandidates(BaseModel):
    products: list[AlternativeCandidate] = Field(max_length=3)
