# Conduces VMO

Validación de conduces y generación de estimaciones para hormigonera.

Un **conduce** es el comprobante de entrega de agregados de un transportista o suplidor. El sistema los importa desde PDF, los valida (sello, firma, correspondencia con el Excel), y genera las estimaciones que se le entregan al cliente.

> [!TIP]
> **¿Recién llegás, o volvés después de un tiempo?** Empezá por [HANDOFF.md](HANDOFF.md) — estado actual, qué está bloqueado y por quién, y las trampas que te van a morder.

---

## Estado

> **Foto del 3 de septiembre de 2026, no un tablero en vivo.** GitHub no puede correr
> nada, así que esta tabla es un valor congelado y va a envejecer. Para los números de
> hoy, en un checkout: `python scripts/estado.py`.

| | |
|---|---|
| **Conduces en base** | 3 523 · 11 compañías |
| **Facturas** | 4 185 |
| **Fases cerradas** | 8 de 9 |
| **Período cerrado** | `2026-07-17` → `2026-08-16`, 10 529 m³ |
| **Pendientes por revisión** | 39, todas MACAO 2 por falta de sello |
| **Aprobados a mano** | 2, con rastro de quién y por qué |
| **Tests en `main`** | 626 al 3 de septiembre |

> [!NOTE]
> CANCHAS cerró con cero filas porque no tuvo entregas en el rango. Por eso son 8 fases y no 9.
>
> El módulo de **Conduces está en pausa** hasta limpiar los datos y definir los parámetros de almacén. Los conduces de junio y julio 2026 son datos de siembra, cargados para construir el sistema: no son operativos, y los hallazgos sobre ellos no representan plata en riesgo.

---

## Último cierre

**Se vació el backlog: diez issues cerrados entre el 2 y el 3 de septiembre**, y la suite pasó de 560 a 626 tests.

El que destrabó todo no fue código. **El conduce trae impreso el código de producto**, en una columna propia a la izquierda de la descripción. Cruzarlo contra `Lista de precios.xlsx` resuelve a qué renglón y a qué precio va un conduce **sin preguntarle a nadie** — y eso liquidó seis descripciones huérfanas que llevaban semanas trabadas esperando un documento del cliente que nunca llegó.

