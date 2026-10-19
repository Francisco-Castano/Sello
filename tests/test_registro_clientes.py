"""Registro de clientes en /c/<slug>: datos, consentimientos, tarjetas sin duplicar y errores."""

from datetime import date

import pytest
import models
from routers import passes


@pytest.fixture
def cafe(make_business):
    return make_business()


# --- Páginas ---

@pytest.mark.parametrize("path", ["/", "/c/cafe-roma", "/alta", "/pos", "/privacidad"])
def test_las_paginas_se_sirven_y_se_revalidan(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_los_archivos_estaticos_se_revalidan(client):
    response = client.get("/static/card-editor.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


# --- Registro correcto ---

def test_registro_completo(client, db, cafe, register, wallet):
    response = register(name="  lucía  pérez ", birthday_day=29, birthday_month=2, birthday_year=1992,
                        marketing_opt_in=True)
    assert response.status_code == 200
    data = response.json()
    assert data["existing"] is False
    assert data["client_name"] == "Lucía Pérez"
    assert data["wallet_url"].startswith("https://pay.google.com/")
    assert len(data["pass_id"]) == len("sello_") + 16

    user = db.query(models.User).one()
    assert user.phone == "1155551234"
    assert (user.birthday, user.birth_year) == ("02-29", 1992)

    pass_obj = db.get(models.Pass, data["pass_id"])
    assert pass_obj.business_id == cafe.id
    assert pass_obj.marketing_opt_in is True
    assert pass_obj.privacy_version == passes.PRIVACY_VERSION
    assert pass_obj.privacy_accepted_at is not None

    assert wallet.created[-1]["design"].business_name == "Café Roma"


def test_la_fecha_de_nacimiento_es_opcional(client, db, cafe, register):
    assert register().status_code == 200
    assert db.query(models.User).one().birthday is None


# --- Validaciones ---

@pytest.mark.parametrize("changes, message", [
    ({"accept_privacy": False}, "privacidad"),
    ({"phone": ""}, "teléfono"),
    ({"phone": "1234"}, "teléfono"),
    ({"name": "   "}, "nombre"),
    ({"birthday_day": 12, "birthday_month": 3}, "año"),
    ({"birthday_day": 31, "birthday_month": 2, "birthday_year": 1990}, "no es válida"),
    ({"birthday_day": 29, "birthday_month": 2, "birthday_year": 1991}, "no es válida"),
    ({"birthday_day": 1, "birthday_month": 1, "birthday_year": 1899}, "no es válida"),
    ({"birthday_day": 1, "birthday_month": 1, "birthday_year": date.today().year + 1}, "no es válida"),
])
def test_rechaza_datos_invalidos_sin_guardar_nada(client, db, cafe, register, changes, message):
    response = register(**changes)
    assert response.status_code == 400
    assert message in response.json()["detail"]
    assert db.query(models.User).count() == 0
    assert db.query(models.Pass).count() == 0


def test_sin_comercio_es_un_error_y_no_cae_en_demo_cafe(client, cafe):
    response = client.post("/passes/crear-google", json={"name": "Ana", "phone": "1155551234", "accept_privacy": True})
    assert response.status_code == 422


def test_comercio_inexistente(client, register):
    assert register(business_slug="no-existe").status_code == 404


def test_sin_credenciales_de_google_da_un_error_claro_y_no_guarda_nada(client, db, cafe, register, wallet):
    wallet.fail_signing = True
    response = register()
    assert response.status_code == 503
    assert "credenciales" in response.json()["detail"]
    assert db.query(models.Pass).count() == 0
    assert db.query(models.User).count() == 0


# --- Tarjetas sin duplicar ---

def test_volver_a_registrarse_devuelve_la_misma_tarjeta(client, db, cafe, register):
    first = register(birthday_day=29, birthday_month=2, birthday_year=1992, marketing_opt_in=True).json()
    second = register(name="LUCIA PEREZ", phone="+54 11 5555 1234".replace("+54 ", ""),
                      birthday_day=5, birthday_month=5, birthday_year=2000, marketing_opt_in=False).json()

    assert second["existing"] is True
    assert second["pass_id"] == first["pass_id"]
    assert db.query(models.Pass).count() == 1

    user = db.query(models.User).one()
    assert (user.birthday, user.birth_year) == ("02-29", 1992)  # No se pisa la fecha ya cargada
    assert db.get(models.Pass, first["pass_id"]).marketing_opt_in is False  # Vale la última elección


def test_telefono_registrado_con_otro_nombre_se_rechaza(client, cafe, register):
    register()
    response = register(name="Otra Persona")
    assert response.status_code == 409


def test_mismo_cliente_en_otro_comercio_tiene_otra_tarjeta(client, db, cafe, make_business, register):
    make_business("Pizzería Nápoles", "pizzeria-napoles")
    first = register().json()
    second = register(business_slug="pizzeria-napoles").json()

    assert second["existing"] is False
    assert second["pass_id"] != first["pass_id"]
    assert db.query(models.User).count() == 1


# --- La caja ve el cumpleaños ---

def test_la_caja_ve_cumpleanos_edad_y_aviso_del_dia(client, db, cafe, register, login):
    pass_id = register(birthday_day=29, birthday_month=2, birthday_year=1992).json()["pass_id"]
    headers = login()
    today = date.today()

    data = client.get(f"/passes/{pass_id}", headers=headers).json()
    assert data["birthday"] == "02-29"
    assert data["age"] == today.year - 1992 - (today.strftime("%m-%d") < "02-29")

    db.query(models.User).one().birthday = today.strftime("%m-%d")
    db.commit()
    data = client.get(f"/passes/{pass_id}", headers=headers).json()
    assert data["birthday_today"] is True
    assert data["age"] == today.year - 1992


def test_cliente_sin_fecha_no_tiene_aviso(client, cafe, make_pass, login):
    make_pass(cafe)
    data = client.get("/passes/sello_prueba0001", headers=login()).json()
    assert (data["birthday"], data["birthday_today"], data["age"]) == (None, False, None)
