# Nexaris — instrucciones para Claude

Antes de hacer nada, leé **`PROMPT_PROYECTO.md`**: tiene quién es John, cómo funciona el sistema, dónde corre, el estado actual, el plan y las reglas. Mantenelo actualizado cuando cambie algo importante.

- Respondé en español simple (Uruguay), de a un paso, sin prometer ganancias.
- El código vivo está en `fabrica/`. Tests: `cd fabrica && python -m pytest -q` (tienen que pasar todos antes de subir).
- Flujo de cambios: commit en la rama de trabajo → pull request → merge a `main`; después John aplica con el comando de `fabrica/actualizar.sh` (está en el prompt).
- Nunca escribas tokens, claves ni contraseñas en el repositorio (es público).
- No bajes la exigencia de los exámenes ni saques protecciones; no subas la plata ni el riesgo sin que John lo decida.
