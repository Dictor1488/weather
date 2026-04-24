# -*- coding: utf-8 -*-
"""
Extract WoT map preview images from res/packages/*.pkg into mod GUI resources.

Usage:
  python tools/extract_map_thumbs.py
  python tools/extract_map_thumbs.py --game D:/World_of_Tanks_EU

Output:
  resources/in/gui/maps/icons/weather/maps/<map_id>.png

The script can auto-detect the World of Tanks folder. Detection order:
  1. --game argument
  2. WOT_FOLDER environment variable
  3. Current working directory / parent directories
  4. Common install folders on all available Windows drives

A valid game folder must contain:
  res/packages/
"""

from __future__ import print_function

import argparse
import os
import re
import zipfile

MAP_IDS = [
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
GOOD_HINTS = (
    'minimap', 'preview', 'loading', 'map', 'maps', 'arena', 'battle_loading',
    'thumbnail', 'thumb', 'screen', 'screenshot', 'icons',
)
BAD_HINTS = (
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


def is_game_folder(path):
    return bool(path and os.path.isdir(os.path.join(path, 'res', 'packages')))


def normalize_path(path):
    if not path:
        return None
    return os.path.abspath(os.path.normpath(os.path.expandvars(os.path.expanduser(path))))


def iter_parent_dirs(path):
    path = normalize_path(path)
    seen = set()
    while path and path not in seen:
        seen.add(path)
        yield path
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent


def iter_windows_drives():
    # No external dependencies: just test common drive letters.
    for letter in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
        root = letter + ':\\'
        if os.path.isdir(root):
            yield root


def find_game_folder(explicit=None):
    candidates = []

    if explicit:
        candidates.append(explicit)

    env_path = os.environ.get('WOT_FOLDER') or os.environ.get('WOWS_FOLDER')
    if env_path:
        candidates.append(env_path)

    cwd = os.getcwd()
    for parent in iter_parent_dirs(cwd):
        candidates.append(parent)

    for drive in iter_windows_drives():
        for rel in COMMON_INSTALL_DIRS:
            candidates.append(os.path.join(drive, rel))

    seen = set()
    for candidate in candidates:
        candidate = normalize_path(candidate)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if is_game_folder(candidate):
            return candidate
    return None


def score_member(name, map_id):
    low = name.lower().replace('\\', '/')
    if not IMAGE_RE.search(low):
        return -9999

    score = 0
    if map_id.lower() in low:
        score += 50
    for hint in GOOD_HINTS:
        if hint in low:
            score += 10
    for hint in BAD_HINTS:
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


def find_pkg(packages_dir, map_id):
    exact = os.path.join(packages_dir, map_id + '.pkg')
    if os.path.isfile(exact):
        return exact
    candidates = []
    for name in os.listdir(packages_dir):
        low = name.lower()
        if low.startswith(map_id.lower()) and low.endswith('.pkg') and '_hd' not in low:
            candidates.append(os.path.join(packages_dir, name))
    candidates.sort()
    return candidates[0] if candidates else None


def extract_one(packages_dir, out_dir, map_id):
    pkg = find_pkg(packages_dir, map_id)
    if not pkg:
        print('MISS pkg:', map_id)
        return False

    try:
        zf = zipfile.ZipFile(pkg, 'r')
    except Exception as e:
        print('BAD pkg:', pkg, e)
        return False

    best = None
    best_score = -9999
    try:
        for name in zf.namelist():
            s = score_member(name, map_id)
            if s > best_score:
                best_score = s
                best = name

        if not best or best_score < 0:
            print('MISS image:', map_id, 'pkg=', os.path.basename(pkg))
            return False

        data = zf.read(best)
        if not data:
            print('EMPTY image:', map_id, best)
            return False

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        out_path = os.path.join(out_dir, map_id + '.png')
        with open(out_path, 'wb') as f:
            f.write(data)
        print('OK:', map_id, '<-', best)
        return True
    finally:
        zf.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game', default=None, help='World of Tanks folder. Optional; auto-detected when omitted.')
    parser.add_argument('--out', default='resources/in/gui/maps/icons/weather/maps')
    args = parser.parse_args()

    game_folder = find_game_folder(args.game)
    if not game_folder:
        raise SystemExit(
            'World of Tanks folder not found. Pass --game "C:/Games/World_of_Tanks_EU" '
            'or set WOT_FOLDER environment variable.'
        )

    packages_dir = os.path.join(game_folder, 'res', 'packages')
    print('Game folder:', game_folder)
    print('Packages:', packages_dir)

    ok = 0
    for map_id in MAP_IDS:
        if extract_one(packages_dir, args.out, map_id):
            ok += 1
    print('Done: %d/%d extracted' % (ok, len(MAP_IDS)))


if __name__ == '__main__':
    main()
