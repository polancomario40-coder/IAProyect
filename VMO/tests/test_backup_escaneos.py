"""
Tests del espejo de escaneos de scripts/backup_db.py.

Los escaneos van con otra logica que las bases: son ~1,5 GB append-only, asi
que se ESPEJAN —copiar solo lo que falta, no rotar nunca— en vez de sacarles
una copia fechada por dia. Importa porque para los lotes importados antes del
2026-08-24 `conduces/archivos/` es la unica copia que existe: esos PDFs no
estan en `estimaciones/facturas/procesadas/`.

Todo corre sobre directorios temporales: ninguna prueba lee los zips reales ni
escribe en Google Drive.

Correr con: python -m pytest tests/test_backup_escaneos.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import backup_db  # noqa: E402


@pytest.fixture
def escenario(tmp_path, monkeypatch):
    """Un origen con dos lotes y un suelto, y un destino vacio que hace de Drive."""
    origen = tmp_path / "archivos"
    (origen / "escaneos").mkdir(parents=True)
    (origen / "Puente 1.zip").write_bytes(b"x" * 1000)
    (origen / "Puente 2.zip").write_bytes(b"y" * 2000)
    (origen / "escaneos" / "08-01-M8-14430.pdf").write_bytes(b"z" * 500)
    destino = tmp_path / "gdrive"
    destino.mkdir()

    monkeypatch.setattr(backup_db, "ESCANEOS_DIR", origen)
    monkeypatch.setattr(backup_db, "ESCANEOS_SUELTOS", origen / "escaneos")
    monkeypatch.setattr(backup_db, "GDRIVE_BACKUP_DIR", str(destino))
    monkeypatch.setattr(backup_db, "LOG_PATH", tmp_path / "backup_log.txt")
    return origen, destino / "escaneos"


def test_toma_los_zips_de_lotes_y_los_pdf_sueltos(escenario):
    origen, _ = escenario
    (origen / "CONDUCES 18-08-2026.xlsx").write_bytes(b"no soy un escaneo")
    nombres = [p.name for p in backup_db._origenes_de_escaneos()]
    assert nombres == ["Puente 1.zip", "Puente 2.zip", "08-01-M8-14430.pdf"]


def test_la_primera_corrida_copia_todo(escenario):
    _, destino = escenario
    backup_db.espejar_escaneos()
    assert sorted(p.name for p in destino.iterdir()) == [
        "08-01-M8-14430.pdf", "Puente 1.zip", "Puente 2.zip",
    ]


def test_la_segunda_corrida_no_copia_nada(escenario, monkeypatch):
    """Se cuentan las llamadas a copy2, NO los mtime del destino: copy2 copia
    la metadata del origen, asi que el mtime queda igual aunque el archivo se
    haya vuelto a subir. La primera version de este test comparaba mtime y
    pasaba con y sin el arreglo — o sea que no guardaba nada."""
    backup_db.espejar_escaneos()

    llamadas = []
    real = backup_db.shutil.copy2

    def copy2_espia(src, dst, *a, **k):
        llamadas.append(os.path.basename(str(src)))
        return real(src, dst, *a, **k)

    monkeypatch.setattr(backup_db.shutil, "copy2", copy2_espia)
    backup_db.espejar_escaneos()
    assert llamadas == [], f"no se vuelve a subir nada ya espejado, y se subio {llamadas}"


def test_un_lote_que_crecio_se_vuelve_a_copiar(escenario):
    origen, destino = escenario
    backup_db.espejar_escaneos()
    (origen / "Puente 2.zip").write_bytes(b"y" * 3000)
    backup_db.espejar_escaneos()
    assert (destino / "Puente 2.zip").stat().st_size == 3000


def test_nunca_borra_lo_que_ya_estaba_en_el_destino(escenario):
    """No hay rotacion: un escaneo viejo sigue siendo el respaldo del conduce
    de ese dia, aunque su lote ya no este en el origen."""
    origen, destino = escenario
    backup_db.espejar_escaneos()
    (origen / "Puente 1.zip").unlink()
    backup_db.espejar_escaneos()
    assert (destino / "Puente 1.zip").exists()


def test_sin_gdrive_avisa_fuerte_y_no_copia(escenario, monkeypatch, capsys):
    _, destino = escenario
    monkeypatch.setattr(backup_db, "GDRIVE_BACKUP_DIR", None)
    backup_db.espejar_escaneos()
    assert not destino.exists()
    salida = capsys.readouterr().out
    assert "SIN respaldar" in salida
    assert "unica copia" in salida, (
        "el aviso tiene que decir POR QUE importa, o se lee como un warning mas"
    )


def test_sin_escaneos_en_el_origen_se_salta_sin_reventar(tmp_path, monkeypatch):
    monkeypatch.setattr(backup_db, "ESCANEOS_DIR", tmp_path / "no-existe")
    monkeypatch.setattr(backup_db, "ESCANEOS_SUELTOS", tmp_path / "no-existe" / "escaneos")
    monkeypatch.setattr(backup_db, "LOG_PATH", tmp_path / "backup_log.txt")
    backup_db.espejar_escaneos()  # no debe lanzar


def test_un_archivo_ilegible_no_frena_a_los_demas(escenario, monkeypatch):
    origen, destino = escenario
    real = backup_db.shutil.copy2

    def copy2_que_falla(src, dst, *a, **k):
        if os.path.basename(str(src)) == "Puente 1.zip":
            raise PermissionError("archivo en uso")
        return real(src, dst, *a, **k)

    monkeypatch.setattr(backup_db.shutil, "copy2", copy2_que_falla)
    backup_db.espejar_escaneos()
    assert not (destino / "Puente 1.zip").exists()
    assert (destino / "Puente 2.zip").exists(), "el que falla no puede llevarse a los otros"
