"""Caja (/pos): login con la clave del comercio, permisos y carga de puntos."""

import pytest
import auth
import models


@pytest.fixture
def two_businesses(make_business, make_pass):
    cafe = make_business("Café Roma", "cafe-roma")
    other = make_business("Pizzería Nápoles", "pizzeria-napoles", password="clave-pizzeria-1")
    pass_obj = make_pass(cafe, balance=20)
    return cafe, other, pass_obj


# --- Login ---

def test_login_correcto_devuelve_token_y_comercio(client, make_business):
    make_business()
    response = client.post("/auth/login", json={"business_slug": "cafe-roma", "password": "clave-segura-1"})
    assert response.status_code == 200
    assert response.json()["business"] == "Café Roma"
    assert response.json()["access_token"]


@pytest.mark.parametrize("slug, password", [
    ("cafe-roma", "clave-incorrecta"),
    ("no-existe", "clave-segura-1"),
])
def test_login_rechaza_clave_o_comercio_incorrectos_con_el_mismo_mensaje(client, make_business, slug, password):
    make_business()
    response = client.post("/auth/login", json={"business_slug": slug, "password": password})
    assert response.status_code == 401
    assert response.json()["detail"] == "Comercio o clave incorrectos"


def test_comercio_sin_clave_no_puede_entrar(client, make_business):
    make_business(password=None)
    response = client.post("/auth/login", json={"business_slug": "cafe-roma", "password": "cualquiera"})
    assert response.status_code == 401


def test_auth_me_devuelve_el_comercio_logueado(client, make_business, login):
    make_business()
    response = client.get("/auth/me", headers=login())
    assert response.json() == {"business": "Café Roma", "business_slug": "cafe-roma"}


# --- Permisos ---

@pytest.mark.parametrize("headers", [None, {"Authorization": "Bearer token-falso"}])
def test_sin_sesion_valida_no_se_ve_ni_se_carga_nada(client, two_businesses, headers):
    assert client.get("/passes/sello_prueba0001", headers=headers).status_code == 401
    response = client.post("/passes/sello_prueba0001/sumar-puntos", json={"points": 10}, headers=headers)
    assert response.status_code == 401


def test_un_comercio_no_ve_ni_carga_pases_de_otro(client, two_businesses, login):
    headers = login("pizzeria-napoles", "clave-pizzeria-1")
    assert client.get("/passes/sello_prueba0001", headers=headers).status_code == 404
    response = client.post("/passes/sello_prueba0001/sumar-puntos", json={"points": 10}, headers=headers)
    assert response.status_code == 404


def test_cambiar_la_clave_cierra_las_sesiones_de_ese_comercio(client, db, two_businesses, login):
    cafe, other, _ = two_businesses
    cafe_headers = login("cafe-roma")
    other_headers = login("pizzeria-napoles", "clave-pizzeria-1")

    cafe.pos_credential.password_hash = auth.hash_password("clave-nueva-123")
    db.commit()

    assert client.get("/auth/me", headers=cafe_headers).status_code == 401
    assert client.get("/auth/me", headers=other_headers).status_code == 200


# --- Puntos ---

def test_el_comercio_ve_su_pase(client, two_businesses, login):
    response = client.get("/passes/sello_prueba0001", headers=login())
    assert response.status_code == 200
    assert response.json()["balance"] == 20


def test_sumar_puntos_actualiza_saldo_historial_y_wallet(client, db, two_businesses, login, wallet):
    response = client.post("/passes/sello_prueba0001/sumar-puntos",
                           json={"points": 10, "description": "Café con leche"}, headers=login())
    assert response.status_code == 200
    assert response.json()["new_balance"] == 30
    assert response.json()["google_wallet_synced"] is True

    transaction = db.query(models.Transaction).one()
    assert (transaction.points, transaction.description) == (10, "Café con leche")
    assert wallet.updated[-1]["balance"] == 30


def test_canje_descuenta_puntos(client, two_businesses, login):
    response = client.post("/passes/sello_prueba0001/sumar-puntos", json={"points": -20}, headers=login())
    assert response.json()["new_balance"] == 0


@pytest.mark.parametrize("points, message", [
    (-21, "Saldo insuficiente para el canje"),
    (0, "La cantidad de puntos no puede ser 0"),
])
def test_rechaza_canjes_sin_saldo_y_cargas_de_cero(client, two_businesses, login, points, message):
    response = client.post("/passes/sello_prueba0001/sumar-puntos", json={"points": points}, headers=login())
    assert response.status_code == 400
    assert response.json()["detail"] == message


def test_no_carga_puntos_a_un_pase_inactivo(client, db, two_businesses, login):
    _, _, pass_obj = two_businesses
    pass_obj.status = "suspended"
    db.commit()
    response = client.post("/passes/sello_prueba0001/sumar-puntos", json={"points": 10}, headers=login())
    assert response.status_code == 400
