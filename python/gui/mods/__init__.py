# -*- coding: utf-8 -*-
"""
Точка входу мода.
v1.4.0 — виправлено розсинхронізацію з weather_controller v4.0
         (прибрано всі звернення до g_controller.config,
          виправлено _get_space_name_from_avatar)
"""

try:
    import BigWorld
    import Keys
    IN_GAME = True
except ImportError:
    IN_GAME = False

_InputHandler = None
def _get_input_handler():
    global _InputHandler
    if _InputHandler is None and IN_GAME:
        try:
            from gui import InputHandler as _ih
            _InputHandler = _ih
        except Exception:
            pass
    return _InputHandler

from weather_controller import g_controller

try:
    from battle_hud import open_hud, handle_key as hud_handle_key, is_active as hud_is_active
    HAS_BATTLE_HUD = True
except ImportError:
    HAS_BATTLE_HUD = False
    def open_hud():
        pass
    def hud_handle_key(k):
        return False
    def hud_is_active():
        return False


_BATTLE_SPACE_HOOKS = []
_KEY_HOOK_INSTALLED = False
_INIT_DONE = False
_hotkey_codes = []
_DEFAULT_WEIGHT_VALUE = 20
_PRESET_IDS = ['standard', 'midnight', 'overcast', 'sunset', 'midday']

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

MAP_IDS    = [m[0] for m in ALL_MAPS]
MAP_LABELS = [m[1] for m in ALL_MAPS]


def _log():
    import logging
    return logging.getLogger('weather_mod')


def _default_weights():
    return dict((pid, _DEFAULT_WEIGHT_VALUE) for pid in _PRESET_IDS)


def _effective_ui_weights(weights):
    result = {}
    source = weights or {}
    total = 0
    for pid in _PRESET_IDS:
        try:
            value = int(source.get(pid, 0))
        except Exception:
            value = 0
        result[pid] = value
        total += value
    if total > 0:
        return result
    return _default_weights()


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


def _extract_space_name_from_arena_type(arena_type):
    if not arena_type:
        return None
    for attr in ('geometryName', 'geometry', 'name'):
        v = getattr(arena_type, attr, None)
        if v and isinstance(v, str):
            name = v.strip()
            if '/' in name:
                name = name.rsplit('/', 1)[-1]
            if name:
                return name
    return None


def _get_space_name_from_avatar(avatar):
    try:
        arena = getattr(avatar, 'arena', None)
        arena_type = getattr(arena, 'arenaType', None) if arena else None
        return _extract_space_name_from_arena_type(arena_type)
    except Exception:
        _log().exception('_get_space_name_from_avatar failed')
    return None


def _install_battle_space_hook():
    if not IN_GAME or _BATTLE_SPACE_HOOKS:
        return

    log = _log()
    installed_any = False

    try:
        import ClientArena

        if hasattr(ClientArena, 'ClientArena'):
            cls_arena = ClientArena.ClientArena
            if hasattr(cls_arena, 'onNewVehicleListReceived'):
                orig_nvlr = cls_arena.onNewVehicleListReceived

                def make_arena_wrapper(orig):
                    def wrapped(self, *args, **kwargs):
                        try:
                            arena_type = getattr(self, 'arenaType', None)
                            space_name = _extract_space_name_from_arena_type(arena_type)
                            if space_name:
                                log.info('ClientArena.onNewVehicleListReceived hook: space=%s', space_name)
                                g_controller.onSpaceEntered(space_name)
                        except Exception:
                            log.exception('ClientArena hook failed')
                        return orig(self, *args, **kwargs)
                    return wrapped

                cls_arena.onNewVehicleListReceived = make_arena_wrapper(orig_nvlr)
                _BATTLE_SPACE_HOOKS.append((cls_arena, 'onNewVehicleListReceived', orig_nvlr))
                log.info('Installed EARLY hook: ClientArena.onNewVehicleListReceived')
                installed_any = True
            else:
                log.warning('ClientArena.onNewVehicleListReceived not found')
        else:
            log.warning('ClientArena.ClientArena class not found')
    except ImportError:
        log.warning('ClientArena module not available, skipping early hook')
    except Exception:
        log.exception('Failed to install ClientArena hook')

    try:
        import Avatar

        if not hasattr(Avatar, 'PlayerAvatar'):
            log.warning('Avatar.PlayerAvatar not found')
        else:
            cls = Avatar.PlayerAvatar
            if not hasattr(cls, 'onEnterWorld'):
                log.warning('PlayerAvatar.onEnterWorld not found')
            else:
                original = cls.onEnterWorld

                def make_wrapper(orig, early_installed):
                    def wrapped(self, *args, **kwargs):
                        try:
                            space_name = _get_space_name_from_avatar(self)
                            if space_name:
                                if early_installed:
                                    log.info('onEnterWorld fallback: space=%s (early hook already ran)', space_name)
                                else:
                                    log.info('onEnterWorld fallback: space=%s (writing space.settings)', space_name)
                                    g_controller.onSpaceEntered(space_name)
                        except Exception:
                            log.exception('onEnterWorld hook failed')
                        return orig(self, *args, **kwargs)
                    return wrapped

                cls.onEnterWorld = make_wrapper(original, installed_any)
                _BATTLE_SPACE_HOOKS.append((cls, 'onEnterWorld', original))
                log.info('Installed FALLBACK hook: Avatar.PlayerAvatar.onEnterWorld (early_installed=%s)', installed_any)

    except Exception:
        log.exception('Failed to install Avatar hook')


