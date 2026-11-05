from typing import Annotated, Self
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator
from .models import QuestionType

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(max_length=5000)]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class Login(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class AccountLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=254)
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value):
        return value.casefold()


class Register(AccountLogin):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
    password: Annotated[str, StringConstraints(min_length=12, max_length=128)]


class ScheduleInput(BaseModel):
    scheduled_at: datetime

    @field_validator("scheduled_at")
    @classmethod
    def future_time(cls, value):
        if not value.tzinfo or value.utcoffset() is None or value <= datetime.now(timezone.utc):
            raise ValueError("Alege o dată viitoare, cu fus orar.")
        return value


class RevisionInput(BaseModel):
    expected_revision: int = Field(ge=0)


class ParticipantUpdate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]


class CompetitionInput(BaseModel):
    title: Title
    description: Description = ""


class EditionInput(BaseModel):
    name: Title
    description: Description = ""
    password: Password


class EditionUpdate(BaseModel):
    name: Title
    description: Description = ""
    password: Password | None = None


class OptionInput(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    is_correct: bool = False


class QuestionInput(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]
    type: QuestionType
    options: list[OptionInput] = Field(min_length=2, max_length=20)

    @model_validator(mode="after")
    def validate_correct(self) -> Self:
        count = sum(o.is_correct for o in self.options)
        if self.type == QuestionType.SINGLE_CHOICE and count != 1:
            raise ValueError("O întrebare cu răspuns unic trebuie să aibă exact o variantă corectă.")
        if self.type == QuestionType.MULTIPLE_CHOICE and count < 2:
            raise ValueError("O întrebare cu răspuns multiplu trebuie să aibă minimum două variante corecte.")
        return self


class Join(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class AnswerInput(BaseModel):
    question_id: int = Field(gt=0)
    option_ids: list[int] = Field(min_length=1, max_length=20)


class NextInput(BaseModel):
    expected_question_id: int = Field(gt=0)


class ReorderInput(BaseModel):
    question_ids: list[int] = Field(max_length=10000)
