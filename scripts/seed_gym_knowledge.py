#!/usr/bin/env python3
"""Seed the gym_knowledge table with exercise guides and safety info for RAG.

Usage:
    python scripts/seed_gym_knowledge.py

Requires: sentence-transformers (pip install sentence-transformers)
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from gym_shared.db.models import GymKnowledge
from gym_shared.db.session import get_db
from gym_shared.logging import configure_logging, get_logger
from gym_shared.settings import settings

configure_logging(settings.log_format, settings.log_level)
log = get_logger(__name__)

KNOWLEDGE_ENTRIES: list[dict] = [
    # ── Exercise form guides ───────────────────────────────────────────────────
    {
        "title": "Squat — Proper Form",
        "category": "exercise_form",
        "content": (
            "Stand with feet shoulder-width apart, toes slightly turned out. Keep chest tall "
            "and core braced. Push knees out in line with toes as you descend. Lower until "
            "thighs are parallel to the floor (or deeper if mobility allows). Drive through "
            "heels to stand. Common mistakes: knees caving inward (knee valgus), rounding "
            "the lower back, heels rising. Cue: 'chest up, knees out, sit back'."
        ),
    },
    {
        "title": "Squat — Common Mistakes",
        "category": "exercise_form",
        "content": (
            "Knee cave (valgus collapse): strengthen glutes and adductors, cue 'push knees out'. "
            "Forward lean: improve ankle mobility, use heel elevation if needed, strengthen upper back. "
            "Butt wink (lumbar flexion at bottom): limited hip mobility; work on hip flexor stretching. "
            "Heels rising: tight calves or poor ankle dorsiflexion; stretch calves, try wider stance."
        ),
    },
    {
        "title": "Push-Up — Proper Form",
        "category": "exercise_form",
        "content": (
            "Start in plank with hands slightly wider than shoulder-width. Keep body in straight line "
            "from head to heels — no sagging hips or raised backside. Lower chest to an inch above "
            "the floor, elbows at 45° from body (not flared out to 90°). Press back up explosively. "
            "Common mistakes: sagging core, flaring elbows, partial range of motion."
        ),
    },
    {
        "title": "Bicep Curl — Proper Form",
        "category": "exercise_form",
        "content": (
            "Stand with feet hip-width, hold dumbbells with palms facing forward. Pin elbows to sides "
            "— do not let them drift forward or backward. Curl the weight toward shoulders, squeeze "
            "bicep at top. Lower with control (2-3 seconds eccentric). Common mistakes: swinging body, "
            "using momentum, elbows drifting forward, incomplete range of motion."
        ),
    },
    {
        "title": "Lateral Raise — Proper Form",
        "category": "exercise_form",
        "content": (
            "Stand holding dumbbells at sides, slight bend in elbows. Raise arms to shoulder height "
            "with palms facing down — thumbs slightly lower than pinkies (internal rotation) for "
            "proper shoulder mechanics. Lower slowly (3 seconds). Keep torso still. "
            "Common mistakes: shrugging shoulders, using momentum, raising too high above shoulder level."
        ),
    },
    {
        "title": "Deadlift — Proper Form",
        "category": "exercise_form",
        "content": (
            "Stand with bar over mid-foot, hip-width stance. Hip hinge to grip bar just outside legs. "
            "Neutral spine (not rounded), chest up, shoulders slightly in front of bar. Push floor away "
            "while driving hips forward. Keep bar close to body throughout — it should scrape the shins. "
            "Lockout by squeezing glutes, not hyperextending lower back. "
            "Common mistakes: rounding lower back, bar drifting forward, jerking the weight off the floor."
        ),
    },
    {
        "title": "Bench Press — Proper Form",
        "category": "exercise_form",
        "content": (
            "Lie on bench with eyes under bar. Grip slightly wider than shoulder-width. "
            "Retract and depress shoulder blades into bench — maintain arch in lower back. "
            "Unrack bar, lower to lower chest with elbows at 45-75°. Touch chest lightly, press up "
            "and slightly back toward rerack position. Keep feet flat on floor. "
            "Common mistakes: bouncing off chest, flaring elbows, losing shoulder blade retraction, "
            "lifting hips off bench."
        ),
    },
    {
        "title": "Lunge — Proper Form",
        "category": "exercise_form",
        "content": (
            "Stand tall, step forward with one leg, lower back knee toward floor (1 inch above). "
            "Front shin stays vertical, knee tracks over toes. Keep torso upright, core braced. "
            "Drive through front heel to return to start. "
            "Common mistakes: front knee collapsing inward, leaning forward excessively, "
            "stepping too short (knee goes far past toes)."
        ),
    },
    {
        "title": "Pull-Up — Proper Form",
        "category": "exercise_form",
        "content": (
            "Hang from bar with overhand grip slightly wider than shoulders. Depress shoulders "
            "(pull shoulder blades down and back) before pulling. Drive elbows toward hips, "
            "chin over bar at top. Lower with full control to dead hang. "
            "Common mistakes: kipping (unless intentional), partial range of motion, "
            "shrugging shoulders, crossing ankles (use neutral spine)."
        ),
    },

    # ── Recovery and programming ───────────────────────────────────────────────
    {
        "title": "Muscle Recovery — Rest Days",
        "category": "recovery",
        "content": (
            "Muscles need 48-72 hours of recovery after a strength session targeting a specific muscle "
            "group. Training the same muscles two days in a row limits recovery and can increase injury risk. "
            "Signs you need more rest: persistent soreness, decreased performance, poor sleep, irritability. "
            "Active recovery (light walking, yoga, swimming) on rest days improves blood flow without "
            "adding stress."
        ),
    },
    {
        "title": "Progressive Overload",
        "category": "programming",
        "content": (
            "Progressive overload is the key principle for strength and muscle gains. Increase the "
            "challenge gradually over time by: adding weight (2.5-5 lbs per week for upper body, "
            "5-10 lbs for lower body), adding reps within your target range, adding sets, "
            "reducing rest time, or improving range of motion. Aim for small consistent increases "
            "rather than large jumps that compromise form."
        ),
    },
    {
        "title": "Rep Ranges for Different Goals",
        "category": "programming",
        "content": (
            "Strength: 1-5 reps at 85-100% 1RM, long rest (3-5 min). "
            "Hypertrophy (muscle growth): 6-12 reps at 67-85% 1RM, moderate rest (60-90s). "
            "Endurance/muscular endurance: 15-20+ reps at <67% 1RM, short rest (30-60s). "
            "For general fitness, 8-12 reps is a practical middle ground. "
            "Sets: 3-5 working sets per exercise is typical for strength/hypertrophy."
        ),
    },
    {
        "title": "Warm-Up and Cool-Down",
        "category": "safety",
        "content": (
            "Warm up before lifting: 5-10 min light cardio, then dynamic stretches (leg swings, "
            "arm circles, hip circles). Do 1-2 warm-up sets at 40-60% of working weight before "
            "heavy sets. Cool down: 5-10 min light activity, static stretching for worked muscles "
            "(hold 20-30 seconds). Skipping warm-up increases injury risk, especially for joints."
        ),
    },

    # ── Safety ─────────────────────────────────────────────────────────────────
    {
        "title": "Signs to Stop Exercising",
        "category": "safety",
        "content": (
            "Stop immediately if you experience: sharp or joint pain (different from muscle burn), "
            "chest pain or tightness, dizziness or lightheadedness, shortness of breath beyond normal "
            "exertion, numbness or tingling in limbs. Muscle soreness (DOMS) is normal 24-48 hours "
            "after training — this is different from sharp/acute pain during exercise."
        ),
    },
    {
        "title": "Breathing During Lifting",
        "category": "safety",
        "content": (
            "Valsalva maneuver (holding breath) stabilizes the spine under heavy loads — appropriate "
            "for 1-3 rep max attempts. For general training: inhale during the eccentric (lowering) "
            "phase, exhale during the concentric (lifting) phase. "
            "Example squat: breathe in as you descend, exhale as you stand up. "
            "Never hold your breath for extended periods — it raises blood pressure significantly."
        ),
    },

    # ── Nutrition basics ───────────────────────────────────────────────────────
    {
        "title": "Pre-Workout Nutrition",
        "category": "nutrition",
        "content": (
            "Eat 1-3 hours before training. A meal with carbohydrates and protein works best: "
            "oats with protein powder, rice with chicken, banana with peanut butter. "
            "Avoid high-fat or high-fiber meals immediately before — they slow digestion and can "
            "cause discomfort. If training fasted (morning), a small snack (banana, protein shake) "
            "30 min before can improve performance."
        ),
    },
    {
        "title": "Post-Workout Nutrition",
        "category": "nutrition",
        "content": (
            "The post-workout 'anabolic window' is wider than once thought — aim for 20-40g protein "
            "within 2 hours of training. Carbohydrates help replenish glycogen (important for "
            "back-to-back training days). Good options: protein shake + fruit, chicken and rice, "
            "Greek yogurt with berries. Hydration is critical — drink water throughout the day, "
            "not just during exercise."
        ),
    },
    {
        "title": "Protein Intake for Muscle Building",
        "category": "nutrition",
        "content": (
            "Research supports 1.6-2.2g protein per kg bodyweight per day for maximizing muscle "
            "protein synthesis. For a 75kg person: 120-165g protein/day. Spread intake across "
            "3-5 meals (20-40g per meal). Good sources: chicken breast, eggs, Greek yogurt, "
            "fish, legumes, tofu, protein shakes. Higher protein is not harmful for healthy "
            "individuals but offers diminishing returns above 2.2g/kg."
        ),
    },
]


async def seed() -> None:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("ERROR: sentence-transformers not installed.")
        print("Run: pip install sentence-transformers")
        return

    print("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    async with get_db() as db:
        inserted = 0
        skipped = 0
        for entry in KNOWLEDGE_ENTRIES:
            # Check if already exists
            from sqlalchemy import select
            result = await db.execute(
                select(GymKnowledge.id).where(GymKnowledge.title == entry["title"])
            )
            if result.scalar_one_or_none():
                print(f"  SKIP  {entry['title']}")
                skipped += 1
                continue

            embedding = model.encode(entry["content"]).tolist()
            knowledge = GymKnowledge(
                title=entry["title"],
                content=entry["content"],
                category=entry["category"],
                embedding=embedding,
            )
            db.add(knowledge)
            print(f"  ADD   {entry['title']}")
            inserted += 1

        print(f"\nDone: {inserted} inserted, {skipped} skipped.")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
