---
description: Revisión de bugs de un módulo contra datos reales y el Excel de origen; cada bug confirmado va a issue
argument-hint: "[logistica|comercial|conduces|estimaciones|todos] (vacío: los módulos que toca la rama)"
---

Revisión de bugs. Existe porque el 2026-10-23 la primera revisión de Logística y
Comercial encontró **17 bugs acumulados** (#164–#180): las revisiones se dejaron
de hacer el 06/10 y nada obligaba a retomarlas. Uno era grave y llevaba días a
la vista: el vs ppto de Comercial comparaba Ene–Jun real contra real, porque el
plan guardado no era lo que se creía. **Los tests verdes no lo vieron: solo
atrapan lo que alguien pensó en probar.**

Se corre **antes de abrir cada PR** que toque un módulo y cada vez que el
usuario lo pida. Desde `brain` las rutas relativas no resuelven: el repo es
`C:\Users\axelo\VMO\conduces`.

Módulos: `$ARGUMENTS`. Si viene vacío, son los que toca la rama
(`git diff --name-only main...HEAD`; en `main` sin cambios, preguntá cuál con
AskUserQuestion). Qué archivos son de cada módulo:

- **logistica**: `static/logistica*`, `routes_logistica.py`, la sección
  Logística de `core.py` (desde `LOG_DB_PATH`, incluye los PDF),
  `tests/logistica/*.test.js` salvo `comercial.test.js`, `tests/test_logistica_*`.
- **comercial**: `static/comercial*`, `routes_comercial.py`, la sección
  Comercial de `core.py` (desde `COM_DB_PATH`), `tests/test_comercial.py`,
  `tests/logistica/comercial.test.js`.
- **conduces** / **estimaciones**: `routes_conduces.py` / `routes_estimaciones.py`
  y lo que esas rutas usan de `core.py`; sus tests en `tests/`.

## 1. Copias, nunca las bases de verdad

```bash
cd /c/Users/axelo/VMO/conduces && python scripts/revisar_copias.py "<scratchpad>/revision-<fecha>" <modulos>
```

Toda la revisión trabaja sobre esas copias. Los scripts de prueba van en esa
misma carpeta, nunca en el repo. Los Excel de origen que lista el script se
**leen**, nunca se modifican: si hace falta abrirlos con openpyxl, primero se
copian a la carpeta de la revisión.

## 2. Tests

`python -m pytest -q` y `node --test tests/logistica/*.test.js`. Si algo falla,
eso va primero en el informe.

## 3. Un agente por módulo, en paralelo

Agente `general-purpose` en background, uno por módulo, con este encargo
(completá el módulo, sus archivos, la ruta de la copia y la carpeta de scripts):

> Bug hunt del módulo X. Buscá bugs REALES que los tests no atrapan: números o
> porcentajes mal, filas perdidas o contadas dos veces, datos que se pierden al
> guardar o al subir sin aviso, la pantalla y el PDF o el Excel exportado
> diciendo cosas distintas, validaciones que dejan pasar datos malos, bordes de
> fecha y hora, celular contra computadora. No estilo ni refactors.
> **Compará contra el Excel de origen:** leé sus fórmulas y tablas dinámicas y
> verificá que la app calcula lo mismo y que cada dato guardado significa lo
> que el código cree que significa. Por ejemplo: ¿el "plan" es presupuesto o es
> real?
> Reglas duras: no edites el repo, no hagas git que cambie estado, no abras
> issues ni PRs. No abras las bases del repo, solo la copia. No toques
> servidores en :8000. No imprimas secretos.
> Antes de abrir uno nuevo, mirá los issues abiertos (`gh issue list --repo
> lach06/VMO`) para no repetir un bug ya anotado.
> **Cada hallazgo se demuestra** con un script que da la salida incorrecta con
> datos concretos, o con las filas reales que lo disparan. Lo que no se puede
> demostrar va marcado PLAUSIBLE, con el porqué.
> Devolvé, en español y del más grave al menos grave: título, archivo:línea,
> qué pasa (entrada → resultado incorrecto contra el correcto), evidencia (ruta
> del script y salida), si toca un número que se ve HOY con los datos reales, y
> el arreglo en una o dos líneas. Al final, qué revisaste y quedó limpio.

## 4. Verificá vos antes de creerle

Corré los scripts de evidencia de cada hallazgo que toque números de hoy y mirá
el código en la línea que citan. Lo que no se reproduce no va. Un agente
también se equivoca.

## 5. Informe al usuario

Corto, sin tablas, en dos grupos:
- **Tocan números de hoy:** caso real, número que se ve contra el correcto.
- **Hoy no afectan:** una línea cada uno.

Si no hubo hallazgos, decilo igual, con lo que se revisó. Después preguntá con
AskUserQuestion qué se hace: solo issues, issues y arreglar los de hoy, o
arreglar todos. Cada bug confirmado va a un issue en `lach06/VMO`, con
evidencia y arreglo sugerido, aunque se arregle en el momento. Los arreglos
siguen el camino de siempre: rama, mostrarle el resultado antes de subir y PR
recién con el "súbelo".

## Qué no es

No reemplaza los tests ni el "enseñame antes de subirlo". Es la parte que los
tests no cubren: alguien que sale a buscar el bug a propósito.
