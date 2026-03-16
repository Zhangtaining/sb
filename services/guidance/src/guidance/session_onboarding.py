"""Session onboarding — greets user at session start and recommends a workout plan."""
from __future__ import annotations

import json
import uuid

from gym_shared.db.session import get_db
from gym_shared.events.publisher import ensure_consumer_group, read_group, ack, publish
from gym_shared.logging import get_logger
from gym_shared.redis_client import get_redis_ctx

from guidance.config import GuidanceConfig
from guidance.llm_client import GymLLMClient
from guidance.prompt_builder import PromptBuilder
from guidance.tool_definitions import TOOLS
from guidance.tool_executor import ToolExecutor

log = get_logger(__name__)

_MAX_ONBOARDING_TURNS = 3


class SessionOnboardingHandler:
    """Handles session-start conversations triggered by identity_resolved events.

    When a person is identified:
    1. Greet them by name and ask what they want to work on today (TTS via WS)
    2. Accept their response (up to _MAX_ONBOARDING_TURNS turns)
    3. Call suggest_workout_plan tool to build a plan
    4. Store plan in GymSession.workout_plan
    5. Publish onboarding_complete guidance event
    """

    def __init__(self, config: GuidanceConfig, llm_client: GymLLMClient) -> None:
        self._config = config
        self._llm = llm_client
        self._prompt_builder = PromptBuilder()
        # person_id -> pending onboarding state
        self._pending: dict[str, dict] = {}

    async def start(self) -> None:
        """Start consuming identity_resolved events from all cameras."""
        import asyncio

        tasks = [
            asyncio.create_task(self._consume_camera(camera_id))
            for camera_id in self._config.camera_ids
        ]
        if tasks:
            await asyncio.gather(*tasks)

    async def _consume_camera(self, camera_id: str) -> None:
        stream_key = f"identity_resolved:{camera_id}"
        group = "onboarding-workers"
        consumer = self._config.consumer_name

        async with get_redis_ctx(self._config.redis_url) as redis:
            await ensure_consumer_group(redis, stream_key, group)

        while True:
            try:
                async with get_redis_ctx(self._config.redis_url) as redis:
                    messages = await read_group(
                        redis, stream_key, group, consumer,
                        count=5, block_ms=self._config.block_ms,
                    )
                for msg_id, data in messages:
                    await self._handle_identity_resolved(camera_id, data)
                    async with get_redis_ctx(self._config.redis_url) as redis:
                        await ack(redis, stream_key, group, msg_id)
            except Exception as exc:
                import asyncio
                log.error("onboarding_consume_error", camera_id=camera_id, error=str(exc))
                await asyncio.sleep(1)

    async def _handle_identity_resolved(self, camera_id: str, data: dict) -> None:
        person_id_str = data.get("person_id")
        session_id_str = data.get("session_id", "")
        track_id = data.get("track_id")

        if not person_id_str:
            return

        # Skip if already onboarding this person
        if person_id_str in self._pending:
            return

        try:
            person_id = uuid.UUID(person_id_str)
            session_id = uuid.UUID(session_id_str) if session_id_str else None
        except ValueError:
            return

        log.info("onboarding_triggered", person_id=person_id_str, session_id=session_id_str)

        async with get_db() as db:
            system_prompt = await self._prompt_builder.build_onboarding_prompt(db, person_id)

        # Generate greeting
        greeting = await self._llm.generate_guidance(
            system_prompt=system_prompt,
            user_message="Start the session greeting now.",
        )
        if not greeting:
            greeting = "Hey! Welcome to your workout session. What would you like to focus on today?"

        # Dispatch greeting via WebSocket (track_id routes it to the right user)
        await self._dispatch_guidance(
            camera_id=camera_id,
            track_id=int(track_id) if track_id is not None else 0,
            person_id=person_id_str,
            session_id=session_id_str,
            message=greeting,
            message_type="onboarding",
        )

        # Store state for when user responds
        self._pending[person_id_str] = {
            "person_id": person_id,
            "session_id": session_id,
            "camera_id": camera_id,
            "track_id": track_id,
            "system_prompt": system_prompt,
            "turns": 0,
        }

    async def handle_user_response(
        self,
        person_id_str: str,
        user_message: str,
    ) -> str | None:
        """Process a user reply during onboarding. Returns AI response text."""
        state = self._pending.get(person_id_str)
        if state is None:
            return None

        state["turns"] += 1
        person_id: uuid.UUID = state["person_id"]
        session_id: uuid.UUID | None = state["session_id"]

        async with get_db() as db:
            executor = ToolExecutor(db, person_id)

            # Run one LLM turn with tools available
            response_text, plan = await self._run_with_tools(
                system_prompt=state["system_prompt"],
                user_message=user_message,
                executor=executor,
            )

            # If a plan was generated, store it
            if plan and session_id:
                from sqlalchemy import update
                from gym_shared.db.models import GymSession

                await db.execute(
                    update(GymSession.__table__)
                    .where(GymSession.__table__.c.id == session_id)
                    .values(workout_plan=plan)
                )
                log.info(
                    "workout_plan_stored",
                    person_id=person_id_str,
                    session_id=str(session_id),
                )

        # Dispatch response via WebSocket
        await self._dispatch_guidance(
            camera_id=state["camera_id"],
            track_id=int(state["track_id"]) if state["track_id"] is not None else 0,
            person_id=person_id_str,
            session_id=str(session_id) if session_id else "",
            message=response_text or "Let's get started!",
            message_type="onboarding_plan" if plan else "onboarding",
            extra={"workout_plan": plan} if plan else {},
        )

        # Clear state if max turns reached or plan accepted
        if plan or state["turns"] >= _MAX_ONBOARDING_TURNS:
            del self._pending[person_id_str]
            # Publish onboarding_complete event
            async with get_redis_ctx(self._config.redis_url) as redis:
                await publish(
                    redis,
                    f"onboarding_complete:{state['camera_id']}",
                    {
                        "person_id": person_id_str,
                        "session_id": str(session_id) if session_id else "",
                        "workout_plan": json.dumps(plan) if plan else "",
                    },
                    maxlen=100,
                )

        return response_text

    async def _run_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        executor: ToolExecutor,
    ) -> tuple[str, dict | None]:
        """Run one LLM turn. Returns (response_text, workout_plan or None)."""
        import anthropic

        # Only use tool-calling for Anthropic provider for now
        provider = getattr(self._llm, "_provider", None)
        client = getattr(provider, "_client", None)
        model = getattr(provider, "_model", "claude-sonnet-4-6")

        if client is None or not isinstance(client, anthropic.AsyncAnthropic):
            # Fallback: no tool use
            text = await self._llm.generate_guidance(system_prompt, user_message)
            return text or "", None

        messages = [{"role": "user", "content": user_message}]
        plan: dict | None = None

        try:
            response = await client.messages.create(
                model=model,
                max_tokens=1024,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )

            # Handle tool use loop (max 2 iterations)
            for _ in range(2):
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
                        if block.name == "suggest_workout_plan":
                            plan = json.loads(result_str)

                messages = messages + [
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": tool_results},
                ]
                response = await client.messages.create(
                    model=model,
                    max_tokens=1024,
                    system=system_prompt,
                    tools=TOOLS,
                    messages=messages,
                )

            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text
            return text.strip(), plan

        except Exception as exc:
            log.error("onboarding_llm_error", error=str(exc))
            return "", None

    async def _dispatch_guidance(
        self,
        camera_id: str,
        track_id: int,
        person_id: str,
        session_id: str,
        message: str,
        message_type: str = "onboarding",
        extra: dict | None = None,
    ) -> None:
        from gym_shared.events.publisher import publish

        payload = {
            "camera_id": camera_id,
            "track_id": str(track_id),
            "person_id": person_id,
            "session_id": session_id,
            "message": message,
            "type": message_type,
        }
        if extra:
            payload.update(extra)

        async with get_redis_ctx(self._config.redis_url) as redis:
            await publish(redis, "guidance", payload, maxlen=1000)
