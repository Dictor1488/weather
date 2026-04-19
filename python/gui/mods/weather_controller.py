# -*- coding: utf-8 -*-
"""
Weather controller v5.0

Читає дані прямо з environments.*.wotmod:
- шукає встановлені пакети в mods/<version>/
- витягує реальні GUID та <name> з environment.xml
- будує registry: preset -> space -> {guid, env_name, package}
- застосовує preset до карти через space.settings + environments/environments.xml

Без хардкоду GUID та без обов'язкового geometry_mapping.json.
"""
import json
import os
import random
import logging
import traceback
import zipfile
import re

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

PRESET_PACKAGE_PATTERNS = {
    "midday": re.compile(r"^environments\.midday_.*\.wotmod$", re.I),
    "midnight": re.compile(r"^environments\.midnight_.*\.wotmod$", re.I),
    "overcast": re.compile(r"^environments\.overcast_.*\.wotmod$", re.I),
    "sunset": re.compile(r"^environments\.sunset_.*\.wotmod$", re.I),
}

ENV_XML_RE = re.compile(
    r"^res/spaces/([^/]+)/environments/([A-Fa-f0-9\-]+)/environment\.xml$",
    re.I
)
ENV_NAME_RE = re.compile(r"<name>\s*([^<]+?)\s*</name>", re.I | re.S)

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
    "hotkey": {"enabled": True, "mods": ["LALT"], "key": "KEY_F12"},
    "iconPosition": {"x": 20, "y": 120},
}

_cfg = {}
_current_override_preset = None
_current_cycle_index = 0
_environment_registry = {}
_registry_loaded = False
_last_space_name = None


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


def _safe_listdir(path):
    try:
        return os.listdir(path)
    except Exception:
        return []


def _has_game_layout(base_path):
    try:
        if not base_path or not os.path.isdir(base_path):
            return False
        return os.path.isdir(os.path.join(base_path, 'mods')) or os.path.isdir(os.path.join(base_path, 'res_mods'))
    except Exception:
        return False


def _resolve_game_root():
    candidates = []

    try:
        cwd = os.path.abspath(os.getcwd())
        candidates.append(cwd)
        candidates.append(os.path.abspath(os.path.join(cwd, '..')))
    except Exception:
        pass

    try:
        exe_path = getattr(os, 'getcwd', None) and os.getcwd()
        if exe_path:
            candidates.append(os.path.abspath(exe_path))
    except Exception:
        pass

    try:
        if IN_GAME:
            prefs = (BigWorld.wg_getPreferencesFilePath()
                     if hasattr(BigWorld, 'wg_getPreferencesFilePath')
                     else BigWorld.getPreferencesFilePath())
            if prefs:
                prefs_dir = os.path.dirname(prefs)
                candidates.append(os.path.abspath(os.path.join(prefs_dir, '..', '..', '..', '..')))
    except Exception:
        LOG.error('_resolve_game_root via prefs failed\n%s', traceback.format_exc())

    seen = set()
    for candidate in candidates:
        candidate = os.path.normpath(candidate)
        if candidate in seen:
            continue
        seen.add(candidate)
        if _has_game_layout(candidate):
            LOG.info('Resolved game root: %s', candidate)
            return candidate

    fallback = os.path.abspath(os.getcwd())
    LOG.warning('Could not confidently resolve game root, fallback=%s candidates=%s', fallback, candidates)
    return fallback


def _find_latest_version_dir(root_name):
    game_root = _resolve_game_root()
    root = os.path.join(game_root, root_name)
    if not os.path.isdir(root):
        LOG.warning('%s root not found: %s', root_name, root)
        return None

    dirs = []
    for name in _safe_listdir(root):
        full = os.path.join(root, name)
        if os.path.isdir(full):
            dirs.append(full)

    if not dirs:
        LOG.warning('No version dirs in %s', root)
        return None

    dirs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    LOG.info('Resolved latest %s dir: %s', root_name, dirs[0])
    return dirs[0]


def _extract_env_name(xml_bytes):
    try:
        if not isinstance(xml_bytes, basestring):
            xml_text = xml_bytes.decode('utf-8', 'ignore')
        else:
            xml_text = xml_bytes
        match = ENV_NAME_RE.search(xml_text)
        if match:
            return match.group(1).strip()
    except Exception:
        LOG.error('_extract_env_name failed\n%s', traceback.format_exc())
    return None


def _detect_preset_from_filename(filename):
    lower = os.path.basename(filename).lower()
    for preset_id, pattern in PRESET_PACKAGE_PATTERNS.items():
        if pattern.match(lower):
            return preset_id
    return None


