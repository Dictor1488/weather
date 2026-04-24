# -*- coding: utf-8 -*-
"""
Weather controller v8.0

Механізм (перевірено через дебаг протанків):
  1. Preset wotmod-и (environments_midnight_*.wotmod і т.д.) мають бути в mods/VERSION/
     Вони містять: res/spaces/КАРТА/environments/GUID/environment.xml + текстури
  2. При виборі пресету — генеруємо бінарний WoT XML файл:
       res_mods/VERSION/spaces/КАРТА/environments/environments.xml
     з guid обраного пресету. Це говорить WoT який environment активний.
  3. Додатково пишемо space.settings з <environment> та <environmentOverride>
     (береться з environments_spaces_wg wotmod як шаблон)
  4. BigWorld.restartGame() — перезапуск щоб WoT перечитав файли

Формат бінарного environments.xml (124 байти, guid завжди 35 символів):
  HEADER (54 байти) + GUID (35 байти) + GUID (35 байти)
  де HEADER містить: magic, назви полів activeEnvironment/environment, offsets
"""

import binascii
import json
import os
import re
import random
import logging
import traceback
import zipfile

try:
    basestring
except NameError:
    basestring = str

try:
    import BigWorld
    import ResMgr
    IN_GAME = True
except ImportError:
    IN_GAME = False

LOG = logging.getLogger('weather_mod')
LOG.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Константи пресетів
# ---------------------------------------------------------------------------

PRESET_ORDER = ['standard', 'midnight', 'overcast', 'sunset', 'midday']

PRESET_LABELS = {
    'standard': u'Стандарт',
    'midnight': u'Ніч',
    'overcast': u'Хмарно',
    'sunset':   u'Захід',
    'midday':   u'Полудень',
}

# Guid-и пресетів (формат з крапками, 35 символів)
PRESET_GUIDS = {
    'midnight': '15755E11.4090266B.594778B6.B233C12C',
    'overcast': '56BA3213.40FFB1DF.125FBCAD.173E8347',
    'sunset':   '6DEE1EBB.44F63FCC.AACF6185.7FBBC34E',
    'midday':   'BF040BCB.4BE1D04F.7D484589.135E881B',
}

# Live API BigWorld Space.setEnvironment(name) приймає не GUID, а <name>
# з самого environment.xml. Це перевірено по логах: getEnvironment() повертає
# u'03_midday', хоча активний GUID у environments.xml — BF040BCB...
PRESET_ENV_NAMES = {
    'midnight': 'Night_01',
    'overcast': '01_Overcast',
    'sunset':   '02_Sunset',
    'midday':   '03_midday',
}

MAX_WEIGHT = 20
DEFAULT_WEIGHT = 20
DEFAULT_EQUAL_WEIGHTS = dict((k, DEFAULT_WEIGHT) for k in PRESET_ORDER)

# Назви файлів wotmod для кожного пресету (regex)
PRESET_WOTMOD_RE = {
    'midnight': re.compile(r'^environments[._]midnight.*\.wotmod$', re.I),
    'overcast': re.compile(r'^environments[._]overcast.*\.wotmod$', re.I),
    'sunset':   re.compile(r'^environments[._]sunset.*\.wotmod$', re.I),
    'midday':   re.compile(r'^environments[._]midday.*\.wotmod$', re.I),
}
SPACES_WG_RE = re.compile(r'^environments[._]spaces_wg.*\.wotmod$', re.I)

# ---------------------------------------------------------------------------
# Дефолтні guid-и карт (читаються з оригінального environments.xml через ResMgr)
# ---------------------------------------------------------------------------

_default_guid_cache = {}  # space_name -> guid (стандартний WoT environment)


def _read_default_guid(space_name):
    """
    Читає стандартний guid environment для карти через ResMgr.
    ResMgr читає з оригінальних pkg файлів (не з res_mods/).
    Кешує результат.
    """
    if space_name in _default_guid_cache:
        return _default_guid_cache[space_name]
    guid = None
    try:
        if IN_GAME:
            section = ResMgr.openSection(
                'spaces/%s/environments/environments.xml' % space_name)
            if section:
                # activeEnvironment або environment
                for key in ('activeEnvironment', 'environment'):
                    val = section.readString(key, '')
                    if val and len(val) == 35:
                        guid = val
                        break
                ResMgr.purge('spaces/%s/environments/environments.xml' % space_name)
    except Exception as e:
        LOG.warning('_read_default_guid %s: %s', space_name, e)
    if guid:
        _default_guid_cache[space_name] = guid
        LOG.info('_read_default_guid: %s -> %s', space_name, guid)
    else:
        LOG.warning('_read_default_guid: no guid for %s', space_name)
    return guid



# ---------------------------------------------------------------------------
# Бінарний WoT XML для environments.xml
# Заголовок незмінний (guid завжди 35 символів у форматі XXXXXXXX.XXXXXXXX.XXXXXXXX.XXXXXXXX)
# ---------------------------------------------------------------------------

