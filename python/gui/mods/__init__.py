# -*- coding: utf-8 -*-
"""
Точка входу мода.
SAFE rollback version:
- без ранніх GUI hooks
- тільки Avatar.PlayerAvatar.onEnterWorld
- hotkey + Mod Settings залишені
"""

try:
    import BigWorld
    import Keys
    from gui import InputHandler
    IN_GAME = True
except ImportError:
    IN_GAME = False

from weather_controller import g_controller


_BATTLE_SPACE_HOOKS = []  # list of (cls, attr_name, original_func)
_KEY_HOOK_INSTALLED = False
_INIT_DONE = False

_hotkey_codes = []


ALL_MAPS = [
    ('',                       u'— Оберіть карту —'),
    ('01_karelia',             u'Карелія'),
    ('02_malinovka',           u'Малинівка'),
    ('03_campania_big',        u'Кампанія'),
    ('04_himmelsdorf',         u'Хіммельсдорф'),
    ('05_prohorovka',          u'Прохорівка'),
    ('06_ensk',                u'Енськ'),
    ('07_lakeville',           u'Лейквіль'),
    ('08_ruinberg',            u'Руїнберг'),
    ('10_hills',               u'Рудники'),
    ('11_murovanka',           u'Мурованка'),
    ('13_erlenberg',           u'Ерленберг'),
    ('14_siegfried_line',      u'Лінія Зігфріда'),
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
    ('217_er_alaska',          u'Устрична затока'),
    ('222_er_clime',           u'Вайдпарк'),
]

MAP_IDS = [m[0] for m in ALL_MAPS]
MAP_LABELS = [m[1] for m in ALL_MAPS]


def _log():
    import logging
    return logging.getLogger('weather_mod')


def _normalize_space_name(raw):
    if not raw:
        return None

    try:
        name = str(raw).strip()
    except Exception:
        return None

    if not name:
        return None

    if '/' in name:
        name = name.rsplit('/', 1)[-1]

    if '\\' in name:
        name = name.rsplit('\\', 1)[-1]

    if name in MAP_IDS:
        return name

    for map_id in MAP_IDS:
        if map_id and map_id in name:
            return map_id

    return name


def _load_hotkey_codes():
    global _hotkey_codes
    if not IN_GAME:
        _hotkey_codes = []
        return
    try:
        hk = g_controller.getHotkey()
        if not hk.get('enabled', True):
            _hotkey_codes = []
            return
        codes = []
        for mod_name in hk.get('mods', []):
            code = getattr(Keys, mod_name, None)
            if code is not None:
                codes.append(code)
        key_name = hk.get('key', 'KEY_F12')
        key_code = getattr(Keys, key_name, None)
        if key_code is not None:
            codes.append(key_code)
        _hotkey_codes = codes
    except Exception:
        _log().exception('_load_hotkey_codes failed')
        _hotkey_codes = []


# -----------------------------------------------------------------------------
# FALLBACK HOOK: Avatar.PlayerAvatar.onEnterWorld
# -----------------------------------------------------------------------------
def _get_space_name_from_avatar(avatar):
    try:
        arena = getattr(avatar, 'arena', None)

        geometry_name = getattr(arena, 'geometryName', None) if arena else None
        if geometry_name:
            return _normalize_space_name(geometry_name)

        arena_type = getattr(arena, 'arenaType', None) if arena else None
        if not arena_type:
            return None

        for attr in ('geometryName', 'geometry', 'name'):
            v = getattr(arena_type, attr, None)
            if v:
                return _normalize_space_name(v)
    except Exception:
        _log().exception('_get_space_name_from_avatar failed')
    return None


def _install_battle_space_hook():
    if not IN_GAME or _BATTLE_SPACE_HOOKS:
        return

    log = _log()

    try:
        import Avatar

        if not hasattr(Avatar, 'PlayerAvatar'):
            log.warning('Avatar.PlayerAvatar not found')
            return

        cls = Avatar.PlayerAvatar

        if not hasattr(cls, 'onEnterWorld'):
            log.warning('PlayerAvatar.onEnterWorld not found')
            return

        original = cls.onEnterWorld

        def make_wrapper(orig):
            def wrapped(self, *args, **kwargs):
                try:
                    space_name = _get_space_name_from_avatar(self)
                    if space_name:
                        log.info('onEnterWorld hook: space=%s', space_name)
                        g_controller.onSpaceEntered(space_name)
                except Exception:
                    log.exception('onEnterWorld hook failed')
                return orig(self, *args, **kwargs)
            return wrapped

        cls.onEnterWorld = make_wrapper(original)
        _BATTLE_SPACE_HOOKS.append((cls, 'onEnterWorld', original))
        log.info('Installed hook: Avatar.PlayerAvatar.onEnterWorld')

    except Exception:
        log.exception('Failed to install battle space hook')


