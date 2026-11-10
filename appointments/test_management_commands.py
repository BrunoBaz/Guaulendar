import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class DatabaseBackupCommandTests(SimpleTestCase):
	def setUp(self):
		self.temp_dir = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp_dir.cleanup)
		self.directory = Path(self.temp_dir.name)
		self.database = self.directory / "current.sqlite3"
		self.backup = self.directory / "backup.sqlite3"
		self._create_database(self.database, "current")
		self._create_database(self.backup, "restored")

	@staticmethod
	def _create_database(path, value):
		database = sqlite3.connect(path)
		try:
			database.execute("CREATE TABLE sample (value TEXT)")
			database.execute("INSERT INTO sample (value) VALUES (?)", [value])
			database.commit()
		finally:
			database.close()

	def test_backup_command_creates_a_valid_sqlite_copy(self):
		destination = self.directory / "generated.sqlite3"

		with patch(
			"appointments.management.commands.backup_database.get_database_path",
			return_value=self.database,
		):
			call_command("backup_database", output=destination)

		database = sqlite3.connect(destination)
		try:
			value = database.execute("SELECT value FROM sample").fetchone()[0]
		finally:
			database.close()
		self.assertEqual(value, "current")

	def test_backup_command_does_not_overwrite_existing_file(self):
		with patch(
			"appointments.management.commands.backup_database.get_database_path",
			return_value=self.database,
		):
			with self.assertRaises(CommandError):
				call_command("backup_database", output=self.backup)

	def test_restore_requires_confirmation_and_keeps_a_safety_copy(self):
		with patch(
			"appointments.management.commands.restore_database.get_database_path",
			return_value=self.database,
		), patch(
			"appointments.management.commands.restore_database.connection.close",
		):
			with self.assertRaises(CommandError):
				call_command(
					"restore_database",
					input=self.backup,
					confirm=False,
				)
			call_command(
				"restore_database",
				input=self.backup,
				confirm=True,
			)

		database = sqlite3.connect(self.database)
		try:
			value = database.execute("SELECT value FROM sample").fetchone()[0]
		finally:
			database.close()
		self.assertEqual(value, "restored")
		safety_copies = list(self.directory.glob("current.pre-restore-*.sqlite3"))
		self.assertEqual(len(safety_copies), 1)
		database = sqlite3.connect(safety_copies[0])
		try:
			original_value = database.execute(
				"SELECT value FROM sample"
			).fetchone()[0]
		finally:
			database.close()
		self.assertEqual(original_value, "current")
