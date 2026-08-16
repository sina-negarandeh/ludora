from pydantic import BaseModel, Field

class AspectMiniSummary(BaseModel):
    aspect: str = Field(description="The name of the aspect being summarized")
    summary: str = Field(description="A concise summary of what customers say about this aspect")
    sentiment: str = Field(description="The overall sentiment of the reviews for this aspect (e.g., 'mostly_positive', 'mixed', 'mostly_negative')")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0 representing how strongly the reviews agree on this sentiment")

class FinalGameSummary(BaseModel):
    summary: str = Field(description="The final 2-3 sentence 'Customers say' paragraph summarizing the game's reviews")
