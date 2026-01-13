import argparse
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def delete_backup_files(backup_file, dry_run=True):
    """
    Удаляет файл бэкапа и связанные файлы (.log, .notes).

    Args:
        backup_file: Path объект файла бэкапа
        dry_run: Если True, только показывает что будет удалено

    Returns:
        Размер освобождённого места в байтах
    """
    # Ищем связанные файлы
    # Из "vzdump-qemu-100-2025_01_01-01_00_00.vma.zst"
    # получаем "vzdump-qemu-100-2025_01_01-01_00_00"
    base_name = backup_file.name.replace('.vma.zst', '')

    related_files = [
        backup_file,  # сам архив .vma.zst
        backup_file.parent / f"{base_name}.log",  # лог файл
        backup_file.parent / f"{backup_file.name}.notes"  # файл заметок
    ]

    total_size = 0

    for file in related_files:
        if file.exists():
            size = file.stat().st_size
            total_size += size

            if dry_run:
                print(f"    [DRY RUN] Удалить: {file.name}")
            else:
                print(f"    Удаляю: {file.name}")
                file.unlink()  # Удаляем файл

    return total_size


def parse_backup_filename(filename):
    """Парсит имя файла бэкапа и возвращает информацию."""
    
    pattern = r'vzdump-(\w+)-(\d+)-(\d{4})_(\d{2})_(\d{2})-(\d{2})_(\d{2})_(\d{2})'
    
    match = re.match(pattern, filename)
    
    if not match:
        return None
    
    vm_type = match.group(1)  # qemu или lxc
    vm_id = int(match.group(2))  # ID виртуальной машины
    
    year = int(match.group(3))
    month = int(match.group(4))
    day = int(match.group(5))
    hour = int(match.group(6))
    minute = int(match.group(7))
    second = int(match.group(8))
    
    timestamp = datetime(year, month, day, hour, minute, second)
    
    return {
        'vm_type': vm_type,
        'vm_id': vm_id,
        'timestamp': timestamp
    }




def main():
    parser = argparse.ArgumentParser(
        description='Утилита для очистки старых бэкапов Proxmox VE'
    )
    
    parser.add_argument(
        'backup_dir',
        help='Путь к директории с бэкапами'
    )

    parser.add_argument(
        '--keep', '-k',
        type=int,
        default=3,
        help='Сколько последних бэкапов оставить для каждой VM (по умолчанию: 3)'
    )

    parser.add_argument(
        '--execute', '-e',
        action='store_true',
        help='Реально удалить файлы (без этого флага - только показать)'
    )

    args = parser.parse_args()
    
    backup_path = Path(args.backup_dir)

    if not backup_path.exists():
        print(f"Дериктории {backup_path} не существует")
        return 1
    
    if not backup_path.is_dir():
        print(f"Это не дериктория {backup_path}")
        return 1
    
    print(f"Дериктория существет")

    backup_files = list(backup_path.glob("*.vma.zst"))
    print(f"Найдено файлов бэкапов: {len(backup_files)}")

    backups_by_vm = defaultdict(list)


    for file in backup_files:
        info = parse_backup_filename(file.name)
        if info:
            backups_by_vm[info['vm_id']].append({
                'file': file,
                'info': info
            })

    print("\nБэкапов по VM:")
    for vm_id in sorted(backups_by_vm.keys()):
        backups = backups_by_vm[vm_id]
        print(f"  VM {vm_id}: {len(backups)} бэкапов")

    old_backups = []

    for vm_id, backups in backups_by_vm.items():
        backups.sort(key=lambda b: b['info']['timestamp'], reverse=True)

        if len(backups) > args.keep:
            old_backups.extend(backups[args.keep:])

    print(f"\n Найдено {len(old_backups)} старых бэкапов для удаления")
    print(f"   (оставляем последние {args.keep} для каждой VM)\n")

    total_freed = 0  # Общий размер освобождённого места

    for backup in old_backups:
        info = backup['info']
        file = backup['file']
        print(f"  VM {info['vm_id']} | {info['timestamp']} | {file.name}")

        # Удаляем файлы (или показываем что будет удалено)
        freed = delete_backup_files(file, dry_run=not args.execute)
        total_freed += freed

    # Показываем сколько места освободили
    if total_freed > 0:
        # Форматируем размер в GB
        freed_gb = total_freed / (1024 ** 3)
        mode = "будет освобождено" if not args.execute else "освобождено"
        print(f"\n💾 Всего {mode}: {freed_gb:.2f} GB")

    if not args.execute:
        print("\n⚠️  Это был пробный запуск (dry-run)!")
        print("   Для реального удаления используйте флаг --execute")


if __name__ == "__main__":
    main()