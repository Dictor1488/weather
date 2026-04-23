# -*- coding: utf-8 -*-
"""
Точка входу мода. v3.0
Сумісність з weather_controller v8.0
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

_BATTLE_SPACE_HOOKS = []
_KEY_HOOK_INSTALLED = False
_INIT_DONE = False
_DEFAULT_WEIGHT_VALUE = 20
_PRESET_IDS = ['standard', 'midnight', 'overcast', 'sunset', 'midday']
_HARDCODED_TRIGGER_KEY = getattr(Keys, 'KEY_F12', 0) if IN_GAME else 0

ALL_MAPS = [
    ('01_karelia',             u'Карелія'),
    ('02_malinovka',           u'Малинівка'),
    ('03_campania_big',        u'Кампанія'),
    ('04_himmelsdorf',         u'Хіммельсдорф'),
    ('05_prohorovka',          u'Прохорівка'),
    ('06_ensk',                u'Єнськ'),
    ('07_lakeville',           u'Ласвілль'),
    ('08_ruinberg',            u'Руїнберг'),
    ('10_hills',               u'Круча'),
    ('11_murovanka',           u'Мурованка'),
    ('13_erlenberg',           u'Ерленберг'),
    ('14_siegfried_line',      u'Лінія Зигфріда'),
    ('17_munchen',             u'Крафтверк'),
    ('18_cliff',               u'Перевал'),
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
    ('101_dday',               u'Нормандія'),
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
    ('217_er_alaska',          u'Клондайк'),
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
    total  = 0
    source = weights or {}
    for pid in _PRESET_IDS:
        try:
            value = int(source.get(pid, 0))
        except Exception:
            value = 0
        result[pid] = value
        total += value
    return result if total > 0 else _default_weights()


def _load_hotkey_codes():
    if IN_GAME:
        try:
            g_controller.setHotkey(True, [], 'KEY_F12')
        except Exception:
            _log().exception('_load_hotkey_codes failed')


def _extract_space_name_from_arena_type(arena_type):
    if not arena_type:
        return None
    for attr in ('geometryName', 'geometry', 'name'):
        v = getattr(arena_type, attr, None)
        if v and isinstance(v, str):
            name = v.strip().rsplit('/', 1)[-1]
            if name:
                return name
    return None


def _get_space_name_from_avatar(avatar):
    try:
        arena      = getattr(avatar, 'arena', None)
        arena_type = getattr(arena, 'arenaType', None) if arena else None
        return _extract_space_name_from_arena_type(arena_type)
    except Exception:
        _log().exception('_get_space_name_from_avatar failed')
    return None


def _get_space_name_for_become_player(avatar):
    log = _log()
    # Спосіб 1: arenaTypeID + ArenaType.g_cache
    try:
        arena_type_id = getattr(avatar, 'arenaTypeID', None)
        if arena_type_id:
            from ArenaType import g_cache
            arena_type = g_cache.get(arena_type_id)
            if arena_type:
                name = _extract_space_name_from_arena_type(arena_type)
                if name:
                    log.info('_get_space_name_for_become_player: arenaTypeID=%s -> %s',
                             arena_type_id, name)
                    return name
    except Exception as e:
        log.warning('_get_space_name_for_become_player: arenaTypeID ERR: %s', e)
    # Спосіб 2: arena.arenaType
    name = _get_space_name_from_avatar(avatar)
    if name:
        log.info('_get_space_name_for_become_player: via arena.arenaType = %s', name)
        return name
    # Спосіб 3: arena.geometryName напряму
    try:
        arena = getattr(avatar, 'arena', None)
        if arena:
            for attr in ('geometryName', 'geometry'):
                v = getattr(arena, attr, None)
                if v and isinstance(v, str):
                    name = v.strip().rsplit('/', 1)[-1]
                    if name:
                        log.info('_get_space_name_for_become_player: arena.%s = %s', attr, name)
                        return name
    except Exception as e:
        log.warning('_get_space_name_for_become_player: arena.geometryName ERR: %s', e)
    log.warning('_get_space_name_for_become_player: could not determine space name')
    return None


_become_player_wrote_spaces = set()

def _mark_become_player_wrote(space_name):
    _become_player_wrote_spaces.add(space_name)

def _become_player_wrote_for_space(space_name):
    return space_name in _become_player_wrote_spaces


def _install_battle_space_hook():
    log = _log()
    try:
        import Avatar
        if not hasattr(Avatar, 'PlayerAvatar'):
            log.warning('Avatar.PlayerAvatar not found')
            return
        cls = Avatar.PlayerAvatar

        # onBecomePlayer — найраніший момент
        if hasattr(cls, 'onBecomePlayer'):
            orig_bp = cls.onBecomePlayer
            def make_bp_wrapper(orig):
                def wrapped_bp(self, *a, **kw):
                    try:
                        space_name = _get_space_name_for_become_player(self)
                        if space_name:
                            _log().info('onBecomePlayer hook: space=%s -> writing files', space_name)
                            result = g_controller.onSpaceEntered(space_name)
                            if result:
                                _mark_become_player_wrote(space_name)
                                _log().info('onBecomePlayer hook: files written OK for %s', space_name)
                            else:
                                _log().warning('onBecomePlayer hook: onSpaceEntered returned False for %s', space_name)
                        else:
                            _log().warning('onBecomePlayer hook: no space_name')
                    except Exception:
                        _log().exception('onBecomePlayer hook failed')
                    return orig(self, *a, **kw)
                return wrapped_bp
            cls.onBecomePlayer = make_bp_wrapper(orig_bp)
            _BATTLE_SPACE_HOOKS.append((cls, 'onBecomePlayer', orig_bp))
            log.info('Installed EARLY hook: Avatar.PlayerAvatar.onBecomePlayer')

        # onEnterWorld — запасний
        if hasattr(cls, 'onEnterWorld'):
            original = cls.onEnterWorld
            def make_wrapper(orig):
                def wrapped(self, *args, **kwargs):
                    try:
                        space_name = _get_space_name_from_avatar(self)
                        if space_name:
                            if _become_player_wrote_for_space(space_name):
                                _log().info('onEnterWorld: space=%s skip (onBecomePlayer OK)', space_name)
                            else:
                                _log().info('onEnterWorld: space=%s writing', space_name)
                                g_controller.onSpaceEntered(space_name)
                    except Exception:
                        _log().exception('onEnterWorld hook failed')
                    return orig(self, *args, **kwargs)
                return wrapped
            cls.onEnterWorld = make_wrapper(original)
            _BATTLE_SPACE_HOOKS.append((cls, 'onEnterWorld', original))
            log.info('Installed FALLBACK hook: Avatar.PlayerAvatar.onEnterWorld')

        # onLeaveWorld — записуємо пресет для наступного бою
        if hasattr(cls, 'onLeaveWorld'):
            orig_lw = cls.onLeaveWorld
            def make_lw_wrapper(orig):
                def wrapped_lw(self, *a, **kw):
                    try:
                        space_name = _get_space_name_from_avatar(self)
                        preset_id  = g_controller.getCurrentPreset()
                        _log().info('onLeaveWorld: space=%s preset=%s -> writing files', space_name, preset_id)
                        # v8: write_environments_xml для поточної карти
                        from weather_controller import write_environments_xml, write_space_settings
                        if space_name:
                            write_environments_xml(space_name, preset_id)
                            write_space_settings(space_name, preset_id)
                    except Exception:
                        _log().exception('onLeaveWorld hook failed')
                    return orig(self, *a, **kw)
                return wrapped_lw
            cls.onLeaveWorld = make_lw_wrapper(orig_lw)
            _BATTLE_SPACE_HOOKS.append((cls, 'onLeaveWorld', orig_lw))
            log.info('Installed POST-BATTLE hook: Avatar.PlayerAvatar.onLeaveWorld')

    except Exception:
        log.exception('Failed to install Avatar hook')


def _remove_battle_space_hook():
    while _BATTLE_SPACE_HOOKS:
        cls, attr, original = _BATTLE_SPACE_HOOKS.pop()
        try:
            setattr(cls, attr, original)
        except Exception:
            _log().exception('Failed to remove battle space hook')


# ---------------------------------------------------------------------------
# Клавіатура
# ---------------------------------------------------------------------------

def _hotkey_matches(key_code):
    return bool(_HARDCODED_TRIGGER_KEY) and key_code == _HARDCODED_TRIGGER_KEY


def _handle_hotkey_trigger(key_code):
    in_battle = False
    try:
        player    = BigWorld.player()
        in_battle = player is not None and getattr(player, 'arena', None) is not None
    except Exception:
        pass
    _log().info('hotkey matched: key=%s in_battle=%s', key_code, in_battle)
    if in_battle:
        g_controller.cyclePreset()


def _extract_key_event_data(event_or_key):
    key = None
    is_down = True
    try:
        if hasattr(event_or_key, 'key'):
            key     = getattr(event_or_key, 'key', None)
            is_down = bool(event_or_key.isKeyDown()) if hasattr(event_or_key, 'isKeyDown') else True
        else:
            key = int(event_or_key)
    except Exception:
        key = None
    return key, is_down


def _on_key_event(event_or_key):
    if not IN_GAME:
        return
    key_code, is_down = _extract_key_event_data(event_or_key)
    if key_code is None or not is_down:
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
                        _log().exception('AvatarInputHandler hotkey dispatch failed')
                    return orig(self, *a, **kw)
                return _aih_patched
            cls_aih.handleKeyEvent = _make_aih_wrapper(_orig_aih)
            installed = True
            log.info('Key hook: AvatarInputHandler.handleKeyEvent OK')
    except ImportError:
        log.warning('AvatarInputHandler not available')
    except Exception:
        log.exception('Failed to install AvatarInputHandler key hook')

    if not installed:
        try:
            _ih = _get_input_handler()
            if _ih is not None and getattr(_ih, 'g_instance', None) is not None:
                _ih.g_instance.onKeyDown += _on_key_event
                installed = True
                log.info('Key hook: InputHandler.g_instance.onKeyDown OK (fallback)')
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
            try:
                _ih.g_instance.onKeyDown -= _on_key_event
            except Exception:
                pass
    except Exception:
        pass
    _KEY_HOOK_INSTALLED = False


# ---------------------------------------------------------------------------
# Власне вікно + кнопка в нижньому меню модів
# ---------------------------------------------------------------------------

WEATHER_PANEL_ALIAS = 'weatherPanel'
WEATHER_PANEL_SWF = 'weather/WeatherPanel.swf'
_MODS_LIST_ICON = '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'
_VIEW_REGISTERED = False


def _register_weather_view():
    global _VIEW_REGISTERED
    if _VIEW_REGISTERED:
        return
    try:
        from gui.Scaleform.framework import ViewSettings, ViewTypes, ScopeTemplates, g_entitiesFactories
        from weather_window import WeatherWindowMeta
        settings = ViewSettings(WEATHER_PANEL_ALIAS, WeatherWindowMeta, WEATHER_PANEL_SWF,
                                ViewTypes.WINDOW, None, ScopeTemplates.DEFAULT_SCOPE)
        g_entitiesFactories.addSettings(settings)
        _VIEW_REGISTERED = True
        _log().info('Weather view registered: %s', WEATHER_PANEL_ALIAS)
    except Exception:
        _log().exception('Weather view registration failed')


def _register_mods_list_entry():
    try:
        from gui.mods.modsListApi import g_modsListApi
        g_modsListApi.addMod(
            id='weather_panel',
            name=u'Погода на картах',
            description=u'Окрема панель керування погодними пресетами',
            icon=_MODS_LIST_ICON,
            enabled=True,
            login=False,
            lobby=True,
            callback=open_weather_window,
        )
        _log().info('modsListApi entry registered')
    except Exception:
        _log().warning('modsListApi not available or entry registration failed')


# ---------------------------------------------------------------------------
# Mod Settings API
# ---------------------------------------------------------------------------

def open_weather_window():
    try:
        from gui.app_loader import g_appLoader
        from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
        _register_weather_view()
        app = g_appLoader.getDefLobbyApp()
        if app is not None:
            app.loadView(SFViewLoadParams(WEATHER_PANEL_ALIAS))
            return
    except Exception:
        _log().exception('open_weather_window failed')

    try:
        from gui import SystemMessages
        SystemMessages.pushMessage(
            u'Не вдалося відкрити вікно погоди. Перевір SWF та реєстрацію view.',
            type=SystemMessages.SM_TYPE.Error)
    except Exception:
        pass


def _on_settings_changed(linkage, newSettings):
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

    _load_hotkey_codes()


# ---------------------------------------------------------------------------
# init / fini
# ---------------------------------------------------------------------------

def _patch_ls_env_switcher():
    """Перехоплює _switchEnvironment для діагностики."""
    try:
        import LSArenaPhasesComponent as _ls
        sw = _ls.LSEnvironmentSwitcher
        orig_switch = sw._switchEnvironment
        orig_setup  = sw.setupEnvironment

        def patched_switch(self, *args, **kwargs):
            _log().info('INTERCEPT _switchEnvironment: args=%s _spaceID=%s',
                        args, getattr(self, '_spaceID', 'MISSING'))
            return orig_switch(self, *args, **kwargs)

        def patched_setup(self, *args, **kwargs):
            _log().info('INTERCEPT setupEnvironment: args=%s _spaceID=%s',
                        args, getattr(self, '_spaceID', 'MISSING'))
            return orig_setup(self, *args, **kwargs)

        sw._switchEnvironment = patched_switch
        sw.setupEnvironment   = patched_setup
        _log().info('LSEnvironmentSwitcher patched for interception OK')
    except Exception as e:
        _log().warning('patch LSEnvSwitcher ERR: %s', e)


def init(*args, **kwargs):
    global _INIT_DONE
    if _INIT_DONE:
        return

    _patch_ls_env_switcher()
    _load_hotkey_codes()
    _install_battle_space_hook()
    _install_key_hook()
    _register_weather_view()
    _register_mods_list_entry()

    try:
        from gui.modsSettingsApi import g_modsSettingsApi
        from gui.modsSettingsApi import templates as t
        import Keys as K

        current_codes       = [_HARDCODED_TRIGGER_KEY] if _HARDCODED_TRIGGER_KEY else [K.KEY_F12]
        general_weights     = _effective_ui_weights(g_controller.getGeneralWeights())
        default_map_weights = _default_weights()

        def make_sliders(prefix, values):
            weights = _effective_ui_weights(values)
            return [
                t.createSlider(varName=prefix+'standard', text=u'Стандарт', value=weights.get('standard', _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
                t.createSlider(varName=prefix+'midnight', text=u'Ніч',      value=weights.get('midnight', _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
                t.createSlider(varName=prefix+'overcast', text=u'Похмуро',   value=weights.get('overcast', _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
                t.createSlider(varName=prefix+'sunset',   text=u'Захід сонця',    value=weights.get('sunset',   _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
                t.createSlider(varName=prefix+'midday',   text=u'Полудень', value=weights.get('midday',   _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
            ]

        column1 = [t.createLabel(text=u'Загальні налаштування'), t.createEmpty()]
        column1.extend(make_sliders('global_', general_weights))
        column1.append(t.createEmpty())
        column1.append(t.createHotkey(varName='hotkey', text=u'Зміна погоди в бою', value=current_codes))

        column2 = [
            t.createLabel(text=u'Налаштування по картах'), t.createEmpty(),
            t.createDropdown(varName='active_map', text=u'Карта', options=MAP_LABELS, value=0),
        ]
        column2.extend(make_sliders('map_', default_map_weights))

        template = {
            'modDisplayName': u'Погода на картах',
            'enabled':        True,
            'column1':        column1,
            'column2':        column2,
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


def onBecomeNonPlayer(*args, **kwargs):
    global _become_player_wrote_spaces
    try:
        _become_player_wrote_spaces = set()
    except Exception:
        _log().exception('onBecomeNonPlayer failed')
    return None


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
