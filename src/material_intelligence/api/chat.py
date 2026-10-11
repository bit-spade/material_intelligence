from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from material_intelligence.api.schemas.ResponseSchema import ResponseSchema

def llm_response(user_prompt, docs, api_key):
    llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", api_key=api_key, temperature=0.1)
    structured_llm = llm.with_structured_output(ResponseSchema)
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are an expert in material intelligence. Your task is to assess materials."),
        ("human", "{user_prompt}\n\nUse the following context to assess the material:\n\n{context}")
    ])
    
    chain = prompt_template | structured_llm
    
    context_text = "\n\n".join([doc.page_content for doc in docs])
    
    assessment = chain.invoke({
        "user_prompt": user_prompt, 
        "context": context_text
    })
    
    return (
        assessment.green_index, 
        assessment.green_level, 
        assessment.incorrect_input, 
        assessment.suggestion_to_improve_input
    )
