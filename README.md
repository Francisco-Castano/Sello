# Sello
Plataforma de desarrollo de pases para google pay y apple wallet.

## Pruebas automáticas

Las pruebas usan una base de datos en memoria y un Google Wallet simulado: no tocan `sello.db`, no necesitan `google_credentials.json` y no se conectan a internet.

Instalar las herramientas de desarrollo (una sola vez):

```bash
pip install -r requirements-dev.txt
```

Correr todas las pruebas (conviene hacerlo antes de cada commit):

```bash
python -m pytest
```

Están en la carpeta `tests/`, una por área: caja, registro de clientes, comercios, tarjetas, base de datos y utilidades.