def scan_environment_packages():
    packages = []
    version_dir = _find_latest_version_dir('mods')
    if not version_dir:
        return packages

    candidates = [version_dir, os.path.join(version_dir, 'environments')]
    seen = set()

    for folder in candidates:
        if not os.path.isdir(folder):
            continue

        for name in _safe_listdir(folder):
            lower = name.lower()
            if not lower.endswith('.wotmod'):
                continue
            if not lower.startswith('environments.'):
                continue

            preset_id = _detect_preset_from_filename(name)
            if not preset_id:
                continue

            full_path = os.path.normpath(os.path.join(folder, name))
            if full_path in seen:
                continue

            seen.add(full_path)
            packages.append({
                'preset_id': preset_id,
                'path': full_path,
                'name': name,
            })

    LOG.info('scan_environment_packages: found=%s packages=%s', len(packages), [p['name'] for p in packages])
    return packages


def _read_package_registry_entry(package_info):
    result = {
        'preset_id': package_info['preset_id'],
        'path': package_info['path'],
        'name': package_info['name'],
        'spaces': {},
    }

    try:
        archive = zipfile.ZipFile(package_info['path'], 'r')
    except Exception:
        LOG.error('Failed to open package: %s\n%s', package_info['path'], traceback.format_exc())
        return result

    try:
        for member in archive.namelist():
            match = ENV_XML_RE.match(member)
            if not match:
                continue

            space_name = match.group(1)
            guid = match.group(2).upper()

            try:
                xml_bytes = archive.read(member)
            except Exception:
                LOG.error('Failed to read %s from %s\n%s', member, package_info['path'], traceback.format_exc())
                continue

            env_name = _extract_env_name(xml_bytes)
            if not env_name:
                LOG.warning('No <name> in %s from %s', member, package_info['name'])
                continue

            result['spaces'][space_name] = {
                'guid': guid,
                'env_name': env_name,
                'package': package_info['name'],
                'package_path': package_info['path'],
                'environment_xml_path': member,
            }
    finally:
        try:
            archive.close()
        except Exception:
            pass

    LOG.info('Loaded package %s preset=%s spaces=%s', package_info['name'], package_info['preset_id'], len(result['spaces']))
    return result


def load_environment_registry(force=False):
    global _environment_registry, _registry_loaded

    if _registry_loaded and not force:
        return _environment_registry

    registry = {}
    packages = scan_environment_packages()

    for package_info in packages:
        package_data = _read_package_registry_entry(package_info)
        preset_id = package_data['preset_id']
        entry = registry.setdefault(preset_id, {
            'package': package_data['name'],
            'package_path': package_data['path'],
            'spaces': {},
        })
        if package_data['spaces']:
            entry['spaces'].update(package_data['spaces'])

    _environment_registry = registry
    _registry_loaded = True

    summary = {}
    for preset_id, data in registry.items():
        summary[preset_id] = len(data.get('spaces', {}))
    LOG.info('Environment registry loaded: %s', summary)
    return _environment_registry


def get_environment_registry():
    return load_environment_registry(force=False)


def resolve_environment_for_space(space_name, preset_id):
    if not preset_id or preset_id == 'standard':
        return None

    registry = get_environment_registry()
    preset_data = registry.get(preset_id)
    if not preset_data:
        LOG.warning('resolve_environment_for_space: preset not found in registry: %s', preset_id)
        return None

    data = preset_data.get('spaces', {}).get(space_name)
    if not data:
        LOG.warning('resolve_environment_for_space: no space=%s in preset=%s package=%s', space_name, preset_id, preset_data.get('package'))
        return None

    return data


def _get_fallback_preset_order(primary_preset):
    order = []
    if primary_preset and primary_preset != 'standard':
        order.append(primary_preset)
    for preset_id in PRESET_ORDER:
        if preset_id == 'standard':
            continue
        if preset_id not in order:
            order.append(preset_id)
    return order


def resolve_environment_with_fallback(space_name, preset_id):
    candidates = _get_fallback_preset_order(preset_id)
    if not candidates:
        return None, None

    for candidate in candidates:
        resolved = resolve_environment_for_space(space_name, candidate)
        if resolved:
            if candidate != preset_id:
                LOG.warning('resolve_environment_with_fallback: fallback selected for space=%s requested=%s actual=%s package=%s', space_name, preset_id, candidate, resolved.get('package'))
            else:
                LOG.info('resolve_environment_with_fallback: exact preset selected for space=%s preset=%s package=%s', space_name, candidate, resolved.get('package'))
            return candidate, resolved

    LOG.warning('resolve_environment_with_fallback: no available preset for space=%s requested=%s candidates=%s', space_name, preset_id, candidates)
    return None, None


