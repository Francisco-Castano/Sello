"""Comercios: alta desde /alta, aprobación, suspensión, página pública y administración."""

import pytest
import models


@pytest.fixture
def alta(client):
    def do_signup(**changes):
        data = {"name": "Café Ñandú", "slug": "cafe-nandu", "contact_email": "Hola@Nandu.com",
                "password": "clave-nandu-1", **changes}
        return client.post("/public/businesses/alta", json=data)
    return do_signup


def set_status(db, slug, status):
    db.query(models.Business).filter_by(slug=slug).one().status = status
    db.commit()


# --- Alta ---

def test_alta_queda_pendiente_con_email_y_clave_cifrada(client, db, alta):
    response = alta()
    assert response.status_code == 201
    assert response.json() == {"status": "pending", "name": "Café Ñandú", "slug": "cafe-nandu"}

    business = db.query(models.Business).one()
    assert business.contact_email == "hola@nandu.com"
    assert business.pos_credential.password_hash.startswith("scrypt$")


def test_sin_link_se_genera_del_nombre_sin_tildes(client, alta):
    response = alta(name="Pizzería Nápoles", slug=None)
    assert response.json()["slug"] == "pizzeria-napoles"


@pytest.mark.parametrize("changes, status", [
    ({"slug": "Mal Link!"}, 400),
    ({"slug": "ab"}, 400),
    ({"contact_email": "no-es-email"}, 400),
    ({"password": "corta"}, 400),
])
def test_alta_rechaza_datos_invalidos(client, alta, changes, status):
    assert alta(**changes).status_code == status


def test_alta_rechaza_un_link_en_uso(client, alta, make_business):
    make_business(slug="cafe-nandu")
    assert alta().status_code == 409


# --- Estados ---

def test_comercio_pendiente_no_opera(client, alta, register):
    alta()
    public = client.get("/public/businesses/cafe-nandu").json()
    assert public["active"] is False

    wrong = client.post("/auth/login", json={"business_slug": "cafe-nandu", "password": "otra-clave-1"})
    assert wrong.status_code == 401  # Con clave incorrecta no se revela el estado

    right = client.post("/auth/login", json={"business_slug": "cafe-nandu", "password": "clave-nandu-1"})
    assert right.status_code == 403
    assert "pendiente" in right.json()["detail"]

    assert register(business_slug="cafe-nandu").status_code == 403


def test_comercio_aprobado_opera(client, db, alta, register, login):
    alta()
    set_status(db, "cafe-nandu", "active")

    assert client.get("/public/businesses/cafe-nandu").json()["active"] is True
    headers = login("cafe-nandu", "clave-nandu-1")
    pass_id = register(business_slug="cafe-nandu").json()["pass_id"]
    response = client.post(f"/passes/{pass_id}/sumar-puntos", json={"points": 5}, headers=headers)
    assert response.status_code == 200


def test_suspender_corta_las_cajas_abiertas(client, db, alta, register, login):
    alta()
    set_status(db, "cafe-nandu", "active")
    headers = login("cafe-nandu", "clave-nandu-1")
    pass_id = register(business_slug="cafe-nandu").json()["pass_id"]

    set_status(db, "cafe-nandu", "suspended")

    response = client.post(f"/passes/{pass_id}/sumar-puntos", json={"points": 5}, headers=headers)
    assert response.status_code == 401
    relogin = client.post("/auth/login", json={"business_slug": "cafe-nandu", "password": "clave-nandu-1"})
    assert relogin.status_code == 403
    assert "suspendido" in relogin.json()["detail"]


def test_pagina_publica_de_comercio_inexistente(client):
    assert client.get("/public/businesses/no-existe").status_code == 404


# --- Administración por API ---

def test_administracion_cerrada_sin_variable(client, monkeypatch):
    monkeypatch.delenv("SELLO_ADMIN_KEY", raising=False)
    assert client.get("/businesses/").status_code == 403


def test_administracion_con_clave(client, make_business, monkeypatch):
    make_business()
    monkeypatch.setenv("SELLO_ADMIN_KEY", "clave-admin-de-prueba")
    assert client.get("/businesses/", headers={"X-Admin-Key": "otra"}).status_code == 403
    response = client.get("/businesses/", headers={"X-Admin-Key": "clave-admin-de-prueba"})
    assert response.status_code == 200
    assert [b["slug"] for b in response.json()] == ["cafe-roma"]
