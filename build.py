# build.py — Weather Mod
# Адаптовано під структуру: python/gui/mods/ + Scaleform SWF

import argparse
import datetime
import json
import logging
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import zipfile
from typing import Optional

try:
    import psutil
except ImportError:
    raise ImportError("psutil is not installed. Run 'pip install psutil'.")


MAP_THUMB_IDS = [
    '01_karelia', '02_malinovka', '04_himmelsdorf', '05_prohorovka', '06_ensk',
    '07_lakeville', '08_ruinberg', '10_hills', '11_murovanka', '13_erlenberg',
    '14_siegfried_line', '17_munchen', '18_cliff', '19_monastery', '23_westfeld',
    '28_desert', '29_el_hallouf', '31_airfield', '33_fjord', '34_redshire',
    '35_steppes', '36_fishing_bay', '37_caucasus', '38_mannerheim_line',
    '44_north_america', '45_north_america', '47_canada_a', '59_asia_great_wall',
    '60_asia_miao', '63_tundra', '90_minsk', '95_lost_city_ctf', '99_poland',
    '101_dday', '105_germany', '112_eiffel_tower_ctf', '114_czech', '115_sweden',
    '121_lost_paradise_v', '127_japort', '128_last_frontier_v',
    '208_bf_epic_normandy', '209_wg_epic_suburbia', '210_bf_epic_desert',
    '212_epic_random_valley', '217_er_alaska', '222_er_clime',
]

IMAGE_RE = re.compile(r'\.(png|jpg|jpeg)$', re.I)
GOOD_IMAGE_HINTS = (
    'minimap', 'preview', 'loading', 'map', 'maps', 'arena', 'battle_loading',
    'thumbnail', 'thumb', 'screen', 'screenshot', 'icons',
)
BAD_IMAGE_HINTS = (
    'normal', 'height', 'splat', 'blend', 'mask', 'noise', 'detail', 'terrain',
    'flora', 'water', 'sky', 'shadow', 'lightmap', 'ao', 'color_grading', 'lut',
)
COMMON_INSTALL_DIRS = (
    'World_of_Tanks_EU',
    'World_of_Tanks',
    'Games/World_of_Tanks_EU',
    'Games/World_of_Tanks',
    'Wargaming/World_of_Tanks_EU',
    'Wargaming/World_of_Tanks',
    'Program Files/World_of_Tanks_EU',
    'Program Files/World_of_Tanks',
    'Program Files (x86)/World_of_Tanks_EU',
    'Program Files (x86)/World_of_Tanks',
)


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


def normalize_path(path):
    if not path:
        return None
    return pathlib.Path(os.path.expandvars(os.path.expanduser(str(path)))).resolve()


def is_game_folder(path):
    return bool(path and (path / 'res' / 'packages').is_dir())


def iter_parent_dirs(path):
    path = normalize_path(path)
    seen = set()
    while path and str(path).lower() not in seen:
        seen.add(str(path).lower())
        yield path
        if path.parent == path:
            break
        path = path.parent


def iter_windows_drives():
    for letter in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
        root = pathlib.Path(letter + ':/')
        if root.is_dir():
            yield root


def find_game_folder(config_path: Optional[str]) -> Optional[pathlib.Path]:
    candidates = []
    env_path = os.environ.get('WOT_FOLDER')
    if env_path:
        candidates.append(env_path)
    if config_path:
        candidates.append(config_path)
    candidates.extend(iter_parent_dirs(pathlib.Path.cwd()))
    for drive in iter_windows_drives():
        for rel in COMMON_INSTALL_DIRS:
            candidates.append(drive / rel)

    seen = set()
    for candidate in candidates:
        path = normalize_path(candidate)
        if not path:
            continue
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if is_game_folder(path):
            return path
    return None


def detect_game_version(game_folder: Optional[pathlib.Path], configured: Optional[str]) -> str:
    env_version = os.environ.get('WOT_VERSION')
    if env_version:
        return env_version
    if configured:
        return configured
    if game_folder is None:
        return ''
    mods_dir = game_folder / 'mods'
    if not mods_dir.is_dir():
        return ''
    versions = [p.name for p in mods_dir.iterdir() if p.is_dir()]
    versions.sort(reverse=True)
    return versions[0] if versions else ''


def score_image_member(name: str, map_id: str) -> int:
    low = name.lower().replace('\\', '/')
    if not IMAGE_RE.search(low):
        return -9999
    score = 0
    if map_id.lower() in low:
        score += 50
    for hint in GOOD_IMAGE_HINTS:
        if hint in low:
            score += 10
    for hint in BAD_IMAGE_HINTS:
        if hint in low:
            score -= 30
    if '/gui/' in low:
        score += 30
    if '/spaces/' in low:
        score += 5
    if low.endswith('.png'):
        score += 5
    if 'hd' in low:
        score -= 3
    return score


def find_map_pkg(packages_dir: pathlib.Path, map_id: str) -> Optional[pathlib.Path]:
    exact = packages_dir / f'{map_id}.pkg'
    if exact.is_file():
        return exact
    candidates = []
    for fp in packages_dir.glob(f'{map_id}*.pkg'):
        low = fp.name.lower()
        if '_hd' not in low:
            candidates.append(fp)
    candidates.sort(key=lambda p: p.name)
    return candidates[0] if candidates else None


