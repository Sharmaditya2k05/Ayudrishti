"""Progress analytics: history turned into the series the charts render."""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..models.models import Asana, PoseAssessment, PracticeSession, User
from .engines import get_analyzer, get_registry, load_history, to_profile


def overall_progress(db: Session, user: User) -> Dict[str, object]:
    """Everything the Progress screen needs in one payload."""
    history = load_history(db, user.id)
    analysis = get_analyzer().analyze(history, to_profile(user))
    registry = get_registry()

    total_sessions = db.execute(
        select(func.count(PracticeSession.id)).where(
            PracticeSession.user_id == user.id,
            PracticeSession.status == "completed",
        )
    ).scalar_one()

    # Session-level scores drive the headline trend chart.
    session_rows = db.execute(
        select(PracticeSession)
        .where(
            PracticeSession.user_id == user.id,
            PracticeSession.status == "completed",
            PracticeSession.overall_score.is_not(None),
        )
        .order_by(PracticeSession.started_at)
    ).scalars().all()

    score_history = [
        {
            "date": row.started_at.date().isoformat(),
            "score": round(row.overall_score, 1),
            "session_id": row.id,
        }
        for row in session_rows
    ]

    per_asana: List[Dict[str, object]] = []
    for asana_id, perf in analysis.asana_performance.items():
        config = registry.get(asana_id)
        records = history.for_asana(asana_id)
        per_asana.append(
            {
                "asana_id": asana_id,
                "asana_name": config.english_name if config else asana_id,
                "attempts": perf.attempts,
                "average_score": round(perf.average_score, 1),
                "latest_score": round(perf.latest_score, 1),
                "best_score": round(perf.best_score, 1),
                "trend": None if perf.trend is None else round(perf.trend, 1),
                "days_since": perf.days_since,
                "weak_components": perf.weak_components,
                "history": [
                    {
                        "date": r.performed_at.date().isoformat(),
                        "score": round(r.score, 1),
                        "session_id": r.session_id,
                    }
                    for r in records
                ],
                "component_history": _component_series(records),
            }
        )

    per_asana.sort(key=lambda p: p["average_score"])

    return {
        "overall_average": (
            None if analysis.overall_average is None else round(analysis.overall_average, 1)
        ),
        "overall_trend": (
            None if analysis.overall_trend is None else round(analysis.overall_trend, 1)
        ),
        "total_sessions": total_sessions,
        "total_assessments": len(history),
        "ready_to_progress": analysis.ready_to_progress,
        "score_history": score_history,
        "per_asana": per_asana,
        "weaknesses": [w.to_dict() for w in analysis.weaknesses],
        "consistency": analysis.consistency.to_dict() if analysis.consistency else None,
    }


def asana_progress(db: Session, user: User, asana_id: str) -> Dict[str, object]:
    """Detailed progress for a single asana."""
    registry = get_registry()
    config = registry.get(asana_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown asana '{asana_id}'."
        )

    history = load_history(db, user.id)
    records = history.for_asana(asana_id)
    if not records:
        return {
            "asana_id": asana_id,
            "asana_name": config.english_name,
            "attempts": 0,
            "average_score": 0.0,
            "latest_score": 0.0,
            "best_score": 0.0,
            "trend": None,
            "days_since": None,
            "weak_components": [],
            "history": [],
            "component_history": {},
        }

    analysis = get_analyzer().analyze(history, to_profile(user))
    perf = analysis.asana_performance[asana_id]

    return {
        "asana_id": asana_id,
        "asana_name": config.english_name,
        "attempts": perf.attempts,
        "average_score": round(perf.average_score, 1),
        "latest_score": round(perf.latest_score, 1),
        "best_score": round(perf.best_score, 1),
        "trend": None if perf.trend is None else round(perf.trend, 1),
        "days_since": perf.days_since,
        "weak_components": perf.weak_components,
        "history": [
            {
                "date": r.performed_at.date().isoformat(),
                "score": round(r.score, 1),
                "session_id": r.session_id,
            }
            for r in records
        ],
        "component_history": _component_series(records),
    }


def _component_series(records) -> Dict[str, List[Dict[str, object]]]:
    """Per-component score series, so charts can show which part improved."""
    series: Dict[str, List[Dict[str, object]]] = {}
    for record in records:
        for component, value in (record.component_scores or {}).items():
            series.setdefault(component, []).append(
                {
                    "date": record.performed_at.date().isoformat(),
                    "score": round(value, 1),
                    "session_id": record.session_id,
                }
            )
    return series
