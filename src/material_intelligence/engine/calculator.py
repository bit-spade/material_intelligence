from typing import Literal, Optional

from material_intelligence.models.eco_score_points import product_textile, product_acoustic, product_lighting


def get_product_config(
    product_type: Literal["Textile_product", "Acoustic_product", "Lighting_product"],
):
    if product_type == "Textile_product":
        return product_textile
    elif product_type == "Acoustic_product":
        return product_acoustic
    elif product_type == "Lighting_product":
        return product_lighting
    else:
        raise ValueError(f"Unknown product type: {product_type}")


def calculate(
    product_type: Literal["Textile_product", "Acoustic_product", "Lighting_product"],
    llm_mask: list[Optional[bool]]
):
    product = get_product_config(product_type)

    return sum(
        criterion.points
        for criterion, is_selected in zip(product.criteria, llm_mask)
        if is_selected is True
    )


def calculate_level(percentage: float) -> str:
    """Classifies a percentage score into High, Medium, or Low sustainability level."""
    if percentage >= 75.0:
        return "High"
    elif percentage >= 40.0:
        return "Medium"
    else:
        return "Low"


def calculate_score_and_level(
    product_type: Literal["Textile_product", "Acoustic_product", "Lighting_product"],
    llm_mask: list[Optional[bool]],
) -> dict:
    """Calculates points, maximum points, percentage and level."""
    product = get_product_config(product_type)
    points = calculate(product_type, llm_mask)
    max_points = product.total_max_points
    percentage = (points / max_points * 100) if max_points > 0 else 0.0
    level = calculate_level(percentage)

    return {
        "points": points,
        "max_points": max_points,
        "percentage": round(percentage, 2),
        "level": level,
    }