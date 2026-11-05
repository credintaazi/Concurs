import unicodedata
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .models import (AnswerSelection, Competition, Edition, Participant, ParticipantAnswer,
                     Question, QuestionOption, QuestionType, Status, utcnow)
from .schemas import AnswerInput, QuestionInput


def get_or_404(db: Session, model, identity):
    value = db.get(model, identity)
    if not value:
        raise HTTPException(404, "Resursa nu există.")
    return value


def lock_edition(db: Session, edition_id: int) -> Edition:
    edition = db.scalar(select(Edition).where(Edition.id == edition_id).with_for_update().execution_options(populate_existing=True))
    if not edition:
        raise HTTPException(404, "Ediția nu există.")
    return edition


def require_editable(edition: Edition):
    if edition.status not in {Status.DRAFT, Status.SCHEDULED, Status.WAITING}:
        raise HTTPException(409, "Întrebările și ediția sunt blocate după START.")


def questions_for(db: Session, edition_id: int):
    return list(db.scalars(select(Question).where(Question.edition_id == edition_id).order_by(Question.position)))


def question_data(question: Question, reveal=False):
    return {"id": question.id, "text": question.text, "type": question.type, "position": question.position,
            "options": [{"id": o.id, "text": o.text, **({"is_correct": o.is_correct} if reveal else {})} for o in question.options]}


def competition_data(c: Competition, db: Session | None = None):
    result = {"id": c.id, "title": c.title, "description": c.description, "created_at": c.created_at}
    if db is not None:
        editions = list(db.scalars(select(Edition).where(Edition.competition_id == c.id)))
        priority = [Status.LIVE, Status.PAUSED, Status.WAITING, Status.SCHEDULED, Status.DRAFT, Status.FINISHED]
        result.update(status=next((s for s in priority if any(e.status == s for e in editions)), Status.DRAFT),
                      edition_count=len(editions),
                      participant_count=db.scalar(select(func.count()).select_from(Participant).join(Edition).where(Edition.competition_id == c.id)),
                      live_edition_id=next((e.id for e in editions if e.status in {Status.LIVE, Status.PAUSED}), None))
    return result


def edition_data(db: Session, e: Edition):
    return {"id": e.id, "competition_id": e.competition_id, "name": e.name, "description": e.description,
            "status": e.status, "current_index": e.current_index, "revision": e.revision,
            "created_at": e.created_at, "started_at": e.started_at, "finished_at": e.finished_at,
            "scheduled_at": e.scheduled_at, "results_published": e.results_published,
            "total_questions": db.scalar(select(func.count()).select_from(Question).where(Question.edition_id == e.id)),
            "participant_count": db.scalar(select(func.count()).select_from(Participant).where(Participant.edition_id == e.id)),
            "active_participant_count": db.scalar(select(func.count()).select_from(Participant).where(Participant.edition_id == e.id, Participant.is_active.is_(True)))}


def state_data(db: Session, edition_id: int, participant: Participant | None = None):
    # One row lock makes the edition, question and counters one coherent snapshot.
    e = lock_edition(db, edition_id)
    if participant is not None:
        db.refresh(participant)
        if not participant.is_active:
            raise HTTPException(403, "Participarea ta a fost închisă de administrator.")
    questions = questions_for(db, e.id)
    current = questions[e.current_index] if e.status in {Status.LIVE, Status.PAUSED} else None
    result = {**edition_data(db, e), "competition_title": get_or_404(db, Competition, e.competition_id).title,
              "question": question_data(current, reveal=participant is None) if current else None}
    if participant:
        answer = db.scalar(select(ParticipantAnswer).where(ParticipantAnswer.participant_id == participant.id,
                                                         ParticipantAnswer.question_id == current.id)) if current else None
        result.update(participant={"id": participant.id, "name": participant.name}, answered=answer is not None,
                      selected_option_ids=[s.option_id for s in answer.selections] if answer else [])
    else:
        result["answer_count"] = db.scalar(select(func.count()).select_from(ParticipantAnswer).join(Participant).where(
            ParticipantAnswer.question_id == current.id, Participant.is_active.is_(True))) if current else 0
    return result


def save_question(db: Session, edition: Edition, payload: QuestionInput, question: Question | None = None):
    require_editable(edition)
    if question is None:
        position = db.scalar(select(func.max(Question.position)).where(Question.edition_id == edition.id))
        question = Question(edition_id=edition.id, position=0 if position is None else position + 1)
        db.add(question)
    question.text, question.type = payload.text, payload.type
    question.options = [QuestionOption(text=o.text, is_correct=o.is_correct, position=i) for i, o in enumerate(payload.options)]
    edition.revision += 1
    db.flush()
    return question


def normalize_name(name: str):
    return unicodedata.normalize("NFKC", " ".join(name.split())).casefold()


