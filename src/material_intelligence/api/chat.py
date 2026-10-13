import json
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from material_intelligence.api.schemas.ResponseSchema import AnswersSchema
from material_intelligence.api.utils import attach, load_questionnaire
from material_intelligence.config import SYSTEM_PROMPT


def ask_llm(category, files, extra_notes, api_key=None):
    api_key = api_key or os.getenv("GEMINI_API_KEY")
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite", api_key=api_key, temperature=0
    ).with_structured_output(AnswersSchema)
    questionnaire = load_questionnaire(category)
    files = files or []
    content = [
        {
            "type": "text",
            "text": (
                f"QUESTIONNAIRE\n{json.dumps(questionnaire, ensure_ascii=False)}\n\n"
                f"ADDITIONAL NOTES FROM THE USER (may be empty)\n{extra_notes or 'none'}\n\n"
                "SOURCE MATERIAL: the attached documents. Answer every question."
            ),
        },
        *[attach(f) for f in files],
    ]

    answers = llm.invoke([SystemMessage(SYSTEM_PROMPT), HumanMessage(content=content)]).answers
    if len(answers) != len(questionnaire["questions"]):
        raise ValueError(f"Expected {len(questionnaire['questions'])} answers, got {len(answers)}")
    return answers

