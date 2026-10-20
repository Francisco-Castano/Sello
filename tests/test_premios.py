"""Programa de puntos: modo fijo o por monto, premios configurables y canje desde la caja."""

import pytest
import GoogleWallet
import models
from program import reward_progress


@pytest.fixture
def cafe(make_business):
    return make_business()


@pytest.fixture
def headers(cafe, login):
    return login()


def save_program(client, headers, **changes):
    data = {"points_mode": "fixed", "points_per_visit": 10, "pesos_per_point": None,
            "rewards": [{"name": "Café gratis", "points_cost": 100}, {"name": "Torta", "points_cost": 250}],
            **changes}
    return client.put("/program", json=data, headers=headers)


# --- Configuración ---

def test_programa_por_defecto(client, headers):
    assert client.get("/program", headers=headers).json() == {
        "points_mode": "fixed", "points_per_visit": 10, "pesos_per_point": None, "rewards": []}


def test_configurar_requiere_sesion(client, cafe):
    assert client.get("/program").status_code == 401
    assert client.put("/program", json={}).status_code == 401


def test_guardar_premios_ordenados_por_puntos(client, headers):
    response = save_program(client, headers, rewards=[
        {"name": "  Torta  ", "points_cost": 250}, {"name": "Café gratis", "points_cost": 100}])
    assert response.status_code == 200
    rewards = client.get("/program", headers=headers).json()["rewards"]
    assert [(r["name"], r["points_cost"]) for r in rewards] == [("Café gratis", 100), ("Torta", 250)]


@pytest.mark.parametrize("changes, message", [
    ({"points_mode": "otro"}, "Elegí cómo se suman"),
    ({"points_mode": "amount", "pesos_per_point": None}, "cada cuántos pesos"),
    ({"points_per_visit": 0}, "entre 1 y 10.000"),
    ({"rewards": [{"name": "   ", "points_cost": 100}]}, "nombre"),
    ({"rewards": [{"name": "Café", "points_cost": 0}]}, "Los puntos de"),
    ({"rewards": [{"name": f"Premio {i}", "points_cost": 10 + i} for i in range(11)]}, "hasta 10 premios"),
])
def test_rechaza_configuraciones_invalidas(client, headers, changes, message):
    response = save_program(client, headers, **changes)
    assert response.status_code == 400
    assert message in response.json()["detail"]


def test_un_error_no_cambia_lo_guardado(client, headers):
    save_program(client, headers)
    save_program(client, headers, points_mode="amount", pesos_per_point=None)
    assert client.get("/program", headers=headers).json()["points_mode"] == "fixed"


def test_editar_conserva_el_premio_y_quitar_lo_desactiva(client, db, headers):
    rewards = save_program(client, headers).json()["rewards"]
    cafe_id, torta_id = rewards[0]["id"], rewards[1]["id"]

    response = save_program(client, headers, rewards=[{"id": cafe_id, "name": "Café doble", "points_cost": 120}])
    assert [(r["id"], r["name"], r["points_cost"]) for r in response.json()["rewards"]] == [(cafe_id, "Café doble", 120)]
    assert db.get(models.Reward, torta_id).active is False  # No se borra, por el historial de canjes


def test_cambiar_premios_actualiza_las_tarjetas_y_cambiar_el_modo_no(client, cafe, headers, make_pass, wallet):
    make_pass(cafe)
    assert save_program(client, headers).json()["passes_to_update"] == 1
    assert wallet.synced_businesses == [cafe.id]

    response = save_program(client, headers, points_mode="amount", pesos_per_point=1000)
    assert response.json()["passes_to_update"] == 0
    assert wallet.synced_businesses == [cafe.id]


# --- Sumar puntos ---

def test_modo_fijo_suma_los_puntos_indicados(client, db, cafe, headers, make_pass):
    make_pass(cafe)
    response = client.post("/passes/sello_prueba0001/sumar-puntos", json={"points": 10}, headers=headers)
    assert response.json()["new_balance"] == 10
    transaction = db.query(models.Transaction).one()
    assert (transaction.kind, transaction.description) == ("earn", "Compra en local")


def test_modo_por_monto_calcula_los_puntos(client, db, cafe, headers, make_pass):
    make_pass(cafe)
    save_program(client, headers, points_mode="amount", pesos_per_point=1000)

    response = client.post("/passes/sello_prueba0001/sumar-puntos", json={"amount": 5999.99}, headers=headers)
    assert response.status_code == 200
    assert response.json()["points_added"] == 5  # Solo cuentan los $1000 completos
    transaction = db.query(models.Transaction).one()
    assert (transaction.kind, transaction.sale_amount) == ("earn", 5999.99)


