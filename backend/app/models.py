from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class UTCDateTime(TypeDecorator):
    """SQLite drops timezone metadata; return aware UTC on both database engines."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return value.astimezone(timezone.utc) if value is not None else None

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def utcnow():
    return datetime.now(timezone.utc)


class Status(str, Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    WAITING = "WAITING"
    LIVE = "LIVE"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"


class QuestionType(str, Enum):
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"


class Role(str, Enum):
    ADMIN = "ADMIN"
    USER = "USER"


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str | None] = mapped_column(String(80), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[Role] = mapped_column(SAEnum(Role, name="account_role"), default=Role.USER, server_default="USER")
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


# Compatibility for existing server-side integrations; authorization uses Role.
Admin = Account


class Competition(Base):
    __tablename__ = "competitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    editions: Mapped[list["Edition"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)


class Edition(Base):
    __tablename__ = "editions"
    __table_args__ = (CheckConstraint("current_index >= -1"), CheckConstraint("revision >= 0"))
    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    status: Mapped[Status] = mapped_column(SAEnum(Status, name="edition_status"), default=Status.DRAFT)
    current_index: Mapped[int] = mapped_column(default=-1)
    revision: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    scheduled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    results_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    questions: Mapped[list["Question"]] = relationship(cascade="all, delete-orphan", passive_deletes=True, order_by="Question.position")
    participants: Mapped[list["Participant"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("edition_id", "position", deferrable=True, initially="DEFERRED").ddl_if(dialect="postgresql"), UniqueConstraint("edition_id", "position").ddl_if(dialect="sqlite"), CheckConstraint("position >= 0"))
    id: Mapped[int] = mapped_column(primary_key=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("editions.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    type: Mapped[QuestionType] = mapped_column(SAEnum(QuestionType, name="question_type"))
    position: Mapped[int] = mapped_column(Integer)
    options: Mapped[list["QuestionOption"]] = relationship(cascade="all, delete-orphan", passive_deletes=True, order_by="QuestionOption.position")


class QuestionOption(Base):
    __tablename__ = "question_options"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    position: Mapped[int] = mapped_column(Integer)


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (UniqueConstraint("edition_id", "normalized_name"), UniqueConstraint("edition_id", "account_id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("editions.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    normalized_name: Mapped[str] = mapped_column(String(160))
    joined_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    final_score: Mapped[int | None] = mapped_column(Integer)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ParticipantAnswer(Base):
    __tablename__ = "participant_answers"
    __table_args__ = (UniqueConstraint("participant_id", "question_id"), CheckConstraint("points IN (0, 1)"))
    id: Mapped[int] = mapped_column(primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    points: Mapped[int] = mapped_column(Integer)
    submitted_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    selections: Mapped[list["AnswerSelection"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)


class AnswerSelection(Base):
    __tablename__ = "answer_selections"
    __table_args__ = (UniqueConstraint("answer_id", "option_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    answer_id: Mapped[int] = mapped_column(ForeignKey("participant_answers.id", ondelete="CASCADE"), index=True)
    option_id: Mapped[int] = mapped_column(ForeignKey("question_options.id", ondelete="CASCADE"))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (CheckConstraint("(account_id IS NULL) <> (participant_id IS NULL)"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf: Mapped[str] = mapped_column(String(64))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    participant_id: Mapped[int | None] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
