# Contribuir

Gracias por el interés. Dos formas de contribuir, según el tamaño del cambio:

## Un check nuevo (lo más habitual)

Un check nuevo **no necesita tocar este repositorio**. Publica tu propio
paquete con una entrada en el grupo de entry points `repo_health.checks`
— ver [`examples/js-stale-deps-plugin`](examples/js-stale-deps-plugin)
como plantilla completa y funcional, y la sección "Arquitectura" del
[README](README.md#arquitectura-cada-check-es-un-plugin).

Si aun así crees que un check merece vivir en este repo (por ejemplo,
soporte a un lenguaje muy usado que hoy falta en `dead_files`/
`stale_deps`), abre primero un issue para hablarlo antes del PR.

## Un cambio al núcleo (`repo_health/plugin.py`, `runner.py`, `report.py`, `cli.py`)

Estas piezas son el contrato que usa cualquier plugin — un cambio aquí
puede romper checks de terceros que no vemos. Abre un issue explicando el
problema antes de mandar el PR.

## Antes de mandar un PR

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```

- Cualquier check nuevo o corregido necesita sus propios tests — no hay
  excepción, ni siquiera para heurísticas "obviamente correctas". La
  mayoría de los checks incorporados ya tuvieron al menos un fallo real
  encontrado por su propia batería de tests durante el desarrollo.
- Si el check puede dar falsos positivos (casi todos los heurísticos
  pueden), dilo explícitamente en el `detail` del `Finding`, no lo dejes
  implícito.
- `ruff check .` sin avisos. No hay configuración de formateador todavía
  — mantén el estilo del código de alrededor.

## Reportar un bug o proponer una idea

Un issue normal. Si es un falso positivo de algún check, el mínimo para
poder reproducirlo: el fragmento de código concreto que lo dispara (no
hace falta el repo entero).
