# -*- coding: utf-8 -*-
"""
DAAPI-міст між Flash (WeatherMediator.as) та weather_controller.
"""

try:
    from gui.Scaleform.framework.entities.View import View as AbstractLobbyView
    IN_GAME = True
except ImportError:
    try:
        from gui.Scaleform.framework.entities.BaseDAAPIModule import BaseDAAPIModule as AbstractLobbyView
        IN_GAME = True
    except ImportError:
        try:
            from gui.Scaleform.daapi.view.lobby.AbstractLobbyView import AbstractLobbyView
            IN_GAME = True
        except ImportError:
            IN_GAME = False
            class AbstractLobbyView(object):
                def __init__(self, *args, **kw): pass
                def _populate(self): pass
                def _dispose(self): pass

from weather.controller import (
    g_controller,
    PRESET_ORDER,
    PRESET_LABELS,
    PRESET_GUIDS,
    DEFAULT_WEIGHT,
)

import logging
import os
import re
import zipfile

LOG = logging.getLogger('weather_mod')

_active_window = None
_runtime_thumbs_ready = False
_runtime_thumb_paths = {}

PRESET_PREVIEW = {
    'standard': 'img://gui/maps/icons/pro.environment/default.png',
    'midnight': 'img://gui/maps/icons/pro.environment/15755E11.4090266B.594778B6.B233C12C.png',
    'overcast': 'img://gui/maps/icons/pro.environment/56BA3213.40FFB1DF.125FBCAD.173E8347.png',
    'sunset':   'img://gui/maps/icons/pro.environment/6DEE1EBB.44F63FCC.AACF6185.7FBBC34E.png',
    'midday':   'img://gui/maps/icons/pro.environment/BF040BCB.4BE1D04F.7D484589.135E881B.png',
}

IMAGE_RE = re.compile(r'\.(png|jpg|jpeg)$', re.I)
GOOD_IMAGE_HINTS = (
    '/gui/', 'gui/', 'maps/icons', 'map_icons', 'map/list', 'map/stats',
    'minimap', 'preview', 'loading', 'battle_loading', 'thumbnail', 'thumb',
    'screen', 'screenshot', 'arena_screen',
)
BAD_IMAGE_HINTS = (
    'normal', 'height', 'splat', 'blend', 'mask', 'noise', 'detail', 'terrain',
    'flora', 'water', 'sky', 'shadow', 'lightmap', 'ao', 'color_grading', 'lut',
    'density', 'alpha', 'specular', 'roughness', 'metallic', 'atlas', 'decal',
    'lod', 'visibility', 'collision', 'outland', 'cascade', 'tile_map',
)


def _file_url(path):
    try:
        path = os.path.abspath(path).replace('\\', '/')
        return 'file:///' + path
    except Exception:
        return path


def _map_icon(map_id):
    path = _runtime_thumb_paths.get(map_id)
    if path and os.path.isfile(path):
        return _file_url(path)
    return ''


MAP_REGISTRY = [
    ('01_karelia',             u'Карелія'),
    ('02_malinovka',           u'Малинівка'),
    ('04_himmelsdorf',         u'Хіммельсдорф'),
    ('05_prohorovka',          u'Прохорівка'),
    ('06_ensk',                u'Єнськ'),
    ('07_lakeville',           u'Ласвілль'),
    ('08_ruinberg',            u'Руїнберг'),
    ('10_hills',               u'Копальні'),
    ('11_murovanka',           u'Мурованка'),
    ('13_erlenberg',           u'Ерленберг'),
    ('14_siegfried_line',      u'Лінія Зигфріда'),
    ('17_munchen',             u'Мюнхен'),
    ('18_cliff',               u'Круча'),
    ('19_monastery',           u'Монастир'),
    ('23_westfeld',            u'Вестфілд'),
    ('28_desert',              u'Піщана ріка'),
    ('29_el_hallouf',          u'Ель-Халлуф'),
    ('31_airfield',            u'Летовище'),
    ('33_fjord',               u'Фіорди'),
    ('34_redshire',            u'Редшир'),
    ('35_steppes',             u'Степи'),
    ('36_fishing_bay',         u'Рибальська бухта'),
    ('37_caucasus',            u'Кавказ'),
    ('38_mannerheim_line',     u'Лінія Маннергейма'),
    ('44_north_america',       u'Лайв Окс'),
    ('45_north_america',       u'Хайвей'),
    ('47_canada_a',            u'Перлинна річка'),
    ('59_asia_great_wall',     u'Велика стіна'),
    ('60_asia_miao',           u'Тихий берег'),
    ('63_tundra',              u'Тундра'),
    ('90_minsk',               u'Мінськ'),
    ('95_lost_city_ctf',       u'Загублене місто'),
    ('99_poland',              u'Студзянки'),
    ('101_dday',               u'Нормандія (D-Day)'),
    ('105_germany',            u'Берлін'),
    ('112_eiffel_tower_ctf',   u'Париж'),
    ('114_czech',              u'Промзона'),
    ('115_sweden',             u'Кордон імперії'),
    ('121_lost_paradise_v',    u'Перевал'),
    ('127_japort',             u'Стара гавань'),
    ('128_last_frontier_v',    u'Фата-моргана'),
    ('208_bf_epic_normandy',   u'Оверлорд'),
    ('209_wg_epic_suburbia',   u'Крафтверк'),
    ('210_bf_epic_desert',     u'Застава'),
    ('212_epic_random_valley', u'Долина'),
    ('217_er_alaska',          u'Клондайк'),
    ('222_er_clime',           u'Вайдпарк'),
]


