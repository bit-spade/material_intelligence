import json
import os
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from material_intelligence.api.schemas.ResponseSchema import RecommendationResult
from material_intelligence.api.utils import load_questionnaire
from material_intelligence.config import SYSTEM_PROMPT_RECOMMENDATION


def get_sustainable_recommendations(
    category: str,
    baseline_result: dict,
    project_priorities: Optional[str] = None,
    api_key: Optional[str] = None,
) -> RecommendationResult:
    """Analyze a baseline product's ECO-SCORE results and generate market recommendations.

    Args:
        category: The material category key (e.g. 'Textile_product')
        baseline_result: The dictionary returned by run_assessment()
        project_priorities: Optional additional context or designer priorities
        api_key: Gemini API key (defaults to GEMINI_API_KEY env var)

    Returns:
        RecommendationResult instance with baseline analysis and alternative products.
    """
    api_key = api_key or os.getenv("GEMINI_API_KEY")
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite", api_key=api_key, temperature=0.2
    ).with_structured_output(RecommendationResult)

    questionnaire = load_questionnaire(category)

    # Format the baseline performance clearly for the LLM
    unmet_criteria = []
    supported_criteria = []
    for r in baseline_result.get("rows", []):
        entry = f"[{r['id']}] {r['text']} (State: {r['state']}, Max points: {r['points']})"
        if r["state"] == "supported":
            supported_criteria.append(entry)
        else:
            unmet_criteria.append(entry)

    prompt_content = f"""PRODUCT EVALUATION CONTEXT
Category: {category}
Product Name: {baseline_result.get('product', 'Unknown')}
Calculated ECO-SCORE: {baseline_result.get('percentage', 0):.0f}% ({baseline_result.get('points', 0)} / {baseline_result.get('max_points', 0)} pts)
Assigned Sustainability Tier: {baseline_result.get('level', 'Unknown')}

USER / DESIGNER PROJECT PRIORITIES:
{project_priorities.strip() if project_priorities and project_priorities.strip() else 'Standard interior specification (prioritize higher overall ECO-SCORE, circularity, verified certificates)'}

SUPPORTED CRITERIA (Strengths):
{chr(10).join(supported_criteria) if supported_criteria else 'None'}

UNMET OR UNVERIFIED CRITERIA (Improvement Opportunities):
{chr(10).join(unmet_criteria) if unmet_criteria else 'None'}

CATEGORY QUESTIONNAIRE REFERENCE:
{json.dumps(questionnaire, ensure_ascii=False, indent=2)}

TASK:
Analyze the product's baseline performance, identify key environmental shortcomings based on the criteria above, and recommend 2-3 real, commercially available alternative products that outperform the baseline product.
"""

    response = llm.invoke(
        [
            SystemMessage(SYSTEM_PROMPT_RECOMMENDATION),
            HumanMessage(content=prompt_content),
        ]
    )
    return response