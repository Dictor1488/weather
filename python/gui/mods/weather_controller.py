# -*- coding: utf-8 -*-
"""
Weather controller v4.0
Новий підхід: BigWorld.addSpaceGeometryMapping + фізичний запис у res_mods

З аналізу ProTanki і BigWorld API:
- BigWorld.addSpaceGeometryMapping(spaceID, path, order) додає VFS маппінг
- WoT читає environment з папки з найвищим пріоритетом
- Записуємо мінімальний space.settings з потрібним GUID у res_mods папку
- Додаємо маппінг -> WoT підхоплює новий environment
"""
import json
import os
import random
import logging
import traceback

try:
    basestring
except NameError:
    basestring = str

try:
    import BigWorld
    import ResMgr
    from gui import SystemMessages
    IN_GAME = True
except ImportError:
    IN_GAME = False

logger = logging.getLogger("weather_mod")
logger.setLevel(logging.INFO)
LOG = logger

PRESET_GUIDS = {
    "standard": None,
    "midday":   "BF040BCB-4BE1D04F-7D484589-135E881B",
    "sunset":   "6DEE1EBB-44F63FCC-AACF6185-7FBBC34E",
    "overcast": "56BA3213-40FFB1DF-125FBCAD-173E8347",
    "midnight": "15755E11-4090266B-594778B6-B233C12C",
}

PRESET_LABELS = {
    "standard": u"Стандарт",
    "midnight": u"Ніч",
    "overcast": u"Пасмурно",
    "sunset":   u"Закат",
    "midday":   u"Полдень",
}

PRESET_ORDER = ["standard", "midnight", "overcast", "sunset", "midday"]
MAX_WEIGHT = 20

WEATHER_SYSTEM_LABELS = {
    "Clear":   u"Ясно",
    "Cloudy":  u"Хмарно",
    "Cloudy2": u"Хмарно 2",
    "Cloudy3": u"Хмарно 3",
    "Cloudy4": u"Хмарно 4",
    "Urban":   u"Місто",
    "Stormy":  u"Шторм",
    "Hail":    u"Град",
}

try:
    _prefs = (BigWorld.wg_getPreferencesFilePath()
              if hasattr(BigWorld, 'wg_getPreferencesFilePath')
              else BigWorld.getPreferencesFilePath())
    _prefs_dir = os.path.dirname(_prefs)
    CONFIG_PATH = os.path.normpath(os.path.join(_prefs_dir, 'mods', 'weather', 'config.json'))
    _RES_MODS_CANDIDATES = [
        os.path.normpath(os.path.join(_prefs_dir, '../../../../res_mods')),
        os.path.normpath(os.path.join(_prefs_dir, '../../../res_mods')),
        os.path.normpath(os.path.join(os.getcwd(), 'res_mods')),
    ]
except Exception:
    CONFIG_PATH = os.path.normpath(os.path.join(os.getcwd(), 'mods', 'weather', 'config.json'))
    _RES_MODS_CANDIDATES = [os.path.normpath(os.path.join(os.getcwd(), 'res_mods'))]

DEFAULT_CFG = {
    "enabled": True,
    "show_in_battle": True,
    "generalWeights": {k: 0 for k in PRESET_ORDER},
    "mapWeights": {},
    "hotkey": {"enabled": True, "mods": ["LALT"], "key": "KEY_F12"},
    "iconPosition": {"x": 20, "y": 120},
}

_cfg = {}
_current_override_preset = None
_current_cycle_index = 0


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


def _normalize_weights(dct):
    out = {}
    for key in PRESET_ORDER:
        try:
            out[key] = max(0, min(MAX_WEIGHT, int(dct.get(key, 0))))
        except Exception:
            out[key] = 0
    return out


