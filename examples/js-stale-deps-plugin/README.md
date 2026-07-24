# auditkit-js-example

Plugin de ejemplo para [auditkit](../../README.md): puerto a
JavaScript/TypeScript del check `stale_deps` incorporado. Sirve como
plantilla real y funcional para escribir un plugin propio — no como
código decorativo.

Detecta:
- Dependencias declaradas en `package.json` que ningún fichero
  `.js`/`.jsx`/`.ts`/`.tsx` del repo importa (`require(...)`,
  `import ... from ...`, `import(...)`).
- Imports de paquetes que sí se usan en el código pero no están
  declarados en `package.json`.

## Instalación

```bash
pip install auditkit auditkit-js-example
auditkit list-checks   # ya sale "js_stale_deps"
auditkit analyze . --only js_stale_deps
```

## Lo único que hace falta para que `auditkit` lo descubra

Una entrada de entry point en el `pyproject.toml` de este paquete:

```toml
[project.entry-points."auditkit.checks"]
js_stale_deps = "auditkit_js_example.check:JsStaleDepsCheck"
```

Nada más. `auditkit` nunca importa este paquete directamente — lo
encuentra en tiempo de ejecución vía
[entry points](https://packaging.python.org/en/latest/specifications/entry-points/)
igual que a cualquiera de sus checks incorporados.

## Desarrollo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"   # instala tambien auditkit desde PyPI
pytest
ruff check .
```
