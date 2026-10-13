from typing import Literal, Optional

from material_intelligence.models.eco_score_points import product_textile, product_acoustic, product_lighting


def calculate(
    product_type: Literal["Textile product", "Acoustic product", "Lighting product"],
    llm_mask: list[Optional[bool]]
):
    if product_type == "Textile product":
        product = product_textile
    elif product_type == "Acoustic product":
        product = product_acoustic
    elif product_type == "Lighting product":
        product = product_lighting
    else:
        raise ValueError(f"Unknown product type: {product_type}")

    return sum(
        criterion.points
        for criterion, is_selected in zip(product.criteria, llm_mask)
        if is_selected is True
    )