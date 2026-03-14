import os
"""Script seguro para eliminar usuarios no superusuarios.

Este script ahora requiere el argumento `--confirm` para proceder con la
eliminación; sin él solo muestra qué usuarios serían afectados (modo dry-run
por defecto). Esto evita borrados accidentales al ejecutar el script.
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SENNOVA.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Eliminar usuarios no superusuarios (seguro). Requiere --confirm.'
    )
    parser.add_argument('--confirm', action='store_true', help='Confirmar la eliminación')
    parser.add_argument('--dry-run', action='store_true', help='Mostrar usuarios que se eliminarían, sin borrar')
    args = parser.parse_args()

    User = get_user_model()

    if not args.confirm:
        print('No se ha pasado --confirm. Ejecución abortada. Para ver qué se eliminaría use --dry-run. Para proceder, ejecute con --confirm')
        # Show what would be deleted to avoid surprises
        qs = User.objects.filter(is_superuser=False)
        print('No-superusuarios encontrados:', list(qs.values_list('username', flat=True)))
        sys.exit(0)

    print('Usuarios totales antes:', User.objects.count())
    qs = User.objects.filter(is_superuser=False)
    print('No-superusuarios encontrados:', list(qs.values_list('username', flat=True)))

    if args.dry_run:
        print('Dry run activado, no se eliminará nada.')
        return

    for u in list(qs):
        print('Eliminando:', u.username)
        u.delete()

    print('Usuarios totales después:', User.objects.count())


if __name__ == '__main__':
    main()
