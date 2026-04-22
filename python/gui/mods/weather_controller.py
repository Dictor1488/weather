# -*- coding: utf-8 -*-
"""
Weather controller v7.0

Зміни відносно v6.0:
- CORE FIX: res_mods/spaces/ не читається движком — видалено як основний метод
- CORE FIX: прибрано мертвий код (wg_setHourOfDay з неправильними аргументами,
            addSpaceGeometryMapping для server space, DAAPI Flash view в бою)
- feat: діагностика ArenaType.g_cache для пошуку правильного live API
- feat: діагностика Weather модуля (вбудований WoT environment switcher)
- info: основний метод застосування — патч wotmod (робиться окремо при збірці)
        live API буде підключено після знаходження правильного методу через лог
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
    "midday":   re.compile(r"^environments[._]midday_.*\.wotmod$",   re.I),
    "midnight": re.compile(r"^environments[._]midnight_.*\.wotmod$", re.I),
    "overcast": re.compile(r"^environments[._]overcast_.*\.wotmod$", re.I),
    "sunset":   re.compile(r"^environments[._]sunset_.*\.wotmod$",   re.I),
}
SPACES_WG_PACKAGE_RE = re.compile(r"^environments[._]spaces_wg_.*\.wotmod$", re.I)

ENV_XML_RE = re.compile(
    r"^res/spaces/([^/]+)/environments/([A-Fa-f0-9\-]+)/environment\.xml$",
    re.I
)
ENV_NAME_RE_FULL = re.compile('<name>\\t([^\\t<]+)\\t</name>', re.I)
ENV_NAME_RE_OLD  = re.compile('<name>\\s*([^<]+?)\\s*</name>', re.I | re.S)
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
        for m in ENV_NAME_RE_FULL.finditer(xml_text):
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
            if not lower.endswith('.wotmod') or not (lower.startswith('environments.') or lower.startswith('environments_')):
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
# space.settings патч (запасний — для res_mods)
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
            try:
                archive.close()
            except Exception:
                pass
    except Exception:
        LOG.error('Failed to open spaces_wg package\n%s', traceback.format_exc())
    return result

def _patch_space_settings_template(template_text, env_name, preset_guid):
    if not template_text:
        return None
    text = template_text
    nl = u'\r\n' if u'\r\n' in text else u'\n'
    closing_tag = u'</space.settings>' if u'</space.settings>' in text else u'</root>'
    if ROOT_ENV_RE.search(text):
        text = ROOT_ENV_RE.sub(r'\1%s\3' % env_name, text, count=1)
    else:
        text = text.replace(closing_tag,
                            u'  <environment>%s</environment>%s%s' % (env_name, nl, closing_tag), 1)
    if preset_guid:
        if ROOT_ENV_OVERRIDE_RE.search(text):
            text = ROOT_ENV_OVERRIDE_RE.sub(r'\1%s\3' % preset_guid, text, count=1)
        else:
            text = text.replace(closing_tag,
                                u'  <environmentOverride>%s</environmentOverride>%s%s' % (preset_guid, nl, closing_tag), 1)
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
    """
    Повертає список шляхів куди писати environments.json.
    Протанки кладуть в configs/protanki/ - це і є правильний шлях.
    Також пишемо в scripts/client/mods/ як запасний варіант.
    """
    try:
        game_root = _resolve_game_root()
        version_dir = _find_latest_version_dir('res_mods')
        paths = []
        # Основний шлях - configs/protanki/ (де WoT шукає environments.json)
        if game_root:
            version_name = os.path.basename(_find_latest_version_dir('mods') or '')
            configs_path = os.path.normpath(
                os.path.join(game_root, 'mods', version_name, 'configs', 'protanki', 'environments.json'))
            paths.append(configs_path)
        # Запасний - scripts/client/mods/
        if version_dir:
            paths.append(os.path.normpath(
                os.path.join(version_dir, 'scripts', 'client', 'mods', 'environments.json')))
        return paths[0] if paths else None
    except Exception:
        LOG.error('_find_environments_json_path failed\n%s', traceback.format_exc())
        return None


def _get_all_environments_json_paths():
    """Повертає всі шляхи для запису environments.json."""
    try:
        game_root = _resolve_game_root()
        version_dir = _find_latest_version_dir('res_mods')
        mods_dir = _find_latest_version_dir('mods')
        paths = []
        if game_root and mods_dir:
            version_name = os.path.basename(mods_dir)
            paths.append(os.path.normpath(
                os.path.join(game_root, 'mods', version_name, 'configs', 'protanki', 'environments.json')))
        if version_dir:
            paths.append(os.path.normpath(
                os.path.join(version_dir, 'scripts', 'client', 'mods', 'environments.json')))
        return paths
    except Exception:
        return []

def _guid_to_dot(guid):
    return guid.replace('-', '.')

def write_environments_json_for_preset(preset_id, space_name=None):
    """
    Пише environments.json з УСІМА guid-ами всіх пресетів.
    WoT читає цей файл і завантажує всі перелічені environment-и в простір.
    Після цього _switchEnvironment може перемикати між ними live.

    randomizer визначає який пресет обрати при вході (вага 100 = обраний).
    """
    try:
        env_json_path = _find_environments_json_path()
        if not env_json_path:
            return False

        registry = get_environment_registry()

        # Збираємо всі guid-и для поточної карти (або глобальні якщо карта невідома)
        all_guids = []
        labels = {}

        for pid in PRESET_ORDER:
            if pid == 'standard':
                continue
            preset_data = registry.get(pid)
            if not preset_data:
                continue
            # Беремо guid для конкретної карти якщо є, інакше перший доступний
            guid = None
            if space_name:
                sd = preset_data.get('spaces', {}).get(space_name)
                if sd:
                    guid = _guid_to_dot(sd.get('guid', ''))
            if not guid:
                for _, sd in preset_data.get('spaces', {}).items():
                    g = sd.get('guid')
                    if g:
                        guid = _guid_to_dot(g)
                        break
            if guid:
                all_guids.append(guid)
                labels[guid] = PRESET_LABELS.get(pid, pid)

        if not all_guids:
            LOG.warning('write_environments_json: no guids found')
            return False

        # Визначаємо ваги — обраний пресет = 100, інші = 0
        # (randomizer вибирає environment при завантаженні карти)
        common_weights = {'default': 0}
        selected_guid = None

        if preset_id and preset_id != 'standard':
            preset_data = registry.get(preset_id)
            if preset_data:
                if space_name:
                    sd = preset_data.get('spaces', {}).get(space_name)
                    if sd:
                        selected_guid = _guid_to_dot(sd.get('guid', ''))
                if not selected_guid:
                    for _, sd in preset_data.get('spaces', {}).items():
                        g = sd.get('guid')
                        if g:
                            selected_guid = _guid_to_dot(g)
                            break

        for guid in all_guids:
            common_weights[guid] = 100 if guid == selected_guid else 0

        payload = {
            'enabled':    True,
            'environments': all_guids,
            'labels':     labels,
            'randomizer': {'advanced': {}, 'common': common_weights},
            'toogleKeyset': [-1, 88],
        }

        # Пишемо в всі можливі шляхи
        written = False
        for path in _get_all_environments_json_paths():
            try:
                folder = os.path.dirname(path)
                if not os.path.isdir(folder):
                    os.makedirs(folder)
                with open(path, 'w') as f:
                    json.dump(payload, f, indent=4, ensure_ascii=False)
                LOG.info('write_environments_json: written to %s', path)
                written = True
            except Exception as e:
                LOG.warning('write_environments_json: failed to write %s: %s', path, e)
        LOG.info('write_environments_json: preset=%s guids=%s selected=%s',
                 preset_id, all_guids, selected_guid)
        return written
    except Exception:
        LOG.error('write_environments_json failed\n%s', traceback.format_exc())
        return False


def _write_text_file(target_path, content):
    try:
        folder = os.path.dirname(target_path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        if isinstance(content, bytes):
            raw = content
        else:
            raw = content.encode('utf-8')
        with open(target_path, 'wb') as f:
            f.write(raw)
        return True
    except Exception:
        LOG.error('write %s failed\n%s', target_path, traceback.format_exc())
        return False


# ---------------------------------------------------------------------------
# Діагностика ArenaType і Weather — для пошуку live API
# ---------------------------------------------------------------------------

def _find_env_settings_view():
    """Шукає Flash view EnvironmentsSettingsUI через app container."""
    try:
        from gui.app_loader import g_appLoader
        app = g_appLoader.getApp()
        if app is None:
            return None
        for mgr_name in ('containerManager', 'viewsManager'):
            mgr = getattr(app, mgr_name, None)
            if mgr is None:
                continue
            for alias in ('EnvironmentsSettingsUI', 'environmentsSettings',
                          'protanki-components-environment', 'EnvironmentsBackground'):
                try:
                    view = (mgr.getViewByAlias(alias)
                            if hasattr(mgr, 'getViewByAlias') else None)
                    if view is not None:
                        return view
                except Exception:
                    pass
    except Exception:
        pass
    return None


def _push_environments_to_flash(all_guids, selected_guid, space_name):
    """
    Передає список environment guid-ів у Flash компонент EnvironmentsSettingsUI
    через as_setStaticData або as_setDynamicData.

    Flash потім передає їх движку для завантаження в поточний простір.
    """
    if not IN_GAME:
        return False

    try:
        registry = get_environment_registry()

        # Будуємо StaticVO — список пресетів для відображення і завантаження
        content_tabs = []
        for pid in PRESET_ORDER:
            if pid == 'standard':
                continue
            preset_data = registry.get(pid)
            if not preset_data:
                continue
            guid = None
            if space_name:
                sd = preset_data.get('spaces', {}).get(space_name)
                if sd:
                    guid = _guid_to_dot(sd.get('guid', ''))
            if not guid:
                for _, sd in preset_data.get('spaces', {}).items():
                    g = sd.get('guid')
                    if g:
                        guid = _guid_to_dot(g)
                        break
            if not guid:
                continue
            content_tabs.append({
                'envName':        PRESET_LABELS.get(pid, pid),
                'formattedValue': guid,
                'envImage':       'res/gui/maps/icons/pro.environment/%s.png' % guid,
                'selected':       guid == selected_guid,
            })

        static_data = {
            'titleLabel':  u'Weather',
            'buttonClose': u'X',
            'buttonApply': u'Apply',
            'buttonBack':  u'Back',
            'contentTabs': content_tabs,
            'environments': all_guids,
            'selected':     selected_guid,
            'spaceName':    space_name or '',
        }

        # Спроба 1: через Flash view as_setStaticData / as_setDynamicData
        view = _find_env_settings_view()
        if view is not None:
            flash = getattr(view, 'flashObject', None)
            if flash is not None:
                for method in ('as_setStaticData', 'as_setDynamicData'):
                    fn = getattr(flash, method, None)
                    if fn:
                        try:
                            fn(static_data)
                            LOG.info('_push_to_flash: %s OK', method)
                            return True
                        except Exception as e:
                            LOG.info('_push_to_flash: %s ERR: %s', method, str(e)[:100])

        # Спроба 2: через DAAPI напряму
        try:
            from gui.Scaleform.daapi.view.battle import EnvironmentsSettingsUI as _env_ui
            inst = getattr(_env_ui, 'g_instance', None) or getattr(_env_ui, 'instance', None)
            if inst:
                for method in ('as_setStaticData', 'as_setDynamicData', 'setStaticData'):
                    fn = getattr(inst, method, None)
                    if fn:
                        try:
                            fn(static_data)
                            LOG.info('_push_to_flash: DAAPI %s OK', method)
                            return True
                        except Exception as e:
                            LOG.info('_push_to_flash: DAAPI %s ERR: %s', method, str(e)[:100])
        except ImportError:
            pass

        # Спроба 3: шукаємо в sys.modules
        try:
            import sys
            for mod_name, mod in list(sys.modules.items()):
                if 'environment' not in mod_name.lower():
                    continue
                if mod is None:
                    continue
                for attr in ('g_instance', 'instance', 'g_environmentSettings'):
                    inst = getattr(mod, attr, None)
                    if inst is None:
                        continue
                    for method in ('as_setStaticData', 'as_setDynamicData'):
                        fn = getattr(inst, method, None)
                        if fn:
                            try:
                                fn(static_data)
                                LOG.info('_push_to_flash: %s.%s.%s OK', mod_name, attr, method)
                                return True
                            except Exception as e:
                                LOG.info('_push_to_flash: %s.%s.%s ERR: %s',
                                         mod_name, attr, method, str(e)[:80])
        except Exception as e:
            LOG.info('_push_to_flash: sys.modules scan ERR: %s', e)

        LOG.info('_push_to_flash: no Flash view found')
        return False

    except Exception:
        LOG.error('_push_environments_to_flash failed\n%s', traceback.format_exc())
        return False


def _try_live_apply(space_name, preset_id, env_name, preset_guid):
    """
    Live-застосування environment:
    1. _push_environments_to_flash — передає всі guid-и у Flash → движок завантажує їх
    2. _switchEnvironment(guid) — перемикає на потрібний environment
    """
    if not IN_GAME:
        return False

    guid_dot = _guid_to_dot(preset_guid) if preset_guid else None
    if not guid_dot:
        return False

    space_id = None
    try:
        player = BigWorld.player()
        if player:
            space_id = getattr(player, 'spaceID', None)
        if not space_id and hasattr(BigWorld, 'spaceID'):
            space_id = BigWorld.spaceID()
    except Exception as e:
        LOG.warning('live_apply: spaceID ERR: %s', e)

    if not space_id:
        LOG.warning('live_apply: no spaceID')
        return False

    # Збираємо всі guid-и для Flash
    registry = get_environment_registry()
    all_guids = []
    for pid in PRESET_ORDER:
        if pid == 'standard':
            continue
        preset_data = registry.get(pid)
        if not preset_data:
            continue
        g = None
        if space_name:
            sd = preset_data.get('spaces', {}).get(space_name)
            if sd:
                g = _guid_to_dot(sd.get('guid', ''))
        if not g:
            for _, sd in preset_data.get('spaces', {}).items():
                raw = sd.get('guid')
                if raw:
                    g = _guid_to_dot(raw)
                    break
        if g:
            all_guids.append(g)

    # Крок 1: передаємо всі guid-и у Flash (щоб завантажити в простір)
    flash_ok = _push_environments_to_flash(all_guids, guid_dot, space_name)
    LOG.info('live_apply: push_to_flash=%s', flash_ok)

    # Крок 2: перемикаємо через LSEnvironmentSwitcher
    try:
        import LSArenaPhasesComponent as _ls
        sw_class = getattr(_ls, 'LSEnvironmentSwitcher', None)
        if sw_class is None:
            return False

        inst = sw_class.__new__(sw_class)
        inst._spaceID = space_id
        inst._callbackDelayer = None
        inst._switchEnvironment(guid_dot)
        LOG.info('live_apply: _switchEnvironment(%s) OK', guid_dot)

        # Тригер оновлення рендеру
        try:
            fn_tod = getattr(BigWorld, 'spaceTimeOfDay', None)
            if fn_tod:
                current_time = fn_tod(space_id, '')
                fn_tod(space_id, current_time)
                LOG.info('live_apply: spaceTimeOfDay refresh OK')
        except Exception as e:
            LOG.info('live_apply: spaceTimeOfDay ERR: %s', str(e)[:80])

        return True

    except Exception:
        LOG.warning('live_apply: ERR: %s', traceback.format_exc())
        return False


# ---------------------------------------------------------------------------
# Основна функція застосування environment
# ---------------------------------------------------------------------------

def apply_environment_via_packages(space_name, preset_id):
    """
    Застосовує пресет для вказаної карти.

    При заході в бій:
      - пише environments.json (для randomizer системи WoT)
      - пише space.settings в res_mods (запасний варіант)
      - основне застосування відбувається через патч wotmod при збірці пресету

    В бою (F12):
      - намагається live-застосування через LSEnvironmentSwitcher / ArenaType
      - логує діагностику для знаходження правильного API
    """
    try:
        LOG.info('apply_env: space=%s preset=%s', space_name, preset_id)
        if not space_name:
            return False

        # Завжди пишемо environments.json
        write_environments_json_for_preset(preset_id, space_name)

        if not preset_id or preset_id == 'standard':
            LOG.info('apply_env: standard preset — environments.json cleared')
            return True

        actual_preset_id, resolved = resolve_environment_with_fallback(space_name, preset_id)
        if not resolved:
            LOG.warning('apply_env: no resolved environment for space=%s preset=%s',
                        space_name, preset_id)
            return False

        env_name    = resolved.get('env_name')
        preset_guid = resolved.get('guid')
        LOG.info('apply_env: resolved preset=%s env_name=%s guid=%s',
                 actual_preset_id, env_name, preset_guid)

        # Пишемо space.settings в res_mods (запасний)
        templates = _get_spaces_wg_templates(space_name)
        space_settings_path = find_space_settings_path(space_name)
        if space_settings_path and templates.get('space_settings'):
            settings_content = _patch_space_settings_template(
                templates.get('space_settings'), env_name, preset_guid)
            if settings_content:
                ok = _write_text_file(space_settings_path, settings_content)
                LOG.info('apply_env: res_mods space.settings write=%s path=%s',
                         ok, space_settings_path)

        # Live-зміна (тільки якщо реально в бою)
        in_battle = False
        if IN_GAME:
            try:
                player = BigWorld.player()
                in_battle = player is not None and getattr(player, 'arena', None) is not None
            except Exception:
                pass

        if in_battle:
            live = _try_live_apply(space_name, actual_preset_id, env_name, preset_guid)
            LOG.info('apply_env: live apply = %s', live)
            if not live:
                try:
                    from gui import SystemMessages
                    SystemMessages.pushMessage(
                        u'[Weather] %s — застосується при наступному заході в бій' %
                        PRESET_LABELS.get(preset_id, preset_id),
                        SystemMessages.SM_TYPE.Information)
                except Exception:
                    pass

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
            if not preset_id or preset_id == 'standard':
                non_std = [p for p in PRESET_ORDER if p != 'standard']
                preset_id = random.choice(non_std)
                LOG.info('on_space_entered: weights gave standard, forced random=%s', preset_id)
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
            current = available[0] if available else 'standard'
        idx         = available.index(current) if current in available else 0
        next_preset = available[(idx + 1) % len(available)]

        _current_cycle_index = PRESET_ORDER.index(next_preset) if next_preset in PRESET_ORDER else 0
        _current_override_preset = None if next_preset == 'standard' else next_preset

        if arena_name:
            apply_environment_via_packages(arena_name, _current_override_preset)

        save_config()

        try:
            from gui import SystemMessages
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
            arena_type = getattr(arena, 'arenaType', None)
            if arena_type is not None:
                for attr in ('geometryName', 'geometry', 'name'):
                    value = _normalize_space_name(getattr(arena_type, attr, None))
                    if value:
                        return value
            for attr in ('geometryName', 'geometry'):
                value = _normalize_space_name(getattr(arena, attr, None))
                if value:
                    return value
    except Exception:
        LOG.error('_resolve_current_arena_name failed\n%s', traceback.format_exc())
    return _last_space_name

def get_available_cycle_presets(space_name):
    available = []
    registry  = get_environment_registry()
    for preset_id in PRESET_ORDER:
        if preset_id == 'standard':
            continue
        if registry.get(preset_id, {}).get('spaces', {}).get(space_name):
            available.append(preset_id)
    if not available:
        available = [p for p in PRESET_ORDER if p != 'standard']
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

def set_override_and_apply(preset_id):
    """Зберігає пресет і одразу застосовує до поточної карти."""
    global _current_override_preset, _current_cycle_index
    if preset_id not in PRESET_ORDER:
        LOG.warning('set_override_and_apply: unknown preset=%s', preset_id)
        return False
    _current_override_preset = None if preset_id == 'standard' else preset_id
    _current_cycle_index     = PRESET_ORDER.index(preset_id)
    save_config()
    space = _resolve_current_arena_name()
    if space:
        apply_environment_via_packages(space, _current_override_preset)
    return True

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

    def setOverrideAndApply(self, preset_id):
        return set_override_and_apply(preset_id)

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
