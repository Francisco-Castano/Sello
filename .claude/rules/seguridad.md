---
paths:
  - "routers/**"
  - "auth.py"
  - "admin.py"
---

# Seguridad y permisos

- Todo endpoint que use la caja depende de `get_current_business` y filtra los datos por `business.id`. Un recurso de otro comercio responde 404, nunca 403: no hay que revelar que existe.
- Los únicos endpoints públicos son las páginas, `/public/businesses/*`, `/passes/crear-google`, `/auth/login` y `/media/*`. Cualquier endpoint público nuevo es una decisión a consultar con el usuario.
- El login responde el mismo mensaje si el comercio no existe, no tiene clave o la clave es incorrecta. El estado del comercio (pendiente o suspendido) solo se informa después de validar la clave.
- Las validaciones van en el servidor aunque la página también las haga; el JavaScript de las páginas se puede saltear.
- Las claves se guardan con `auth.hash_password` (scrypt) y se comparan con `hmac.compare_digest`. Nunca guardarlas, devolverlas ni imprimirlas en texto plano.
- Un cliente se identifica por teléfono, y entregar su tarjeta a otro nombre permite robarle los puntos. No relajar la comparación de nombre del registro sin consultarlo.
- Los consentimientos (privacidad y promociones) se guardan por pase, con fecha y `PRIVACY_VERSION`.
