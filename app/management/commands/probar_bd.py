"""Comprueba la conexión con SQL Server.

Uso:  python manage.py probar_bd
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from app.models import BorradoNoPermitido, Categoria, Marca, Permiso, Rol


class Command(BaseCommand):
    help = 'Comprueba que Django se conecta a la base de datos NapoBeauty en SQL Server.'

    def handle(self, *args, **options):
        ajustes = connection.settings_dict
        self.stdout.write(f"Conectando a {ajustes['HOST']} / {ajustes['NAME']} ...")
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT @@SERVERNAME, DB_NAME(), SUSER_SNAME()')
                servidor, base, usuario = cursor.fetchone()
        except Exception as error:
            raise CommandError(f'No se pudo conectar: {error}')

        self.stdout.write(self.style.SUCCESS(f'Conectado a {servidor}, base {base}, usuario {usuario}'))
        self.stdout.write(f'  Roles:      {Rol.objects.count()}  ({", ".join(Rol.objects.values_list("nombre", flat=True))})')
        self.stdout.write(f'  Permisos:   {Permiso.objects.count()}')
        self.stdout.write(f'  Categorías: {Categoria.objects.count()}')
        self.stdout.write(f'  Marcas:     {Marca.objects.count()}')

        try:
            Marca.objects.filter(pk=-1).delete()
        except BorradoNoPermitido:
            self.stdout.write(self.style.SUCCESS('  Borrado bloqueado correctamente (solo se puede deshabilitar).'))