- [x] **[#23](https://github.com/lach06/VMO/issues/23) y [#26](https://github.com/lach06/VMO/issues/26)** — 5 alias verificados contra el código impreso, no por parecido de texto
- [x] **[#38](https://github.com/lach06/VMO/issues/38)** — el cierre ya no ignora `pendientes_revision`, y se agregó descartar/reponer para que el bloqueo tenga salida
- [x] **[#31](https://github.com/lach06/VMO/issues/31)** — el Monto Pendiente ahora declara sobre cuántos conduces está calculado
- [x] **[#37](https://github.com/lach06/VMO/issues/37)**, **[#39](https://github.com/lach06/VMO/issues/39)**, **[#48](https://github.com/lach06/VMO/issues/48)** — el `PARTIDA:` vacío, el re-precio de la hoja borrada, y Fase 1 del importador extrayendo los 11 campos
- [x] **[#34](https://github.com/lach06/VMO/issues/34) y [#41](https://github.com/lach06/VMO/issues/41)** — los dos que esperaban a la oficina, cerrados **midiendo** en vez de esperando
- [x] **[PR #52](https://github.com/lach06/VMO/pull/52) y [PR #53](https://github.com/lach06/VMO/pull/53)** — aviso antes de re-cerrar un período ya entregado, y el seed de las claves con cero explícito

> [!WARNING]
> **Lo más caro que se encontró.** `POST /api/estimaciones/cerrar` hace DELETE + INSERT por `numero_estimacion`, y las guardas de solapamiento y de hueco excluyen el propio número a propósito — así que re-cerrar el MISMO período devolvía una lista de avisos **vacía**. Medido contra la base real: un re-cierre del `2026-07-17 → 2026-08-16` de MACAO 2 metía 4,5 m³ de hormigón sin sello en un documento ya entregado, sin error y sin aviso. El PR #52 cerró esa puerta.

**El caso que muestra por qué el código vale más que el texto.** Un conduce de CAVERNAS decía `rev. 8"` en la descripción y traía el código `44510`, que es el producto de `rev. 7"`. El texto libre estaba mal tipeado; el código estaba bien. Ese mismo dato había inducido un issue entero ([#40](https://github.com/lach06/VMO/issues/40)) partiendo de una premisa falsa escrita en un comentario del código — se cerró sin construirlo, y el comentario se corrigió con los números medidos al lado.

---

## Pendiente

**Un solo issue abierto, y no pide construir.** Al 2026-09-14 no queda nada construible del lado del sistema: el #66 murió cuando llegó el PPACT de CAVERNAS (las nueve fases reconcilian) y el #72 se construyó ese mismo día (`obra_familia`, el mapa de obras confirmado a mano).

| | Qué |
|---|---|
| [#28](https://github.com/lach06/VMO/issues/28) | **Dónde va a vivir esto.** Servidor de oficina o VPS; HTTPS bloqueado detrás de esa decisión. Espera a IT, y arrastra un prerrequisito sin filear: el auth es un token compartido sin identidad de usuario, así que hoy no queda registro de quién hizo cada cosa. |

### Lo que espera a una persona, no a código

| | Qué |
|---|---|
| **Los 39 pendientes por revisión** | 260,5 m³ de MACAO 2 retenidos por falta de sello. El sistema los frena a propósito y no deja cerrar el período hasta que alguien decida: aprobarlos, descartarlos, o revisarlos uno por uno. No los pierde ni los cuenta a medias. |
| **Los precios de los suplidores** | Lo único que queda para X. Ni `Costo` ni `XCosto` sirven como están — se midió y quedó el criterio escrito en [HANDOFF.md](HANDOFF.md). No bloquea nada hasta que entre una carga real. |

> [!TIP]
> El correo a X se reescribió el 2026-09-03 y quedó en 7 preguntas más una hoja de 33 combinaciones de compañía y producto. **No está en `dropoff/`** — se armó en el scratchpad de la sesión, y no hay constancia de que se enviara. El anexo viejo con el detalle sigue en `dropoff/preguntas_para_X.md`.

---

<details>
<summary><b>Entregado</b> — 36 issues cerrados</summary>

### Generador de estimaciones

| | |
|---|---|
| [#6](https://github.com/lach06/VMO/issues/6) | Exportar la estimación a PDF |
| [#9](https://github.com/lach06/VMO/issues/9) | OC/Contrato fijo por fase |
| [#10](https://github.com/lach06/VMO/issues/10) | Separar Torres / Torre Grúa y arreglar la colisión de matching |
| [#11](https://github.com/lach06/VMO/issues/11) | Acumulado anterior en vivo |
| [#12](https://github.com/lach06/VMO/issues/12) | Contratos paralelos principal y PPACT |
| [#13](https://github.com/lach06/VMO/issues/13) | Sembrar el acumulado de las 8 fases restantes |
| [#14](https://github.com/lach06/VMO/issues/14) | Arreglar las fases solo-PPACT que sembraban en la columna equivocada |
| [#16](https://github.com/lach06/VMO/issues/16) | Reparto principal/PPACT por lote |
| [#17](https://github.com/lach06/VMO/issues/17) | Libro mayor de estimaciones cerradas, con botón Cerrar |
| [#18](https://github.com/lach06/VMO/issues/18) | Paginar las hojas RGO en bloques de 40 folios |
| [#25](https://github.com/lach06/VMO/issues/25) | Aviso pasivo de resoluciones manuales desalineadas |
| [#33](https://github.com/lach06/VMO/issues/33) | Las hojas RGO volvieron a salir firmadas en las 9 fases |
| [#35](https://github.com/lach06/VMO/issues/35) | El contratista de las RGO sale por empresa, no cableado |
| [#36](https://github.com/lach06/VMO/issues/36) | Una `clave_resuelta` obsoleta ya no tapa el auto-match |
| [#27](https://github.com/lach06/VMO/issues/27) | Hojas RCO (croquis) y RFO (reporte fotográfico) — completa el juego que se entrega |
| [#23](https://github.com/lach06/VMO/issues/23) | 5 alias verificados contra el código de producto impreso en el conduce |
| [#26](https://github.com/lach06/VMO/issues/26) | La variante `rev. 8"` de CAVERNAS, resuelta por su código y no por el texto |
| [#37](https://github.com/lach06/VMO/issues/37) | El `PARTIDA:` (A15) sale vacío, como en los documentos del cliente |
| [#38](https://github.com/lach06/VMO/issues/38) | El cierre se niega si quedan pendientes del período, y se puede descartar/reponer |

### Validación de documentos

| | |
|---|---|
| [#7](https://github.com/lach06/VMO/issues/7) | Sello obligatorio en MACAO 2 |
| [#8](https://github.com/lach06/VMO/issues/8) | Firma obligatoria en el resto de las fases |
| [#15](https://github.com/lach06/VMO/issues/15) | El Excel como fuente de verdad de la descripción |
| [#20](https://github.com/lach06/VMO/issues/20) | Aprobación manual de conduces sin sello o firma, con reversa auditada |
| [#22](https://github.com/lach06/VMO/issues/22) | Decidido: los 2 conduces sin sello se aprueban a mano |
| [#48](https://github.com/lach06/VMO/issues/48) | Fase 1 del importador extrae los 11 campos igual que Fase 2 |
| [#40](https://github.com/lach06/VMO/issues/40) | Resolver el producto por su código — cerrado **sin construir**: partía de una premisa falsa escrita en un comentario del código |

### Módulo Conduces

| | |
|---|---|
| [#31](https://github.com/lach06/VMO/issues/31) | El Monto Pendiente declara sobre cuántos conduces está calculado (1 632 de 3 523 sin precio) |
| [#39](https://github.com/lach06/VMO/issues/39) | Re-precio de las 40 facturas que cargaron el precio de una hoja de la lista que ya no existe |
| [#34](https://github.com/lach06/VMO/issues/34) | `Costo` o `XCosto` — cerrado midiendo: ninguna de las dos sirve, y quedó el criterio para la próxima carga real |
| [#41](https://github.com/lach06/VMO/issues/41) | El ITBIS de BISONO y A. ALBA — siete casos caen con el factor 1,18 y uno no |

### Base del proyecto

| | |
|---|---|
| [#2](https://github.com/lach06/VMO/issues/2) | Fase 2: cobertura y reproducibilidad |
| [#3](https://github.com/lach06/VMO/issues/3) | Tests de las 9 rutas de conduces |
| [#4](https://github.com/lach06/VMO/issues/4) | Separar `main.py` en routers por dominio |
| [#5](https://github.com/lach06/VMO/issues/5) | Bootstrap reproducible de ambas bases |
| [#19](https://github.com/lach06/VMO/issues/19) | Unificar `importar_puente.py` con el core |
| [#24](https://github.com/lach06/VMO/issues/24) | Unificar las dos escrituras de CONSTRUCTORA REBESA, con reversa por respaldo |

</details>

---

## Cómo correr

```bash
python -m uvicorn main:app
```

Después, `http://127.0.0.1:8000`.

> [!IMPORTANT]
> **No uses `--reload`.** En Windows no es confiable y ya causó una investigación de un bug inexistente. Reiniciá el servidor a mano después de cualquier cambio de backend.

Antes de cualquier operación que escriba en la base:

```bash
python scripts/backup_db.py
```

Respalda las dos bases y la carpeta de memoria del proyecto — `log.md`, `MEMORY.md` y el resto del historial de decisiones, que vive fuera del repo y no la versiona git — a `backups/db/` y a Google Drive.

## Estructura

Reorganizada el **1 de septiembre de 2026**. La raíz es **VMO**: adentro va `dropoff/` y todo
lo que los dos módulos usan en conjunto, y después una carpeta por módulo con sus datos.

```
VMO/
├─ dropoff/  backups/  documentos/  docs/  presentacion/  misc/   ← compartido
├─ core.py  main.py  routes_*.py  scripts/  tests/  static/       ← código, compartido
├─ conduces/      → db/  data/  archivos/  reportes/  facturas/  fallos/
└─ estimaciones/  → db/  data/  archivos/  reportes/  facturas/
```

> [!IMPORTANT]
> **El código no se parte por módulo, y es a propósito.** `core.py` lo usan los dos, y los
> ~22 scripts calculan su `BASE_DIR` como `parent.parent` de su propio archivo: moverlos
> dentro de una carpeta de módulo les cambia la raíz **sin lanzar ningún error**, y quedan
> leyendo y escribiendo donde no es.

Las rutas de datos son constantes en `core.py` (líneas 52-64 y 114-115). Los tests **no
tocan ninguna carpeta de datos** — arman los Excel en memoria — así que verlos en verde no
prueba que las rutas estén bien: eso se verifica levantando el servidor.

---

## Reglas críticas de negocio

- El **ID real del conduce** es la llave primaria, nunca el número aleatorio del sistema interno.
- Estados: solo `pagado` / `no_pagado`. Plazo de pago: 30 días.
- Nunca se consulta un conduce que no esté en la base.
- **Sello y firma son fase-condicionales**: MACAO 2 exige sello, cualquier otra fase exige firma ([#7](https://github.com/lach06/VMO/issues/7), [#8](https://github.com/lach06/VMO/issues/8)).
- El **Excel de conduces es la fuente de verdad** de la descripción y la fase ([#15](https://github.com/lach06/VMO/issues/15)).
- Una factura anterior al **corte de conteo** de su fase no se recalcula: ya está contada en el libro mayor ([#17](https://github.com/lach06/VMO/issues/17)).

## Estructura

| Archivo | Qué hace |
|---|---|
| `core.py` | Lógica de negocio: Vision, matching, clasificación de series, generación de documentos |
| `main.py` | Arranque de la app y montaje de routers |
| `routes_conduces.py` | Endpoints del módulo de conduces |
| `routes_estimaciones.py` | Endpoints del generador de estimaciones |
| `static/index.html` | Frontend completo |
| `scripts/` | Importación, backups y correcciones de datos puntuales |
| `tests/` | Suite de pytest |
| `estimaciones/` | Base, plantillas por fase y PDF de facturas |

> [!CAUTION]
> `.env` tiene la API key y nunca se comparte ni se sube. `estimaciones/db/` y `estimaciones/facturas/` están en `.gitignore` a propósito: son datos reales.

## Flujo de trabajo

Para cualquier feature no trivial: **spec → issue → worktree → agente en background → verificación independiente → PR**.

Al agente que construye siempre se le pide que **denuncie los errores del spec** en vez de improvisar en silencio. Va 5 de 5: en los issues #16, #17, #18, #19 y #20 el spec tenía un error real y el agente lo encontró. Tres habrían llegado a producción.

La verificación termina **mirándolo en pantalla**, no cuando los tests pasan. En el #20 la suite estaba 369 en verde y aun así el botón de aprobar mostraba un spinner que decía "estoy procesando" cuando en realidad decía "te faltan campos". Un test no puede fallar por eso.
