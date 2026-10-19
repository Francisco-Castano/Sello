"""Actualización automática de la base al arrancar: bases viejas y varios servidores a la vez."""

import sqlite3
import threading

import pytest
from sqlalchemy import create_engine
import database


@pytest.fixture
def old_database(tmp_path, monkeypatch):
    """Una base con el esquema original: comercios sin estado ni marca, y nada más."""
    path = tmp_path / "vieja.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE businesses (id VARCHAR NOT NULL, name VARCHAR NOT NULL, "
                "slug VARCHAR NOT NULL, created_at DATETIME, PRIMARY KEY (id))")
    con.execute("INSERT INTO businesses VALUES ('1', 'Viejo', 'viejo', NULL)")
    con.commit()
    con.close()
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 10})
    monkeypatch.setattr(database, "engine", engine)
    yield path
    engine.dispose()


def columns(path, table):
    return {row[1] for row in sqlite3.connect(path).execute(f"PRAGMA table_info({table})")}


def tables(path):
    return {row[0] for row in sqlite3.connect(path).execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_actualiza_una_base_vieja_y_deja_activos_a_los_comercios(old_database):
    database.setup_database()
    database.setup_database()  # Correrla dos veces no tiene que fallar

    assert {"status", "contact_email", "brand_color", "reward_text"} <= columns(old_database, "businesses")
    assert {"birthday", "birth_year"} <= columns(old_database, "users")
    assert {"privacy_accepted_at", "privacy_version", "marketing_opt_in"} <= columns(old_database, "passes")
    assert {"users", "passes", "transactions", "pos_credentials", "business_images"} <= tables(old_database)

    status = sqlite3.connect(old_database).execute("SELECT status FROM businesses").fetchone()[0]
    assert status == "active"


def test_varios_servidores_arrancando_a_la_vez(old_database):
    errors = []

    def start_server():
        try:
            database.setup_database()
        except Exception as e:
            errors.append(repr(e))

    threads = [threading.Thread(target=start_server) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert {"birthday", "birth_year"} <= columns(old_database, "users")
