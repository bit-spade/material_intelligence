from typing import Literal, Optional

from material_intelligence.models.eco_score_points import product_textile, product_acoustic, product_lighting


def calculate(
    product_type: Literal["Textile_product", "Acoustic_product", "Lighting_product"],
    llm_mask: list[Optional[bool]]
):
    if product_type == "Textile_product":
        product = product_textile
    elif product_type == "Acoustic_product":
        product = product_acoustic
    elif product_type == "Lighting_product":
        product = product_lighting
    else:
        raise ValueError(f"Unknown product type: {product_type}")

    return sum(
        criterion.points
        for criterion, is_selected in zip(product.criteria, llm_mask)
        if is_selected is True
    )