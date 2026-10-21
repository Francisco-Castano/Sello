# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

Sello es una plataforma de tarjetas de fidelidad para comercios en Google Wallet (Apple Wallet todavía no está implementado). FastAPI + SQLAlchemy, con páginas HTML estáticas y JavaScript sin frameworks ni paso de build. Todo el texto de la interfaz, los mensajes de error y los comentarios del código están en español rioplatense (voseo); mantenerlo así.

## Comandos

```bash
.venv/bin/uvicorn main:app --reload --port 8000        # servidor de desarrollo
.venv/bin/python -m pytest                              # todas las pruebas (~3 s)
.venv/bin/python -m pytest tests/test_caja.py           # un archivo
.venv/bin/python -m pytest tests/test_premios.py::test_canjear_un_premio   # una prueba
.venv/bin/python -m pytest -k canje                     # por nombre
pip install -r requirements-dev.txt                     # pytest (además de requirements.txt)
```

`admin.py` es la herramienta del Super Admin (no hay panel web): `comercios`, `pendientes`, `aprobar <slug>`, `suspender <slug>`, `crear-comercio "Nombre" [slug]`, `clave-pos <slug>` (pide la clave por consola) y `plantilla-wallet` (aplica la plantilla de la clase en la cuenta emisora de Google; se corre una vez por cuenta).

## Arquitectura

- `main.py` arma la app, sirve las páginas (`/`, `/c/{slug}`, `/alta`, `/pos`, `/privacidad`) con `Cache-Control: no-cache` (también todo `/static/`) y llama a `setup_database()` al importarse.
- La lógica de dominio vive en módulos sueltos en la raíz (`auth.py`, `branding.py`, `program.py`, `names.py`, `GoogleWallet.py`) y los endpoints en `routers/`. Los routers importan esos módulos con imports absolutos (`from program import ...`), así que la raíz tiene que estar en el path.
- Páginas: `home.html` (institucional), `index.html` (registro de clientes en `/c/<slug>`), `alta.html` (alta de comercios), `pos.html` (la caja: escaneo, carga de puntos, canje, "Premios" y "Mi tarjeta") y `privacidad.html`. `card-editor.js` es el editor de tarjeta con vista previa, compartido por `alta.html` y `pos.html`.

### Flujos que cruzan varios archivos

- **Comercios:** se dan de alta en `/alta` y quedan `pending` hasta `admin.py aprobar`. Solo los `active` pueden entrar a la caja o registrar clientes; `suspended` corta además las sesiones abiertas.
- **Caja (auth):** una clave compartida por comercio (`PosCredential`, scrypt). El login devuelve un JWT HS256 que incluye un hash de la clave (`ver`): cambiar la clave invalida todas las sesiones de ese comercio. `get_current_business` es la dependencia que protege todo lo de la caja y filtra por comercio; un pase de otro comercio responde 404, no 403. `/businesses/` solo se abre con el header `X-Admin-Key` igual a `SELLO_ADMIN_KEY`.
- **Registro de clientes** (`POST /passes/crear-google`): el teléfono, normalizado a dígitos, identifica al cliente entre comercios. Si ya tiene pase en ese comercio se le devuelve el mismo (no se duplican), y un teléfono existente con otro nombre se rechaza con 409. Guarda los consentimientos por pase junto con `PRIVACY_VERSION` (en `routers/passes.py`; hay que cambiarla cuando se publique la política definitiva). El link de Wallet se firma antes de guardar, así un error de credenciales no deja datos a medias.
- **Puntos y premios** (`program.py`): cada comercio tiene `points_mode` `fixed` (puntos sugeridos por compra) o `amount` (1 punto cada `pesos_per_point` pesos completos). Cada `Transaction` tiene `kind`: `earn`, `redeem` o `adjust`. Los premios no se borran: se desactivan (`active=False`) para conservar el historial; usar `business.active_rewards`.
- **Google Wallet:** `GoogleWallet.build_visual_fields()` es la única fuente de los campos visibles y se usa tanto al crear (link JWT "save to wallet") como al actualizar (PATCH del objeto). `branding.card_design(business)` arma el `CardDesign` del comercio. Puntos y Premio aparecen en la cara de la tarjeta gracias a `CLASS_TEMPLATE_INFO` en la clase compartida `sello_generic_v2`. Cuando un comercio cambia su marca o sus premios, `branding.sync_business_passes` actualiza en segundo plano todas sus tarjetas ya entregadas.
- **Imágenes** (logo y portada): se guardan en la base (`BusinessImage`, no en disco) y se sirven en `/media/{slug}/{kind}?v=<hash>`. Solo se mandan a Wallet si `SELLO_PUBLIC_URL` es una URL `https` pública; en localhost las tarjetas salen sin imágenes.

### Base de datos

SQLite en `sello.db` (no está en git; cada desarrollador tiene la suya) o lo que indique `SELLO_DATABASE_URL`. **No hay migraciones:** `setup_database()` crea las tablas que faltan y agrega las columnas listadas en `ADDED_COLUMNS` (`database.py`). Una columna nueva en una tabla que ya existe tiene que sumarse a `ADDED_COLUMNS` además del modelo; si no, las bases existentes se rompen. Las tablas nuevas se crean solas. `setup_database()` tolera varios servidores arrancando a la vez, porque `--reload` en dos procesos ya provocó choques.

### Configuración

Variables de entorno: `SELLO_DATABASE_URL`, `SELLO_SECRET_KEY` (si falta, se genera `.secret_key`, ignorado por git), `SELLO_ADMIN_KEY` y `SELLO_PUBLIC_URL`. `google_credentials.json` (cuenta de servicio de Wallet) está en `.gitignore`. Ya se filtró una vez y hubo que reescribir el historial y revocar las claves, así que nunca agregarlo con `git add -f` ni con comandos que suman todo el directorio.

## Pruebas

`tests/conftest.py` arma una base SQLite en memoria por prueba y define el `SELLO_*` de prueba antes de importar la app. Las pruebas no tocan `sello.db` ni la red. El fixture autouse `wallet` (`FakeWallet`) reemplaza las llamadas a Google y hace fallar cualquier intento de obtener un token real. Si un módulo nuevo importa directamente `sync_business_passes`, `update_google_wallet_pass` o similares, hay que parchearlo también en ese fixture: ya pasó con `routers/program.py`. El cliente HTTP llama a la app ASGI a mano porque `starlette.testclient` pide `httpx2`, que no está instalado. Fixtures útiles: `make_business`, `login`, `register`, `make_pass`.

## Estado

- La política de privacidad (`static/privacidad.html`) es un borrador con datos `[entre corchetes]` pendientes y revisión legal pendiente.
- La cuenta emisora de Google Wallet está en modo de prueba: las tarjetas muestran "[TEST ONLY]" y solo las pueden guardar cuentas de prueba.
- El próximo paso planificado es publicar en un hosting (se habló de Render con Postgres). Eso implica sumar Alembic, credenciales de Google por variable de entorno y límite de intentos en el login, el alta y el registro, que todavía no existen.
- El repo en GitHub es `Francisco-Castano/Sello`; se trabaja directo sobre `main`.
