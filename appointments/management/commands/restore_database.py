from datetime import datetime
from pathlib import Path
import tempfile
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from ._sqlite_backup import create_database_copy, get_database_path, validate_database


class Command(BaseCommand):
	help = "Restaura una copia SQLite validada y conserva una copia previa."

	def add_arguments(self, parser):
		parser.add_argument(
			"--input",
			required=True,
			type=Path,
			help="Archivo SQLite de origen.",
		)
		parser.add_argument(
			"--confirm",
			action="store_true",
			help="Confirma que se reemplazará la base de datos configurada.",
		)

	def handle(self, *args, **options):
		if not options["confirm"]:
			raise CommandError("La restauración requiere --confirm.")

		source = options["input"].expanduser().resolve()
		database = get_database_path()
		if source == database:
			raise CommandError("El archivo de respaldo no puede ser la base activa.")
		validate_database(source)
		if not database.is_file():
			raise CommandError(f"No existe la base de datos configurada: {database}")

		timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
		safety_copy = database.with_name(
			f"{database.stem}.pre-restore-{timestamp}{database.suffix}"
		)
		create_database_copy(database, safety_copy)

		descriptor, temporary_name = tempfile.mkstemp(
			prefix=f".{database.name}.restore.",
			suffix=".tmp",
			dir=database.parent,
		)
		os.close(descriptor)
		temporary = Path(temporary_name)
		temporary.unlink()
		try:
			create_database_copy(source, temporary)
			connection.close()
			sidecars = [
				Path(f"{database}-wal"),
				Path(f"{database}-shm"),
				Path(f"{database}-journal"),
			]
			existing_sidecars = [path for path in sidecars if path.exists()]
			if existing_sidecars:
				raise CommandError(
					"Cierra la aplicación antes de restaurar; SQLite aún tiene "
					"archivos auxiliares abiertos: "
					+ ", ".join(str(path) for path in existing_sidecars)
				)
			os.replace(temporary, database)
		except Exception:
			temporary.unlink(missing_ok=True)
			raise

		self.stdout.write(
			self.style.SUCCESS(
				f"Base restaurada desde {source}. Copia previa conservada en {safety_copy}."
			)
		)