_ENVIRONMENTS_XML_HEADER = binascii.unhexlify(
    '454ea162'                          # magic: EN\xa1b
    '00'                                # null
    '616374697665456e7669726f6e6d656e74'  # 'activeEnvironment'
    '00'                                # null
    '656e7669726f6e6d656e74'            # 'environment'
    '00'                                # null
    '0002000000'                        # element count = 2
    '00100000'                          # descriptor 1
    '23000010'                          # descriptor 2
    '01004600'                          # descriptor 3 (0x46 = 70 = 35*2, total data size)
    '0010'                              # descriptor end
)


def make_environments_xml(guid_dot):
    """
    Генерує бінарний WoT XML файл environments.xml для заданого guid.
    guid_dot — рядок формату XXXXXXXX.XXXXXXXX.XXXXXXXX.XXXXXXXX (35 символів)
    """
    assert len(guid_dot) == 35, \
        'GUID має бути 35 символів: XXXXXXXX.XXXXXXXX.XXXXXXXX.XXXXXXXX, отримано: %r' % guid_dot
    b = guid_dot.encode('ascii')
    return _ENVIRONMENTS_XML_HEADER + b + b


# ---------------------------------------------------------------------------
# Шляхи
# ---------------------------------------------------------------------------

def _safe_listdir(path):
    try:
        return os.listdir(path)
    except Exception:
        return []


def _has_game_layout(path):
    try:
        return (os.path.isdir(os.path.join(path, 'mods')) or
                os.path.isdir(os.path.join(path, 'res_mods')))
    except Exception:
        return False


def _resolve_game_root():
    candidates = []
    try:
        candidates.append(os.path.abspath(os.getcwd()))
        candidates.append(os.path.abspath(os.path.join(os.getcwd(), '..')))
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
        pass
    seen = set()
    for c in candidates:
        c = os.path.normpath(c)
        if c in seen:
            continue
        seen.add(c)
        if _has_game_layout(c):
                    return c
    return os.path.abspath(os.getcwd())


def _find_latest_version_dir(root_name):
    game_root = _resolve_game_root()
    root = os.path.join(game_root, root_name)
    if not os.path.isdir(root):
        return None
    version_re = re.compile(r'^\d+\.\d+')
    dirs = [os.path.join(root, n) for n in _safe_listdir(root)
            if os.path.isdir(os.path.join(root, n)) and version_re.match(n)]
    if not dirs:
        return None
    dirs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    LOG.debug('%s version dir: %s', root_name, dirs[0])
    return dirs[0]


# ---------------------------------------------------------------------------
# Пошук wotmod файлів
# ---------------------------------------------------------------------------

def _find_wotmod(pattern_re, search_dir):
    """Шукає wotmod файл за regex в папці і в підпапці weather_packs/."""
    if not search_dir or not os.path.isdir(search_dir):
        return None
    weather_packs = os.path.join(search_dir, 'weather_packs')
    for folder in [weather_packs, search_dir]:
        if not os.path.isdir(folder):
            continue
        for name in _safe_listdir(folder):
            if pattern_re.match(name):
                return os.path.join(folder, name)
    return None


def _get_mods_dir():
    return _find_latest_version_dir('mods')


def _get_resmods_dir():
    return _find_latest_version_dir('res_mods')


def _find_spaces_wg_wotmod():
    mods_dir = _get_mods_dir()
    if not mods_dir:
        return None
    path = _find_wotmod(SPACES_WG_RE, mods_dir)
    if path:
        LOG.debug('spaces_wg wotmod: %s', path)
    else:
        LOG.warning('spaces_wg wotmod not found in %s', mods_dir)
    return path


def _find_preset_wotmod(preset_id):
    mods_dir = _get_mods_dir()
    if not mods_dir or preset_id not in PRESET_WOTMOD_RE:
        return None
    path = _find_wotmod(PRESET_WOTMOD_RE[preset_id], mods_dir)
    if path:
        LOG.debug('preset wotmod %s: %s', preset_id, path)
    else:
        LOG.warning('preset wotmod %s not found in %s', preset_id, mods_dir)
    return path


def get_available_presets():
    """Повертає список пресетів для яких є wotmod файли."""
    available = ['standard']
    mods_dir = _get_mods_dir()
    if not mods_dir:
        return available
    for preset_id, pattern in PRESET_WOTMOD_RE.items():
        if _find_wotmod(pattern, mods_dir):
            available.append(preset_id)
    return available


# ---------------------------------------------------------------------------
# Запис environments.xml в res_mods/
# ---------------------------------------------------------------------------

