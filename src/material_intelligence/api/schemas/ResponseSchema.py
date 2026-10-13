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