def get_preset_guid(preset_id, space_name=None):
    if not preset_id or preset_id == 'standard':
        return None

    registry = get_environment_registry()
    preset_data = registry.get(preset_id)
    if not preset_data:
        return None

    if space_name:
        data = preset_data.get('spaces', {}).get(space_name)
        return data.get('guid') if data else None

    spaces = preset_data.get('spaces', {})
    for _space_name, data in spaces.items():
        guid = data.get('guid')
        if guid:
            return guid
    return None


def load_config():
    global _cfg
    _cfg = json.loads(json.dumps(DEFAULT_CFG))
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                user_cfg = json.load(f)
            _deep_update(_cfg, user_cfg)
    except Exception:
        logger.exception('load_config failed')

    _cfg['generalWeights'] = _normalize_weights(_cfg.get('generalWeights', {}))
    maps = _cfg.get('mapWeights', {})
    fixed = {}
    for map_name, weights in maps.items():
        if isinstance(weights, dict):
            fixed[map_name] = _normalize_weights(weights)
    _cfg['mapWeights'] = fixed
    save_config()
    load_environment_registry(force=True)
    logger.info('config loaded from %s', CONFIG_PATH)
    return _cfg


def save_config():
    try:
        _ensure_dir(CONFIG_PATH)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(_cfg, f, indent=2, sort_keys=True)
    except Exception:
        logger.exception('save_config failed')


def get_config():
    return _cfg


def is_enabled():
    return bool(_cfg.get('enabled', True))


def set_enabled(flag):
    _cfg['enabled'] = bool(flag)
    save_config()


def get_show_in_battle():
    return bool(_cfg.get('show_in_battle', True))


def set_show_in_battle(flag):
    _cfg['show_in_battle'] = bool(flag)
    save_config()


def get_general_weights():
    return dict(_cfg.get('generalWeights', {}))


def set_general_weights(weights):
    _cfg['generalWeights'] = _normalize_weights(weights or {})
    save_config()


def get_map_weights(map_name):
    maps = _cfg.setdefault('mapWeights', {})
    return dict(maps.get(map_name, _cfg.get('generalWeights', {})))


def set_map_weights(map_name, weights):
    maps = _cfg.setdefault('mapWeights', {})
    maps[map_name] = _normalize_weights(weights or {})
    save_config()


def get_hotkey():
    hk = _cfg.get('hotkey', {})
    return {
        'enabled': bool(hk.get('enabled', True)),
        'mods': list(hk.get('mods', ['LALT'])),
        'key': hk.get('key', 'KEY_F12')
    }


def set_hotkey(enabled, mods, key):
    _cfg['hotkey'] = {
        'enabled': bool(enabled),
        'mods': list(mods or []),
        'key': key
    }
    save_config()


def get_icon_position():
    pos = _cfg.get('iconPosition', {})
    return int(pos.get('x', 20)), int(pos.get('y', 120))


def set_icon_position(x, y):
    _cfg['iconPosition'] = {'x': int(x), 'y': int(y)}
    save_config()


def weighted_choice(weights_dict):
    pool = []
    for preset in PRESET_ORDER:
        w = int(weights_dict.get(preset, 0))
        if w > 0:
            pool.extend([preset] * w)
    if not pool:
        return 'standard'
    return random.choice(pool)


def get_preset_for_map(map_name):
    maps = _cfg.get('mapWeights', {})
    if map_name in maps:
        return weighted_choice(maps[map_name])
    return weighted_choice(_cfg.get('generalWeights', {}))


def get_all_general_for_ui():
    items = []
    weights = _cfg.get('generalWeights', {})
    registry = get_environment_registry()
    for preset in PRESET_ORDER:
        label = PRESET_LABELS[preset]
        if preset != 'standard' and preset not in registry:
            label += u' [missing]'
        items.append({'id': preset, 'label': label, 'weight': int(weights.get(preset, 0))})
    return items


def get_all_for_map_ui(map_name):
    items = []
    weights = get_map_weights(map_name)
    registry = get_environment_registry()
    for preset in PRESET_ORDER:
        label = PRESET_LABELS[preset]
        if preset != 'standard':
            has_space = bool(registry.get(preset, {}).get('spaces', {}).get(map_name))
            if not has_space:
                label += u' [n/a]'
        items.append({'id': preset, 'label': label, 'weight': int(weights.get(preset, 0))})
    return items


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