def _remove_battle_space_hook():
    while _BATTLE_SPACE_HOOKS:
        cls, attr, original = _BATTLE_SPACE_HOOKS.pop()
        try:
            setattr(cls, attr, original)
        except Exception:
            _log().exception('Failed to remove battle space hook')


def _extract_key_event_data(event_or_key):
    key = None
    is_down = True
    try:
        if hasattr(event_or_key, 'key'):
            key = getattr(event_or_key, 'key', None)
            if hasattr(event_or_key, 'isKeyDown'):
                is_down = bool(event_or_key.isKeyDown())
        else:
            key = int(event_or_key)
            is_down = True
    except Exception:
        key = None
        is_down = False
    return key, is_down


def _hotkey_matches(key_code):
    if not _hotkey_codes:
        return key_code == Keys.KEY_F12 and BigWorld.isKeyDown(Keys.KEY_LALT)
    trigger_key = _hotkey_codes[-1]
    modifiers = _hotkey_codes[:-1]
    if key_code != trigger_key:
        return False
    for mod in modifiers:
        if not BigWorld.isKeyDown(mod):
            return False
    return True


def _handle_hotkey_trigger(key_code):
    in_battle = False
    try:
        player = BigWorld.player()
        in_battle = player is not None and getattr(player, 'arena', None) is not None
    except Exception:
        pass

    _log().info('hotkey matched: key=%s in_battle=%s has_hud=%s', key_code, in_battle, HAS_BATTLE_HUD)
    if HAS_BATTLE_HUD and in_battle:
        open_hud()
    else:
        g_controller.cycleWeatherInBattle()


def _on_key_event(event_or_key):
    if not IN_GAME:
        return

    key_code, is_down = _extract_key_event_data(event_or_key)
    if key_code is None or not is_down:
        return

    if HAS_BATTLE_HUD and hud_is_active():
        if hud_handle_key(key_code):
            return

    if not _hotkey_matches(key_code):
        return

    _handle_hotkey_trigger(key_code)


def _install_key_hook():
    global _KEY_HOOK_INSTALLED
    if not IN_GAME or _KEY_HOOK_INSTALLED:
        return
    log = _log()
    installed = False

    try:
        import AvatarInputHandler as _AIH
        cls_aih = _AIH.AvatarInputHandler
        if hasattr(cls_aih, 'handleKeyEvent'):
            _orig_aih = cls_aih.handleKeyEvent

            def _make_aih_wrapper(orig):
                def _aih_patched(self, *a, **kw):
                    try:
                        if a:
                            _on_key_event(a[0])
                    except Exception:
                        log.exception('AvatarInputHandler hotkey dispatch failed')
                    return orig(self, *a, **kw)
                return _aih_patched

            cls_aih.handleKeyEvent = _make_aih_wrapper(_orig_aih)
            installed = True
            log.info('Key hook installed: AvatarInputHandler.handleKeyEvent (battle)')
        else:
            log.warning('AvatarInputHandler.handleKeyEvent not found')
    except ImportError:
        log.warning('AvatarInputHandler not available')
    except Exception:
        log.exception('Failed to install AvatarInputHandler key hook')

    try:
        _ih = _get_input_handler()
        if _ih is not None and getattr(_ih, 'g_instance', None) is not None:
            _ih.g_instance.onKeyDown += _on_key_event
            installed = True
            log.info('Key hook installed: InputHandler.g_instance.onKeyDown (global)')
    except Exception:
        log.exception('Failed to install InputHandler key hook')

    _KEY_HOOK_INSTALLED = installed


