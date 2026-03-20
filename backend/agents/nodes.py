import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.json_utils import try_parse_json_dict
from agents.prompts import WRITER_SYSTEM_PROMPT
from agents.qa_similarity import (
    ARTIFACT_QA_FEEDBACK,
    ARTIFACT_QA_LAST_FEEDBACK,
    ARTIFACT_QA_STAGNANT_LOOP,
    MIN_QA_FEEDBACK_CHARS,
    STAGNANT_SIMILARITY_THRESHOLD,
    previous_qa_feedback_from_state,
    semantic_similarity_pair,
    stagnant_artifacts,
)
from agents.state import LOOP_COUNTER_STEP, OfficeState
from agents.thoughts import emit_thought
from core.config import settings
from memory_service import (
    ARTIFACT_INTERNAL_KNOWLEDGE_CONTEXT,
    ARTIFACT_FINAL_DELIVERABLE,
    format_internal_knowledge_context,
    search_internal_knowledge,
)
from integrations.supplemental_research import fetch_supplemental_market_facts
from storage.output_store import save_writer_output

logger = logging.getLogger(__name__)


def _parse_research_json_to_markdown(text: str) -> str:
    data = try_parse_json_dict(text)
    if data is None:
        cleaned = text.strip()
        return cleaned if cleaned else "Research synthesis returned empty output."
    rn = str(data.get("research_notes") or "").strip()
    sources = data.get("sources") or []
    oq = data.get("open_questions") or []
    parts: list[str] = [rn] if rn else []
    if sources:
        lines: list[str] = []
        for i, s in enumerate(sources, 1):
            if isinstance(s, dict):
                t = str(s.get("title") or "").strip()
                u = str(s.get("url") or "").strip()
                lines.append(f"{i}. {t}" + (f" — {u}" if u else ""))
            else:
                lines.append(f"{i}. {s!s}")
        parts.append("### Sources (model-suggested)\n" + "\n".join(lines))
    if oq:
        oq_lines = [f"- {q}" for q in oq if str(q).strip()]
        if oq_lines:
            parts.append("### Open questions\n" + "\n".join(oq_lines))
    out = "\n\n".join(parts).strip()
    return out or rn


def _research_fallback_no_llm(
    topic: str, internal_ctx: str, supplemental: str, err: str
) -> str:
    parts: list[str] = []
    if internal_ctx.strip():
        parts.append("## Prior office memory\n\n" + internal_ctx.strip())
    if supplemental.strip():
        parts.append("## Supplemental market facts\n\n" + supplemental.strip())
    msg = (
        "## Research synthesis\n\n"
        "Configure `GOOGLE_API_KEY` for AI-generated research. "
        f"**Topic:** {topic}"
    )
    if err:
        msg += f"\n\n*(Last error: {err})*"
    parts.append(msg)
    return "\n\n---\n\n".join(parts)


async def _research_notes_via_llm(
    topic: str, internal_ctx: str, supplemental: str
) -> str:
    model = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=0.35,
    )
    prompt = f"""You are a professional researcher. Synthesize research notes for downstream Writer and Developer agents.

Topic: {topic}

--- Prior office memory (may be empty) ---
{internal_ctx or "(none)"}

--- Supplemental live snippets (may be empty) ---
{supplemental or "(none)"}

Rules:
- Output Markdown with headings (##, ###).
- Distinguish verified facts (from supplemental/API) from general synthesis.
- For time-sensitive topics (e.g. "last week"), state the implied date range in UTC and note uncertainty where data is incomplete.
- Do not label the output as mock or placeholder data.

Respond with ONE JSON object ONLY (no markdown fences) with this exact shape:
{{"research_notes": "<markdown string>", "sources": [{{"title": "string", "url": "string"}}], "open_questions": ["string"]}}
"""
    out = await model.ainvoke([HumanMessage(content=prompt)])
    text = out.content if isinstance(out.content, str) else str(out.content)
    return _parse_research_json_to_markdown(text)


def _parse_writer_payload(text: str) -> str:
    data = try_parse_json_dict(text)
    if data is None:
        cleaned = text.strip()
        return cleaned if cleaned else "# (Writer output empty)"
    payload = data.get("payload")
    if isinstance(payload, dict):
        wc = str(payload.get("written_content") or "").strip()
        if wc:
            return wc
    wc = str(data.get("written_content") or "").strip()
    return wc if wc else text.strip()