def extract_one_map_thumb(packages_dir: pathlib.Path, out_dir: pathlib.Path, map_id: str) -> bool:
    pkg = find_map_pkg(packages_dir, map_id)
    if not pkg:
        return False
    try:
        with zipfile.ZipFile(str(pkg), 'r') as zf:
            best_name = None
            best_score = -9999
            for name in zf.namelist():
                score = score_image_member(name, map_id)
                if score > best_score:
                    best_score = score
                    best_name = name
            if not best_name or best_score < 0:
                return False
            data = zf.read(best_name)
            if not data:
                return False
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f'{map_id}.png').write_bytes(data)
            logger.debug('Map thumb: %s <- %s', map_id, best_name)
            return True
    except Exception as e:
        logger.debug('Map thumb skipped: %s (%s)', map_id, e)
        return False


def extract_map_thumbs(game_folder: Optional[pathlib.Path], res_root: pathlib.Path) -> None:
    if game_folder is None:
        logger.warning('Map thumbs skipped: game folder not found. CI builds need prepacked resources/in/gui/maps/icons/weather/maps/*.png')
        return
    packages_dir = game_folder / 'res' / 'packages'
    if not packages_dir.is_dir():
        logger.warning('Map thumbs skipped: packages folder not found: %s', packages_dir)
        return
    out_dir = res_root / 'gui' / 'maps' / 'icons' / 'weather' / 'maps'
    ok = 0
    for map_id in MAP_THUMB_IDS:
        if extract_one_map_thumb(packages_dir, out_dir, map_id):
            ok += 1
    logger.info('Map thumbs extracted: %s/%s -> %s', ok, len(MAP_THUMB_IDS), out_dir)


def build_python(config: AppConfig) -> None:
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
    parser.add_argument('--ingame', action='store_true', help='Copy to game directory.')
    parser.add_argument('--distribute', action='store_true', help='Create distributable zip.')
    parser.add_argument('--run', action='store_true', help='Run the game after build.')
    args = parser.parse_args()

    config_path = pathlib.Path('build.json')
    if not config_path.is_file():
        raise FileNotFoundError('build.json not found')
    with config_path.open('r', encoding='utf-8') as f:
        config = AppConfig(json.load(f))

    game_folder = find_game_folder(config.game.folder)
    game_version = detect_game_version(game_folder, config.game.version)
    if (args.ingame or args.run) and game_folder is None:
        raise ValueError('Game folder not found. Set WOT_FOLDER or build.json game.folder.')
    if not game_version and (args.ingame or args.distribute):
        raise ValueError('Game version not configured and could not be detected from mods/ folder.')
    if game_folder:
        logger.info('Game folder: %s', game_folder)
    else:
        logger.warning('Game folder not found; packaging without extracting map thumbnails from res/packages.')
    if game_version:
        logger.info('Game version: %s', game_version)

    temp_dir = pathlib.Path('temp')
    build_dir = pathlib.Path('build')
    for d in (temp_dir, build_dir):
        if d.is_dir():
            shutil.rmtree(d)
        d.mkdir()

    logger.info("Building...")
    build_python(config)

    package_name = f'{config.info.id}_{config.info.version}.wotmod'
    logger.info("Packaging: %s", package_name)

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

    copytree('python', str(temp_dir / 'res/scripts/client'), ignore=shutil.ignore_patterns('*.py'))

    if pathlib.Path('resources/in').is_dir():
        copytree('resources/in', str(temp_dir / 'res'))
        logger.info('Resources copied: resources/in -> res/')

    extract_map_thumbs(game_folder, temp_dir / 'res')

    gui_src = temp_dir / 'res' / 'gui'
    if gui_src.is_dir():
        copytree(str(gui_src), str(temp_dir / 'res/gui/flash/gui'))
        logger.info('GUI resources duplicated: res/gui -> res/gui/flash/gui/')

    swf_src = pathlib.Path('as3/bin/WeatherPanel.swf')
    if not swf_src.is_file():
        raise FileNotFoundError('SWF not found: as3/bin/WeatherPanel.swf. Build AS3 first with Flex/mxmlc.')
    swf_root = temp_dir / 'res' / 'gui' / 'flash'
    swf_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(swf_src), str(swf_root / 'WeatherPanel.swf'))
    swf_compat = swf_root / 'weather'
    swf_compat.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(swf_src), str(swf_compat / 'WeatherPanel.swf'))
    logger.info('SWF copied: WeatherPanel.swf (%s bytes) -> res/gui/flash/ and res/gui/flash/weather/', swf_src.stat().st_size)

    zip_folder(str(temp_dir), str(build_dir / package_name))
    logger.info("Created: %s", build_dir / package_name)

    if args.ingame:
        mods_dir = game_folder / 'mods' / game_version
        if not mods_dir.is_dir():
            raise FileNotFoundError(f'Mods folder not found: {mods_dir}')
        for proc in psutil.process_iter(['name', 'pid']):
            if proc.info['name'] and 'worldoftanks' in proc.info['name'].lower():
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

    if args.distribute:
        logger.info("Creating distribution archive...")
        dist_dir = temp_dir / 'distribute'
        dist_mods_dir = dist_dir / 'mods' / game_version
        dist_mods_dir.mkdir(parents=True)
        shutil.copy2(str(build_dir / package_name), str(dist_mods_dir))

        if pathlib.Path('resources/out').is_dir():
            copytree('resources/out', str(dist_dir))

        zip_name = f'{config.info.id}_{config.info.version}.zip'
        zip_folder(str(dist_dir), str(build_dir / zip_name))
        logger.info("Distribution: %s", build_dir / zip_name)

    cleanup = [temp_dir]
    cleanup.extend(pathlib.Path('python').rglob('*.pyc'))
    for p in cleanup:
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file():
            p.unlink(missing_ok=True)

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
