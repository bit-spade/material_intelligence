from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from material_intelligence.api.schemas.ResponseSchema import ResponseSchema

def llm_response(material, api_key):
    llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", api_key=api_key, temperature=0.1)

    structured_llm = llm.with_structured_output(ResponseSchema)

    prompt = ChatPromptTemplate.from_messages([
    ("system", " You are expert in material intelligence. Your task is to assess materials."),
    ("human", "Assess the material: {material}")
])
    chain = prompt | structured_llm
    assessment = chain.invoke({"material": material})
    return assessment.green_index, assessment.green_level, assessment.incorrect_input, assessment.suggestion_to_improve_input