def load_config():
    global _cfg
    _cfg = json.loads(json.dumps(DEFAULT_CFG))
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                user_cfg = json.load(f)
            _deep_update(_cfg, user_cfg)
    except Exception:
        logger.exception("load_config failed")

    _cfg["generalWeights"] = _normalize_weights(_cfg.get("generalWeights", {}))
    maps = _cfg.get("mapWeights", {})
    fixed = {}
    for map_name, weights in maps.items():
        if isinstance(weights, dict):
            fixed[map_name] = _normalize_weights(weights)
    _cfg["mapWeights"] = fixed
    save_config()
    logger.info("config loaded from %s", CONFIG_PATH)
    return _cfg


def save_config():
    try:
        _ensure_dir(CONFIG_PATH)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(_cfg, f, indent=2, sort_keys=True)
    except Exception:
        logger.exception("save_config failed")


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
    _cfg["generalWeights"] = _normalize_weights(weights or {})
    save_config()


def get_map_weights(map_name):
    maps = _cfg.setdefault("mapWeights", {})
    return dict(maps.get(map_name, _cfg.get("generalWeights", {})))


def set_map_weights(map_name, weights):
    maps = _cfg.setdefault("mapWeights", {})
    maps[map_name] = _normalize_weights(weights or {})
    save_config()