def _remove_battle_space_hook():
    while _BATTLE_SPACE_HOOKS:
        cls, attr, original = _BATTLE_SPACE_HOOKS.pop()
        try:
            setattr(cls, attr, original)
        except Exception:
            _log().exception('Failed to remove battle space hook')


# -----------------------------------------------------------------------------
# KEY HOOK
# -----------------------------------------------------------------------------
def _on_key_event(event):
    if not IN_GAME:
        return
    if not hasattr(event, 'isKeyDown') or not event.isKeyDown():
        return

    if not _hotkey_codes:
        if event.key == Keys.KEY_F12 and BigWorld.isKeyDown(Keys.KEY_LALT):
            g_controller.cycleWeatherInBattle()
        return

    trigger_key = _hotkey_codes[-1]
    modifiers = _hotkey_codes[:-1]
    if event.key != trigger_key:
        return
    for mod in modifiers:
        if not BigWorld.isKeyDown(mod):
            return
    g_controller.cycleWeatherInBattle()


def _install_key_hook():
    global _KEY_HOOK_INSTALLED
    if not IN_GAME or _KEY_HOOK_INSTALLED:
        return
    try:
        if getattr(InputHandler, 'g_instance', None) is not None:
            InputHandler.g_instance.onKeyDown += _on_key_event
            _KEY_HOOK_INSTALLED = True
            _log().info('Key hook installed')
    except Exception:
        _log().exception('Failed to install key hook')


def _remove_key_hook():
    global _KEY_HOOK_INSTALLED
    if not IN_GAME or not _KEY_HOOK_INSTALLED:
        return
    try:
        if getattr(InputHandler, 'g_instance', None) is not None:
            InputHandler.g_instance.onKeyDown -= _on_key_event
    except Exception:
        pass
    _KEY_HOOK_INSTALLED = False


def open_weather_window():
    try:
        from gui import SystemMessages
        SystemMessages.pushMessage(
            u'Окреме вікно поки не підключене. Користуйся Mod Settings.',
            SystemMessages.SM_TYPE.Information
        )
    except Exception:
        pass


# -----------------------------------------------------------------------------
# SETTINGS CALLBACK
# -----------------------------------------------------------------------------
def _on_settings_changed(linkage, newSettings):
    log = _log()
    log.debug('settings changed: %s', newSettings)

    preset_order = ['standard', 'midnight', 'overcast', 'sunset', 'midday']

    current_general = g_controller.getGeneralWeights()
    changed_general = False
    for pid in preset_order:
        key = 'global_' + pid
        if key in newSettings:
            current_general[pid] = int(newSettings[key])
            changed_general = True
    if changed_general:
        g_controller.setGeneralWeights(current_general)

    map_idx = newSettings.get('active_map', 0)
    try:
        active_map = MAP_IDS[int(map_idx)]
    except (IndexError, TypeError, ValueError):
        active_map = ''

    if active_map:
        current_map = g_controller.getMapWeights(active_map)
        changed_map = False
        for pid in preset_order:
            key = 'map_' + pid
            if key in newSettings:
                current_map[pid] = int(newSettings[key])
                changed_map = True
        if changed_map:
            g_controller.setMapWeights(active_map, current_map)

    if 'hotkey' in newSettings:
        raw = newSettings['hotkey']
        if isinstance(raw, (list, tuple)):
            _update_hotkey_from_codes([int(c) for c in raw])


