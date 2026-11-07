# AGENDA — historial narrativo

> **Este archivo dejó de ser el traspaso entre sesiones el 2026-09-04.** No lo
> uses para saber en qué estado está el proyecto: **es historial**, ordenado de
> lo más nuevo a lo más viejo, y cada bloque vale por la fecha que lleva encima.
>
> Para retomar, en este orden:
>
> | Qué necesitás | Dónde está |
> |---|---|
> | Estado, trampas y cómo se trabaja acá | **`HANDOFF.md`** |
> | Qué falta | `gh issue list --state open` |
> | Contexto y reglas de negocio | `CLAUDE.md` |
> | La punta de `main` | `git log --oneline -1` |
>
> **Por qué se lo sacó del arranque.** Hasta hoy este archivo abría con un
> traspaso del 2026-08-31 que decía `main` en `da4bb20`, **483 tests en verde**,
> "lo único construible es el #27" y "esperan a X los #23, #26 y #34". Para el
> 2026-09-03 ya eran 626 tests y esos cuatro issues estaban cerrados, así que un
> agente que arrancara por acá —como todavía le pedía `AGENTS.md`— empezaba
> creyendo cuatro cosas falsas. El problema no era que el bloque estuviera
> desactualizado: era que **un traspaso escrito por fecha caduca solo**, y ya
> había dos en este mismo archivo contradiciéndose. Se borró ese bloque en vez
> de reescribirlo, porque reescribirlo solo mueve la caducidad un día. Lo que
> decía y seguía siendo cierto (Conduces en pausa, el #28 esperando a IT, los
> recordatorios de método) ya vive en `HANDOFF.md`, que sí se mantiene.

## 📜 Cierre del 2026-08-31

> **El backlog dejó de vivir en este archivo.** Los pendientes son ahora issues de GitHub (`gh issue list --state open`), y el estado del proyecto se ve en el `README.md`, que es la portada del repo. Esta agenda queda como **historial narrativo**: lo que pasó y por qué, no lo que falta.

### ✅ CERRADO 2026-08-31 — [#20](https://github.com/lach06/VMO/issues/20): aprobación manual de conduces sin sello o firma

Mergeado a `main` en `f7d80f4`. Suite **369 passed** sobre el merge. Un botón por fila en Pendientes por Revisión, restringido a los motivos `falta sello` y `falta firma`, con quién/por qué/cuándo obligatorios, más reversa protegida por el libro mayor.

**`sin fila en el Excel` y `fase no reconocida` quedaron fuera a propósito**: sin fase el sistema no sabe a qué clave van los m³, y aprobarlos repetiría el mecanismo del error de los 370 m³. Se arreglan con el documento o el Excel, no con un botón.

**Decisiones tomadas en el spec** (no reabrir): la marca es **solo interna** (el documento del cliente sale idéntico); la aprobación es **reversible** salvo cuando el conduce entró de verdad en una estimación cerrada; se aprueba **de a una**, cada una con su motivo; y un conduce debajo del corte **se aprueba igual, con aviso**, sin tocar el libro mayor.

**Hallazgo que condicionó el diseño:** los 41 pendientes son todos de DOMICEM/MACAO 2 y anteriores al corte de conteo de esa fase (2026-08-16). `core.py` saltea toda factura anterior al corte (`if fecha <= corte: continue`), así que aprobarlos los registra pero **no suma a ninguna estimación**. Sin el aviso, el botón habría parecido funcionar sin mover un solo número.

**Dos errores del spec encontrados al construir. La técnica va 5/5.**

