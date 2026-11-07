# TODOS.md — proyecto conduces

> Items diferidos durante reviews, no bloquean el trabajo en curso.
> Formato: What / Why / Pros / Cons / Context / Depends on.

> **Estado al 2026-09-03: los tres items de este archivo estan cerrados.** Lo que
> queda vivo del proyecto vive en los issues de GitHub (`gh issue list --state
> open`), y hoy es **uno solo**: el #28, esperando a IT. El #34 y el #41, que
> esperaban a la oficina, se cerraron el 2026-09-03 **midiendo en vez de esperando
> la respuesta** — el detalle esta en `HANDOFF.md`. **No queda nada construible.**

---

## ✅ AUDITADO Y CERRADO 2026-08-28 — reportes/Estimaciones con el bug de Monto Pendiente

**What:** Revisar los reportes HTML (`reportes/`) y facturas (`facturas/`) ya generados antes del fix de Fase 1 (Hijo 3), para confirmar que ninguno se usó para una decisión de pago real con el número de "Monto Pendiente" incorrecto.

**Why:** `main.py:206` y `main.py:406` calculaban `monto_pendiente`/`monto_pagado` sumando solo `precio` (unitario) en vez de `precio × cantidad`. Cualquier reporte generado antes del fix de Fase 1 (Hijo 3) tiene ese número mal, salvo que `cantidad` fuera siempre 1 en los conduces de ese reporte.

**Pros:** Cierra cualquier duda sobre si una decisión de negocio pasada se basó en un número incorrecto.

**Cons:** Trabajo manual de revisar archivos históricos — no automatizable de forma confiable porque no todos los reportes cacheados tienen fecha de generación en el nombre.

**Context:** El usuario confirmó (2026-08-21) que el sistema todavía está en validación interna — no hay pagos reales ni Estimaciones reales entregadas al cliente CONFOTUR corriendo sobre este bug ahora mismo. Por eso se difiere en vez de auditar de inmediato.

**Depends on / blocked by:** Nada técnicamente — se puede hacer en cualquier momento. Recomendado antes de que el sistema pase a uso real con dinero/cliente real.

---

### Resultado de la auditoría (2026-08-28): **ningún archivo quedó con el número malo**

La premisa de "no automatizable de forma confiable" no se sostuvo: hay **5 archivos en total** (3 en `reportes/`, 2 en `facturas/`), todos generados el **21/08/2026 12:18-12:19**, y todos se pudieron verificar contra la BD.

**El fix se aplicó el 2026-08-21, no el 24.** El commit `132fd8c` tiene fecha del 24 porque se commiteó después; el log del proyecto registra el arreglo del bug financiero el 21. Los reportes se generaron ese mismo día **después** del fix.

**Prueba directa, no inferencia** — cada archivo muestra el valor de `precio × cantidad`, no el de `precio` solo:

| Archivo | Muestra | Habría mostrado con el bug |
|---|---|---|
| `reporte_general_todos.html` | **$63,861,990.71** | $2,456,897.51 |
| `reporte_general_2026-07-04_2026-07-18.html` | **$110,390.00** | $4,150.00 |
| `factura_CONSTRUCTORA_REBESA_SRL_...html` | **$853,746.30** | $34,030.00 |
| `reporte_general_2026-08-01_2026-08-20.html` | $0.00 | $0.00 (sin datos en el rango) |
| `factura_CONSORCIO_REMIX_SA_...html` | $0.00 | $0.00 (sin datos en el rango) |

Los tres archivos con datos coinciden **exacto** con el cálculo correcto. Que tres archivos independientes coincidan con la fórmula correcta y ninguno con la del bug es concluyente.

**Magnitud que tenía el bug, para dimensionar lo que se evitó:** subestimaba el Monto Pendiente **26 veces** ($2.46M en vez de $63.86M), y el **100% de los 3,523 conduces tiene `cantidad` distinta de 1**, así que habría afectado a todos los reportes sin excepción.

**No hay nada que rehacer.** El item queda cerrado.

---

## ✅ CERRADO 2026-08-31 — una compañía partida en dos por una coma

**What:** `CONSTRUCTORA REBESA SRL` (1,152 conduces, $16,321,710.04) y `CONSTRUCTORA REBESA, SRL` (75 conduces, $1,594,861.60) son **la misma empresa**, separadas solo por una coma. Son las únicas 2 variantes entre las 12 compañías de la BD.

**Why:** cualquier reporte o factura filtrada por un nombre **se pierde el otro**. La factura auditada arriba (`factura_CONSTRUCTORA_REBESA_SRL_2026-07-01_2026-07-23.html`) se generó para la variante **con** coma y totaliza $853,746.30.

