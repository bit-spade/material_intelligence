from pydantic import BaseModel, Field

class ResponseSchema(BaseModel):
    green_index: int = Field(description="Green index of the material from 1 to 10 (1 is worst, 10 is best)")
    green_level: str = Field(description="Green level of the material from G to A (G is worst, A is best)")
    incorrect_input: bool = Field(description="True if the user input is not a material, False otherwise")
    suggestion_to_improve_input: str = Field(description="Suggestion to improve the input if it is not a material")