def build_environments_xml(active_guid, all_guids):
    if not active_guid:
        return None

    def _dotted(guid):
        return guid.replace('-', '.')

    lines = [u'<root>']
    lines.append(u'\t<activeEnvironment>{0}</activeEnvironment>'.format(_dotted(active_guid)))
    lines.append(u'\t<isEnvironmentSwitchAllowed>False</isEnvironmentSwitchAllowed>')

    seen = set()
    ordered = []
    for g in all_guids:
        if g and g not in seen:
            seen.add(g)
            ordered.append(g)
    if active_guid not in seen:
        ordered.append(active_guid)

    for g in ordered:
        lines.append(u'\t<environment>{0}</environment>'.format(_dotted(g)))

    lines.append(u'</root>')
    lines.append(u'')
    return u'\r\n'.join(lines)


def find_space_settings_path(space_name):
    try:
        version_dir = _find_latest_version_dir('res_mods')
        if not version_dir:
            LOG.warning('find_space_settings_path: no res_mods version dir')
            return None
        candidate = os.path.join(version_dir, 'spaces', space_name, 'space.settings')
        LOG.info('find_space_settings_path: candidate=%s', candidate)
        return candidate
    except Exception:
        LOG.error('find_space_settings_path: failed\n%s', traceback.format_exc())
        return None


def find_environments_xml_path(space_name):
    try:
        version_dir = _find_latest_version_dir('res_mods')
        if not version_dir:
            return None
        candidate = os.path.join(version_dir, 'spaces', space_name, 'environments', 'environments.xml')
        LOG.info('find_environments_xml_path: candidate=%s', candidate)
        return candidate
    except Exception:
        LOG.error('find_environments_xml_path: failed\n%s', traceback.format_exc())
        return None