1. **El grave:** el spec afirmaba que `cerrada_en` y `aprobado_fecha` compartían formato y reloj. Falso — `cerrada_en` es UTC con sufijo `Z` y segundos (`core.py:2693`, issue #17), `aprobado_fecha` es `isoformat()` local con microsegundos. Verificado contra la BD: `2026-08-28T16:29:37Z` contra `2026-08-20T09:25:29.526082`. La guarda de la reversa los comparaba **como texto**. Corregido en `6f27be4` comparando instantes. **El bug tenía las dos direcciones**: con huso detrás de UTC bloqueaba de más, con huso adelantado dejaba pasar una reversa que desincroniza el libro mayor — el test a `+10:00` falla con `DID NOT RAISE` contra el código anterior.
2. **Menor:** `max_length` de pydantic devuelve 422, no el 400 que pedía el spec. Los límites (120/500) se implementaron como chequeo explícito en el handler.

**Verificación independiente antes de mergear:** suite corrida por fuera del agente, los 4 tests del arreglo corridos contra el código viejo para confirmar que fijan el bug, guarda y orden archivo/BD leídos a mano, y BD de producción comparada antes y después. Migración aplicada a producción el 2026-08-31 con backup previo: 5 columnas nuevas, 4183 facturas / 41 pendientes / 20 cerradas / 69 seed intactos.

**Probado en vivo por el usuario** sobre una copia de la BD: aprobó los 2 conduces sin sello, vio el badge de "no cuenta" y la reversa. Esas aprobaciones eran sobre la copia; **las reales están pendientes de rehacerse sobre la base de producción**.

### ✅ CERRADO 2026-08-31 — [#29](https://github.com/lach06/VMO/pull/29): el repo tiene README

Mergeado en `2435cd4`. El repo no tenía portada. El `README.md` es a la vez la introducción y el tablero de estado: cifras de la BD, el trabajo en revisión, los pendientes **agrupados por quién tiene que decidir** con el monto en juego, las reglas críticas de negocio y cómo correr el servidor.

Se descartó GitHub Pages: el repo es privado y publicarlo expondría cifras de facturación.

### 🆕 Backlog fileado como issues el 2026-08-31

Los pendientes que vivían en prosa en este archivo y en `TODOS.md` pasaron a ser issues rastreables, con etiquetas `esperando-a-X`, `decision`, `riesgo-financiero`, `infraestructura`:

| Issue | Tema | En juego |
|---|---|---|
| [#22](https://github.com/lach06/VMO/issues/22) | Los 2 conduces sin sello | 4.5 m³, bajo el corte |
| [#23](https://github.com/lach06/VMO/issues/23) | 101 facturas huérfanas | **$5,269** · 625 m³ |
| [#24](https://github.com/lach06/VMO/issues/24) | REBESA partida por una coma | **$15,703.60** · 75 conduces |
| [#25](https://github.com/lach06/VMO/issues/25) | `clave_resuelta` sin revalidación | ya costó **$4,070** |
| [#26](https://github.com/lach06/VMO/issues/26) | Alias de CAVERNAS `rev. 8"` | 7 m³, inerte |
| [#27](https://github.com/lach06/VMO/issues/27) | Hojas RCO y RFO | 12 hojas faltantes |
| [#28](https://github.com/lach06/VMO/issues/28) | Deployment y HTTPS | bloqueado por IT |

### ℹ️ Cerrado sin acción — el sello "invisible" de `M800013968`

Al aprobarlo, el usuario anotó como motivo *"Tiene sello pero muy claro"*, lo que a primera vista sugería un falso negativo de Vision y un problema mayor que el botón (39 pendientes más con el mismo motivo). **Preguntado, el usuario confirmó que el sello era casi invisible**, así que Vision se comportó bien al marcarlo. No hay nada que investigar ni umbral que ajustar. Corrige de paso lo que esta agenda daba por verificado: no es que el papel no tenga sello, es que es ilegible.

---

## 📜 Historial anterior — estado al cierre del 2026-08-28


**Issue #15 construido, mergeado a `main` (commit `817940b`) y cerrado en GitHub.** El Excel de conduces ahora es fuente de verdad de la descripción y la fase también en `/procesar-zip` (antes solo `importar_puente.py` lo hacía). Worktree + agente Sonnet, siguiendo el spec ya aprobado — ver detalle completo en `log.md`. Suite **260/260** en ese momento (231 base + 29 nuevos), verificada de forma independiente (no solo el reporte del agente): diff revisado a mano, tests corridos por mí antes y después del merge, y los 2 criterios de aceptación de frontend (error real del backend en vez de mensaje genérico; reset limpia ambos archivos) probados en navegador real, no solo leyendo el código.

**Auditoría completa de estimaciones — 2026-08-27, commit `fe8e260`, pusheado.** El usuario pasó 12 estimaciones reales generadas por la empresa este mes (`archivos/auditoria_estimaciones_2026-08-27/`, 11 documentos + el ZIP original), comparadas una por una contra lo que calcula el sitio (`vista-previa`, mismo motor que `/generar`) para el mismo período. MACAO 2 se excluyó a pedido del usuario (confirmado que funciona perfecto). Resultado:

- **Corregido ya:** 4 descripciones de facturas reales que no matcheaban ningún producto del catálogo (CAVERNAS x3 — 595 m³; PODIUM-1-2-3 x1 — 935 m³, el 100% de esa estimación del período) — agregados como alias en `_EST_ALIAS_DESCRIPCION_FACTURA`. **De paso se encontró y corrigió un bug de diseño real**: los alias eran globales por número de clave, no por fase — un alias de CAVERNAS se podía filtrar a cualquier otra fase con una clave del mismo número. Se corrigió escopeando por `(empresa, fase)`, con test de regresión nuevo. Suite: **261/261**.
- **Sin hallazgos:** CEDIS N10 (principal), CAVERNAS PPACT N07, VIVIENDAS PPACT N05, EXTERIORES PPACT N18 — coinciden exacto contra los documentos reales.

**Segunda vuelta sobre los 2 hallazgos que habían quedado "bloqueados" — 2026-08-27, resueltos sin necesidad de info externa.** Se agotó la evidencia disponible (el Excel de conduces, los documentos fuente del seed en `estimaciones/data/plantillas_por_fase/`, y la BD) antes de darlos por bloqueados. **En los dos casos el sistema estaba bien y el error es de la empresa** — ver los 2 puntos de abajo con el detalle probatorio.

**Cambio de flujo (regla vigente, en memoria):** la revisión de documentos se hace por el sitio web, no con scripts. Claude deja los PDFs en `dropoff/`, el usuario los comprime y los sube, y pega el screenshot del resultado en `dropoff/`. Antes de que suba: correr `scripts/backup_db.py` y anotar conteos. Después: verificar contra la BD, no contra el resumen de la pantalla.

### ✅ RESUELTO 2026-08-28 — los 370 m³ mal asignados de CAVERNAS

**Corregido en producción con `scripts/corregir_clave_resuelta_cavernas_150.py --aplicar --modo limpiar`.** CAVERNAS se puede volver a generar.

**Qué pasaba.** Antes de que existiera el alias de `fe8e260`, el sistema pidió resolver a mano las descripciones que no matcheaban, y esas resoluciones **quedan guardadas para siempre** en `facturas.clave_resuelta`, con prioridad sobre el catálogo (`clave = clave_resuelta or catalogo_norm_a_clave.get(...)`, `core.py:2207`). En una se eligió mal: 56 conduces / **370.0 m³** de `Hormigón 150 kg/cm2, Ag 3/4", T 35C, rev. 7" +/- 1"` (DOMICEM/CAVERNAS, del 2026-07-17 al 2026-08-14) quedaron resueltos a la clave 3 (*Hormigón 210*, $122) cuando van en la clave 2 (*Hormigón 150*, $111). Las otras 5 resoluciones guardadas estaban bien y quedaron intactas.

**El daño era mayor que lo que decía esta agenda.** Medido corriendo el clasificador real sobre la BD antes y después:

| | clave 2 (Hormigón 150, $111) | clave 3 (Hormigón 210, $122) |
|---|---|---|
| Antes | — | 429 m³ principal + **114 m³ PPACT** |
| Después | **370 m³** principal | **173 m³** principal, 0 en PPACT |

No era solo cobrar $4,070 de más en el renglón equivocado: los 370 m³ inflaban la clave 3 por encima de su tope (2,285 de 2,720) y ese desborde empujaba **114 m³ a la serie PPACT que no van ahí**. Corregido, la clave 3 cabe entera en el principal y el desborde desaparece. **Los dos números coinciden exacto con el N44 de la empresa** ($41,070 y $21,106) — confirmación independiente de que el arreglo es el correcto.

**Cómo se hizo.** Script en el estilo de `corregir_descripcion_desde_excel.py`: `--check`/`--aplicar`, transaccional, idempotente, backup automático con la API de backup de sqlite3 antes de escribir, y guardas que abortan sin tocar nada (que el matcher vigente mande esa descripción a la clave 2; que el universo sean exactamente las 56 filas / 370.0 m³ auditadas; que el `UPDATE` afecte esa misma cantidad). Se eligió `--modo limpiar` (borra la resolución manual y deja mandar al catálogo + alias, que es la fuente verificada contra el N44) sobre `--modo reasignar` (escribir `'2'` fijo): con `limpiar`, si algún día el alias se rompiera, estas facturas saldrían marcadas como `sin_match` — falla ruidosa — en vez de irse calladas al renglón equivocado. Probado de punta a punta sobre una copia de la BD antes de tocar producción; backup estándar (`scripts/backup_db.py`, con copia a Google Drive) corrido antes. Verificado después contra la BD, no contra la salida del script. Suite **261/261**.

### ⚠️ CORRECCIÓN — el "defecto de diseño" de vista-previa vs `/generar` NO existe

Esta agenda afirmaba que `_est_vista_previa()` ignora `clave_resuelta` mientras `/generar` sí lo usa, y que por eso la pantalla podía mostrar una cosa y el documento salir con otra. **Es falso, y conviene no seguir arrastrándolo.** `_est_vista_previa()` no nombra `clave_resuelta` en su cuerpo — de ahí venía la confusión — pero delega en `_est_clasificar_series()` (`core.py:2324`), que es exactamente el mismo clasificador que usa `/generar` (`routes_estimaciones.py:463`). Corridos los dos sobre la BD real dan idéntico, antes y después del fix. El error no pasó desapercibido por una divergencia de pantalla: **la vista previa mostraba el número malo igual**, simplemente nadie lo comparó contra el N44 hasta la auditoría.

**Lo que sí es un defecto real y sigue sin resolver:** `clave_resuelta` le gana al catálogo/alias para siempre, y nada revalida una resolución manual vieja contra un alias agregado después. Hay que decidir si se revalidan al generar, si se les pone fecha de vencimiento, o si se avisa cuando el catálogo/alias discrepa de una resolución guardada.

### 🆕 Hallazgo menor de paso — una descripción de CAVERNAS sin match

`M800013172` (2026-06-30, 7.0 m³, DOMICEM/CAVERNAS) tiene la descripción `Hormigón 150 kg/cm2, Ag 3/4", T 35C, rev. **8"** +/- 1"` — la variante de `rev. 8"`, que no está en el catálogo ni en los alias de `fe8e260` (que solo cubrió `rev. 7"`). El matcher la manda a `None` y además la factura está **sin `precio_unitario`**. Hoy es inerte: su fecha es anterior al `fecha_base` 2026-07-16, así que cae dentro del acumulado ya sembrado y no se recalcula. Pero si alguna vez se genera un período que la incluya, va a salir como `sin_match`. Decidir si se agrega como cuarto alias de CAVERNAS (apuntando a la clave 2, igual que la de `rev. 7"`) o si se corrige la descripción.

### ✅ CERRADO 2026-08-28 — la regla PPACT, construida y mergeada

Los dos issues del spec quedaron construidos por agentes Fable en worktrees, verificados de forma independiente y mergeados a `main`. Suite **285/285**.

- **[#16](https://github.com/lach06/VMO/issues/16)** (commit `270e339`) — reparto por lote y el contrato principal deja de cerrarse. Verificación: se volcó la clasificación de las 9 fases con el core viejo y el nuevo contra producción en `mode=ro` y se comparó campo por campo. Una sola diferencia en todo el sistema: `M800013832` (VMO/CEDIS clave 2) pasa de principal a ppact, dejando la clave en **0/7**, idéntico al N06. **Dos errores del spec, encontrados al construir:** el conteo del aviso es 1,478 y no 1,483, y se rompían 3 tests y no 1.
- **[#17](https://github.com/lach06/VMO/issues/17)** (commit `483220d`) — libro mayor `estimacion_cerrada` y botón Cerrar explícito. Verificación: criterio 5 idéntico en las 9 fases; criterio 12 comprobado borrando las 4,183 facturas anteriores sobre una copia scratch (resultado idéntico, el acumulado ya no depende de la historia); criterio 8 con el seed byte a byte igual, 69 filas.

### ✅ CERRADO 2026-08-28 — las 9 estimaciones del período, cerradas por el sitio

Hecho por la interfaz real, no por script: se levantó el servidor con el código de #16 y #17, y se cerraron las 9 fases del período **2026-07-17 a 2026-08-16** con el número `2026-07-17_2026-08-16`. Nueve `POST /api/estimaciones/cerrar`, nueve respuestas 200, cero errores.

**Resultado verificado contra la BD, no contra la pantalla — 20 filas en 8 fases:**

| Fase | Filas | m³ |
|---|---|---|
| DOMICEM/CAVERNAS | 5 | 627.5 |
| DOMICEM/MACAO 2 | 4 | 8,418.5 |
| DOMICEM/PATIO DE MANIOBRAS-TRB | 1 | 12.5 |
| DOMICEM/VIVIENDAS | 3 | 108.5 |
| VMO/CEDIS | 3 | 61.0 |
| VMO/EXTERIORES | 2 | 345.0 |
| VMO/PATIO DE MANIOBRAS-TRA | 1 | 21.0 |
| VMO/PODIUM-1-2-3 | 1 | 935.0 |

CANCHAS cerró con 0 filas, que es correcto: no tuvo entregas en el período (su última fue el 6 de julio). Coincide fila por fila con la simulación hecha antes de empezar. Seed intacto (69 filas), facturas intactas (4,183), un solo número y un solo período en toda la tabla.

**Lo que esto arregla, medido:** el acumulado que va a usar la próxima estimación de VMO/CEDIS clave 2 pasó de `28 principal / 2 ppact` (replay factura por factura) a **`23 / 7`**, que es lo que dice el N06 de la empresa. Y el aviso de facturas en el hueco pasó de **1,478 a 0** en las 9 fases.

**Los dos pendientes de UI quedaron probados de paso:** el botón Cerrar de #17 funcionó en las 9 fases, y la franja de aviso de #16 se comportó bien (no apareció, porque el hueco estaba vacío). Los diálogos de confirmación se registraron uno por uno y mostraron los números correctos en cada fase.

### ✅ CERRADO 2026-08-28 — [#18](https://github.com/lach06/VMO/issues/18): las hojas RGO paginadas en bloques de 40

**El usuario lo trajo el 2026-08-28: se lo pidieron el día anterior.** Nuestro generador agranda una sola hoja continua; el cliente exige que salga **dividido por página, 40 folios por página**. Verificado contra los documentos reales de la empresa (`estimaciones/data/plantillas_por_fase/`), no supuesto:

- Cada página: encabezado repetido (CLAVE / CONCEPTO / U.M. + títulos de columna) + **40 folios** + fila en blanco + **bloque de firmas** (analista de estimaciones / gerencia de obra) + salto de página explícito.
- El bloque de firmas se repite en **todas** las páginas, no solo al final.
- El **TOTAL aparece una sola vez, al final**, y su fórmula suma **un rango por página**, no un rango continuo: `=+SUM(G213:G252,G164:G203,G115:G154,G66:G105,G18:G57,)`.
- Layout medido: datos en 18-57, 66-105, 115-154, 164-203, 213-252 — bloques de 40 filas cada 49, con 8 filas de estructura entre bloques.
- Ejemplo del volumen real que manejan: la `CD-COAF-RGO-08` del N33 de MACAO 2 tiene **1,005 folios en 23 saltos de página**.

**Impacto medido sobre el período 2026-07-17 a 2026-08-16:** de 20 claves con datos, **5 superan los 40 folios** (MACAO 2 clave 8 con 837 → 21 páginas; MACAO 2 clave 6 con 312 → 8; PODIUM clave 3 con 134 → 4; CAVERNAS clave 2 con 56 → 2; EXTERIORES clave 6 con 50 → 2). El juego completo necesitaría **52 páginas RGO**.

**Qué hay que cambiar:** `_est_rgo_redimensionar()` en `core.py` (~1873-1960) y la constante `EST_RGO_CAPACIDAD_NATIVA = 40`, que hoy se usa como "capacidad antes de agrandar" y pasa a ser "tamaño de bloque". Los tests de `tests/test_rgo_capacidad_dinamica.py` fijan el comportamiento viejo.

**No bloquea cerrar estimaciones** (el libro mayor registra cantidades, no maquetación) — de hecho las 9 ya se cerraron — pero **sí bloquea entregar documentos al cliente**.

**Spec'eado y fileado el 2026-08-28 como [#18](https://github.com/lach06/VMO/issues/18)**, quality gate de codex **9/10** (el mejor de los tres specs del día). En construcción por agente Fable en el worktree `.claude/worktrees/issue-18`, rama `feat/18-rgo-paginado`.

**Aritmética fijada en el spec, verificada:** período de **48 filas** (40 datos + 4 de pie + 4 de encabezado), que coincide exacto con la primera página del documento del cliente. Con 41 folios: datos 18-57 y 66, salto en 61, TOTAL en 106. Con 175: bloques de 40/40/40/40/15, saltos en 61/109/157/205, TOTAL en 250.

**Decisión clave del spec:** con `n <= 40` **no se toca nada** — el código actual encoge la hoja para `n < 40` (TOTAL en `18+n`) y la deja nativa en `n == 40` (TOTAL en 58). La paginación es un camino nuevo que solo se activa con `n > 40`, así que 15 de las 20 claves del período no cambian ni una celda. Esa contradicción la encontró codex en el borrador (yo había escrito que el TOTAL iba en 58 para todo `n <= 40`) y se corrigió antes de filear.

**Mergeado y cerrado el 2026-08-28** (commit `0e64b52`). Suite **309/309**. Verificado de forma independiente antes de mergear: saltos en 61/109/157/205 con 175 folios, la fórmula del TOTAL sumando un rango por página, contador 1..175 sin huecos, y las 15 claves de 40 folios o menos idénticas a antes.

**Un error del spec, encontrado al construir.** El issue afirmaba que la plantilla no trae `print_area`. **Era falso**: la base trae `A1:I61` y el cliente extiende la suya según las páginas (su hoja de 63 folios tiene `A1:I111`). Por eso el `.xlsx` salía perfecto pero **el PDF seguía sin dar 40 por página física** — con `landscape + fitToWidth` un bloque de 48 filas no entra en una página apaisada y LibreOffice mete saltos automáticos (175 folios daban 27+13, 36+4, 36+4, 36+4, 15). Se pasó al setup del cliente (**portrait, escala fija 64**) y se acotó `print_area` a las columnas **A:I** hasta el pie de la última página. Verificado en PDF real: PODIUM 134 → 4 páginas 40/40/40/14; EXTERIORES 50 → 2 páginas 40/10; CAVERNAS 40 → 1 página. Comprobado antes que portrait+64 entra a lo ancho en las 9 fases, así que el setup quedó uniforme. El agente detectó y reportó esto en vez de improvisar fuera del alcance que se le dio.

**Hallazgo que cambió el enfoque:** los documentos del cliente **no son internamente consistentes**. `CD-COAF-RGO-03` del N34 tiene la página 1 con solo 13 folios y el contador con huecos. Por eso el objetivo del spec es **la regla** (40 por página), no clonar sus archivos byte a byte, que sería copiar descuidos.

### Lo que sigue, en orden de peso

1. **✅ CERRADO 2026-08-27 — la empresa confirmó el error y lo asumió como propio.** Se les avisó, respondieron que sí, que fue de su parte. No queda nada por hacer de nuestro lado; el sistema ya clasificaba bien los 5 conduces. *(Detalle probatorio abajo, se conserva por si hace falta reconstruir el caso.)* — **doble facturación real en el TRB N18.** Los folios `M800014203` (7.0 m³) y `M800014205` (5.0 m³), fecha 27/07/2026, están facturados **dos veces, en dos documentos distintos y a dos precios distintos**: en `VIVIENDAS PPACT N05` pág. 19 (RGO clave 8, "Mortero Fc80", $134.69/m³) **y** en `TRB N18` pág. 6 (RGO clave 3, "Hormigón Fc350", $154.02/m³). **Nuestro sistema tiene razón y el TRB N18 es el que está mal:** el Excel de conduces (`archivos/CONDUCES 18-08-2026.xlsx`, fuente de verdad desde el issue #15) dice `Cliente = MACAO ALTO RESORT SRL, (CIUDAD PALACE - VIVIENDAS)` / `Producto = Mortero Fc80` para ambos — exactamente lo que tiene nuestra BD, y lo que dice el propio documento de VIVIENDAS de la empresa. **Además el TRB N18 omite los 12.5 m³ que sí le corresponden:** `M800013847` (8.0), `M800013858` (2.0) y `M800013902` (2.5), que el Excel confirma como `PATIO MANIOBRAS TRB` / `Hormigón Fc350 AMB IIIA` y que nuestro sistema sí incluye. Neto: el TRB N18 completo ($1,848.24, el 100% de esa estimación) es el duplicado erróneo, y faltan los $1,925.25 reales. **CONFIRMADO CON EL PAPEL FÍSICO (2026-08-27):** los 2 PDF estaban dentro de `archivos/Puente 1.zip` y se extrajeron a `dropoff/conduces_disputados_TRB_VIVIENDAS/` (con `LEEME.md` explicando el caso). Los dos papeles dicen impreso `Cliente: MACAO ALTO RESORT SRL, (CIUDAD PALACE - VIVIENDAS)` y `Producto 44604 — Mortero Fc80 kg/cm2`, cantidades 7,00 y 5,00, misma O/C `00109827`, misma bomba `B-37`, ambos firmados. La evidencia queda **4 a 1** y el papel es la autoridad final. **El usuario confirmó el error el 2026-08-27.** Pendiente: avisarle a la empresa.
2. **🗣️ CEDIS — (a) resuelto a nuestro favor, (b) sigue necesitando a X.**
   - **(a) ✅ CERRADO 2026-08-27 — X confirmó que el acumulado a tomar es el del N05, o sea los 1,626 que el sistema ya tenía. No hubo que cambiar nada** (verificado en la BD: `estimacion_acumulado_base`, VMO/CEDIS/clave 11/serie ppact = `1626.0` a `fecha_base 2026-07-16`). La corrección le corresponde a la empresa en su N06. Detalle probatorio: **nuestro 1,626 es el correcto, el N06 de la empresa está mal.** El documento fuente del seed (`estimaciones/data/plantillas_por_fase/VMO/EST_VMO_CEDIS_PPACT_N05_22072026_V1.xlsx`, hoja `CD-COAF-REO-01` fila 27) dice: `1,521` rotulado **N01-N04**, `105` rotulado **N05**, `1,626` rotulado **N01-N05**. El N06 nuevo rotula `1,521` como "N01-N05" — o sea reusó el acumulado de **N04** y perdió los 105 m³ facturados en N05 ($13,965). Confirmado que esos 105 m³ son entregas reales: la hoja `CD-COAF-RGO-11` del N05 lista **17 folios** (17-jun a 2-jul-2026) que suman exactamente 105, y **los 17 están en nuestra BD sumando 105.0 exacto**. El seed leyó la celda correcta; no hay nada que corregir de nuestro lado.
   - **(b) ✅ CERRADO 2026-08-28 — construido y mergeado. Issues [#16](https://github.com/lach06/VMO/issues/16) (regla por lote + el principal deja de cerrarse) y [#17](https://github.com/lach06/VMO/issues/17) (guardar cada estimación cerrada, con botón Cerrar). #16 va primero. Ambos pasaron el quality gate de codex con 8/10. Sin construir.** Contexto: **X RESPONDIÓ 2026-08-27: la regla es la (a) — "si lo entregado en el mes no cabe entero en lo que queda del contrato principal, se va TODO al PPACT".** O sea que hay que **cambiar el código**: hoy `_est_clasificar_series()` en `core.py` aplica "la factura no se divide" a nivel **factura** (la que entra va al principal, la que no entra va a PPACT); tiene que pasar a aplicarse a nivel **lote/período**. **Impacto medido sobre las 9 fases para el período auditado: solo 2 claves cambian** — VMO/CEDIS clave 2 (5/2 → 0/7) y DOMICEM/CAVERNAS clave 3. **Esa medición hay que rehacerla:** se hizo con el bug de los 370 m³ vivo, y corregirlo el 2026-08-28 eliminó el desborde de 114 m³ que CAVERNAS clave 3 mandaba a PPACT — con la clave 3 cabiendo entera en el principal (173 de un tope de 2,720), es probable que esa clave ya no cambie y quede solo la de CEDIS. **Pregunta de diseño abierta que la regla no resuelve sola:** cómo se clasifican las facturas **anteriores** al período (entre `fecha_base` y `fecha_desde`), porque no sabemos dónde cortaban los períodos viejos. **Por eso conviene pasarlo por `/gstack-spec` antes de construir** (regla fija del proyecto): es lógica financiera central, toca las 9 fases y tiene esa ambigüedad. Contexto original del caso: **clave 2, la regla de reparto principal/PPACT.** El contrato principal (`4800036588`) tenía 6 m³ libres y estaba **activo** (en N09 entregó 5 m³, quedando 23 de 29). Llegaron 7 m³ el 17-jul (`M800013832` 5.0 + `M800013843` 2.0). Nuestro sistema aplica "la factura no se divide" **a nivel factura**: los 5 entran al principal (23+5=28 ≤ 29) y los 2 se van a PPACT. La empresa mandó los 7 completos a PPACT (el N06 pág. 3 lista ambos folios explícitamente) y dejó el principal intacto en 23/29. **Hipótesis a confirmar con X:** que la regla se aplique a nivel **período/lote** (si el lote entero no cabe en lo que resta, todo el lote va a PPACT), no a nivel factura. Es el único caso discriminante en los 9 documentos — en todos los demás o el principal estaba agotado o sobraba lugar, y ahí las dos reglas dan lo mismo.
3. **Decisión de X — 2 conduces sin sello** que el sistema frena a propósito y quien arma el documento a mano incluye igual: `M800013968` (falta sello, clave 6, 3 m³) y `M800014137` (falta sello, clave 6, 1.5 m³). **Verificado abriendo los PDFs: los papeles realmente no tienen sello ni firma**, así que el bloqueo es correcto. O se respeta la regla, o se revisa.
4. **Hojas RCO y RFO** (croquis de ubicación y croquis) — la empresa tiene 6 de cada una en su documento, nosotros ninguna. Feature nueva completa, sin spec.
5. **✅ AUDITADO Y CERRADO 2026-08-28 — `TODOS.md`, el bug de Monto Pendiente.** **Ningún archivo quedó con el número malo.** Son 5 archivos en total (3 reportes, 2 facturas), todos del 21/08/2026, y los 3 que tienen datos muestran **exacto** el valor correcto (`precio × cantidad`), no el del bug. El fix se aplicó el 21, no el 24: el commit `132fd8c` tiene fecha del 24 porque se commiteó después. Para dimensionar lo que se evitó, el bug subestimaba el Monto Pendiente **26 veces** ($2.46M en vez de $63.86M) y el 100% de los 3,523 conduces tiene `cantidad` distinta de 1. **Hallazgo nuevo de esa auditoría:** `CONSTRUCTORA REBESA SRL` y `CONSTRUCTORA REBESA, SRL` son la misma empresa partida por una coma (1,152 conduces / $16.3M contra 75 / $1.59M) — cualquier reporte filtrado por un nombre se pierde el otro. Anotado en `TODOS.md`, necesita que se decida el nombre canónico.
6. **✅ CERRADO 2026-08-28 — [#19](https://github.com/lach06/VMO/issues/19), `importar_puente.py` unificado con `core.py`.** Las 7 funciones de datos delegan en `core`; `CLIENTE_FASE` eliminada. **Las 3 de Vision quedaron fuera a propósito**: sus prompts difieren de verdad (el del script no pide `id_documento`, el de core sí), así que unificarlas cambiaría qué extrae el modelo de los PDFs. Trabajo en dos commits: tests de caracterización primero contra el código duplicado, refactor después, con 0 líneas de esos tests tocadas en el segundo. Suite **309 → 332**. Verificado: los 15 `cliente` reales dan idéntico, los 4 casos que devolvían `None` ahora clasifican, y los 2 corrompidos por OCR siguen en `None`. **Error del spec encontrado al construir:** decía que `buscar_precio` era copia idéntica de core, y es falso en el ruteo — con `empresa=None` core devuelve `None` pero el script consulta `precios_vmo`, camino alcanzable; unificar "a la core" habría cambiado precios en silencio. *Pendiente menor:* `decidir_no_macao2` usa una fase marcadora `"NO-MACAO-2"` para forzar la rama genérica de `_motivo_sello_firma`; funciona y está testeado, pero es un string mágico que conviene revisar si se toca esa función.
7. **Deployment** — sin definir (servidor de la oficina vs VPS; falta hablar con IT). HTTPS pendiente hasta que eso se decida.

### Ideas sin spec (ver sección "Ideas futuras" más abajo)

Reporte interno de costo/tiempo de Vision, y chatbot para revisar/editar estimaciones ya generadas.

---

## PARA CLAUDE — leer esto primero (dejado por Codex el 2026-08-26)

Codex corrigió que el sitio web leyera la fase del campo equivocado, siguiendo
`documentos/tarea_codex_fase_desde_cliente.md`.

**Qué hice:**
- `core.py`: `_enriquecer_y_matchear()` ahora determina la fase desde
  `cliente` y usa `obra` solamente como respaldo cuando el cliente no matchea.
- `core.py`: `_normalizar_fase()` ahora recibe un parámetro genérico `texto` y
  su docstring dejó de afirmar que solo procesa obras.
- `tests/test_estimaciones_validacion.py`: agregué cuatro regresiones para
  cliente prioritario, respaldo a obra, ambos campos desconocidos y el caso
  textual real de `M800014137`.

**Prueba de no-regresión:** **4,169/4,169** filas de `facturas` coincidieron
entre su fase guardada y la fase producida por la lógica nueva; **0 diferencias**.
La consulta se ejecutó con SQLite `mode=ro` sobre la BD real.

**Estado de los tests:** **230/230 verdes** (`python -m pytest tests/ -v`).

**Qué verifiqué de verdad:** antes del fix reproduje que el cliente real daba
`MACAO 2`, `obra="PARMOL"` daba `None` y el pipeline actual elegía `None`.
Después del fix ejecuté `_enriquecer_y_matchear()` con la fila real almacenada
en `pendientes_revision`: devolvió `fase="MACAO 2"` y `empresa="DOMICEM"`.
La fila siguió guardada con su motivo previo `fase no reconocida`, confirmando
que la BD no se modificó.

**Qué NO pude hacer o me quedó dudoso:** nada dentro del alcance. No se tocó
`scripts/importar_puente.py`, no se reclasificaron filas existentes y no se
resolvió manualmente `M800014137`; deberá volver a subirse por el sitio.

**Hallazgos inesperados:** ninguno adicional. Sigue pendiente, fuera de esta
tarea, el riesgo ya documentado de Vision: en `M800014137` leyó `Fc250` donde
el papel dice `Fc350` y tomó el teléfono como O/C en vez de `00109564`.

---

## PARA CLAUDE — leer esto primero (dejado por Codex el 2026-08-26)

Codex trabajó las diferencias entre nuestra estimación y la de la empresa,
siguiendo `documentos/tarea_codex_diferencias_documento_oficial.md`.

**Qué hice:**
- `core.py`: corregí el contratista DOMICEM a `DOMICEM S.A` (sin punto final).
- `core.py`: las fechas de `E12`, `H12` y `K12` ahora se escriben como fechas
  reales de Excel con el formato oficial; los valores vacíos o no ISO se
  conservan sin hacer fallar el generador.
- `core.py`: `M9` se escribe como número cuando el OC/Contrato contiene solo
  dígitos y sigue como texto para valores como `PPACT`.
- `core.py`: `H16`, `K16` y `N16` se derivan de números `N\d+`; para `N01` se
  deja `H16` vacío porque no existe estimación anterior, y para formatos no
  estándar se dejan las tres celdas vacías.
- `core.py`: las hojas RGO ahora usan la clave del producto, con padding para
  claves numéricas, sanitización para Excel y guarda contra nombres duplicados.
- `tests/test_generar_pdf_estimacion.py` y
  `tests/test_estimaciones_validacion.py`: agregué cobertura de los cinco
  cambios y actualicé las expectativas de nombres/tipos anteriores.

**Estado de los tests:** 226/226 verdes (`python -m pytest tests/ -v`; se usó
`--basetemp` dentro del workspace y ejecución fuera del sandbox para permitir
que LibreOffice corriera sus pruebas reales).

**Qué verifiqué de verdad:** generé DOMICEM/MACAO 2, período 2026-07-17 a
2026-08-16, estimación N35, semana 35, serie principal, usando una copia exacta
de la BD de producción. Comparé con `dropoff/Generadoporempresa.xlsx`: `B9`,
`E12`, `H12`, `K12`, `M9`, `H16`, `K16` y `N16` coinciden exactamente en valor,
tipo y formato. El archivo generado creó `CD-COAF-RGO-06`, `-08` y `-09`, como
pedía la tarea. La BD real no se modificó.

**Qué NO pude hacer o me quedó dudoso:** nada dentro del alcance funcional.
Las diferencias de cantidades, conduces bloqueados/faltantes y hojas RCO/RFO
siguen fuera de alcance por decisión previa. Quedó una carpeta temporal vacía o
inaccesible, `.tmp_pytest_codex_focused/`, creada por la primera corrida dentro
del sandbox: Windows negó incluso recuperar su ACL fuera del sandbox. Git no
puede leerla; no contiene cambios del producto y habrá que borrarla con una
cuenta administrativa si se quiere limpiar ese artefacto del entorno.

**Hallazgos inesperados:** la primera corrida de LibreOffice dentro del sandbox
agotó el timeout; las mismas dos pruebas pasaron inmediatamente fuera del
sandbox. No era un fallo funcional. La suite indicada en la tarea partía de
221 pruebas; con las cinco nuevas quedó en 226.

---

## Detalle de lo hecho el 2026-08-26

- **Las 9 de 9 fases tienen el acumulado automático funcionando** (issues #11, #12, #13, #14). Objetivo cumplido.
- **Suite: 231/231** (221 → 231 en el correr del día: +5 de Codex por las diferencias con el documento oficial, +4 de Codex por la fase desde `cliente`, +1 por `MACAO 11`).
- **Estética de la hoja RGO corregida** en las 10 plantillas (folios desalineados + línea vertical en la columna de transporte) — `scripts/normalizar_estetica_rgo.py`, commit `31d3c75`.
- **Se puede excluir un producto de una estimación puntual** — columna "Incluir" en la pantalla de revisión, commit `cc401d5`. El renglón sale igual en el documento con su Acumulado Anterior; solo se omite "Esta Estimación" y su hoja de generadores. *Limitación conocida:* las facturas excluidas siguen contando para el Acumulado de la próxima estimación.
- **Los 14 conduces MACAO 2 mal bloqueados quedaron resueltos** por el sitio web, y las 14 facturas sin precio que eso destapó, corregidas — ver las 2 secciones de abajo.
- **1 issue abierto: [#15](https://github.com/lach06/VMO/issues/15)** (spec'eado, sin construir). Los 6 viejos (#2, #3, #4, #5, #6, #9) se cerraron el 2026-08-26 tras verificarlos uno por uno contra el código. **Desde ahora el issue se cierra en el mismo paso que el merge.**
- **`main` local == `origin/main`.** Todo pusheado.
- Working tree limpio, `dropoff/` vacío, sin worktrees ni ramas colgando.
- **gstack v1.69.0.0** — ⚠️ los skills ahora llevan prefijo `gstack-` y las entradas viejas se borraron: `/gstack-spec`, `/gstack-browse`, etc. Codex tampoco está en el PATH: `~/.codex/packages/standalone/current/bin/codex.exe`.

### ✅ RESUELTO 2026-08-26 — los 14 conduces MACAO 2 mal bloqueados por falta de firma

**Nuevo modo de trabajo (decisión del usuario):** de ahora en adelante **la revisión de documentos se hace por el website**, no con scripts — todo tiene que terminar funcionando por ahí. Claude deja una carpeta de PDFs en `dropoff/`, el usuario la comprime y la sube por "Procesar Facturas".

- [x] **No había ningún camino abierto en el código — quedó probado, no supuesto.** `M800014672` se bloqueó el 2026-08-24 a las **13:14**; el issue #7 se mergeó a las **16:05** del mismo día (casi 3h después). El commit vigente a esa hora (`f0c7830`, 12:09) exigía `not tiene_sello or not tiene_firma` y escribía el texto `"sin firma"` — el motivo exacto que tenía guardado. Los otros 13 dicen `"falta firma"` porque vienen del script de auditoría del día 20. Verificados los 3 caminos vivos (`core.py:1166`, `importar_puente.py:530`, `reprocesar_errores_vision.py:74`): ninguno puede bloquear un MACAO 2 por firma. **No se repite.**
- [x] **13 de 14 incorporados por el sitio** (backup previo de ambas BDs, local + Google Drive). `pendientes por firma` **14 → 0**; `facturas` 4169 → 4182; MACAO 2 3268 → 3281; `sin_firma=1` 0 → 10; m³ MACAO 2 23475.0 → **23571.0**. **0 frenados por sello** — confirma que los 14 sí lo tenían.
- [x] **Entró `M800014672`** (7 m³, clave 8) — uno de los 3 documentos que faltaban para que la N35 cuadre con la de la empresa.

**Hallazgo nuevo — Vision confunde los números romanos:** el único que quedó fuera (`M800012439`, 7 m³) NO fue por sello sino por `fase no reconocida`: Vision leyó **`MACAO 11`** en vez de `MACAO II` (`cliente="...(MACAO 11, ESTRUCTURA)"`, `obra="MALESPIN MACAO 11"`). Corregido agregando esa variante a `_normalizar_fase()` (`core.py:1101`) — seguro, no existe ninguna fase con ese nombre. Cero facturas de las 4,182 ya importadas tenían la variante, así que fue la primera aparición. **`scripts/importar_puente.py` no necesita el mismo fix**: saca la fase del Excel, no de Vision.

**Bug de UI corregido de paso:** el título de la categoría decía *"(sin sello)"* aunque el motivo real de la fila fuera otro (`static/index.html:2038,2135`) — engañoso; ahora dice "ver motivo".

Suite: **231/231**. Verificado con no-regresión sobre las 4,182 facturas reales (0 diferencias) y servidor reiniciado a mano.

- [x] **Los 2 PDFs de `dropoff/reintentar_fase/` subidos y resueltos.** `M800012439` entró (fase `MACAO 2`, `sin_firma=1`, auto-resuelto de pendientes) — nota honesta: **no fue el fix de `MACAO 11` lo que lo desbloqueó**, sino que Opus, al reprocesar, leyó `MACAO II` bien; el fix sigue valiendo como red de seguridad para cuando Haiku lea mal **sin** fallar el JSON (que es justo lo que pasó a las 14:31 y lo mandó a pendientes). `M800014137` pasó de `fase no reconocida` a `MACAO 2` ✅ (el fix de Codex funcionó) y esta vez Vision leyó `Fc350` correcto, pero quedó bloqueado por **`falta sello`** — verificado abriendo el PDF: el papel efectivamente **no tiene sello ni firma**, el bloqueo es correcto. Pasa a la misma pila que `M800013968` → decisión de X. Estado final: `facturas` **4183**, MACAO 2 **3282**, `sin_firma=1` **11**, m³ MACAO 2 **23578.0**, pendientes **41 — todos por sello**, `por firma` y `fase no reconocida` en **0**.

### 🔴 BLOQUEO NUEVO — las 14 facturas entraron SIN precio, y eso frena la generación de MACAO 2

Encontrado 2026-08-26 al verificar el resultado. **Las 14 son las únicas facturas MACAO 2 sin `precio_unitario` en todo el histórico.**

**Por qué:** el precio se matchea por `descripcion` exacta (TRIM) + fase. Estas 14 entraron **por el sitio web**, que guarda la descripción que leyó Vision — llena de errores de OCR (`AM0. IIIA`, `Tomp. 020`, `Tolup. 02C`, `Agr 3/8"`, `Asg 3/8"`, `Agua 3/8"`, `AMP UIA (UIA)`, `f 25L`). Ninguna matchea. Las otras 3,268 facturas MACAO 2 entraron por `scripts/importar_puente.py`, que toma la descripción del **Excel** (texto limpio tipeado), por eso sí tienen precio.

**Impacto real, no hipotético:** `routes_estimaciones.py:460` lanza 422 `precios_faltantes` si **cualquier** factura de una clave tiene precio `NULL` — o sea que **las estimaciones de MACAO 2 que cubran junio, julio (día 3) o agosto (día 6) están bloqueadas** hasta corregir esto.

**Salida ya verificada:** los 14 conduces están en `archivos/CONDUCES 18-08-2026.xlsx` con la descripción limpia, y **las 14 cantidades coinciden exacto** con lo que hay en la BD. Son 3 productos distintos, los 3 con precio conocido en `precios_domicem` para MACAO 2:

| Docs | Código | Precio | Facturas que ya usan esa descripción |
|---|---|---|---|
| 10 | 4418 | $159.10 | 2,284 |
| 2 (`M800012679`, `M800012670`) | 4419 | $154.02 | 767 |
| 2 (`M800013080`, `M800013103`) | 4477 | $186.98 | 172 |

- [x] **Las 14 corregidas — bloqueo levantado.** `scripts/corregir_descripcion_desde_excel.py` (nuevo, idempotente, transaccional, con `--check`/`--aplicar`). Guardas: solo toca filas SIN precio, exige que la cantidad de la BD coincida con la del Excel, y exige que la descripción del Excel tenga precio para esa fase — si algo no cuadra salta la fila en vez de adivinar. Solo reescribe `descripcion`, `precio_unitario` y `total`, cada uno con su valor (nunca se mueven valores entre campos). Saltó correctamente `M800013172` (CAVERNAS, el hueco de datos real ya conocido). **Verificado:** MACAO 2 sin precio **14 → 0**; segunda corrida da 0 corregibles (idempotente); las 14 con `total = precio × cantidad` exacto y **0 inconsistencias en toda la BD**.
- [x] **Probado end-to-end por la API real, no solo en la BD:** `vista-previa` de MACAO 2 devuelve `sin_match: 0` y `sin_resolver: 0`, y `POST /generar` **generó la N35 completa** (Excel + PDF) — antes daba 422. **La clave 8 quedó en 6271.0 m³ (837 conduces), exactamente el número del documento de la empresa.** Archivos de prueba borrados después.

**Estado del cuadre con el documento de la empresa (N35, 2026-07-17 a 2026-08-16):**

| Clave | Nosotros ahora | Empresa | |
|---|---|---|---|
| 6 | 2028.0 (312) | 2032.5 (314) | faltan los 2 sin sello (`M800013968` 3.0 + `M800014137` 1.5) → decisión de X |
| 8 | **6271.0 (837)** | **6271.0 (837)** | ✅ cuadra |
| 9 | 62.5 (9) | 0 | se excluye con la feature de exclusión |

- [x] **Causa raíz spec'eada — [issue #15](https://github.com/lach06/VMO/issues/15), listo para construir.** `/spec` con 2 rondas de quality gate de Codex (**6→8/10**) más 5 precisiones extra cerradas después del gate. El Excel pasa a ser la fuente de verdad de la **descripción** y de la **fase** también en el sitio web. Decisiones tomadas: el Excel se sube junto con el ZIP (obligatorio); un PDF sin fila en el Excel va a Pendientes con motivo `sin fila en el Excel` **y sin gastar Vision**; solo la descripción manda entre los campos guardados; la fase sale del `Cliente` del Excel sin respaldo a Vision (mata de raíz la clase de bug de `MACAO 11`); y las correcciones se muestran en el resumen para poder ver si Vision empeora. +30 tests, ~3h de construcción.
  - **La 1ª ronda de Codex (6/10) encontró errores reales míos**, no cosméticos: `corregidas_lista` no puede salir de `/incorporar-y-reprocesar` (es asíncrono, el resultado sale por `/reprocesar-progreso`); el pseudocódigo de la fase se contradecía con la decisión (dejaba `obra` de Vision como respaldo, justo la puerta del bug); `procesarZip()` descarta el detalle de todo error y siempre muestra "No se pudo conectar con el servidor", así que un 400 real quedaría invisible; y varias referencias de línea estaban corridas por mi propio edit de `MACAO 11` de esta misma sesión.
  - **Medido antes de escribir el spec, no supuesto:** 4,183 de 4,183 facturas tienen hoy exactamente la descripción del Excel — **0 diferencias**, así que no hay nada contaminado que auditar hacia atrás. El riesgo es solo hacia adelante.
  - **Pendiente:** construirlo (worktree + agente, por la regla de paralelismo no arranca junto a otro que toque `core.py`).

### Comparación con el documento real de la empresa — qué quedó abierto

**El cuadre da EXACTO.** Verificado 2026-08-26: nuestro documento + los 3 conduces que faltan − los 9 de la clave 9 excluidos = el documento de la empresa, al decimal y al conduce.

| Clave | Nosotros | + faltantes | = Total | Empresa |
|---|---|---|---|---|
| 6 | 2028.0 (312) | +4.5 (2) | **2032.5 (314)** | 2032.5 (314) ✅ |
| 8 | 6264.0 (836) | +7.0 (1) | **6271.0 (837)** | 6271.0 (837) ✅ |
| 9 | 62.5 (9) | excluidos | **0** | 0 ✅ |

Los 312 y 836 que compartimos coinciden uno por uno. **No hay ningún conduce perdido ni mal clasificado** — la diferencia se explica al 100% con 3 documentos:

| Conduce | m³ | Clave | Por qué falta | Estado |
|---|---|---|---|---|
| `M800013968` | 3.0 | 6 | Falta **sello** | Bloqueo correcto → decisión de X |
| `M800014672` | 7.0 | 8 | Sin **firma** | ✅ **Resuelto 2026-08-26** — importado por el sitio, la clave 8 debería dar ya los 6271.0 (837) de la empresa |
| `M800014137` | 1.5 | 6 | Fase PARMOL | Fase ya arreglada (Codex); el PDF está en `dropoff/reintentar_fase/` listo para resubir. Falta revisar el producto a mano (Vision leyó `Fc250` en vez de `Fc350`) |


Se comparó `Generadoporempresa.xlsx` vs `Generadopornosotros.xlsx` (DOMICEM/MACAO 2, N35). Los 5 defectos nuestros ya se corrigieron (Codex). Lo que sigue abierto:

- [ ] **1 conduce sin sello que la empresa incluyó y nosotros frenamos** — `M800013968` (falta sello, clave 6, 3 m³), en `pendientes_revision`. El sistema lo bloquea a propósito (regla confirmada en los issues #7/#8), pero quien arma el documento a mano lo pone igual. **Decisión de X:** o se respeta la regla, o se revisa. *(`M800014672` ya no aplica — era el de firma, resuelto el 2026-08-26.)*
- [ ] **Vision leyó mal 2 campos** del conduce `M800014137` (PDF en `archivos/07-24-M8-14137.pdf`): leyó `Fc250` donde el papel dice **`Fc350`**, y como orden de compra agarró el **teléfono del membrete** (`809-362-4111/4195`) en vez del O/C real (`00109564`). El del producto es el riesgoso: si Vision confunde 250 con 350, un conduce puede entrar al renglón equivocado de un documento oficial sin que nadie lo note. Este se salvó solo porque la fase lo frenó antes.
- [ ] **Hojas RCO y RFO** (croquis de ubicación y croquis) — la empresa tiene 6 de cada una, nosotros ninguna. Es una feature nueva completa, no un arreglo.
- [ ] **Unificar `core.py` con `scripts/importar_puente.py`** — hoy se parchó que el sitio web lea la fase de `cliente`, pero la lógica sigue duplicada en los 2 pipelines. Es la causa raíz del bug de `M800014137` y un riesgo ya señalado en la ronda 3 de revisión.
- [x] **9 conduces de la clave 9 (62.5 m³) que nosotros teníamos y la empresa no** — **resuelto, no era error de nadie.** El usuario ya sabía que esas entregas no corresponden a esta estimación y las había intentado excluir; la exclusión no tuvo efecto por el incidente del servidor con código viejo. Confirmado que son entregas válidas que van en otra estimación: excluirlas es correcto, y que sigan contando en el Acumulado también.

*(La lista de pendientes ya no vive en este archivo: son issues de GitHub, `gh issue list --state open`.)*

---

## ✅ Resuelto 2026-08-26 — Issue #13: Acumulado Anterior + PPACT sembrados para las 8 fases restantes

- [x] **Issue #13 — mergeado a `main` (commit `93efe4a`), seed corrido contra la BD real.** `/spec` con 3 rondas de quality gate de Codex (**7→8→9/10**, el puntaje más alto del proyecto) → agente en worktree → merge fast-forward. Suite: **215/215**. Detalle completo en `CLAUDE.md`.
  - Se verificaron los 14 documentos reales del jefe con openpyxl. Matching contra `catalogo_estimacion`: **100% limpio, cero casos sin match** (no hizo falta ningún alias nuevo).
  - 3 reglas de negocio confirmadas: columna `D` de PPACT se ignora siempre; un principal pegado justo debajo de su tope es la regla de "la factura no se divide", no un dato malo; typo de fecha de CEDIS (`"16/07/206"`) normalizado y celdas vacías sembradas como `0`.
  - `scripts/seed_acumulado_base_fases.py` (nuevo) — un solo script parametrizado, 59 filas de datos, `ON CONFLICT` explícito, CLI `--todas`/`--fase`/`--list`. BD real: 10→69 filas, idempotencia confirmada con 2 corridas, MACAO 2 intacto.
  - **Resultado real: 5 de las 8 fases ganan el cálculo automático** (CAVERNAS, TRB, CANCHAS, CEDIS, TRA — verificado contra la BD real: TRB clave 2 = `2300.5/2301/333`, exacto). Las 3 solo-PPACT quedan con datos sembrados pero inertes — ver issue #14 abajo.

## ✅ Resuelto 2026-08-26 — Issue #14: las 3 fases solo-PPACT sembraban en la columna equivocada

- [x] **[#14](https://github.com/lach06/VMO/issues/14) cerrado (commit `66e0dcf`). El issue estaba mal planteado por mí — no era un hueco de `core.py`.** Arrancando el `/spec` para cerrar los 3 puntos de diseño abiertos, probé una hipótesis contra una copia de la BD real y resultó que el problema era otro: **el seed del issue #13 puso 16 filas en la columna equivocada**. En esas 3 fases el PPACT *es* el contrato (`EST_OC_CONTRATO` ya devuelve "PPACT" para ellas), o sea que es su serie **principal**, no una serie de desborde — no hay ningún contrato numerado del cual desbordar. Guardarlas como `serie='ppact'` con la serie principal vacía fue el error.
  - **Los 3 puntos de diseño abiertos desaparecieron.** El riesgo central (que el filtro por `req.serie` rompiera la generación) no existe: las facturas se siguen clasificando a `'principal'` — verificado, VMO/EXTERIORES entra con las mismas 53 facturas, 345.0 m³, mismo hash de ids antes y después. No hace falta ninguna fuente de verdad para "es solo-PPACT" porque ningún código se ramifica por eso. El frontend no cambia. **Cero cambios en `core.py`, `routes_estimaciones.py` y el frontend.**
  - `scripts/seed_acumulado_base_fases.py`: las 3 fases pasan de `"ppact"` a `"principal"` con tope `None` (PPACT nunca tiene techo). Datos totales sin cambio: 59 filas, ahora 52 principal + 7 ppact (antes 36 + 23). La validación "ppact sin principal falla" pasa a ser **incondicional** — la excepción para solo-PPACT era justamente la que permitía el estado inerte. **2 bugs encontrados al hacerlo**, ambos habrían roto el seed: la validación rechazaba `tope=None`, y `float(None)` reventaba en el INSERT.
  - `scripts/migrar_solo_ppact_a_principal.py` (nuevo): mueve las 16 filas ya sembradas. Idempotente, transaccional, aborta si encuentra un estado que no reconoce.
  - Verificado contra la BD real con backup previo: VIVIENDAS 0→2/9, PODIUM-1-2-3 0→1/3, EXTERIORES 0→13/15 productos con acumulado real; las 6 fases con contrato principal **idénticas**; migración y seed idempotentes (2 corridas de cada uno); total de la tabla preservado (69 filas); MACAO 2 intacto. Suite: **217/217**.
  - **Con esto, las 9 de 9 fases tienen el acumulado automático funcionando** — el objetivo original de los issues #11/#12/#13 queda completo.

## ❌ FALSA ALARMA (descartada 2026-08-26) — orden de productos de VMO/PATIO DE MANIOBRAS-TRA

- [x] **No hay ningún problema — el hallazgo del 2026-08-26 estaba mal planteado por mí (Claude).** Al revisar los documentos reales del issue #13 señalé que TRA tenía las claves 2 y 3 "en filas físicas invertidas respecto a `catalogo_estimacion`". **Falso.** Verificado: `core.py:2096` escribe cada producto en `fila = EST_REO_FIRST_ROW + (orden - 1)` — es la columna `orden` la que manda la fila física, no la `clave`. Y el catálogo de TRA ya tiene `orden=2 → clave=3` y `orden=3 → clave=2`, que es exactamente el orden del documento real del jefe. Una estimación generada de TRA sale idéntica al documento oficial. El error fue comparar la posición en el documento contra el número de clave sin mirar que `orden` ya tenía codificado el orden real. No hay nada que arreglar.

---

## ✅ Resuelto 2026-08-25 — probando el generador en vivo (post-merge del issue #12)

Encontrado y arreglado probando el generador real con el usuario, después de mergear los 4 issues de hoy:

- [x] **"Cant. Proyecto" precargado en la pantalla de revisión.** El tope real del contrato principal (`c.principal.tope`, ya venía en la respuesta del issue #12) ahora precarga el campo en la sección "Serie Principal" — sigue editable. En "Serie PPACT" (sin tope real) se precarga igual al "Acumulado Anterior" de esa fila, replicando lo que hacen los documentos reales de PPACT (esa columna siempre sale igual al acumulado anterior cuando no hay tope).
- [x] **Alias "Imp" = "Hidrofugo" para MACAO 2 clave 7.** 9 conduces reales del 24-jul-2026 quedaban sin resolver en el acumulado porque el papel/Vision dice "Imp" en vez del texto canónico del catálogo ("Hidrofugo") para el mismo aditivo — confirmado con el usuario que va a seguir pasando. `_EST_ALIAS_DESCRIPCION_FACTURA` (nuevo, en `core.py`) agrega esta variante al matching compartido (`_est_catalogo_norm_a_clave()`), beneficiando los 3 puntos que lo usan (vista-previa, generar, clasificación de series) de una sola vez. Verificado: las 9 facturas quedan clasificadas correctamente como PPACT.
- Nota de UX pendiente, no arreglada a propósito (el usuario pidió dejarla así): el aviso de "facturas sin resolver" cuenta descripciones únicas, no cantidad real de conduces — si se repite este patrón, considerar mostrar el conteo real.

---

## ✅ Resuelto 2026-08-25 — inconsistencia de fase entre `core.py` e `importar_puente.py`

- [x] **`core.py` unificado con `importar_puente.py` — "CIMENTACIONES..." ya normaliza a fase `"MACAO 2"`, no a una fase separada.** Investigación mostró que el problema era más grave de lo anotado: `catalogo_estimacion`/`EST_PLANTILLAS` nunca tuvieron entrada para "CIMENTACIONES MACAO II" (0 productos, 0 plantilla) — era un callejón sin salida, y además `POST /api/estimaciones/generar` filtra facturas por `fase = ?` exacto, así que un documento con esa fase separada se habría perdido silenciosamente de la estimación real de MACAO 2 (no solo el problema de sello/firma del issue #8). Confirmado con el usuario que el único lugar donde debía decir "cimentaciones" era el texto de `EST_OBRA_TEXTO[("DOMICEM","MACAO 2")]` = "SUMINISTRO DE HORMIGON PARA CIMENTACION Y ESTRUCTURA MACAO II" — ya atado a fase `"MACAO 2"`, no depende de una fase separada. Fix: `_normalizar_fase()` (`core.py`) fusiona la rama "CIMENTACIONES" con "MACAO II"/"MACAO 2", `FASES_DOMICEM` ya no incluye "CIMENTACIONES MACAO II". Verificado: `_normalizar_fase("CIMENTACIONES MACAO II TORRE A")` → `"MACAO 2"`, `_motivo_sello_firma()` ahora pide sello (no firma) para esos documentos, texto de "cimentación" sigue saliendo en el encabezado del documento oficial. Suite completa: **175/175 verdes**. Nota: `precios_domicem` sigue con 5 filas bajo fase="CIMENTACIONES MACAO II" (códigos 4413, 44548, 44567, 44601, 4461) que ya eran inalcanzables en la práctica (los 3,268 documentos reales de esa obra entraron por `importar_puente.py`, que ya unificaba) — quedan como datos huérfanos inofensivos, sin limpiar, no bloquean nada.

---

## Ideas futuras (sin spec todavía, para otra sesión)

- [ ] **Reporte interno de costo/tiempo promedio de Vision.** Idea del usuario 2026-08-24: cada vez que Vision procesa un lote (de cualquier tamaño — `importar_puente.py` y/o el ZIP subido por el sitio web en `/procesar-zip`, falta confirmar si aplica a los dos), guardar el dinero real gastado y el tiempo real que tardó, dividido entre la cantidad de documentos del lote, y acumularlo en un archivo interno (no visible en el sitio — algo que Claude pueda leer rápido entre sesiones, no un reporte para el usuario) para ir calculando un promedio cada vez más preciso de costo/tiempo por documento. Explícitamente NO es lo mismo que el ETA en vivo que ya se intentó y se quitó (saltaba de forma inconsistente) — esto es un promedio histórico post-corrida, no un contador en tiempo real. Toca los mismos archivos que el issue #8 (`core.py`, `importar_puente.py`, `scripts/reprocesar_errores_vision.py` — los puntos donde se llama a Vision) — **el #8 ya está mergeado a `main` (2026-08-24), queda libre para spec\'earse.** Falta cerrar: ¿aplica también al endpoint web, o solo al script de lotes grandes?
- [ ] **Chatbot para revisión y edición de Estimaciones.** Idea del usuario 2026-08-25, para el futuro — un chat (similar al que ya existe para validar Conduces) para revisar una estimación ya generada y corregirla si algo salió mal, sin tener que rehacer todo el formulario/proceso de generación desde cero. Sin spec, sin alcance definido todavía (qué se puede editar, si reescribe el `.xlsx` ya generado o genera uno nuevo, qué pasa con el PDF).

## Issues #9, #10, #11 — OC/Contrato, Torres/Grúa y Acumulado en vivo (2026-08-25)

- [x] **Issue #9 — OC/Contrato fijo por fase.** `/spec` (quality gate Codex 8/10) → agente en worktree → **mergeado a `main` 2026-08-25** (fast-forward, commit `dd9fde2`). Suite post-merge: 179/179. Detalle completo en `CLAUDE.md`.
- [x] **Issue #10 — separar CIMENTACION TORRES / TORRE GRUA en catálogo MACAO 2 + fix de colisión en matching.** `/spec` (quality gate Codex 9/10, 2 rondas de correcciones) → agente en worktree → **mergeado a `main` 2026-08-25** (fast-forward, commit `1893019`). Migración corrida contra la BD real de producción (8→9 filas, orden 1-9 contiguo). Suite post-merge: **185/185**. Detalle completo en `CLAUDE.md`.
- [x] **Issue #11 — Acumulado Anterior en vivo (prueba MACAO 2).** `/spec` (quality gate Codex 8/10, 2 rondas de correcciones reales) → agente en worktree → **mergeado a `main` 2026-08-25** (fast-forward, commit `555f78e`). Suite post-merge: **196/196**. Migración de esquema (`setup_est_db()`, tabla `estimacion_acumulado_base` + columna `facturas.clave_resuelta`) y seed de los 9 valores reales de MACAO 2 corridos contra la BD real de producción (idempotencia confirmada con 2 corridas). Hallazgo real del agente durante la construcción (no estaba en el issue): 3 fixtures de test existentes armaban su propia BD sintética a mano sin pasar por `setup_est_db()` — sin actualizarlas la suite se hubiera roto con la tabla/columna nueva, se corrigieron antes de escribir los tests nuevos. Detalle completo en `CLAUDE.md`.
  - Mecanismo: usuario da una base fija por producto a una fecha de corte (MACAO 2: 9 valores reales al 2026-07-16, sacados de `EST_DOMICEM_MACAO_II_4800029677_N34_22072026_V01.xlsx`, confirmado por el usuario como documento real y confiable), el sistema suma automático desde ahí con las facturas reales, el campo queda precargado en la pantalla de revisión pero sigue editable. Las resoluciones manuales de facturas ambiguas (ej. Torres/Grúa) quedan guardadas para siempre por `id_documento` (`facturas.clave_resuelta`) — nunca se vuelve a preguntar la misma factura.
  - Si una factura entre la fecha base y el período no se puede resolver, el sistema la deja afuera del cálculo y avisa — no bloquea ni inventa un número. Solo se resuelve generando una estimación real que incluya su fecha (decisión del usuario: no se construyó una pantalla aparte para resolver facturas sueltas).
  - **Pendiente para otra sesión:** expandir a las otras 8 fases cuando el usuario mande sus documentos reales — hoy solo MACAO 2 tiene filas en `estimacion_acumulado_base`, cualquier otra fase sigue 100% manual sin cambio de comportamiento.

## ✅ Resuelto 2026-08-25 — Issue #12: contratos paralelos (principal vs PPACT), prueba MACAO 2

El hallazgo de que el "OC/Contrato" no es fijo por fase sino que varía por producto (según si ese producto ya agotó su contrato principal y pasó a PPACT) — encontrado revisando documentos reales en `dropoff/` mientras se armaba el issue #11, afectaba al issue #9 ya mergeado — **quedó resuelto y mergeado el mismo día**.

- [x] **Issue #12 — contratos paralelos (principal vs PPACT) por producto.** `/spec` (5 rondas de quality gate de Codex — bajó a 6/10 en la 4ª ronda por un bug crítico real encontrado ahí mismo, terminó en 8/10) → agente en worktree → **mergeado a `main` 2026-08-25** (fast-forward, commit `a6fd265`). Suite post-merge: **207/207**.
  - Mecanismo: `estimacion_acumulado_base` (tabla del issue #11) se extendió para soportar 2 filas por producto (`serie='principal'`/`'ppact'`, PK recreada con migración transaccional). Función nueva `_est_clasificar_series()` clasifica cada factura, en orden cronológico, a la serie que corresponde — una factura NUNCA se divide entre las dos (si sumarla se pasaría del tope, la factura completa va a PPACT). La pantalla de revisión muestra ambas series juntas cuando hay excedente real, con 2 botones de generar separados — igual que los documentos reales del negocio (ej. N34 + PPACT N04 de MACAO 2).
  - Datos reales sembrados para MACAO 2: 9 topes de contrato principal + 1 fila PPACT para la clave 7 (LOSAS Y VIGAS HIDROFUGO, único producto ya agotado — 10,445/10,445 m³, 100%, con 1,767 m³ ya en PPACT).
  - **2 bugs reales encontrados por el agente durante la construcción** (no anticipados por el pseudocódigo del issue): (1) faltaba el caso de respaldo del "snapshot" del acumulado anterior — sin él, un período sin ninguna factura "de ese período" perdía facturas del cálculo; (2) el script de seed viejo del issue #11, corrido DESPUÉS del nuevo, borraba en silencio los topes recién cargados (`INSERT OR REPLACE` de SQLite resetea columnas no listadas) — reproducido contra la BD real antes de arreglarlo.
  - Verificado independientemente antes y después de mergear: diff revisado a mano, suite corrida por fuera del reporte del agente, migración+seeds corridos contra la BD real de producción con idempotencia confirmada (2 corridas de cada script), y verificación manual contra el servidor real — clave 7 congelada en 10,445 con PPACT creciendo en 1,767+, VMO/CEDIS (fase sin PPACT) confirmado sin ningún cambio de comportamiento.
  - **Pendiente para otra sesión:** expandir a las otras 4 fases con ambas series activas (CAVERNAS, PATIO DE MANIOBRAS-TRB, PATIO DE MANIOBRAS-TRA, CEDIS) — documentos reales ya en `dropoff/`. También retomar la expansión de Acumulado Anterior (issue #11) a las 8 fases restantes, que estaba pausada esperando este issue.

---

## PENDIENTE — el import de "Puente 2" (745 PDFs) TERMINÓ, retomar esto ahora

- [x] **`importar_puente.py` ahora guarda el PDF de los documentos importados con éxito — RESUELTO 2026-08-24.** `insert_factura()` recibe `pdf_bytes` opcional y escribe a `estimaciones/facturas/procesadas/` solo si el INSERT insertó una fila nueva de verdad (`cur.rowcount`), igual que ya hacía `guardar_pendiente_revision()` para los rechazados. Los 3 call sites actualizados: Fase 1 (que antes ni siquiera leía el PDF del ZIP, solo el Excel — ahora abre el ZIP también), Fase 2, y `scripts/reprocesar_errores_vision.py`. Verificado con una prueba real (BD + directorio temporales, no solo lectura de código): un insert nuevo escribe el archivo, un duplicado no lo toca ni falla.

- [x] **Exportar la Estimación a PDF — RESUELTO y mergeado a `main` 2026-08-24 (issue [#6](https://github.com/lach06/VMO/issues/6)).** `POST /generar` ahora también convierte el `.xlsx` a PDF con LibreOffice (`_est_convertir_a_pdf()` en `core.py`) y devuelve `download_url_pdf` (Excel sigue disponible igual que antes, no se reemplaza). Se confirmaron y arreglaron los 2 hallazgos reales de la investigación: (1) la hoja RGO no tenía ninguna configuración de impresión → salía partida en 2 páginas — ahora se configura horizontal + ajustar-a-ancho al clonarla por producto; (2) el pie de página mostraba `_x000a_` literal — resuelto parcheando el XML crudo del `.xlsx` ya guardado (se comprobó leyendo el código fuente de openpyxl que la API pública no puede evitar el re-escapeo). Si LibreOffice falla o no está instalado, el Excel se sigue generando igual (`download_url_pdf: null`, el botón de PDF no se renderiza). Verificado por mí de forma independiente (no solo el reporte del agente): generé un PDF real con 45 facturas sintéticas y confirmé a simple vista que el pie de página quedó en 2 líneas limpias y la hoja RGO entra en el ancho de la página. Suite completa: **155/155 tests verdes** (143 → 155, +12 nuevos, incluyen 2 tests end-to-end reales con LibreOffice para VMO/CEDIS y DOMICEM/MACAO 2).

---

## `dropoff/` limpiado 2026-08-24 — resuelto, todo guardado "por si acaso"

- [x] **`archivos/CONDUCES 18-08-2026.xlsx` (7,561 filas) — NO está importado del todo.** Verificado contra `facturas`: abril-mayo 2026 y la primera quincena de agosto 2026 no están en la BD (junio-julio sí, coincide con "Puente 1.zip"). Decisión del usuario 2026-08-24: no hace falta procesarlo ahora, se guarda igual "por si acaso" — movido de `data/` a `archivos/` junto con los ZIPs ya procesados.
- [x] **`archivos/conduces.zip` + `archivos/Puente 1.zip` (1.26GB juntos) — ya 100% procesados**, confirmado contra `facturas`. Decisión del usuario: se guardan como respaldo, no se borran.

---

## Fase 2 (issues #3, #4, #5) — COMPLETA, mergeada a `main` 2026-08-24

Construida con 2 agentes en paralelo (Claude en worktree separado para #3/#4, Codex en el checkout principal para #5) — ver `CLAUDE.md`, historial de decisiones, para el detalle completo de cada uno.

- [x] **#3** — `tests/test_rutas_conduces.py`, 19 tests (éxito+fallo, las 9 rutas de Conduces).
- [x] **#4** — `main.py` (2221 líneas) separado en `core.py` (config/auth/estado global/lógica de negocio), `routes_conduces.py` (9 rutas), `routes_estimaciones.py` (10 rutas), `main.py` final (22 líneas: crea `app`, incluye los 2 routers, monta `static/` al final).
- [x] **#5** — `requirements.txt`, `scripts/setup_db.py` crea `fecha_pago` desde el inicio, `setup_est_db()` crea también `catalogo_estimacion`/`precios_vmo`/`precios_domicem`, `scripts/seed_precios_catalogo.py` siembra los 158 valores reales idempotentemente.
- [x] **Merge de las 2 ramas resuelto a mano** — conflicto real y esperado en `main.py` (una rama lo redujo a 22 líneas, la otra le agregó 3 tablas a `setup_est_db()` sobre la versión vieja): se resolvió tomando la versión nueva de `main.py` completa y portando las 3 `CREATE TABLE` a mano dentro de `setup_est_db()` en `core.py`. De paso se corrigieron 2 referencias a `main.py` que quedaron desactualizadas post-split: `tests/test_bootstrap.py` (usaba `main.setup_est_db`/`main.DB_PATH`/etc., no `core.X`) y `AGENTS.md` (comando de bootstrap todavía decía `from main import setup_est_db`). También se actualizó la sección de estructura de `CLAUDE.md` para reflejar los 4 archivos nuevos.
- [x] **Verificado independientemente en cada paso** (no solo confiando en los reportes de los agentes): suite completa corrida por mí en cada worktree y después del merge, **143/143 tests verdes**; servidor real levantado y probado con `curl` (`GET /` → 200, `GET /companias` sin auth → 401, `GET /openapi.json` → 200); `.env`/`db/conduces.db`/`reportes/` confirmados gitignorados antes de que los agentes los tocaran; conteos de `estimaciones.db` real sin cambios (71/36/51) antes y después de todo el trabajo.
- [x] **Reproducibilidad real cerrada — 2026-08-24, `/ultrareview` cloud lo confirmó y yo lo corregí.** El ultrareview corrido sobre el PR de Fase 2 reprodujo el hallazgo que ya habíamos anotado como pendiente: un clone limpio de verdad daba **89 tests rojos** porque las plantillas de Estimaciones nunca se commitearon. Se agregó una excepción puntual en `.gitignore` para las 10 plantillas (`plantilla_estimacion_{empresa}_{fase}.xlsx` x9 + `plantilla_estimacion.xlsx` genérica) — de paso se encontró y arregló un bug real en el propio `.gitignore`: la regla `data/` sin anclar también capturaba `estimaciones/data/` por accidente, así que ninguna negación funcionaba ahí hasta anclarla a `/data/`. **Verificado clonando el repo a un directorio limpio de verdad (2 veces, no solo revisando el gitignore)**: la primera pasada bajó de 89 a 18 rojos (se me había escapado `plantilla_estimacion.xlsx`, la genérica sin sufijo de fase, que usa `test_rgo_capacidad_dinamica.py`), la segunda dio **143/143 verde** en el clone limpio. El resto de `estimaciones/data/` (listas de precio, Excel reales de facturas, validaciones de sesión) sigue gitignorado — decisión explícita del usuario, solo se commitearon las plantillas.
- [x] **Pusheado a `origin/main` el 2026-08-26.** Nota: esta línea decía "nada está pusheado" hasta esa fecha y estaba desactualizada — al ir a pushear se verificó que solo había 5 commits pendientes (los del día), no todo el historial de Fase 1/Fase 2/issues #6-#12, que ya estaba en el remoto.

---

## Verificación de Codex sobre la ronda 4 — COMPLETADA 2026-08-24

Era el único pendiente explícito de la sesión anterior. Codex sí dio veredicto esta vez (corrió en su propia terminal) y encontró 3 fallos reales más — 2 P1 (uno era una regresión real: `NameError` garantizado en `POST /api/estimaciones/incorporar-y-reprocesar`) y 1 P2. Los 3 corregidos y verificados, 3 tests de regresión nuevos agregados. Ver detalle completo en `CLAUDE.md`, entrada 2026-08-24. Suite completa: **123/123 tests verdes** (120 → 123).

**Sigue pendiente (sin cambios desde la sesión anterior):**
- Nada de la Fase 1 está commiteado todavía — sigue en el working tree, sin pedir commit
- `TODOS.md` — auditar reportes/Estimaciones ya generados con el número viejo de Monto Pendiente, antes de producción real con CONFOTUR (no urgente)
- **Fase 2** (siguiente, sin detallar): arquitectura de `main.py`, cobertura de tests hacia el resto de Conduces/Estimaciones, reproducibilidad del esquema, puntos de calidad/documentación restantes del review original

---

## Fase 1 (integridad de datos, seguridad, bug financiero) — COMPLETA, construida y probada

Pedido directo del usuario: "vamos a subir todos esos puntos a 10" sobre el
review combinado Claude+Codex del proyecto (13 áreas puntuadas 1-10). Pasó
por `/spec` (5 rondas) y `/plan-eng-review` (arquitectura/código/tests/
performance + segunda opinión independiente) antes de tocar código — ver
detalle completo de cada hallazgo y decisión en `CLAUDE.md`, historial de
decisiones del 2026-08-21.

**Corregido y probado hoy:**
- [x] Bug financiero real: `monto_pendiente`/`monto_pagado` ahora es `precio × cantidad` (3 ubicaciones: `main.py:206,220,406`)
- [x] Caché de reportes se invalida (borrado completo) tras cualquier import/pago
- [x] Nombre de compañía sanitizado en nombres de archivo (`_slug_compania()`)
- [x] Regla de ID unificada — mínimo 4 caracteres sin tope, en los 4 puntos de entrada
- [x] `pagar.py`: columna `fecha_pago` (migración idempotente automática), re-marcar un pago ya hecho no lo sobreescribe
- [x] XSS en `onclick` de los 4 botones de descarga — ahora usan `escapeAttr()`
- [x] `exportarCSV()` sin CSV injection (quoting + neutralización de fórmulas)
- [x] Límite del ZIP de facturas: 50MB / 1000 PDFs por lote
- [x] Fase no reconocida en facturas → `pendientes_revision` (ya no cae en VMO a ciegas) — se mapearon también las 3 fases VMO que faltaban (CAMPO DE GOLF, PUENTES DE MANGLAR, BALLROOM)
- [x] Si falla el doble-chequeo de sello/firma con Sonnet → `pendientes_revision`, no confía en Haiku
- [x] `_confirmar_registros()`: PDF se escribe antes del INSERT, cuenta con `rowcount` real, excepciones logueadas (no silenciadas)
- [x] Generador de Estimaciones: valida `orden` contiguo del catálogo (evita escribir en la fila física equivocada de un documento oficial); período sin facturas da error claro en vez de Excel vacío con 200
- [x] `tests/test_conduces.py` nuevo — primera cobertura del módulo Conduces (0% → cubierto)
- [x] Suite completa: **112/112 tests verdes** (89 → 112)

**Rondas 2, 3 y 4 de verificación (mismo día) — 3 fallos reales más encontrados y corregidos en cada ronda, ver `CLAUDE.md` para el detalle completo de cada uno.** Patrón confirmado: la auto-revisión de Claude no bastaba sola, cada ronda con Codex/subagente independiente encontró algo real que se había pasado. Regla permanente guardada en memoria (`feedback_no_dejar_desorden.md`): nunca declarar un cambio terminado sin correr la suite completa y sin segunda opinión externa. Suite final: **120/120 tests verdes**.

**Verificación de Codex sobre la ronda 4 — RESUELTA 2026-08-24, ver sección al inicio de este archivo y `CLAUDE.md`.** Encontró 3 fallos reales más (2 P1, 1 P2), todos corregidos.

---

## Generador de Estimaciones — COMPLETO (T1-T7), construido y probado con datos reales de las 9 fases

Spec completo en `documentos/spec_generador_estimaciones.md` (quality gate
Codex 7/10, actualizado varias veces hoy con hallazgos reales — ver historial
de decisiones en `CLAUDE.md`). Estado real al cierre de la sesión 2026-08-19:

**Recibido:** el usuario consiguió las estimaciones reales (PDF+Excel) de las
**9 fases** (4 DOMICEM + 5 VMO) vía WeTransfer, organizadas en
`estimaciones/data/plantillas_por_fase/{DOMICEM,VMO}/`. Esto permitió corregir
varias cosas que el spec original tenía mal (ver `CLAUDE.md` para el detalle
completo de cada hallazgo):
- Celda del cliente es `A2`, no `B2`
- Texto de "OBRA" (`B7`) es una frase completa por fase, no el nombre corto — tabla de las 9 confirmada en el spec
- Contratista: "DOMICEM S.A." / "VMO CONCRETOS S.A" (sin coma)
- **`REO-01` lista el catálogo COMPLETO de productos de la fase** (no solo los entregados ese mes) — decisión del usuario, fiel al documento real
- El catálogo real de productos (con renglones por elemento estructural, ej. "PILOTES", "LOSAS Y VIGAS") **no es el mismo** que `precios_vmo`/`precios_domicem` (esa tabla sigue siendo solo para precio de facturas individuales) — se creó tabla nueva `catalogo_estimacion` (71 productos, extraídos de los 9 Excel reales)
- En MACAO 2, "CIMENTACION TORRES" y "TORRE GRUA" son el mismo concreto sin forma de distinguirlos desde la factura — se fusionaron en 1 renglón
- El match factura↔catálogo es automático pero **con pantalla de revisión antes de generar** (decisión del usuario) — lo que no matchea automático (`sin_match`) se resuelve a mano antes de poder generar

**Construido y probado hoy:**
- [x] `catalogo_estimacion` en `estimaciones.db` (71 productos, 9 fases)
- [x] `estimaciones/data/plantilla_estimacion.xlsx` — plantilla limpia derivada de VMO/CEDIS (CEO-01+REO-01+1 hoja RGO, fórmulas intactas, datos de ejemplo borrados). **Capacidad actual: 12 productos** (exacto para CEDIS) — las demás fases (3 a 15 productos) todavía no están generalizadas, ver pendiente abajo
- [x] `GET /api/estimaciones/vista-previa` — matchea facturas del período contra el catálogo, devuelve `sin_match` si algo no coincide
- [x] `POST /api/estimaciones/generar` — genera el `.xlsx` real (duplica hoja RGO por producto con entregas, llena REO-01 completo, valida precios faltantes / >40 facturas por producto / campos faltantes)
- [x] `GET /api/estimaciones/descargar/{nombre}`
- [x] **Probado end-to-end con datos reales de VMO/CEDIS** (junio-julio 2026): vista previa matcheó 12/12 sin nada sin_match, validación de capacidad (>40 facturas) rechazó correctamente con 422, generación completa con rango chico (15 facturas reales) produjo un `.xlsx` verificado a mano — celdas, fórmulas cruzadas REO-01↔RGO-01, y suma de cantidades todo correcto
- [x] Recálculo automático con LibreOffice — **RESUELTO 2026-08-20**, ver sección "LibreOffice — RESUELTO" más abajo

**Arquitectura de la generalización — DECIDIDA 2026-08-20 (`/office-hours` + `/plan-eng-review` de gstack, con segunda opinión de Codex):**

Ver `docs/designs/generador-estimaciones-plantillas.md` para el registro completo
de la decisión (premisas, alternativas consideradas, opinión de Codex). Resumen:

- **9 plantillas fijas por fase** (`plantilla_estimacion_{empresa}_{fase}.xlsx`),
  no inserción dinámica de filas — Codex confirmó contra la documentación de
  openpyxl que `insert_rows()` no garantiza mantener celdas combinadas/fórmulas,
  y ya habíamos visto fallar esto una vez
- Las 9 plantillas se construyen **todas con la misma regla**: bloque de
  productos siempre empieza en fila 17 (nosotros lo controlamos al limpiarlas,
  no depende de dónde estaba en el documento original)
- **La fila final no se hardcodea — se calcula:** `17 + cantidad_productos - 1`,
  usando la cantidad real de `catalogo_estimacion`. El registro `(empresa,fase)`
  solo guarda la ruta del archivo + cantidad de productos esperada (para el
  chequeo de sincronización, ver abajo)
- **Chequeo de sincronización catálogo↔plantilla** antes de generar — si en el
  futuro se agrega un producto a `catalogo_estimacion` sin reconstruir la
  plantilla de esa fase, el sistema falla claro en vez de escribir en la fila
  equivocada de un documento oficial
- Si falta el archivo de plantilla para una combinación válida → error 500
  claro, nunca genera con una plantilla de respaldo
- **Script reutilizable** para limpiar/reconstruir una plantilla (documentar en
  este archivo cuando se construya) — no hacerlo todo a mano sin dejar rastro
- **Se introduce pytest** (primera vez en este proyecto) — tests mínimos que
  abren cada una de las 9 plantillas generadas y verifican estructura (hoja
  correcta, cantidad de filas, fórmula de `K`, sin `#REF!`). No prueba el
  cálculo de Excel en sí (requiere LibreOffice, sigue pendiente instalar)

**Diseño del frontend — RESUELTO 2026-08-20 (`/plan-design-review` de gstack, 7 dimensiones):**

Wireframes HTML/CSS reales (sin IA — no había API key de OpenAI configurada
y no se configuró sin instrucción explícita) guardados en
`C:\Users\axelo\AppData\Local\Temp\wireframe_generar_estimacion.html` y
`wireframe_generar_estimacion_revision.html` (temporales — el diseño final
queda documentado en `docs/designs/generador-estimaciones-plantillas.md`,
sección "Diseño del frontend"). Decisión clave: "Cant. Proyecto"/"Acum.
Anterior" se construyen editables por ahora (dependen de las preguntas #3/#4
aún pendientes con el jefe). T6 y T7 abajo ya incorporan los hallazgos de la
revisión (spinner, estado de descarga, mensajes de error visibles en la
pantalla, mobile, accesibilidad).

**T1-T7 — CONSTRUIDO Y PROBADO 2026-08-20** (trabajado con segunda opinión de Codex antes de tocar los 9 documentos oficiales, y probado por la interfaz real con gstack `/browse` — no solo curl. Detalle completo de cada hallazgo en `CLAUDE.md`):
1. [x] **T1** — `scripts/limpiar_plantilla_estimacion.py` (nuevo, reutilizable) — las 9 plantillas generadas y verificadas estructuralmente. Hallazgos reales de la inspección: fórmula pegada como número literal en CAVERNAS (arreglado reescribiendo las 8 columnas de fórmula explícitamente en vez de confiar en el archivo real), y MACAO 2 con 9 filas físicas vs 8 en catálogo (Codex confirmó que `delete_rows()` de openpyxl no ajusta fórmulas/celdas combinadas — se optó por dejar 1 fila en blanco sin tocar la estructura, cero riesgo)
2. [x] **T2** — Registro `EST_PLANTILLAS` (empresa,fase)→archivo+capacidad en `main.py`
3. [x] **T3** — `estimaciones_generar`/`vista_previa` generalizados, ya no dependen de CEDIS
4. [x] **T4** — `_est_plantilla_de_fase()` — plantilla no encontrada (500) / catálogo excede capacidad (422 `catalogo_desincronizado`)
5. [x] **T5** — pytest instalado (primera vez en el proyecto), `tests/test_plantillas_estimacion.py`, 55 casos, todos verdes
6. [x] **T6** — Frontend reescrito según los wireframes aprobados: formulario → "Continuar" → pantalla de revisión (4 campos manuales + tabla de catálogo editable + tabla roja de reasignación manual, botón bloqueado hasta resolver todo) → descarga
7. [x] **T7** — `mensajeErrorEstimacion()` traduce cada código de error del backend a un mensaje específico en español
8. [x] Probado con datos reales de DOMICEM/VIVIENDAS y DOMICEM/CAVERNAS (con `sin_match` real) además de la regresión de VMO/CEDIS

**2 bugs reales encontrados y arreglados probando por la interfaz (no en código de prueba):**
- `escapeHtml()` no escapa comillas dobles — corrompía el HTML al guardar una descripción con símbolo de pulgadas (`"`) en un atributo. Arreglado evitando pasar la descripción por un atributo HTML del todo (se lee por índice del array JS)
- CSS Grid en mobile (`grid-template-columns: 1fr` sin `minmax(0, ...)`) dejaba que la tabla ancha de catálogo empujara todo el layout fuera del viewport — cambiado a `minmax(0, 1fr)`

**LibreOffice — RESUELTO 2026-08-20.** Instalado (26.2.5 x86-64). `tests/test_calculo_estimacion.py` (nuevo) fuerza el recálculo real de las 9 plantillas con `soffice --headless` y verifica los valores calculados (no solo el texto de la fórmula) contra lo esperado a mano — 9/9 verdes.

**Bug de capacidad de la hoja RGO — RESUELTO 2026-08-20.** El usuario probó MACAO 2 en vivo y encontró que el límite de 40 facturas/producto/período (pensado para CEDIS) no alcanzaba — MACAO 2 llega a 937 facturas/mes para un solo producto. Se cambió a **capacidad dinámica** (`_est_redimensionar_rgo()` en `main.py`): la hoja de generadores de cada producto crece o encoge exactamente según la cantidad real de facturas, sin techo fijo. Se encontraron y arreglaron 4 bugs reales durante la construcción (detalle completo en `CLAUDE.md`) — probado con LibreOffice (`tests/test_rgo_capacidad_dinamica.py`, 18 casos) y con el caso real exacto que falló primero (MACAO 2, 511+52 facturas fusionadas, 703 facturas totales, verificado que la hoja de 563 filas suma correcto). Suite completa del proyecto: **82/82 tests verdes**.

**Pendiente (no bloquea nada de lo anterior):**
- 1 factura histórica de DOMICEM/CAVERNAS sin `precio_unitario` en la tabla `facturas` (hueco de datos real, no un bug — se puede corregir con `scripts/backfill_precios.py` cuando se tenga el precio)
- Preguntas #3/#4 con el jefe (Cant. Proyecto/Acum. Anterior fijo o variable) siguen abiertas — por ahora esos campos son editables a mano

---

## Completado hoy — Zona de "Pendientes por Revisión" + Haiku/Opus en panel web

Mientras el spec de arriba estaba en hold, se construyó una feature completa (pedida directamente, sin pasar por `/spec`):

- [x] Panel "Procesar Facturas" ahora usa **Haiku** primero (antes Opus siempre) — más barato
- [x] Resumen con 4 categorías: OK / errores de lectura (reprocesable) / pendientes sin sello-firma (nunca reprocesable) / duplicados
- [x] Botón único **"Incorporar válidos y reprocesar errores con Opus"** (`POST /api/estimaciones/incorporar-y-reprocesar`) — repetible si quedan errores tras reprocesar
- [x] Tabla nueva `pendientes_revision` en `estimaciones.db` + carpeta `estimaciones/facturas/pendientes_revision/` — guarda PDF + todo lo que Vision alcanzó a leer
- [x] Panel nuevo en el sitio: "Pendientes por Revisión" (solo lectura)
- [x] Auto-resolución: si se resube el mismo `id_documento` ya corregido, sale de pendientes solo
- [x] `importar_puente.py` también manda sus rechazados a la misma tabla (consistencia entre los dos pipelines)
- [x] 2 bugs de paso arreglados: matching de precio por `id_producto` en vez de `descripcion` en el endpoint web (ya se había arreglado en el script, faltaba acá); bug de "thinking" de Opus 5 en `_procesar_pdf_sync`
- [x] Probado end-to-end por la interfaz real con gstack `/browse`

**Nada pendiente de esto** — quedó completo y probado.

---

## Bloqueado — Esperando respuesta del jefe

**2026-08-24: decisión del usuario — se van a conversar en persona, no por mail.** Puntos de charla armados (mismo contenido que las 7 preguntas de abajo, redactados como mensaje) en `C:\Users\axelo\.claude\jobs\280f923b\tmp\email_preguntas_jefe.txt` si se quieren llevar de referencia a la reunión.

1. ~~Número de estimación (N06)~~ — **RESUELTO 2026-08-25**: lo ingresa el usuario (queda como campo manual, sin cambio de código).
2. ~~OC/Contrato~~ — **RESUELTO 2026-08-25**: es fijo por fase, se puede hardcodear (como ya son `EST_CLIENTE`/`EST_CONTRATISTA`/`EST_OBRA_TEXTO`). Confirmado analizando la celda `M9` de los 9 documentos reales:

   | Fase | OC/Contrato |
   |---|---|
   | DOMICEM — CAVERNAS | `4800029676` |
   | DOMICEM — MACAO 2 | `4800029677` |
   | DOMICEM — PATIO DE MANIOBRAS-TRB | `4800032854` |
   | DOMICEM — VIVIENDAS | `PPACT` |
   | VMO — CANCHAS | `4800037426` |
   | VMO — CEDIS | `4800036588` |
   | VMO — PATIO DE MANIOBRAS-TRA | `4800025583` |
   | VMO — PODIUM-1-2-3 | `PPACT` |
   | VMO — EXTERIORES | `PPACT` (el documento real tenía "PPACT 16" — el usuario confirmó quitar el "16") |

   "PPACT" no es un número de contrato, es un tipo de documento — el usuario explicó que se crea un PPACT cuando el contrato original de esa fase ya se agotó, para seguir registrando lo consumido después de agotarlo. Esas 3 fases (VIVIENDAS, PODIUM-1-2-3, EXTERIORES) usan ese texto fijo en vez de un número.
   - [x] **RESUELTO y mergeado a `main` 2026-08-25 (issue #9)**: `EST_OC_CONTRATO` (constante `(empresa,fase)→valor` en `core.py`, igual patrón que `EST_OBRA_TEXTO`) implementada con `_est_oc_contrato()` (falla 500 `oc_contrato_no_definido` si falta la combinación, mismo patrón que `_est_plantilla_de_fase()`). Campo manual quitado de `EstGenerarRequest`, del formulario del frontend, y de los 2 payloads de test. 4 tests nuevos (2 unit + 2 integración con datos reales verificando celda M9). Suite completa post-merge: **179/179**.
3. **Cantidades totales del proyecto** — el contrato es una cantidad fija que se ha ido despachando durante años (confirmado 2026-08-25) — implica que "Cant. Proyecto" por producto también debería ser un valor fijo guardado una sola vez (ej. en `catalogo_estimacion`) en vez de pedirse editable en cada generación como está hoy. Falta el número real por producto — no resuelto todavía, solo la naturaleza del dato.
4. ~~Acumulado anterior (N01-N05)~~ — **RESUELTO 2026-08-25**: lo ingresa el usuario cada vez (coincide con lo ya construido — campo editable en la pantalla de revisión, sin cambio de código necesario).
5. ~~Semana calendario~~ — **RESUELTO 2026-08-25**: lo ingresa el usuario (coincide con lo ya construido, sin cambio de código necesario).
6. ~~Fecha de estimación~~ — **RESUELTO 2026-08-25**: se ingresa a mano (coincide con lo ya construido, sin cambio de código necesario).
7. ~~Facturas sin sello~~ — **RESUELTO** vía issue #7 (sello obligatorio para MACAO 2, no se aceptan sin sello).
8. ~~80 facturas "MACAO 2" con producto de hormigón Fc350 (Agg 3/8" y 3/4", rev. 8"+/-1")~~ — **RESUELTO 2026-08-19**: confirmado que "CIMENTACIONES MACAO II" y "MACAO 2" son la misma fase para estos 2 productos. Se agregaron los códigos `44600` (Agg 3/8", $208.01) y `44570` (Agg 3/4", $191.27) a `precios_domicem` también bajo fase "MACAO 2" (duplicando el precio de CIMENTACIONES MACAO II, sin tocar los demás códigos que sí tenían precio propio y distinto bajo MACAO 2, ej. código 44567). Backfill corrido — 81 de 82 facturas quedaron con precio. Solo queda 1 factura de CAVERNAS sin precio (hueco de datos real, no relacionado).
9b. ~~Cliente/contratista exacto para estimación VMO~~ — **RESUELTO 2026-08-19**: confirmado con los 9 archivos reales. Cliente = "MACAO ALTO RESORT S.R.L" (mismo que DOMICEM), contratista = "VMO CONCRETOS S.A" (sin coma — corregido desde la primera confirmación, que usaba el membrete de los conduces en vez del documento de estimación real).
9. ~~Conduce `30376` (CONSTRUCTORA REBESA) — falta la fecha~~ — **BAJA PRIORIDAD / no crítico**: es dato de prueba de la importación inicial del 2026-08-06 (antes del trabajo de Estimaciones), probablemente de fines de junio 2026 (estimado por proximidad de numeración, sin confirmar). El precio/cantidad ya está correcto. No bloquea nada — completar la fecha solo si en algún momento se necesita, sin urgencia

---

## Auditoría sello/firma MACAO 2 — COMPLETADA 2026-08-20

Se confirmó que Haiku da falsos positivos de sello (confunde membrete impreso
con timbre físico). Se validó `claude-sonnet-5` como alternativa confiable y
más barata que Opus. Se auditaron las **2,742 facturas de fase MACAO 2** ya
importadas, vía Batch API (`scripts/auditar_sello_macao2.py`).

**Resultado: 53 facturas con problema real de sello/firma** (0 errores de
lectura) — 45 sin sello, 8 sin firma. Se movieron las 53 de `facturas` a
`pendientes_revision` (mismo mecanismo que usa el resto del sistema — el PDF
se guardó en `estimaciones/facturas/pendientes_revision/`, se sacaron de
`facturas`). Si alguien resube esos documentos corregidos, el sistema los
saca de pendientes solo (mecanismo ya existente, sin cambios).

`facturas` con fase MACAO 2 quedó en 2,689 (2,742 − 53). `pendientes_revision`
quedó con 58 filas en total (5 que ya había + las 53 nuevas).

- [ ] **Pendiente de verificar:** `estimaciones/data/estimaciones_main.xlsx`
  (el Excel maestro) probablemente todavía tiene esas 53 filas — el
  movimiento se hizo directo en la BD, no pasó por el flujo normal de la
  interfaz que sincroniza el Excel. Revisar y limpiar si hace falta.

---

## Operación: asegurar la base — REQUISITO antes de Estimaciones

El usuario pidió hacer esto ANTES de arrancar el generador de estimaciones (aunque ya lleguen las respuestas del jefe). Cubre:

- [x] **Seguridad del sistema — RESUELTO 2026-08-20**: auditoría `/cso` completa (reporte en `.gstack/security-reports/2026-08-20-audit.json`). 6 hallazgos (2 críticos, 2 altos, 1 medio, 1 bajo) — los 6 arreglados y verificados funcionando de verdad con `/browse` (login, descarga de reporte, panel de pendientes). Detalle completo en `CLAUDE.md`. Pendiente real que queda: **HTTPS** — no se tocó porque el sistema corre local por ahora (sin deployment con acceso remoto todavía) — revisar cuando se decida cómo desplegarlo (ver sección de deployment más abajo)
- [x] **Backups de las bases de datos — RESUELTO POR COMPLETO 2026-08-20 (local + copia externa)**
  - `scripts/backup_db.py` — respalda `conduces.db` y `estimaciones.db` con la API de backup de sqlite3 (segura con la BD en uso), guarda en `backups/db/` con timestamp, borra automáticamente lo de más de 30 días
  - Tarea programada de Windows **"VMO_Backup_Conduces_Estimaciones"** — corre el script todos los días a las 8:00 PM, con "ejecutar en cuanto sea posible" si la compu estaba apagada a esa hora. Probada manualmente (`LastTaskResult: 0` = éxito, backup real generado)
  - Log en `backups/backup_log.txt`
  - **Copia externa activa** — usuario instaló Google Drive para escritorio (`G:\My Drive`), se creó la carpeta `G:\My Drive\VMO Conduces - Backups` y se agregó `GDRIVE_BACKUP_DIR` a `.env`. Probado corriendo el script: los 2 backups llegaron correctamente a la carpeta sincronizada — Google Drive los sube solo en segundo plano
- [x] **Integridad de los datos** — resuelto 2026-08-19. Chequeo final sobre ambas BD:
  - `estimaciones.db`: 3,480 facturas, 0 campos críticos nulos, 0 duplicados de `id_documento`, 0 inconsistencias precio×cantidad≠total, empresa/fase consistentes. Solo 82 sin precio (bloqueadas por pregunta #8 al jefe)
  - `conduces.db`: 3,523 conduces, 0 duplicados, 0 IDs inválidos, 0 cantidades/precios negativos
  - [x] Conduce `30619` completado 2026-08-19 — producto="GRAVILLLA", precio=830 (recuperado de `data/conduces_para_revisar.xlsx`, sin conflicto con lo que ya había en la BD)
  - [x] **Conduce `30376` — conflicto precio/cantidad RESUELTO 2026-08-19**: `conduces.db` (precio=830.0/cantidad=27.5) confirmado correcto contra el documento fuente original (`archivos/2026-08-06 14-31.pdf`, Orden 53587 — ~280 conduces de ARENA/GRAVA de REBESA, el 100% con precio=830.00 fijo y cantidad variable 17-30). `data/conduces_para_revisar.xlsx` tenía los valores invertidos, no se usó. No se tocó la BD (ya estaba bien). Solo falta la fecha — ver pregunta #9 arriba, no hay documento fuente disponible con ese dato

---

## Bug crítico encontrado y arreglado — precio_unitario nunca se matcheaba

`scripts/importar_puente.py` tenía `insert_factura()` como placeholder sin terminar — nunca buscaba el precio (comentario "se puede actualizar despues" + `pass`). Verificado contra la BD real: **0 de 3311 facturas tenían precio matcheado.**

- [x] Arreglado — ahora matchea por `descripcion` (viene del Excel, no de Vision — el código de producto que extrae Vision no es confiable, VMO nunca lo trae)
- [x] Backfill corrido sobre las filas ya importadas (`scripts/backfill_precios.py`, reutilizable)
- **DOMICEM: 2918/3000 con precio (97.3%)** — excelente (dataset completo, tras terminar el proceso Vision MACAO 2 al 100%)
- **VMO: 40/463 con precio inicialmente (8.6%)** — no era bug de código, `precios_vmo` solo tenía 34 productos cargados

### Actualización 2026-08-19 — usuario subió `dropoff/Lista de precios (1).xlsx`

- Hoja DOMICEM: **coincide 100%** con lo que ya teníamos (0 diferencias, 0 productos nuevos) — confirma que esa tabla está correcta
- Hoja VMO: 72 productos (vs los 34 que teníamos) — **se cargaron 6 de los 7 productos faltantes**, `precios_vmo` ahora tiene 40 filas
- **VMO subió a 328/463 (70.8%)** con los primeros 6 productos cargados
- [x] **RESUELTO — el "producto ambiguo" no era ambiguo**: las 135 facturas de "280...Fibra" son TODAS de fase PODIUM-1-2-3 (no Exteriores como se pensó al principio) — match exacto e inequívoco con código 44534 (RD$142.00)
- [x] **RESUELTO — columna `fase` agregada a `precios_vmo`** (`scripts/migrar_precios_vmo_fase.py`), con fallback (código sin fase específica = aplica a cualquier fase). Matching actualizado en `main.py` (endpoint en vivo, ahora matchea por `descripcion` en vez de `id_producto` — Vision no es confiable ahí) e `importar_puente.py`
- **✅ VMO: 463/463 con precio (100%)**
- **DOMICEM: 2918/3000 (97.3%)** — quedan 82 facturas sin precio, son solo 3 productos con revenimiento "8" +/-1"" que no están en la lista de precios (hueco real de datos, no bug)
- [ ] **PENDIENTE — 3 fases VMO nuevas sin mapear en el código**: CAMPO DE GOLF, PUENTES DE MANGLAR, BALLROOM (aparecen en la lista de precios, no en `CLIENTE_FASE`/`FASES_VMO`) — **según compañero del usuario, son fases ya terminadas**, baja prioridad, no se mapearon esta sesión
- [ ] **PENDIENTE — 3 productos DOMICEM con revenimiento "8" +/- 1""** (82 facturas):
  - 81 de esas 82 **sí tienen precio en la lista**, pero bajo la fase "CIMENTACIONES MACAO II" en vez de "MACAO 2" — ver pregunta #8 en "Bloqueado — Esperando respuesta del jefe" arriba
  - 1 factura (CAVERNAS, "Hormigón 150 kg/cm2...rev 8"+/-1"") genuinamente no tiene precio en ningún lado de la lista — conseguir con el jefe/área de precios

---

## Pendiente de construcción

- [ ] Generador de estimación (backend `/api/estimaciones/generar`) — bloqueado hasta respuestas del jefe Y hasta completar "Operación: asegurar la base" de arriba
- [ ] Plantilla Excel de estimación VMO — aún no se ha recibido el ejemplo
- [ ] Panel "Generar Estimación" — conectar con el backend cuando esté listo
- [ ] Probar ZIP con facturas reales que tengan sello y firma (el ZIP actual tenía facturas sin sello)

---

## Pendiente general

- Definir convenciones de código del proyecto
- Formato de entrada por suplidor — cada uno entrega diferente, resolver cuando lleguen más documentos
- Explorar deployment web — preguntas pendientes: usuarios, acceso (local vs remoto), servidor/VPS, presupuesto
  - Pista del jefe: hay un servidor físico en la oficina que maneja IT — evaluar esa opción antes que VPS externo. Falta hablar con IT (specs, si puede correr Python 24/7, HTTPS, acceso remoto)

---

## Proceso Vision MACAO 2 — COMPLETADO (2026-08-19)

Script que importó 3,490 PDFs del ZIP "Puente 1.zip" (junio-julio 2026). **100% terminado.**
- Fase 1 (738 PDFs no-MACAO 2): completada — importados del Excel sin Vision
- Fase 2 (2,752 PDFs MACAO 2): completada — Vision con Haiku, 2752/2752 (100%)

**Resultado final:** 2311 importados, 738 duplicados, 5 sin sello/firma, 17 errores de Vision (JSON malformado con Haiku), 0 sin Excel. Precios backfilleados (ver bug arreglado arriba).

**Fix de robustez agregado:** `importar_puente.py` ahora reintenta automáticamente con `claude-opus-5` si Haiku falla en un PDF (progreso muestra `[haiku]`→`[opus]`). Los 17 que habían fallado se reprocesaron con `scripts/reprocesar_errores_vision.py` — los 17 quedaron importados. Total final: **3,480 facturas**.

**Archivos (mantener por si hay que reprocesar algo):**
- `data/puente_progreso.txt` — PDFs procesados
- `data/puente_errores_sello.txt` — rechazados por falta de sello/firma

---

## Notas técnicas para la próxima sesión

- Servidor: `cd C:\Users\axelo\vmo\conduces && python -m uvicorn main:app --reload`
- Si hay caché en el browser: Ctrl+Shift+R
- Si hay múltiples servidores en puerto 8000: `powershell -Command "Stop-Process -Name python -Force"`
- `python-multipart` ya instalado — requerido para file uploads
- Skill UI/UX Pro Max instalado en `.claude/skills/` — reiniciar Claude Code para activar
