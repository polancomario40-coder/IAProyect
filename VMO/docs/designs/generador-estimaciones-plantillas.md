# Design: Generalizar la plantilla del generador de Estimaciones a las 9 fases

Generado por /office-hours el 2026-08-20
Rama: main
Repo: lach06/VMO
Status: APPROVED
Modo: Startup (intrapreneurship)

## Problema

El generador de estimaciones (backend ya construido y probado con VMO/CEDIS)
solo funciona para 1 de 9 fases porque `plantilla_estimacion.xlsx` tiene
capacidad fija de 12 filas de producto, exacta para CEDIS. Las otras 8 fases
necesitan entre 3 y 15 filas. Sin resolver esto, la feature no reemplaza el
trabajo manual que hace el jefe cada mes — solo lo reemplaza para 1 fase de 9.

## Evidencia de demanda

El documento de estimación es un requisito real y existente para un proceso
regulatorio (CONFOTUR, proyecto Moon Palace) — se arma a mano todos los meses
hoy mismo, no es un problema hipotético.

## Status quo

Excel armado a mano cada mes, por cada una de las 9 fases, copiando la
plantilla anterior y actualizando manualmente cantidades y facturas.

## Restricciones

- Solo `openpyxl` disponible (sin LibreOffice/Excel instalado para
  recalcular fórmulas automáticamente en pruebas)
- Sin suite de tests en el proyecto
- Desarrollador solo (sin CI/CD)

## Premisas (confirmadas)

1. El problema está aislado a la construcción del archivo Excel — el resto
   del sistema (matching, endpoints, validaciones) ya funciona igual para
   cualquier fase.
2. Ya existe código reusable — el patrón completo ya se validó con CEDIS.
3. Resolver esto es central, no opcional, para que la feature sirva a las 9
   fases y de verdad reemplace el trabajo manual.
4. No aplica plan de distribución — es una función web interna, no un
   artefacto instalable.

## Perspectiva cruzada (Codex)

Lectura independiente, sin ver la conversación completa:
- **Recomienda plantillas fijas por fase** — verificó contra la
  documentación oficial de openpyxl que `insert_rows()` no garantiza
  mantener celdas combinadas ni fórmulas de forma confiable; clasifica la
  inserción dinámica como "no soportada y no segura" para este caso.
- **Reto propuesto:** comparar estructuralmente las 9 plantillas reales
  (fórmulas, celdas combinadas, alturas de fila, pie de página) para
  confirmar que solo difieren en cantidad de filas de producto.
- **Plan concreto:** limpiar las 8 plantillas restantes igual que CEDIS, un
  registro `(empresa, fase) → archivo/filas esperadas`, reemplazar los
  rangos hardcodeados, verificar cada archivo generado (hojas, celdas
  combinadas, fórmulas, ausencia de `#REF!`) antes de darlo por bueno.

## Enfoques considerados

### Enfoque A: Inserción dinámica de filas (openpyxl `insert_rows`)
Una sola plantilla genérica; el código inserta/quita filas según el catálogo
de cada fase al generar. **Descartado** — ya falló una vez (celdas
combinadas del pie de página), y Codex confirmó contra la documentación
oficial que openpyxl no garantiza preservar celdas combinadas/fórmulas en
este escenario.

### Enfoque B: 9 plantillas fijas por fase
Limpiar cada uno de los 9 documentos reales (mismo patrón ya usado con
CEDIS: borrar datos de ejemplo, dejar fórmulas intactas) y guardarlos como
`plantilla_estimacion_{empresa}_{fase}.xlsx`. El generador elige el archivo
correcto según empresa+fase.

## Enfoque recomendado

**Enfoque B** — 9 plantillas fijas por fase. Acordado por el usuario, con el
respaldo de Codex. Más simple, más seguro (mismo patrón ya validado), y no
depende de un comportamiento de openpyxl que no está garantizado.

## Preguntas abiertas

- ~~Diseño del frontend~~ — resuelto vía `/plan-design-review` el 2026-08-20,
  ver sección siguiente.

## Diseño del frontend — revisado 2026-08-20 (`/plan-design-review`)

