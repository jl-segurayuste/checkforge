# checkforge-js-example

Plugin de ejemplo para [checkforge](../../README.md): puerto a
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

Ninguno de los dos está en PyPI todavía, así que se instalan desde GitHub:

```bash
pip install git+https://github.com/jl-segurayuste/checkforge.git
pip install "git+https://github.com/jl-segurayuste/checkforge.git#subdirectory=examples/js-stale-deps-plugin"
checkforge list-checks   # ya sale "js_stale_deps"
checkforge analyze . --only js_stale_deps
```

## Lo único que hace falta para que `checkforge` lo descubra

Una entrada de entry point en el `pyproject.toml` de este paquete:

```toml
[project.entry-points."checkforge.checks"]
js_stale_deps = "checkforge_js_example.check:JsStaleDepsCheck"
```

Nada más. `checkforge` nunca importa este paquete directamente — lo
encuentra en tiempo de ejecución vía
[entry points](https://packaging.python.org/en/latest/specifications/entry-points/)
igual que a cualquiera de sus checks incorporados.

## Desarrollo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"   # instala tambien checkforge desde PyPI
pytest
ruff check .
```
