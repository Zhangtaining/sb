"""Persons API — GET and PATCH person profile."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from gym_shared.db.models import Person
from gym_shared.db.session import get_db

router = APIRouter(prefix="/persons", tags=["persons"])


class PersonResponse(BaseModel):
    id: uuid.UUID
    name: str
    goals: list[str]
    injury_notes: str
    member_since: str

    model_config = {"from_attributes": True}


class PersonUpdateRequest(BaseModel):
    goals: list[str] | None = None
    injury_notes: str | None = None


@router.get("/{person_id}", response_model=PersonResponse)
async def get_person(person_id: uuid.UUID):
    async with get_db() as db:
        result = await db.execute(select(Person).where(Person.id == person_id))
        person = result.scalar_one_or_none()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        goals = person.goals if isinstance(person.goals, list) else []
        return PersonResponse(
            id=person.id,
            name=person.display_name,
            goals=goals,
            injury_notes=person.injury_notes or "",
            member_since=person.created_at.strftime("%B %Y") if person.created_at else "",
        )


@router.patch("/{person_id}", response_model=PersonResponse)
async def update_person(person_id: uuid.UUID, body: PersonUpdateRequest):
    async with get_db() as db:
        result = await db.execute(select(Person).where(Person.id == person_id))
        person = result.scalar_one_or_none()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        if body.goals is not None:
            person.goals = body.goals
        if body.injury_notes is not None:
            person.injury_notes = body.injury_notes

        await db.commit()
        await db.refresh(person)

        goals = person.goals if isinstance(person.goals, list) else []
        return PersonResponse(
            id=person.id,
            name=person.display_name,
            goals=goals,
            injury_notes=person.injury_notes or "",
            member_since=person.created_at.strftime("%B %Y") if person.created_at else "",
        )
