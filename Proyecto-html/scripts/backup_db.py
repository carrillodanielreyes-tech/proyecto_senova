"""Backup simple para db.sqlite3.

Coloca este script en `scripts/` y puede ejecutarse manualmente o desde un
programador de tareas. Crea copias con timestamp en `backups/` y mantiene
un número máximo de copias (por defecto 7).
"""
from pathlib import Path
import shutil
import datetime
import os
import sys


def find_project_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / 'manage.py').exists():
            return p
    raise RuntimeError('No se encontró manage.py en el árbol de directorios')


def backup_db(retain: int = 7):
    start = Path(__file__).resolve().parent
    root = find_project_root(start)
    db_path = root / 'db.sqlite3'
    if not db_path.exists():
        print(f'No se encontró la base de datos en {db_path}')
        return 1

    backups_dir = root / 'backups'
    backups_dir.mkdir(exist_ok=True)

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = backups_dir / f'db.sqlite3.{ts}'
    shutil.copy2(db_path, dest)
    print(f'Backup creado: {dest} ({(dest.stat().st_size if dest.exists() else 0)} bytes)')

    # Retención: mantener solo las más recientes
    files = sorted([f for f in backups_dir.iterdir() if f.is_file() and f.name.startswith('db.sqlite3.')], key=lambda x: x.stat().st_mtime, reverse=True)
    if len(files) > retain:
        for f in files[retain:]:
            try:
                f.unlink()
                print(f'Eliminado backup antiguo: {f.name}')
            except Exception as e:
                print(f'No se pudo eliminar {f}: {e}')

    return 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Crear backup de db.sqlite3 con retención')
    parser.add_argument('--retain', type=int, default=7, help='Número de backups a conservar (por defecto 7)')
    args = parser.parse_args()
    sys.exit(backup_db(retain=args.retain))


if __name__ == '__main__':
    main()
