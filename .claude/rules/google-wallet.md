---
paths:
  - "GoogleWallet.py"
  - "branding.py"
  - "program.py"
  - "routers/passes.py"
  - "routers/branding.py"
  - "routers/program.py"
---

# Google Wallet

- `build_visual_fields()` es la única fuente de lo que se ve en la tarjeta. Cualquier dato nuevo en la tarjeta se agrega ahí, para que salga igual al crearla y al actualizarla.
- Las tarjetas ya entregadas no se actualizan solas. Si un cambio afecta lo que muestran (marca del comercio, premios, formato), después de guardar hay que llamar a `sync_business_passes` en segundo plano (`BackgroundTasks`), como hacen `routers/branding.py` y `routers/program.py`.
- Las imágenes solo se mandan a Google como URL `https` pública (`SELLO_PUBLIC_URL`). En localhost se omiten; no mandar URLs de localhost ni data URLs.
- `CLASS_TEMPLATE_INFO` y `admin.py plantilla-wallet` modifican la clase compartida por todos los comercios en la cuenta emisora real. No correr nada que llame a la API real de Google (plantilla, sincronizaciones, scripts sueltos) sin confirmación explícita del usuario.
- Leer `google_credentials.json` solo desde `GoogleWallet.py`. Nunca mostrar su contenido, ni siquiera parcialmente, salvo `client_email` o los primeros caracteres de `private_key_id` para identificar la clave.
