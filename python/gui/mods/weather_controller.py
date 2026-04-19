# -*- coding: utf-8 -*-
"""
Спрощений weather_controller.py

Мета:
- без ваг
- без live runtime apply
- без складної логіки
- завжди форсити один preset для перевірки, що environment взагалі працює

ВАЖЛИВО:
Ця схема застосовується на НАСТУПНИЙ бій через запис space.settings.
"""

import json
import os
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

logger = logging.getLogger("weather_mod")
logger.setLevel(logging.INFO)
LOG = logger

# ----------------------------------------------------------------------
# ТУТ МІНЯЙ ПРЕСЕТ ДЛЯ ТЕСТУ
# Можна ставити: 'midday', 'midnight', 'overcast', 'sunset'
# ----------------------------------------------------------------------
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


try:
    _prefs = (BigWorld.wg_getPreferencesFilePath()
              if hasattr(BigWorld, 'wg_getPreferencesFilePath')
              else BigWorld.getPreferencesFilePath())
    _prefs_dir = os.path.dirname(_prefs)
    CONFIG_PATH = os.path.normpath(os.path.join(_prefs_dir, 'mods', 'weather', 'config.json'))
except Exception:
    CONFIG_PATH = os.path.normpath(os.path.join(os.getcwd(), 'mods', 'weather', 'config.json'))


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

    # Тримай currentPreset жорстко на FORCED_PRESET
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
    # Тимчасово завжди один preset
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


def build_space_settings_xml(env_name, preset_guid):
    if not env_name:
        return None

    if not preset_guid:
        return u'''<?xml version="1.0" encoding="utf-8"?>
<root>
    <environment>{env}</environment>
</root>
'''.format(env=env_name)

    return u'''<?xml version="1.0" encoding="utf-8"?>
<root>
    <environment>{env}</environment>
    <environmentOverride>{guid}</environmentOverride>
</root>
'''.format(env=env_name, guid=preset_guid)


# Fallback mapping: space_name -> environment name
# Поки вважаємо, що ім'я environment збігається з ім'ям карти
FALLBACK_ENVIRONMENT_BY_SPACE = {
    '01_karelia': '01_karelia',
    '02_malinovka': '02_malinovka',
    '03_campania_big': '03_campania_big',
    '04_himmelsdorf': '04_himmelsdorf',
    '05_prohorovka': '05_prohorovka',
    '06_ensk': '06_ensk',
    '07_lakeville': '07_lakeville',
    '08_ruinberg': '08_ruinberg',
    '10_hills': '10_hills',
    '11_murovanka': '11_murovanka',
    '13_erlenberg': '13_erlenberg',
    '14_siegfried_line': '14_siegfried_line',
    '17_munchen': '17_munchen',
    '18_cliff': '18_cliff',
    '19_monastery': '19_monastery',
    '23_westfeld': '23_westfeld',
    '28_desert': '28_desert',
    '29_el_hallouf': '29_el_hallouf',
    '31_airfield': '31_airfield',
    '33_fjord': '33_fjord',
    '34_redshire': '34_redshire',
    '35_steppes': '35_steppes',
    '36_fishing_bay': '36_fishing_bay',
    '37_caucasus': '37_caucasus',
    '38_mannerheim_line': '38_mannerheim_line',
    '44_north_america': '44_north_america',
    '45_north_america': '45_north_america',
    '47_canada_a': '47_canada_a',
    '59_asia_great_wall': '59_asia_great_wall',
    '60_asia_miao': '60_asia_miao',
    '63_tundra': '63_tundra',
    '90_minsk': '90_minsk',
    '95_lost_city_ctf': '95_lost_city_ctf',
    '99_poland': '99_poland',
    '101_dday': '101_dday',
    '105_germany': '105_germany',
    '112_eiffel_tower_ctf': '112_eiffel_tower_ctf',
    '114_czech': '114_czech',
    '115_sweden': '115_sweden',
    '121_lost_paradise_v': '121_lost_paradise_v',
    '127_japort': '127_japort',
    '128_last_frontier_v': '128_last_frontier_v',
    '208_bf_epic_normandy': '208_bf_epic_normandy',
    '209_wg_epic_suburbia': '209_wg_epic_suburbia',
    '210_bf_epic_desert': '210_bf_epic_desert',
    '212_epic_random_valley': '212_epic_random_valley',
    '217_er_alaska': '217_er_alaska',
    '222_er_clime': '222_er_clime',
}


def load_geometry_mapping():
    LOG.info('load_geometry_mapping: using fallback dictionary, entries=%s', len(FALLBACK_ENVIRONMENT_BY_SPACE))
    return dict(FALLBACK_ENVIRONMENT_BY_SPACE)


