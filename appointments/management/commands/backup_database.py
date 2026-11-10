from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ._sqlite_backup import create_database_copy, get_database_path


class Command(BaseCommand):
	help = "Crea y valida una copia consistente de la base de datos SQLite."

	def add_arguments(self, parser):
		parser.add_argument(
			"--output",
			required=True,
			type=Path,
			help="Ruta nueva donde guardar la copia SQLite.",
		)

	def handle(self, *args, **options):
		source = get_database_path()
		destination = options["output"].expanduser().resolve()
		if not source.is_file():
			raise CommandError(f"No existe la base de datos configurada: {source}")
		create_database_copy(source, destination)
		self.stdout.write(self.style.SUCCESS(f"Copia verificada: {destination}"))
