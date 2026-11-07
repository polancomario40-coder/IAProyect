---
description: Cierra la sesión con el protocolo del proyecto — escribe el log, corre cierre.py y deja main limpia
---

Ejecutá el protocolo de cierre de este proyecto. Está definido en `CLAUDE.md`,
sección "Protocolo de apertura y cierre".

## 1. Escribí el log primero

`scripts/cierre.py` comprueba que haya entradas de hoy, pero **no las escribe**: eso
requiere criterio y es tuyo.

Agregá a `memory/log.md` **una entrada por cada decisión tomada en esta sesión**, no
una que resuma el día. Si hoy se tomaron seis decisiones, van seis entradas. El
formato es el de las filas que ya están (`| YYYY-MM-DD | **Titular.** cuerpo |`), y
el archivo es **append-only**: nunca edites una entrada vieja. Si una quedó mal,
agregá una que la corrija — hay precedentes en el archivo.

Qué merece una entrada:

- Una decisión de diseño y **por qué se eligió eso** y no lo otro.
- Un hallazgo medido, con el número y cómo se midió.
- **Un error propio y qué lo destapó.** Estos son los que más valen, y los que más
  tentación da omitir.

Qué no: que se corrió la suite, que se abrió un PR, o cualquier cosa que `git log`
ya cuente mejor.

## 2. Corré el cierre

```bash
python scripts/cierre.py
```

Comprueba seis cosas y sale con código 1 si falta alguna de las que bloquean: `main`
mergeada, limpia, sincronizada y sin ramas, worktrees ni PRs colgando; al menos una
entrada de hoy en `log.md`; qué quedó en `dropoff/`; los servidores de desarrollo que
siguen corriendo; el respaldo; y el estado final.

Dos de esos pasos hacen algo, no solo miran, y los dos son de los que no tienen
criterio: **el respaldo** y **cerrar los servidores**. El resto reporta.

**El `dropoff` se reporta y nunca se borra.** El script separa lo declarado intocable
—con su motivo— de lo que hay que revisar, y ahí se queda: ahí adentro hay copias
únicas, y borrar es una decisión que se consulta. No bloquea el cierre.

## 3. Actuá sobre lo que reporte

**Lo que podés hacer sin preguntar**, porque no es destructivo ni sale del proyecto:
escribir las entradas del log, y volver a correr el script.

**Lo que tenés que consultar antes**, porque son decisiones y no tareas: commitear,
mergear, borrar una rama o descartar cambios sin commitear. La regla del proyecto es
que no hay commits automáticos, y `/cierre` no la deroga. Decime qué falta y qué
proponés hacer.

**Nunca cierres la sesión escondiendo lo que quedó abierto.** Si el script sale con
código 1 y no se puede resolver ahora, eso se dice — un cierre que reporta verde
porque se salteó lo incómodo es peor que no cerrar.

## 4. Cerrá con un resumen corto

- **Qué quedó hecho**, y qué quedó abierto **a propósito** con su motivo.
- **Lo que hay que saber para retomar**, si es algo que ningún script va a decir.
- Si algo quedó en un estado raro, decilo ahí y no en una nota al pie.