def write_environments_xml(space_name, preset_id):
    """
    Записує бінарний environments.xml в:
      res_mods/VERSION/spaces/SPACE_NAME/environments/environments.xml

    Це основний механізм — WoT читає цей файл при завантаженні карти
    і визначає який environment активний.

    preset_id='standard' → видаляє файл (WoT використає дефолтний)
    """
    resmods_dir = _get_resmods_dir()
    if not resmods_dir:
        LOG.warning('write_environments_xml: res_mods not found')
        return False

    target = os.path.normpath(
        os.path.join(resmods_dir, 'spaces', space_name, 'environments', 'environments.xml'))

    # standard = видаляємо файл щоб WoT використав дефолтний
    if not preset_id or preset_id == 'standard':
        if os.path.isfile(target):
            try:
                os.remove(target)
                LOG.info('write_environments_xml: removed %s', target)
            except Exception as e:
                LOG.warning('write_environments_xml: remove failed: %s', e)
        return True

    guid = PRESET_GUIDS.get(preset_id)
    if not guid:
        LOG.warning('write_environments_xml: no guid for preset %s', preset_id)
        return False

    try:
        folder = os.path.dirname(target)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        data = make_environments_xml(guid)
        with open(target, 'wb') as f:
            f.write(data)
        LOG.info('write_environments_xml: %s -> %s (%s)', preset_id, target, guid)
        return True
    except Exception:
        LOG.error('write_environments_xml failed\n%s', traceback.format_exc())
        return False


def write_environments_xml_all_maps(preset_id):
    """
    Записує environments.xml для ВСІХ карт які є в preset wotmod.
    Викликати при старті гри / зміні пресету.
    """
    if not preset_id or preset_id == 'standard':
        # Видаляємо всю папку spaces/ з res_mods (скидаємо до стандарту)
        resmods_dir = _get_resmods_dir()
        if resmods_dir:
            spaces_dir = os.path.join(resmods_dir, 'spaces')
            if os.path.isdir(spaces_dir):
                import shutil
                try:
                    shutil.rmtree(spaces_dir)
                    LOG.info('write_all: removed res_mods/spaces/')
                except Exception as e:
                    LOG.warning('write_all: rmtree failed: %s', e)
        return True

    preset_wotmod = _find_preset_wotmod(preset_id)
    if not preset_wotmod:
        LOG.warning('write_all: no wotmod for preset %s', preset_id)
        return False

    guid = PRESET_GUIDS.get(preset_id)
    if not guid:
        LOG.warning('write_all: no guid for preset %s', preset_id)
        return False

    # Отримуємо список карт з wotmod
    spaces = _get_spaces_from_wotmod(preset_wotmod)
    if not spaces:
        LOG.warning('write_all: no spaces in wotmod %s', preset_wotmod)
        return False

    count = 0
    for space_name in spaces:
        if write_environments_xml(space_name, preset_id):
            count += 1

    LOG.info('write_all: preset=%s written %d/%d maps', preset_id, count, len(spaces))
    return count > 0


def _get_spaces_from_wotmod(wotmod_path):
    """Повертає список назв карт (space names) з wotmod файлу."""
    spaces = set()
    try:
        with zipfile.ZipFile(wotmod_path, 'r') as zf:
            for member in zf.namelist():
                # res/spaces/КАРТА/environments/GUID/environment.xml
                m = re.match(r'^res/spaces/([^/]+)/environments/', member)
                if m:
                    spaces.add(m.group(1))
    except Exception:
        LOG.error('_get_spaces_from_wotmod failed\n%s', traceback.format_exc())
    return list(spaces)


# ---------------------------------------------------------------------------
# space.settings патч (додатковий механізм)
# ---------------------------------------------------------------------------

def _read_space_settings_template(space_name):
    """Читає space.settings шаблон з environments_spaces_wg wotmod."""
    wg_path = _find_spaces_wg_wotmod()
    if not wg_path:
        return None
    member = 'res/spaces/%s/space.settings' % space_name
    try:
        with zipfile.ZipFile(wg_path, 'r') as zf:
            return zf.read(member).decode('utf-8', 'ignore')
    except Exception:
        return None


def _patch_space_settings(template, guid_dot):
    """Додає <environment> та <environmentOverride> в space.settings."""
    if not template:
        return None
    nl = '\r\n' if '\r\n' in template else '\n'
    closing = '</space.settings>' if '</space.settings>' in template else '</root>'

    # Видаляємо старі якщо є
    template = re.sub(r'\s*<environment>[^<]*</environment>', '', template)
    template = re.sub(r'\s*<environmentOverride>[^<]*</environmentOverride>', '', template)

    # Вставляємо перед закриваючим тегом
    insert = (
        '  <environment>\t%s\t</environment>%s'
        '  <environmentOverride>\t%s\t</environmentOverride>%s'
    ) % (guid_dot, nl, guid_dot, nl)

    return template.replace(closing, insert + closing)


