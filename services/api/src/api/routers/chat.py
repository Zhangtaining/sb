"""Stateless chat endpoint — no person or conversation ID required.

Used by anonymous (Phase 1) sessions to talk to the AI coach.
Messages are not persisted; context is passed inline per request.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from gym_shared.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []  # [{"role": "user"|"assistant", "content": "..."}]
    track_id: str | None = None


class ChatReply(BaseModel):
    response: str


def _get_llm():
    from guidance.config import build_config
    from guidance.llm_client import GymLLMClient
    from gym_shared.settings import settings
    config = build_config(settings)
    return GymLLMClient(config), config


@router.post("", response_model=ChatReply)
async def stateless_chat(body: ChatRequest) -> ChatReply:
    """Send a message and get an AI coach response. No auth required."""
    llm, config = _get_llm()

    system_prompt = (
        "You are an expert personal trainer and gym coach. "
        "Your job is to immediately create a workout plan when the user tells you what they want to do. "
        "Do NOT ask follow-up questions. Do NOT ask about equipment or time. "
        "Assume a full gym with standard equipment and a 45-60 minute session. "
        "When the user states any workout goal or picks a category, IMMEDIATELY respond with: "
        "1) One short enthusiastic sentence, then "
        "2) A JSON code block with their plan in this EXACT format:\n"
        "```json\n"
        '{"focus_area": "Legs & Glutes", "duration_minutes": 45, "exercises": ['
        '{"name": "squat", "sets": 4, "reps": "8-10", "rest_seconds": 90, "notes": "Keep chest up, knees tracking toes"},'
        '{"name": "romanian_deadlift", "sets": 3, "reps": "10-12", "rest_seconds": 75, "notes": "Hinge at hips, slight knee bend"}],'
        '"note": "Focus on full range of motion today."}\n'
        "```\n"
        "Exercise names must be snake_case (e.g. bench_press, bicep_curl). "
        "Include 4-6 exercises. Keep notes concise coaching cues. "
        "If the user asks to change the plan or asks a question, respond conversationally and provide a new plan if needed."
    )

    messages = [{"role": "system", "content": system_prompt}]
    for h in body.history[-10:]:  # keep last 10 turns for context
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": body.message})

    # Build a single user prompt that includes recent history inline
    history_text = ""
    for h in body.history[-6:]:
        role = "You" if h.get("role") == "assistant" else "User"
        history_text += f"{role}: {h.get('content', '')}\n"

    user_prompt = (
        f"{history_text}User: {body.message}"
        if history_text
        else body.message
    )

    try:
        response = await llm.generate_guidance(
            system_prompt=system_prompt,
            user_message=user_prompt,
        )
        return ChatReply(response=response or "Let's get started! What kind of workout are you feeling today?")
    except Exception as exc:
        log.error("stateless_chat_error", error=str(exc))
        return ChatReply(
            response="I'm having trouble connecting right now. Try again in a moment!"
        )


class ExerciseIntroRequest(BaseModel):
    exercise_name: str   # snake_case


class ExerciseIntroReply(BaseModel):
    intro: str   # 2-3 sentence spoken introduction


@router.post("/exercise-intro", response_model=ExerciseIntroReply)
async def exercise_intro(body: ExerciseIntroRequest) -> ExerciseIntroReply:
    """Return a short spoken introduction for a specific exercise movement."""
    llm, _ = _get_llm()

    system_prompt = (
        "You are a personal trainer giving a brief spoken introduction to an exercise. "
        "Respond with exactly 2-3 short sentences that: "
        "1) Name the primary muscles worked, "
        "2) Describe the movement simply, "
        "3) Give one key coaching cue. "
        "Be conversational and encouraging. No lists, no markdown, just plain spoken text."
    )

    exercise_display = body.exercise_name.replace("_", " ")
    try:
        intro = await llm.generate_guidance(
            system_prompt=system_prompt,
            user_message=f"Introduce the {exercise_display} exercise.",
        )
        return ExerciseIntroReply(intro=intro or f"Let's do some {exercise_display}!")
    except Exception as exc:
        log.error("exercise_intro_error", error=str(exc))
        return ExerciseIntroReply(intro=f"Let's get into {exercise_display}. Focus on good form and controlled movement.")
