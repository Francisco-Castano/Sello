"""
Preparación compartida de las pruebas.

Cada prueba usa una base de datos nueva en memoria y un Google Wallet simulado:
no se toca sello.db, no se lee google_credentials.json y no se sale a internet.
"""

import asyncio
import json as jsonlib
import os

# Antes de importar la app: base descartable, clave de sesión fija y sin administración ni URL pública
os.environ["SELLO_DATABASE_URL"] = "sqlite://"
os.environ["SELLO_SECRET_KEY"] = "clave-de-sesion-solo-para-pruebas"
os.environ.pop("SELLO_ADMIN_KEY", None)
os.environ.pop("SELLO_PUBLIC_URL", None)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import auth
import branding
import database
import GoogleWallet
import main
import models
from routers import branding as branding_router
from routers import passes


# --- Base de datos ---

@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    database.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(branding, "SessionLocal", factory)

    def get_test_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[database.get_db] = get_test_db
    yield factory
    main.app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def db(session_factory):
    session = session_factory()
    yield session
    session.close()


# --- Google Wallet simulado ---

class FakeWallet:
    """Guarda lo que la app le habría mandado a Google, para revisarlo en las pruebas."""

    def __init__(self):
        self.created = []         # Tarjetas firmadas al registrar clientes
        self.updated = []         # Actualizaciones de saldo y diseño
        self.synced_businesses = []
        self.fail_signing = False

    def generate_url(self, **kwargs):
        if self.fail_signing:
            raise FileNotFoundError("google_credentials.json")
        self.created.append(kwargs)
        return f"https://pay.google.com/gp/v/save/{kwargs['pass_id']}"

    def update_pass(self, *args, **kwargs):
        self.updated.append(kwargs)
        return True


@pytest.fixture(autouse=True)
def wallet(monkeypatch):
    fake = FakeWallet()

    def no_network(*args, **kwargs):
        raise AssertionError("Una prueba intentó conectarse a Google Wallet")

    monkeypatch.setattr(GoogleWallet, "get_google_auth_token", no_network)
    monkeypatch.setattr(branding, "get_google_auth_token", no_network)
    monkeypatch.setattr(passes, "generate_google_wallet_url", fake.generate_url)
    monkeypatch.setattr(passes, "update_google_wallet_pass", fake.update_pass)
    monkeypatch.setattr(branding_router, "sync_business_passes", fake.synced_businesses.append)
    monkeypatch.setattr(branding, "PUBLIC_URL", "")
    return fake


# --- Cliente HTTP ---

class Response:
    def __init__(self, status_code: int, headers: dict, content: bytes):
        self.status_code = status_code
        self.headers = headers
        self.content = content

    def json(self):
        return jsonlib.loads(self.content)


class ApiClient:
    """Llama a la app directamente (sin servidor), como lo haría un navegador."""

    def request(self, method: str, path: str, json=None, headers: dict | None = None) -> Response:
        path, _, query = path.partition("?")
        body = jsonlib.dumps(json).encode() if json is not None else b""
        raw_headers = [(b"host", b"testserver")]
        if json is not None:
            raw_headers.append((b"content-type", b"application/json"))
        raw_headers += [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]

        messages = []

        async def run():
            sent = False

            async def receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                await asyncio.sleep(3600)

            async def send(message):
                messages.append(message)

            scope = {
                "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
                "root_path": "", "query_string": query.encode(), "headers": raw_headers,
                "server": ("testserver", 80), "client": ("testclient", 50000),
            }
            await main.app(scope, receive, send)

        asyncio.run(run())
        start = next(m for m in messages if m["type"] == "http.response.start")
        response_headers = {k.decode().lower(): v.decode() for k, v in start["headers"]}
        content = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
        return Response(start["status"], response_headers, content)

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)


@pytest.fixture
def client(session_factory):
    return ApiClient()


# --- Ayudas para armar escenarios ---

DEFAULT_PASSWORD = "clave-segura-1"


@pytest.fixture
def make_business(db):
    def make(name="Café Roma", slug="cafe-roma", password=DEFAULT_PASSWORD, status="active", **fields):
        business = models.Business(name=name, slug=slug, status=status, **fields)
        db.add(business)
        db.flush()
        if password:
            db.add(models.PosCredential(business_id=business.id, password_hash=auth.hash_password(password)))
        db.commit()
        return business
    return make


@pytest.fixture
def login(client):
    def do_login(slug="cafe-roma", password=DEFAULT_PASSWORD) -> dict:
        response = client.post("/auth/login", json={"business_slug": slug, "password": password})
        assert response.status_code == 200, response.content
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    return do_login


@pytest.fixture
def register(client):
    def do_register(**changes):
        data = {
            "name": "Lucía Pérez",
            "phone": "11 5555-1234",
            "business_slug": "cafe-roma",
            "accept_privacy": True,
            **changes,
        }
        return client.post("/passes/crear-google", json=data)
    return do_register


@pytest.fixture
def make_pass(db):
    def make(business, name="Ana García", phone="1144443333", balance=0, pass_id="sello_prueba0001"):
        user = db.query(models.User).filter_by(phone=phone).first() or models.User(name=name, phone=phone)
        db.add(user)
        db.flush()
        pass_obj = models.Pass(id=pass_id, business_id=business.id, user_id=user.id, balance=balance)
        db.add(pass_obj)
        db.commit()
        return pass_obj
    return make
