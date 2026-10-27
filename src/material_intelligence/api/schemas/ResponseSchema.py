from typing import Optional
from pydantic import BaseModel, Field


class AnswersSchema(BaseModel):
    answers: list[Optional[bool]] = Field(
        description=(
            "One value per questionnaire question, in questionnaire order: "
            "True (explicitly supported), False (explicitly contradicted), "
            "None (unknown or not applicable)."
        )
    )


class AlternativeProduct(BaseModel):
    product_name: str = Field(
        description="Full product name and model (e.g., Kvadrat Revive 1, Camira Rivet)"
    )
    manufacturer: str = Field(
        description="Manufacturer or brand name (e.g., Kvadrat, Camira, Gabriel, BAUX)"
    )
    description: str = Field(
        description="Brief summary of the product, primary materials, and intended interior application."
    )
    sustainable_advantages: list[str] = Field(
        description="Key environmental strengths addressing criteria the baseline product missed (e.g., 100% post-consumer recycled PET, closed-loop take-back, PFAS-free)."
    )
    certifications: list[str] = Field(
        description="Recognized third-party ecolabels or standards (e.g., EU Ecolabel, OEKO-TEX Standard 100, Cradle to Cradle Certified, EPD, GRS, GOTS)."
    )
    material_composition: str = Field(
        description="Stated material composition (e.g., 100% recycled polyester, 100% post-consumer wool)."
    )
    estimated_level: str = Field(
        description="Estimated ECO-SCORE tier: 'High' or 'Medium'."
    )
    why_recommended: str = Field(
        description="Clear rationale explaining why this serves as a superior sustainable alternative for the specifier/designer."
    )


class RecommendationResult(BaseModel):
    baseline_summary: str = Field(
        description="Brief assessment of the baseline product's performance and why alternatives are needed."
    )
    key_improvement_areas: list[str] = Field(
        description="The specific ECO-SCORE criteria categories where the baseline product scored low or lacked documentation."
    )
    alternatives: list[AlternativeProduct] = Field(
        description="List of 2 to 3 real, commercially available alternative products in the same category."
    )