def find_space_settings_path(space_name):
    try:
        possible_roots = [
            os.path.join(os.getcwd(), 'res_mods'),
            os.path.normpath(os.path.join(os.getcwd(), '..', 'res_mods')),
            r'D:\World_of_Tanks_EU\res_mods',
        ]

        LOG.info('find_space_settings_path: cwd=%s', os.getcwd())

        res_mods_root = None
        for root in possible_roots:
            if os.path.isdir(root):
                res_mods_root = root
                break

        if not res_mods_root:
            LOG.warning('find_space_settings_path: res_mods root not found')
            return None

        LOG.info('find_space_settings_path: using res_mods_root=%s', res_mods_root)

        version_dirs = []
        for name in os.listdir(res_mods_root):
            full = os.path.join(res_mods_root, name)
            if os.path.isdir(full):
                version_dirs.append(full)

        version_dirs.sort(reverse=True)

        for version_dir in version_dirs:
            candidate = os.path.join(version_dir, 'spaces', space_name, 'space.settings')
            LOG.info('find_space_settings_path: candidate=%s', candidate)
            return candidate

        LOG.warning('find_space_settings_path: no version dirs found')
        return None

    except Exception:
        LOG.error('find_space_settings_path: failed\n%s', traceback.format_exc())
        return None


def write_space_settings_to_res_mods(target_path, content):
    try:
        folder = os.path.dirname(target_path)
        if not os.path.isdir(folder):
            os.makedirs(folder)

        if not isinstance(content, basestring):
            content = content.decode('utf-8')

        with open(target_path, 'w') as f:
            f.write(content)

        LOG.info('write_space_settings_to_res_mods: wrote %s bytes to %s', len(content), target_path)
        return True

    except Exception:
        LOG.error('write_space_settings_to_res_mods: failed\n%s', traceback.format_exc())
        return False


def apply_environment_via_geometry_mapping(space_name, preset_id):
    try:
        LOG.info('apply_environment_via_geometry_mapping: start space=%s preset=%s', space_name, preset_id)

        if not space_name:
            LOG.warning('apply_environment_via_geometry_mapping: no space_name')
            return False

        env_map = load_geometry_mapping()
        env_name = env_map.get(space_name)
        if not env_name:
            LOG.warning('apply_environment_via_geometry_mapping: no mapping for space=%s', space_name)
            return False

        preset_guid = PRESET_GUIDS.get(preset_id)
        LOG.info('apply_environment_via_geometry_mapping: env_name=%s preset_guid=%s', env_name, preset_guid)

        target_path = find_space_settings_path(space_name)
        if not target_path:
            LOG.warning('apply_environment_via_geometry_mapping: no target path')
            return False

        content = build_space_settings_xml(env_name, preset_guid)
        if not content:
            LOG.warning('apply_environment_via_geometry_mapping: empty content')
            return False

        ok = write_space_settings_to_res_mods(target_path, content)
        LOG.info('apply_environment_via_geometry_mapping: result=%s', ok)
        return ok

    except Exception:
        LOG.error('apply_environment_via_geometry_mapping: failed\n%s', traceback.format_exc())
        return False


def on_space_entered(space_name):
    try:
        LOG.info('on_space_entered: raw space_name=%s', space_name)

        if not space_name:
            LOG.warning('on_space_entered: empty space_name')
            return False

        forced_preset = FORCED_PRESET
        LOG.info('on_space_entered: FORCED preset=%s', forced_preset)

        result = apply_environment_via_geometry_mapping(space_name, forced_preset)

        LOG.info(
            'on_space_entered: apply_environment_via_geometry_mapping(space=%s, preset=%s) -> %s',
            space_name, forced_preset, result
        )

        if result:
            _push_message(u'[Weather] Форсовано preset: %s (наступний бій)' % PRESET_LABELS.get(forced_preset, forced_preset))
        else:
            _push_message(u'[Weather] Не вдалося записати preset, дивись python.log')

        return result

    except Exception:
        LOG.error('on_space_entered: failed\n%s', traceback.format_exc())
        return False


def cycle_weather_system():
    LOG.info('cycle_weather_system: disabled in simplified build')
    return False


def cycle_weather_in_battle():
    """
    Тимчасово hotkey нічого live не міняє.
    Лише повідомляє, що зараз тестуємо forced preset через наступний бій.
    """
    LOG.info('cycle_weather_in_battle: simplified build, live switching disabled')
    _push_message(u'[Weather] Зараз тестуємо лише forced preset через наступний бій')
    return False


def get_current_override_preset():
    return FORCED_PRESET


def set_override_preset(preset_id):
    LOG.info('set_override_preset: ignored in simplified build, forced=%s', FORCED_PRESET)
    return False


def get_preset_labels():
    return dict(PRESET_LABELS)


def get_weather_system_labels():
    return {}


def get_preset_order():
    return list(PRESET_ORDER)


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
