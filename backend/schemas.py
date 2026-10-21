from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=24000)
    interrupted: bool = False


class ReplyRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=100)
    opening: bool = False
    turns: list[Turn] = Field(default_factory=list, max_length=1000)


class ReportRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=100)
    turns: list[Turn] = Field(max_length=1000)


class SpeechRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=24000)


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["grammar", "word choice", "clarity", "simplification"]
    quote: str = Field(min_length=1, max_length=2000)
    suggestion: str = Field(min_length=1, max_length=2000)
    explanation: str = Field(min_length=1, max_length=2000)


class ReportFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=2000)
    findings: list[Finding]


class Feedback(ReportFeedback):
    """Bound each model response; combined reports may contain more findings."""
    findings: list[Finding] = Field(max_length=12)


class CompletedSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    created_at: AwareDatetime
    completed_at: AwareDatetime
    turns: list[Turn] = Field(min_length=1, max_length=1000)
    report_text: str = Field(min_length=1, max_length=100000)

    @model_validator(mode="after")
    def completed_session(self):
        if self.completed_at < self.created_at:
            raise ValueError("Completion must follow creation.")
        if not self.report_text.strip():
            raise ValueError("A completed report is required.")
        return self
