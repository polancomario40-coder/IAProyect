# HANDOFF

Para quien retome este proyecto: el mismo usuario después de un tiempo, otra
persona, o una sesión nueva que arranca sin contexto.

**Arrancá corriendo `python scripts/estado.py`**, y cerrá con
`python scripts/cierre.py` — el protocolo completo está en `CLAUDE.md`. Todo lo que es
un número vive en el primero, calculado en el momento. Este documento guarda lo que un script no puede deducir —
por qué se decidió algo y qué trampas cuestan caro— así que no lleva fecha de
actualización arriba: envejece por partes, y cada afirmación con fecha la lleva
escrita al lado.

---

## Qué es esto

Un sistema interno de VMO (hormigonera) con **tres módulos** (los dos primeros
comparten código; el tercero es autocontenido):

- **Conduces** — valida comprobantes de entrega de agregados de transportistas.
  **Hoy está en pausa** hasta limpiar los datos y definir parámetros de almacén.
- **Estimaciones** — genera el documento formal que se le entrega al cliente
  (proyecto Moon Palace, CONFOTUR) desglosando el hormigón entregado. **Este es
  el módulo activo**, y donde está toda la plata.
- **Logística** — dashboard de cumplimiento de despacho (2026-09-29), 100%
  cliente y sin base de datos: cruza la programación del día contra el cargue
  real. Cubre todo el despacho de VMO, no solo Moon Palace — ver su sección en
  `CLAUDE.md`.

Una **estimación** es un Excel de varias hojas que reemplaza un trabajo que
antes se hacía a mano cada mes, por cada una de las 9 fases del proyecto.

---

## Estado

```bash
python scripts/estado.py
```

Eso imprime la punta de `main`, el último commit que cambió comportamiento, si el
árbol está limpio, las filas de las dos bases, el libro mayor, el último período
cerrado, los issues abiertos y cuántos tests hay. **Tarda unos segundos y siempre
dice la verdad.**

**Acá no hay una tabla con esos números, y es a propósito.** Los tenía —diez, escritos
a mano— y para el 2026-09-04 varios ya eran falsos en tres archivos distintos a la vez:
`AGENDA.md` decía 483 tests cuando eran 626, y una punta de `main` de tres días antes.
El problema no era que nadie los actualizara: es que **un número derivable escrito a
mano tiene fecha de vencimiento el día que se escribe**. El PR #55 ya había arreglado
uno de esos campos dos veces seguidas antes de aceptar que la solución era no
escribirlo.

La regla que queda: **si un dato se puede calcular, no se escribe acá.** Lo que sí vive
en este documento es lo que ningún script puede deducir — por qué se decidió algo, y las
trampas de más abajo.

Lo que el script no puede saber, y conviene tener presente: el documento que se
entrega ya sale completo: carátula, resumen, generadores
(RGO), croquis de ubicación (RCO) y reporte fotográfico (RFO). **Lo único
manual que queda es pegar las fotos en las hojas RFO.**

Desde el 2026-09-04 el PDF además **trae anexado el escaneo de cada conduce**, una
página por conduce detrás de las hojas, como el documento del cliente. Son dos cosas
distintas y conviene no confundirlas: **las hojas RFO siguen pidiendo las fotos a
mano**; lo que se automatizó es el respaldo escaneado de cada conduce. Ver la trampa
"El PDF entregable sale con páginas de aviso donde falta el escaneo".

---

## Lo que está bloqueado, y por quién

**Al 2026-09-14 queda uno**, y no es urgente:

| Issue | Espera a | Qué decide |
|---|---|---|
| [#28](https://github.com/lach06/VMO/issues/28) | **IT** | Dónde se despliega esto, y HTTPS detrás de eso — espera desde el 2026-09-03 |

Los otros dos que este cuadro tenía al 2026-09-07 se cerraron: el **#67** se
construyó ese mismo día (columna `obra_papel`), y el **#66** murió el 2026-09-14
cuando apareció el PPACT de CAVERNAS — ver la trampa del PPACT, que ahora cuenta
cómo terminó. Ese día también se cerró el **#72**: `obra_familia`, la lectura
agrupada de `obra_papel`, con el mapa de equivalencias confirmado a mano (las
decisiones y su evidencia están en el issue).

Arrastra un prerrequisito sin filear: el auth es un token compartido, sin identidad
de usuario, así que hoy no queda registro de quién hizo cada cosa.

Cerrados el **2026-09-02**, todo mergeado a `main`: **#23**, **#26**, **#31**, **#37**,
**#38**, **#39**, **#40** y **#48**. Cuatro de ellos se filearon y se cerraron el
mismo día. El **#40** se cerró sin construirlo: se midió y la cobertura incremental
del código de producto es de 0 facturas sobre 4.185.

Cerrados el **2026-09-03**: **#34** y **#41**, los dos que esperaban a la oficina.
**Se cerraron midiendo, no esperando la respuesta** — ver "Los dos que esperaban a la
oficina se resolvieron midiendo" más abajo. Ese mismo día entraron dos arreglos que no
tenían issue: el aviso de re-cierre ([PR #52](https://github.com/lach06/VMO/pull/52)) y
el seed de las claves con cero explícito ([PR #53](https://github.com/lach06/VMO/pull/53)).

**Hasta el 2026-09-06 no quedaba nada construible.** El #67 lo cambia: es trabajo
interno, no espera a nadie. El #66 es pedir un archivo, no construir.

<details>
<summary>Cómo se veía este cuadro el 2026-09-01, cuando los seis estaban trabados</summary>

| Issue | Espera a | Qué decide |
|---|---|---|
| [#23](https://github.com/lach06/VMO/issues/23) | **X** | A qué renglón van 625 m³ sin asignar |
| [#26](https://github.com/lach06/VMO/issues/26) | **X** | Un CAVERNAS con revenimiento 8" sin precio |
| [#34](https://github.com/lach06/VMO/issues/34) | **X** | `Costo` o `XCosto` en el reporte de conduces |
| [#37](https://github.com/lach06/VMO/issues/37) | decisión interna | Qué criterio usa el `PARTIDA:` (A15) |
| [#31](https://github.com/lach06/VMO/issues/31) | decisión interna | Depende de la respuesta del #34 |
| [#28](https://github.com/lach06/VMO/issues/28) | **IT** | Dónde se despliega esto, y HTTPS detrás de eso |

### El próximo movimiento es un correo, no código

`dropoff/mail_para_X.md` está redactado y **sin enviar**. Tiene dos preguntas
reales y cuatro confirmaciones. Cierra el #23 y el #26, y la parte de conduces
cierra el #34 y destraba el #31.

**Cuatro de los seis issues se destraban con ese correo.** Mientras no salga, el
proyecto no avanza por más código que se escriba.

</details>

### El dato que destrabó el backlog

**El conduce trae impreso el código de producto**, en una columna `PRODUCTO` propia a
la izquierda de la descripción. Los PDFs escaneados están en
`conduces/archivos/Puente 1.zip`. Cruzándolo contra `Lista de precios.xlsx` se
resuelve a qué renglón y a qué precio va un conduce **sin preguntarle a nadie**.

Con eso, la Parte A del correo a X —seis preguntas sobre a qué renglón va la plata—
quedó contestada con evidencia del papel, no por parecido de texto. El caso que lo
demuestra: `M800013172` dice `rev. 8"` en la descripción y trae el código `44510`,
que es el producto de `rev. 7"`. El texto libre estaba mal tipeado y el código estaba
bien.

**El correo a X está archivado y no queda nada que enviar.** La Parte A murió el
2026-09-03 con el código de producto impreso; de las 7 preguntas de la Parte B, **4 se
contestaron midiendo** ese mismo día (#34 y #41). Sobreviven tres —si existe una lista
de precios pactados, confirmar los 22 precios derivados, y la anomalía de A. ALBA /
ARENA GRIS— y **ninguna bloquea nada**: solo importan cuando entre una carga real de
esas compañías. El archivo `documentos/mail_para_X_2026-09-03.md` abre con el detalle
de cuál murió y cuál no. Si ese momento llega, se rearma con esas tres; no se reenvían
las siete.

### Los dos que esperaban a la oficina se resolvieron midiendo

El **#34** preguntaba si guardar `Costo` o `XCosto`. La respuesta medida sobre las 6.930
filas de `conduces/data/Entrada y Salida de un Producto.xls` es que **ninguna de las dos
sirve como está**. Agrupando por compañía + producto + mes, `XCosto` —lo que el sistema
guarda hoy— da entre 29 y 213 precios distintos por grupo: REBESA sola aparece con 213
valores para ARENA CALIZA en un solo mes, así que no es un precio. En **julio**
`Costo / Entradas` sí da precios reales, redondos y distintos por compañía (REBESA $830,
TRANSMELSA $900, MARMOTECH $960, TAVERAS $1.000, TROBEL $800). En **junio** no: el mismo
valor al centavo se repite entre empresas —$1.203,90 en seis compañías distintas— o sea
que ahí las dos columnas son valoración de inventario. Cobertura de precio real en junio:
33 de 1.848 conduces (1,8%).

**El criterio para la próxima carga real**, que es lo único que sobrevive del issue:

1. No guardar `XCosto` en `precio`. Nunca es un precio.
2. Usar `Costo / Entradas` solo cuando el grupo pasa el control de valoración.
3. El control: si el mismo valor al centavo aparece en dos compañías distintas, o si un
   grupo compañía+producto+mes tiene más de unos pocos valores, es valoración — rechazarla.
4. Sin precio confiable, la fila entra **sin precio y avisando**, no en $0 en silencio
   (eso último ya lo arregló el #31).

El **#41** preguntaba si BISONO y A. ALBA se registran sin ITBIS. De las 22 combinaciones
con precio derivable de julio, las siete que no dan redondo son **todas de esas dos
compañías y se vuelven redondas con el mismo factor 1,18**. La excepción que no encaja es
**A. ALBA / ARENA GRIS, $1.303,38 en 226 conduces**, que da $1.537,99: casi redondo pero
no múltiplo de 5, cuando las otras siete caen en múltiplos de 5 o de 10. Queda una
pregunta de una línea para cuando entre una carga real de esas dos compañías.

---

## Cómo correr las cosas

```bash
cd C:\Users\axelo\VMO\conduces
python scripts/estado.py            # EMPEZAR POR ACA: el estado, calculado ahora
python scripts/secuencia.py         # que falta: escaneos contra las bases, por secuencia
python scripts/backfill_obra_papel.py --dry-run   # que filas no tienen la obra del papel
python -m uvicorn main:app          # servidor, luego http://127.0.0.1:8000
python -m pytest tests/ -v          # la suite (cuantos son lo dice estado.py)
python scripts/backup_db.py         # antes de cualquier escritura en BD
```

**No uses `--reload`.** En Windows no es confiable y ya costó una investigación
de un bug que no existía. Reiniciá a mano después de cualquier cambio de backend.

Un test compara contra los 15 documentos del cliente, que **no están versionados**
(768 MB). En **este checkout no hace falta hacer nada**: los documentos están en su ruta
por defecto (`estimaciones/data/plantillas_por_fase/`) y la suite corre entera, **sin un
solo skip**, en poco menos de 4 minutos.

Donde sí hace falta es en un **worktree o un clone limpio**, que no los tiene: ahí ese
test **se saltea solo**, y la suite termina con un skip y un test menos. Para
ejercerlo, apuntá la variable a la copia principal:

```bash
EST_FUENTES_DIR=/c/Users/axelo/VMO/conduces/estimaciones/data/plantillas_por_fase \
  python -m pytest tests/ -q
```

**Ese skip en un worktree no es un problema.** Es honesto y dice por qué se salteó.

---

## Trampas que te van a morder

Están ordenadas por cuánto cuestan si las descubrís tarde.

### NO re-cierres el 2026-07-17 → 2026-08-16 de MACAO 2

El libro mayor tiene **2.028,0 m³** en la clave 6 de esa estimación, que es lo que se
entregó. Si hoy se corriera la clasificación sobre ese mismo período daría **2.032,5**.

La diferencia son los 4,5 m³ de `M800013968` (3,0) y `M800014137` (1,5): dos conduces
sin sello que se aprobaron a mano el 2026-08-31, tres días **después** del cierre del
2026-08-28. El sistema los había bloqueado bien; el documento manual que los incluía
era el equivocado.

`POST /api/estimaciones/cerrar` hace **DELETE + INSERT** por `numero_estimacion`, así
que un re-cierre reescribiría ese 2.028,0 con 2.032,5 y metería hormigón sin sello en
un documento ya entregado.

**Hasta el 2026-09-03 eso pasaba sin error y sin aviso.** El bloqueo del issue #38 mira
`pendientes_revision` y estos dos ya no están ahí, están en `facturas`; y las guardas de
solapamiento y de hueco excluyen el propio `numero_estimacion` a propósito, así que
re-cerrar el MISMO número devolvía una lista de avisos vacía. El
[PR #52](https://github.com/lach06/VMO/pull/52) cerró esa puerta: ahora sale un aviso
`re_cierre` que va **primero** en la lista, con el rango, cuándo se cerró, y cuántas
filas y cuánta cantidad se van a reemplazar.

**El aviso no es un bloqueo**: como los otros, se puede pasar con `confirmar_aviso`. Es
una confirmación a propósito, no una pared, así que esta trampa sigue acá.

**Re-cerrar el mismo período con OTRO número sí está bloqueado** desde el
[issue #96](https://github.com/lach06/VMO/issues/96): no pisa al anterior, se
suma, y cada día en común se contaba dos veces en el acumulado. Pasó el
2026-10-05 en CAVERNAS, MACAO 2 y CEDIS. Para corregir un número: `/reabrir`
el viejo y cerrar con el nuevo. `cierre.py` falla si el libro mayor tiene
días cerrados con dos números.

Hacia adelante no hay riesgo: las dos fechas (21 y 24 de julio) quedan detrás del
corte del 16 de agosto, así que `_est_calcular_acumulados()` las saltea y no entran en
ninguna estimación futura. El único camino por el que reaparecen es re-cerrar ese
período puntual.

Si alguna vez hace falta re-cerrarlo, primero hay que decidir qué pasa con esos 4,5 m³
— no descubrirlo después de mandar el documento.

### El PPACT se factura en un documento aparte — no leas un faltante como plata sin mirar la serie

Cuando una clave llena su **tope contratado** —`cantidad_proyecto_principal` en
`estimacion_acumulado_base`— lo que se sigue entregando no desaparece: pasa a la
serie **`ppact`**, y el cliente la factura en un **documento separado**. En las
fases que lo tienen se ve directo: el PPACT de MACAO 2 trae **111 conduces que el
documento principal no tiene**, y el de CEDIS los 81 suyos.

Hasta el 2026-09-14 faltaba el PPACT de CAVERNAS —la única fase con m³ en
`ppact` sin su documento— y por eso esa fase no reconciliaba: 74 folios de 89.
**Ese día apareció** (`EST_DOMICEM_CIUDAD_PALACE_CAVERNAS_EXTERIORES_PPACT_N06_23072026_V01.xlsx`,
en `DOMICEM/`) **y confirmó el cuadro número por número**: trae exactamente los
15 folios que faltaban, todos en `facturas` (89 de 89), 65,0 m³ de la clave 8 y
35,0 de la clave 11, con acumulados **212** y **105** — idénticos a lo sembrado
en `ppact` — y un importe de estimación de **$15.969,30**, el monto exacto que el
falso hallazgo leía como "sin facturar". Con eso las nueve fases reconcilian y
la carpeta tiene los ocho PPACT que existen (CANCHAS no tiene m³ en `ppact`).

**Ya generó un falso hallazgo, y vale como advertencia.** El 2026-09-07 se cruzaron
los folios de los 15 documentos contra `facturas`: ocho de las nueve fases dieron
100% dentro del período que cada documento declara, y CAVERNAS dio 74 de 89. Los 15
que faltaban —100 m³, $15.969,30— parecían dos productos que el cliente nunca
facturaba. No lo eran:

- Los 10 de $145,00 son la **clave 8** del catálogo del cliente: `Hormigón 280
  kg/cm2, Ag 3/4", T 35C, rev. 6" +/- 1", imp.` Su principal está en **1.795,0 de
  1.795,0 — lleno** — y ya tiene 212,0 sembrados en `ppact`.
- Los 5 de $186,98 son la **clave 11**: `Hormigón 350kg/cm2, AMB IIIA (EHE)...`
  Principal 2.688,0 de 2.694,0, con 105,0 en `ppact`.

O sea que los dos productos **están en el catálogo del cliente con ese precio
exacto**, y sus 100 m³ ya están contados en el acumulado base, que salió de los
documentos del cliente incluido el PPACT que no tenemos.

**El detalle que engaña:** la clave 8 (`... rev. 6" +/- 1", imp.`, $145) y la clave
10 (`... rev. 6" +/- 1".`, $133) son **hormigones distintos con descripciones casi
idénticas** — la diferencia es `imp.`, impermeabilizado. Ver una a $133 facturada y
la otra a $145 no, y leerlo como una anomalía, es el error que se cometió.

**Y los "21 m³ vivos sobre el corte" tampoco existían:** los 3 conduces del
2026-07-18 ya se cerraron el 2026-08-28 como clave 8 / `ppact` / 21,0 m³ del
período 2026-07-17 → 2026-08-16. El sistema los clasificó bien solo.

La regla que sale de todo esto: **antes de leer un faltante de reconciliación como
plata, mirá si la clave tiene `ppact`.** Si lo tiene, el conduce puede estar
facturado en un documento que no está en la carpeta — hoy están los ocho, pero un
PPACT nuevo del cliente vuelve a abrir esa ventana hasta que su archivo llegue.

### Un escaneo rotado 180° entra con datos ERRÓNEOS, no vacíos

Hay escaneos dados vuelta —el `HANDOFF` ya lo decía— pero lo que no estaba
escrito es qué le hacen a la extracción, y es lo contrario de lo que uno
supone. **Vision no falla con ellos: devuelve un documento completo y
equivocado.**

Medido el 2026-09-07 sobre `06-17-M7-18862.pdf`, el mismo archivo con y sin
rotar:

| campo | sin rotar | rotado | lo que dice el papel |
|---|---|---|---|
| `id_documento` | `M7018882` | `M700018862` | M700018862 |
| `cantidad` | **11.0** | **7.0** | 7,00 |
| `descripcion` | `Hormigón 282 mm/cm² por/kg 1.2 + 0.75 diam` | la correcta | — |
| `tiene_sello` / `tiene_firma` | true / true | true / true | — |

**Cuatro m³ inventados en un solo conduce**, y con sello y firma afirmados el
documento tampoco caía en `pendientes_revision`. Un "no pude leerlo" sería
seguro; esto no lo es.

**La orientación no se puede deducir del archivo.** En los cuatro rotados que
aparecieron `page.rotation` vale **0** — la vuelta está en la imagen, no en el
metadato — y estos PDFs no tienen capa de texto. Ningún chequeo local la ve.

**Y el id no sirve de alarma**, aunque lo parezca: el nombre del PDF trae el
número y Vision devuelve el suyo, así que una discrepancia suena a detector
gratis. Medido sobre 11 documentos sanos, **6 ya traen el id distinto** por
confusiones de OCR (`MS00012229` por `M800012229`, `M7000188815` por
`M700018815`). Como detector daría más falsos positivos que aciertos.

Lo que quedó, desde el [PR #74](https://github.com/lach06/VMO/pull/74): se le
pregunta al modelo en el mismo prompt (campo `al_reves`, 8 de 8 en la
medición) y, si dice que sí, se relee con la página rotada. No cuesta ninguna
llamada extra en el caso normal. Aplica a `_procesar_pdf_sync()` y a
`_extraer_obra_papel()`.

**Ojo, que «la orientación no se ve en el archivo» vale solo para el 180°.**
Medido el 2026-10-05 sobre los ~6.100 conduces de los cuatro zips y
`procesadas/`: **118 traen `/Rotate` en 90°, 180° o 270°** con la imagen
vertical adentro, y los 118 se ven derechos —el escáner ya los enderezó— y
Vision los lee bien (los 118 tienen `obra_papel` correcto). O sea que el
metadato sí se respeta; lo que no hay es metadato en los 4 dados vuelta.
Cualquier chequeo que mire la **imagen embebida** en vez de `page.rect`
marcaría a esos 118 como rotados, y no lo están.

**90° y 270°: no apareció ninguno, y si aparece se ve gratis.** El conduce
es un papel apaisado, así que un contenido girado 90° o 270° **se ve
vertical**, y eso es geometría, no Vision. Desde la rama
`escaneo-vertical-a-revision`, una página que se ve vertical va a
`pendientes_revision` con motivo `escaneo vertical`, en los dos caminos
(`_motivo_sello_firma()` y `decidir_macao2()`/`decidir_no_macao2()` del
masivo). Va **último**: solo cambia algo cuando el documento iba a entrar.
Es aprobable a mano porque el único vertical que existe hoy, `M800015683`,
es un escaneo atascado pero derecho — **quien lo apruebe tiene que comparar
la cantidad contra el papel**, porque por el camino individual sale de Vision.

**El import masivo pregunta `al_reves` desde la rama `al-reves-en-el-masivo`.**
Hasta ahí `vision_extract()` de `importar_puente.py` no lo preguntaba, y los 4
dados vuelta conocidos entraron por ese camino con sello, firma y
`obra_papel` leídos de cabeza (la cantidad y el número no: salen del Excel).

**El doble-chequeo de sello/firma tiene que mirar el PDF enderezado.** Es una
segunda llamada con su propio PDF, así que corregir solo la primera lectura
no alcanza: la segunda opinión vuelve a leer de cabeza y es la que manda.
Por eso las dos lecturas devuelven `_rotado` y los dos caminos le pasan
`_rotar_pdf()` al doble-chequeo cuando viene en true. **El escaneo que se
guarda en disco sigue siendo el original**, sin rotar.

### La misma lectura de Vision no siempre da lo mismo

Sobre un campo difícil, dos llamadas al mismo PDF pueden devolver cosas
distintas. `M700018862` dio `EXTERIORES1111`, `EXTERIORES 1141` y
`EXTERIORES$111` en tres corridas del 2026-09-07 — el `$` es un `1` mal leído.

No es un defecto de un arreglo puntual: es **cómo se comporta la extracción**,
y explica dos cosas que se ven en los datos. Que `obra_papel` tenga 133 valores
distintos con familias que son la misma obra escrita de varias formas (issue
#72). Y que el fallo de parseo del issue #69 fuera aleatorio por llamada y no
propiedad del documento.

La regla que sale: **antes de tratar una diferencia entre dos lecturas como un
hallazgo, repetila.** Si no se repite, era ruido de la extracción, no un dato.

### Una clave sin fila de acumulado base sale del documento en blanco

`_est_clasificar_series()` tiene un camino degradado: si una clave no tiene fila en
`estimacion_acumulado_base`, la clasifica igual pero con `calculado` en `None`, y esa
línea sale del documento **sin acumulado anterior**. No falla nada y no avisa nadie.

Pasó con DOMICEM/VIVIENDAS hasta el 2026-09-03: el seed solo cargaba las 2 claves con
acumulado distinto de cero, y las otras 7 quedaban sin fila. No estaban ausentes del
documento del jefe — **traen `N = 0` escrito**. Corregido en el
[PR #53](https://github.com/lach06/VMO/pull/53).

La regla que sale de ahí: **una celda vacía y un cero escrito se siembran los dos como
0.** El cero escrito es evidencia más fuerte que la celda vacía, no menos.

### Los escaneos de los lotes viejos dependen de que el espejo siga corriendo

El PDF de la estimación anexa el escaneo de cada conduce, una página por conduce, y el
mapeo sale de `facturas.archivo_pdf`. La cobertura no se escribe acá porque es derivable:
la dice `python scripts/secuencia.py`.

`importar_puente.py` guarda el PDF en `estimaciones/facturas/procesadas/` al importar
desde el 2026-08-24, así que **todo lote posterior deja su propio respaldo**. Los dos
anteriores no: para los 3.490 de `Puente 1.zip` y los 743 de `Puente 2.zip`,
`conduces/archivos/` es la única copia en esta máquina, y ese directorio está en
`.gitignore`. Lo que los cubre es el espejo a Drive que corre en `backup_db.py`
(`<GDRIVE_BACKUP_DIR>/escaneos/`, sin rotar nunca). **Si alguien desconfigura
`GDRIVE_BACKUP_DIR`, esos 4.233 escaneos vuelven a estar en un solo lugar** — el script
avisa, pero avisa, no bloquea.

**Cuando entra un lote nuevo:** va a `conduces/archivos/` como `.zip`, o suelto en
`conduces/archivos/escaneos/`. Entra solo al índice, sin tocar código ni reimportar.
**No borres la carpeta fuente después** — el 2026-08-24 se borró `Puente 2.zip` recién
importado y 743 conduces quedaron sin imagen hasta el 2026-09-04, que aparecieron de
casualidad.

Si a un conduce le falta el escaneo, el PDF **no lo saltea en silencio**: deja una
página `ESCANEO NO DISPONIBLE` con su número. Un documento con esas páginas **no es
entregable**: son un pedido de escaneos, no un defecto del generador.

### `secuencia.py` y el generador miran fuentes distintas, así que uno puede dar verde mientras el otro deja huecos

Los dos reconcilian escaneos, y es fácil leerlos como si fueran el mismo control.
No lo son: **`secuencia.py` reconcilia por número de conduce y el generador mapea
por nombre de archivo.** Un escaneo puede estar presente para uno y ausente para
el otro.

Eso ya costó: el 2026-09-25 el principal de MACAO 2 salió con 29 páginas
`ESCANEO NO DISPONIBLE` y su PPACT con otras 29 distintas, **con los 58 archivos
existiendo** en `estimaciones/facturas/procesadas/`. `secuencia.py` no avisó nada
porque esa carpeta sí estaba en su índice; la que no la miraba era
`core._est_indice_escaneos()`. Se tapó copiando los 58 a
`conduces/archivos/escaneos/`, que no es el arreglo sino el punto de extensión
usado como parche.

Cerrado por el [issue #81](https://github.com/lach06/VMO/issues/81): el índice
del generador toma ahora las tres fuentes, con precedencia **zip → `procesadas/`
→ suelto**. El zip le gana a `procesadas/` a propósito —los bytes son los mismos,
`importar_puente.py` escribe el `zf.read()` tal cual— así que `procesadas/` sólo
llena huecos y ningún escaneo que ya resolvía cambia de fuente.

**Lo que sobrevive como trampa** es la forma, no el caso: cuando aparezca una
cuarta fuente de escaneos, hay que agregarla **a los dos** índices. Y si algún
día un control da verde y el documento igual sale con páginas de aviso, la
pregunta correcta no es cuál de los dos miente — es **qué fuente ve cada uno**.

### El import puede perder conduces sin avisar, y la secuencia es lo único que lo ve

**El número de conduce no es opaco.** Son 10 caracteres: los 2 primeros la
**planta** (M3, M5, M7 y M8) y los 8 restantes una **secuencia propia de esa
planta**, que avanza con el tiempo. Eso no está en ningún esquema ni lo deduce
un script solo, y es lo que convierte al número en un **control de totalidad**:
la base sabe lo que entró, pero por sí sola no puede saber lo que faltó.

Medido sobre las 4.224 filas de las dos tablas el **2026-09-07**: el formato no
falla ni una vez, ningún número aparece repetido, y ordenando por número dentro
de cada planta **no hay una sola inversión de fecha**. Eso último vale por sí
mismo: número y fecha los lee Vision **por separado** del mismo papel, así que
4.224 lecturas que no se contradicen son una validación cruzada gratis. El día
que aparezca una inversión, es una lectura mala de alguno de los dos —y hasta
resolverla, los huecos dejan de significar nada.

**Lo que encontró la primera corrida: 9 conduces escaneados que no estaban en
ninguna de las dos tablas.** Están en `Puente 1.zip`, existen en papel, y el
import no los dejó en ningún lado que alguien mire.

**El porqué que este documento tenía escrito era falso.** Decía que no eran
bloqueos por sello «porque esos viven en `pendientes_revision` y estos no estaban
ahí». Sí eran bloqueos por sello: los 9 están en
`conduces/data/puente_errores_sello.txt`, 5 con motivo `sin sello` y 4 con `sin
firma` — un motivo que dejó de bloquear el 2026-08-24 con el issue #7. Verificado
el 2026-09-08.

Lo que no hay es fila en ninguna tabla, y eso se comprobó contra los **43
respaldos** de `backups/db/` del 2026-08-20 al 2026-09-07: los 9 no aparecen ni
una vez, ni en `facturas`, ni en `pendientes_revision`, ni en
`pendiente_descartado`. No se borraron después: **nunca estuvieron**.

En qué corrida se rechazaron no se puede fechar: `errores_sello.txt` se abre en
modo `a` y no lleva fecha por línea. Lo que sí está medido es que el camino de
rechazo de Fase 2 **con el código de hoy inserta la fila** —reproducido sobre una
copia de la base el 2026-09-08— así que el defecto que las perdió no está en la
versión actual. No lo des por muerto sin más: no se identificó la línea que
fallaba, solo se acotó a que ya no reproduce.

**El mecanismo que los enterró era `puente_progreso.txt`**, que anotaba «visto»,
no «importado»: `prog_file.write(fn)` corría en las **dos** ramas, la que
importaba y la que rechazaba, y Fase 2 arrancaba con `if fn not in progreso`. Un
rechazado quedaba marcado como procesado para siempre y ninguna corrida futura lo
volvía a mirar, ni siquiera cuando la regla que lo bloqueó cambió. Eso explica por
qué otros sí se recuperaron y estos no: los 13 bloqueados por firma del
2026-08-20 volvieron a `facturas` el 2026-08-27 — **porque estaban en
`pendientes_revision`, una tabla que alguien mira**. Los 9 solo estaban en un
`.txt` que no leía nadie. Medido el 2026-09-08: de las 3.315 líneas de
`progreso.txt`, exactamente 9 no tenían fila en ninguna tabla, los mismos 9 que
encuentra `secuencia.py` por el otro camino.

**El issue #78 (2026-09-09) mató ese archivo.** Las dos fases chequean la base
—`facturas`, `pendientes_revision` y `pendiente_descartado`— antes de pagar
Vision; un rechazado se reintenta borrando su fila de `pendientes_revision`, y el
que no está en ninguna tabla se reintenta solo. El resumen final reconcilia
contra el total del ZIP o sale con error, y `secuencia.py` cuenta también
`pendiente_descartado` para no inventar huérfanos. Los 9 tienen fuente en la
planilla `COnduces.xls` y entran en la próxima corrida sin ningún paso manual.

Son del 2 de junio al 13 de julio, o sea **todos por debajo del corte**
(`fecha_base = 2026-07-16` en las nueve fases), así que
`_est_calcular_acumulados()` los saltearía aunque se importaran hoy, y el
acumulado base que los cubre salió de los documentos del cliente. **No es plata
que falte: es fidelidad del import.** Ningún documento entregado está mal por
esto. Lo que sí queda probado es que el import puede tirar filas sin que se
entere nadie, y ahora hay cómo detectarlo:

```bash
python scripts/secuencia.py
```

**Corrélo antes de cada cierre.** Reconcilia los escaneos contra las dos tablas
y parte los faltantes por el corte, que es la única división que importa: por
debajo ya están contados en el acumulado, por encima **todavía no se contaron en
ningún lado** y son m³ que no van a entrar al próximo documento.

**Un hueco de secuencia NO prueba que falte un conduce**, y esto ya se comprobó
en vez de suponerlo. La planta le sirve a más de un cliente, así que el número
pudo no ser nuestro nunca. Al 2026-09-07 hay 432 huecos; de los 165 que caen en
la ventana donde los documentos del cliente son comparables, **160 tampoco están
en el papel del cliente** — el documento manual saltea exactamente los mismos
números. O sea que fueron a otra obra y no hay que preguntarle nada a la planta.

Los otros 5 sí eran nuestros: `M300056140`, `M700018924`, `M800012675`,
`M800012704` y `M800012743`. Tres de ellos están entre los 9 huérfanos de arriba,
o sea que tenemos el escaneo y solo falta importarlo.

El script muestra los huecos separados justamente para que no se lean como
pérdidas; para clasificarlos hay que cruzarlos contra los documentos del cliente
— con el cuidado que explica la trampa del PPACT, porque falta un documento y su
ausencia se lee como un faltante que no existe.

### Verde en los tests no prueba que las rutas estén bien

La suite arma los Excel **en memoria** y no toca ninguna carpeta de datos. Si
rompés una ruta de archivos, la suite entera sigue en verde. Eso se verifica
**levantando el servidor y pegándole por HTTP**, no corriendo pytest.

**Pasó de nuevo el 2026-09-02, y vale como ejemplo.** El issue #31 agregó
`sin_precio` al retorno de `core.generar_reporte()`, con 7 tests en verde. Pero
las tres rutas de `routes_conduces.py` rearmaban la respuesta a mano
(`{"download_url", "cached"}`) y tiraban el campo — junto con `total`,
`pagados` y `pendientes`, que venían siendo descartados desde antes sin que
nadie lo notara. Los tests pasaban porque llamaban a `core.generar_reporte()`
**directo**, nunca por HTTP. Se descubrió pegándole al servidor **después de
mergear**.

La regla que sale de ahí: **si el campo tiene que llegarle al cliente, el test
va por la ruta.** Un test que llama a la primitiva de `core` prueba la
primitiva, no la API.

### Un test que sólo falla en CI puede ser el defecto, no el test

El runner no tiene LibreOffice, así que la conversión a PDF se saltea y **todo
corre mucho más rápido que en tu máquina**. Eso no es una diferencia cosmética:
cambia qué defectos son visibles.

Pasó el 2026-09-30 con el [issue #83](https://github.com/lach06/VMO/issues/83).
El nombre del entregable era
`EST_{empresa}_{fase}_{desde}_{hasta}_{YYYYmmdd_HHMMSS}.xlsx` — **sin la serie y
con resolución de un segundo**— así que generar el `principal` y el `ppact` del
mismo período escribía dos veces el mismo archivo y el segundo pisaba al
primero. Con LibreOffice instalado la conversión mete segundos entre una
generación y la siguiente y el choque no ocurre nunca; sin soffice las dos caen
en el mismo segundo. **En local pasaba, en CI fallaba, y el que tenía razón era
CI.** Arreglado con la serie en el nombre, milisegundos, y un sufijo `_2` si el
nombre ya existe.

Dos cosas que dejó y valen más que el arreglo:

- **`main` estuvo roja cuatro días sin que nadie mirara** (desde el 2026-09-26).
  Un rojo heredado es más fácil de ignorar que uno propio, y se vuelve el ruido
  de fondo que tapa al siguiente. Si el check está rojo, leelo antes de mergear
  aunque el PR sea ajeno.
- **Medí en el arnés donde falla, no en uno parecido.** La hipótesis correcta se
  dio por muerta una vez: una sonda escrita fuera de pytest dio 0 choques en 10
  corridas, porque armar la BD en cada vuelta empujaba las dos generaciones a
  segundos distintos. La misma sonda **adentro** de pytest reprodujo el choque a
  la primera.

### `copy_worksheet` de openpyxl pierde cosas en silencio

Pierde **imágenes, `print_area` y el footer**. Los merges y las fórmulas sí
sobreviven. Todo lo perdido hay que volver a ponerlo en cada hoja después de
copiar. Verificado empíricamente contra openpyxl 3.1.5.

### Medí el PDF, no el `.xlsx`

Dos defectos reales aparecieron solo al mirar el PDF generado: bloques que se
partían por escala, y un croquis descentrado porque **LibreOffice recorta un
offset de ancla más grande que su celda**. El `.xlsx` se veía perfecto en los dos
casos.

### `obra` y `fase` son columnas distintas, y ninguna de las dos es la obra del papel

En `facturas`, `fase` es la normalizada por `_normalizar_fase()`. **El generador
usa `fase`.** Auditar por `obra` produce falsos hallazgos: aparecen valores como
`PARMOL` que parecen fases desconocidas y no lo son.

**Y `obra` tampoco es lo que dice el papel.** El conduce trae impresa una línea
`OBRA:` con la obra real —`DIMECA`, `CONCAVA`, `LIDOMI`— además del `Cliente:`,
que en las tres dice lo mismo: `MACAO ALTO RESORT SRL (CIUDAD PALACE - CAVERNAS
Y EXT)`. Verificado el 2026-09-07 — `DIMECA`, `CONCAVA` y `LIDOMI` no aparecían
**ni una vez** en `obra`, `cliente`, `referencia` ni `observaciones` de las 4.185
filas, mientras que están impresos en los PDFs.

**El porqué que este documento tenía escrito era falso**, y se corrigió al
construir el issue #67 mirando el código: no era que Vision devolviera "el
cliente normalizado". El camino masivo es `scripts/importar_puente.py`, y ahí
pasaban dos cosas distintas — (a) `obra` recibe `row['fase']`, o sea la fase, por
decisión explícita del usuario, y (b) el prompt de `vision_extract()` **nunca
pedía el campo `obra`**, así que el dato no llegaba ni para descartarlo. El
prompt de `core._procesar_pdf_sync()` (camino individual) sí lo pide y lo lee
bien: 10/10 sobre los 10 fixtures reales. De ahí que por ese camino la columna
traiga valores como `MALESPIN MACAO II` o `PARMOL`.

**`obra` tiene por eso dos semánticas según el camino** — por el import masivo
vale la fase, por el individual lo que devuelva Vision — y **eso sigue igual**:
el issue #67 no las unificó.

Desde el issue #67 (2026-09-07) el dato del papel vive en su propia columna,
**`obra_papel`**, en `facturas`, `pendientes_revision` y `pendiente_descartado`;
la pueblan los dos caminos de escritura y la expone
`GET /api/estimaciones/pendientes-revision`. **Las 4.185 filas viejas quedan en
`NULL`**: se rellenan con `python scripts/backfill_obra_papel.py --limite N`, que
es **una llamada a Vision por fila y eso cuesta plata** — la corrida completa la
decide el usuario, no se dispara sola. Mientras `obra_papel` esté en NULL, para
saber a qué obra fue un conduce viejo hay que abrir el escaneo.

Ojo con la conclusión fácil: **la obra NO es lo que decide si el cliente factura
un conduce.** Se comprobó con `M800013170` (obra CONCAVA) que **sí** está en la
estimación de CAVERNAS, al lado de conduces de LIDOMI. Lo que separa lo facturado
de lo no facturado es el **producto y su precio** — ver la trampa de los dos
productos de CAVERNAS.

### `orden` y `clave` no son intercambiables

En el catálogo, `orden` es la **posición física** del renglón y `clave` es la
**etiqueta** del producto. Coinciden en 70 de 72 filas, así que un error acá vive
mucho tiempo escondido. La única fase donde difieren es **VMO/PATIO DE
MANIOBRAS-TRA**. Si "corregís" el cálculo de la fila usando la clave, en TRA se
intercambian dos renglones enteros del REO y **eso sí mueve plata**.

### Los documentos del cliente no son consistentes entre sí

Están armados a mano. El título de la celda A5 viene con **las letras espaciadas
una por una**, con doble espacio irregular en algunos. Hay hojas con 13 folios
donde deberían ir 40, títulos equivocados en 6 de 15 documentos, y geometrías que
varían sin regla. **Buscá la regla en varios ejemplos; no clones un archivo.**

### VMO/EXTERIORES tiene un renglón que el documento del cliente no trae

La clave **16, Mortero fc250 a 148,11**, la agregamos nosotros el 2026-10-05:
aparecieron 2 conduces (`M700019645`/`46`, 14 m³, del 2026-09-05) sin renglón
donde caer. La plantilla lo hace con `renglones_extra` en `EST_PLANTILLAS`:
ocupa la fila en blanco de antes de TOTALES, así que **no se movió nada** y
TOTALES queda pegado al bloque. Solo cabe uno así; un segundo producto nuevo ya
obliga a insertar filas, y eso sí corre firmas, pie y referencias.

**Cuando el cliente lo agregue en su documento, compará la clave.** Si le pone
otro número u otra posición, manda la del cliente (ver «`orden` y `clave` no
son intercambiables»), y hay que mover catálogo, acumulado base y plantilla
juntos.

### El ciclo de estimaciones corre del 17 al 16

No es mes calendario. Cuando alguien dice "el mes", se refiere al período de la
estimación.

### Los conduces de junio y julio 2026 son datos de siembra

Entraron para construir el sistema, no son operativos. **No traduzcas un hallazgo
sobre esa data a "plata en riesgo".** Lo que sobrevive de un hallazgo ahí suele
ser el defecto de código, no el monto. Ojo: esto vale para el módulo de
**Conduces**; los hallazgos sobre `estimaciones.db` sí valen por su plata, porque
esos documentos se entregan.

### Un worktree no trae los datos ignorados

Los 15 documentos del cliente (768 MB) y las dos bases están en `.gitignore`. Un
agente trabajando en un worktree limpio **no los tiene**. Hay que copiarle las
bases (aisladas, para que no toque producción) y pasarle la ruta de los
documentos en solo lectura.

### Los scripts asumen vivir un nivel debajo de la raíz

Los ~22 scripts calculan `BASE_DIR` como `parent.parent` de su propio archivo.
Moverlos dentro de una carpeta de módulo les cambia la raíz **sin lanzar ningún
error**: siguen corriendo y leen o escriben donde no es. Por eso el código quedó
compartido en la raíz y solo los datos se partieron por módulo.

---

## Cómo se trabaja acá

El flujo que funciona, en este orden:

1. `/gstack-spec` para definir el trabajo, y `/gstack-plan-eng-review` para
   revisarlo con una segunda voz **antes** de construir
2. Filear el issue en GitHub
3. `git worktree add` y despachar un agente en background
4. **Revisar el diff y correr la suite por fuera del reporte del agente**

**Al despachar el agente, pasale el spec INLINE en el brief.** No le pidas que corra
`gh issue view`: en una sesión no interactiva `gh` puede estar bloqueado por permisos
y el prompt de aprobación no le llega a nadie. Pasó el 2026-09-02 con el #38 — el
agente no pudo leer el issue, no escribió una sola línea, y la corrida se perdió.
El archivo del spec que deja `/spec` en `~/.gstack/projects/lach06-VMO/specs/` sirve
tal cual para pegarlo en el brief.

**Y copiale las bases al worktree.** `conduces.db`, `estimaciones.db` y `.env` están
en `.gitignore`, así que un worktree limpio no los tiene. Van como copias aisladas
para que el agente pueda escribirles sin tocar producción. Para que la suite completa
corra ahí hace falta además
`EST_FUENTES_DIR=/c/Users/axelo/VMO/conduces/estimaciones/data/plantillas_por_fase`
— en el checkout principal esa variable no hace falta porque los documentos están.

El paso 4 no es opcional. En cada uno de los últimos issues el agente encontró un
error real del spec, y en cada revisión independiente apareció algo que su
reporte no decía.

**Al escribir el brief de un agente, pedile explícitamente que denuncie los
errores del spec.** En seis issues seguidos el spec tenía un error real y quien
lo construyó lo encontró (los #16 al #20, y el #27).

**Después de escribir un test de regresión, comprobá que falla si sacás el fix.**
Un test que pasa con y sin el arreglo no guarda nada, y ya se coló uno así.

---

## Dónde vive el conocimiento

- **`CLAUDE.md`** — contexto completo del proyecto, reglas de negocio, estructura
  de datos, y el detalle de cada módulo. Es lo primero que hay que leer.
- **`README.md`** — la portada del repo: estado, backlog agrupado por quién
  decide, y lo entregado.
- **Issues de GitHub** — el backlog real desde el 2026-08-31. No está en
  `AGENDA.md`.
- **`AGENDA.md`** — historial narrativo por fecha, de lo más nuevo a lo más viejo.
  **Ya no es el arranque** desde el 2026-09-04: su bloque de traspaso decía cifras y
  issues de hacía tres días, así que se borró en vez de reescribirlo. Se lee para
  entender por qué se decidió algo, nunca para saber en qué estado está el proyecto.
- **`memory/log.md`** — historial cronológico de decisiones, append-only. No se
  lee entero: se consulta con grep cuando hace falta el detalle de una decisión
  pasada. **Vive fuera del repo**, en la carpeta de memoria de Claude Code, y se
  respalda con `scripts/backup_db.py`.
- **`documentos/`** — specs formales, incluido el del issue #27 con su reporte de
  revisión. Acá vive también el **correo a X archivado**,
  `mail_para_X_2026-09-03.md` y su adjunto `lista_precios_suplidores_2026-09-03.md`
  (con `.pdf` al lado). **No es un pendiente**: abre con un aviso de qué preguntas
  murieron al medirse y cuáles quedan para una carga real futura. Se guarda por si
  vuelve a aparecer un tema de precios de suplidores, no para mandarlo.
- **`conduces/archivos/Puente 1.zip`** — los 3.491 PDFs escaneados de los conduces,
  nombrados `MM-DD-Mx-NNNNN.pdf`. Cada uno trae impreso el **código de producto**, que
  es lo que permite resolver a qué renglón va un conduce sin preguntarle a nadie.
  El nombre trae la **planta y el número de secuencia**, que es lo que deja
  reconciliarlos contra las bases sin abrir un solo PDF — ver la trampa del import. Son
  escaneos sin capa de texto: hay que renderizarlos con PyMuPDF y mirarlos, y algunos
  vienen rotados 180°.
- **`dropoff/`** — intercambio de archivos: dos documentos de ejemplo con las hojas
  RCO/RFO nuevas, el anexo `preguntas_para_X.md` y el análisis del #31. **No está
  versionado** (`.gitignore:48`), así que en un clone limpio esa carpeta viene vacía
  y `scripts/backup_db.py` tampoco la respalda: lo que quede solo acá vive en una
  sola máquina. **El correo a X ya no está acá** — se movió a `documentos/`, que sí
  se versiona. Regla que sale de eso: si un entregable tiene que sobrevivir a la
  sesión, no lo dejes en `dropoff/` ni en un scratchpad.

---

## Si tenés diez minutos y querés entender el proyecto

Abrí `dropoff/ejemplo_DOMICEM_MACAO_2_*.pdf`. Son 47 páginas: la carátula, el
resumen con todos los productos, y después una hoja por producto con sus
entregas, su croquis y su reporte fotográfico. **Eso es lo que el sistema
reemplaza**, y antes se armaba a mano todos los meses, por cada una de las 9
fases.