def _remove_key_hook():
    global _KEY_HOOK_INSTALLED
    if not IN_GAME or not _KEY_HOOK_INSTALLED:
        return
    try:
        _ih = _get_input_handler()
        if _ih is not None and getattr(_ih, 'g_instance', None) is not None:
            _ih.g_instance.onKeyDown -= _on_key_event
    except Exception:
        pass
    _KEY_HOOK_INSTALLED = False


def open_weather_window():
    try:
        from gui import SystemMessages
        SystemMessages.pushI18nMessage(
            u'Окреме вікно ще не підключене. Користуйся панеллю Mod Settings.',
            type=SystemMessages.SM_TYPE.Information
        )
    except Exception:
        pass


def _on_settings_changed(linkage, newSettings):
    log = _log()
    log.debug('settings changed: %s', newSettings)

    current_general = g_controller.getGeneralWeights()
    changed_general = False
    for pid in _PRESET_IDS:
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
        for pid in _PRESET_IDS:
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
            K.KEY_LALT: 'LALT', K.KEY_RALT: 'RALT',
            K.KEY_LCONTROL: 'LCTRL', K.KEY_RCONTROL: 'RCTRL',
            K.KEY_LSHIFT: 'LSHIFT', K.KEY_RSHIFT: 'RSHIFT',
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
    current_general = g_controller.getGeneralWeights()
    changed = False
    for pid in _PRESET_IDS:
        key = 'global_' + pid
        if key in saved:
            current_general[pid] = int(saved[key])
            changed = True
    if changed:
        g_controller.setGeneralWeights(current_general)

    map_idx = saved.get('active_map', 0)
    try:
        active_map = MAP_IDS[int(map_idx)]
    except (IndexError, TypeError, ValueError):
        active_map = ''
    if active_map:
        current_map = g_controller.getMapWeights(active_map)
        changed_map = False
        for pid in _PRESET_IDS:
            key = 'map_' + pid
            if key in saved:
                current_map[pid] = int(saved[key])
                changed_map = True
        if changed_map:
            g_controller.setMapWeights(active_map, current_map)

    if 'hotkey' in saved:
        raw = saved['hotkey']
        if isinstance(raw, (list, tuple)) and raw:
            _update_hotkey_from_codes([int(c) for c in raw])

    _load_hotkey_codes()


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
        mods = hk.get('mods', ['LALT'])
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

        general_weights = _effective_ui_weights(g_controller.getGeneralWeights())
        default_map_weights = _default_weights()

        def make_sliders(prefix, values):
            weights = _effective_ui_weights(values)
            return [
                t.createSlider(varName=prefix + 'standard', text=u'Стандарт' if prefix == 'global_' else u'[карта] Стандарт', value=weights.get('standard', _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'midnight', text=u'Ніч' if prefix == 'global_' else u'[карта] Ніч', value=weights.get('midnight', _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'overcast', text=u'Хмарно' if prefix == 'global_' else u'[карта] Хмарно', value=weights.get('overcast', _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'sunset', text=u'Захід' if prefix == 'global_' else u'[карта] Захід', value=weights.get('sunset', _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'midday', text=u'Полудень' if prefix == 'global_' else u'[карта] Полудень', value=weights.get('midday', _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
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
        column2.extend(make_sliders('map_', default_map_weights))

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


def sendEvent(*args, **kwargs):
    return None


def handleKeyEvent(event=None, *args, **kwargs):
    try:
        if event is not None:
            _on_key_event(event)
    except Exception:
        _log().exception('handleKeyEvent failed')
    return None


def onAccountBecomePlayer(*args, **kwargs):
    if not _INIT_DONE:
        init()
    return None


def onBecomePlayer(*args, **kwargs):
    if not _INIT_DONE:
        init()
    return None


def startGUI(*args, **kwargs):
    if not _INIT_DONE:
        init()
    return None


def destroyGUI(*args, **kwargs):
    return None


def onDisconnected(*args, **kwargs):
    return None


def onConnected(*args, **kwargs):
    return None