def _writer_fallback_markdown(
    topic: str,
    research_notes: str,
    dev_summary: str,
    developer_files: dict[str, str],
) -> str:
    lines: list[str] = [f"# {topic}", "", "## Research basis", research_notes[:12000]]
    if dev_summary.strip():
        lines.extend(["", "## Technical notes (Developer)", dev_summary[:8000]])
    if developer_files:
        lines.append("")
        lines.append("## Artifacts from sandbox")
        for k, v in list(developer_files.items())[:12]:
            excerpt = (v or "")[:2000]
            lines.append(f"### `{k}`")
            lines.append(f"```\n{excerpt}\n```")
    lines.extend(
        [
            "",
            "---",
            "*Set `GOOGLE_API_KEY` for an AI-polished narrative; this draft was assembled from artifacts without the Writer LLM.*",
        ]
    )
    return "\n".join(lines)


async def _written_content_via_llm(
    topic: str,
    research_notes: str,
    dev_summary: str,
    developer_files: dict[str, str],
) -> str:
    model = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=0.35,
    )
    if developer_files:
        chunks: list[str] = []
        for path, body in list(developer_files.items())[:12]:
            excerpt = (body or "")[:4000]
            chunks.append(f"### {path}\n```\n{excerpt}\n```\n")
        files_blob = "\n".join(chunks)
    else:
        files_blob = "(none)"

    user_msg = f"""Topic / request: {topic}

## Research notes (from Researcher)
{research_notes}

## Developer summary
{dev_summary or "(none)"}

## Files produced in sandbox (excerpts)
{files_blob}

Produce the final deliverable document as Markdown using the above. Do not invent facts beyond what is supported; mark gaps as TBD.

Return ONE JSON object ONLY (no markdown fences) with this shape:
{{"schema_version":"1.0","role":"writer","payload":{{"written_content":"<full markdown string>","format":"markdown","dependencies_on_research":["string"]}}}}
"""
    out = await model.ainvoke(
        [
            SystemMessage(content=WRITER_SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ]
    )
    text = out.content if isinstance(out.content, str) else str(out.content)
    return _parse_writer_payload(text)


async def research_node(state: OfficeState) -> dict:
    topic = state.get("topic", "the task")
    await emit_thought("pm", f"Scoping research priorities for: {topic}")

    matches = await search_internal_knowledge(topic, topic, top_k=5)
    internal_ctx = format_internal_knowledge_context(matches)
    if matches:
        await emit_thought(
            "researcher",
            f"Retrieved {len(matches)} prior memory snippet(s) before external research.",
        )
    else:
        await emit_thought(
            "researcher",
            "No matching prior office memory — proceeding with fresh research.",
        )

    supplemental = await fetch_supplemental_market_facts(topic)
    if supplemental:
        await emit_thought(
            "researcher",
            "Merged supplemental market facts (e.g. spot quotes) into research context.",
        )

    if settings.google_api_key:
        try:
            research_notes = await _research_notes_via_llm(topic, internal_ctx, supplemental)
        except Exception as e:
            logger.exception("Research LLM failed")
            await emit_thought("researcher", f"Research LLM error: {e!s} — using fallback notes.")
            research_notes = _research_fallback_no_llm(topic, internal_ctx, supplemental, str(e))
    else:
        research_notes = _research_fallback_no_llm(topic, internal_ctx, supplemental, "")

    msg_excerpt = research_notes[:280] + ("…" if len(research_notes) > 280 else "")
    return {
        **LOOP_COUNTER_STEP,
        "messages": [
            {
                "role": "researcher",
                "content": f"Research notes for «{topic}»: {msg_excerpt}",
            }
        ],
        "current_phase": "research",
        "artifacts": {
            ARTIFACT_INTERNAL_KNOWLEDGE_CONTEXT: internal_ctx,
            "research_notes": research_notes,
        },
        "agent_status": {
            "pm": "thinking",
            "researcher": "working",
            "developer": "idle",
            "writer": "idle",
            "qa": "idle",
        },
    }


async def writer_node(state: OfficeState) -> dict:
    topic = state.get("topic", "the task")
    artifacts = state.get("artifacts") or {}
    notes = str(artifacts.get("research_notes", "") or "")
    dev_summary = str(artifacts.get("developer_summary", "") or "")
    dev_files: dict[str, str] = dict(artifacts.get("developer_files") or {})
    await emit_thought(
        "writer",
        f"Drafting deliverable from research notes: {notes[:100]}…",
    )

    if settings.google_api_key:
        try:
            draft_body = await _written_content_via_llm(topic, notes, dev_summary, dev_files)
        except Exception as e:
            logger.exception("Writer LLM failed")
            await emit_thought("writer", f"Writer LLM error: {e!s} — assembling artifact-only draft.")
            draft_body = _writer_fallback_markdown(topic, notes, dev_summary, dev_files)
    else:
        draft_body = _writer_fallback_markdown(topic, notes, dev_summary, dev_files)

    writer_file = await save_writer_output(topic, draft_body, ".md")
    return {
        **LOOP_COUNTER_STEP,
        "messages": [
            {
                "role": "writer",
                "content": f"Written deliverable for «{topic}» ({len(draft_body)} chars).",
            }
        ],
        "current_phase": "write",
        "artifacts": {
            "written_content": draft_body,
            ARTIFACT_FINAL_DELIVERABLE: draft_body,
            "writer_file": writer_file,
        },
        "agent_status": {
            "pm": "idle",
            "researcher": "idle",
            "developer": "idle",
            "writer": "working",
            "qa": "idle",
        },
    }


async def _generate_qa_feedback_text(topic: str, draft: str) -> str:
    if not settings.google_api_key:
        return (
            f"QA review: Strengthen alignment with the style guide for «{topic}»; "
            "clarify section headings and ensure research/developer signals are reflected consistently."
        )
    model = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=0.4,
    )
    prompt = (
        "You are QA. Respond with one short paragraph of actionable feedback (plain text, no JSON). "
        "Focus on: correctness, clarity, risk, and style/tone.\n\n"
        f"Topic: {topic}\n\nDraft:\n{draft[:6000]}"
    )
    out = await model.ainvoke([HumanMessage(content=prompt)])
    text = out.content if isinstance(out.content, str) else str(out.content)
    return (text or "").strip() or "QA: Verify formatting and citations."


