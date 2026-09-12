"""Unit tests for the token-conservation policy (local_model.token_policy)."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from local_model.token_policy import (
    allocate_sections,
    build_rollup,
    estimate_messages_tokens,
    estimate_tokens,
    pack_messages,
    truncate_text,
)


def _conv(n, prefix="user msg number "):
    msgs = [SystemMessage(content="SECRET SYSTEM BRIEF that must always survive")]
    for i in range(n):
        msgs.append(HumanMessage(content=f"{prefix}{i} " + "hello world " * 12))
        msgs.append(AIMessage(content=f"assistant reply {i} " + "ok " * 12))
    return msgs


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0


def test_estimate_tokens_rough_chars_per_4():
    assert estimate_tokens("four") == 1
    assert estimate_tokens("a" * 100) == 25


def test_estimate_messages_sum():
    msgs = [HumanMessage(content="a" * 40), AIMessage(content="b" * 40)]
    assert estimate_messages_tokens(msgs) == 20


def test_truncate_short_unchanged():
    assert truncate_text("short", 100) == "short"


def test_truncate_long_never_splits_word():
    out = truncate_text("the quick brown fox jumps", 12)
    assert out.endswith("…")
    assert out.startswith("the quick")
    assert len(out) <= 12


def test_truncate_when_budget_negative_returns_original():
    assert truncate_text("anything", -5) == "anything"


def test_pack_under_budget_is_identity():
    msgs = _conv(2)
    packed = pack_messages(msgs, budget_tokens=10_000)
    assert packed == msgs


def test_pack_preserves_system_brief():
    msgs = _conv(20)
    packed = pack_messages(msgs, budget_tokens=400)
    assert any(m.type == "system" and "SECRET SYSTEM BRIEF" in m.content for m in packed)


def test_pack_rolls_old_into_summary_keeps_recent():
    msgs = _conv(20)  # 40 non-system messages
    packed = pack_messages(msgs, budget_tokens=300, keep_recent=4, min_recent=3)
    rolls = [m for m in packed if m.type == "system" and "condensed to save tokens" in m.content]
    assert len(rolls) == 1
    # The final user turn must still be present verbatim.
    human_contents = [m.content for m in packed if m.type == "human"]
    assert msgs[-2].content in human_contents


def test_pack_fits_budget():
    msgs = _conv(30)
    budget = 500
    packed = pack_messages(msgs, budget_tokens=budget)
    assert estimate_messages_tokens(packed) <= budget or len([m for m in packed if m.type != "system"]) == 0


def test_pack_too_few_recent_returns_original():
    msgs = [SystemMessage(content="sys"), HumanMessage(content="hi")]
    packed = pack_messages(msgs, budget_tokens=2, keep_recent=6, min_recent=4)
    assert packed == msgs


def test_build_rollup_single_line_per_msg():
    old = [
        HumanMessage(content="tell me about drill grades"),
        AIMessage(content="Grades are measured in g/t gold."),
    ]
    rollup = build_rollup(old)
    assert "User: " in rollup.content
    assert "Assistant: " in rollup.content
    assert "g/t" in rollup.content


def test_allocate_sections_greedy_and_truncates_last():
    sections = [("a", "x" * 100), ("b", "y" * 100), ("c", "z" * 100)]
    fitted = allocate_sections(sections, budget_chars=220)
    assert fitted[0][0] == "a"
    assert fitted[1][0] == "b"
    assert len(fitted) == 3  # 'c' truncated to last ~20 chars
    assert fitted[2][1].endswith("…")


def test_allocate_sections_empty_budget():
    assert allocate_sections([("a", "x" * 10)], budget_chars=0) == []