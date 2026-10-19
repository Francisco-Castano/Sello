"""Funciones chicas: nombres, teléfonos, edad, links de comercios y claves."""

from datetime import date

import pytest
import auth
from names import format_person_name
from routers.businesses import generate_slug
from routers.passes import age_on, normalize_phone


@pytest.mark.parametrize("raw, expected", [
    ("felipe amelong", "Felipe Amelong"),
    ("  MARÍA   DE LA cruz ", "María de la Cruz"),
    ("ana-lía o'connor", "Ana-Lía O'Connor"),
    ("juan y pedro", "Juan y Pedro"),
    ("de la torre", "De la Torre"),
    ("Ñandú", "Ñandú"),
    ("   ", ""),
])
def test_formato_de_nombres(raw, expected):
    assert format_person_name(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("11 2345-6789", "1123456789"),
    ("+54 9 11 2345 6789", "5491123456789"),
    ("1234567", None),        # Muy corto
    ("1" * 16, None),         # Muy largo
    ("", None),
])
def test_normalizacion_de_telefonos(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("birthday, today, expected", [
    ("02-29", date(2026, 2, 28), 33),
    ("02-29", date(2026, 3, 1), 34),
    ("10-19", date(2026, 10, 19), 26),
    ("10-20", date(2026, 10, 19), 25),
])
def test_edad(birthday, today, expected):
    birth_year = 1992 if birthday == "02-29" else 2000
    assert age_on(birth_year, birthday, today) == expected


@pytest.mark.parametrize("name, slug", [
    ("Café Ñandú", "cafe-nandu"),
    ("  Pizzería   Nápoles!! ", "pizzeria-napoles"),
    ("Groovin", "groovin"),
])
def test_links_de_comercios(name, slug):
    assert generate_slug(name) == slug


def test_las_claves_se_guardan_cifradas_y_se_verifican():
    stored = auth.hash_password("clave-segura-1")
    assert stored.startswith("scrypt$") and "clave-segura-1" not in stored
    assert auth.verify_password("clave-segura-1", stored)
    assert not auth.verify_password("otra-clave", stored)
    assert not auth.verify_password("clave-segura-1", "formato-roto")
