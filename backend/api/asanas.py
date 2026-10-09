"""The asana library: what poses exist and what the system checks in each."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from ..schemas.schemas import AsanaDetail, AsanaOut
from ..services.engines import get_registry

router = APIRouter(prefix="/asanas", tags=["asanas"])


@router.get("", response_model=List[AsanaOut])
def list_asanas(
    difficulty: Optional[str] = Query(default=None),
    goal: Optional[str] = Query(default=None),
    stage: Optional[str] = Query(default=None),
) -> List[dict]:
    configs = get_registry().all()
    if difficulty:
        configs = [c for c in configs if c.difficulty == difficulty]
    if goal:
        configs = [c for c in configs if goal in c.target_goals]
    if stage:
        configs = [c for c in configs if c.sequence_stage == stage]
    return [c.to_dict(include_rules=False) for c in sorted(configs, key=lambda c: c.id)]


@router.get("/{asana_id}", response_model=AsanaDetail)
def get_asana(asana_id: str) -> dict:
    """Full detail including every alignment rule.

    Exposing the rules is deliberate: it is what lets the app explain a
    score instead of asserting one.
    """
    config = get_registry().get(asana_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown asana '{asana_id}'."
        )
    return config.to_dict(include_rules=True)
