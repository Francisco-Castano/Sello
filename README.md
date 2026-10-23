# Sello

Sello es una plataforma de tarjetas de fidelidad para comercios en Google Wallet. El comercio comparte su link (`/c/<slug>`), el cliente guarda la tarjeta en el celular sin bajar ninguna app, y en cada compra el comercio le carga puntos escaneando el QR desde la caja (`/pos`), que funciona en el navegador. Los puntos se actualizan solos en la tarjeta del cliente y se canjean por los premios que define cada comercio.

Apple Wallet todavía no está implementado.

Está hecho con FastAPI y SQLAlchemy. Las páginas son HTML y JavaScript sin frameworks ni paso de build.

## Requisitos

- Python 3.13 y git.
- `google_credentials.json` (la cuenta de servicio de Google Wallet), solo si querés generar tarjetas reales. Pedíselo al otro desarrollador por un canal privado y guardalo en la raíz del proyecto. **Nunca lo subas al repo**: ya se filtró una vez y hubo que reescribir el historial y revocar las claves. Está en `.gitignore`; no lo agregues con `git add -f` ni con `git add .`.

Sin ese archivo funciona todo menos el botón "Añadir a Google Wallet".

## Instalación

**macOS**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn main:app --reload --port 8000
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\uvicorn main:app --reload --port 8000
```

Después abrí <http://localhost:8000>. La primera vez se crean solos `sello.db` (la base local) y `.secret_key` (la clave que firma las sesiones de la caja). Los dos están en `.gitignore`: cada desarrollador tiene los suyos.

Si cambian las dependencias (`requirements.txt`), volvé a correr el `pip install`.

## Tu primer comercio de prueba

Con el entorno instalado, en otra terminal:

```bash
.venv/bin/python admin.py crear-comercio "Café Demo" demo-cafe
.venv/bin/python admin.py clave-pos demo-cafe
```

En Windows es lo mismo, con `.venv\Scripts\python`. `clave-pos` te pide la clave por consola (mínimo 8 caracteres).

Los comercios creados con `admin.py` quedan activos. Ahora podés:

- Entrar a la caja en <http://localhost:8000/pos> con `demo-cafe` y la clave que pusiste.
- Registrarte como cliente en <http://localhost:8000/c/demo-cafe>.

En localhost las tarjetas salen sin logo ni portada (ver `SELLO_PUBLIC_URL` más abajo).

## Páginas

| Ruta | Qué es | Para quién |
|---|---|---|
| `/` | Página institucional que explica Sello | Cualquiera |
| `/alta` | Pedido de alta de un comercio (queda pendiente hasta que se apruebe) | Comercios nuevos |
| `/c/{slug}` | Registro de clientes y botón para guardar la tarjeta | Clientes del comercio |
| `/pos` | La caja: escaneo, carga de puntos, canjes, premios y diseño de la tarjeta | Comercios activos |
| `/privacidad` | Política de privacidad (borrador) | Cualquiera |

## admin.py

No hay panel web de administración: todo se hace desde la terminal con `python admin.py <comando>`.

| Comando | Qué hace |
|---|---|
| `comercios` | Lista todos los comercios con su estado |
| `pendientes` | Lista los pedidos de alta que esperan aprobación |
| `aprobar <slug>` | Habilita un comercio pendiente |
| `suspender <slug>` | Suspende un comercio y le corta las sesiones abiertas de la caja |
| `crear-comercio "Nombre" [slug]` | Crea un comercio activo; si no pasás el slug, se arma con el nombre |
| `clave-pos <slug>` | Define o cambia la clave de la caja (cierra las sesiones abiertas) |
| `plantilla-wallet` | Aplica la plantilla de la tarjeta en la cuenta emisora de Google. Se corre una vez por cuenta |

## Configuración

Todo es opcional para desarrollar en local.

| Variable | Para qué sirve | Si no está |
|---|---|---|
| `SELLO_DATABASE_URL` | Base de datos (ej: Postgres) | Usa `sello.db` en la carpeta del proyecto |
| `SELLO_SECRET_KEY` | Clave que firma las sesiones de la caja | Se genera `.secret_key` |
| `SELLO_ADMIN_KEY` | Abre la administración por API (`/businesses/`, header `X-Admin-Key`) | Esa API queda cerrada; se usa `admin.py` |
| `SELLO_PUBLIC_URL` | URL pública `https` del servidor, desde donde Google descarga logos y portadas | Las tarjetas salen sin imágenes |

## Pruebas

Las pruebas usan una base de datos en memoria y un Google Wallet simulado: no tocan `sello.db`, no necesitan `google_credentials.json` y no se conectan a internet. Tardan unos segundos.

```bash
.venv/bin/python -m pytest                                  # todas
.venv/bin/python -m pytest tests/test_caja.py               # un archivo
.venv/bin/python -m pytest -k canje                         # las que tengan "canje" en el nombre
```

Están en `tests/`, un archivo por área: caja, registro de clientes, comercios, premios, tarjetas, base de datos y utilidades. Los fixtures compartidos (`make_business`, `login`, `register`, `make_pass`, etc.) están en `tests/conftest.py`.

## Cómo está armado

```
main.py            arma la app y sirve las páginas
database.py        conexión y creación de tablas (sin migraciones)
models.py          tablas: comercios, pases, transacciones, premios, imágenes
auth.py            claves de caja y sesiones (JWT)
program.py         puntos y premios
branding.py        diseño de la tarjeta de cada comercio
GoogleWallet.py    todo lo que habla con Google Wallet
names.py           formato de nombres de personas
admin.py           herramienta del Super Admin
routers/           endpoints de la API
static/            páginas HTML y card-editor.js
tests/             pruebas automáticas
```

Los flujos que cruzan varios archivos (registro de clientes, sesiones de la caja, sincronización con Wallet, imágenes) están explicados en [CLAUDE.md](CLAUDE.md). Las convenciones del proyecto están en [.claude/rules/](.claude/rules/).

## Cómo trabajamos

- Trabajamos directo sobre `main`. Antes de pushear, `git fetch` para ver si el otro subió algo.
- Agregá archivos por nombre (`git add archivo1 archivo2`), nunca `git add -A` ni `git add .`: en la carpeta viven `google_credentials.json`, `sello.db` y `.secret_key`.
- Commits en español, con un título corto en primera persona ("Agrego…", "Saco…").
- Corré las pruebas antes de cada commit. Todo comportamiento nuevo de la API lleva su prueba.
- No hay migraciones: `setup_database()` crea las tablas que faltan, pero una columna nueva en una tabla existente también tiene que sumarse a `ADDED_COLUMNS` en `database.py`. Si no, las bases que ya existen se rompen.
- Todo el texto que ve una persona va en español rioplatense con voseo ("Ingresá tu teléfono").
- Si un cambio obliga al otro a hacer algo (instalar dependencias, reiniciar el servidor, poner una clave), avisalo.

## Estado

- La cuenta emisora de Google Wallet está en modo de prueba: las tarjetas muestran "[TEST ONLY]" y solo las pueden guardar las cuentas de prueba.
- La política de privacidad es un borrador con datos pendientes y sin revisión legal.
- Todavía no está publicado. Para publicarlo (se habló de Render con Postgres) faltan Alembic para las migraciones, las credenciales de Google por variable de entorno y un límite de intentos en el login, el alta y el registro.