def write_space_settings(space_name, preset_id):
    """Записує патчений space.settings в res_mods/."""
    resmods_dir = _get_resmods_dir()
    if not resmods_dir:
        return False

    target = os.path.normpath(
        os.path.join(resmods_dir, 'spaces', space_name, 'space.settings'))

    if not preset_id or preset_id == 'standard':
        if os.path.isfile(target):
            try:
                os.remove(target)
            except Exception:
                pass
        return True

    guid = PRESET_GUIDS.get(preset_id)
    if not guid:
        return False

    template = _read_space_settings_template(space_name)
    if not template:
        LOG.warning('write_space_settings: no template for %s', space_name)
        return False

    patched = _patch_space_settings(template, guid)
    if not patched:
        return False

    try:
        folder = os.path.dirname(target)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with open(target, 'wb') as f:
            f.write(patched.encode('utf-8'))
        LOG.info('write_space_settings: %s -> %s', space_name, preset_id)
        return True
    except Exception:
        LOG.error('write_space_settings failed\n%s', traceback.format_exc())
        return False


# ---------------------------------------------------------------------------
# Конфіг
# ---------------------------------------------------------------------------

def _get_config_path():
    try:
        prefs = (BigWorld.wg_getPreferencesFilePath()
                 if IN_GAME and hasattr(BigWorld, 'wg_getPreferencesFilePath')
                 else BigWorld.getPreferencesFilePath() if IN_GAME else None)
        if prefs:
            return os.path.normpath(
                os.path.join(os.path.dirname(prefs), 'mods', 'weather', 'config.json'))
    except Exception:
        pass
    return os.path.normpath(os.path.join(os.getcwd(), 'mods', 'weather', 'config.json'))


CONFIG_PATH = None  # ініціалізується в load_config()

DEFAULT_CFG = {
    'enabled': True,
    'currentPreset': 'standard',
    'generalWeights': dict(DEFAULT_EQUAL_WEIGHTS),
    'mapWeights': {},
    'hotkey': {'enabled': True, 'mods': [], 'key': 'KEY_F12'},
    'iconPosition': {'x': 20, 'y': 120},
}

_cfg = {}
_current_preset = 'standard'


def _normalize_weights(d):
    out = {}
    for k in PRESET_ORDER:
        try:
            out[k] = max(0, min(MAX_WEIGHT, int((d or {}).get(k, 0))))
        except Exception:
            out[k] = 0
    return out


def _effective_weights(d, fallback=None):
    n = _normalize_weights(d)
    if any(v > 0 for v in n.values()):
        return n
    if fallback:
        f = _normalize_weights(fallback)
        if any(v > 0 for v in f.values()):
            return f
    return dict(DEFAULT_EQUAL_WEIGHTS)


def load_config():
    global _cfg, _current_preset, CONFIG_PATH
    CONFIG_PATH = _get_config_path()
    _cfg = json.loads(json.dumps(DEFAULT_CFG))
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                _cfg.update(json.load(f))
    except Exception:
        LOG.exception('load_config failed')

    _cfg['generalWeights'] = _normalize_weights(_cfg.get('generalWeights', {}))
    preset = _cfg.get('currentPreset', 'standard')
    if preset not in PRESET_ORDER:
        preset = 'standard'
    _current_preset = preset

    LOG.info('config loaded: preset=%s', _current_preset)
    save_config()
    return _cfg


def save_config():
    try:
        _cfg['currentPreset'] = _current_preset
        folder = os.path.dirname(CONFIG_PATH)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(_cfg, f, indent=2, sort_keys=True)
    except Exception:
        LOG.exception('save_config failed')


def get_config():
    return _cfg


# ---------------------------------------------------------------------------
# Основна логіка застосування
# ---------------------------------------------------------------------------

_last_space_name = None


def _resolve_space_name_from_avatar(avatar):
    try:
        arena = getattr(avatar, 'arena', None)
        arena_type = getattr(arena, 'arenaType', None) if arena else None
        if arena_type:
            for attr in ('geometryName', 'geometry', 'name'):
                v = getattr(arena_type, attr, None)
                if v and isinstance(v, basestring):
                    name = v.strip().rsplit('/', 1)[-1]
                    if name:
                        return name
        # Fallback: arenaTypeID + g_cache
        arena_type_id = getattr(avatar, 'arenaTypeID', None)
        if arena_type_id:
            from ArenaType import g_cache
            at = g_cache.get(arena_type_id)
            if at:
                for attr in ('geometryName', 'geometry', 'name'):
                    v = getattr(at, attr, None)
                    if v and isinstance(v, basestring):
                        name = v.strip().rsplit('/', 1)[-1]
                        if name:
                            return name
    except Exception:
        pass
    return _last_space_name


def _weighted_choice(weights_dict):
    pool = []
    for preset in PRESET_ORDER:
        w = int(_effective_weights(weights_dict).get(preset, 0))
        pool.extend([preset] * w)
    return random.choice(pool) if pool else 'standard'


