from pydantic import BaseModel, Field


class StandardResponse(BaseModel):
    """A standard response schema for simple confirmation messages or status."""

    detail: str = Field(
        ..., description="A message detailing the result of the operation."
    )
    success: bool = Field(
        True, description="Indicates if the operation was successful."
    )
