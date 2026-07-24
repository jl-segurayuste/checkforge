# checkforge

Un único comando que agrega varias auditorías de un repositorio —
dependencias, secretos, código muerto, historial de git — en un solo
informe, en vez de tener que ejecutar y leer media docena de herramientas
sueltas por separado.

```
$ checkforge analyze .

checkforge — /ruta/al/repo

── secrets ──────────────────────────────
  53 fichero(s) analizados, 2 hallazgo(s).
  [HIGH  ] Posible secreto: AWS Access Key ID (config/settings.py:14)
           Revisar y revocar si es real antes de publicar.

── stale_deps ───────────────────────────
  12 dependencia(s) declarada(s), 1 hallazgo(s).
  [LOW   ] Dependencia declarada pero no importada en ningún fichero: requests
           Heurística -- puede usarse indirectamente (plugin, entry point, CLI de terceros).

Total: 3 hallazgo(s) — 1 high, 2 low
```

## Por qué existe

Hoy existen muchas herramientas excelentes que resuelven un problema cada
una — un detector de secretos, un linter de dependencias, un analizador de
churn de git — pero ninguna las normaliza en un único informe accionable.
`checkforge` no compite con ellas: es un agregador. El núcleo no sabe
nada de ningún lenguaje ni de ningún tipo de análisis concreto; cada check
es un plugin independiente.

## Instalación

Todavía no está publicado en PyPI, así que se instala directamente desde GitHub:

```bash
pip install git+https://github.com/jl-segurayuste/checkforge.git
```

## Uso

```bash
checkforge analyze .                    # informe en consola
checkforge analyze . --json             # informe en JSON
checkforge analyze . --only secrets     # solo un check
checkforge analyze . --skip git_hotspots
checkforge analyze . --fail-on high     # código de salida 1 si hay algo "high" (para CI)
checkforge list-checks                  # que checks estan instalados
```

## Checks incluidos (v0.1)

| Check | Qué mira |
|---|---|
| `secrets` | Claves privadas, tokens de proveedores conocidos, asignaciones con aspecto de secreto, IPs privadas |
| `dead_files` | Ficheros Python que ningún otro fichero del repo importa |
| `git_hotspots` | Ficheros que cambian con mucha frecuencia, ramas obsoletas, ficheros enormes |
| `stale_deps` | Dependencias Python declaradas sin usar, o usadas sin declarar |
| `readme_drift` | Versión de Python y comandos de CLI del README frente a `pyproject.toml` |

Todo es análisis estático: nada de esto ejecuta el código del repo que se
analiza. `dead_files` y `stale_deps` son heurísticas y hoy solo entienden
Python — lo dicen explícitamente en cada hallazgo, porque un falso
positivo silencioso es peor que no tener el check.

## Arquitectura: cada check es un plugin

El núcleo (`checkforge.runner`) descubre los checks instalados vía
[entry points](https://packaging.python.org/en/latest/specifications/entry-points/)
del grupo `checkforge.checks` — exactamente igual para los cuatro checks
que trae este paquete que para uno que instale un tercero. No hace falta
tocar este repositorio para añadir un check nuevo.

Un check es cualquier clase con este contrato:

```python
from pathlib import Path
from checkforge.plugin import CheckResult, Finding

class MiCheck:
    name = "mi_check"
    description = "Qué hace, en una frase."

    def run(self, repo_path: Path) -> CheckResult:
        findings = [
            Finding(severity="medium", title="...", detail="...", path="...", line=1),
        ]
        return CheckResult(check_name=self.name, summary="...", findings=findings)
```

Y en el `pyproject.toml` de tu propio paquete:

```toml
[project.entry-points."checkforge.checks"]
mi_check = "mi_paquete.checks:MiCheck"
```

Con tu paquete instalado, `checkforge list-checks` ya lo verá. Ejemplo
real y funcional, no solo el fragmento de arriba:
[`examples/js-stale-deps-plugin`](examples/js-stale-deps-plugin) — puerto
a JavaScript/TypeScript del check `stale_deps`, con sus propios tests.

Otras ideas obvias para un plugin de terceros: soporte a más lenguajes en
`dead_files`/`stale_deps` (Go/Rust/Java), comprobación de versiones
desactualizadas contra el índice real de paquetes (`stale_deps` de este
repo es deliberadamente offline), un check de cobertura de tests.

## Desarrollo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
```

Ver [CONTRIBUTING.md](CONTRIBUTING.md) antes de mandar un check nuevo o
un cambio al núcleo.

## Licencia

MIT.
