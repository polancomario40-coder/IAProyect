---
description: Abre la sesión con el protocolo del proyecto — estado calculado, trampas, y qué se puede hacer hoy
---

Ejecutá el protocolo de apertura de este proyecto. Está definido en `CLAUDE.md`,
sección "Protocolo de apertura y cierre". Son tres pasos y unos 8 minutos, casi
todo lectura.

## 1. El estado, calculado

```bash
python scripts/estado.py
```

Eso da la punta de `main`, el último commit que cambió comportamiento, si el árbol
está limpio, las filas de las dos bases, el libro mayor, el último período cerrado,
los issues abiertos y cuántos tests hay.

**No copies esos números a ningún `.md`.** Si alguno hace falta más tarde, se vuelve
a correr el script. Ese es todo el punto de que exista.

## 2. Las trampas

Leé la sección **"Trampas que te van a morder"** de `HANDOFF.md`, entera. Son ~1.280
palabras y están ordenadas por cuánto cuestan si las descubrís tarde, así que si
tenés que cortar, cortá por abajo y decilo.

## 3. Nada más

**No abras `AGENDA.md`.** Es historial cerrado: hasta el 2026-09-04 arrancaba
diciendo 483 tests cuando eran 626 y cuatro issues cerrados como si estuvieran
pendientes.

Si necesitás el detalle de una decisión pasada, `memory/log.md` se consulta **con
grep**, nunca se lee entero.

> **Un `Pendiente:` al final de una entrada del log es un dato fechado, no un
> estado.** Dice lo que se pensó ese día. Antes de tratarlo como trabajo abierto —y
> sobre todo antes de copiarlo a un documento vivo— **abrí el código y comprobalo**.
> Ya pasó: un pendiente del 2026-08-24 que se había resuelto ese mismo día terminó
> escrito como trampa en el `HANDOFF`.

## Después de los tres pasos, decime en pocas líneas

- **Dónde está parado el proyecto**, en una frase.
- **Qué se puede construir hoy** y qué está bloqueado esperando a alguien de afuera.
  Si no hay nada construible, decilo derecho en vez de inventar trabajo.
- **Qué trampa aplica** a lo que estemos por hacer, si ya sabés qué vamos a hacer.

No me repitas la salida del script: ya la vi. Decime lo que **concluís** de ella.