def _norm_path(path):
    try:
        return os.path.abspath(os.path.normpath(path))
    except Exception:
        return path


def _is_game_folder(path):
    return bool(path and os.path.isdir(os.path.join(path, 'res', 'packages')))


def _find_game_folder():
    candidates = []
    try:
        candidates.append(os.getcwd())
    except Exception:
        pass
    try:
        candidates.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    except Exception:
        pass
    try:
        import BigWorld
        pref = BigWorld.wg_getPreferencesFilePath()
        if pref:
            candidates.append(os.path.dirname(pref))
    except Exception:
        pass

    expanded = []
    for c in candidates:
        c = _norm_path(c)
        while c and c not in expanded:
            expanded.append(c)
            parent = os.path.dirname(c)
            if parent == c:
                break
            c = parent

    for root in expanded:
        if _is_game_folder(root):
            return root

    for letter in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
        drive = letter + ':\\'
        if not os.path.isdir(drive):
            continue
        for rel in ('World_of_Tanks_EU', 'World_of_Tanks', 'Games\\World_of_Tanks_EU', 'Games\\World_of_Tanks'):
            p = os.path.join(drive, rel)
            if _is_game_folder(p):
                return p
    return None


def _score_image_member(name, map_id):
    low = name.lower().replace('\\', '/')
    if not IMAGE_RE.search(low):
        return -9999
    if '.dds.' in low or low.endswith('.dds'):
        return -9999

    # Main safety rule: the file must belong to this exact arena.
    # Otherwise gui-part*.pkg can return generic posters/schemes for unrelated maps.
    if map_id.lower() not in low:
        return -9999

    # Never use world/terrain PNGs. They are masks/heightmaps, not UI previews.
    if '/spaces/' in low or low.startswith('spaces/') or '/content/' in low or low.startswith('content/') or low.startswith('maps/'):
        return -9999

    score = 40
    good_hit = False
    for hint in GOOD_IMAGE_HINTS:
        if hint in low:
            good_hit = True
            score += 25
    for hint in BAD_IMAGE_HINTS:
        if hint in low:
            score -= 80

    if not good_hit:
        return -9999
    if low.endswith('.png'):
        score += 10
    if low.endswith('.jpg') or low.endswith('.jpeg'):
        score += 5
    return score


def _iter_candidate_pkgs(packages_dir, map_id):
    result = []
    try:
        names = os.listdir(packages_dir)
    except Exception:
        return result

    for name in sorted(names):
        low = name.lower()
        if low.startswith('gui-part') and low.endswith('.pkg'):
            result.append(os.path.join(packages_dir, name))

    exact = os.path.join(packages_dir, map_id + '.pkg')
    if os.path.isfile(exact):
        result.append(exact)

    for name in sorted(names):
        low = name.lower()
        if low.startswith(map_id.lower()) and low.endswith('.pkg') and '_hd' not in low:
            path = os.path.join(packages_dir, name)
            if path not in result:
                result.append(path)
    return result


def _find_best_image_in_pkg(pkg, map_id):
    try:
        zf = zipfile.ZipFile(pkg, 'r')
    except Exception:
        return None, None
    try:
        best = None
        best_score = -9999
        for name in zf.namelist():
            s = _score_image_member(name, map_id)
            if s > best_score:
                best_score = s
                best = name
        if not best or best_score < 0:
            return None, None
        return zf.read(best), best
    except Exception:
        return None, None
    finally:
        try:
            zf.close()
        except Exception:
            pass


def _extract_one_runtime_thumb(packages_dir, out_dir, map_id):
    out_path = os.path.join(out_dir, map_id + '.png')
    for pkg in _iter_candidate_pkgs(packages_dir, map_id):
        data, _name = _find_best_image_in_pkg(pkg, map_id)
        if not data:
            continue
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        f = open(out_path, 'wb')
        try:
            f.write(data)
        finally:
            f.close()
        _runtime_thumb_paths[map_id] = out_path
        return True

    if os.path.isfile(out_path):
        try:
            os.remove(out_path)
        except Exception:
            pass
    return False