def _update_hotkey_from_codes(int_codes):
    global _hotkey_codes
    _hotkey_codes = int_codes

    if not IN_GAME:
        return
    try:
        import Keys as K
        modifier_map = {
            K.KEY_LALT: 'KEY_LALT', K.KEY_RALT: 'KEY_RALT',
            K.KEY_LCONTROL: 'KEY_LCONTROL', K.KEY_RCONTROL: 'KEY_RCONTROL',
            K.KEY_LSHIFT: 'KEY_LSHIFT', K.KEY_RSHIFT: 'KEY_RSHIFT',
        }
        mods = []
        for code in int_codes[:-1]:
            name = modifier_map.get(code)
            if name:
                mods.append(name)

        key_name = 'KEY_F12'
        if int_codes:
            last = int_codes[-1]
            for attr in dir(K):
                if attr.startswith('KEY_') and getattr(K, attr) == last:
                    key_name = attr
                    break

        g_controller.setHotkey(True, mods, key_name)
    except Exception:
        _log().exception('_update_hotkey_from_codes failed')


def _apply_saved_settings(saved):
    preset_order = ['standard', 'midnight', 'overcast', 'sunset', 'midday']

    current_general = g_controller.getGeneralWeights()
    changed = False
    for pid in preset_order:
        key = 'global_' + pid
        if key in saved:
            current_general[pid] = int(saved[key])
            changed = True
    if changed:
        g_controller.setGeneralWeights(current_general)

    if 'hotkey' in saved:
        raw = saved['hotkey']
        if isinstance(raw, (list, tuple)) and raw:
            _update_hotkey_from_codes([int(c) for c in raw])

    _load_hotkey_codes()


# -----------------------------------------------------------------------------
# INIT / FINI
# -----------------------------------------------------------------------------
def init(*args, **kwargs):
    global _INIT_DONE
    if _INIT_DONE:
        return

    _load_hotkey_codes()
    _install_battle_space_hook()
    _install_key_hook()

    try:
        from gui.modsSettingsApi import g_modsSettingsApi
        from gui.modsSettingsApi import templates as t
        import Keys as K

        hk = g_controller.getHotkey()
        mods = hk.get('mods', ['KEY_LALT'])
        key = hk.get('key', 'KEY_F12')
        current_codes = []

        for m in mods:
            code = getattr(K, m, None)
            if code is not None:
                current_codes.append(code)

        key_code = getattr(K, key, None)
        if key_code is not None:
            current_codes.append(key_code)

        if not current_codes:
            current_codes = [K.KEY_LALT, K.KEY_F12]

        general_weights = g_controller.getGeneralWeights()

        def make_sliders(prefix, values):
            return [
                t.createSlider(varName=prefix + 'standard',
                               text=u'Стандарт',
                               value=values.get('standard', 0), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'midnight',
                               text=u'Ніч',
                               value=values.get('midnight', 0), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'overcast',
                               text=u'Хмарно',
                               value=values.get('overcast', 0), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'sunset',
                               text=u'Захід',
                               value=values.get('sunset', 0), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'midday',
                               text=u'Полудень',
                               value=values.get('midday', 0), min=0, max=20, interval=1),
            ]

        column1 = [
            t.createLabel(text=u'Загальні налаштування для всіх карт'),
            t.createEmpty(),
        ]
        column1.extend(make_sliders('global_', general_weights))
        column1.append(t.createEmpty())
        column1.append(t.createHotkey(varName='hotkey', text=u'Зміна погоди в бою', value=current_codes))

        column2 = [
            t.createLabel(text=u'Налаштування по картах'),
            t.createEmpty(),
            t.createDropdown(varName='active_map', text=u'Карта', options=MAP_LABELS, value=0),
        ]
        column2.extend(make_sliders('map_', {pid: 0 for pid in ['standard', 'midnight', 'overcast', 'sunset', 'midday']}))

        template = {
            'modDisplayName': u'Погода на картах',
            'enabled': True,
            'column1': column1,
            'column2': column2,
        }

        saved = g_modsSettingsApi.setModTemplate(
            linkage='com.example.weather',
            template=template,
            callback=_on_settings_changed,
            buttonHandler=open_weather_window,
        )
        if saved:
            _apply_saved_settings(saved)

    except Exception:
        _log().exception('modsSettingsApi registration failed')

    _INIT_DONE = True


def fini(*args, **kwargs):
    global _INIT_DONE
    _remove_key_hook()
    _remove_battle_space_hook()
    _INIT_DONE = False
