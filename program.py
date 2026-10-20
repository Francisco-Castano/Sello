"""
Programa de puntos de cada comercio: cómo se suman los puntos y qué premios se canjean.
"""

import math
import models

POINTS_MODES = ("fixed", "amount")
MAX_REWARDS = 10
MAX_REWARD_NAME = 40
MAX_POINTS = 1_000_000


class ProgramError(ValueError):
    """Dato inválido del programa; el mensaje se muestra tal cual al comercio."""


def points_for_amount(business: models.Business, amount: float) -> int:
    """Puntos que corresponden a una compra: 1 punto cada pesos_per_point pesos completos."""
    if business.points_mode != "amount" or not business.pesos_per_point:
        raise ProgramError("Este comercio no suma puntos según el monto de la compra")
    if not math.isfinite(amount) or amount <= 0:
        raise ProgramError("Ingresá el monto de la compra")
    points = int(amount // business.pesos_per_point)
    if points == 0:
        raise ProgramError(f"El monto no alcanza para sumar puntos (1 punto cada ${business.pesos_per_point})")
    return points


def reward_progress(rewards: list[tuple[str, int]], balance: int) -> str | None:
    """Texto para la tarjeta: el mejor premio que ya puede canjear, o cuánto le falta para el próximo."""
    if not rewards:
        return None
    affordable = [r for r in rewards if r[1] <= balance]
    if affordable:
        name, _ = max(affordable, key=lambda r: r[1])
        return f"¡Ya podés canjear: {name}!"
    name, cost = min(rewards, key=lambda r: r[1])
    return f"Te faltan {cost - balance} pts para: {name}"


def program_info(business: models.Business) -> dict:
    return {
        "points_mode": business.points_mode,
        "points_per_visit": business.points_per_visit,
        "pesos_per_point": business.pesos_per_point,
        "rewards": [
            {"id": r.id, "name": r.name, "points_cost": r.points_cost}
            for r in business.active_rewards
        ],
    }


def rewards_for_balance(business: models.Business, balance: int) -> list[dict]:
    """Premios con lo que le falta al cliente para cada uno, para mostrar en la caja."""
    return [
        {
            "id": r.id,
            "name": r.name,
            "points_cost": r.points_cost,
            "available": balance >= r.points_cost,
            "missing": max(0, r.points_cost - balance),
        }
        for r in business.active_rewards
    ]


def update_program(business: models.Business, points_mode: str, points_per_visit: int,
                   pesos_per_point: int | None, rewards: list[dict]) -> bool:
    """Guarda modo y premios. Los premios que ya no vienen se desactivan (no se borran, por el historial).
    Devuelve True si cambiaron los premios, porque entonces hay que actualizar las tarjetas."""
    if points_mode not in POINTS_MODES:
        raise ProgramError("Elegí cómo se suman los puntos")
    if not 1 <= points_per_visit <= 10_000:
        raise ProgramError("Los puntos por compra tienen que estar entre 1 y 10.000")
    if points_mode == "amount" and not (pesos_per_point and 1 <= pesos_per_point <= 10_000_000):
        raise ProgramError("Indicá cada cuántos pesos se suma 1 punto")
    if len(rewards) > MAX_REWARDS:
        raise ProgramError(f"Podés tener hasta {MAX_REWARDS} premios")

    cleaned = []
    for reward in rewards:
        name = " ".join((reward.get("name") or "").split())
        cost = reward.get("points_cost")
        if not name or len(name) > MAX_REWARD_NAME:
            raise ProgramError(f"Cada premio necesita un nombre de hasta {MAX_REWARD_NAME} caracteres")
        if not isinstance(cost, int) or not 1 <= cost <= MAX_POINTS:
            raise ProgramError(f"Los puntos de \"{name}\" tienen que ser un número entre 1 y {MAX_POINTS:,}".replace(",", "."))
        cleaned.append((reward.get("id"), name, cost))

    business.points_mode = points_mode
    business.points_per_visit = points_per_visit
    business.pesos_per_point = pesos_per_point if points_mode == "amount" else business.pesos_per_point

    before = [(r.name, r.points_cost) for r in business.active_rewards]
    existing = {r.id: r for r in business.rewards}
    kept_ids = set()
    for reward_id, name, cost in cleaned:
        reward = existing.get(reward_id) if reward_id else None
        if reward and reward.active:
            reward.name, reward.points_cost = name, cost
            kept_ids.add(reward.id)
        else:
            business.rewards.append(models.Reward(name=name, points_cost=cost))
    for reward in business.rewards:
        if reward.id and reward.id in existing and reward.id not in kept_ids:
            reward.active = False

    after = sorted((name, cost) for _, name, cost in cleaned)
    return sorted(before) != after
