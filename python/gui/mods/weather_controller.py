# -*- coding: utf-8 -*-
"""
weather_controller.py
Live-first controller:
1) tries runtime environment switch in current battle
2) falls back to writing res_mods/.../space.settings for next battle
3) keeps backward compatibility with current __init__.py
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
except Exception:
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
    "sunset":   u"Захід",
    "midday":   u"Полудень",
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
except Exception:
    CONFIG_PATH = os.path.normpath(os.path.join(os.getcwd(), 'mods', 'weather', 'config.json'))


DEFAULT_CFG = {
    "enabled": True,
    "show_in_battle": True,
    "generalWeights": {k: 0 for k in PRESET_ORDER},
    "mapWeights": {},
    "hotkey": {"enabled": True, "mods": ["KEY_LALT"], "key": "KEY_F12"},
    "iconPosition": {"x": 20, "y": 120},
    "currentPreset": "standard"
}

_cfg = {}
_current_override_preset = None
_current_cycle_index = 0


# -----------------------------------------------------------------------------
# utils
# -----------------------------------------------------------------------------
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


def _push_message(text):
    if not IN_GAME:
        return
    try:
        SystemMessages.pushMessage(text, SystemMessages.SM_TYPE.Information)
    except Exception:
        LOG.error('_push_message failed\n%s', traceback.format_exc())


# -----------------------------------------------------------------------------
# config
# -----------------------------------------------------------------------------
def load_config():
    global _cfg, _current_override_preset, _current_cycle_index

    _cfg = json.loads(json.dumps(DEFAULT_CFG))

    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                user_cfg = json.load(f)
            _deep_update(_cfg, user_cfg)
    except Exception:
        LOG.exception("load_config failed")

    _cfg["generalWeights"] = _normalize_weights(_cfg.get("generalWeights", {}))

    maps = _cfg.get("mapWeights", {})
    fixed = {}
    for map_name, weights in maps.items():
        if isinstance(weights, dict):
            fixed[map_name] = _normalize_weights(weights)
    _cfg["mapWeights"] = fixed

    preset = _cfg.get("currentPreset", "standard")
    if preset not in PRESET_ORDER:
        preset = "standard"

    _current_override_preset = None if preset == "standard" else preset
    _current_cycle_index = PRESET_ORDER.index(preset)

    save_config()
    LOG.info("config loaded from %s", CONFIG_PATH)
    return _cfg


def save_config():
    try:
        _cfg["currentPreset"] = get_current_override_preset()
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


# -----------------------------------------------------------------------------
# weights / UI helpers
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# map/environment fallback mapping
# -----------------------------------------------------------------------------
# Fallback env names. If your environment packages use another naming scheme,
# the log will show it and we can adjust.
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


def _read_json_resource(path):
    try:
        if not IN_GAME:
            return None
        sect = ResMgr.openSection(path)
        if sect is None:
            return None
        raw = None
        if hasattr(sect, 'asBinary'):
            try:
                raw = sect.asBinary
                if callable(raw):
                    raw = raw()
            except Exception:
                raw = None
        if not raw and hasattr(sect, 'readString'):
            try:
                raw = sect.readString('')
            except Exception:
                raw = None
        if not raw:
            return None
        if not isinstance(raw, basestring):
            raw = raw.decode('utf-8')
        return json.loads(raw)
    except Exception:
        LOG.exception("read json resource failed: %s", path)
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
            LOG.info('load_geometry_mapping: loaded from %s entries=%s', path, len(data))
            return data
    LOG.warning('load_geometry_mapping: no json mapping found, using fallback dictionary')
    return dict(FALLBACK_ENVIRONMENT_BY_SPACE)


# -----------------------------------------------------------------------------
# next-battle fallback through space.settings
# -----------------------------------------------------------------------------
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


def find_space_settings_path(space_name):
    try:
        game_root = None

        try:
            if hasattr(BigWorld, 'wg_getPreferencesFilePath'):
                prefs = BigWorld.wg_getPreferencesFilePath()
            else:
                prefs = None
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

        for version_dir in version_dirs:
            candidate = os.path.join(version_dir, 'spaces', space_name, 'space.settings')
            LOG.info('find_space_settings_path: using %s', candidate)
            return candidate

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
        LOG.info('apply_environment_via_geometry_mapping: geometry map loaded, entries=%s', len(env_map) if env_map else 0)

        env_name = env_map.get(space_name)
        if not env_name:
            LOG.warning('apply_environment_via_geometry_mapping: no mapping for space=%s', space_name)
            return False

        preset_guid = PRESET_GUIDS.get(preset_id) if preset_id else None
        LOG.info('apply_environment_via_geometry_mapping: env_name=%s preset_guid=%s', env_name, preset_guid)

        target_path = find_space_settings_path(space_name)
        if not target_path:
            LOG.warning('apply_environment_via_geometry_mapping: space settings path not found for %s', space_name)
            return False

        content = build_space_settings_xml(env_name, preset_guid)
        if not content:
            LOG.warning('apply_environment_via_geometry_mapping: generated empty content')
            return False

        ok = write_space_settings_to_res_mods(target_path, content)
        LOG.info('apply_environment_via_geometry_mapping: write result=%s', ok)
        return ok

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

        LOG.info('on_space_entered: apply_environment_via_geometry_mapping(space=%s, preset=%s) -> %s',
                 space_name, preset_id, result)
        return result

    except Exception:
        LOG.error('on_space_entered: failed\n%s', traceback.format_exc())
        return False


# -----------------------------------------------------------------------------
# runtime live apply
# -----------------------------------------------------------------------------
def _get_player():
    try:
        return BigWorld.player()
    except Exception:
        return None


def _get_current_arena_name():
    """
    Try both arena.geometryName and arena.arenaType.geometryName.
    """
    try:
        player = _get_player()
        if not player:
            return None

        arena = getattr(player, 'arena', None)
        if not arena:
            return None

        geometry_name = getattr(arena, 'geometryName', None)
        if geometry_name:
            return geometry_name

        arena_type = getattr(arena, 'arenaType', None)
        if arena_type:
            for attr in ('geometryName', 'geometry', 'name'):
                v = getattr(arena_type, attr, None)
                if v:
                    name = v.strip()
                    if '/' in name:
                        name = name.rsplit('/', 1)[-1]
                    return name
    except Exception:
        LOG.error('_get_current_arena_name failed\n%s', traceback.format_exc())

    return None


def _try_call(obj, method_names, *args):
    for name in method_names:
        try:
            fn = getattr(obj, name, None)
            if callable(fn):
                LOG.info('_try_call: calling %s on %s', name, type(obj))
                return True, fn(*args)
        except Exception:
            LOG.error('_try_call: %s failed on %s\n%s', name, type(obj), traceback.format_exc())
    return False, None


def _describe_runtime_targets():
    try:
        player = _get_player()
        arena = getattr(player, 'arena', None) if player else None
        arena_type = getattr(arena, 'arenaType', None) if arena else None
        bw_space_id = getattr(player, 'spaceID', None) if player else None

        LOG.info('runtime describe: player=%s', type(player))
        LOG.info('runtime describe: arena=%s', type(arena))
        LOG.info('runtime describe: arenaType=%s', type(arena_type))
        LOG.info('runtime describe: player.spaceID=%s', bw_space_id)

        if player:
            for attr in ('spaceID', 'guiSessionProvider', 'vehicle', 'arena'):
                try:
                    LOG.info('runtime player attr %s=%s', attr, type(getattr(player, attr, None)))
                except Exception:
                    pass

        if arena:
            for attr in ('geometryName', 'arenaType'):
                try:
                    LOG.info('runtime arena attr %s=%s', attr, repr(getattr(arena, attr, None)))
                except Exception:
                    pass
    except Exception:
        LOG.error('_describe_runtime_targets failed\n%s', traceback.format_exc())


def _apply_live_via_weather_system(preset_id):
    """
    Fallback live approximation using built-in weather systems.
    This is not the same as environment GUID presets, but may still visibly change weather.
    """
    try:
        import Weather
    except Exception:
        LOG.info('_apply_live_via_weather_system: Weather module unavailable')
        return False

    try:
        weather_obj = getattr(Weather, 's_weather', None)
        if weather_obj is None:
            LOG.info('_apply_live_via_weather_system: Weather.s_weather is None')
            return False

        mapping = {
            'standard': 'Clear',
            'midday': 'Clear',
            'sunset': 'Cloudy',
            'overcast': 'Cloudy4',
            'midnight': 'Stormy',
        }
        target_system = mapping.get(preset_id or 'standard', 'Clear')

        ok, _ = _try_call(weather_obj, ['nextWeatherSystem', 'setWeatherSystem', 'changeWeatherSystem'], target_system)
        if ok:
            LOG.info('_apply_live_via_weather_system: success target=%s', target_system)
            return True

        LOG.info('_apply_live_via_weather_system: no callable runtime method found')
        return False

    except Exception:
        LOG.error('_apply_live_via_weather_system failed\n%s', traceback.format_exc())
        return False


def _apply_live_via_environment_probes(preset_id):
    """
    Experimental probe-based runtime environment switch.
    We do not assume exact API names. We probe common method names.
    """
    try:
        _describe_runtime_targets()

        player = _get_player()
        if not player:
            LOG.info('_apply_live_via_environment_probes: no player')
            return False

        preset_guid = PRESET_GUIDS.get(preset_id) if preset_id else None
        arena_name = _get_current_arena_name()

        LOG.info('_apply_live_via_environment_probes: arena_name=%s preset=%s guid=%s',
                 arena_name, preset_id, preset_guid)

        targets = []

        try:
            arena = getattr(player, 'arena', None)
            if arena:
                targets.append(('arena', arena))
        except Exception:
            pass

        try:
            arena_type = getattr(getattr(player, 'arena', None), 'arenaType', None)
            if arena_type:
                targets.append(('arenaType', arena_type))
        except Exception:
            pass

        try:
            gsp = getattr(player, 'guiSessionProvider', None)
            if gsp:
                targets.append(('guiSessionProvider', gsp))
        except Exception:
            pass

        # Probe methods on likely runtime objects
        method_groups = [
            ['setEnvironmentOverride', 'applyEnvironmentOverride', 'changeEnvironmentOverride'],
            ['setEnvironmentPreset', 'applyEnvironmentPreset', 'changeEnvironmentPreset'],
            ['setEnvironment', 'applyEnvironment', 'changeEnvironment'],
        ]

        for label, obj in targets:
            LOG.info('_apply_live_via_environment_probes: probing target=%s type=%s', label, type(obj))

            # standard = clear override
            if preset_guid is None:
                for names in method_groups:
                    ok, _ = _try_call(obj, names, None)
                    if ok:
                        LOG.info('_apply_live_via_environment_probes: standard reset via %s', label)
                        return True
                    ok, _ = _try_call(obj, names, '')
                    if ok:
                        LOG.info('_apply_live_via_environment_probes: standard reset(empty) via %s', label)
                        return True
            else:
                for names in method_groups:
                    ok, _ = _try_call(obj, names, preset_guid)
                    if ok:
                        LOG.info('_apply_live_via_environment_probes: guid applied via %s', label)
                        return True

                    if arena_name:
                        ok, _ = _try_call(obj, names, arena_name, preset_guid)
                        if ok:
                            LOG.info('_apply_live_via_environment_probes: arena+guid applied via %s', label)
                            return True

        LOG.info('_apply_live_via_environment_probes: no runtime probe matched')
        return False

    except Exception:
        LOG.error('_apply_live_via_environment_probes failed\n%s', traceback.format_exc())
        return False


def apply_environment_live(space_name, preset_id):
    """
    Live apply pipeline:
    1) true environment/runtime probes
    2) built-in Weather system approximation
    """
    try:
        LOG.info('apply_environment_live: start space=%s preset=%s', space_name, preset_id)

        # Try exact-ish runtime environment switching first
        if _apply_live_via_environment_probes(preset_id):
            LOG.info('apply_environment_live: success via environment probes')
            return True

        # Fallback: built-in weather system live switch
        if _apply_live_via_weather_system(preset_id):
            LOG.info('apply_environment_live: success via Weather system fallback')
            return True

        LOG.warning('apply_environment_live: no live method succeeded')
        return False

    except Exception:
        LOG.error('apply_environment_live failed\n%s', traceback.format_exc())
        return False


# -----------------------------------------------------------------------------
# weather system old fallback
# -----------------------------------------------------------------------------
def cycle_weather_system():
    try:
        import Weather
        if not hasattr(Weather, 's_weather') or Weather.s_weather is None:
            LOG.warning("Weather.s_weather unavailable")
            return False

        cur = getattr(Weather.s_weather, 'currentWeatherSystem', None)
        all_names = list(WEATHER_SYSTEM_LABELS.keys())
        if cur not in all_names:
            nxt = all_names[0]
        else:
            nxt = all_names[(all_names.index(cur) + 1) % len(all_names)]

        Weather.s_weather.nextWeatherSystem(nxt)
        LOG.info("fallback weather system changed: %s -> %s", cur, nxt)
        _push_message(u'[Weather] Системна погода: %s' % WEATHER_SYSTEM_LABELS.get(nxt, nxt))
        return True

    except Exception:
        LOG.exception("cycle_weather_system failed")
        return False


# -----------------------------------------------------------------------------
# current preset
# -----------------------------------------------------------------------------
def get_current_override_preset():
    return _current_override_preset or "standard"


def set_override_preset(preset_id):
    global _current_override_preset, _current_cycle_index

    if preset_id not in PRESET_ORDER:
        return False

    _current_override_preset = None if preset_id == "standard" else preset_id
    _current_cycle_index = PRESET_ORDER.index(preset_id)
    _cfg["currentPreset"] = preset_id
    save_config()
    return True


def get_preset_labels():
    return dict(PRESET_LABELS)


def get_weather_system_labels():
    return dict(WEATHER_SYSTEM_LABELS)


def get_preset_order():
    return list(PRESET_ORDER)


# -----------------------------------------------------------------------------
# main hotkey action
# -----------------------------------------------------------------------------
def cycle_weather_in_battle():
    global _current_cycle_index, _current_override_preset

    try:
        current = _current_override_preset or 'standard'
        if current not in PRESET_ORDER:
            current = 'standard'

        idx = PRESET_ORDER.index(current)
        next_preset = PRESET_ORDER[(idx + 1) % len(PRESET_ORDER)]

        _current_cycle_index = PRESET_ORDER.index(next_preset)
        _current_override_preset = None if next_preset == 'standard' else next_preset
        _cfg["currentPreset"] = next_preset

        arena_name = _get_current_arena_name()
        battle_loaded = arena_name is not None

        LOG.info('cycle_weather_in_battle: current=%s next=%s battle_loaded=%s arena_name=%s',
                 current, next_preset, battle_loaded, arena_name)

        applied_live = False
        applied_next = False

        if battle_loaded:
            applied_live = apply_environment_live(arena_name, _current_override_preset)

            if not applied_live:
                applied_next = apply_environment_via_geometry_mapping(arena_name, _current_override_preset)
        else:
            LOG.warning('cycle_weather_in_battle: battle not ready, storing only for later')

        save_config()

        if applied_live:
            _push_message(u'[Weather] %s (live)' % PRESET_LABELS.get(next_preset, next_preset))
        elif applied_next:
            _push_message(u'[Weather] %s (наступний бій)' % PRESET_LABELS.get(next_preset, next_preset))
        else:
            _push_message(u'[Weather] %s (runtime недоступний, дивись python.log)' %
                          PRESET_LABELS.get(next_preset, next_preset))

        return applied_live or applied_next

    except Exception:
        LOG.error('cycle_weather_in_battle: fatal error\n%s', traceback.format_exc())
        return False


# -----------------------------------------------------------------------------
# compatibility wrapper class
# -----------------------------------------------------------------------------
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
