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

WEATHER_PANEL_ALIAS = 'weatherPanel'
WEATHER_PANEL_SWF   = 'weather/WeatherPanel.swf'
_VIEW_REGISTERED    = False

_BATTLE_SPACE_HOOKS = []
_KEY_HOOK_INSTALLED = False
_INIT_DONE = False
_DEFAULT_WEIGHT_VALUE = 20
_PRESET_IDS = ['standard', 'midnight', 'overcast', 'sunset', 'midday']
_HARDCODED_TRIGGER_KEY = getattr(Keys, 'KEY_F12', 0) if IN_GAME else 0

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

                        # Створюємо LSEnvironmentSwitcher через 2 секунди після входу
                        # щоб BigWorld встиг ініціалізувати компоненти простору
                        try:
                            space_id = getattr(self, 'spaceID', None)
                            if space_id and IN_GAME:
                                from weather_controller import _create_switcher_on_battle_start
                                def _delayed_create():
                                    try:
                                        _create_switcher_on_battle_start(space_id)
                                    except Exception as e:
                                        _log().info('delayed switcher create ERR: %s', e)
                                BigWorld.callback(2.0, _delayed_create)
                        except Exception as e:
                            _log().info('switcher scheduling ERR: %s', e)

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
                        # Скидаємо switcher - він невалідний поза боєм
                        try:
                            import weather_controller
                            weather_controller._persistent_switcher = None
                        except Exception:
                            pass
                        # v8: write_environments_xml + environments.json для НАСТУПНОГО бою
                        from weather_controller import (write_environments_xml,
                                                        write_space_settings,
                                                        _write_environments_json)
                        if space_name:
                            write_environments_xml(space_name, preset_id)
                            write_space_settings(space_name, preset_id)
                            # environments.json з усіма guid-ами — WoT прочитає при наступному вході
                            _write_environments_json(space_name, preset_id)
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
# Mod Settings API
# ---------------------------------------------------------------------------

def _get_window_layer():
    """WoT 2.x uses frameworks.wulf.WindowLayer, not old ViewTypes.

    In 2.2.x WindowLayer.WINDOW == 7. The old fallback value 3 is
    WindowLayer.MARKER, so the SWF can be registered but never appear as
    a normal window.
    """
    try:
        from frameworks.wulf import WindowLayer
        return WindowLayer.WINDOW
    except Exception:
        pass
    try:
        from frameworks.wulf.gui_constants import WindowLayer
        return WindowLayer.WINDOW
    except Exception:
        pass
    return 7


def _register_weather_view():
    global _VIEW_REGISTERED
    if _VIEW_REGISTERED:
        return
    try:
        from weather_window import WeatherWindowMeta
        from gui.Scaleform.framework import g_entitiesFactories, ScopeTemplates
        layer = _get_window_layer()

        # Correct location in WoT 2.x: GroupedViewSettings is exported from
        # gui.Scaleform.framework, not gui.Scaleform.framework.entities.GroupedView.
        try:
            from gui.Scaleform.framework import GroupedViewSettings
            settings = GroupedViewSettings(
                WEATHER_PANEL_ALIAS, WeatherWindowMeta, WEATHER_PANEL_SWF,
                layer, None, None, ScopeTemplates.DEFAULT_SCOPE,
                False, None, True, True, False, True
            )
            g_entitiesFactories.addSettings(settings)
            _VIEW_REGISTERED = True
            _log().info('Weather view registered (GroupedViewSettings): alias=%s swf=%s layer=%s',
                        WEATHER_PANEL_ALIAS, WEATHER_PANEL_SWF, layer)
            return
        except Exception as e:
            _log().info('_register: GroupedViewSettings failed: %s', e)

        from gui.Scaleform.framework import ViewSettings
        settings = ViewSettings(
            WEATHER_PANEL_ALIAS, WeatherWindowMeta, WEATHER_PANEL_SWF,
            layer, None, ScopeTemplates.DEFAULT_SCOPE,
            False, None, True, True, False, True
        )
        g_entitiesFactories.addSettings(settings)
        _VIEW_REGISTERED = True
        _log().info('Weather view registered (ViewSettings): alias=%s swf=%s layer=%s',
                    WEATHER_PANEL_ALIAS, WEATHER_PANEL_SWF, layer)
    except Exception:
        _log().exception('Weather view registration failed')