@pytest.mark.parametrize("amount, message", [
    (999, "no alcanza"),
    (0, "Ingresá el monto"),
    (-500, "Ingresá el monto"),
])
def test_monto_que_no_alcanza_o_invalido(client, cafe, headers, make_pass, amount, message):
    make_pass(cafe)
    save_program(client, headers, points_mode="amount", pesos_per_point=1000)
    response = client.post("/passes/sello_prueba0001/sumar-puntos", json={"amount": amount}, headers=headers)
    assert response.status_code == 400
    assert message in response.json()["detail"]


def test_monto_en_modo_fijo_es_un_error(client, cafe, headers, make_pass):
    make_pass(cafe)
    response = client.post("/passes/sello_prueba0001/sumar-puntos", json={"amount": 5000}, headers=headers)
    assert response.status_code == 400


def test_ajustes_manuales_quedan_marcados(client, db, cafe, headers, make_pass):
    make_pass(cafe, balance=50)
    client.post("/passes/sello_prueba0001/sumar-puntos",
                json={"points": -5, "description": "Corrección"}, headers=headers)
    save_program(client, headers, points_mode="amount", pesos_per_point=1000)
    client.post("/passes/sello_prueba0001/sumar-puntos", json={"points": 3}, headers=headers)

    kinds = [(t.kind, t.description) for t in db.query(models.Transaction).order_by(models.Transaction.created_at)]
    assert kinds == [("adjust", "Corrección"), ("adjust", "Ajuste manual")]


# --- Canje ---

def test_canjear_un_premio(client, db, cafe, headers, make_pass, wallet):
    make_pass(cafe, balance=120)
    cafe_id = save_program(client, headers).json()["rewards"][0]["id"]

    response = client.post("/passes/sello_prueba0001/canjear", json={"reward_id": cafe_id}, headers=headers)
    assert response.status_code == 200
    assert response.json()["new_balance"] == 20

    transaction = db.query(models.Transaction).one()
    assert (transaction.kind, transaction.points, transaction.reward_id) == ("redeem", -100, cafe_id)
    assert transaction.description == "Canje: Café gratis"
    assert wallet.updated[-1]["balance"] == 20


def test_no_se_canjea_sin_puntos_suficientes(client, cafe, headers, make_pass):
    make_pass(cafe, balance=70)
    cafe_id = save_program(client, headers).json()["rewards"][0]["id"]
    response = client.post("/passes/sello_prueba0001/canjear", json={"reward_id": cafe_id}, headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "Le faltan 30 puntos para canjear Café gratis"


def test_no_se_canjean_premios_desactivados_ni_de_otro_comercio(client, cafe, headers, make_business, login, make_pass):
    make_pass(cafe, balance=500)
    cafe_rewards = save_program(client, headers).json()["rewards"]
    save_program(client, headers, rewards=[cafe_rewards[0]])  # Se quita la torta

    make_business("Pizzería Nápoles", "pizzeria-napoles")
    other_reward = save_program(client, login("pizzeria-napoles")).json()["rewards"][0]["id"]

    for reward_id in (cafe_rewards[1]["id"], other_reward):
        response = client.post("/passes/sello_prueba0001/canjear", json={"reward_id": reward_id}, headers=headers)
        assert response.status_code == 404


def test_la_caja_ve_que_premios_puede_canjear(client, cafe, headers, make_pass):
    make_pass(cafe, balance=120)
    save_program(client, headers)
    data = client.get("/passes/sello_prueba0001", headers=headers).json()
    assert [(r["name"], r["available"], r["missing"]) for r in data["rewards"]] == [
        ("Café gratis", True, 0), ("Torta", False, 130)]
    assert data["program"]["points_mode"] == "fixed"


# --- Tarjeta y página pública ---

@pytest.mark.parametrize("balance, expected", [
    (70, "Te faltan 30 pts para: Café gratis"),
    (120, "¡Ya podés canjear: Café gratis!"),
    (300, "¡Ya podés canjear: Torta!"),
])
def test_progreso_hacia_el_proximo_premio(balance, expected):
    assert reward_progress([("Café gratis", 100), ("Torta", 250)], balance) == expected


def test_la_tarjeta_usa_el_progreso_y_si_no_hay_premios_el_texto_libre():
    with_rewards = GoogleWallet.CardDesign("Café", reward_text="Texto", rewards=[("Café gratis", 100)])
    without = GoogleWallet.CardDesign("Café", reward_text="Texto")
    assert GoogleWallet.build_visual_fields(with_rewards, "Ana", 40)["textModulesData"][1]["body"] == \
        "Te faltan 60 pts para: Café gratis"
    assert GoogleWallet.build_visual_fields(without, "Ana", 40)["textModulesData"][1]["body"] == "Texto"


def test_la_pagina_publica_muestra_premios_y_equivalencia(client, headers):
    save_program(client, headers, points_mode="amount", pesos_per_point=1000)
    data = client.get("/public/businesses/cafe-roma").json()
    assert data["rewards"] == [{"name": "Café gratis", "points_cost": 100}, {"name": "Torta", "points_cost": 250}]
    assert (data["points_mode"], data["pesos_per_point"]) == ("amount", 1000)
