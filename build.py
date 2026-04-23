# build.py — Weather Mod
# Адаптовано під структуру: python/gui/mods/ (без Flash/SWF)

import argparse
import datetime
import json
import logging
import os
import pathlib
import random
import shutil
import string
import subprocess
import sys
import time
import zipfile
from typing import Any, Dict, List, Optional, Set

try:
    import psutil
except ImportError:
    raise ImportError("psutil is not installed. Run 'pip install psutil'.")


# --- Logger ---

class ElapsedFormatter(logging.Formatter):
    def __init__(self):
        super().__init__()
        self.start_time = time.time()

    def format(self, record):
        elapsed = datetime.timedelta(seconds=record.created - self.start_time)
        return f"{elapsed.seconds:03d}.{int(elapsed.microseconds/1000):03d} {record.getMessage()}"


def setup_logger():
    handler = logging.StreamHandler()
    handler.setFormatter(ElapsedFormatter())
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    return logger


# --- Config ---

class AppConfig:
    class Software:
        def __init__(self, data):
            self.python: Optional[str] = data.get('python')

    class Game:
        def __init__(self, data):
            self.force: bool = data.get('force', False)
            self.folder: Optional[str] = data.get('folder')
            self.version: Optional[str] = data.get('version')

    class Info:
        def __init__(self, data):
            self.id: Optional[str] = data.get('id')
            self.name: Optional[str] = data.get('name')
            self.description: Optional[str] = data.get('description')
            self.version: Optional[str] = data.get('version')

    def __init__(self, data):
        self.version: int = data.get('version', 0)
        self.software = self.Software(data.get('software', {}))
        self.game = self.Game(data.get('game', {}))
        self.info = self.Info(data.get('info', {}))


# --- Utils ---

def copytree(source, destination, ignore=None):
    src = pathlib.Path(source)
    dst = pathlib.Path(destination)
    dst.mkdir(parents=True, exist_ok=True)
    names = os.listdir(src)
    ignored = ignore(str(src), names) if ignore else set()
    for name in names:
        if name in ignored or '.gitkeep' in name:
            continue
        s = src / name
        d = dst / name
        try:
            if s.is_dir():
                copytree(str(s), str(d), ignore)
            else:
                shutil.copy2(str(s), str(d))
        except (IOError, os.error) as e:
            logger.error("Can't copy %s to %s: %s", s, d, e)


def zip_folder(source, destination, mode='w', compression=zipfile.ZIP_STORED):
    src = pathlib.Path(source)
    now = tuple(datetime.datetime.now().timetuple())[:6]
    with zipfile.ZipFile(destination, mode, compression) as zf:
        for fp in src.rglob('*'):
            arcname = fp.relative_to(src)
            if fp.is_dir():
                info = zipfile.ZipInfo(str(arcname).replace('\\', '/') + '/', now)
                info.compress_type = compression
                zf.writestr(info, '')
            else:
                info = zipfile.ZipInfo(str(arcname).replace('\\', '/'), now)
                info.external_attr = 33206 << 16
                info.compress_type = compression
                zf.writestr(info, fp.read_bytes())


# --- Build Steps ---

def build_python(config: AppConfig) -> None:
    """Компілює .py → .pyc через Python 2.7"""
    python_dir = pathlib.Path('python')
    if not python_dir.exists():
        logger.warning("python/ directory not found, skipping compilation")
        return

    if not config.software.python:
        raise ValueError("Python 2.7 path not configured in build.json")

    for py_file in python_dir.rglob('*.py'):
        try:
            subprocess.check_output(
                [config.software.python, '-m', 'py_compile', str(py_file)],
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8'
            )
            logger.info('Compiled: %s', py_file)
        except subprocess.CalledProcessError as e:
            logger.error('Compile failed: %s\n%s', py_file, e.output)


