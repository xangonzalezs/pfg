"""
PFG: Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de
la técnica en ejercicios posturales. UNED

Módulo de apertura y control de la conexión con la base de datos.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from core.persistence import schema

# Ubicación de la base de datos dentro del proyecto.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = _PROJECT_ROOT / "data" / "handstand.db"

# Ruta reservada para una base de datos en memoria, útil en las pruebas.
IN_MEMORY = ":memory:"


class DatabaseError(Exception):
    # La base de datos no pudo abrirse o una operación falló.

    pass


def utc_now() -> str:
    # Instante actual en ISO-8601 con zona. formato en que se persisten las marcas.

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    # Conexión única a la base de datos, con su esquema garantizado.

    def __init__(self, path: Path | str = DEFAULT_DATABASE_PATH) -> None:
        self._path = path if path == IN_MEMORY else Path(path)
        self._connection: sqlite3.Connection | None = None

    @property
    def path(self) -> Path | str:
        # Archivo que respalda la base de datos.

        return self._path

    @property
    def is_open(self) -> bool:
        # Indica si la conexión está abierta.

        return self._connection is not None

    @property
    def connection(self) -> sqlite3.Connection:
        # Conexión viva, o DatabaseError si no se ha abierto.

        if self._connection is None:
            raise DatabaseError("La base de datos no está abierta.")
        return self._connection

    def open(self) -> None:
        # Abre la conexión y crea el esquema si no existe.

        if self._connection is not None:
            return

        if isinstance(self._path, Path):
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                raise DatabaseError(
                    f"No se puede crear el directorio de la base de datos "
                    f"{self._path.parent}: {error}"
                ) from error

        try:
            connection = sqlite3.connect(
                self._path if self._path == IN_MEMORY else str(self._path)
            )
        except sqlite3.Error as error:
            raise DatabaseError(
                f"No se puede abrir la base de datos {self._path}: {error}"
            ) from error

        connection.row_factory = sqlite3.Row
        self._configure(connection)
        self._connection = connection
        self._create_schema()

    def close(self) -> None:
        # Cierra la conexión. Puede invocarse más de una vez.

        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        # Agrupa varias escrituras: se aplican todas o ninguna.

        connection = self.connection
        try:
            with connection:
                yield connection
        except sqlite3.Error as error:
            raise DatabaseError(f"Operación rechazada: {error}") from error

    def __enter__(self) -> "Database":
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _configure(self, connection: sqlite3.Connection) -> None:
        # SQLite desactiva la integridad referencial por defecto porconexión. 
        # sin esto los ON DELETE del esquema no se aplicarían.

        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA user_version = {schema.SCHEMA_VERSION}")

    def _create_schema(self) -> None:
        # Crea tablas e índices.
        # abrir una base de datos ya poblada no la altera.

        try:
            with self.transaction() as connection:
                for statement in schema.TABLES + schema.INDEXES:
                    connection.execute(statement)
        except DatabaseError as error:
            raise DatabaseError(
                f"No se puede crear el esquema en {self._path}: {error}"
            ) from error

    @property
    def schema_version(self) -> int:
        # Versión del esquema registrada en el propio archivo.

        row = self.connection.execute("PRAGMA user_version").fetchone()
        return int(row[0])