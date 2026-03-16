"""LLM tool definitions for Phase 2 personalized guidance."""
from __future__ import annotations

# Tool schemas in Anthropic tool-use format
TOOLS: list[dict] = [
    {
        "name": "get_workout_history",
        "description": (
            "Retrieve the person's recent workout sessions including exercises performed, "
            "rep counts, and form scores. Use this to answer questions about past performance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (default 7)",
                    "default": 7,
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_exercise_stats",
        "description": (
            "Get statistics for a specific exercise: personal best rep count, "
            "average form score, and recent trend."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "exercise_name": {
                    "type": "string",
                    "description": "Name of the exercise (e.g. 'squat', 'push_up')",
                }
            },
            "required": ["exercise_name"],
        },
    },
    {
        "name": "suggest_workout_plan",
        "description": (
            "Generate a structured workout plan for today's session based on the person's "
            "history, goals, and focus area. Returns a list of exercises with sets and reps."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "focus_area": {
                    "type": "string",
                    "description": "Muscle group or goal (e.g. 'legs', 'upper body', 'cardio')",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Target workout duration in minutes (default 45)",
                    "default": 45,
                },
            },
            "required": ["focus_area"],
        },
    },
    {
        "name": "get_person_profile",
        "description": (
            "Get the person's profile including goals, injury notes, and experience level."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