def get_hotkey():
    hk = _cfg.get("hotkey", {})
    return {
        "enabled": bool(hk.get("enabled", True)),
        "mods": list(hk.get("mods", ["LALT"])),
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


def weighted_choice(weights_dict):
    pool = []
    for preset in PRESET_ORDER:
        w = int(weights_dict.get(preset, 0))
        if w > 0:
            pool.extend([preset] * w)
    if not pool:
        return "standard"
    return random.choice(pool)


def get_preset_for_map(map_name):
    maps = _cfg.get("mapWeights", {})
    if map_name in maps:
        return weighted_choice(maps[map_name])
    return weighted_choice(_cfg.get("generalWeights", {}))


def get_all_general_for_ui():
    items = []
    weights = _cfg.get("generalWeights", {})
    for preset in PRESET_ORDER:
        items.append({
            "id": preset,
            "label": PRESET_LABELS[preset],
            "weight": int(weights.get(preset, 0))
        })
    return items


def get_all_for_map_ui(map_name):
    items = []
    weights = get_map_weights(map_name)
    for preset in PRESET_ORDER:
        items.append({
            "id": preset,
            "label": PRESET_LABELS[preset],
            "weight": int(weights.get(preset, 0))
        })
    return items


def build_space_settings_xml(env_name, preset_guid):
    if not env_name:
        return None

    if not preset_guid:
        content = u'''<?xml version="1.0" encoding="utf-8"?>
<root>
    <environment>{env}</environment>
</root>
'''.format(env=env_name)
        return content.encode('utf-8') if not isinstance(content, basestring) else content

    content = u'''<?xml version="1.0" encoding="utf-8"?>
<root>
    <environment>{env}</environment>
    <environmentOverride>{guid}</environmentOverride>
</root>
'''.format(env=env_name, guid=preset_guid)
    return content.encode('utf-8') if not isinstance(content, basestring) else content


def _read_json_resource(path):
    try:
        if not IN_GAME:
            return None
        sect = ResMgr.openSection(path)
        if sect is None:
            return None
        if hasattr(sect, 'asBinary'):
            raw = sect.asBinary
            if callable(raw):
                raw = raw()
        else:
            raw = sect.readString('') if hasattr(sect, 'readString') else None
        if not raw:
            return None
        if not isinstance(raw, basestring):
            raw = raw.decode('utf-8')
        return json.loads(raw)
    except Exception:
        logger.exception("read json resource failed: %s", path)
        return None


def load_geometry_mapping():
    candidates = [
        'spaces/geometry_mapping.json',
        'spaces/spaces_geometry_mapping.json',
        'scripts/client/mods/weather/geometry_mapping.json',
        'mods/weather/geometry_mapping.json',
    ]
    for path in candidates:
        data = _read_json_resource(path)
        if isinstance(data, dict) and data:
            return data
    return {}


def find_space_settings_path(space_name):
    try:
        game_root = None

        try:
            import BigWorld
            if hasattr(BigWorld, 'wg_getPreferencesFilePath'):
                prefs = BigWorld.wg_getPreferencesFilePath()
                if prefs:
                    game_root = os.path.abspath(os.path.join(os.path.dirname(prefs), '..', '..', '..', '..'))
        except Exception:
            LOG.error('find_space_settings_path: failed to resolve via prefs\n%s', traceback.format_exc())

        if not game_root:
            game_root = os.getcwd()

        LOG.info('find_space_settings_path: game_root=%s', game_root)

        res_mods_root = os.path.join(game_root, 'res_mods')
        if not os.path.isdir(res_mods_root):
            LOG.warning('find_space_settings_path: no res_mods root at %s', res_mods_root)
            return None

        version_dirs = []
        for name in os.listdir(res_mods_root):
            full = os.path.join(res_mods_root, name)
            if os.path.isdir(full):
                version_dirs.append(full)

        version_dirs.sort(key=lambda p: os.path.getmtime(p), reverse=True)

        LOG.info('find_space_settings_path: version dirs=%s', version_dirs)

        for version_dir in version_dirs:
            candidate = os.path.join(version_dir, 'spaces', space_name, 'space.settings')
            LOG.info('find_space_settings_path: checking %s', candidate)
            return candidate

        LOG.warning('find_space_settings_path: no version dirs in res_mods')
        return None

    except Exception:
        LOG.error('find_space_settings_path: failed\n%s', traceback.format_exc())
        return None


def write_space_settings_to_res_mods(target_path, content):
    try:
        folder = os.path.dirname(target_path)
        if not os.path.isdir(folder):
            os.makedirs(folder)

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
        LOG.info('apply_environment_via_geometry_mapping: geometry map loaded, entries=%s', len(env_map) if env_map else 0)

        env_name = env_map.get(space_name)
        if not env_name:
            LOG.warning('apply_environment_via_geometry_mapping: no mapping for space=%s', space_name)
            return False

        preset_guid = PRESET_GUIDS.get(preset_id) if preset_id else None
        LOG.info(
            'apply_environment_via_geometry_mapping: env_name=%s preset_guid=%s',
            env_name, preset_guid
        )

        space_settings_path = find_space_settings_path(space_name)
        if not space_settings_path:
            LOG.warning('apply_environment_via_geometry_mapping: space settings path not found for %s', space_name)
            return False

        LOG.info('apply_environment_via_geometry_mapping: target path=%s', space_settings_path)

        content = build_space_settings_xml(env_name, preset_guid)
        if not content:
            LOG.warning('apply_environment_via_geometry_mapping: generated empty content')
            return False

        write_space_settings_to_res_mods(space_settings_path, content)
        LOG.info('apply_environment_via_geometry_mapping: write OK')
        return True

    except Exception:
        LOG.error('apply_environment_via_geometry_mapping: failed\n%s', traceback.format_exc())
        return False


def on_space_entered(space_name):
    try:
        LOG.info('on_space_entered: raw space_name=%s override=%s', space_name, _current_override_preset)

        if not space_name:
            LOG.warning('on_space_entered: empty space_name')
            return False

        preset_id = _current_override_preset
        LOG.info('on_space_entered: chosen preset=%s', preset_id if preset_id else 'standard')

        result = apply_environment_via_geometry_mapping(space_name, preset_id)

        LOG.info(
            'on_space_entered: apply_environment_via_geometry_mapping(space=%s, preset=%s) -> %s',
            space_name, preset_id, result
        )
        return result

    except Exception:
        LOG.error('on_space_entered: failed\n%s', traceback.format_exc())
        return False


def cycle_weather_system():
    """
    Старий runtime weather system.
    Залишаємо як fallback/debug, але hotkey більше не повинен його використовувати.
    """
    try:
        import Weather
        if not hasattr(Weather, 's_weather') or Weather.s_weather is None:
            logger.warning("Weather.s_weather unavailable")
            return
        cur = getattr(Weather.s_weather, 'currentWeatherSystem', None)
        all_names = list(WEATHER_SYSTEM_LABELS.keys())
        if cur not in all_names:
            nxt = all_names[0]
        else:
            nxt = all_names[(all_names.index(cur) + 1) % len(all_names)]
        Weather.s_weather.nextWeatherSystem(nxt)
        logger.info("fallback weather system changed: %s -> %s", cur, nxt)
        try:
            SystemMessages.pushMessage(
                u'[Weather] Системна погода: %s' % WEATHER_SYSTEM_LABELS.get(nxt, nxt),
                SystemMessages.SM_TYPE.Information
            )
        except Exception:
            pass
    except Exception:
        logger.exception("cycle_weather_system failed")


def cycle_weather_in_battle():
    global _current_cycle_index, _current_override_preset

    try:
        from gui import SystemMessages
    except Exception:
        SystemMessages = None

    try:
        preset_order = ['standard', 'midnight', 'overcast', 'sunset', 'midday']

        current = _current_override_preset or 'standard'
        if current not in preset_order:
            current = 'standard'

        idx = preset_order.index(current)
        next_preset = preset_order[(idx + 1) % len(preset_order)]

        LOG.info('cycle_weather_in_battle: current=%s next=%s', current, next_preset)

        _current_cycle_index = preset_order.index(next_preset)
        _current_override_preset = None if next_preset == 'standard' else next_preset

        battle_loaded = False
        arena_name = None
        player = None

        try:
            import BigWorld
            player = BigWorld.player()
            battle_loaded = player is not None and getattr(player, 'arena', None) is not None
            if battle_loaded:
                arena_name = getattr(player.arena, 'geometryName', None)
        except Exception:
            LOG.error('cycle_weather_in_battle: failed to inspect BigWorld state\n%s', traceback.format_exc())

        LOG.info(
            'cycle_weather_in_battle: battle_loaded=%s arena_name=%s override=%s',
            battle_loaded, arena_name, _current_override_preset
        )

        applied = False

        if battle_loaded and arena_name:
            try:
                applied = apply_environment_via_geometry_mapping(arena_name, _current_override_preset)
                LOG.info(
                    'cycle_weather_in_battle: apply_environment_via_geometry_mapping returned %s for arena=%s preset=%s',
                    applied, arena_name, _current_override_preset
                )
            except Exception:
                LOG.error('cycle_weather_in_battle: apply failed\n%s', traceback.format_exc())
        else:
            LOG.warning('cycle_weather_in_battle: battle or arena not ready, preset only stored')

        save_config()

        msg = '[Weather] preset: %s' % next_preset
        if not applied and battle_loaded:
            msg += ' (stored, may require next battle reload)'
        elif not battle_loaded:
            msg += ' (stored for next battle)'

        if SystemMessages is not None:
            try:
                SystemMessages.pushMessage(msg, SystemMessages.SM_TYPE.Information)
            except Exception:
                LOG.error('cycle_weather_in_battle: failed to show system message\n%s', traceback.format_exc())

    except Exception:
        LOG.error('cycle_weather_in_battle: fatal error\n%s', traceback.format_exc())


def get_current_override_preset():
    return _current_override_preset or "standard"


def set_override_preset(preset_id):
    global _current_override_preset, _current_cycle_index
    if preset_id not in PRESET_ORDER:
        return
    _current_override_preset = None if preset_id == "standard" else preset_id
    _current_cycle_index = PRESET_ORDER.index(preset_id)
    save_config()


def get_preset_labels():
    return dict(PRESET_LABELS)


def get_weather_system_labels():
    return dict(WEATHER_SYSTEM_LABELS)


def get_preset_order():
    return list(PRESET_ORDER)


class WeatherController(object):
    def __init__(self):
        load_config()

    def onSpaceEntered(self, space_name):
        return on_space_entered(space_name)

    def cycleWeatherInBattle(self):
        return cycle_weather_in_battle()

    def cycleWeatherSystem(self):
        return cycle_weather_system()

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
