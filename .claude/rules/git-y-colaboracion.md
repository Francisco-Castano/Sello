# Git y colaboración

- Se trabaja directo sobre `main` de `Francisco-Castano/Sello`, compartido por dos personas (Felipe en macOS y Francisco en Windows). Commitear y pushear solo cuando el usuario lo pide, y antes de pushear hacer `git fetch` para ver si el otro subió algo.
- Agregar archivos por nombre (`git add archivo1 archivo2`). Nunca `git add -A` ni `git add .`: `google_credentials.json`, `sello.db` y `.secret_key` viven en la carpeta del proyecto.
- Mensajes de commit en español: un título corto en primera persona ("Agrego…", "Saco…", "Borro…") y, si el cambio es grande, una lista de viñetas con lo que cambió.
- No reescribir historial ni hacer `push --force` sin acuerdo explícito: obliga al otro a resincronizar su copia y puede borrarle trabajo.
- Si un cambio obliga al otro desarrollador a hacer algo (instalar dependencias, reiniciar el servidor, poner una clave), decirlo al terminar.
