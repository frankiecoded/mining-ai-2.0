"""
Token Conservation Policy — deterministic budget math, zero LLM calls.

Every heuristic here deliberately runs in O(n) and never spends a modelling
token to *plan* token savings. The policy mirrors a plain sliding-window +
rolling-summary strategy so the assistant stays fully cooperative: the system
brief and the most recent exchanges are always preserved verbatim; only the
aged middle of a session is folded into a compact summary.

Entry points
------------
- ``estimate_tokens(text)``       cheap chars/4 estimator (result is "tokens")
- ``estimate_messages_tokens()``  sum over a LangChain message list
- ``pack_messages()``             fit a whole message list inside a budget
- ``truncate_text()``             headline-safe char limiter

The adapter and orchestrator both import these so a single definition of the
budget lives in one place.
"""

from typing import Callable, List, Optional

from langchain_core.messages import BaseMessage, SystemMessage

#: Human-read label used by the roll-up message so the model can distinguish
#: summarised "old" context from real persisted history.
_ROLLUP_LABEL = "[Earlier conversation summary (condensed to save tokens)]"

#: Hard cap per message when folding old turns into the roll-up summary.
_ROLLUP_MSG_CHARS = 200


def estimate_tokens(text) -> int:
    """Cheap token estimate. ~4 chars/token for ASCII; longer content is still
    linear, so this is a stable ordering metric even where it is not exact."""
    if not text:
        return 0
    return max(1, len(str(text)) // 4)


def estimate_messages_tokens(messages) -> int:
    return sum(estimate_tokens(getattr(m, "content", "")) for m in messages)


def truncate_text(text: str, max_chars: int) -> str:
    """Headline-safe truncation: never split inside a word, always append an
    ellipsis so no one mistakes the cut for the real ending."""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1]
    cut = cut.rsplit(" ", 1)[0] if " " in cut else cut
    return cut + "…"


def _role_label(msg: BaseMessage) -> str:
    t = getattr(msg, "type", "")
    if t == "human":
        return "User"
    if t == "ai":
        return "Assistant"
    if t == "tool":
        return "Tool result"
    if t == "system":
        return "System"
    return t or "Message"


def build_rollup(old_messages: List[BaseMessage]) -> SystemMessage:
    """Compress many old messages into one summary SystemMessage. One-line per
    original message keeps the information, but a fraction of the tokens."""
    parts = []
    for msg in old_messages:
        label = _role_label(msg)
        content = str(getattr(msg, "content", ""))[: _ROLLUP_MSG_CHARS].replace("\n", " ")
        if content:
            parts.append(f"{label}: {content}")
    return SystemMessage(content=_ROLLUP_LABEL + ("\n" + "\n".join(parts) if parts else ""))


def pack_messages(
    messages: List[BaseMessage],
    budget_tokens: int,
    keep_recent: int = 6,
    min_recent: int = 4,
) -> List[BaseMessage]:
    """Fit ``messages`` inside ``budget_tokens`` without losing cooperation.

    Guarantees
    ----------
    - Every ``system`` message is kept verbatim (the agent brief / persona).
    - The most recent ``keep_recent`` non-system messages are kept verbatim.
    - Older non-system turns are folded into a single compact summary that is
      itself truncated to the *remaining* budget, so the final array fits.
    - If the system block plus the minimum recent tail alone still exceed the
      budget, the summary is dropped before newer history (newest always wins).

    The estimate is deterministic (chars/4), so the returned array is sized to
    the budget without any LLM round-trip.
    """
    if not messages:
        return messages
    if estimate_messages_tokens(messages) <= budget_tokens:
        return messages

    system_msgs = [m for m in messages if m.type == "system"]
    non_system = [m for m in messages if m.type != "system"]
    if len(non_system) <= min_recent:
        # Nothing safe to fold without dropping the user's current question.
        return messages

    if len(non_system) <= keep_recent:
        # Everything is recent — keep it all rather than invent a summary.
        return messages

    recent = non_system[-keep_recent:]
    older = non_system[:-keep_recent]

    budget_after = max(8, budget_tokens - estimate_messages_tokens(system_msgs) - estimate_messages_tokens(recent))

    folded = list(older)
    rollup_chars = budget_after * 4
    rollup = build_rollup(folded)
    if estimate_messages_tokens([rollup]) > budget_after:
        rollup = SystemMessage(content=truncate_text(rollup.content, rollup_chars))

    while estimate_messages_tokens(system_msgs + [rollup] + recent) > budget_tokens and len(recent) > min_recent:
        folded.append(recent[0])
        recent = recent[1:]
        rollup = build_rollup(folded)
        if estimate_messages_tokens([rollup]) > budget_after:
            rollup = SystemMessage(content=truncate_text(rollup.content, rollup_chars))

    result = system_msgs + [rollup] + recent
    if estimate_messages_tokens(result) > budget_tokens:
        # Hard floor: keep the system brief + the minimum recent tail verbatim.
        return system_msgs + recent
    return result


def allocate_sections(
    sections: List[tuple[str, str]],
    budget_chars: int,
    keep_order: bool = True,
) -> List[tuple[str, str]]:
    """Greedy char-budget allocator for named system-prompt sections.

    Sections are (label, body) pairs. Returns the sections that fit, dropping
    lowest-priority tail sections first and truncating the final kept one.
    Intended for bounding pre-built text blocks (RAG snippets, digests) before
    they are rendered into the system prompt.
    """
    fitted: List[tuple[str, str]] = []
    used = 0
    for label, body in sections:
        remaining = budget_chars - used
        if remaining <= 0:
            break
        if len(body) > remaining:
            fitted.append((label, truncate_text(body, remaining)))
            used += remaining
            break
        fitted.append((label, body))
        used += len(body)
    return fitted