---
paths:
  - "static/**"
---

# Páginas (HTML y JavaScript)

- HTML, CSS y JavaScript sin frameworks ni paso de build. No sumar React, Tailwind, bundlers ni librerías nuevas sin consultarlo.
- Datos que vienen del usuario o de la API (nombres, premios, mensajes) se insertan con `textContent` o `innerText`. `innerHTML` solo para vaciar un contenedor (`= ""`).
- Leer las respuestas con tolerancia a errores: si el servidor no devuelve JSON (un 500), igual tiene que mostrarse un mensaje legible. Usar el patrón `leerRespuesta` o `try { await res.json() } catch {}`, y mostrar `detail` solo si es un string.
- En la caja (`pos.html`), un 401 significa sesión vencida: llamar a `mostrarLogin(...)`. `localStorage` siempre dentro de `try/catch` (con las funciones `leer`, `guardar` y `borrar`).
- Todo tiene que funcionar en un celular de 375 px de ancho sin scroll horizontal: la caja y el registro se usan desde teléfonos.
- `card-editor.js` se comparte entre `alta.html` (tema claro) y `pos.html` (tema oscuro). Sus colores salen de las variables `--ed-*` que define cada página; no fijar colores ahí adentro.
- Las páginas se sirven con `no-cache`, así que no hace falta versionar los archivos. Una ruta HTML nueva se registra en `main.py` con `html_page(...)`.