def main():
    parser = argparse.ArgumentParser(description='Build script for Weather Mod.')
    parser.add_argument('--ingame',    action='store_true', help='Copy to game directory.')
    parser.add_argument('--distribute',action='store_true', help='Create distributable zip.')
    parser.add_argument('--run',       action='store_true', help='Run the game after build.')
    args = parser.parse_args()

    # Load config
    config_path = pathlib.Path('build.json')
    if not config_path.is_file():
        raise FileNotFoundError('build.json not found')
    with config_path.open('r', encoding='utf-8') as f:
        config = AppConfig(json.load(f))

    game_folder  = pathlib.Path(os.environ.get('WOT_FOLDER',  config.game.folder  or ''))
    game_version = os.environ.get('WOT_VERSION', config.game.version or '')
    if not game_folder or not game_version:
        raise ValueError("Game folder or version not configured.")

    # Prepare dirs
    temp_dir  = pathlib.Path('temp')
    build_dir = pathlib.Path('build')
    for d in (temp_dir, build_dir):
        if d.is_dir():
            shutil.rmtree(d)
        d.mkdir()

    # --- Build ---
    logger.info("Building...")
    build_python(config)

    # --- Package ---
    package_name = f'{config.info.id}_{config.info.version}.wotmod'
    logger.info("Packaging: %s", package_name)

    # meta.xml
    meta_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<root>\n'
        f'    <id>{config.info.id}</id>\n'
        f'    <version>{config.info.version}</version>\n'
        f'    <name>{config.info.name}</name>\n'
        f'    <description>{config.info.description}</description>\n'
        '</root>\n'
    )
    (temp_dir / 'meta.xml').write_text(meta_xml, encoding='utf-8')

    # Копіюємо Python .pyc в res/scripts/client/
    # Структура: python/gui/mods/__init__.pyc → res/scripts/client/gui/mods/__init__.pyc
    copytree('python', str(temp_dir / 'res/scripts/client'),
             ignore=shutil.ignore_patterns('*.py'))

    # Якщо є resources/in — копіюємо як res/
    if pathlib.Path('resources/in').is_dir():
        copytree('resources/in', str(temp_dir / 'res'))

    # SWF — копіюємо в res/gui/flash/weather/
    swf_src = pathlib.Path('as3/bin/WeatherPanel.swf')
    if swf_src.is_file():
        swf_dest = temp_dir / 'res' / 'gui' / 'flash' / 'weather'
        swf_dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(swf_src), str(swf_dest / 'WeatherPanel.swf'))
        logger.info('SWF copied: WeatherPanel.swf -> res/gui/flash/weather/')

    # Створюємо .wotmod
    zip_folder(str(temp_dir), str(build_dir / package_name))
    logger.info("Created: %s", build_dir / package_name)

    # --- Ingame copy ---
    if args.ingame:
        mods_dir = game_folder / 'mods' / game_version
        if not mods_dir.is_dir():
            raise FileNotFoundError(f'Mods folder not found: {mods_dir}')
        # Зупиняємо гру якщо запущена
        for proc in psutil.process_iter(['name', 'pid']):
            if 'worldoftanks' in proc.info['name'].lower():
                try:
                    p = psutil.Process(proc.info['pid'])
                    p.terminate()
                    p.wait(timeout=10)
                    logger.info('WoT terminated (pid: %s)', proc.info['pid'])
                except psutil.Error as e:
                    logger.warning("Could not terminate WoT: %s", e)
        dest = mods_dir / package_name
        shutil.copy2(str(build_dir / package_name), str(dest))
        logger.info("Copied to: %s", dest)

    # --- Distribute ---
    if args.distribute:
        logger.info("Creating distribution archive...")
        dist_dir      = temp_dir / 'distribute'
        dist_mods_dir = dist_dir / 'mods' / game_version
        dist_mods_dir.mkdir(parents=True)
        shutil.copy2(str(build_dir / package_name), str(dist_mods_dir))

        # Якщо є resources/out — додаємо в дистрибутив
        if pathlib.Path('resources/out').is_dir():
            copytree('resources/out', str(dist_dir))

        zip_name = f'{config.info.id}_{config.info.version}.zip'
        zip_folder(str(dist_dir), str(build_dir / zip_name))
        logger.info("Distribution: %s", build_dir / zip_name)

    # --- Cleanup ---
    cleanup = [temp_dir]
    cleanup.extend(pathlib.Path('python').rglob('*.pyc'))
    for p in cleanup:
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file():
            p.unlink(missing_ok=True)

    # --- Run ---
    if args.run:
        exe = game_folder / 'worldoftanks.exe'
        if exe.is_file():
            logger.info("Starting WoT...")
            subprocess.Popen([str(exe)])
        else:
            logger.warning("Game executable not found: %s", exe)

    logger.info("Build finished.")


if __name__ == '__main__':
    logger = setup_logger()
    try:
        main()
    except Exception as e:
        logger.exception("Build error: %s", e)
        sys.exit(1)
