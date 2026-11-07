# AGENTS.md

Este proyecto usa `CLAUDE.md` como la fuente de verdad del contexto completo — léelo primero, completo, antes de hacer cualquier cosa. Contiene el negocio, la arquitectura, las reglas críticas y el historial completo de decisiones.

Después lee `HANDOFF.md`: es el traspaso entre sesiones — estado, qué está
bloqueado y por quién, y las trampas que cuestan caro si las descubrís tarde.
Lo que falta se consulta con `gh issue list --state open`. **`AGENDA.md` ya no
es el arranque**, es historial narrativo por fecha.

## Reglas que aplican sin importar qué agente esté trabajando

- Toda comunicación en **español**.
- **Pedir confirmación antes de cualquier cambio** (archivos, BD, scripts, frontend, etc.) — no asumir permiso.
- No hacer commits ni push automáticos salvo que se pida explícitamente.
- No modificar la plantilla de reportes (`generar_reporte()` en `core.py`) sin confirmación explícita del usuario.
- **Nunca intercambiar valores entre campos** (`precio`, `cantidad`, `fecha`, etc.) — ver "Reglas de negocio críticas" en CLAUDE.md.
- **Antes de declarar un cambio "terminado": correr `python -m pytest tests/ -v` y verificarlo de verdad.** No basta con que el código se vea correcto. Si el cambio toca borrado/escritura de archivos (caché, reportes, PDFs), verificar aislamiento con archivos canario antes y después. Regla puesta después de 3 rondas de bugs reales encontrados en la misma sesión (ver CLAUDE.md, historial de decisiones 2026-08-21) — no es opcional.
- Actualizar `CLAUDE.md` (historial de decisiones) después de cualquier cambio real, siguiendo el formato ya usado ahí. Si el cambio mueve el estado del proyecto o agrega una trampa, va también a `HANDOFF.md`. **`AGENDA.md` no se toca**: es historial cerrado.

## Cómo correr el proyecto

```bash
cd C:\Users\axelo\vmo\conduces
python scripts/estado.py       # AL ABRIR: el estado del proyecto, calculado ahora
python scripts/cierre.py       # AL CERRAR: comprueba main, log y respaldo
python -m uvicorn main:app     # SIN --reload: en Windows no es confiable y ya
                               # costo investigar un bug que no existia (ver HANDOFF.md)
python -m pytest tests/ -v
```

## Bootstrap desde cero

Desde la raíz de un checkout limpio, ejecutar en este orden:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/setup_db.py
python -c "from core import setup_est_db; setup_est_db()"
python scripts/seed_precios_catalogo.py
python -m pytest tests/ -v
python -m uvicorn main:app --reload
```

`seed_precios_catalogo.py` acepta como argumento opcional una ruta alternativa
a `estimaciones.db`; los tests siempre usan una BD temporal y nunca las BDs reales.
