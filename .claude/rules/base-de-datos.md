---
paths:
  - "models.py"
  - "database.py"
---

# Base de datos

- No hay migraciones. Al agregar una columna a una tabla que ya existe, sumarla también a `ADDED_COLUMNS` en `database.py`, con una definición SQL que sirva para bases viejas: nullable o con `DEFAULT`. Si no, las bases de los desarrolladores (y la de producción) fallan al arrancar. Las tablas nuevas no necesitan nada: `create_all` las crea.
- Toda columna nueva con valor por defecto lleva `default=` (Python) y `server_default=` (SQL), para que las filas viejas queden con un valor válido.
- No renombrar ni borrar columnas o tablas: `setup_database()` solo sabe agregar. Si hace falta, avisar al usuario, porque requiere un plan de migración.
- No borrar registros que forman parte del historial (premios, pases, movimientos): desactivarlos. Por ejemplo, `Reward.active = False` y filtrar con `business.active_rewards`.
- Usar tipos portables entre SQLite y Postgres (el plan es pasar a Postgres): nada de SQL específico de SQLite en el código de la app.
- `setup_database()` tiene que seguir tolerando varios procesos arrancando a la vez (los dos servidores con `--reload` ya chocaron una vez).
