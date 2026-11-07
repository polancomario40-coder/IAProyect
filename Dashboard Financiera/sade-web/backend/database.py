"""
database.py — Conexión a SQL Server via pyodbc
Usa variables de entorno definidas en .env
"""
from contextlib import contextmanager
from typing import Generator
import pyodbc
from pydantic_settings import BaseSettings


from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"

class Settings(BaseSettings):
    DB_SERVER: str = "localhost"
    DB_DATABASE: str = "Financiera"
    DB_USERNAME: str = "sa"
    DB_PASSWORD: str = ""
    DB_DRIVER: str = "ODBC Driver 17 for SQL Server"
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    class Config:
        env_file = str(ENV_PATH)
        env_file_encoding = "utf-8"


settings = Settings()


def _resolve_driver(preferred: str) -> str:
    installed = pyodbc.drivers()
    if preferred in installed:
        return preferred
    for candidate in (
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "ODBC Driver 11 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    ):
        if candidate in installed:
            return candidate
    return preferred


def get_connection_string() -> str:
    driver = _resolve_driver(settings.DB_DRIVER)
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={settings.DB_SERVER};"
        f"DATABASE={settings.DB_DATABASE};"
        f"UID={settings.DB_USERNAME};"
        f"PWD={settings.DB_PASSWORD};"
        "TrustServerCertificate=yes;"
        "Timeout=30;"
    )


def test_connection() -> bool:
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:
        return False


@contextmanager
def get_db() -> Generator[pyodbc.Connection, None, None]:
    """
    Context manager que proporciona una conexión a SQL Server.
    Se cierra automáticamente al terminar el bloque 'with'.
    Usa autocommit=True para evitar bloqueos y transacciones implícitas en consultas.
    """
    conn = pyodbc.connect(get_connection_string(), autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


def execute_sp(sp_name: str, *args) -> list[dict]:
    """
    Ejecuta un Stored Procedure y retorna el primer result-set
    como lista de diccionarios.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        placeholders = ", ".join(["?" for _ in args])
        cursor.execute(f"EXEC dbo.{sp_name} {placeholders}", *args)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]


def execute_sp_multi(sp_name: str, *args) -> list[list[dict]]:
    """
    Ejecuta un SP que retorna múltiples result-sets.
    Retorna una lista de listas de diccionarios (uno por result-set).
    """
    results = []
    with get_db() as conn:
        cursor = conn.cursor()
        placeholders = ", ".join(["?" for _ in args])
        cursor.execute(f"EXEC dbo.{sp_name} {placeholders}", *args)

        while True:
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                results.append([dict(zip(columns, row)) for row in rows])
            if not cursor.nextset():
                break

    return results