Sin API key de OpenAI configurada (decisión: no configurarla sin instrucción
explícita del usuario) — mockups hechos como wireframes HTML/CSS reales,
usando los colores, tipografía y componentes exactos ya documentados en
`CLAUDE.md` (sin IA, sin costo). Archivos:
`C:\Users\axelo\AppData\Local\Temp\wireframe_generar_estimacion.html` (pantalla
1: formulario + tabla de catálogo) y
`wireframe_generar_estimacion_revision.html` (pantalla 2: revisión de
matching antes de generar).

**Pantalla 1 — formulario + catálogo:** 4 campos manuales en fila (N° de
Estimación, OC/Contrato, Fecha de Estimación, Semana Calendario) + tabla
densa por producto del catálogo (clave, descripción, cant. proyecto, acum.
anterior, badge verde "N facturas" o badge gris "sin entregas").

**Pantalla 2 — revisión de matching:** 3 tarjetas resumen (matcheadas / sin
match / total catálogo) + acordeón por producto (reusa `acordRow`, mismo
patrón que "Procesar Facturas") con el detalle de facturas matcheadas +
sección aparte con borde rojo para facturas sin match, cada una con un
`<select>` para asignar manualmente a un producto o excluir de la
estimación.

**Hallazgo resuelto:** los campos "Cant. Proyecto" y "Acum. Anterior" tocan
directamente las preguntas #3 y #4 aún pendientes con el jefe (presupuesto
fijo vs variable, cálculo automático vs manual la primera vez). Decisión:
construir editable por ahora — si el jefe confirma que el sistema debe
calcularlo, se ajusta ese campo sin rehacer el resto de la pantalla.

**Resto de la revisión (7 dimensiones):**
- Jerarquía visual y consistencia: fuerte — reusa componentes ya validados,
  sin patrones nuevos que aprender.
- Interacción/feedback: falta explícitamente construir el estado de carga
  (spinner en botón, mismo patrón `::after` ya usado) durante la vista
  previa y durante la generación, y el estado posterior con botón verde de
  descarga (mismo patrón que ya existe en el panel actual de Estimaciones).
- Estados de error: falta el mensaje específico por tipo ya acordado en
  `/plan-eng-review` (plantilla faltante, catálogo desincronizado) —
  reflejarlo en la pantalla de revisión, no solo en el backend.
- Responsive: debe seguir el mismo tratamiento mobile ya construido para el
  resto de la app (`@media max-width:860px` — tablas con scroll horizontal,
  campos en una columna).
- Accesibilidad: contraste de texto ya cumple (paleta existente); agregar
  `<label>` a los `<select>` de asignación manual en la pantalla de
  revisión.
- Copy/contenido: terminología tomada directamente del documento Excel real
  (Folio Remisión, Cant. Proyecto, etc.) — consistente con el documento
  físico que se está reemplazando.

Estos puntos (spinner, estado de descarga, mensajes de error específicos,
mobile, labels de accesibilidad) quedan incorporados al alcance de T6
(frontend) en el plan de `/plan-eng-review`, no como tareas nuevas.

## Criterios de éxito

- Las 9 fases generan un `.xlsx` válido, con fórmulas correctas verificadas
  (a mano o con recálculo automático si se instala LibreOffice).
- El generador rechaza claramente (sin corromper el archivo) cualquier caso
  que no calce con el catálogo esperado de esa fase.

## Dependencias

- Bloquea: construcción del frontend del generador (no tiene sentido
  construirlo sobre una plantilla que solo sirve para 1 fase).

## La tarea concreta

Limpiar las 8 plantillas Excel reales restantes (mismo proceso manual que ya
se hizo una vez con CEDIS), y construir el registro `(empresa, fase) →
plantilla` que reemplace los rangos de filas hardcodeados en el backend.

## Qué noté sobre cómo piensas

- Insististe en que el catálogo de `REO-01` fuera fiel al documento real
  completo, no solo lo entregado ese mes — decisión de negocio correcta que
  yo no había anticipado en el spec original, y que cambió el diseño.
- Cuando encontraste el choque entre "CIMENTACION TORRES" y "TORRE GRUA" en
  MACAO 2, tu instinto fue fusionarlos en vez de forzar una distinción que
  los datos no soportan — mismo criterio que ya habías aplicado antes con
  la regla de "nunca intercambiar valores entre campos".