def _get_preset_for_map(space_name):
    map_w = _cfg.get('mapWeights', {}).get(space_name)
    if map_w:
        return _weighted_choice(map_w)
    return _weighted_choice(_cfg.get('generalWeights', {}))


def _write_environments_json(space_name, active_preset_id):
    """
    Пише mods/configs/weather/environments.json з усіма guid-ами пресетів.
    WoT читає цей файл і завантажує ВСІ перелічені environments в простір —
    тільки тоді _switchEnvironment може між ними перемикати live.

    active_preset_id — пресет з вагою 100 (буде обраний при завантаженні).
    """
    try:
        game_root = _resolve_game_root()
        path = os.path.normpath(
            os.path.join(game_root, 'mods', 'configs', 'weather', 'environments.json'))

        # Збираємо всі guid-и пресетів для цієї карти
        all_guids = []
        for preset_id in PRESET_ORDER:
            if preset_id == 'standard':
                continue
            guid = PRESET_GUIDS.get(preset_id)
            if guid:
                all_guids.append(guid)

        if not all_guids:
            return False

        # Визначаємо активний guid
        if active_preset_id and active_preset_id != 'standard':
            active_guid = PRESET_GUIDS.get(active_preset_id)
        else:
            active_guid = _read_default_guid(space_name) if space_name else None

        # Завжди додаємо дефолтний guid карти (standard preset)
        default_guid = _read_default_guid(space_name) if space_name else None
        if default_guid and default_guid not in all_guids:
            all_guids.append(default_guid)
            LOG.info('_write_protanki_env_json: added default guid %s', default_guid)
        if active_guid and active_guid not in all_guids:
            all_guids.append(active_guid)

        # Ваги: активний = 100, решта = 11
        # Якщо active_guid=None (standard без відомої карти) — всі по 11,
        # активний environment визначається з environments.xml
        common_weights = {'default': 0}
        for guid in all_guids:
            common_weights[guid] = 100 if (active_guid and guid == active_guid) else 11

        payload = {
            'enabled': True,
            'environments': all_guids,
            'labels': {
                '15755E11.4090266B.594778B6.B233C12C': u'\u041d\u0456\u0447',
                '56BA3213.40FFB1DF.125FBCAD.173E8347': u'\u0425\u043c\u0430\u0440\u043d\u043e',
                '6DEE1EBB.44F63FCC.AACF6185.7FBBC34E': u'\u0417\u0430\u0445\u0456\u0434',
                'BF040BCB.4BE1D04F.7D484589.135E881B': u'\u041f\u043e\u043b\u0443\u0434\u0435\u043d\u044c',
                'default': u'\u0421\u0442\u0430\u043d\u0434\u0430\u0440\u0442',
            },
            'randomizer': {
                'advanced': {},
                'common': common_weights,
            },
            'toogleKeyset': [-1, 88],
        }

        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with open(path, 'w') as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
        LOG.info('_write_environments_json: %s guids=%s active=%s',
                 space_name, all_guids, active_guid)
        return True
    except Exception:
        LOG.error('_write_environments_json failed\n%s', traceback.format_exc())
        return False


def get_presets_for_space(space_name):
    """Повертає список пресетів які мають environment для цієї карти."""
    available = ['standard']  # standard завжди доступний
    for preset_id, pattern in PRESET_WOTMOD_RE.items():
        mods_dir = _get_mods_dir()
        wotmod = _find_wotmod(pattern, mods_dir) if mods_dir else None
        if not wotmod:
            continue
        spaces = _get_spaces_from_wotmod(wotmod)
        if space_name in spaces:
            available.append(preset_id)
    return available



def apply_preset(space_name, preset_id):
    """
    Записує environments.xml, space.settings і environments.json для карти.
    environments.json завантажує ВСІ пресети в простір — для live перемикання.
    """
    LOG.info('apply_preset: space=%s preset=%s', space_name, preset_id)
    ok1 = write_environments_xml(space_name, preset_id)
    ok2 = write_space_settings(space_name, preset_id)

    LOG.info('apply_preset: environments_xml=%s space_settings=%s', ok1, ok2)
    return ok1


def apply_preset_all_maps(preset_id):
    """Записує environments.xml для всіх карт пресету. Для ініціалізації."""
    LOG.info('apply_preset_all_maps: preset=%s', preset_id)
    ok = write_environments_xml_all_maps(preset_id)

    # Також пишемо space.settings для всіх карт
    preset_wotmod = _find_preset_wotmod(preset_id) if preset_id and preset_id != 'standard' else None
    spaces = _get_spaces_from_wotmod(preset_wotmod) if preset_wotmod else []
    for space_name in spaces:
        write_space_settings(space_name, preset_id)

    # environments.json — пишемо один раз (не залежить від карти)
    # використовуємо першу доступну карту для отримання дефолтного guid
    sample_space = spaces[0] if spaces else None
    _write_environments_json(sample_space, preset_id)

    return ok


