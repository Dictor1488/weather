# -*- coding: utf-8 -*-

import json
import os
import sys
import logging
import traceback

try:
    basestring
except NameError:
    basestring = str

try:
    import BigWorld
    from gui import SystemMessages
    IN_GAME = True
except Exception:
    IN_GAME = False

LOG = logging.getLogger("weather_mod")
LOG.setLevel(logging.INFO)

# ---------------------------------------------------------------------
# ПРОСТИЙ ТЕСТ:
# форсимо один preset для всіх карт
# поміняй на 'midnight' / 'overcast' / 'sunset' якщо треба
# ---------------------------------------------------------------------
FORCED_PRESET = 'midday'

PRESET_GUIDS = {
    "standard": None,
    "midday":   "BF040BCB-4BE1D04F-7D484589-135E881B",
    "sunset":   "6DEE1EBB-44F63FCC-AACF6185-7FBBC34E",
    "overcast": "56BA3213-40FFB1DF-125FBCAD-173E8347",
    "midnight": "15755E11-4090266B-594778B6-B233C12C",
}

PRESET_LABELS = {
    "standard": u"Стандарт",
    "midday":   u"Полдень",
    "sunset":   u"Закат",
    "overcast": u"Пасмурно",
    "midnight": u"Ніч",
}

PRESET_ORDER = ["standard", "midnight", "overcast", "sunset", "midday"]

DEFAULT_CFG = {
    "enabled": True,
    "show_in_battle": True,
    "generalWeights": {k: 0 for k in PRESET_ORDER},
    "mapWeights": {},
    "hotkey": {"enabled": True, "mods": ["KEY_LALT"], "key": "KEY_F12"},
    "iconPosition": {"x": 20, "y": 120},
    "currentPreset": FORCED_PRESET
}

_cfg = {}


def _push_message(text):
    if not IN_GAME:
        return
    try:
        SystemMessages.pushMessage(text, SystemMessages.SM_TYPE.Information)
    except Exception:
        LOG.error('_push_message failed\n%s', traceback.format_exc())


def _ensure_dir(path):
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)


