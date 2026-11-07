# CLAUDE.md — Sistema de Validación de Conduces

> Este archivo se revisa al inicio de cada sesión y se actualiza conforme avanzamos.
> Contiene TODO el contexto del proyecto. No tomar decisiones sin consultarlo.

---

## Reglas de trabajo
- Toda comunicación en **español**
- **Pedir confirmación antes de cualquier cambio** (archivos, BD, scripts, frontend, etc.)
- No hacer commits automáticos salvo que se pida explícitamente
- No modificar la plantilla de reportes sin confirmación del usuario
- Código y nombres técnicos pueden quedar en inglés
- **Actualizar este archivo INMEDIATAMENTE después de cada acción, decisión o cambio — sin excepción**
- **Abrir y cerrar cada sesión con el protocolo de acá abajo.** No es opcional y no lleva un minuto
- **Antes de empezar cualquier feature/tarea nueva no trivial: sugerir proactivamente pasar primero por `/office-hours` o `/spec` (armar el plan) y luego `/plan-eng-review` o `/autoplan` (revisarlo con Codex+Claude) antes de construir — el usuario lo pidió como recordatorio fijo porque se le puede olvidar**

---

## Protocolo de apertura y cierre

Establecido el 2026-09-04. **Cada regla de acá salió de algo que fallo de verdad**,
no de teoría: si alguna parece burocrática, mirá el motivo que tiene al lado.

**En Claude Code se ejecuta con `/apertura`, `/revisar` y `/cierre`** (viven en
`.claude/commands/`, y son lo único de `.claude/` que se versiona). Lo de abajo es lo
que esos comandos hacen: si se corren, no hace falta seguirlo a mano.

### Al abrir — tres cosas, unos 8 minutos

**El número está medido, no estimado**: `estado.py` tarda 5 segundos y las trampas del
`HANDOFF` son ~1.500 palabras, o sea unos 7 minutos y medio de lectura. Decía "un
minuto" hasta que se cronometró. Importa: un protocolo que promete un minuto y pide
ocho se saltea en el paso 2, que es el caro.

1. **`python scripts/estado.py`** — punta de `main`, último cambio de comportamiento,
   filas de las dos bases, libro mayor, último período cerrado, issues abiertos y
   cuántos tests hay. Calculado en el momento.
2. **Las trampas de `HANDOFF.md`** — lo que cuesta caro si lo descubrís tarde. Está
   ordenado por cuánto cuesta.
3. **Nada más.** `AGENDA.md` es historial cerrado y **no se abre**: hasta el 2026-09-04
   arrancaba diciendo 483 tests cuando eran 626, `main` en un hash de tres días antes,
   y cuatro issues como pendientes que estaban cerrados.

> **Un `Pendiente:` al final de una entrada del log es un dato fechado, no un estado.**
> Dice lo que se pensó ese día. El 2026-09-04 se dio por abierto un pendiente del
> 2026-08-24 que se había resuelto ese mismo día, y terminó escrito como trampa en el
> `HANDOFF`. Antes de copiar una afirmación vieja a un documento vivo, **abrí el
> código**. Este log es historia; el backlog son los issues.

### Antes de cada PR — `/revisar` el módulo que toca