def on_space_entered(space_name):
    """Викликається при вході в бій."""
    global _last_space_name, _current_preset
    _last_space_name = space_name
    LOG.info('on_space_entered: space=%s current_preset=%s', space_name, _current_preset)

    # Якщо пресет не встановлений — вибираємо за вагами
    if not _current_preset:
        _current_preset = _get_preset_for_map(space_name) or 'standard'
        save_config()

    # Перевіряємо чи поточний пресет підтримує цю карту
    supported = get_presets_for_space(space_name)
    if _current_preset not in supported:
        # Вибираємо перший доступний (крім standard якщо є інші)
        fallback = next((p for p in supported if p != 'standard'), 'standard')
        LOG.info('on_space_entered: preset %s not supported for %s, fallback to %s',
                 _current_preset, space_name, fallback)
        return apply_preset(space_name, fallback)

    return apply_preset(space_name, _current_preset)


def cycle_preset():
    """Перемикає на наступний доступний пресет + рестарт."""
    global _current_preset
    available = get_available_presets()
    if not available:
        return

    current = _current_preset or 'standard'
    if current not in available:
        current = available[0]
    idx = available.index(current)
    next_preset = available[(idx + 1) % len(available)]

    _current_preset = next_preset
    save_config()

    LOG.info('cycle_preset: %s -> %s', current, next_preset)

    apply_preset_all_maps(next_preset)

    # Спочатку пробуємо live switch через збережений LSEnvironmentSwitcher
    live_ok = _try_live_switch(next_preset)

    label = PRESET_LABELS.get(next_preset, next_preset)
    if live_ok:
        msg = u'[Weather] %s' % label
    else:
        _do_restart()
        msg = u'[Weather] %s — перезапуск...' % label

    try:
        from gui import SystemMessages
        SystemMessages.pushMessage(msg, SystemMessages.SM_TYPE.Information)
    except Exception:
        pass


def set_preset(preset_id):
    """Встановлює пресет: спочатку live switch, якщо не вийшло — restart fallback."""
    if preset_id not in PRESET_ORDER:
        return False
    live_ok = set_preset_live(preset_id)
    if not live_ok:
        _do_restart()
    return True



# Глобальна змінна для збереження екземпляра switcher-а
_persistent_switcher = None


def _create_switcher_on_battle_start(space_id):
    """
    Створюємо LSEnvironmentSwitcher при вході в бій і зберігаємо.
    Протанки теж створюють свій switcher один раз на бій.
    """
    global _persistent_switcher
    try:
        import LSArenaPhasesComponent as _ls
        sw_class = getattr(_ls, 'LSEnvironmentSwitcher', None)
        if sw_class is None:
            return False

        # Шукаємо як реально створюється LSEnvironmentSwitcher
        # Дивимось __init__ сигнатуру
        try:
            import inspect
            init_sig = inspect.getargspec(sw_class.__init__)
            LOG.info('_create_switcher: __init__ args=%s', init_sig)
        except Exception:
            pass

        # Спроба через CGF компонентну систему
        try:
            import CGF
            if hasattr(CGF, 'getGame'):
                game = CGF.getGame(space_id)
                if game:
                    LOG.info('_create_switcher: CGF game=%s attrs=%s',
                             type(game).__name__, [a for a in dir(game) if 'nviron' in a.lower() or 'witch' in a.lower()])
                    # Шукаємо через компоненти
                    for attr in dir(game):
                        if attr.startswith('_') or attr in ('__class__',):
                            continue
                        try:
                            val = getattr(game, attr, None)
                            if val and isinstance(val, sw_class):
                                _persistent_switcher = val
                                LOG.info('_create_switcher: FOUND via CGF.game.%s', attr)
                                return True
                        except Exception:
                            pass
        except ImportError:
            LOG.info('_create_switcher: CGF not available')
        except Exception as e:
            LOG.info('_create_switcher: CGF ERR: %s', e)

        # Спроба через ComponentSystem WoT 2.x
        try:
            import gameplay.GamePlay as _gp
            gp_attrs = [a for a in dir(_gp) if 'nviron' in a.lower() or 'witch' in a.lower()]
            LOG.info('_create_switcher: GamePlay environ attrs: %s', gp_attrs)
        except Exception:
            pass

        # Спроба: створити власний екземпляр з правильними параметрами
        try:
            from helpers.CallbackDelayer import CallbackDelayer
            # Спробуємо викликати __init__ правильно
            sw = sw_class(space_id)
            _persistent_switcher = sw
            LOG.info('_create_switcher: created with spaceID=%s', space_id)
            return True
        except Exception as e:
            LOG.info('_create_switcher: creation with spaceID failed: %s', e)

        # Якщо нічого не вийшло - створюємо через __new__
        try:
            from helpers.CallbackDelayer import CallbackDelayer
            sw = sw_class.__new__(sw_class)
            sw._spaceID = space_id
            sw._callbackDelayer = CallbackDelayer()
            # Ініціалізуємо необхідні атрибути
            if hasattr(sw_class, '_switcher'):
                sw._switcher = None
            _persistent_switcher = sw
            LOG.info('_create_switcher: created via __new__ with spaceID=%s', space_id)
            return True
        except Exception as e:
            LOG.info('_create_switcher: __new__ failed: %s', e)

    except Exception as e:
        LOG.info('_create_switcher: ERR: %s', e)
    return False