def _deep_update(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_update(dst[k], v)
        else:
            dst[k] = v


def _safe_norm(path):
    try:
        return os.path.normpath(os.path.abspath(path))
    except Exception:
        return path


def _get_possible_game_roots():
    roots = []

    try:
        roots.append(_safe_norm(os.getcwd()))
    except Exception:
        pass

    try:
        exe_path = sys.argv[0]
        if exe_path:
            roots.append(_safe_norm(os.path.dirname(exe_path)))
    except Exception:
        pass

    try:
        # win64 -> game root
        cwd = _safe_norm(os.getcwd())
        roots.append(_safe_norm(os.path.join(cwd, '..')))
    except Exception:
        pass

    try:
        prefs = None
        if IN_GAME and hasattr(BigWorld, 'wg_getPreferencesFilePath'):
            prefs = BigWorld.wg_getPreferencesFilePath()
        if prefs:
            # prefs путь не до папки гри, але хай буде як запасний варіант
            roots.append(_safe_norm(os.path.join(os.path.dirname(prefs), '..', '..', '..', '..')))
    except Exception:
        pass

    # прибираємо дублікати
    uniq = []
    for p in roots:
        if p and p not in uniq:
            uniq.append(p)
    return uniq


def _find_res_mods_dir():
    """
    Шукаємо саме папку виду:
    D:\\World_of_Tanks_EU\\res_mods\\2.2.0.2

    Як у ProTanki:
    Found res_mods: D:\\World_of_Tanks_EU\\res_mods\\2.2.0.2
    """
    candidates = []

    for root in _get_possible_game_roots():
        candidates.append(_safe_norm(os.path.join(root, 'res_mods')))
        candidates.append(_safe_norm(os.path.join(root, '..', 'res_mods')))

    # запасні явні кандидати
    candidates.extend([
        _safe_norm(r'D:\World_of_Tanks_EU\res_mods'),
        _safe_norm(r'C:\Games\World_of_Tanks\res_mods'),
    ])

    checked = []
    for base in candidates:
        if not base or base in checked:
            continue
        checked.append(base)

        if not os.path.isdir(base):
            continue

        try:
            subdirs = []
            for name in os.listdir(base):
                full = os.path.join(base, name)
                if os.path.isdir(full):
                    subdirs.append((name, full))

            # спочатку схоже на версію x.x.x.x
            version_like = []
            for name, full in subdirs:
                if name.count('.') >= 2:
                    version_like.append((name, full))

            version_like.sort(reverse=True)

            if version_like:
                found = version_like[0][1]
                LOG.info('Found res_mods: %s', found)
                return found

            # якщо нема версійних директорій — беремо base
            LOG.info('Found res_mods root without version dir: %s', base)
            return base
        except Exception:
            LOG.error('_find_res_mods_dir: failed while scanning %s\n%s', base, traceback.format_exc())

    LOG.warning('res_mods not found; checked=%s', checked)
    return None


def _get_config_path():
    try:
        if IN_GAME and hasattr(BigWorld, 'wg_getPreferencesFilePath'):
            prefs = BigWorld.wg_getPreferencesFilePath()
            if prefs:
                prefs_dir = os.path.dirname(prefs)
                return _safe_norm(os.path.join(prefs_dir, 'mods', 'weather', 'config.json'))
    except Exception:
        pass
    return _safe_norm(os.path.join(os.getcwd(), 'mods', 'weather', 'config.json'))


CONFIG_PATH = _get_config_path()


def load_config():
    global _cfg
    _cfg = json.loads(json.dumps(DEFAULT_CFG))
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                user_cfg = json.load(f)
            _deep_update(_cfg, user_cfg)
    except Exception:
        LOG.exception("load_config failed")

    _cfg["currentPreset"] = FORCED_PRESET
    save_config()
    LOG.info("config loaded from %s", CONFIG_PATH)
    return _cfg


def save_config():
    try:
        _cfg["currentPreset"] = FORCED_PRESET
        _ensure_dir(CONFIG_PATH)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(_cfg, f, indent=2, sort_keys=True)
    except Exception:
        LOG.exception("save_config failed")


def get_config():
    return _cfg


def is_enabled():
    return bool(_cfg.get("enabled", True))


def set_enabled(flag):
    _cfg["enabled"] = bool(flag)
    save_config()


def get_show_in_battle():
    return bool(_cfg.get("show_in_battle", True))


def set_show_in_battle(flag):
    _cfg["show_in_battle"] = bool(flag)
    save_config()


def get_general_weights():
    return dict(_cfg.get("generalWeights", {}))


def set_general_weights(weights):
    _cfg["generalWeights"] = dict(weights or {})
    save_config()


def get_map_weights(map_name):
    maps = _cfg.setdefault("mapWeights", {})
    return dict(maps.get(map_name, {}))


def set_map_weights(map_name, weights):
    maps = _cfg.setdefault("mapWeights", {})
    maps[map_name] = dict(weights or {})
    save_config()


def get_hotkey():
    hk = _cfg.get("hotkey", {})
    return {
        "enabled": bool(hk.get("enabled", True)),
        "mods": list(hk.get("mods", ["KEY_LALT"])),
        "key": hk.get("key", "KEY_F12")
    }


def set_hotkey(enabled, mods, key):
    _cfg["hotkey"] = {
        "enabled": bool(enabled),
        "mods": list(mods or []),
        "key": key
    }
    save_config()


def get_icon_position():
    pos = _cfg.get("iconPosition", {})
    return int(pos.get("x", 20)), int(pos.get("y", 120))


def set_icon_position(x, y):
    _cfg["iconPosition"] = {"x": int(x), "y": int(y)}
    save_config()


def get_preset_for_map(map_name):
    return FORCED_PRESET


def get_all_general_for_ui():
    items = []
    for preset in PRESET_ORDER:
        items.append({
            "id": preset,
            "label": PRESET_LABELS[preset],
            "weight": 20 if preset == FORCED_PRESET else 0
        })
    return items


def get_all_for_map_ui(map_name):
    return get_all_general_for_ui()


def get_current_override_preset():
    return FORCED_PRESET


def set_override_preset(preset_id):
    LOG.info('set_override_preset ignored in forced build: %s', preset_id)
    return False


def get_preset_labels():
    return dict(PRESET_LABELS)


def get_weather_system_labels():
    return {}


def get_preset_order():
    return list(PRESET_ORDER)


def build_space_settings_xml(preset_guid):
    """
    Робимо мінімальний варіант.
    У ProTanki по логу головне — що вони пишуть space.settings з GUID.
    Не ускладнюємо env_name поки не доведемо сам факт підхоплення.
    """
    if not preset_guid:
        return u'''<?xml version="1.0" encoding="utf-8"?>
<root>
    <environmentOverride></environmentOverride>
</root>
'''

    return u'''<?xml version="1.0" encoding="utf-8"?>
<root>
    <environmentOverride>{guid}</environmentOverride>
</root>
'''.format(guid=preset_guid)


def find_space_settings_path(space_name):
    try:
        res_mods_dir = _find_res_mods_dir()
        if not res_mods_dir:
            LOG.warning('find_space_settings_path: res_mods dir not found')
            return None

        candidate = _safe_norm(os.path.join(res_mods_dir, 'spaces', space_name, 'space.settings'))
        LOG.info('find_space_settings_path: candidate=%s', candidate)
        return candidate

    except Exception:
        LOG.error('find_space_settings_path failed\n%s', traceback.format_exc())
        return None


def write_space_settings_to_res_mods(space_name, preset_guid):
    try:
        target_path = find_space_settings_path(space_name)
        if not target_path:
            return False

        content = build_space_settings_xml(preset_guid)
        folder = os.path.dirname(target_path)
        if not os.path.isdir(folder):
            os.makedirs(folder)

        with open(target_path, 'w') as f:
            f.write(content)

        LOG.info('Written space.settings for %s -> %s', space_name, preset_guid)
        return True

    except Exception:
        LOG.error('write_space_settings_to_res_mods failed\n%s', traceback.format_exc())
        return False


def patch_resmgr(space_name, preset_name):
    """
    Логуємо так само, як ProTanki.
    Реального runtime patch тут поки не робимо.
    """
    try:
        LOG.info('ResMgr patch: %s -> %s', space_name, preset_name)
        return True
    except Exception:
        LOG.error('patch_resmgr failed\n%s', traceback.format_exc())
        return False


def apply_forced_preset(space_name):
    try:
        if not space_name:
            LOG.warning('apply_forced_preset: empty space_name')
            return False

        preset_name = FORCED_PRESET
        preset_guid = PRESET_GUIDS.get(preset_name)

        LOG.info('apply_forced_preset: map=%s preset=%s guid=%s', space_name, preset_name, preset_guid)

        if not preset_guid:
            LOG.warning('apply_forced_preset: no guid for preset %s', preset_name)
            return False

        ok_write = write_space_settings_to_res_mods(space_name, preset_guid)
        ok_patch = patch_resmgr(space_name, preset_name)

        ok = bool(ok_write or ok_patch)

        if ok:
            _push_message(u'[Weather] Форсований preset: %s (наступний бій)' %
                          PRESET_LABELS.get(preset_name, preset_name))
        else:
            _push_message(u'[Weather] Не вдалося підготувати preset, дивись python.log')

        return ok

    except Exception:
        LOG.error('apply_forced_preset failed\n%s', traceback.format_exc())
        return False


def on_space_entered(space_name):
    try:
        LOG.info('on_space_entered: raw space_name=%s', space_name)
        return apply_forced_preset(space_name)
    except Exception:
        LOG.error('on_space_entered failed\n%s', traceback.format_exc())
        return False


def cycle_weather_system():
    LOG.info('cycle_weather_system disabled in forced build')
    return False


def cycle_weather_in_battle():
    LOG.info('cycle_weather_in_battle disabled in forced build')
    _push_message(u'[Weather] Зараз тестуємо лише примусовий preset через наступний бій')
    return False


class WeatherController(object):
    def __init__(self):
        load_config()
        self._sync_legacy_config()

    def _sync_legacy_config(self):
        self.config = {
            'enabled': is_enabled(),
            'show_in_battle': get_show_in_battle(),
            'generalWeights': get_general_weights(),
            'mapWeights': dict(_cfg.get('mapWeights', {})),
            'hotkey': get_hotkey(),
            'iconPosition': {'x': get_icon_position()[0], 'y': get_icon_position()[1]},
            'currentPreset': get_current_override_preset()
        }

    def onSpaceEntered(self, space_name):
        result = on_space_entered(space_name)
        self._sync_legacy_config()
        return result

    def cycleWeatherInBattle(self):
        result = cycle_weather_in_battle()
        self._sync_legacy_config()
        return result

    def cycleWeatherSystem(self):
        result = cycle_weather_system()
        self._sync_legacy_config()
        return result

    def getCurrentOverridePreset(self):
        return get_current_override_preset()

    def setOverridePreset(self, preset_id):
        result = set_override_preset(preset_id)
        self._sync_legacy_config()
        return result

    def getAllGeneralForUI(self):
        return get_all_general_for_ui()

    def getAllForMapUI(self, map_name):
        return get_all_for_map_ui(map_name)

    def getPresetLabels(self):
        return get_preset_labels()

    def getWeatherSystemLabels(self):
        return get_weather_system_labels()

    def getPresetOrder(self):
        return get_preset_order()

    def getGeneralWeights(self):
        return get_general_weights()

    def setGeneralWeights(self, weights):
        result = set_general_weights(weights)
        self._sync_legacy_config()
        return result

    def getMapWeights(self, map_name):
        return get_map_weights(map_name)

    def setMapWeights(self, map_name, weights):
        result = set_map_weights(map_name, weights)
        self._sync_legacy_config()
        return result

    def getHotkey(self):
        return get_hotkey()

    def setHotkey(self, enabled, mods, key):
        result = set_hotkey(enabled, mods, key)
        self._sync_legacy_config()
        return result

    def isEnabled(self):
        return is_enabled()

    def setEnabled(self, flag):
        result = set_enabled(flag)
        self._sync_legacy_config()
        return result

    def getShowInBattle(self):
        return get_show_in_battle()

    def setShowInBattle(self, flag):
        result = set_show_in_battle(flag)
        self._sync_legacy_config()
        return result

    def getIconPosition(self):
        return get_icon_position()

    def setIconPosition(self, x, y):
        result = set_icon_position(x, y)
        self._sync_legacy_config()
        return result

    def getPresetForMap(self, map_name):
        return get_preset_for_map(map_name)


g_controller = WeatherController()