def _ensure_runtime_map_thumbs():
    global _runtime_thumbs_ready
    if _runtime_thumbs_ready:
        return
    _runtime_thumbs_ready = True
    game_folder = _find_game_folder()
    if not game_folder:
        return
    packages_dir = os.path.join(game_folder, 'res', 'packages')
    out_dir = os.path.join(game_folder, 'res', 'gui', 'maps', 'icons', 'weather', 'maps')
    for map_id, _label in MAP_REGISTRY:
        _extract_one_runtime_thumb(packages_dir, out_dir, map_id)


def _build_presets_for_ui(weights=None):
    weights = weights or {}
    return [
        {
            'id':         pid,
            'label':      PRESET_LABELS.get(pid, pid),
            'guid':       PRESET_GUIDS.get(pid, ''),
            'previewSrc': PRESET_PREVIEW.get(pid, ''),
            'weight':     int(weights.get(pid, DEFAULT_WEIGHT)),
        }
        for pid in PRESET_ORDER
    ]


def _build_hotkey_str(hotkey_dict):
    try:
        key  = hotkey_dict.get('key', 'KEY_F12')
        mods = hotkey_dict.get('mods', [])
        return '+'.join(list(mods) + [key.replace('KEY_', '')])
    except Exception:
        return 'F12'


def _build_payload():
    _ensure_runtime_map_thumbs()
    current_preset = g_controller.getCurrentPreset()
    general = g_controller.getGeneralWeights() or {}

    maps = []
    for map_id, label in MAP_REGISTRY:
        map_weights = g_controller.getMapWeights(map_id) or {}
        maps.append({
            'id': map_id,
            'label': label,
            'thumbSrc': _map_icon(map_id),
            'useGlobal': False,
            'presets': _build_presets_for_ui(map_weights),
        })

    hk = g_controller.getHotkey()
    hotkey_str = _build_hotkey_str(hk)
    hotkey_keys = []
    try:
        import Keys
        key_name = hk.get('key', 'KEY_F12')
        code = getattr(Keys, key_name, 0)
        if code:
            hotkey_keys.append(code)
    except Exception:
        pass

    return {
        'presets': _build_presets_for_ui(general),
        'maps': maps,
        'hotkey': hotkey_str,
        'hotkeyKeys': hotkey_keys,
        'currentPreset': current_preset,
    }


def show_existing_window():
    global _active_window
    win = _active_window
    if win is None:
        return False
    try:
        flash = getattr(win, 'flashObject', None)
        if flash is None:
            _active_window = None
            return False
        flash.as_setData(_build_payload())
        return True
    except Exception:
        _active_window = None
        return False


class WeatherWindowMeta(AbstractLobbyView):

    def __init__(self, *args, **kwargs):
        super(WeatherWindowMeta, self).__init__(*args, **kwargs)
        self._ctrl = g_controller

    def _populate(self):
        global _active_window
        _active_window = self
        super(WeatherWindowMeta, self)._populate()
        try:
            self.flashObject.as_setData(_build_payload())
        except Exception:
            pass

    def py_onPresetSelected(self, mapId, presetId):
        try:
            preset_id = str(presetId) if presetId else 'standard'
            map_id = str(mapId) if mapId else None
            if not map_id:
                self._ctrl.setPreset(preset_id)
            else:
                from weather.controller import apply_preset
                apply_preset(map_id, preset_id)
        except Exception:
            pass

    def py_onWeightChanged(self, mapId, presetId, value):
        try:
            map_id = str(mapId) if mapId else None
            if not map_id:
                weights = self._ctrl.getGeneralWeights() or {}
                weights[str(presetId)] = int(float(value))
                self._ctrl.setGeneralWeights(weights)
            else:
                weights = self._ctrl.getMapWeights(map_id) or {}
                weights[str(presetId)] = int(float(value))
                self._ctrl.setMapWeights(map_id, weights)
        except Exception:
            pass

    def py_onMapSelected(self, mapId):
        pass

    def py_onTabChanged(self, tab):
        pass

    def py_onCloseRequested(self):
        global _active_window
        self._ctrl.on_close_requested()
        _active_window = None
        try:
            self.destroy()
            return
        except Exception:
            pass
        try:
            self._destroy()
            return
        except Exception:
            pass
        try:
            self.onWindowClose()
            return
        except Exception:
            pass

    def py_onHotkeyChanged(self, keyCodes, hotkeyStr):
        try:
            parts = str(hotkeyStr).split('+')
            key = 'KEY_' + parts[-1] if parts else 'KEY_F12'
            mods = parts[:-1] if len(parts) > 1 else []
            self._ctrl.on_hotkey_changed(list(keyCodes or []), str(hotkeyStr))
            from weather.controller import set_hotkey
            set_hotkey(True, mods, key)
        except Exception:
            pass

    def _dispose(self):
        global _active_window
        if _active_window is self:
            _active_window = None
        self._ctrl.on_close_requested()
        super(WeatherWindowMeta, self)._dispose()