def _get_current_space():
    """Повертає поточний BigWorld Space для гравця."""
    if not IN_GAME:
        return None
    try:
        player = BigWorld.player()
        if player is None:
            return None
        space_id = getattr(player, 'spaceID', None)
        if space_id is None:
            return None
        try:
            return BigWorld.spaces.get(space_id)
        except Exception:
            return BigWorld.spaces[space_id]
    except Exception as e:
        LOG.info('_get_current_space: ERR: %s', e)
    return None


def _try_live_switch(preset_id):
    """
    Live перемикання environment/skyDome.

    Це саме той API, який використовує клієнтський visual script block
    scripts/client/visual_script_client/arena_blocks.py::SetEnvironment:

        BigWorld.spaces[BigWorld.player().spaceID].setEnvironment(name)

    Важливо: одного запису `space.environment = guid` недостатньо.
    Потрібно прямо викликати C++/BigWorld метод `setEnvironment(name)`.
    """
    space = _get_current_space()
    if space is None:
        LOG.info('_try_live_switch: no current space')
        return False

    try:
        LOG.info('_try_live_switch: preset=%s space=%s env_before=%r',
                 preset_id, type(space).__name__, getattr(space, 'environment', None))
    except Exception:
        pass

    # Повернення до дефолтного environment карти.
    if not preset_id or preset_id == 'standard':
        ok = False
        try:
            space.resetEnvironment()
            ok = True
            LOG.info('_try_live_switch: resetEnvironment() OK')
        except Exception as e:
            LOG.info('_try_live_switch: resetEnvironment ERR: %s', e)
        try:
            space.environment = ''
        except Exception:
            pass
        return ok

    guid_dot = PRESET_GUIDS.get(preset_id)
    env_real_name = PRESET_ENV_NAMES.get(preset_id)
    if not guid_dot or not env_real_name:
        LOG.info('_try_live_switch: no guid/name for preset=%s', preset_id)
        return False

    # Важливо: Space.setEnvironment() в live-режимі приймає <name> з environment.xml,
    # а не GUID директорії. У логах було: setEnvironment(GUID) OK, але
    # getEnvironment() лишався u'03_midday'. Тому перший кандидат — реальна назва.
    # GUID-и лишаємо тільки як fallback для інших клієнтів/збірок.
    guid_dash = guid_dot.replace('.', '-')
    candidates = [env_real_name, guid_dot, guid_dash]

    for env_name in candidates:
        try:
            if hasattr(space, 'setEnvironment'):
                before = None
                try:
                    before = space.getEnvironment() if hasattr(space, 'getEnvironment') else None
                except Exception:
                    pass

                space.setEnvironment(env_name)

                after = None
                try:
                    after = space.getEnvironment() if hasattr(space, 'getEnvironment') else None
                except Exception:
                    pass

                try:
                    space.environment = guid_dot
                except Exception:
                    pass

                LOG.info('_try_live_switch: setEnvironment(%r) OK, getEnvironment: %r -> %r',
                         env_name, before, after)

                # Для реальної назви перевіряємо, що движок справді переключив активний env.
                # Для GUID fallback не блокуємо, бо старі клієнти можуть не мати getEnvironment().
                if env_name == env_real_name:
                    if after == env_real_name or after is None:
                        return True
                    LOG.info('_try_live_switch: real name was not accepted visually, continue fallbacks')
                else:
                    return True
        except Exception as e:
            LOG.info('_try_live_switch: setEnvironment(%r) ERR: %s', env_name, e)

    # Останній fallback — property callback з GeneralSpaceData.
    try:
        space.environment = guid_dot
        if hasattr(space, 'set_environment'):
            space.set_environment(None)
            LOG.info('_try_live_switch: set_environment(None) fallback OK')
            return True
    except Exception as e:
        LOG.info('_try_live_switch: set_environment fallback ERR: %s', e)

    return False


def set_preset_live(preset_id):
    """Встановлює пресет і пробує застосувати його в поточному бою без restartGame()."""
    global _current_preset
    if preset_id not in PRESET_ORDER:
        return False
    _current_preset = preset_id
    save_config()

    # Файли потрібні для наступного завантаження карти / fallback після рестарту.
    apply_preset_all_maps(preset_id)

    # Якщо ми вже в бою — пробуємо перемкнути поточний Space напряму.
    return _try_live_switch(preset_id)


