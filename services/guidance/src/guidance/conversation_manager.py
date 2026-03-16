"""Conversation manager — full chat with RAG, context window, and LLM tool use."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from gym_shared.db.session import get_db
from gym_shared.logging import get_logger
from gym_shared.redis_client import get_redis_ctx

from guidance.config import GuidanceConfig
from guidance.llm_client import GymLLMClient
from guidance.prompt_builder import PromptBuilder
from guidance.tool_definitions import TOOLS
from guidance.tool_executor import ToolExecutor

log = get_logger(__name__)

_MAX_REDIS_MESSAGES = 20  # messages kept hot in Redis per conversation
_SUMMARIZE_THRESHOLD = 20  # summarize when Redis list hits this count


def _conv_key(conversation_id: uuid.UUID) -> str:
    return f"conv:{conversation_id}:messages"


class ConversationManager:
    """Manages full multi-turn conversations between a user and the AI trainer.

    - Persists messages to DB (conversations + messages tables)
    - Keeps last 20 messages in Redis for fast context retrieval
    - Summarizes older messages when context exceeds threshold
    - Injects RAG knowledge chunks when relevant
    - Supports LLM tool calls for data retrieval
    """

    def __init__(self, config: GuidanceConfig, llm_client: GymLLMClient) -> None:
        self._config = config
        self._llm = llm_client
        self._prompt_builder = PromptBuilder()

    async def get_or_create_conversation(
        self,
        person_id: uuid.UUID,
        session_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Return existing open conversation or create a new one."""
        from gym_shared.db.models import Conversation

        async with get_db() as db:
            from sqlalchemy import select

            result = await db.execute(
                select(Conversation.id)
                .where(Conversation.person_id == person_id)
                .where(Conversation.session_id == session_id)
                .order_by(Conversation.started_at.desc())
                .limit(1)
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing

            conv = Conversation(person_id=person_id, session_id=session_id)
            db.add(conv)
            await db.flush()
            return conv.id

    async def send_message(
        self,
        conversation_id: uuid.UUID,
        person_id: uuid.UUID,
        user_text: str,
    ) -> str:
        """Process a user message and return the AI response text."""
        from gym_shared.db.models import Message

        # Persist user message
        async with get_db() as db:
            user_msg = Message(
                conversation_id=conversation_id,
                role="user",
                content=user_text,
            )
            db.add(user_msg)
            await db.flush()

        # Update Redis context
        await self._push_to_redis(
            conversation_id, {"role": "user", "content": user_text}
        )

        # Get recent context from Redis
        context_messages = await self._get_redis_context(conversation_id)

        # Build personalized system prompt + RAG injection
        async with get_db() as db:
            system_prompt = await self._prompt_builder.build_system_prompt(db, person_id)
            rag_context = await self._retrieve_rag(db, user_text)

        if rag_context:
            system_prompt += f"\n\nRelevant knowledge:\n{rag_context}"

        # Run LLM with tool support
        async with get_db() as db:
            executor = ToolExecutor(db, person_id)
            response_text = await self._run_with_tools(
                system_prompt=system_prompt,
                messages=context_messages,
                executor=executor,
            )

        if not response_text:
            response_text = "I'm having trouble responding right now. Please try again."

        # Persist assistant message
        async with get_db() as db:
            assistant_msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=response_text,
            )
            db.add(assistant_msg)
            await db.flush()

        # Update Redis context
        await self._push_to_redis(
            conversation_id, {"role": "assistant", "content": response_text}
        )

        # Check if summarization is needed
        await self._maybe_summarize(conversation_id, system_prompt)

        log.info(
            "conversation_turn",
            conversation_id=str(conversation_id),
            user_len=len(user_text),
            response_len=len(response_text),
        )
        return response_text

    async def get_messages(
        self, conversation_id: uuid.UUID, limit: int = 50
    ) -> list[dict]:
        """Fetch message history from DB."""
        from gym_shared.db.models import Message
        from sqlalchemy import select

        async with get_db() as db:
            result = await db.execute(
                select(Message.role, Message.content, Message.created_at)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
                .limit(limit)
            )
            return [
                {"role": role, "content": content, "created_at": created_at.isoformat()}
                for role, content, created_at in result.fetchall()
            ]

    # ── Redis context ──────────────────────────────────────────────────────────

    async def _push_to_redis(
        self, conversation_id: uuid.UUID, message: dict
    ) -> None:
        key = _conv_key(conversation_id)
        async with get_redis_ctx(self._config.redis_url) as redis:
            await redis.rpush(key, json.dumps(message))
            await redis.expire(key, 86400)  # 24h TTL

    async def _get_redis_context(
        self, conversation_id: uuid.UUID
    ) -> list[dict]:
        key = _conv_key(conversation_id)
        async with get_redis_ctx(self._config.redis_url) as redis:
            raw = await redis.lrange(key, -_MAX_REDIS_MESSAGES, -1)
        return [json.loads(m) for m in raw]

    async def _maybe_summarize(
        self, conversation_id: uuid.UUID, system_prompt: str
    ) -> None:
        key = _conv_key(conversation_id)
        async with get_redis_ctx(self._config.redis_url) as redis:
            count = await redis.llen(key)

        if count < _SUMMARIZE_THRESHOLD:
            return

        # Get oldest 10 messages to summarize
        async with get_redis_ctx(self._config.redis_url) as redis:
            old_raw = await redis.lrange(key, 0, 9)

        old_messages = [json.loads(m) for m in old_raw]
        conversation_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in old_messages
        )

        summary = await self._llm.generate_guidance(
            system_prompt="Summarize the following conversation excerpt concisely (2–3 sentences):",
            user_message=conversation_text,
        )
        if not summary:
            return

        # Replace oldest 10 with summary
        async with get_redis_ctx(self._config.redis_url) as redis:
            await redis.ltrim(key, 10, -1)
            await redis.lpush(
                key,
                json.dumps({"role": "system", "content": f"[Earlier conversation summary: {summary}]"}),
            )

        log.info("conversation_summarized", conversation_id=str(conversation_id))

    # ── RAG retrieval ──────────────────────────────────────────────────────────

    async def _retrieve_rag(
        self, db, user_text: str, top_k: int = 3
    ) -> str:
        """Retrieve relevant GymKnowledge chunks via pgvector cosine search."""
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError:
            return ""

        try:
            from gym_shared.db.models import GymKnowledge
            from sqlalchemy import select

            model = SentenceTransformer("all-MiniLM-L6-v2")
            query_emb = model.encode(user_text).tolist()

            # pgvector cosine distance operator <=>
            result = await db.execute(
                select(GymKnowledge.title, GymKnowledge.content)
                .where(GymKnowledge.embedding != None)  # noqa: E711
                .order_by(GymKnowledge.embedding.op("<=>")(query_emb))
                .limit(top_k)
            )
            chunks = [f"[{title}] {content}" for title, content in result.fetchall()]
            return "\n\n".join(chunks)
        except Exception as exc:
            log.debug("rag_retrieval_failed", error=str(exc))
            return ""

    # ── LLM with tools ─────────────────────────────────────────────────────────

    async def _run_with_tools(
        self,
        system_prompt: str,
        messages: list[dict],
        executor: ToolExecutor,
    ) -> str:
        """Run multi-turn LLM call with tool use support."""
        import anthropic

        provider = getattr(self._llm, "_provider", None)
        client = getattr(provider, "_client", None)
        model = getattr(provider, "_model", "claude-sonnet-4-6")

        if client is None or not isinstance(client, anthropic.AsyncAnthropic):
            # Fallback: plain generate
            last_user = next(
                (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
            )
            return await self._llm.generate_guidance(system_prompt, last_user) or ""

        # Filter out system-role messages (not supported in Anthropic messages API)
        api_messages = [m for m in messages if m["role"] in ("user", "assistant")]
        if not api_messages:
            return ""

        try:
            response = await client.messages.create(
                model=model,
                max_tokens=self._config.llm_max_tokens,
                system=system_prompt,
                tools=TOOLS,
                messages=api_messages,
            )

            # Handle tool use loop
            for _ in range(3):
                if response.stop_reason != "tool_use":
                    break

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result_str = await executor.run(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        })

                api_messages = api_messages + [
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": tool_results},
                ]
                response = await client.messages.create(
                    model=model,
                    max_tokens=self._config.llm_max_tokens,
                    system=system_prompt,
                    tools=TOOLS,
                    messages=api_messages,
                )

            return "".join(
                block.text for block in response.content if hasattr(block, "text")
            ).strip()

        except Exception as exc:
            log.error("conversation_llm_error", error=str(exc))
            return ""
