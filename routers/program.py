"""
Enrutador de FastAPI para el programa de puntos del comercio.
La caja configura cómo se suman los puntos y qué premios se pueden canjear.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
import models
from auth import get_current_business
from branding import sync_business_passes
from program import ProgramError, program_info, update_program

router = APIRouter(prefix="/program", tags=["Programa de puntos"])


class RewardInput(BaseModel):
    id: str | None = None          # Premio existente; sin id se crea uno nuevo
    name: str
    points_cost: int


class ProgramUpdate(BaseModel):
    points_mode: str = "fixed"
    points_per_visit: int = 10
    pesos_per_point: int | None = None
    rewards: list[RewardInput] = []


@router.get("")
def get_program(business: models.Business = Depends(get_current_business)):
    return program_info(business)


@router.put("")
def save_program(
    data: ProgramUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    business: models.Business = Depends(get_current_business)
):
    try:
        rewards_changed = update_program(
            business,
            points_mode=data.points_mode,
            points_per_visit=data.points_per_visit,
            pesos_per_point=data.pesos_per_point,
            rewards=[r.model_dump() for r in data.rewards],
        )
    except ProgramError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(business)

    # La tarjeta muestra el próximo premio, así que si cambian los premios hay que actualizarlas
    passes_to_update = len(business.passes) if rewards_changed else 0
    if passes_to_update:
        background_tasks.add_task(sync_business_passes, business.id)

    return {"status": "ok", "passes_to_update": passes_to_update, **program_info(business)}
