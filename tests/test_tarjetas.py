"""Personalización de tarjetas: color, premio, logo, portada, imágenes públicas y diseño para Google Wallet."""

import base64
import struct
import zlib

import pytest
import branding
import GoogleWallet
import models


def png_data_url(width=4, height=4) -> str:
    """Un PNG mínimo y válido, armado a mano."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    pixels = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(pixels))
           + chunk(b"IEND", b""))
    return "data:image/png;base64," + base64.b64encode(png).decode()


JPG_DATA_URL = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 100).decode()


@pytest.fixture
def alta_con_marca(client):
    data = {"name": "Heladería Polo", "contact_email": "a@b.co", "password": "clave-polo-1",
            "brand_color": "#0f766e", "reward_text": "  10 sellos =   1 helado  ",
            "logo": png_data_url(), "hero": JPG_DATA_URL}

    def do_signup(**changes):
        return client.post("/public/businesses/alta", json={**data, **changes})
    return do_signup


@pytest.fixture
def polo(db, alta_con_marca):
    assert alta_con_marca().status_code == 201
    business = db.query(models.Business).filter_by(slug="heladeria-polo").one()
    business.status = "active"
    db.commit()
    return business


# --- Alta con marca ---

def test_alta_guarda_color_premio_e_imagenes(polo):
    assert polo.brand_color == "#0F766E"
    assert polo.reward_text == "10 sellos = 1 helado"
    assert {image.kind for image in polo.images} == {"logo", "hero"}


@pytest.mark.parametrize("field, value", [
    ("brand_color", "rojo"),
    ("reward_text", "x" * 61),
    ("logo", "data:image/gif;base64,R0lGOD"),
    ("logo", "data:image/png;base64," + base64.b64encode(b"no soy un png").decode()),
    ("hero", "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff" + b"0" * 1_600_000).decode()),
])
def test_alta_rechaza_marca_invalida(alta_con_marca, field, value):
    assert alta_con_marca(name="Otro Comercio", **{field: value}).status_code == 400


def test_alta_sin_personalizar(client, alta_con_marca):
    response = client.post("/public/businesses/alta", json={
        "name": "Sin Marca", "contact_email": "a@b.co", "password": "12345678"})
    assert response.status_code == 201
    public = client.get("/public/businesses/sin-marca").json()
    assert public["brand_color"] == GoogleWallet.DEFAULT_CARD_COLOR
    assert public["logo_url"] is None


# --- Página pública e imágenes ---

def test_pagina_publica_incluye_la_marca(client, polo):
    public = client.get("/public/businesses/heladeria-polo").json()
    assert public["brand_color"] == "#0F766E"
    assert public["reward_text"] == "10 sellos = 1 helado"
    assert public["logo_url"].startswith("/media/heladeria-polo/logo?v=")


def test_sirve_el_logo_con_cache_larga(client, polo):
    logo_url = client.get("/public/businesses/heladeria-polo").json()["logo_url"]
    response = client.get(logo_url)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert "immutable" in response.headers["cache-control"]


@pytest.mark.parametrize("path", ["/media/heladeria-polo/otra", "/media/no-existe/logo"])
def test_imagenes_inexistentes(client, polo, path):
    assert client.get(path).status_code == 404


# --- Diseño para Google Wallet ---

def test_en_local_la_tarjeta_sale_sin_imagenes(polo):
    design = branding.card_design(polo)
    assert design.color == "#0F766E"
    assert design.logo_url is None and design.hero_url is None


def test_publicado_usa_urls_https_para_las_imagenes(polo, monkeypatch):
    monkeypatch.setattr(branding, "PUBLIC_URL", "https://sello.com")
    design = branding.card_design(polo)
    assert design.logo_url.startswith("https://sello.com/media/heladeria-polo/logo?v=")
    assert design.hero_url.startswith("https://sello.com/media/heladeria-polo/hero?v=")


def test_campos_de_la_tarjeta(polo, monkeypatch):
    monkeypatch.setattr(branding, "PUBLIC_URL", "https://sello.com")
    fields = GoogleWallet.build_visual_fields(branding.card_design(polo), "ana garcía", 30)
    assert fields["cardTitle"]["defaultValue"]["value"] == "Heladería Polo"
    assert fields["header"]["defaultValue"]["value"] == "Ana García"
    assert fields["hexBackgroundColor"] == "#0F766E"
    assert [m["id"] for m in fields["textModulesData"]] == ["balance_module", "reward_module"]
    assert fields["textModulesData"][0]["body"] == "30 pts"
    assert "logo" in fields and "heroImage" in fields


def test_tarjeta_sin_marca_no_tiene_premio_ni_imagenes():
    fields = GoogleWallet.build_visual_fields(GoogleWallet.CardDesign("Sin Marca"), "Ana", 0)
    assert [m["id"] for m in fields["textModulesData"]] == ["balance_module"]
    assert "logo" not in fields and "heroImage" not in fields


def test_la_plantilla_muestra_puntos_y_premio_en_la_cara():
    row = GoogleWallet.CLASS_TEMPLATE_INFO["cardTemplateOverride"]["cardRowTemplateInfos"][0]["twoItems"]
    paths = [row[side]["firstValue"]["fields"][0]["fieldPath"] for side in ("startItem", "endItem")]
    assert paths == ["object.textModulesData['balance_module']", "object.textModulesData['reward_module']"]


# --- Edición desde la caja ---

def test_editar_requiere_sesion(client, polo):
    assert client.get("/branding").status_code == 401
    assert client.put("/branding", json={"brand_color": "#B91C1C"}).status_code == 401


def test_editar_desde_la_caja_y_sincronizar_tarjetas(client, polo, make_pass, login, wallet):
    make_pass(polo)
    headers = login("heladeria-polo", "clave-polo-1")
    assert client.get("/branding", headers=headers).json()["brand_color"] == "#0F766E"

    response = client.put("/branding", headers=headers,
                          json={"brand_color": "#b91c1c", "reward_text": "Nuevo premio", "remove_hero": True})
    data = response.json()
    assert response.status_code == 200
    assert data["brand_color"] == "#B91C1C"
    assert data["hero_url"] is None and data["logo_url"] is not None
    assert data["passes_to_update"] == 1
    assert wallet.synced_businesses == [polo.id]


def test_logo_nuevo_cambia_la_version_de_la_url(client, polo, login):
    headers = login("heladeria-polo", "clave-polo-1")
    old_url = client.get("/branding", headers=headers).json()["logo_url"]
    response = client.put("/branding", headers=headers,
                          json={"brand_color": "#B91C1C", "reward_text": "", "logo": png_data_url(8, 8)})
    assert response.json()["logo_url"] != old_url
    assert response.json()["reward_text"] is None


def test_un_dato_invalido_no_borra_lo_guardado(client, polo, login):
    headers = login("heladeria-polo", "clave-polo-1")
    assert client.put("/branding", headers=headers, json={"brand_color": "verde"}).status_code == 400
    assert client.get("/branding", headers=headers).json()["brand_color"] == "#0F766E"


def test_tarjetas_nuevas_y_cargas_de_puntos_usan_la_marca(client, polo, make_pass, register, login, wallet):
    make_pass(polo)
    register(business_slug="heladeria-polo")
    assert wallet.created[-1]["design"].color == "#0F766E"

    client.post("/passes/sello_prueba0001/sumar-puntos", json={"points": 10},
                headers=login("heladeria-polo", "clave-polo-1"))
    assert wallet.updated[-1]["design"].color == "#0F766E"
    assert wallet.updated[-1]["balance"] == 10


def test_sincronizacion_actualiza_todas_las_tarjetas_con_un_solo_token(polo, make_pass, monkeypatch):
    make_pass(polo, pass_id="sello_prueba0001", phone="1100000001")
    make_pass(polo, pass_id="sello_prueba0002", phone="1100000002")
    calls = []
    monkeypatch.setattr(branding, "get_google_auth_token", lambda: "token-de-prueba")
    monkeypatch.setattr(branding, "update_google_wallet_pass", lambda *a, **kw: calls.append(kw) or True)

    branding.sync_business_passes(polo.id)

    assert len(calls) == 2
    assert all(call["token"] == "token-de-prueba" for call in calls)
