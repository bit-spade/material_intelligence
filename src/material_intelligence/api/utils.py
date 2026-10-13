import json
import base64
from material_intelligence.config import QUESTIONNAIRE_DIR

def load_questionnaire(category: str):
    questionnaire = json.loads(
        (QUESTIONNAIRE_DIR / f"{category}.json").read_text(encoding="utf-8")
    )
    return questionnaire

def attach(file):
    return {
        "type": "media",
        "mime_type": file.type,  
        "data": base64.b64encode(file.getvalue()).decode(),
    }
