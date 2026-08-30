"""Conversation memory (M12): contextualize follow-ups, then answer + persist.

A follow-up like "What house is he in?" can't be retrieved directly ("he"
matches nothing). We rewrite it into a standalone question using recent history,
answer that, and append both turns to the conversation.
"""
from __future__ import annotations

from ..db.models import Conversation, Message, User
from ..db.repositories import ConversationRepository
from ..llm import get_llm
from .qa import Answer, answer_question

CONTEXTUALIZE_SYSTEM = (
    "You rewrite a follow-up question into a standalone question using the "
    "conversation so far. Resolve pronouns/references (e.g. 'he', 'that house') "
    "to what they refer to. Keep the same language. Return ONLY the question."
)

_HISTORY_TURNS = 6  # last N messages used for the rewrite


def contextualize(history: list[Message], question: str) -> str:
    """Rewrite a follow-up into a standalone question. No history -> unchanged."""
    if not history:
        return question
    convo = "\n".join(f"{m.role}: {m.content}" for m in history)
    prompt = (
        "Given the conversation history and a follow-up question, rewrite the "
        "follow-up as a STANDALONE question understandable without the history.\n\n"
        f"CONVERSATION:\n{convo}\n\n"
        f"FOLLOW-UP: {question}\n\n"
        "STANDALONE QUESTION:"
    )
    rewritten = get_llm().complete(prompt, system=CONTEXTUALIZE_SYSTEM).strip()
    return rewritten or question


def ask_in_conversation(
    db, user: User, conversation: Conversation, question: str,
    answer_language: str | None = None,
) -> Answer:
    repo = ConversationRepository(db)
    history = repo.recent_messages(conversation.id, limit=_HISTORY_TURNS)
    standalone = contextualize(history, question)

    answer = answer_question(db, user, standalone, answer_language=answer_language)

    # Persist the turn (store the user's ORIGINAL question, not the rewrite).
    repo.add_message(conversation.id, "user", question)
    repo.add_message(conversation.id, "assistant", answer.answer)
    return answer
