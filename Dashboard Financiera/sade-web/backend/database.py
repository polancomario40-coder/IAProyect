"""
database.py — Conexión a SQL Server via pyodbc
Usa variables de entorno definidas en .env
"""
from contextlib import contextmanager
from typing import Generator
import pyodbc
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DB_SERVER: str = "localhost"
    DB_DATABASE: str = "Financiera"
    DB_USERNAME: str = "sa"
    DB_PASSWORD: str = ""
    DB_DRIVER: str = "ODBC Driver 17 for SQL Server"
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


def get_connection_string() -> str:
    return (
        f"DRIVER={{{settings.DB_DRIVER}}};"
        f"SERVER={settings.DB_SERVER};"
        f"DATABASE={settings.DB_DATABASE};"
        f"UID={settings.DB_USERNAME};"
        f"PWD={settings.DB_PASSWORD};"
        "TrustServerCertificate=yes;"
        "Connection Timeout=30;"
    )


@contextmanager
def get_db() -> Generator[pyodbc.Connection, None, None]:
    """
    Context manager que proporciona una conexión a SQL Server.
    Se cierra automáticamente al terminar el bloque 'with'.

    Uso:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
    """
    conn = pyodbc.connect(get_connection_string(), autocommit=False)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
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