def _do_restart():
    """Перезапускає WoT клієнт щоб він перечитав res_mods/."""
    if not IN_GAME:
        return
    try:
        LOG.info('Restarting client...')
        BigWorld.restartGame()
    except Exception as e:
        LOG.warning('restartGame failed: %s', e)
        try:
            BigWorld.quit()
        except Exception:
            pass


def get_current_preset():
    return _current_preset or 'standard'


def is_enabled():
    return bool(_cfg.get('enabled', True))


def set_enabled(flag):
    _cfg['enabled'] = bool(flag)
    save_config()


def get_general_weights():
    return _effective_weights(_cfg.get('generalWeights', {}))


def set_general_weights(weights):
    _cfg['generalWeights'] = _normalize_weights(weights)
    save_config()


def get_map_weights(map_name):
    w = _cfg.get('mapWeights', {}).get(map_name)
    return _effective_weights(w, _cfg.get('generalWeights', {}))


def set_map_weights(map_name, weights):
    _cfg.setdefault('mapWeights', {})[map_name] = _normalize_weights(weights)
    save_config()


def get_preset_labels():
    return dict(PRESET_LABELS)


def get_preset_order():
    return list(PRESET_ORDER)


def get_hotkey():
    hk = _cfg.get('hotkey', {})
    return {
        'enabled': bool(hk.get('enabled', True)),
        'mods':    list(hk.get('mods', [])),
        'key':     hk.get('key', 'KEY_F12'),
    }


def set_hotkey(enabled, mods, key):
    _cfg['hotkey'] = {'enabled': bool(enabled), 'mods': list(mods or []), 'key': key}
    save_config()


def get_icon_position():
    pos = _cfg.get('iconPosition', {})
    return int(pos.get('x', 20)), int(pos.get('y', 120))


def set_icon_position(x, y):
    _cfg['iconPosition'] = {'x': int(x), 'y': int(y)}
    save_config()


# ---------------------------------------------------------------------------
# WeatherController — публічний API
# ---------------------------------------------------------------------------

class WeatherController(object):
    def __init__(self):
        load_config()
        # При старті — переконуємось що файли на місці
        if IN_GAME:
            try:
                apply_preset_all_maps(_current_preset)
            except Exception:
                LOG.exception('init apply_preset_all_maps failed')

    def onSpaceEntered(self, space_name):
        return on_space_entered(space_name)

    def cyclePreset(self):
        return cycle_preset()

    def setPreset(self, preset_id):
        return set_preset(preset_id)

    def setPresetLive(self, preset_id):
        return set_preset_live(preset_id)

    def getCurrentPreset(self):
        return get_current_preset()

    def getAvailablePresets(self):
        return get_available_presets()

    def isEnabled(self):
        return is_enabled()

    def setEnabled(self, flag):
        return set_enabled(flag)

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

    def getIconPosition(self):
        return get_icon_position()

    def setIconPosition(self, x, y):
        return set_icon_position(x, y)

    def getPresetLabels(self):
        return get_preset_labels()

    def getPresetOrder(self):
        return get_preset_order()

    def getPresetForMap(self, map_name):
        return _get_preset_for_map(map_name)

    def getConfig(self):
        return get_config()

    def on_close_requested(self):
        """Викликається коли Flash вікно закривається."""
        save_config()

    def on_hotkey_changed(self, codes, hotkey_str):
        """Викликається коли гравець змінює хоткей у Flash UI."""
        try:
            key = hotkey_str.split('+')[-1] if hotkey_str else 'KEY_F12'
            mods = hotkey_str.split('+')[:-1] if hotkey_str else []
            set_hotkey(True, mods, key)
            LOG.info('hotkey changed: %s', hotkey_str)
        except Exception:
            pass

    # Зворотна сумісність з v7
    def setOverridePreset(self, preset_id):
        global _current_preset
        if preset_id in PRESET_ORDER:
            _current_preset = preset_id
            save_config()

    def setOverrideAndApply(self, preset_id):
        return set_preset(preset_id)

    def getCurrentOverridePreset(self):
        return get_current_preset()

    def cycleWeatherInBattle(self):
        return cycle_preset()

    def getAllGeneralForUI(self):
        weights = get_general_weights()
        return [{'id': p, 'label': PRESET_LABELS[p], 'weight': int(weights.get(p, DEFAULT_WEIGHT))}
                for p in PRESET_ORDER]

    def getAllForMapUI(self, map_name):
        weights = get_map_weights(map_name)
        return [{'id': p, 'label': PRESET_LABELS[p], 'weight': int(weights.get(p, DEFAULT_WEIGHT))}
                for p in PRESET_ORDER]


g_controller = WeatherController()