def _write_text_file(target_path, content):
    try:
        folder = os.path.dirname(target_path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with open(target_path, 'w') as f:
            f.write(content)
        LOG.info('wrote %s bytes to %s', len(content), target_path)
        return True
    except Exception:
        LOG.error('write %s failed\n%s', target_path, traceback.format_exc())
        return False


def write_space_settings_to_res_mods(target_path, content):
    return _write_text_file(target_path, content)


def _get_all_known_guids_for_space(space_name):
    registry = get_environment_registry()
    guids = []
    for _preset_id, preset_data in registry.items():
        entry = preset_data.get('spaces', {}).get(space_name)
        if entry and entry.get('guid'):
            guids.append(entry['guid'])
    return guids


def apply_environment_via_packages(space_name, preset_id):
    try:
        LOG.info('apply_environment_via_packages: start space=%s preset=%s', space_name, preset_id)

        if not space_name:
            LOG.warning('apply_environment_via_packages: no space_name')
            return False
        if not preset_id or preset_id == 'standard':
            LOG.info('apply_environment_via_packages: preset is standard, skipping override')
            return False

        actual_preset_id, resolved = resolve_environment_with_fallback(space_name, preset_id)
        if not resolved:
            return False

        env_name = resolved.get('env_name')
        preset_guid = resolved.get('guid')
        LOG.info('apply_environment_via_packages: resolved requested=%s actual=%s env_name=%s guid=%s package=%s', preset_id, actual_preset_id, env_name, preset_guid, resolved.get('package'))

        space_settings_path = find_space_settings_path(space_name)
        if not space_settings_path:
            LOG.warning('apply_environment_via_packages: space_settings path not found for %s', space_name)
            return False
        settings_content = build_space_settings_xml(env_name, preset_guid)
        if not settings_content:
            LOG.warning('apply_environment_via_packages: generated empty space.settings')
            return False
        ok1 = _write_text_file(space_settings_path, settings_content)

        env_xml_path = find_environments_xml_path(space_name)
        if not env_xml_path:
            LOG.warning('apply_environment_via_packages: environments.xml path not found for %s', space_name)
            return ok1
        all_guids = _get_all_known_guids_for_space(space_name)
        env_xml_content = build_environments_xml(preset_guid, all_guids)
        if not env_xml_content:
            LOG.warning('apply_environment_via_packages: generated empty environments.xml')
            return ok1
        ok2 = _write_text_file(env_xml_path, env_xml_content)

        LOG.info('apply_environment_via_packages: space.settings=%s environments.xml=%s', ok1, ok2)
        return ok1 and ok2
    except Exception:
        LOG.error('apply_environment_via_packages: failed\n%s', traceback.format_exc())
        return False


def on_space_entered(space_name):
    global _last_space_name
    try:
        LOG.info('on_space_entered: raw space_name=%s override=%s', space_name, _current_override_preset)
        if not space_name:
            LOG.warning('on_space_entered: empty space_name')
            return False

        _last_space_name = space_name

        preset_id = _current_override_preset
        if not preset_id:
            preset_id = get_preset_for_map(space_name)
        LOG.info('on_space_entered: chosen preset=%s', preset_id if preset_id else 'standard')

        result = apply_environment_via_packages(space_name, preset_id)
        LOG.info('on_space_entered: apply_environment_via_packages(space=%s, preset=%s) -> %s', space_name, preset_id, result)
        return result
    except Exception:
        LOG.error('on_space_entered: failed\n%s', traceback.format_exc())
        return False


def cycle_weather_system():
    try:
        import Weather
        if not hasattr(Weather, 's_weather') or Weather.s_weather is None:
            logger.warning('Weather.s_weather unavailable')
            return
        cur = getattr(Weather.s_weather, 'currentWeatherSystem', None)
        all_names = list(WEATHER_SYSTEM_LABELS.keys())
        nxt = all_names[0] if cur not in all_names else all_names[(all_names.index(cur) + 1) % len(all_names)]
        Weather.s_weather.nextWeatherSystem(nxt)
        logger.info('fallback weather system changed: %s -> %s', cur, nxt)
        try:
            SystemMessages.pushMessage(u'[Weather] Системна погода: %s' % WEATHER_SYSTEM_LABELS.get(nxt, nxt), SystemMessages.SM_TYPE.Information)
        except Exception:
            pass
    except Exception:
        logger.exception('cycle_weather_system failed')


def _normalize_space_name(name):
    if not name or not isinstance(name, basestring):
        return None
    result = name.strip()
    if not result:
        return None
    if '/' in result:
        result = result.rsplit('/', 1)[-1]
    return result or None


def _resolve_current_arena_name():
    try:
        import BigWorld
        player = BigWorld.player()
        if player is None:
            return _last_space_name

        arena = getattr(player, 'arena', None)
        if arena is not None:
            arena_type = getattr(arena, 'arenaType', None)
            if arena_type is not None:
                for attr in ('geometryName', 'geometry', 'name'):
                    value = _normalize_space_name(getattr(arena_type, attr, None))
                    if value:
                        return value
            value = _normalize_space_name(getattr(arena, 'geometryName', None))
            if value:
                return value
    except Exception:
        LOG.error('_resolve_current_arena_name failed\n%s', traceback.format_exc())
    return _last_space_name


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
        try:
            import BigWorld
            player = BigWorld.player()
            battle_loaded = player is not None and getattr(player, 'arena', None) is not None
        except Exception:
            LOG.error('cycle_weather_in_battle: failed to inspect BigWorld state\n%s', traceback.format_exc())

        arena_name = _resolve_current_arena_name()
        LOG.info('cycle_weather_in_battle: battle_loaded=%s arena_name=%s override=%s', battle_loaded, arena_name, _current_override_preset)

        applied = False
        if arena_name:
            try:
                applied = apply_environment_via_packages(arena_name, _current_override_preset)
                LOG.info('cycle_weather_in_battle: apply_environment_via_packages returned %s for arena=%s preset=%s', applied, arena_name, _current_override_preset)
            except Exception:
                LOG.error('cycle_weather_in_battle: apply failed\n%s', traceback.format_exc())
        else:
            LOG.warning('cycle_weather_in_battle: arena name unknown, preset only stored')

        save_config()

        msg = '[Weather] preset: %s' % next_preset
        if applied:
            msg += ' (applied)'
        elif battle_loaded and arena_name:
            msg += ' (stored, may require reload)'
        else:
            msg += ' (stored for next battle)'

        if SystemMessages is not None:
            try:
                SystemMessages.pushMessage(msg, SystemMessages.SM_TYPE.Information)
            except Exception:
                LOG.error('cycle_weather_in_battle: failed to show system message\n%s', traceback.format_exc())
    except Exception:
        LOG.error('cycle_weather_in_battle: fatal error\n%s', traceback.format_exc())


def get_current_override_preset():
    return _current_override_preset or 'standard'


def set_override_preset(preset_id):
    global _current_override_preset, _current_cycle_index
    if preset_id not in PRESET_ORDER:
        return
    _current_override_preset = None if preset_id == 'standard' else preset_id
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

    def getEnvironmentRegistry(self):
        return get_environment_registry()


g_controller = WeatherController()
