# -*- coding: utf-8 -*-

import json
import os
import logging
import traceback

LOG = logging.getLogger("weather_mod")
LOG.setLevel(logging.INFO)

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
_initialized = False


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


def _get_config_path():
    try:
        import BigWorld
        if hasattr(BigWorld, 'wg_getPreferencesFilePath'):
            prefs = BigWorld.wg_getPreferencesFilePath()
            if prefs:
                prefs_dir = os.path.dirname(prefs)
                return os.path.normpath(os.path.join(prefs_dir, 'mods', 'weather', 'config.json'))
    except Exception:
        pass
    return os.path.normpath(os.path.join(os.getcwd(), 'mods', 'weather', 'config.json'))


def _push_message(text):
    try:
        from gui import SystemMessages
        SystemMessages.pushMessage(text, SystemMessages.SM_TYPE.Information)
    except Exception:
        pass


def _find_res_mods_dir():
    candidates = [
        os.path.normpath(os.path.join(os.getcwd(), '..', 'res_mods')),
        os.path.normpath(os.path.join(os.getcwd(), 'res_mods')),
        r'D:\World_of_Tanks_EU\res_mods',
    ]

    checked = []
    for base in candidates:
        if base in checked:
            continue
        checked.append(base)

        if not os.path.isdir(base):
            continue

        try:
            version_dirs = []
            for name in os.listdir(base):
                full = os.path.join(base, name)
                if os.path.isdir(full):
                    version_dirs.append((name, full))

            version_dirs.sort(reverse=True)
            if version_dirs:
                found = version_dirs[0][1]
                LOG.info('Found res_mods: %s', found)
                return found
        except Exception:
            LOG.error('_find_res_mods_dir failed for %s\n%s', base, traceback.format_exc())

    LOG.warning('res_mods not found; checked=%s', checked)
    return None


def _build_space_settings_xml(preset_guid):
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


def ensure_initialized():
    global _initialized, _cfg
    if _initialized:
        return

    _cfg = json.loads(json.dumps(DEFAULT_CFG))
    path = _get_config_path()

    try:
        if os.path.isfile(path):
            with open(path, 'r') as f:
                user_cfg = json.load(f)
            _deep_update(_cfg, user_cfg)
    except Exception:
        LOG.exception("load_config failed")

    _cfg["currentPreset"] = FORCED_PRESET

    try:
        _ensure_dir(path)
        with open(path, 'w') as f:
            json.dump(_cfg, f, indent=2, sort_keys=True)
    except Exception:
        LOG.exception("save_config failed")

    LOG.info("config loaded from %s", path)
    _initialized = True


def is_enabled():
    ensure_initialized()
    return bool(_cfg.get("enabled", True))


def set_enabled(flag):
    ensure_initialized()
    _cfg["enabled"] = bool(flag)


def get_show_in_battle():
    ensure_initialized()
    return bool(_cfg.get("show_in_battle", True))


def set_show_in_battle(flag):
    ensure_initialized()
    _cfg["show_in_battle"] = bool(flag)


def get_general_weights():
    ensure_initialized()
    return dict(_cfg.get("generalWeights", {}))


def set_general_weights(weights):
    ensure_initialized()
    _cfg["generalWeights"] = dict(weights or {})


def get_map_weights(map_name):
    ensure_initialized()
    maps = _cfg.setdefault("mapWeights", {})
    return dict(maps.get(map_name, {}))


def set_map_weights(map_name, weights):
    ensure_initialized()
    maps = _cfg.setdefault("mapWeights", {})
    maps[map_name] = dict(weights or {})


def get_hotkey():
    ensure_initialized()
    hk = _cfg.get("hotkey", {})
    return {
        "enabled": bool(hk.get("enabled", True)),
        "mods": list(hk.get("mods", ["KEY_LALT"])),
        "key": hk.get("key", "KEY_F12")
    }


def set_hotkey(enabled, mods, key):
    ensure_initialized()
    _cfg["hotkey"] = {
        "enabled": bool(enabled),
        "mods": list(mods or []),
        "key": key
    }


def get_icon_position():
    ensure_initialized()
    pos = _cfg.get("iconPosition", {})
    return int(pos.get("x", 20)), int(pos.get("y", 120))


def set_icon_position(x, y):
    ensure_initialized()
    _cfg["iconPosition"] = {"x": int(x), "y": int(y)}


def get_preset_for_map(map_name):
    return FORCED_PRESET


def get_all_general_for_ui():
    ensure_initialized()
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
    return False


def get_preset_labels():
    return dict(PRESET_LABELS)


def get_weather_system_labels():
    return {}


def get_preset_order():
    return list(PRESET_ORDER)


def on_space_entered(space_name):
    ensure_initialized()
    try:
        if not space_name:
            LOG.warning('on_space_entered: empty space_name')
            return False

        preset_guid = PRESET_GUIDS.get(FORCED_PRESET)
        res_mods_dir = _find_res_mods_dir()
        if not res_mods_dir:
            return False

        target_path = os.path.join(res_mods_dir, 'spaces', space_name, 'space.settings')
        folder = os.path.dirname(target_path)
        if not os.path.isdir(folder):
            os.makedirs(folder)

        with open(target_path, 'w') as f:
            f.write(_build_space_settings_xml(preset_guid))

        LOG.info('Written space.settings for %s -> %s', space_name, preset_guid)
        LOG.info('ResMgr patch: %s -> %s', space_name, FORCED_PRESET)
        _push_message(u'[Weather] Форсований preset: %s' % PRESET_LABELS.get(FORCED_PRESET, FORCED_PRESET))
        return True

    except Exception:
        LOG.error('on_space_entered failed\n%s', traceback.format_exc())
        return False


def cycle_weather_in_battle():
    ensure_initialized()
    _push_message(u'[Weather] Зараз hotkey вимкнений для safe build')
    return False


def cycle_weather_system():
    return False


class WeatherController(object):
    def __init__(self):
        self.config = {}

    def _sync_legacy_config(self):
        ensure_initialized()
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
        return set_override_preset(preset_id)

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
        return set_general_weights(weights)

    def getMapWeights(self, map_name):
        return get_map_weights(map_name)

    def setMapWeights(self, map_name, weights):
        return set_map_weights(map_name, weights)

    def getHotkey(self):
        return get_hotkey()

    def setHotkey(self, enabled, mods, key):
        return set_hotkey(enabled, mods, key)

    def isEnabled(self):
        return is_enabled()

    def setEnabled(self, flag):
        return set_enabled(flag)

    def getShowInBattle(self):
        return get_show_in_battle()

    def setShowInBattle(self, flag):
        return set_show_in_battle(flag)

    def getIconPosition(self):
        return get_icon_position()

    def setIconPosition(self, x, y):
        return set_icon_position(x, y)

    def getPresetForMap(self, map_name):
        return get_preset_for_map(map_name)


g_controller = WeatherController()