def transition(db: Session, edition_id: int, command: str, expected_question_id: int | None = None,
               expected_revision: int | None = None):
    e = lock_edition(db, edition_id)
    questions = questions_for(db, e.id)
    if expected_revision is not None and e.revision != expected_revision:
        raise HTTPException(409, "Starea ediției s-a schimbat. Verifică și repetă comanda.")
    if command == "open":
        if e.status == Status.WAITING:
            return e
        if e.status not in {Status.DRAFT, Status.SCHEDULED}:
            raise HTTPException(409, "Ediția nu poate fi redeschisă.")
        if not questions:
            raise HTTPException(409, "Adaugă minimum o întrebare înainte de deschidere.")
        e.status = Status.WAITING
    elif command == "start":
        if e.status == Status.LIVE:
            return e
        if e.status != Status.WAITING or not questions:
            raise HTTPException(409, "Doar o ediție deschisă, cu întrebări, poate începe.")
        e.status, e.current_index, e.started_at = Status.LIVE, 0, utcnow()
    elif command in {"pause", "resume"}:
        required = Status.LIVE if command == "pause" else Status.PAUSED
        if e.status != required:
            raise HTTPException(409, "Tranziția pauză/reluare nu este validă pentru starea curentă.")
        e.status = Status.PAUSED if command == "pause" else Status.LIVE
    elif command == "next":
        if e.status != Status.LIVE:
            raise HTTPException(409, "Concursul nu este LIVE.")
        if questions[e.current_index].id != expected_question_id:
            raise HTTPException(409, "Întrebarea s-a schimbat deja. Starea a fost actualizată.")
        if e.current_index + 1 >= len(questions):
            raise HTTPException(409, "Aceasta este ultima întrebare. Finalizează concursul.")
        e.current_index += 1
    elif command in {"finish", "stop"}:
        if e.status == Status.FINISHED:
            return e
        if command == "finish" and (e.status != Status.LIVE or e.current_index != len(questions) - 1):
            raise HTTPException(409, "Finalizarea este disponibilă doar la ultima întrebare.")
        if command == "stop" and e.status not in {Status.LIVE, Status.PAUSED}:
            raise HTTPException(409, "Poți opri doar un concurs început.")
        e.status, e.finished_at = Status.FINISHED, utcnow()
        e.results_published = True
        for participant in db.scalars(select(Participant).where(Participant.edition_id == e.id)):
            participant.final_score = db.scalar(select(func.coalesce(func.sum(ParticipantAnswer.points), 0)).where(
                ParticipantAnswer.participant_id == participant.id))
    e.revision += 1
    db.flush()
    return e


def submit_answer(db: Session, edition_id: int, participant: Participant, payload: AnswerInput):
    e = lock_edition(db, edition_id)
    db.refresh(participant)
    questions = questions_for(db, e.id)
    if not participant.is_active or e.status != Status.LIVE or questions[e.current_index].id != payload.question_id:
        raise HTTPException(409, "Întrebarea nu mai acceptă răspunsuri.")
    question = questions[e.current_index]
    ids = set(payload.option_ids)
    if len(ids) != len(payload.option_ids) or not ids.issubset({o.id for o in question.options}):
        raise HTTPException(422, "Variantele selectate nu sunt valide pentru această întrebare.")
    if question.type == QuestionType.SINGLE_CHOICE and len(ids) != 1:
        raise HTTPException(422, "Selectează o singură variantă.")
    if db.scalar(select(ParticipantAnswer.id).where(ParticipantAnswer.participant_id == participant.id,
                                                   ParticipantAnswer.question_id == question.id)):
        raise HTTPException(409, "Răspunsul a fost deja înregistrat și este final.")
    answer = ParticipantAnswer(participant_id=participant.id, question_id=question.id,
                               points=int(ids == {o.id for o in question.options if o.is_correct}))
    answer.selections = [AnswerSelection(option_id=option_id) for option_id in ids]
    db.add(answer)
    e.revision += 1
    db.flush()
    return e


def results_data(db: Session, edition_id: int, participant: Participant | None = None):
    e = lock_edition(db, edition_id)
    if e.status != Status.FINISHED or not e.results_published:
        raise HTTPException(409, "Rezultatele sunt disponibile doar după finalizare.")
    participants = list(db.scalars(select(Participant).where(Participant.edition_id == edition_id, Participant.is_active.is_(True)).order_by(
        Participant.final_score.desc(), Participant.normalized_name, Participant.id).execution_options(populate_existing=True)))
    rows, previous, rank = [], None, 0
    for index, p in enumerate(participants):
        if p.final_score != previous:
            rank = index + 1
        rows.append({"participant_id": p.id, "name": p.name, "score": p.final_score, "rank": rank})
        previous = p.final_score
    answers = list(db.scalars(select(ParticipantAnswer).where(ParticipantAnswer.participant_id == participant.id))) if participant else []
    return {"edition": edition_data(db, e), "leaderboard": rows,
            "your_score": participant.final_score if participant else None,
            "questions": [question_data(q, reveal=True) for q in questions_for(db, edition_id)],
            "your_answers": [{"question_id": a.question_id, "option_ids": [s.option_id for s in a.selections], "points": a.points} for a in answers]}


def live_leaderboard(db: Session, edition_id: int):
    e = lock_edition(db, edition_id)
    score = func.coalesce(func.sum(ParticipantAnswer.points), 0)
    rows = db.execute(select(Participant.id, Participant.name, score.label("score"), func.count(ParticipantAnswer.id).label("answered"))
        .outerjoin(ParticipantAnswer).where(Participant.edition_id == e.id, Participant.is_active.is_(True))
        .group_by(Participant.id).order_by(score.desc(), Participant.normalized_name, Participant.id))
    leaderboard, previous, rank = [], None, 0
    for index, row in enumerate(rows):
        if row.score != previous:
            rank = index + 1
        leaderboard.append({"participant_id": row.id, "name": row.name, "score": row.score, "answered": row.answered, "rank": rank})
        previous = row.score
    return {"status": e.status, "revision": e.revision, "leaderboard": leaderboard}
