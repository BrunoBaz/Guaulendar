import os
import sqlite3
import tempfile
from pathlib import Path

from django.core.management.base import CommandError
from django.db import connection


def get_database_path():
	if connection.settings_dict["ENGINE"] != "django.db.backends.sqlite3":
		raise CommandError("Estos comandos solo funcionan con SQLite.")

	name = str(connection.settings_dict["NAME"])
	if name == ":memory:" or name.startswith("file:"):
		raise CommandError("No se puede respaldar una base SQLite en memoria.")
	return Path(name).resolve()


def validate_database(path):
	if not path.is_file():
		raise CommandError(f"No existe el archivo de base de datos: {path}")
	database = None
	try:
		database = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
		result = database.execute("PRAGMA integrity_check").fetchone()
	except sqlite3.Error as error:
		raise CommandError(f"No se pudo validar la base de datos: {error}") from error
	finally:
		if database is not None:
			database.close()
	if result != ("ok",):
		raise CommandError(f"La comprobación de integridad falló: {result[0]}")


def create_database_copy(source, destination):
	source = Path(source).resolve()
	destination = Path(destination).resolve()
	if source == destination:
		raise CommandError("El destino debe ser distinto de la base de datos de origen.")
	if destination.exists():
		raise CommandError(f"El archivo de destino ya existe: {destination}")

	destination.parent.mkdir(parents=True, exist_ok=True)
	descriptor, temporary_name = tempfile.mkstemp(
		prefix=f".{destination.name}.",
		suffix=".tmp",
		dir=destination.parent,
	)
	os.close(descriptor)
	temporary = Path(temporary_name)
	try:
		source_db = None
		destination_db = None
		try:
			source_db = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)
			destination_db = sqlite3.connect(temporary)
			source_db.backup(destination_db)
		except sqlite3.Error as error:
			raise CommandError(f"No se pudo crear la copia SQLite: {error}") from error
		finally:
			if destination_db is not None:
				destination_db.close()
			if source_db is not None:
				source_db.close()

		validate_database(temporary)
		os.replace(temporary, destination)
	except Exception:
		temporary.unlink(missing_ok=True)
		raise
