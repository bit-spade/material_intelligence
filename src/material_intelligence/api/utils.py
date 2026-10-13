import json
import base64
from material_intelligence.config import QUESTIONNAIRE_DIR

def load_questionnaire(category: str):
    file_path = QUESTIONNAIRE_DIR / f"{category}.json"
    if not file_path.exists():
        from pathlib import Path
        alt_path = Path(__file__).resolve().parents[3] / "data" / f"{category}.json"
        if alt_path.exists():
            file_path = alt_path
    questionnaire = json.loads(file_path.read_text(encoding="utf-8"))
    return questionnaire

def attach(file):
    return {
        "type": "media",
        "mime_type": file.type,  
        "data": base64.b64encode(file.getvalue()).decode(),
    }
