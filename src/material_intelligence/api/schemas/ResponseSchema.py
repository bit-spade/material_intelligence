import pydantic
from pydantic import BaseModel, Field

class ResponseSchema(BaseModel):
    green_index: int = Field(description="Green index of the material from 1 to 10 (1 is worst, 10 is best)")
    green_level: str = Field(description="Green level of the material from G to A (G is worst, A is best)")
    
    