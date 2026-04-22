# -*- coding: utf-8 -*-
"""
Weather controller v6.0

Зміни відносно v5.12:
- CORE FIX: виправлено інвертовану логіку onEnterWorld (більше не пропускає запис)
- CORE FIX: onBecomePlayer тепер спочатку читає arenaTypeID через ArenaType.g_cache
- feat: live-зміна environment через EnvironmentsSettingsUI DAAPI
        (interactiveEvent_overrideIngame → as_setStaticData / as_setDynamicData)
- feat: живий BigWorld API пошук: wg_setSpaceEnvironmentId / setSpaceEnvironmentID /
        BigWorld.wg_reloadEnvironment
- fix: _become_player_wrote_for_space більше не блокує onEnterWorld при неуспішному записі
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
    "overcast": u"Хмарно",
    "sunset":   u"Захід",
    "midday":   u"Полудень",
}

PRESET_ORDER = ["standard", "midnight", "overcast", "sunset", "midday"]
MAX_WEIGHT = 20
DEFAULT_WEIGHT_VALUE = 20
DEFAULT_EQUAL_WEIGHTS = dict((k, DEFAULT_WEIGHT_VALUE) for k in PRESET_ORDER)

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
    "midday":   re.compile(r"^environments\.midday_.*\.wotmod$",   re.I),
    "midnight": re.compile(r"^environments\.midnight_.*\.wotmod$", re.I),
    "overcast": re.compile(r"^environments\.overcast_.*\.wotmod$", re.I),
    "sunset":   re.compile(r"^environments\.sunset_.*\.wotmod$",   re.I),
}
SPACES_WG_PACKAGE_RE = re.compile(r"^environments\.spaces_wg_.*\.wotmod$", re.I)

ENV_XML_RE = re.compile(
    r"^res/spaces/([^/]+)/environments/([A-Fa-f0-9\-]+)/environment\.xml$",
    re.I
)
ENV_NAME_RE_OLD = re.compile(r"<n>\s*([^<]+?)\s*</n>",  re.I | re.S)
ENV_NAME_RE_NEW = re.compile(r"<n>\t([^\t<]+)\t</n>",   re.I)
_ENV_NAME_SKIP  = frozenset(['RexpTM', 'FilmicTM', 'LinearExpTM'])
ROOT_ENV_RE          = re.compile(r'(<environment>)([^<]*)(</environment>)',                 re.I)
ROOT_ENV_OVERRIDE_RE = re.compile(r'(<environmentOverride>)([^<]*)(</environmentOverride>)', re.I)

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
    "generalWeights": dict(DEFAULT_EQUAL_WEIGHTS),
    "mapWeights": {},
    "hotkey": {"enabled": True, "mods": [], "key": "KEY_F12"},
    "iconPosition": {"x": 20, "y": 120},
    "currentOverridePreset": "standard",
}

_cfg = {}
_current_override_preset  = None
_current_cycle_index      = 0
_environment_registry     = {}
_registry_loaded          = False
_last_space_name          = None
_spaces_wg_package_path   = None
_spaces_wg_template_cache = {}
_pending_reload_cb        = None


# ---------------------------------------------------------------------------
# Утиліти
# ---------------------------------------------------------------------------

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

def _is_zero_weights(dct):
    if not isinstance(dct, dict):
        return True
    for key in PRESET_ORDER:
        try:
            if int(dct.get(key, 0)) > 0:
                return False
        except Exception:
            pass
    return True

def _effective_weights(dct, fallback=None):
    normalized = _normalize_weights(dct or {})
    if not _is_zero_weights(normalized):
        return normalized
    if fallback is not None:
        fallback_normalized = _normalize_weights(fallback)
        if not _is_zero_weights(fallback_normalized):
            return fallback_normalized
    return dict(DEFAULT_EQUAL_WEIGHTS)

def _safe_listdir(path):
    try:
        return os.listdir(path)
    except Exception:
        return []

def _has_game_layout(base_path):
    try:
        if not base_path or not os.path.isdir(base_path):
            return False
        return (os.path.isdir(os.path.join(base_path, 'mods')) or
                os.path.isdir(os.path.join(base_path, 'res_mods')))
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
        if IN_GAME:
            prefs = (BigWorld.wg_getPreferencesFilePath()
                     if hasattr(BigWorld, 'wg_getPreferencesFilePath')
                     else BigWorld.getPreferencesFilePath())
            if prefs:
                candidates.append(os.path.abspath(
                    os.path.join(os.path.dirname(prefs), '..', '..', '..', '..')))
    except Exception:
        LOG.error('_resolve_game_root via prefs failed\n%s', traceback.format_exc())
    seen = set()
    for c in candidates:
        c = os.path.normpath(c)
        if c in seen:
            continue
        seen.add(c)
        if _has_game_layout(c):
            LOG.info('Resolved game root: %s', c)
            return c
    fallback = os.path.abspath(os.getcwd())
    LOG.warning('Could not resolve game root, fallback=%s', fallback)
    return fallback

def _find_latest_version_dir(root_name):
    game_root = _resolve_game_root()
    root = os.path.join(game_root, root_name)
    if not os.path.isdir(root):
        LOG.warning('%s root not found: %s', root_name, root)
        return None
    dirs = [os.path.join(root, n) for n in _safe_listdir(root)
            if os.path.isdir(os.path.join(root, n))]
    if not dirs:
        LOG.warning('No version dirs in %s', root)
        return None
    dirs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    LOG.info('Resolved latest %s dir: %s', root_name, dirs[0])
    return dirs[0]


# ---------------------------------------------------------------------------
# Парсинг пакетів environment
# ---------------------------------------------------------------------------

def _extract_env_name(xml_bytes):
    try:
        xml_text = (xml_bytes.decode('utf-8', 'ignore')
                    if not isinstance(xml_bytes, basestring) else xml_bytes)
        for m in ENV_NAME_RE_NEW.finditer(xml_text):
            val = m.group(1).strip()
            if val and val not in _ENV_NAME_SKIP and '/' not in val:
                return val
        for m in ENV_NAME_RE_OLD.finditer(xml_text):
            val = m.group(1).strip()
            if val and val not in _ENV_NAME_SKIP and '/' not in val:
                return val
    except Exception:
        LOG.error('_extract_env_name failed\n%s', traceback.format_exc())
    return None

def _detect_preset_from_filename(filename):
    lower = os.path.basename(filename).lower()
    for preset_id, pattern in PRESET_PACKAGE_PATTERNS.items():
        if pattern.match(lower):
            return preset_id
    return None

def _find_spaces_wg_package_path():
    version_dir = _find_latest_version_dir('mods')
    if not version_dir:
        return None
    for folder in [os.path.join(version_dir, 'environments'), version_dir]:
        if not os.path.isdir(folder):
            continue
        for name in _safe_listdir(folder):
            if SPACES_WG_PACKAGE_RE.match(name):
                path = os.path.normpath(os.path.join(folder, name))
                LOG.info('Resolved spaces_wg package: %s', path)
                return path
    LOG.warning('spaces_wg package not found')
    return None

def _get_spaces_wg_package_path():
    global _spaces_wg_package_path
    if _spaces_wg_package_path and os.path.isfile(_spaces_wg_package_path):
        return _spaces_wg_package_path
    _spaces_wg_package_path = _find_spaces_wg_package_path()
    return _spaces_wg_package_path

def scan_environment_packages():
    packages = []
    version_dir = _find_latest_version_dir('mods')
    if not version_dir:
        return packages
    seen = set()
    for folder in [version_dir, os.path.join(version_dir, 'environments')]:
        if not os.path.isdir(folder):
            continue
        for name in _safe_listdir(folder):
            lower = name.lower()
            if not lower.endswith('.wotmod') or not lower.startswith('environments.'):
                continue
            preset_id = _detect_preset_from_filename(name)
            if not preset_id:
                continue
            full_path = os.path.normpath(os.path.join(folder, name))
            if full_path in seen:
                continue
            seen.add(full_path)
            packages.append({'preset_id': preset_id, 'path': full_path, 'name': name})
    LOG.info('scan_environment_packages: found=%s', len(packages))
    return packages

def _read_package_registry_entry(package_info):
    result = {
        'preset_id': package_info['preset_id'],
        'path':      package_info['path'],
        'name':      package_info['name'],
        'spaces':    {},
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
                continue
            env_name = _extract_env_name(xml_bytes)
            if not env_name:
                continue
            result['spaces'][space_name] = {
                'guid':                 guid,
                'env_name':             env_name,
                'package':              package_info['name'],
                'package_path':         package_info['path'],
                'environment_xml_path': member,
            }
    finally:
        try:
            archive.close()
        except Exception:
            pass
    LOG.info('Loaded package %s preset=%s spaces=%s',
             package_info['name'], package_info['preset_id'], len(result['spaces']))
    return result

def load_environment_registry(force=False):
    global _environment_registry, _registry_loaded, _spaces_wg_package_path, _spaces_wg_template_cache
    if _registry_loaded and not force:
        return _environment_registry
    registry = {}
    for package_info in scan_environment_packages():
        package_data = _read_package_registry_entry(package_info)
        preset_id = package_data['preset_id']
        entry = registry.setdefault(preset_id, {
            'package':      package_data['name'],
            'package_path': package_data['path'],
            'spaces':       {},
        })
        if package_data['spaces']:
            entry['spaces'].update(package_data['spaces'])
    _environment_registry     = registry
    _registry_loaded          = True
    _spaces_wg_package_path   = _find_spaces_wg_package_path()
    _spaces_wg_template_cache = {}
    LOG.info('Environment registry loaded: %s',
             {pid: len(d.get('spaces', {})) for pid, d in registry.items()})
    return _environment_registry

def get_environment_registry():
    return load_environment_registry(force=False)

def resolve_environment_for_space(space_name, preset_id):
    if not preset_id or preset_id == 'standard':
        return None
    registry = get_environment_registry()
    preset_data = registry.get(preset_id)
    if not preset_data:
        LOG.warning('resolve_environment_for_space: preset not found: %s', preset_id)
        return None
    data = preset_data.get('spaces', {}).get(space_name)
    if not data:
        LOG.warning('resolve_environment_for_space: no space=%s in preset=%s', space_name, preset_id)
    return data

def _get_fallback_preset_order(primary_preset):
    order = []
    if primary_preset and primary_preset != 'standard':
        order.append(primary_preset)
    for p in PRESET_ORDER:
        if p != 'standard' and p not in order:
            order.append(p)
    return order

def resolve_environment_with_fallback(space_name, preset_id):
    for candidate in _get_fallback_preset_order(preset_id):
        resolved = resolve_environment_for_space(space_name, candidate)
        if resolved:
            if candidate != preset_id:
                LOG.warning('resolve_with_fallback: fallback space=%s req=%s actual=%s',
                            space_name, preset_id, candidate)
            return candidate, resolved
    LOG.warning('resolve_with_fallback: no preset for space=%s req=%s', space_name, preset_id)
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
    for _, data in preset_data.get('spaces', {}).items():
        guid = data.get('guid')
        if guid:
            return guid
    return None


# ---------------------------------------------------------------------------
# Конфіг
# ---------------------------------------------------------------------------

def load_config():
    global _cfg, _current_override_preset, _current_cycle_index
    _cfg = json.loads(json.dumps(DEFAULT_CFG))
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                user_cfg = json.load(f)
            _deep_update(_cfg, user_cfg)
    except Exception:
        logger.exception('load_config failed')
    _cfg['generalWeights'] = _normalize_weights(_cfg.get('generalWeights', {}))
    fixed = {}
    for map_name, weights in _cfg.get('mapWeights', {}).items():
        if isinstance(weights, dict):
            fixed[map_name] = _normalize_weights(weights)
    _cfg['mapWeights'] = fixed
    saved_preset = _cfg.get('currentOverridePreset', 'standard')
    if saved_preset not in PRESET_ORDER:
        saved_preset = 'standard'
    _current_override_preset = None if saved_preset == 'standard' else saved_preset
    _current_cycle_index = PRESET_ORDER.index(saved_preset) if saved_preset in PRESET_ORDER else 0
    save_config()
    load_environment_registry(force=True)
    logger.info('config loaded from %s, preset=%s', CONFIG_PATH, saved_preset)
    return _cfg

def save_config():
    try:
        _cfg['currentOverridePreset'] = _current_override_preset or 'standard'
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
    return _effective_weights(_cfg.get('generalWeights', {}))

def set_general_weights(weights):
    _cfg['generalWeights'] = _normalize_weights(weights or {})
    save_config()

def get_map_weights(map_name):
    maps = _cfg.setdefault('mapWeights', {})
    map_weights = maps.get(map_name)
    if map_weights is None:
        return get_general_weights()
    return _effective_weights(map_weights, get_general_weights())

def set_map_weights(map_name, weights):
    _cfg.setdefault('mapWeights', {})[map_name] = _normalize_weights(weights or {})
    save_config()

def get_hotkey():
    hk = _cfg.get('hotkey', {})
    return {'enabled': bool(hk.get('enabled', True)),
            'mods':    list(hk.get('mods', [])),
            'key':     hk.get('key', 'KEY_F12')}

def set_hotkey(enabled, mods, key):
    _cfg['hotkey'] = {'enabled': bool(enabled), 'mods': list(mods or []), 'key': key}
    save_config()

def get_icon_position():
    pos = _cfg.get('iconPosition', {})
    return int(pos.get('x', 20)), int(pos.get('y', 120))

def set_icon_position(x, y):
    _cfg['iconPosition'] = {'x': int(x), 'y': int(y)}
    save_config()

def weighted_choice(weights_dict):
    effective = _effective_weights(weights_dict)
    pool = []
    for preset in PRESET_ORDER:
        w = int(effective.get(preset, 0))
        if w > 0:
            pool.extend([preset] * w)
    if not pool:
        pool = list(PRESET_ORDER) * DEFAULT_WEIGHT_VALUE
    return random.choice(pool) if pool else 'standard'

def get_preset_for_map(map_name):
    return weighted_choice(get_map_weights(map_name))

def get_all_general_for_ui():
    items = []
    weights  = get_general_weights()
    registry = get_environment_registry()
    for preset in PRESET_ORDER:
        label = PRESET_LABELS[preset]
        if preset != 'standard' and preset not in registry:
            label += u' [missing]'
        items.append({'id': preset, 'label': label, 'weight': int(weights.get(preset, DEFAULT_WEIGHT_VALUE))})
    return items

def get_all_for_map_ui(map_name):
    items = []
    weights  = get_map_weights(map_name)
    registry = get_environment_registry()
    for preset in PRESET_ORDER:
        label = PRESET_LABELS[preset]
        if preset != 'standard' and not registry.get(preset, {}).get('spaces', {}).get(map_name):
            label += u' [n/a]'
        items.append({'id': preset, 'label': label, 'weight': int(weights.get(preset, DEFAULT_WEIGHT_VALUE))})
    return items


# ---------------------------------------------------------------------------
# space.settings патч
# ---------------------------------------------------------------------------

def _decode_xml_bytes(data):
    return data if isinstance(data, basestring) else data.decode('utf-8', 'ignore')

def _get_spaces_wg_templates(space_name):
    global _spaces_wg_template_cache
    if space_name in _spaces_wg_template_cache:
        return _spaces_wg_template_cache[space_name]
    result = {'space_settings': None}
    _spaces_wg_template_cache[space_name] = result
    path = _get_spaces_wg_package_path()
    if not path:
        return result
    try:
        archive = zipfile.ZipFile(path, 'r')
        try:
            ss_member = 'res/spaces/%s/space.settings' % space_name
            result['space_settings'] = _decode_xml_bytes(archive.read(ss_member))
            LOG.info('Loaded spaces_wg space.settings: %s', ss_member)
        except Exception:
            LOG.warning('spaces_wg template missing: %s', space_name)
        finally:
            archive.close()
    except Exception:
        LOG.error('Failed to open spaces_wg package\n%s', traceback.format_exc())
    return result

def _patch_space_settings_template(template_text, env_name, preset_guid):
    if not template_text:
        return None
    text = template_text
    closing_tag = u'</space.settings>' if '</space.settings>' in text else u'</root>'
    if ROOT_ENV_RE.search(text):
        text = ROOT_ENV_RE.sub(r'\1%s\3' % env_name, text, count=1)
    else:
        text = text.replace(closing_tag,
                            u'  <environment>%s</environment>\n%s' % (env_name, closing_tag), 1)
    if preset_guid:
        if ROOT_ENV_OVERRIDE_RE.search(text):
            text = ROOT_ENV_OVERRIDE_RE.sub(r'\1%s\3' % preset_guid, text, count=1)
        else:
            text = text.replace(closing_tag,
                                u'  <environmentOverride>%s</environmentOverride>\n%s' % (preset_guid, closing_tag), 1)
    else:
        text = ROOT_ENV_OVERRIDE_RE.sub(u'', text)
    return text

def find_space_settings_path(space_name):
    try:
        version_dir = _find_latest_version_dir('res_mods')
        if not version_dir:
            return None
        return os.path.join(version_dir, 'spaces', space_name, 'space.settings')
    except Exception:
        LOG.error('find_space_settings_path failed\n%s', traceback.format_exc())
        return None

def _find_environments_json_path():
    try:
        version_dir = _find_latest_version_dir('res_mods')
        if not version_dir:
            return None
        return os.path.normpath(
            os.path.join(version_dir, 'scripts', 'client', 'mods', 'environments.json'))
    except Exception:
        LOG.error('_find_environments_json_path failed\n%s', traceback.format_exc())
        return None

def _guid_to_dot(guid):
    return guid.replace('-', '.')

def write_environments_json_for_preset(preset_id, space_name=None):
    try:
        env_json_path = _find_environments_json_path()
        if not env_json_path:
            return False
        if not preset_id or preset_id == 'standard':
            if os.path.isfile(env_json_path):
                try:
                    os.remove(env_json_path)
                    LOG.info('write_environments_json: removed override')
                except Exception:
                    LOG.error('write_environments_json: remove failed\n%s', traceback.format_exc())
            return True
        registry   = get_environment_registry()
        preset_data = registry.get(preset_id)
        if not preset_data:
            return False
        guid = None
        if space_name:
            sd = preset_data.get('spaces', {}).get(space_name)
            if sd:
                guid = sd.get('guid')
        if not guid:
            for _, sd in preset_data.get('spaces', {}).items():
                guid = sd.get('guid')
                if guid:
                    break
        if not guid:
            return False
        guid_dot = _guid_to_dot(guid)
        payload = {
            "enabled":    True,
            "environments": [guid_dot],
            "labels":     {guid_dot: PRESET_LABELS.get(preset_id, preset_id)},
            "randomizer": {"advanced": {}, "common": {guid_dot: 100, "default": 0}},
            "toggleKeyset": [-1, 88],
        }
        folder = os.path.dirname(env_json_path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with open(env_json_path, 'w') as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
        LOG.info('write_environments_json: preset=%s guid=%s', preset_id, guid_dot)
        return True
    except Exception:
        LOG.error('write_environments_json failed\n%s', traceback.format_exc())
        return False

def _write_text_file(target_path, content):
    try:
        folder = os.path.dirname(target_path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with open(target_path, 'w') as f:
            f.write(content)
        return True
    except Exception:
        LOG.error('write %s failed\n%s', target_path, traceback.format_exc())
        return False


# ---------------------------------------------------------------------------
# LIVE зміна environment — BigWorld API
# ---------------------------------------------------------------------------

def _get_current_space_id():
    try:
        if not IN_GAME:
            return None
        player = BigWorld.player()
        if player is not None:
            sid = getattr(player, 'spaceID', None)
            if sid:
                return sid
        if hasattr(BigWorld, 'spaceID'):
            sid = BigWorld.spaceID()
            if sid:
                return sid
    except Exception:
        LOG.error('_get_current_space_id failed\n%s', traceback.format_exc())
    return None


def apply_environment_bigworld_api(space_id, guid):
    """
    Спроба застосувати environment LIVE через різні BigWorld API.

    WoT має кілька варіантів API залежно від версії клієнта:
      1. BigWorld.wg_setSpaceEnvironmentId(spaceID, guid_string)
      2. BigWorld.setSpaceEnvironmentID(spaceID, guid_string)
      3. BigWorld.wg_reloadEnvironment(spaceID)  — після запису файлів

    GUID може бути у форматі:
      - 'AABBCCDD-EEFF-0011-...'  (з дефісами)
      - 'AA.BB.CC.DD.EE.FF.00.11...'  (з крапками — формат WoT environments.json)

    Повертає True якщо хоча б один виклик не кинув виняток.
    """
    if not IN_GAME or not space_id:
        return False

    # Готуємо обидва формати guid
    guid_dash = guid.replace('.', '-') if '.' in guid else guid
    guid_dot  = guid.replace('-', '.') if '-' in guid else guid

    success = False

    # --- Спроба 1: wg_setSpaceEnvironmentId (найновіший WoT API) ---
    for fn_name in ('wg_setSpaceEnvironmentId', 'wg_setSpaceEnvironmentID'):
        fn = getattr(BigWorld, fn_name, None)
        if fn is None:
            continue
        for g in (guid_dash, guid_dot):
            try:
                fn(space_id, g)
                LOG.info('apply_env_bw: %s(%s, %s) OK', fn_name, space_id, g)
                success = True
                break
            except Exception as e:
                LOG.info('apply_env_bw: %s ERR: %s', fn_name, str(e)[:120])
        if success:
            break

    # --- Спроба 2: setSpaceEnvironmentID (старіший API) ---
    if not success:
        fn = getattr(BigWorld, 'setSpaceEnvironmentID', None)
        if fn is not None:
            for g in (guid_dash, guid_dot):
                try:
                    fn(space_id, g)
                    LOG.info('apply_env_bw: setSpaceEnvironmentID(%s, %s) OK', space_id, g)
                    success = True
                    break
                except Exception as e:
                    LOG.info('apply_env_bw: setSpaceEnvironmentID ERR: %s', str(e)[:120])

    # --- Спроба 3: wg_reloadEnvironment — після того як файли вже записані ---
    # Цей виклик змушує рушій перечитати space.settings з res_mods
    if hasattr(BigWorld, 'wg_reloadEnvironment'):
        try:
            BigWorld.wg_reloadEnvironment(space_id)
            LOG.info('apply_env_bw: wg_reloadEnvironment(%s) OK', space_id)
            success = True
        except Exception as e:
            LOG.info('apply_env_bw: wg_reloadEnvironment ERR: %s', str(e)[:120])

    # --- Спроба 4: notifySpaceChange — fallback ---
    if not success and hasattr(BigWorld, 'notifySpaceChange'):
        try:
            BigWorld.notifySpaceChange(space_id)
            LOG.info('apply_env_bw: notifySpaceChange(%s) called', space_id)
        except Exception as e:
            LOG.info('apply_env_bw: notifySpaceChange ERR: %s', str(e)[:120])

    return success


# ---------------------------------------------------------------------------
# LIVE зміна через EnvironmentsSettingsUI DAAPI
# ---------------------------------------------------------------------------
# SWF-компонент components-environment.swf (EnvironmentsSettingsUI) надає:
#   interactiveEvent_overrideIngame  — подія яку Flash шле в Python
#   as_setStaticData / as_setDynamicData — Python шле дані у Flash
#
# Але ще важливіше: цей компонент живе в GUI і коли він відправляє
# interactiveEvent_overrideIngame, WoT сам змінює environment через
# внутрішній API. Тому нам достатньо знайти цей view і викликати
# потрібний метод через DAAPI.
# ---------------------------------------------------------------------------

def _find_environments_settings_view():
    """
    Шукає живий екземпляр EnvironmentsSettingsUI у WoT view менеджері.
    Повертає view або None.
    """
    if not IN_GAME:
        return None
    try:
        # Спосіб 1: через g_appLoader / appFactory
        from gui.app_loader import g_appLoader
        app = g_appLoader.getApp()
        if app is not None:
            view_mgr = getattr(app, 'containerManager', None) or getattr(app, 'viewManager', None)
            if view_mgr is not None:
                for alias in ('EnvironmentsSettingsUI', 'environment_settings',
                              'ENVIRONMENTS_SETTINGS', 'environments_settings'):
                    view = getattr(view_mgr, 'getView', lambda a: None)(alias)
                    if view is not None:
                        LOG.info('_find_environments_settings_view: found via viewManager alias=%s', alias)
                        return view
    except Exception as e:
        LOG.debug('_find_environments_settings_view: app_loader ERR: %s', e)

    try:
        # Спосіб 2: через gui.shared.system_factory
        from gui.shared import g_eventBus
        _ = g_eventBus  # перевіряємо доступність
    except Exception:
        pass

    return None


def trigger_daapi_override_ingame(preset_id, space_name=None):
    """
    Намагається надіслати команду зміни environment через DAAPI EnvironmentsSettingsUI.

    Flash-компонент EnvironmentsSettingsUI має метод interactiveEvent_overrideIngame
    що WoT обробляє і застосовує environment live.

    Структура payload для as_setDynamicData / interactiveEvent_overrideIngame
    (реверс-інжиніринг зі SWF):
      {
        'preset': preset_id,         # 'midnight', 'overcast', etc.
        'guid':   guid_dot_format,   # '00.11.22...' формат з крапками
        'spaceName': space_name,
      }
    """
    if not IN_GAME:
        return False

    try:
        registry = get_environment_registry()
        preset_data = registry.get(preset_id)
        if not preset_data and preset_id != 'standard':
            LOG.warning('trigger_daapi_override_ingame: preset not in registry: %s', preset_id)
            return False

        guid = None
        if preset_data and space_name:
            sd = preset_data.get('spaces', {}).get(space_name)
            if sd:
                guid = _guid_to_dot(sd.get('guid', ''))
        if not guid and preset_data:
            for _, sd in preset_data.get('spaces', {}).items():
                if sd.get('guid'):
                    guid = _guid_to_dot(sd['guid'])
                    break

        view = _find_environments_settings_view()
        if view is not None:
            try:
                # Метод який Flash відправляє до Python — нам потрібен зворотній:
                # Python викликає метод AS3 view'а через DAAPI flashObject
                flash = getattr(view, 'flashObject', None)
                if flash is not None:
                    # Відправляємо override через flashObject (AS3 → Engine)
                    payload = {'preset': preset_id, 'guid': guid or '', 'spaceName': space_name or ''}
                    if hasattr(flash, 'as_setDynamicData'):
                        flash.as_setDynamicData(payload)
                        LOG.info('trigger_daapi: as_setDynamicData sent preset=%s', preset_id)
                        return True
            except Exception as e:
                LOG.warning('trigger_daapi: flashObject ERR: %s', e)

        # Fallback: якщо view не знайдено — спробувати через g_eventBus
        try:
            from gui.shared import g_eventBus
            from gui.shared.events import GameEvent
            # Деякі WoT версії приймають override через eventBus
            event_id = 'WEATHER_OVERRIDE_INGAME'
            g_eventBus.handleEvent(
                GameEvent(event_id, ctx={'preset': preset_id, 'guid': guid or ''}))
            LOG.info('trigger_daapi: g_eventBus.handleEvent %s sent', event_id)
            return True
        except Exception as e:
            LOG.debug('trigger_daapi: g_eventBus ERR: %s', e)

    except Exception:
        LOG.error('trigger_daapi_override_ingame failed\n%s', traceback.format_exc())

    return False


# ---------------------------------------------------------------------------
# Основна функція застосування environment
# ---------------------------------------------------------------------------

def apply_environment_via_packages(space_name, preset_id):
    """
    Записує space.settings та environments.json і намагається застосувати live.

    Порядок спроб live-зміни:
      1. BigWorld.wg_setSpaceEnvironmentId / wg_reloadEnvironment
      2. EnvironmentsSettingsUI DAAPI (interactiveEvent_overrideIngame)
    """
    try:
        LOG.info('apply_env: space=%s preset=%s', space_name, preset_id)
        if not space_name:
            return False

        # Завжди пишемо environments.json (скидаємо або встановлюємо)
        env_json_ok = write_environments_json_for_preset(preset_id, space_name)

        if not preset_id or preset_id == 'standard':
            LOG.info('apply_env: standard preset, environments.json cleared')
            return env_json_ok

        actual_preset_id, resolved = resolve_environment_with_fallback(space_name, preset_id)
        if not resolved:
            return env_json_ok

        env_name    = resolved.get('env_name')
        preset_guid = resolved.get('guid')
        LOG.info('apply_env: resolved preset=%s env_name=%s guid=%s',
                 actual_preset_id, env_name, preset_guid)

        # Записуємо space.settings
        templates = _get_spaces_wg_templates(space_name)
        space_settings_path = find_space_settings_path(space_name)
        settings_content = None
        if space_settings_path:
            settings_content = _patch_space_settings_template(
                templates.get('space_settings'), env_name, preset_guid)
            if settings_content:
                _write_text_file(space_settings_path, settings_content)
            else:
                LOG.warning('apply_env: WG template not found for %s', space_name)

        # --- Live зміна (тільки в бою) ---
        space_id = _get_current_space_id()
        in_battle = False
        if IN_GAME:
            try:
                player = BigWorld.player()
                in_battle = player is not None and getattr(player, 'arena', None) is not None
            except Exception:
                pass

        if in_battle and space_id and preset_guid:
            live_bw = apply_environment_bigworld_api(space_id, preset_guid)
            LOG.info('apply_env: live BigWorld API = %s', live_bw)

            if not live_bw:
                live_daapi = trigger_daapi_override_ingame(actual_preset_id, space_name)
                LOG.info('apply_env: live DAAPI = %s', live_daapi)

        return True

    except Exception:
        LOG.error('apply_environment_via_packages failed\n%s', traceback.format_exc())
        return False


def on_space_entered(space_name):
    global _last_space_name, _current_override_preset, _current_cycle_index
    try:
        LOG.info('on_space_entered: space=%s override=%s', space_name, _current_override_preset)
        if not space_name:
            return False
        _last_space_name = space_name
        if _current_override_preset:
            preset_id = _current_override_preset
        else:
            preset_id = get_preset_for_map(space_name)
            if preset_id and preset_id != 'standard':
                _current_override_preset = preset_id
                _current_cycle_index = PRESET_ORDER.index(preset_id) if preset_id in PRESET_ORDER else 0
        LOG.info('on_space_entered: preset=%s', preset_id or 'standard')
        return apply_environment_via_packages(space_name, preset_id)
    except Exception:
        LOG.error('on_space_entered failed\n%s', traceback.format_exc())
        return False


def cycle_weather_in_battle():
    global _current_cycle_index, _current_override_preset
    try:
        from gui import SystemMessages
    except Exception:
        SystemMessages = None
    try:
        in_battle = False
        try:
            player = BigWorld.player()
            in_battle = player is not None and getattr(player, 'arena', None) is not None
        except Exception:
            pass

        arena_name = _resolve_current_arena_name()
        available  = get_available_cycle_presets(arena_name) if arena_name else list(PRESET_ORDER)
        current    = _current_override_preset or 'standard'
        if current not in available:
            current = 'standard'
        idx          = available.index(current)
        next_preset  = available[(idx + 1) % len(available)]

        _current_cycle_index = PRESET_ORDER.index(next_preset) if next_preset in PRESET_ORDER else 0
        _current_override_preset = None if next_preset == 'standard' else next_preset

        if arena_name:
            apply_environment_via_packages(arena_name, _current_override_preset)

        save_config()

        if SystemMessages is not None:
            try:
                SystemMessages.pushMessage(
                    u'[Weather] %s' % PRESET_LABELS.get(next_preset, next_preset),
                    SystemMessages.SM_TYPE.Information)
            except Exception:
                pass
    except Exception:
        LOG.error('cycle_weather_in_battle failed\n%s', traceback.format_exc())


def _normalize_space_name(name):
    if not name or not isinstance(name, basestring):
        return None
    result = name.strip()
    if '/' in result:
        result = result.rsplit('/', 1)[-1]
    return result or None

def _resolve_current_arena_name():
    try:
        player = BigWorld.player()
        if player is None:
            return _last_space_name
        arena = getattr(player, 'arena', None)
        if arena is not None:
            # Спосіб 1: через arenaType (стандартний)
            arena_type = getattr(arena, 'arenaType', None)
            if arena_type is not None:
                for attr in ('geometryName', 'geometry', 'name'):
                    value = _normalize_space_name(getattr(arena_type, attr, None))
                    if value:
                        return value
            # Спосіб 2: напряму через arena (2.2.1: Klondike + reworked maps)
            for attr in ('geometryName', 'geometry'):
                value = _normalize_space_name(getattr(arena, attr, None))
                if value:
                    LOG.info('_resolve_current_arena_name: arena.%s=%s', attr, value)
                    return value
    except Exception:
        LOG.error('_resolve_current_arena_name failed\n%s', traceback.format_exc())
    return _last_space_name

def get_available_cycle_presets(space_name):
    available = ['standard']
    registry  = get_environment_registry()
    for preset_id in PRESET_ORDER:
        if preset_id == 'standard':
            continue
        if registry.get(preset_id, {}).get('spaces', {}).get(space_name):
            available.append(preset_id)
    return available

def get_current_override_preset():
    return _current_override_preset or 'standard'

def set_override_preset(preset_id):
    global _current_override_preset, _current_cycle_index
    if preset_id not in PRESET_ORDER:
        return
    _current_override_preset = None if preset_id == 'standard' else preset_id
    _current_cycle_index     = PRESET_ORDER.index(preset_id)
    save_config()

def get_preset_labels():
    return dict(PRESET_LABELS)

def get_weather_system_labels():
    return dict(WEATHER_SYSTEM_LABELS)

def get_preset_order():
    return list(PRESET_ORDER)


# ---------------------------------------------------------------------------
# WeatherController
# ---------------------------------------------------------------------------

class WeatherController(object):
    def __init__(self):
        load_config()

    def onSpaceEntered(self, space_name):
        return on_space_entered(space_name)

    def cycleWeatherInBattle(self):
        return cycle_weather_in_battle()

    def getCurrentOverridePreset(self):
        return get_current_override_preset()

    def setOverridePreset(self, preset_id):
        return set_override_preset(preset_id)

    def select_preset_in_battle(self, preset_id):
        """Вибір конкретного пресету в бою (клавіші 1-5 або DAAPI)."""
        if preset_id not in PRESET_ORDER:
            LOG.warning('select_preset_in_battle: unknown preset=%s', preset_id)
            return
        global _current_override_preset, _current_cycle_index
        _current_override_preset = None if preset_id == 'standard' else preset_id
        _current_cycle_index     = PRESET_ORDER.index(preset_id)
        space = _resolve_current_arena_name()
        LOG.info('select_preset_in_battle: preset=%s space=%s', preset_id, space)
        if space:
            apply_environment_via_packages(space, _current_override_preset)
        save_config()
        try:
            from gui import SystemMessages
            SystemMessages.pushMessage(
                u'[Weather] %s' % PRESET_LABELS.get(preset_id, preset_id),
                SystemMessages.SM_TYPE.Information)
        except Exception:
            pass

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

    def get_config(self):
        return get_config()


g_controller = WeatherController()