Agregado 2026-10-23. La primera revisión de Logística y Comercial encontró **17 bugs
acumulados** (#164–#180), con todos los tests en verde. Las revisiones de bugs se
habían dejado de hacer el 06/10 al cambiar de módulo, y nada obligaba a retomarlas.
El más caro: el vs ppto de Comercial comparaba Ene–Jun real contra real, porque el
plan guardado no era presupuesto. Solo se vio leyendo las fórmulas del Excel.

`/revisar` saca copias de las bases (`scripts/revisar_copias.py`, nunca las de
verdad), corre los tests, manda un agente por módulo a buscar bugs contra los datos
reales y el Excel de origen, verifica cada hallazgo y abre un issue por cada uno
confirmado. Si no encuentra nada, lo dice igual.

### Al cerrar — un comando

```bash
python scripts/cierre.py
```

Comprueba las seis cosas y dice cuáles faltan: (1) `main` mergeada, limpia,
sincronizada y sin ramas, worktrees ni PRs colgando; (2) al menos una entrada de hoy
en `log.md`; (3) qué quedó en `dropoff/`; (4) los servidores de desarrollo que siguen
corriendo; (5) el respaldo; (6) el estado final.

**Solo dos cosas las hace solo**, y son las que no tienen criterio: el respaldo y
cerrar los servidores. No commitea, no mergea, no escribe en el log, no borra ramas y
**no borra nada del `dropoff`**. Decir qué falta es su trabajo; hacerlo es del que
cierra.

**El `dropoff` se reporta y nunca se borra** (agregado 2026-09-30). Ahí conviven
archivos ya procesados con copias únicas, y no se distinguen mirando el nombre: hoy
mismo tiene `OneDrive_1_9-8-2026.zip`, 889 MB sin respaldo en ningún lado, que el log
del 2026-09-28 decidió conservar a propósito. El script los separa en *conservar* —los
que el `HANDOFF` o el log declaran intocables, con el motivo al lado— y *revisar*, y
ahí se queda. Borrar es una decisión y se consulta, como commitear o mergear.

**Los servidores sí se cierran solos** (agregado 2026-09-30). Un `uvicorn` que
sobrevive a la sesión no le sirve a nadie y levantarlo de nuevo es un comando. Cuando
se agregó el paso había uno corriendo **desde hacía 21 horas**, de la sesión anterior,
que nadie sabía que estaba. Solo se cierra lo que se prueba que es este proyecto:
además de buscar procesos de python con `uvicorn`, se le pide `/openapi.json` a su
puerto y se comprueba que exponga rutas nuestras — la línea de comando
`python -m uvicorn main:app` es idéntica en cualquier otro proyecto FastAPI de la
misma máquina. La huella usa **prefijos viejos y estables**: la primera versión usaba
`/api/logistica/dias` y dejaba vivo justo al servidor de ayer, que era este mismo
proyecto de antes de que Logística tuviera rutas.

**Una entrada de `log.md` por decisión, no por sesión.** El 2026-09-04 fueron diez y
estuvo bien: fueron diez decisiones. Lo que no sirve es una entrada que resuma el día.

Es un comando porque **un cierre caro no se hace**: el ritual anterior pedía tocar
cinco `.md` y el 2026-09-03 se salteó justo el que después mintió.

### Cinco reglas que salieron de errores reales

| Regla | De dónde salió |
|---|---|
| **Nunca commitear a `main` directo** — rama y PR | Se hizo una vez el 2026-09-04 y hubo que revertirlo |
| **Un test de regresión no cuenta hasta comprobar que falla sin el fix** | Dos tests verdes que no probaban nada, uno comparando `mtime` que `copy2` preserva |
| **Un dato derivable no se escribe en un `.md`** | El bloque de estado con diez números tipeados, falsos a los tres días |
| **Lo que tiene que sobrevivir la sesión no va en `dropoff/` ni en el scratchpad** | El correo a X vivió en un temporal que se limpia; `dropoff/` está en `.gitignore` y fuera del backup |
| **Un archivo que entra por `dropoff/` se copia a su módulo antes de usarlo** | Los dos Excel del 29-09 se copiaron a `logistica/archivos/`, que sí entra al respaldo; el `dropoff` no |
| **Cuando entra un lote de escaneos, la carpeta fuente no se borra** | El 2026-08-24 se borró `Puente 2.zip` y 743 conduces quedaron sin imagen |
| **Antes de construir sobre un dato, compararlo con el Excel de origen** | El vs ppto acumulado se armó el 2026-10-22 sobre un plan que en Ene–Jun era el real (#180) |

---

## Contexto del negocio
- **Empresa:** VMO (empresa de concreto/hormigón)
- **Operación:** Transportistas/suplidores entregan agregados (arena, gravilla, piedra, etc.)
- **Conduce:** Comprobante físico de entrega de un transportista — es la unidad central del sistema
- **Problema original:** El sistema interno de la compañía genera un número aleatorio por conduce que **no sirve de nada**. Se está esperando que utilicen el ID real del conduce. Este es un punto crítico.
- **Plazo de pago:** 30 días para pagar cada conduce
- **Suplidores:** Cada suplidor entrega sus conduces en formatos diferentes (esto se resolverá en el futuro)

### Aviso diario de conduces pendientes

```bash
python scripts/avisar_pendientes.py --dry-run   # lo imprime, no manda ni guarda estado
python scripts/avisar_pendientes.py             # manda
```

Manda por correo los conduces en `pendientes_revision`. Va una vez al dia por el
Programador de Tareas, igual que el respaldo.

**El asunto lleva la senal, no solo el numero** — `39 conduces pendientes por revisar
— sin cambios` contra `41 conduces pendientes por revisar — 2 nuevos`. Al 2026-09-04
los 39 pendientes son todos `falta sello`, todos de MACAO 2, y no se mueven desde el
2026-08-20: un correo diario identico se filtra en una semana, y el dia que entre uno
nuevo ya nadie lo abre. Cada envio compara contra el anterior, cuyo estado vive en
`estimaciones/data/pendientes_ultimo_envio.json` (**no versionado**, como todo
`estimaciones/data/`).

**Si el envio falla, el estado NO se guarda.** Guardarlo haria que el aviso de manana
dijera "sin cambios" contra un correo que nunca llego, y un pendiente nuevo quedaria
invisible para siempre. Tiene test propio.

Sin configurar, **no manda y explica que falta**, pero imprime igual el listado. Las
claves van en el `.env`:

| Clave | Para que |
|---|---|
| `SMTP_HOST` | servidor (ej. `smtp.gmail.com`) |
| `SMTP_PORT` | 587 STARTTLS o 465 SSL. Default 587 |
| `SMTP_USER` / `SMTP_PASS` | usuario y clave — en Gmail, una **contrasena de aplicacion**, no la del correo |
| `MAIL_REMITENTE` | de quien sale. Default: `SMTP_USER` |
| `MAIL_DESTINATARIOS` | a quienes va, separados por coma |

---

## Reglas de negocio críticas
1. El **ID real del conduce** (impreso en el documento físico) es la llave primaria — NUNCA el número aleatorio del sistema interno
2. Estados posibles: **pagado** / **no_pagado** — solo estos dos, sin estados intermedios
3. La fecha de pago no es importante para el negocio (confirmado por el jefe)
4. Nunca se va a consultar un conduce que no esté en la BD — está garantizado
5. Los conduces se ingresan a la BD semanal o mensualmente
6. El plazo para pagar es de 30 días desde que entra el conduce
7. Los IDs de conduces pueden tener formato libre (ej. `163419/5647` para conduces con referencia doble agregado/transporte) — validación mínima de 4 caracteres. El formato `/` se decidirá definitivamente el lunes con el jefe.
8. **NUNCA intercambiar valores entre campos** — cada campo tiene su valor exacto y no se puede mover a otro campo bajo ninguna circunstancia. Mezclar campos daña toda la integridad de los datos. Esto aplica a `precio`, `cantidad`, `fecha`, `producto`, `compania`, `id_conduce`, y cualquier campo presente o futuro.

---

## Estructura de datos — tabla `conduces`

```sql
CREATE TABLE conduces (
    id_conduce    TEXT PRIMARY KEY,
    fecha         DATE,
    producto      TEXT,
    compania      TEXT,
    precio        REAL,
    cantidad      REAL,
    almacen       TEXT,
    estado        TEXT DEFAULT 'no_pagado',
    id_transporte TEXT,
    fecha_pago    DATETIME
);
```

| Campo | Descripción |
|---|---|
| `id_conduce` | ID real del documento físico — llave primaria |
| `fecha` | Fecha del conduce |
| `producto` | Tipo de agregado (arena, gravilla, piedra, etc.) |
| `compania` | Nombre del transportista/suplidor |
| `precio` | Precio unitario |
| `cantidad` | Cantidad entregada |
| `almacen` | Almacén/obra de destino (ej. Bavaro, SanIsidro, Metaldom) |
| `estado` | `pagado` o `no_pagado` |
| `id_transporte` | ID del conduce de transporte — solo presente en IDs con formato `conduce/transporte` |
| `fecha_pago` | Fecha/hora real en que se marcó como pagado (agregada 2026-08-21) — se agrega sola vía migración idempotente en `pagar.py` (`PRAGMA table_info` + `ALTER TABLE` si falta), no requiere paso manual. Nunca se sobreescribe si el conduce ya estaba pagado. |

---

## Flujo completo del sistema

1. Transportistas entregan conduces físicos
2. Usuario los agrega a un CSV con columnas: `id_conduce, fecha, producto, compania, precio, cantidad`
3. Corre `python importar.py archivo.csv` → entran a la BD (duplicados se ignoran automáticamente)
4. Cuando van a hacer pagos → usuario abre el chat → pregunta por los IDs → Claude valida estado
5. Se pagan los conduces pendientes
6. Corre `python pagar.py C-001 C-002 ...` → se marcan como pagados en la BD
7. En cualquier momento se puede pedir un reporte general

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Base de datos | SQLite (`conduces.db`) |
| Backend / API | Python + FastAPI |
| IA | Anthropic Claude `claude-opus-4-6` con tool use |
| Frontend | HTML/CSS/JS puro |
| Variables de entorno | python-dotenv (`.env`) |
| Modelo Claude | `claude-opus-4-6` — NO cambiar sin confirmación |

---

## Estructura de carpetas y archivos del proyecto

> **Reorganizada el 2026-09-01.** La raiz es **VMO**; adentro van `dropoff/` y todo lo
> que los dos modulos usan en conjunto, y despues **una carpeta por modulo** con los
> datos que le corresponden. El **codigo quedo compartido en la raiz** a proposito:
> `core.py` lo usan los dos modulos, y los ~22 scripts calculan su `BASE_DIR` como
> `parent.parent` de su propio archivo, asi que moverlos adentro de un modulo les
> romperia las rutas **en silencio**, sin lanzar ningun error.

```
VMO/                           <- raiz del repo (carpeta fisica: C:\Users\axelo\VMO\conduces)
|
|   --- compartido entre los dos modulos ---
+-- dropoff/                   <- Carpeta de intercambio bidireccional de archivos
+-- backups/                   <- Respaldos con timestamp de ambas BD y de la memoria del proyecto (`backups/db/`), mas copias de archivos antes de cambios grandes
+-- documentos/                <- Documentos formales (requerimientos, especificaciones, etc.)
+-- docs/                      <- Notas de diseno tecnico (`docs/designs/`)
+-- presentacion/              <- Material para la presentacion del sistema a la jefa - agregada 2026-08-24
+-- misc/                      <- Lo que no encaja en ninguna otra carpeta (screenshots de QA, ZIPs ya usados) - agregada 2026-08-24
|
|   --- codigo (compartido: `core.py` lo usan los dos modulos) ---
+-- main.py                    <- Punto de entrada de uvicorn (raiz, requerido) - solo crea `app` e incluye los 2 routers, sin logica propia (Fase 2, issue #4)
+-- core.py                    <- Config, auth, estado global y toda la logica de negocio (generar_reporte, setup_est_db, etc.) - compartido por ambos routers. **Todas las rutas de datos son constantes en las lineas 52-64 y 114-115** - si hay que mover una carpeta, se cambian ahi
+-- routes_conduces.py         <- Las 9 rutas HTTP de Conduces (incluye /login, /logout)
+-- routes_estimaciones.py     <- Las 10 rutas HTTP de Estimaciones
+-- conduces/archivos/         <- **Fuente de los escaneos** que se anexan al PDF de la estimacion.
|                                Cada `.zip` que aparezca aca entra solo al indice. Precedencia de las
|                                TRES fuentes (issue #81): zip -> `estimaciones/facturas/procesadas/`
|                                -> `.pdf` suelto en `archivos/escaneos/`, que le gana a los dos.
|                                **Esta en .gitignore**
+-- scripts/                   <- Scripts de terminal - de los dos modulos, no se parten
|   +-- setup_db.py            <- Crea la BD - correr solo una vez
|   +-- importar.py            <- Importa CSV a la BD, ignora duplicados
|   +-- pagar.py               <- Marca conduces como pagados
|   +-- consultar.py           <- Consulta estado desde terminal
|   +-- extraer_pdf.py         <- Extrae conduces de PDF escaneado via Claude Vision
|   +-- estado.py             <- El estado del proyecto, calculado. AL ABRIR
|   +-- cierre.py             <- Comprueba main, log y respaldo. AL CERRAR
|   +-- avisar_pendientes.py  <- Manda por correo los conduces pendientes por revisar,
|                                una vez al dia por el Programador de Tareas
+-- tests/                     <- Suite de pytest (cuantos son: python scripts/estado.py). **No tocan ninguna carpeta de datos** (arman los Excel en memoria), asi que estar en verde NO prueba que las rutas esten bien: eso se verifica levantando el servidor
+-- static/
|   +-- index.html             <- Frontend web: dashboard con panel de reportes + chat
|   +-- logo.png               <- Logo VMO
+-- requirements.txt           <- Dependencias con version exacta (Fase 2, issue #5)
+-- CLAUDE.md                  <- Este archivo - contexto completo del proyecto
+-- .env                       <- API key de Anthropic - NUNCA compartir ni commitear
|
|   --- modulo Conduces ---
+-- conduces/
|   +-- db/conduces.db         <- Base de datos SQLite
|   +-- data/                  <- CSV/Excel de importacion, progreso de Vision, auditorias de sello
|   +-- archivos/              <- PDFs, ZIP y Excel fuente de conduces
|   +-- reportes/              <- Backups de reportes HTML generados
|   +-- facturas/              <- Facturas generadas
|   +-- fallos/                <- Excel de conduces con problemas (antes `conduces(fallo)/`)
|
|   --- modulo Estimaciones ---
+-- estimaciones/
|   +-- db/estimaciones.db
|   +-- data/                  <- CSVs, Excel de validacion, Excel main, plantillas por fase
|   +-- archivos/              <- PDFs de referencia y auditorias de estimaciones
|   +-- facturas/              <- `pendientes/`, `pendientes_revision/`, `procesadas/`
|   +-- reportes/              <- estimaciones generadas (documento final)
|
|   --- modulo Logistica (3 rutas de historial, el calculo NO - ver su seccion) ---
+-- logistica/
    +-- archivos/              <- Excels fuente del dia (programacion y tiempo de cargue)
    +-- db/logistica.db        <- historial de dias: los crudos y los supuestos, NO el resultado
    +-- reportes/              <- Excel consolidado exportado desde el dashboard
```

### Reglas de organización
- **Primero preguntarse de qué módulo es la cosa.** Si es de un módulo va adentro de `conduces/`, `estimaciones/` o `logistica/`; si la usan varios, va en la raíz
- Nuevos scripts van en `scripts/` (en la raíz — **no** dentro de un módulo, ver la nota del árbol)
- Nuevos archivos de datos (CSV, Excel) van en `conduces/data/` o `estimaciones/data/`
- Nuevos PDFs e imágenes van en `conduces/archivos/` o `estimaciones/archivos/`
- Documentos formales (requerimientos, especificaciones, acuerdos) van en `documentos/`
- Material para la presentación del sistema a la jefa (diagramas, notas, borradores) va en `presentacion/`
- Lo que no encaja en ninguna categoría anterior (screenshots de prueba, fixtures de QA ya usados) va en `misc/`
### Reglas de `dropoff/` — carpeta de intercambio
- **Usuario → Claude:** el usuario suelta archivos ahí (CSV, Excel, PDF, etc.) → Claude los recoge, procesa y organiza en la carpeta correcta (`conduces/data/`, `estimaciones/archivos/`, etc.)
- **Claude → Usuario:** cuando Claude genera algo para entregar (CSV, reportes, archivos procesados, etc.) lo deja en `dropoff/` para que el usuario lo recoja
- Después de procesar cualquier archivo entrante, Claude lo mueve a su carpeta correspondiente y deja `dropoff/` limpio
- Si se necesitan nuevas carpetas, crearlas siguiendo este criterio y actualizar este archivo
- `main.py` se queda en la raíz — uvicorn lo requiere ahí

---

## Cómo correr el servidor

```bash
cd C:\Users\axelo\VMO\conduces
python -m uvicorn main:app
```

> **No usar `--reload`.** En Windows no es confiable (StatReload falla cuando cambian
> varios archivos a la vez) y ya causó una investigación de un bug inexistente el
> 2026-08-26. Reiniciar el servidor a mano después de cualquier cambio de backend.

## Cómo correr los scripts

```bash
cd C:\Users\axelo\VMO\conduces
python scripts/importar.py conduces/data/archivo.csv
python scripts/pagar.py C-001 C-002
python scripts/extraer_pdf.py conduces/archivos/archivo.pdf
```

Abrir en browser: `http://127.0.0.1:8000`

---

## Respaldos

```bash
python scripts/backup_db.py
```

Corre **antes de cualquier operacion que escriba en una base**, y ademas solo una
vez al dia por el Programador de Tareas de Windows. Respalda tres cosas a
`backups/db/` con timestamp, y las copia a Google Drive si `GDRIVE_BACKUP_DIR`
esta en el `.env` (si no lo esta, avisa y sigue — no falla):

- `conduces.db` y `estimaciones.db`, con la API de backup de sqlite3, que es
  segura sobre una base en uso — no es una copia de archivo
- **La carpeta de memoria del proyecto**, como `memoria_<timestamp>.zip`
  (agregado 2026-09-01). Vive en `~/.claude/projects/<slug>/memory`, o sea
  **fuera del repo**, y no la versiona git: ahi estan `log.md`, `MEMORY.md` y
  los archivos de feedback/proyecto/referencia — todo el historial de
  decisiones. Antes de esto no tenia ningun respaldo, y el vault de Obsidian
  **no cuenta como copia**: es una ventana a los mismos archivos fisicos

La carpeta de memoria se ubica sola por la convencion de rutas de Claude Code,
con un fallback por nombre de carpeta. Si alguna vez no la encuentra, se le
puede pasar la ruta con la variable de entorno `MEMORIA_DIR`.

Retencion: 30 dias, aplicada por separado a los `.db` y a los `.zip`.

---

## Testing

```bash
cd C:\Users\axelo\VMO\conduces
python -m pytest tests/ -v
```

La cantidad de tests la dice `python scripts/estado.py`; no se escribe aca. El generador de Estimaciones (`tests/test_plantillas_estimacion.py`,
`tests/test_calculo_estimacion.py`, `tests/test_rgo_capacidad_dinamica.py`) fue la
primera suite del proyecto, agregada 2026-08-20 — las pruebas de cálculo real usan
LibreOffice (`soffice --headless`) y se saltan solas si no está instalado.
`tests/test_estimaciones_validacion.py` cubre validaciones y el pipeline de facturas
(fase no reconocida, doble-chequeo de sello/firma, `_confirmar_registros`).
`tests/test_conduces.py` (nuevo 2026-08-21, primera cobertura de este módulo)
cubre importación CSV/XLS, pagos, y el cálculo de montos en reportes.
`tests/test_firma_rgo.py` (nuevo 2026-08-31, issue #33) abre el `.xlsx` generado
de cada una de las 9 fases y verifica el bloque de firma de la hoja RGO —
nombre y cargo del analista y de gerencia de obra — tanto tal cual queda
guardado como recalculado con LibreOffice (esta última se salta si no está
instalado). `tests/test_claves_resueltas.py` (nuevo 2026-08-31, issue #25)
cubre el detector de resoluciones manuales desactualizadas: los tres desenlaces
(discrepa / sin auto-match / coincide), la clave que ya no existe en el catálogo,
el escopeo por fase de los alias, la colisión de catálogo y la garantía de
solo-lectura. `tests/test_nombre_hoja.py` y `tests/test_rco_rfo.py` (nuevos
2026-09-01, issue #27) cubren el nombrado de hojas parametrizado
(`_est_nombre_hoja`, las 3 familias) y las hojas RCO/RFO completas: títulos A5
byte-exactos (las letras vienen espaciadas una por una — un test con el string
plano falla siempre), firmas por fase, croquis presente/ausente/ilegible con PNG
sintético, logos por empresa, geometría, orden de hojas, y las regresiones de
print_area y de totales-idénticos-sin-RCO/RFO. Un test compara contra un
documento real del cliente y se salta si las fuentes (768 MB, no versionadas) no
están: correr con `EST_FUENTES_DIR` apuntando a `plantillas_por_fase/` para
ejercerlo. `tests/test_reo_columna_clave.py` (nuevo 2026-09-01) custodia que la columna A
de REO-01 lleve la CLAVE y que la FILA la siga dando el `orden` — las dos
mitades, porque "corregir" tambien el calculo de la fila intercambiaria
renglones enteros. `tests/test_rutas_conduces.py` (nuevo 2026-09-02, issue #31) es el
primero que pega **por HTTP** con `TestClient` en vez de llamar a `core` directo: cubre
que `sin_precio` sobreviva la ruta y los tres valores posibles del campo, incluido el
`None` explícito cuando la respuesta salió del cache.
`tests/test_precios_desactualizados.py` (nuevo 2026-09-02, issue #39) cubre el re-precio
de las facturas que cargaron un precio de una hoja de la lista que ya no existe: 19 tests
sobre bases temporales, verificados mutando el script en cinco formas distintas. Los
tests del importador (`tests/test_importar_puente.py`, issue #48) suman uno que recorre
el **AST** y falla si alguna llamada a `insert_factura` o `guardar_pendiente_revision`
vuelve a recibir un dict literal vacío como `vision_data`.
El total lo dice `python scripts/estado.py`. Para saber si estan en verde hay que correr la suite: contar no es correr.

**Ojo con las plantillas de estimación:** el bloque de firma de la hoja
`CD-COAF-RGO-PLANTILLA` viene cableado a la fila 37/38 de `CD-COAF-REO-01`,
que solo es la fila correcta en 2 de las 9 fases. Desde el issue #33
`_est_escribir_firma_rgo()` lo reescribe como valor al generar, detectando la
fila real por el rótulo `CONTRATISTA` de la columna B de REO-01. Si se
reconstruye una plantilla hay que conservar ese rótulo, o la generación corta
con `bloque_de_firma_no_encontrado` en vez de entregar un documento sin firma.

Y desde el issue #27: **ninguna hoja PLANTILLA puede traer imágenes** —
`wb.copy_worksheet()` pierde las imágenes, el `print_area` y el footer **en
silencio** (openpyxl 3.1.5, verificado empíricamente). El generador re-fija la
config de impresión y re-estampa croquis/logos en cada hoja después de copiar,
y corta con `plantilla_con_imagenes` si una PLANTILLA las trae. Los croquis
viven en `estimaciones/data/croquis/` (versionados, con manifiesto; se
regeneran con `scripts/sembrar_croquis.py`, comprimidos porque openpyxl no
deduplica imágenes dentro del `.xlsx`). Otra trampa medida ahí mismo: un
`colOff`/`rowOff` de ancla más grande que su celda se RECORTA al renderizar en
LibreOffice — los marcadores de ancla van normalizados (`_est_marcador_ancla`).

---

## Herramientas de Claude (tool use — funciones en `core.py`, ruta `/chat` en `routes_conduces.py`)

### `consultar_conduces`
- **Input:** lista de IDs de conduces
- **Acción:** consulta la BD SQLite y devuelve estado de cada uno
- **Respuesta:** indica claramente cuáles están PAGADOS y cuáles PENDIENTES

### `generar_reporte`
- **Input:** ninguno
- **Acción:** consulta toda la BD, genera HTML con reporte general
- **Output:** archivo guardado en `conduces/reportes/reporte_YYYYMMDD_HHMMSS.html`
- El frontend muestra botón naranja de descarga automáticamente

### `generar_reporte_compania`
- **Input:** `compania` (nombre exacto)
- **Acción:** consulta la BD filtrado por compañía, genera HTML con reporte de esa compañía
- **Output:** archivo guardado en `conduces/reportes/reporte_{compania}_{timestamp}.html`
- Mismo diseño que el reporte general pero con nombre de compañía en el encabezado y sin tabla de resumen por compañía

---

## Frontend (`static/index.html`)

Layout de **sidebar de navegación + panel de contenido**:

**Sidebar izquierdo — Menú de navegación:**
- Opción "Validar Conduces" (activa por defecto)
- Opción "Generar Reporte"
- El contenido de la derecha cambia según la opción seleccionada

**Panel: Validar Conduces:**
- Chat con Claude
- Indicador "En línea" en el header del panel
- Cuando Claude consulta conduces, el resultado se muestra como **tabla limpia** (no texto)
- Tabla: ID Conduce | Fecha | Compañía | Estado (badge) — fondo gris oscuro
- Botón "Exportar" CSV en la tabla (abajo a la derecha)
- El historial del chat NO persiste entre sesiones — empieza vacío siempre
- Enter envía el mensaje (Shift+Enter hace salto de línea)
- Claude NO usa emojis ni markdown — instrucción en SYSTEM_PROMPT
- Respuesta de Claude devuelve `consulta_data` (JSON) para renderizar tabla en frontend
- Endpoint `/chat` devuelve `JSONResponse` con charset UTF-8 para evitar errores de encoding en Windows

**Panel: Generar Reporte:**
- Dropdown de compañías (cargado dinámicamente desde `/companias`) + opción Reporte General
- Date picker Desde / Hasta
- Botón "Generar Reporte" (rojo)
- Botón "Descargar Reporte" (verde) aparece tras generación
- Endpoints directos: `POST /api/generar-reporte` y `POST /api/generar-reporte-compania` (bypasan Claude)

**Login:**
- Pantalla de login antes del dashboard
- Credenciales en `.env` (`LOGIN_USER`, `LOGIN_PASS`)
- Token UUID almacenado en `localStorage` — validado en cada request
- Botón "Salir" en el header con icono SVG
- Al cerrar sesión se borra el token y el historial

**Diseño visual (actualizado 2026-08-18):**
- Tema oscuro unificado — header, sidebar y paneles todos oscuros (sin gris)
- Paleta CSS variables en `:root` — `--bg-base`, `--bg-surface`, `--bg-elevated`, `--bg-hover`
- Fondos: `#0D1829` base, `#152535` surface, `#1C3045` elevated, `#243850` hover
- Fuentes: Inter (UI) + Fira Code (IDs/datos monospace) vía Google Fonts
- Iconos SVG inline en sidebar — sin emojis
- Logo con `background:white; padding:4px` para visibilidad en fondo oscuro
- Textura de cuadrícula sutil en fondo (radial-gradient doble)
- Empty state en chat con chips de acceso rápido
- Spinner CSS `::after` en botones con clase `.is-loading` — posicionado con `top: calc(50% - 6.5px)` para evitar salto vertical durante animación. **Colgaba de `.btn-primary:disabled` hasta el 2026-08-31**, así que un botón deshabilitado por validación de formulario (el modal de aprobar del issue #20, y Generar Estimación con facturas sin asignar) mostraba un spinner eterno que parecía "procesando". Ahora el spinner es opt-in: `is-loading` se pone y se saca en las mismas líneas donde ya se toca `disabled`. Al agregar un botón primario que se deshabilita **mientras trabaja**, ponerle la clase; si se deshabilita por validación, no.
- Animación `panelIn` al cambiar de panel
- Backups automáticos en `backups/` antes de cambios grandes
- Calendario (date picker) rango: `in-range` rgba(.22), `hover-range` rgba(.18) — menos transparente

---

## Plantilla de reportes — APROBADA, NO MODIFICAR

Definida en función `generar_reporte()` en `main.py`.

**Estructura:**
1. **Encabezado** — "VMO" (pequeño) + "Reporte de Conduces" (grande) + fecha/hora a la derecha
2. **4 tarjetas de resumen:**
   - Total Conduces (naranja `#D32F2F`)
   - Pagados (verde `#2d6a4f`)
   - Pendientes (rojo `#c1121f`)
   - Monto Pendiente (rojo `#c1121f`)
3. **Tabla por compañía:** Compañía | Total | Pagados | Pendientes | Monto Pendiente
4. **Tabla detalle:** ID Conduce | Fecha | Producto | Compañía | Cantidad | Precio | Estado (badge)
5. **Footer** con fecha de generación

**Colores:**
- Fondo: `#f5f5f5`
- Primario: `#1A3A5C`
- Acento naranja: `#D32F2F`
- Verde (pagado): `#2d6a4f`, fondo badge: `#d8f3dc`
- Rojo (pendiente): `#c1121f`, fondo badge: `#ffe5d0`

**Archivos:** `conduces/reportes/reporte_YYYYMMDD_HHMMSS.html`

---

## Módulo de Logística — Dashboard de cumplimiento de despacho

Agregado el 2026-09-29. Es distinto a los otros dos módulos: **no tiene backend,
router ni base de datos** — es un dashboard 100% cliente (`static/logistica.html`,
hecho por la compañera de trabajo del usuario, revisado y corregido ese mismo día)
que cruza dos Excel del día (la programación de despacho contra el cargue real) y
calcula el cumplimiento de hora de llegada por cliente/obra, con supuestos
editables de trayecto por planta. Cubre **todo el despacho de VMO Concretos**
(Santo Domingo y Punta Cana), no solo Moon Palace.

- Se sirve por el static mount de `main.py` (`/logistica.html`) y está embebido
  como tercer módulo del portal (`static/index.html`) en un iframe con carga
  diferida. No hubo que tocar `main.py` ni agregar router.
- **Tiene base desde el 2026-09-30, y guarda lo que NO es derivable.** En
  `logistica/db/logistica.db` van las filas crudas de los dos Excel, los
  supuestos **de ese día** (cargue, calidad, tolerancia, y trayecto + zona de
  cada planta), los trayectos corregidos a mano y las observaciones. **No se
  guarda el resultado**: ni el estado de cada pedido, ni la diferencia, ni el
  porcentaje. Eso se recalcula al abrir el día, con la misma función que
  calcula el día de hoy.
- Esa decisión es la que define el módulo, y tiene dos consecuencias que
  conviene no deshacer. Que los supuestos viajen **con** el día hace que
  reabrir un día viejo muestre lo que mostró, en vez de recalcularlo con los
  supuestos de hoy. Y que el resultado no se guarde evita reimplementar el
  cruce en Python: **el cálculo sigue existiendo una sola vez**, en
  `static/logistica.logic.js`. Si alguna vez aparece un porcentaje en una
  respuesta de `/api/logistica/`, es que esa regla se rompió.
- Tres rutas, en `routes_logistica.py`, todas con el token del portal:
  `POST /api/logistica/dias` guarda, `GET /api/logistica/dias` lista y
  `GET /api/logistica/dias/{fecha}` devuelve el día entero. El iframe saca el
  token de `localStorage` (`vmo_token`) porque es **el mismo origen** que el
  portal.
- **Se navega desde el sidebar del portal, como Estimaciones** (2026-09-30).
  Tres secciones —Cumplimiento del día, Historial y Estadísticas— con un
  `.content-panel` cada una, y adentro de cada panel un iframe a su página de
  `static/`. `mostrarPanelLog()` en `index.html` es el hermano de
  `mostrarPanelEst()`. **Los paneles no pueden llevar `display` en el style
  inline**: le ganaría al `display:none` de `.content-panel` y se verían los
  tres juntos.
- Cada iframe carga su `src` recién la primera vez que se entra a su sección
  (`data-src` + `cargarIframeLog()`). El del día baja `xlsx` de un CDN y los
  otros dos piden el historial: no hay por qué pagar las tres al abrir el
  módulo. Hay un test que falla si alguien pone un `src` fijo.
- **Abrir un día desde el Historial** cruza dos iframes hermanos, que no se
  hablan entre sí: la página del historial le manda un `postMessage` al portal
  (`logistica:abrir-dia`), y el portal navega el iframe del día a
  `/logistica.html#dia=AAAA-MM-DD`. Por el hash y no con un `postMessage` al
  otro iframe, porque así funciona igual si ese iframe todavía no se cargó. El
  dashboard del día además escucha `hashchange`, para el caso de pedir dos
  veces el mismo día (el `src` no cambia y no recargaría).
- **Tres páginas.** `static/logistica.html` es el trabajo del día (subir los dos
  Excel, ajustar, revisar, guardar), `static/logistica-historial.html` lista los
  días guardados y `static/logistica-estadisticas.html` es el análisis del
  histórico. Comparten `logistica.logic.js` —cálculo puro, probado con node— y
  `logistica.api.js` —el token, el fetch con token y el aviso al portal, o sea
  lo que sí toca el navegador—. **Tres copias de la misma función de fetch se
  separan sin que nadie lo note**, así que hay un test que falla si una página
  redefine `apiLogistica`. Comparten `logistica.logic.js`,
  así que **el cumplimiento se calcula en un solo lugar**: la página de
  estadísticas pide los días crudos y los recalcula con la misma función, no
  lee porcentajes guardados (no existen). Cuesta un pedido por día; con un mes
  son ~30 y no se nota. Si algún día molesta, la salida es un endpoint que
  devuelva el rango junto — **no** calcular el porcentaje en Python.
- **Un pedido es una HORA PROGRAMADA de una obra**, no la obra entera
  (2026-09-30, sobre datos reales). Antes una obra era una fila juzgada por el
  primer camión del día: PARMOL tenía 10 renglones de 09:00 a 20:00 y 70
  camiones en una sola fila, y el primer camión fue uno de **2 m³ a las 00:10**,
  que la hacía "Cumplido" entera. Ahora son cinco filas, una por hora.
- Los camiones se reparten entre las horas **en orden cronológico**, y la cuota
  de cada hora es su columna **`Despachado`**, que el archivo trae. Si esa
  columna falta se usa la cantidad programada. La última hora se queda con lo
  que sobre, para que ningún camión se pierda.
- **El porcentaje pesa por m³, no por pedido.** Cada hora se juzga por su
  primer camión —si la colada arrancó a tiempo— y después pesa por los m³ que
  movió. Las tres variantes medidas sobre el 29-09 real: **9%** pesando por
  cargue, 23% contando pedidos, y **5%** juzgando cada camión contra la hora de
  su pedido — esta última no sirve, porque una colada continua manda camiones
  durante diez horas contra un solo horario y el camión 50 sale tarde por
  definición.
- **La unidad de volumen pasó de cargues a m³ el 2026-10-02**, a pedido de la
  compañera, y el argumento es correcto: contar cargues asume que todos mueven
  el mismo volumen. Medido sobre los tres días guardados, los 435 cargues
  evaluables van de **1 a 16 m³** (mediana 7, promedio 7,89; el 9% por debajo
  de 5). Los m³ reales ya estaban en cada fila (`cantReal`), así que la
  suposición era evitable sin pedir ningún dato nuevo. **Cuánto movió, medido
  antes de hacerlo: poco** — el acumulado pasó de 19% a 17% y por planta la
  diferencia va de 0 a 3 puntos, siempre hacia abajo. Es una corrección de
  rigor, no un número distinto: la unidad que sí cambia el resultado sigue
  siendo la de entregas, que se separa hasta 25 puntos. **Reemplazó** a la
  unidad por cargue en vez de sumarse, porque las dos decían lo mismo con 2
  puntos de diferencia.
- **`camiones` y `camionesCumplidos` siguen existiendo pero son cargues, o sea
  viajes** — un camión que hace tres viajes cuenta tres veces; el 29-09 tuvo
  178 cargues de 63 camiones. Se muestran como cuenta ("Cargues evaluados") y
  **ningún porcentaje sale de ellos**. El nombre del campo quedó por
  compatibilidad; la etiqueta de la pantalla no.
- **La tolerancia tiene techo Y PISO desde el 2026-10-02.** Antes la condición
  era solo `diferencia ≤ tolerancia`, así que **llegar antes nunca incumplía,
  por lejos que fuera**: sobre los tres primeros días había un pedido de las
  09:00 servido por un camión que cargó a las **00:10** saliendo en verde con
  −8h 10min. Y es el mismo camión de las 00:10 que motivó partir los pedidos
  por hora el 30-09 — aquel cambio le sacó el poder de aprobar la obra entera,
  pero seguía aprobando su propia hora. Lo encontró la compañera mirando la
  columna Diferencia.
- **El piso es un supuesto aparte (`toleranciaAdelanto`), no la tolerancia en
  espejo**, porque el negocio no es simétrico: 45 minutos tarde es una cuadrilla
  parada, 45 antes es un camión esperando. Default **60 min**, editable en la
  pantalla. Medido sobre los tres días antes de elegirlo, el acumulado por m³
  da 17% sin piso, 12% con 30, **14% con 60** y 16% con 120; con 60 se dan
  vuelta exactamente los cuatro adelantos absurdos (−8h10, −3h12, −1h27, −1h26)
  y no los de media hora, que son discutibles. Un **0** configurado es legítimo
  ("cualquier adelanto incumple") y por eso el fallback es `??` y nunca `||`.
- **Los días guardados antes del 2026-10-02 tienen `tolerancia_adelanto_min` en
  NULL** y caen al default al reabrirlos — no se quedan sin piso, que sería
  conservar el defecto. Es el mismo criterio que cuando cambió el modelo de
  cumplimiento el 30-09: una corrección del cálculo arregla el historial hacia
  atrás. La columna entró por migración idempotente (`PRAGMA table_info`), igual
  que `despachado`/`pendiente`.
- **Lo no despachado sale de la columna `Pendiente`**, que es un dato exacto del
  archivo, y va **aparte** de los cruces que fallaron: una entrega que no salió
  y un cruce que no se pudo hacer son dos problemas distintos. De rebote arregla
  un falso positivo: un renglón programado en 0 m³ tiene pendiente 0 y deja de
  figurar como incumplido.
- **OAT** = *of all time*: el cumplimiento de una planta sobre **todo** el
  historial guardado, al lado del mismo número para el día. Si alguna vez se
  agrega un filtro de fechas a esa página, el OAT tiene que seguir recibiendo
  el historial entero o deja de ser lo que su nombre dice (hay un test).
- El acumulado **pondera por pedidos, no promedia los porcentajes diarios**: un
  día de 2 pedidos no puede pesar lo mismo que uno de 80.
- **Guardar es explícito**, con el botón "Guardar día": lo aprieta una persona
  cuando ya ajustó trayectos, revisó los cruces marcados y escribió las
  observaciones. Guardar solo al subir los archivos dejaría en el historial el
  primer borrador.
- **Re-guardar un día avisa antes de pisarlo** (409 + `confirmar_aviso`), con
  qué hay guardado y de cuándo. Es el mismo patrón del aviso de re-cierre de
  Estimaciones, y existe por la misma razón: guardar es DELETE + INSERT.
- `logistica.db` está en `backup_db.py` desde el primer día. Importa más que
  las otras dos: **los Excel de origen no quedan en ningún lado** —el dashboard
  los lee en el navegador y no los sube— así que si se pierde esta base, ese
  día no se reconstruye de nada.
- `logistica/archivos/` guarda los Excel fuente del día y `logistica/reportes/`
  los consolidados exportados. Los dos quedan fuera de git por los patrones
  `archivos/` y `reportes/` del `.gitignore` — un clone limpio no los trae.
- **La lógica que no toca el DOM vive en `static/logistica.logic.js`** desde el
  2026-09-30, y se prueba: normalización, horas y fechas de Excel, detección de
  encabezados, el cruce programación-vs-cargue y el resumen por cliente. El
  mismo archivo lo carga el navegador con un `<script src>` y lo importa node
  con `require()`. Las pruebas son `tests/logistica/*.test.js` con el runner que
  trae node —sin `package.json` ni dependencias— y corren **dentro de la suite
  de siempre**: `tests/test_logistica_js.py` las lanza, así que
  `python -m pytest tests/ -q` sigue siendo la única puerta. Si no hay node
  instalado se saltean diciendo por qué.
- Los parsers están partidos en dos a propósito: `parse*Sheets(hojas)` es la
  heurística —lo frágil, y lo que se prueba— y en el HTML quedó un envoltorio de
  tres líneas que usa XLSX para pasar cada hoja a filas. Los tests no necesitan
  la librería del CDN.
- Pendientes conocidos de la revisión del 2026-09-29 (los 4 bugs de lógica ya se
  corrigieron): la librería `xlsx` viene de un CDN (sin internet no lee archivos),
  los nombres de cliente/obra se inyectan al HTML sin escapar, y falta
  persistencia de observaciones/overrides.
- **Arreglado el 2026-09-30**: `Reiniciar` no limpiaba `state.observaciones`,
  así que al cargar otro día una fila del mismo cliente y obra heredaba el
  comentario del anterior. Con el historial eso pasaba de molesto a grave —las
  observaciones de un día guardado se filtrarían al siguiente y se guardarían
  como suyas— así que se corrigió junto con la base.

## Módulo de Estimaciones — Contexto y decisiones

### ¿Qué es una estimación?
- Documento formal (como una factura pero no es factura) que se envía al proyecto Moon Palace (CONFOTUR)
- Desglosa el hormigón entregado — montos grandes, requiere precisión total
- Se genera mensualmente
- Hay dos tipos: **Estimación VMO** (hormigonera) y **Estimación DOMICEM** (cementera, dueña de VMO)
- Cada tipo cubre fases distintas del proyecto — lista completa definida abajo

### Proyecto Moon Palace
- Proyecto CONFOTUR (incentivo de impuestos para turismo en RD)
- Tiene múltiples **fases** (ej. "CIMENTACIONES MACAO II") — lista **cerrada/fija**
- El campo `obra` en el PDF **no** identifica la fase por sí solo: la fase se deriva del `Cliente:`
  con `_normalizar_fase()`. La línea `OBRA:` del papel es un dato aparte y vive en `obra_papel`
- Cada fase pertenece exclusivamente a una empresa — nunca se comparte
- La fase determina automáticamente a cuál estimación pertenece la entrega

**Fases DOMICEM:**
- CAVERNAS
- MACAO 2
- PATIO DE MANIOBRAS-TRB
- VIVIENDAS

**Fases VMO:**
- CANCHAS
- CEDIS
- EXTERIORES
- PATIO DE MANIOBRAS-TRA
- PODIUM-1-2-3
- CAMPO DE GOLF (mapeada en `FASES_VMO`/`_normalizar_fase()` el 2026-08-21 — ya se habían detectado facturas de esta fase antes, pero nunca se había agregado al código, así que caían mal clasificadas como VMO por el fallback en vez de reconocerse explícitamente)
- PUENTES DE MANGLAR (idem)
- BALLROOM (idem)

### Flujo de procesamiento de facturas
1. PDFs escaneados (una factura por archivo) llegan en un ZIP
2. Usuario suelta el ZIP en el panel "Procesar Facturas" → drag & drop
3. Backend extrae cada PDF, parsea nombre de archivo, llama a Claude Vision (**Haiku** primero — más barato)
4. Claude Vision: extrae campos + valida sello (cualquier sello) + firma
5. Se muestra resumen con 4 categorías: OK (listas), errores de lectura (Vision/JSON falló — reprocesable), pendientes por revisión (sin sello/firma — nunca reprocesable), duplicadas
6. Usuario descarga Excel de validación para revisar
7. Usuario aprieta **"Incorporar válidos y reprocesar errores con Opus"** — en un solo paso: (a) los válidos entran a `estimaciones.db` + `estimaciones_main.xlsx` + PDFs a `procesadas/`, (b) los errores de lectura se reintentan con **Opus** (modelo más capaz). Si tras reprocesar siguen quedando errores, el mismo botón reaparece para repetir la ronda
8. Los que faltan sello/firma van directo a la tabla `pendientes_revision` (PDF + datos) — nunca se tocan automáticamente. Si alguien resube el mismo documento (mismo `id_documento`) ya corregido, el sistema lo saca de pendientes solo, sin acción manual

### Validaciones por PDF
- Nombre de archivo válido: `MM-DD-M#-XXXXX.pdf`
- Sello presente (cualquier sello — no importa el texto)
- Firma presente
- Si falla el nombre o la lectura de Vision → "error de lectura", reprocesable con Opus
- Si falta sello/firma → va a "pendientes por revisión", nunca se reprocesa ni se importa hasta corregirse

### Naming del archivo PDF
Formato: `MM-DD-M#-XXXXX.pdf`
- `MM` = mes, `DD` = día, `M#` = planta (ej. M3), `XXXXX` = ID del conduce del camión
- Año se asume como el año en curso
- ID del documento se reconstruye: planta + ID zero-padded a 8 dígitos (ej. M3 + 00048807 = M300048807)

### Campos extraídos de cada PDF
| Campo | Descripción |
|---|---|
| `id_documento` | Del nombre del archivo (ej. M300048807) |
| `fecha` | Del nombre del archivo |
| `planta` | Del nombre del archivo (ej. M3) |
| `orden_compra` | O/C del PDF |
| `referencia` | Del PDF |
| `distancia` | Del PDF |
| `cliente` | Del PDF |
| `obra` | **Dos semánticas según el camino** (no unificadas): por `scripts/importar_puente.py` vale la **fase**; por el camino individual de `core.py`, lo que devuelva Vision (de ahí `MALESPIN MACAO II`, `PARMOL`) |
| `obra_papel` | La línea `OBRA:` impresa en el papel — `DIMECA`, `CONCAVA`, `LIDOMI` (issue #67, 2026-09-07). Dato distinto de `obra` y de `cliente`; las filas anteriores al issue están en NULL hasta correr `scripts/backfill_obra_papel.py` |
| `bomba` | Del PDF |
| `id_producto` | Del PDF |
| `descripcion` | Descripción del hormigón |
| `cantidad` | m³ entregados |
| `precio_unitario` | De tabla de precios (pendiente) |
| `total` | cantidad × precio_unitario (calculado) |
| `ficha` | Del PDF |
| `chofer` | Del PDF |
| `hora_salida` | Del PDF |
| `observaciones` | Del PDF |

### Tabla de precios
- Lista fija, no dinámica — el usuario la provee (`estimaciones/data/Lista de precios.xlsx`)
- Dos tablas: `precios_domicem` (codigo, fase, descripcion, precio_unitario) y `precios_vmo` (mismo esquema, agregado 2026-08-19 — antes no tenía `fase`)
- El sistema hace match automático por `descripcion` (TRIM, exacta) + `fase` — **no** por `id_producto`/código (Vision no lo extrae de forma confiable, sobre todo en VMO)
- Si `fase` no tiene precio específico en `precios_vmo`, usa el genérico (`fase IS NULL`, aplica a cualquier fase) — `precios_domicem` no tiene fallback genérico, siempre requiere fase exacta
- Si un producto no tiene precio → queda `NULL`, se puede correr `scripts/backfill_precios.py` cuando se agregue el precio faltante
- Estado actual: VMO 100% de facturas con precio, DOMICEM 97.3% (quedan 3 productos con revenimiento "8"+/-1"" sin precio)

### Excel main
- `estimaciones/data/estimaciones_main.xlsx` — base de datos maestra en Excel
- Se actualiza automáticamente al confirmar cada importación
- Columnas `precio_unitario` y `total` quedan vacías hasta que se configure la tabla de precios

### Estructura de carpetas — estimaciones
```
estimaciones/
+-- facturas/
|   +-- pendientes/          <- PDFs entran aqui
|   +-- pendientes_revision/ <- sin sello o firma, nunca se tocan automaticamente
|   +-- procesadas/          <- PDFs ya importados se mueven aqui
+-- data/                    <- CSVs, Excel de validacion, Excel main, plantillas por fase
|   +-- croquis/             <- croquis de las hojas RCO + logos DOMICEM (issue #27) - VERSIONADOS, con manifiesto.txt; sembrados por scripts/sembrar_croquis.py
+-- archivos/                <- PDFs de referencia y auditorias (agregada 2026-09-01)
+-- reportes/                <- estimaciones generadas (documento final)
+-- db/                      <- estimaciones.db
```

### BD: tabla `facturas` en `estimaciones.db`
```sql
CREATE TABLE facturas (
    id_documento      TEXT PRIMARY KEY,
    fecha             DATE,
    planta            TEXT,
    orden_compra      TEXT,
    referencia        TEXT,
    distancia         TEXT,
    cliente           TEXT,
    obra              TEXT,
    obra_papel        TEXT,   -- issue #67: la linea OBRA: del papel
    bomba             TEXT,
    id_producto       TEXT,
    descripcion       TEXT,
    cantidad          REAL,
    precio_unitario   REAL,
    total             REAL,
    ficha             TEXT,
    chofer            TEXT,
    hora_salida       TEXT,
    observaciones     TEXT,
    archivo_pdf       TEXT,
    fecha_importacion DATETIME
);
```

### BD: tabla `catalogo_estimacion` en `estimaciones.db` (agregada 2026-08-19)
```sql
CREATE TABLE catalogo_estimacion (
    empresa         TEXT,
    fase            TEXT,
    orden           INTEGER,
    clave           TEXT,
    descripcion     TEXT,
    precio_unitario REAL,
    PRIMARY KEY (empresa, fase, orden)
);
```
Catálogo real de productos que va en el documento formal de estimación (hoja
`REO-01`), extraído directamente de los 9 Excel reales de las 9 fases — **no
es lo mismo** que `precios_vmo`/`precios_domicem` (esas siguen siendo solo
para ponerle precio a facturas individuales). 71 productos en total. Fuente:
`estimaciones/data/plantillas_por_fase/{DOMICEM,VMO}/*.xlsx`.

### Frontend — módulo Estimaciones
- Toggle en el header: `[ Conduces | Estimaciones ]` — rojo VMO cuando activo
- Sidebar: "Procesar Facturas", "Generar Estimación", "Pendientes por Revisión", "Resoluciones Manuales"
- Panel Procesar Facturas: drop zone de ZIP → procesa con Haiku → resumen con 4 categorías (OK / errores de lectura / pendientes sin sello-firma / duplicados) → botón único "Incorporar válidos y reprocesar errores con Opus" (repetible si quedan errores) + Excel + Cancelar
- Panel Pendientes por Revisión: tabla de facturas sin sello/firma, solo lectura — se resuelven solas cuando alguien resube el mismo documento corregido
- Panel Resoluciones Manuales (issue #25, 2026-08-31): aviso pasivo, 100% solo lectura. Compara cada `facturas.clave_resuelta` guardada contra lo que el catálogo y los alias vigentes de su `(empresa, fase)` dirían hoy, y separa el resultado en tres tablas — **discrepan** (caja de borde rojo: las dos claves con su P.U., los m³ y la diferencia en dinero), **sin auto-match** y **coinciden**. No corrige nada ni frena la generación. Backend: `core._est_revisar_claves_resueltas()` + `GET /api/estimaciones/claves-resueltas` (único endpoint del proyecto que abre la BD con `mode=ro` y no llama a `setup_est_db()`, a propósito). Al 2026-08-31, contra la BD real: 265 resoluciones, 0 discrepancias, 1 sin auto-match, 264 redundantes.
- Panel Generar Estimación: pendiente de diseñar

### El conduce trae impreso el código de producto (2026-09-02)

El papel del conduce tiene una columna `PRODUCTO` propia, a la izquierda de la
descripción, con el **código del producto**. Los PDFs escaneados están en
`conduces/archivos/Puente 1.zip` (3.491 archivos, nombrados `MM-DD-Mx-NNNNN.pdf`).

Cruzando ese código contra `estimaciones/data/Lista de precios.xlsx` se resuelve a
qué producto y a qué precio corresponde un conduce **sin depender de que el texto de
la descripción matchee**. Eso destrabó los issues #23 y #26, que llevaban semanas
esperando a X porque agregar un alias es decidir a qué renglón va la plata y no
había documento del cliente de junio 2026 contra el cual verificar.

El caso que lo demuestra: `M800013172` dice `rev. 8"` en la descripción y trae el
código `44510`, que es el producto de `rev. 7"`. **El texto libre estaba mal tipeado
y el código estaba bien.** Con matching por texto eso es indistinguible de un
producto nuevo.

Para leer uno: extraer el PDF del zip y renderizarlo con PyMuPDF (`fitz`) a PNG —
son escaneos sin capa de texto, hay que mirarlos. Algunos vienen rotados 180°.

**Ojo con `facturas.id_producto`.** Guarda ese código cuando Vision lo lee, pero
está poblado en 3.284 de 4.185 y **cero en las 582 de VMO**, y Vision lo corrompe
seguido (`441B`, `3410`, `1418` son corrupciones de `4418`). Por eso el matcher lo
ignora a propósito (`core.py:1350-1352`). El issue #40 propone cruzarlo con la
descripción para que se confirmen entre sí, en vez de confiarle solo.

---

## Estructura del documento de estimación — ANALIZADA

Archivo de referencia: `estimaciones/archivos/EST_DOMICEM_CIUDAD_PALACE_CAVERNAS_EXTERIORES_PPACT_N06_23072026_V01.pdf`
Excel de referencia: `estimaciones/data/EST_DOMICEM_CIUDAD_PALACE_CAVERNAS_EXTERIORES_PPACT_N06_23072026_V01.xlsx`

### Hojas del Excel
| Hoja | Descripción |
|---|---|
| `CD-COAF-CEO-01` | Carátula — portada que jala datos de REO-01 |
| `CD-COAF-REO-01` | Resumen de Estimación — hoja maestra con todos los productos |
| `CD-COAF-RGO-XX` | Resumen de Generadores — una hoja por producto con entregas del período |
| `CD-COAF-RCO-XX` | Resumen de Generadores (Croquis de Ubicación) — desde el issue #27 (2026-09-01) el generador la produce por clave con entregas, con el croquis archivado en `estimaciones/data/croquis/` ya estampado (centrado, proporción conservada) y los logos DOMICEM re-estampados. Sin croquis archivado sale con el marco vacío y queda en el log — no aborta |
| `CD-COAF-RFO-XX` | Resumen de Generadores (**Reporte Fotografico**) — son fotos de obra del periodo, NO un croquis. El titulo real de la celda A5 lo dice; 6 de los 15 documentos del cliente lo traen mal como "CROQUIS DE UBICACION". Corregido 2026-09-01 al medir el issue #27. El generador la produce desde el #27; lo único manual que queda es pegar las fotos (decisión 1 del spec). Geometría: RCO `A1:J46` siempre; RFO `A1:J46` salvo MACAO 2 `A1:J52` a escala 70 |

### Datos del encabezado (todas las hojas)
- Obra, Contratista, OC/Contrato, Estimación N#, Tipo, Periodo (inicio/fin), Fecha estimación, Semana

### Resumen de Estimación (REO-01)
- **La columna A lleva la CLAVE del producto, no su posición.** Son campos
  distintos de `catalogo_estimacion`: `orden` decide en qué fila va el renglón,
  `clave` es la etiqueta que se imprime. Coinciden en 70 de las 72 filas del
  catálogo; en VMO/PATIO DE MANIOBRAS-TRA están cruzadas (orden 2 → clave 3), y
  el documento real del cliente trae 1,3,2,4 ahí. Hasta el 2026-09-01 el
  generador escribía el `orden`, así que en esa fase el REO contradecía a sus
  propias hojas RGO/RCO/RFO. **Nunca cambiar el cálculo de la fila a `clave`:**
  eso intercambia renglones enteros (concepto, P.U., acumulados) y sí mueve
  plata. La columna A no participa de ninguna fórmula.
- Lista todos los productos con: CLAVE | CONCEPTO | U.M. | CANT.proyecto | P.U. | IMPORTE | Acum.anterior | Esta estimación | Acum.actual | Por estimar | %Avance

### Generadores (RGO-XX)
- Una hoja por cada producto que tuvo entregas en el período
- Columnas: FECHA DE ENTREGA | FOLIO REMISION (= id_documento) | NO | NO.ECONÓMICO TRANSPORTE | CANTIDAD | OBSERVACIONES
- Total al final + firmas

### Bloque de firma de las hojas RGO (issues #33 y #35, 2026-08-31)

Tiene **tres partes lado a lado**, todas escritas como valor por
`_est_escribir_firma_rgo()` antes de clonar la plantilla:

| Parte | Origen |
|---|---|
| Contratista (columna A) | `EST_CONTRATISTA[empresa]` — misma fuente que `REO-01!B9`, así no pueden divergir |
| Analista (columna D) | Columna E del bloque de firma de REO-01 |
| Gerencia de obra (columna H) | Columna K del bloque de firma de REO-01 |

**La fila del bloque en REO-01 se detecta leyendo la hoja**, anclada al rótulo
`CONTRATISTA` de la columna B — nunca cableada en un diccionario fase→fila,
porque eso es exactamente lo que produjo el bug: las fórmulas apuntaban a la
fila 37/38 y el bloque solo está ahí en 2 de las 9 fases.

Al agregar una plantilla nueva, verificar que el rótulo `CONTRATISTA` aparezca
**una sola vez** en la columna B de REO-01, y que el nombre esté justo arriba.

### Lo que el sistema puede llenar automáticamente
- FOLIO REMISION = `id_documento` de la BD
- FECHA DE ENTREGA = `fecha`
- CANTIDAD = `cantidad`
- P.U. = `precio_unitario` de tabla de precios
- IMPORTE = `total`

### Pendiente confirmar con el jefe
1. **Número de estimación (N06)** — ¿automático o manual?
2. **OC/Contrato (PPACT)** — ¿fijo o cambia?
3. **Cantidades totales del proyecto** — ¿presupuesto fijo o varía?
4. **Acumulado anterior** — ¿sistema lo calcula o se ingresa la primera vez?
5. **Semana calendario** — ¿cómo se determina el número?
6. **Fecha de estimación** — ¿fecha de generación o se ingresa?
7. **Facturas sin sello** — ¿se aceptan, proceso manual o se devuelven?

---

## gstack

Instalado en `~/.claude/skills/gstack` (herramienta de Garry Tan/YC, repo verificado: github.com/garrytan/gstack, 128k+ estrellas, MIT).

- **Para cualquier navegación/automatización web usar el skill `/gstack-browse` — NUNCA usar las herramientas `mcp__claude-in-chrome__*`**
- ⚠️ **Desde el upgrade a v1.69.0.0 (2026-08-26) todos los skills llevan prefijo `gstack-`** (`skill_prefix: true`). El setup **borró las entradas sin prefijo**, así que `/spec` o `/browse` a secas ya no existen: hay que escribir `/gstack-spec`, `/gstack-browse`, etc.
- Skills disponibles: `/gstack-autoplan`, `/gstack-benchmark`, `/gstack-benchmark-models`, `/gstack-browse`, `/gstack-canary`, `/gstack-careful`, `/gstack-codex`, `/gstack-context-restore`, `/gstack-context-save`, `/gstack-cso`, `/gstack-design-consultation`, `/gstack-design-html`, `/gstack-design-review`, `/gstack-design-shotgun`, `/gstack-devex-review`, `/gstack-diagram`, `/gstack-document-generate`, `/gstack-document-release`, `/gstack-freeze`, `/gstack-upgrade`, `/gstack-guard`, `/gstack-health`, `/gstack-investigate`, `/gstack-land-and-deploy`, `/gstack-landing-report`, `/gstack-learn`, `/gstack-make-pdf`, `/gstack-office-hours`, `/gstack-open-gstack-browser`, `/gstack-pair-agent`, `/gstack-plan-ceo-review`, `/gstack-plan-design-review`, `/gstack-plan-devex-review`, `/gstack-plan-eng-review`, `/gstack-plan-tune`, `/gstack-qa`, `/gstack-qa-only`, `/gstack-retro`, `/gstack-review`, `/gstack-scrape`, `/gstack-setup-browser-cookies`, `/gstack-setup-deploy`, `/gstack-setup-gbrain`, `/gstack-ship`, `/gstack-skillify`, `/gstack-spec`, `/gstack-sync-gbrain`, `/gstack-unfreeze`
- Actualizar con `/gstack-upgrade`

## Pendiente / Futuro

> **Desde el 2026-08-31 el backlog vive en los issues de GitHub** (`gh issue list --state open`), no acá ni en `AGENDA.md`. El `README.md` es la portada del repo y muestra el estado agrupado por quién tiene que decidir. Esta lista queda como residuo histórico.
>
> **Estado al 2026-09-02.** De los seis que estaban abiertos, cuatro quedaron construidos en ramas sin mergear (#23, #26, #31, #37) más el #38 que se fileó y se construyó el mismo día. **Solo dos siguen bloqueados, los dos por gente de afuera:** el #34 (la oficina tiene que decir qué es la columna `Costo` del reporte de conduces) y el #28 (IT, dónde se despliega). Se filearon dos nuevos sin construir: el #39 (40 facturas con precio de una hoja de la lista que ya no existe) y el #40 (resolver el producto por su código).

- Convenciones de código — por definir
- Formato de entrada por suplidor — cada uno entrega diferente, se resolverá cuando lleguen más documentos
- **Deployment web** — posible opción: servidor físico que ya existe en la oficina (IT lo maneja), en vez de VPS/cloud externo. Falta coordinar con IT: specs del servidor, acceso remoto, si soporta correr Python/uvicorn 24/7, HTTPS
- ~~Formato `163419/5647`~~ — resuelto: se separa en `id_conduce` / `id_transporte`. Misma compañía duplicada → sufijo `-2`. Compañía diferente → se conserva ID completo con `/`.
- ~~Tabla de consulta en el chat~~ — verificada y funcionando
- ~~Reportes por compañía~~ — completado
- ~~Mejora visual del frontend~~ — completado (dashboard dos paneles)
- ~~Soporte `.xlsx` en importar~~ — completado (`scripts/importar_xls.py`)

---

## Historial de decisiones

Movido a `brain/Proyectos/conduces/log.md` (archivo real: `memory/log.md` en la carpeta de memoria de este proyecto) — log cronológico append-only, separado de este archivo. Este archivo (`CLAUDE.md`) se queda solo con reglas/estructura/estado actual; consultar el log cuando haga falta el detalle de una decisión pasada.

_Última actualización: 2026-09-02_

---

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules (nombres con prefijo `gstack-` desde v1.69.0.0):
- Product ideas/brainstorming → invoke /gstack-office-hours
- Strategy/scope → invoke /gstack-plan-ceo-review
- Architecture → invoke /gstack-plan-eng-review
- Design system/plan review → invoke /gstack-design-consultation or /gstack-plan-design-review
- Full review pipeline → invoke /gstack-autoplan
- Bugs/errors → invoke /gstack-investigate
- QA/testing site behavior → invoke /gstack-qa or /gstack-qa-only
- Code review/diff check → invoke /gstack-review
- Visual polish → invoke /gstack-design-review
- Ship/deploy/PR → invoke /gstack-ship or /gstack-land-and-deploy
- Save progress → invoke /gstack-context-save
- Resume context → invoke /gstack-context-restore
- Author a backlog-ready spec/issue → invoke /gstack-spec
