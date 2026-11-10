# Operación y recuperación

## Copias SQLite

La copia contiene la base de datos completa, incluidos datos personales. Guarda el
resultado en una ubicación protegida y separada del equipo que ejecuta la
aplicación. El comando usa la API de respaldo de SQLite y valida la integridad del
archivo antes de finalizar; no sobrescribe archivos existentes.

Desde PowerShell, en la carpeta del proyecto:

```powershell
.\.venv\Scripts\python.exe .\manage.py backup_database --output "E:\Copias\guaulendar-2026-11-10.sqlite3"
```

Programa la ejecución periódica con el Programador de tareas de Windows y rota
copias antiguas según la política de retención que se establezca. Mantén al menos
una copia en otro dispositivo o ubicación protegida.

## Restauración

Detén primero el servidor y cualquier proceso conectado a la base de datos. La
restauración exige confirmación explícita, valida el archivo de entrada y crea
automáticamente una copia de la base activa junto a ella antes de reemplazarla:

```powershell
.\.venv\Scripts\python.exe .\manage.py restore_database --input "E:\Copias\guaulendar-2026-11-10.sqlite3" --confirm
```

Comprueba después el acceso a la aplicación y las migraciones. Conserva tanto la
copia restaurada como la copia `*.pre-restore-*.sqlite3` hasta verificar el
resultado. Los comandos respaldan únicamente la base de datos; si en el futuro se
añaden archivos cargados por usuarios, también habrá que respaldar `MEDIA_ROOT`.

## Auditoría de citas

Los cambios, altas y cierres de citas se registran en el historial de auditoría
del administrador de Django. Los eventos guardan el estado anterior y posterior
de los campos relevantes; los eventos no se pueden crear o eliminar desde el
administrador. Las modificaciones masivas que evitan `Appointment.save()` no
generan eventos.
