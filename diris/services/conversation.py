"""Conversation orchestration: route each message (small talk vs document
question), answer, persist the turn, and maintain a rolling summary for long
chats. The router folds reference-resolution + translation into one LLM step.
"""
from __future__ import annotations

from ..db.models import Conversation, User
from ..db.repositories import ConversationRepository
from ..llm import get_llm
from .language import detect_language, translate_to_english
from .qa import Answer, answer_grounded
from .router import CONVERSATIONAL, route_message

_HISTORY_TURNS = 6       # recent messages passed to the router each turn
_SUMMARIZE_AFTER = 10    # start rolling-summarizing once a chat exceeds this many messages


def respond(
    db, user: User, question: str, history: str = "",
    answer_language: str | None = None, top_k: int = 6,
) -> Answer:
    """Route the message, then either reply conversationally or answer from docs.

    Non-English messages are translated to English *for routing* (free-tier models
    classify English far more reliably); the grounded answer is still written in the
    user's own language, anchored to the original question.
    """
    lang = detect_language(question)
    route_input = question if lang == "en" else translate_to_english(question)

    route = route_message(history, route_input)
    if route["category"] == CONVERSATIONAL and route.get("reply"):
        return Answer(
            answer=route["reply"], answered=True, confidence=1.0,
            citations=[], reasoning="conversational",
        )
    retrieval_query = route.get("query") or route_input
    return answer_grounded(
        db, user, retrieval_query, question, answer_language=answer_language, top_k=top_k
    )


def ask_in_conversation(
    db, user: User, conversation: Conversation, question: str,
    answer_language: str | None = None,
) -> Answer:
    repo = ConversationRepository(db)
    history = _history_text(repo, conversation)

    answer = respond(db, user, question, history=history, answer_language=answer_language)

    # Persist the turn (store the user's ORIGINAL question, not any rewrite).
    repo.add_message(conversation.id, "user", question)
    repo.add_message(conversation.id, "assistant", answer.answer)
    _maybe_summarize(repo, conversation.id)
    return answer


def _history_text(repo: ConversationRepository, conversation: Conversation) -> str:
    parts: list[str] = []
    if conversation.summary:
        parts.append(f"EARLIER SUMMARY:\n{conversation.summary}")
    recent = repo.recent_messages(conversation.id, limit=_HISTORY_TURNS)
    if recent:
        parts.append("RECENT MESSAGES:\n" + "\n".join(f"{m.role}: {m.content}" for m in recent))
    return "\n\n".join(parts)


def _maybe_summarize(repo: ConversationRepository, conversation_id: int) -> None:
    """Once a chat is long, fold everything older than the recent window into a
    rolling summary so memory survives beyond the last few turns."""
    messages = repo.messages(conversation_id)
    if len(messages) <= _SUMMARIZE_AFTER:
        return
    older = messages[:-_HISTORY_TURNS]
    if not older:
        return
    convo = "\n".join(f"{m.role}: {m.content}" for m in older)
    try:
        summary = get_llm().complete(
            "Summarize this conversation briefly (2-3 sentences), noting the topic "
            "and any key entities or constraints:\n\n" + convo
        ).strip()
        if summary:
            repo.set_summary(conversation_id, summary)
    except Exception:  # noqa: BLE001 — summarization is best-effort
        pass