async def qa_node(state: OfficeState) -> dict:
    """QA review with stagnant-loop detection vs prior QA feedback."""
    topic = state.get("topic", "the task")
    draft = str((state.get("artifacts") or {}).get(ARTIFACT_FINAL_DELIVERABLE, "") or "")
    await emit_thought("qa", "Reviewing draft; checking for stagnant feedback vs prior QA.")

    feedback = await _generate_qa_feedback_text(topic, draft)
    prev = previous_qa_feedback_from_state(state)

    stagnant = False
    sim = 0.0
    if (
        prev
        and len(prev) >= MIN_QA_FEEDBACK_CHARS
        and len(feedback) >= MIN_QA_FEEDBACK_CHARS
    ):
        sim = await semantic_similarity_pair(prev, feedback)
        if sim > STAGNANT_SIMILARITY_THRESHOLD:
            stagnant = True

    msg_body = feedback
    if stagnant:
        msg_body = (
            f"{feedback}\n\n[Stagnant Loop detected: similarity to prior QA feedback ~{sim:.0%} — "
            "escalating to Office Manager.]"
        )

    if stagnant:
        artifacts_out = stagnant_artifacts(sim, feedback)
    else:
        artifacts_out = {
            ARTIFACT_QA_FEEDBACK: feedback,
            ARTIFACT_QA_STAGNANT_LOOP: False,
            ARTIFACT_QA_LAST_FEEDBACK: feedback,
        }

    if stagnant:
        tf = (
            f"[QA] Stagnant loop — similarity {sim:.2f} > {STAGNANT_SIMILARITY_THRESHOLD}; "
            "escalating to Office Manager."
        )
    elif prev and len(prev) >= MIN_QA_FEEDBACK_CHARS and len(feedback) >= MIN_QA_FEEDBACK_CHARS:
        tf = f"[QA] Feedback recorded (vs prior similarity {sim:.2f})."
    else:
        tf = "[QA] Initial feedback recorded."

    return {
        **LOOP_COUNTER_STEP,
        "messages": [{"role": "qa", "content": msg_body}],
        "current_phase": "qa",
        "artifacts": artifacts_out,
        "agent_status": {
            "pm": "idle",
            "researcher": "idle",
            "developer": "idle",
            "writer": "idle",
            # Node finished; "working" here never got cleared because state merges by key only.
            "qa": "idle",
        },
        "terminal_feed": [tf],
    }
