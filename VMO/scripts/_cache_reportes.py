# by a_oller
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTES_DIR = os.path.join(BASE_DIR, "conduces", "reportes")
FACTURAS_DIR = os.path.join(BASE_DIR, "conduces", "facturas")


def limpiar_cache_reportes():
    """Borra los reportes/facturas HTML cacheados. Se llama despues de
    cualquier cambio a los datos (import, pago) para que el proximo reporte
    pedido refleje el estado actual, nunca uno viejo generado antes del
    cambio. No fatal si un archivo no se puede borrar (permiso denegado,
    abierto por otro proceso) — el import/pago real no debe fallar por eso."""
    borrados = 0
    for directorio in (REPORTES_DIR, FACTURAS_DIR):
        try:
            nombres = os.listdir(directorio)
        except OSError as e:
            # directorio no existe, se borro entre el isdir() implicito y
            # este listdir(), o sin permiso de lectura — no debe tumbar el
            # import/pago real que ya se confirmo en la BD.
            print(f"No se pudo listar {directorio}: {e}")
            continue
        for nombre in nombres:
            if not nombre.endswith(".html"):
                continue
            ruta = os.path.join(directorio, nombre)
            try:
                os.remove(ruta)
                borrados += 1
            except OSError as e:
                print(f"No se pudo borrar {ruta}: {e}")
    return borrados