> ⚠️ **CORREGIDO 2026-08-31 — los $15,703.60 estaban mal.** Esta seccion afirmaba que la variante sin coma tenia $15,703.60 mas en ese rango, y que eso era lo que la coma dejaba afuera. Esa cifra es **un solo conduce**, el `30619` (2026-07-02, GRAVILLLA, 830.0 x 18.92): la unica de 434 filas del rango que tiene precio. Las otras **433 no tienen precio** y por eso valen $0 -- no faltaban por la coma. Eso destapo un hueco de 1,632 conduces sin precio y ~$39.4 millones, fileado como issue #31. **El dano real de la coma no se puede medir hasta resolver el #31**, y va a ser bastante mayor.

> ✅ **RESUELTO.** Se unificaron bajo `CONSTRUCTORA REBESA SRL` (issue #24, cerrado).
> Verificado el 2026-09-02 contra `conduces/db/conduces.db`: hay **una sola variante**
> con 1.227 filas, no dos. El script es `scripts/unificar_compania_rebesa.py`, con
> `--check`/`--aplicar`, respaldo previo y 21 tests en `tests/test_unificar_rebesa.py`.
> El hueco de precios que esto destapó es el #31, tambien cerrado.

**Pros:** unificarlas cierra un agujero de subfacturación silencioso.

**Cons:** hay que decidir cuál es el nombre canónico y si se normaliza el dato en la BD o solo al agrupar. Tocar 75 filas de datos reales pide backup y confirmación.

**Context:** encontrado el 2026-08-28 auditando el bug de Monto Pendiente.

**De dónde sale la variante, investigado:** las 75 filas con coma están **todas** dentro del rango de `id_conduce` de 5 dígitos (30xxx), que es la **importación inicial del 2026-08-06** (documento fuente `archivos/2026-08-06 14-31.pdf`, Orden 53587, ~280 conduces de ARENA/GRAVA con precio 830.00 fijo). Ese mismo lote tiene **483 filas bajo el nombre SIN coma y 75 CON coma** — o sea que no son dos empresas ni dos fuentes distintas: es **una sola importación donde el nombre se tipeó de dos formas**.

Son **datos reales, no de prueba**: el precio y la cantidad del conduce `30376` se verificaron el 2026-08-19 contra el PDF original. Lo que sí es de prueba es la fecha faltante de esa fila puntual, ya anotado aparte en `AGENDA.md`.

**Matiz agregado el 2026-08-31:** el diagnostico de "una sola importacion tipeada de dos formas" no se sostiene del todo. Dentro del mismo bloque `30xxx` las dos variantes se separan limpio: las 75 de la coma traen precio y **no** traen almacen, y las 388 sin coma traen almacen y **386 de 388 no traen precio**. Parecen **dos documentos fuente distintos de la misma empresa**, no dos escrituras del mismo lote. No cambia la recomendacion -- siguen siendo la misma empresa y el canonico sigue siendo el sin coma -- pero conviene saberlo antes de tocar las filas.

**Verificado tambien el 2026-08-31:** no hay colision de `id_conduce` entre las dos variantes, asi que el `UPDATE` no puede chocar con la llave primaria; las 75 estan todas en `no_pagado`; y ningun script ni plantilla tiene el nombre hardcodeado (la unica referencia en tests es `tests/test_conduces.py:260`, que prueba `_slug_compania` como funcion pura y no depende de la BD).

**Recomendación:** el canónico es **`CONSTRUCTORA REBESA SRL`** (sin coma) — es el que usan las 1,152 filas, incluidas 483 del mismo lote viejo, y el que traen todas las importaciones posteriores. La coma aparece solo en 75 filas de un lote de agosto.

**Depends on / blocked by:** confirmación del usuario. Si acepta el canónico propuesto, es un `UPDATE` de 75 filas, con backup previo y un script idempotente con `--check`/`--aplicar` como el de los 370 m³.

---

## ✅ CERRADO 2026-09-02 — 101 facturas / 625 m³ con descripciones que no matchean ningún producto

> ✅ **RESUELTO** (issues #23 y #26, los dos cerrados). Lo que destrabó esto no fue
> conseguir el documento de junio: **el conduce trae impreso el código de producto**,
> en una columna `PRODUCTO` propia, y los PDFs estan en `conduces/archivos/Puente 1.zip`.
> Cruzandolo contra `Lista de precios.xlsx` las huerfanas se resuelven sin adivinar.
>
> El inventario real eran **6 descripciones / 103 facturas / 631,5 m³**, no 4 / 101 /
> 625: faltaban dos de MACAO 2. Cinco quedaron resueltas con alias, cada uno con el
> codigo del papel citado en el comentario:
>
> - 479 m³ EXTERIORES → codigo `44522` = $147 = **clave 9**. Eso cierra la disyuntiva
>   de los $5.269 que planteaba este item, a favor de la 9. Coincide ademas con el N17
>   real, que asigna 255 m³ a la clave 9 y cero a la 8.
> - 119 m³ EXTERIORES → codigo `4415` = $136 = **clave 8**
> - 20 m³ TRA → codigo `4477` = $186.98 = **clave 4**
> - 7 m³ CAVERNAS → codigo `44510` = $111 = **clave 2**. Es el caso que muestra por que
>   el codigo vale mas que el texto: la descripcion dice `rev. 8"` y el codigo es el
>   producto de `rev. 7"`. El texto libre estaba mal tipeado; el codigo estaba bien.
> - 1,5 m³ MACAO 2 → codigo `4419` = $154.02 = **clave 6**
>
> **La sexta no lleva alias, a proposito:** los 5 m³ de `M800013294` a $191.27 chocan
> contra dos renglones del catalogo con el mismo precio, y `_est_catalogo_norm_a_clave`
> devuelve `None` por colision deliberada. Un alias pisaria esa decision.
>
> El issue #40 propuso generalizar esto a un resolvedor por codigo. Se midio y **se
> cerro sin construir**: la descripcion ya resuelve 4.184 de 4.185 sola.

**What:** barrido completo de las 9 fases el 2026-08-28. Hay 4 descripciones huérfanas:

| Fase | Facturas | m³ | Fechas | Descripción |
|---|---|---|---|---|
| VMO/EXTERIORES | 75 | 479.0 | jun 2026 | `Hormigón 280 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1", imp` |
| VMO/EXTERIORES | 22 | 119.0 | jun 2026 | `Hormigón Fc280 kg/cm2, Agg 3/4", Temp. 32C, rev. 6"+/- 1"` |
| VMO/PATIO DE MANIOBRAS-TRA | 3 | 20.0 | 13-jul-2026 | `Hormigón 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Imp` |
| DOMICEM/CAVERNAS | 1 | 7.0 | 30-jun-2026 | `Hormigón 150 kg/cm2, Ag 3/4",T 35C, rev. 8" +/- 1"` (además **sin `precio_unitario`**) |

**Why:** hoy son **inertes**: las 4 son anteriores al `fecha_base` 2026-07-16, así que ya están dentro del acumulado sembrado, y desde el issue #17 el acumulado sale del libro mayor sin recorrer facturas viejas. Pero si alguna vez se genera un período que las incluya, salen como `sin_match` y hay que resolverlas a mano.

**Pros:** cerrar el hueco evita que aparezcan 625 m³ sin clasificar en una pantalla de revisión.

**Cons y por qué NO se resolvió de una vez:** **agregar un alias es decidir a qué renglón y a qué precio va la plata.** Es exactamente el mecanismo que produjo el error de los 370 m³ (una resolución manual que parecía obvia y estaba mal, $4,070 de más en un documento de CONFOTUR). Los 4 alias agregados el 2026-08-27 se verificaron **uno por uno contra el N44/N45 real de la empresa**, no por parecido de texto. Estas 4 no se pueden verificar así porque son de un período que la empresa ya facturó y del que no tenemos el documento a mano.

Candidatos, para cuando haya con qué verificar:

- `Fc280 ... rev. 6"` → **clave 8** de EXTERIORES (`Hormigón 280 kg/cm2, Ag 3/4",T 32C, rev. 6"+/- 1".`, $136). **Alta confianza**: es la misma descripción con otro formato (`Fc280` vs `280`, `Agg`/`Temp.` vs `Ag`/`T`).
- `280 ... rev. 7" ... imp` → ¿**clave 9** (`rev. Imp`, $147) o **clave 8** ($136)? La huérfana tiene rev. 7" **y** imp; la clave 9 tiene imp pero sin revenimiento. **$11/m³ de diferencia sobre 479 m³ = $5,269.**
- `350 ... Min. C: 300kg, rev. 6" ... Imp` → parecido a la **clave 4** de TRA, que difiere en el `Imp` final. Sin confirmar.
- `150 ... rev. 8"` → **clave 2** de CAVERNAS, por el mismo criterio con el que se aceptó el alias de `rev. 7"` (que sí se verificó contra el N44). Es el más defendible de los tres dudosos, y son 7 m³.

**Context:** encontrado el 2026-08-28 barriendo las 9 fases. Confirmado que **el período cerrado 2026-07-17 a 2026-08-16 no tiene ninguna huérfana** (`sin_resolver` = 0 en las 9 fases).

**Depends on / blocked by:** ~~conseguir el documento de la empresa del período correspondiente (junio 2026) para verificar contra él, o que X confirme a qué producto va cada una. Sin eso, agregar los alias es adivinar.~~ **Ya no aplica:** el código impreso en el papel es una fuente de verificación que no requiere ni el documento de la empresa ni a X.
