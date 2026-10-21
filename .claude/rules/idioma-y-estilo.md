# Idioma y estilo

- Todo lo que ve una persona va en español rioplatense con voseo: textos de las páginas, mensajes de error de la API (`detail`), salidas de `admin.py`. Ej: "Ingresá tu teléfono", no "Ingrese su teléfono".
- Los comentarios y docstrings también van en español. Los nombres de variables, funciones y columnas en Python siguen en inglés (`points_mode`, `get_current_business`); en el JavaScript de las páginas se usan nombres en español (`mostrarPase`, `canjearPremio`). Respetar el idioma del archivo que se edita.
- Los mensajes de error de la API se muestran tal cual al usuario final: que sean claros, sin jerga técnica, y que digan qué hacer ("Ingresá un teléfono válido, con código de área").
- Los nombres de personas se formatean con `names.format_person_name` y los teléfonos se normalizan con `normalize_phone` (solo dígitos). No guardar ni comparar esos datos crudos.
- Los montos en pesos se muestran con separador de miles argentino (`toLocaleString("es-AR")` → `$5.500`).