def _register_mods_list_entry():
    """
    modsListApi реєструється пізніше ніж init() —
    тому чекаємо на лобі через callback.
    Пробуємо кілька шляхів імпорту (WoT 2.2.x / 1.x).
    """
    def _do_register():
        g_modsListApi = None
        # WoT 2.x — modsListApi розташований в корені mods
        for mod_path in (
            'gui.mods.modsListApi',
            'modsListApi',
            'gui.modsListApi',
        ):
            try:
                import importlib
                m = importlib.import_module(mod_path)
                g_modsListApi = getattr(m, 'g_modsListApi', None)
                if g_modsListApi is not None:
                    _log().info('modsListApi found at: %s', mod_path)
                    break
            except Exception:
                pass

        if g_modsListApi is None:
            _log().warning('modsListApi not available in any known path')
            return

        try:
            g_modsListApi.addMod(
                id='weather_panel',
                name=u'Погода на картах',
                description=u'Налаштування погодних пресетів для кожної карти',
                icon='gui/maps/icons/pro.environment/modsList.png',
                enabled=True,
                login=False,
                lobby=True,
                callback=open_weather_window,
            )
            _log().info('modsListApi entry registered OK')
        except Exception as e:
            _log().warning('modsListApi.addMod failed: %s', e)

    if not IN_GAME:
        return
    # Реєструємо через callback щоб дати час modsListApi ініціалізуватись
    try:
        import BigWorld
        BigWorld.callback(1.0, _do_register)
    except Exception:
        _do_register()


def open_weather_window():
    _register_weather_view()
    try:
        from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
        app = None
        try:
            from gui.app_loader import g_appLoader
            app = g_appLoader.getDefLobbyApp()
        except Exception:
            pass
        if app is None:
            try:
                from gui.shared.utils.functions import getDefLobbyApp
                app = getDefLobbyApp()
            except Exception:
                pass
        if app is not None:
            app.loadView(SFViewLoadParams(WEATHER_PANEL_ALIAS))
            return
        _log().warning('open_weather_window: no lobby app found')
    except Exception:
        _log().exception('open_weather_window failed')


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

def _intercept_switcher_creation():
    """
    Перехоплюємо створення LSEnvironmentSwitcher щоб зберегти реальний екземпляр.
    Коли WoT сам створить його — ми збережемо посилання.
    """
    if not IN_GAME:
        return
    try:
        import LSArenaPhasesComponent as _ls
        sw_class = getattr(_ls, 'LSEnvironmentSwitcher', None)
        if sw_class is None:
            return
        orig_init = sw_class.__init__
        if getattr(orig_init, '_weather_patched', False):
            return

        def patched_init(self, *args, **kwargs):
            result = orig_init(self, *args, **kwargs)
            try:
                import weather_controller
                weather_controller._persistent_switcher = self
                _log().info('INTERCEPT: captured real LSEnvironmentSwitcher instance (spaceID=%s)',
                           args[0] if args else '?')
            except Exception:
                pass
            return result

        patched_init._weather_patched = True
        sw_class.__init__ = patched_init
        _log().info('LSEnvironmentSwitcher.__init__ patched for interception')
    except Exception:
        _log().exception('_intercept_switcher_creation failed')


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
    _intercept_switcher_creation()
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
                t.createSlider(varName=prefix+'overcast', text=u'Хмарно',   value=weights.get('overcast', _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
                t.createSlider(varName=prefix+'sunset',   text=u'Захід',    value=weights.get('sunset',   _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
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
