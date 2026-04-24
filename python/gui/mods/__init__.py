# -*- coding: utf-8 -*-
"""
Entry point for Weather mod.

Important UI rule:
- Do NOT touch ModsListAPI / ModsSettingsAPI on the login screen.
- Register UI only after the lobby app is really available, otherwise other
  mods' popovers/settings may fail to initialize.
"""

try:
    import BigWorld
    import Keys
    IN_GAME = True
except ImportError:
    IN_GAME = False

try:
    from weather_controller import g_controller
except Exception:
    g_controller = None

WEATHER_PANEL_ALIAS = 'weatherPanel'
WEATHER_PANEL_SWF = 'WeatherPanel.swf'
_VIEW_REGISTERED = False
_INIT_DONE = False
_MODSLIST_REGISTERED = False
_MODSSETTINGS_REGISTERED = False
_KEY_HOOK_INSTALLED = False
_BATTLE_HOOK_INSTALLED = False

_HARDCODED_TRIGGER_KEY = getattr(Keys, 'KEY_F12', 0) if IN_GAME else 0


def _log():
    import logging
    return logging.getLogger('weather_mod')


# ---------------------------------------------------------------------------
# Lobby readiness
# ---------------------------------------------------------------------------

def _get_lobby_app():
    app = None
    try:
        from helpers import dependency
        from skeletons.gui.app_loader import IAppLoader
        app_loader = dependency.instance(IAppLoader)
        try:
            app = app_loader.getDefLobbyApp()
            if app is not None:
                return app
        except Exception:
            pass
        try:
            from gui.app_loader.settings import APP_NAME_SPACE
            for name in ('SF_LOBBY', 'LOBBY'):
                if hasattr(APP_NAME_SPACE, name):
                    try:
                        app = app_loader.getApp(getattr(APP_NAME_SPACE, name))
                        if app is not None:
                            return app
                    except Exception:
                        pass
        except Exception:
            pass
    except Exception:
        pass
    try:
        from gui.app_loader import g_appLoader
        app = g_appLoader.getDefLobbyApp()
        if app is not None:
            return app
    except Exception:
        pass
    return None


def _is_player_in_login_space():
    try:
        p = BigWorld.player()
        name = p.__class__.__name__.lower() if p is not None else ''
        if 'login' in name:
            return True
    except Exception:
        pass
    return False


def _is_lobby_ready():
    if not IN_GAME:
        return False
    if _is_player_in_login_space():
        return False
    return _get_lobby_app() is not None


def _run_when_lobby_ready(func, attempt=0, max_attempts=60):
    if not IN_GAME:
        return
    try:
        if _is_lobby_ready():
            func()
            return
    except Exception:
        _log().exception('lobby readiness check failed')

    if attempt < max_attempts:
        BigWorld.callback(1.0, lambda: _run_when_lobby_ready(func, attempt + 1, max_attempts))
    else:
        _log().warning('Skipped delayed UI registration: lobby not ready')


# ---------------------------------------------------------------------------
# Weather SWF view
# ---------------------------------------------------------------------------

def _get_window_layer():
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
        from gui.Scaleform.framework import g_entitiesFactories, ScopeTemplates, ViewSettings
        layer = _get_window_layer()
        settings = ViewSettings(
            WEATHER_PANEL_ALIAS,
            WeatherWindowMeta,
            WEATHER_PANEL_SWF,
            layer,
            None,
            ScopeTemplates.GLOBAL_SCOPE,
        )
        try:
            g_entitiesFactories.removeSettings(WEATHER_PANEL_ALIAS)
        except Exception:
            pass
        g_entitiesFactories.addSettings(settings)
        _VIEW_REGISTERED = True
        _log().info('Weather custom view registered: alias=%s swf=%s layer=%s scope=GLOBAL', WEATHER_PANEL_ALIAS, WEATHER_PANEL_SWF, layer)
    except Exception:
        _log().exception('Weather custom view registration failed')


def open_weather_window(*args, **kwargs):
    _register_weather_view()

    def _load():
        try:
            try:
                from weather_window import show_existing_window
                if show_existing_window():
                    _log().info('open_weather_window: reused hidden/existing weatherPanel')
                    return
            except Exception:
                _log().exception('open_weather_window: reuse existing panel failed')

            from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
            app = _get_lobby_app()
            if app is None:
                _log().warning('open_weather_window: no lobby app found')
                return
            params = SFViewLoadParams(WEATHER_PANEL_ALIAS)
            _log().info('open_weather_window: loadView alias=%s swf=%s app=%s', WEATHER_PANEL_ALIAS, WEATHER_PANEL_SWF, app)
            try:
                app.loadView(params)
                _log().info('open_weather_window: app.loadView OK')
                return
            except Exception as e:
                _log().warning('open_weather_window: app.loadView failed: %s', e)
            try:
                loader = getattr(app, 'loaderManager', None)
                if loader is not None:
                    loader.loadView(params)
                    _log().info('open_weather_window: loaderManager.loadView OK')
                    return
            except Exception as e:
                _log().warning('open_weather_window: loaderManager.loadView failed: %s', e)
            _log().warning('open_weather_window: all loadView attempts failed')
        except Exception:
            _log().exception('open_weather_window failed')

    try:
        BigWorld.callback(0.05, _load)
    except Exception:
        _load()


# ---------------------------------------------------------------------------
# Delayed UI registration
# ---------------------------------------------------------------------------

def _register_mods_list_entry_now():
    global _MODSLIST_REGISTERED
    if _MODSLIST_REGISTERED:
        return
    g_modsListApi = None
    for mod_path in ('gui.mods.modsListApi', 'modsListApi', 'gui.modsListApi'):
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

    entry = {
        'id': 'weather_panel',
        'name': u'Погода на картах',
        'description': u'Налаштування погодних пресетів для кожної карти',
        'icon': 'gui/maps/icons/pro.environment/modsList.png',
        'enabled': True,
        'login': False,
        'lobby': True,
        'callback': open_weather_window,
    }

    def _try_register(method_name):
        method = getattr(g_modsListApi, method_name, None)
        if method is None:
            return False
        attempts = (
            lambda: method(**entry),
            lambda: method(entry['id'], entry['name'], entry['description'], entry['icon'], entry['enabled'], entry['login'], entry['lobby'], entry['callback']),
            lambda: method(entry['id'], entry['name'], entry['icon'], entry['enabled'], entry['login'], entry['lobby'], entry['callback']),
            lambda: method(entry['id'], entry['name'], entry['description'], entry['icon'], entry['callback']),
        )
        last_error = None
        for call in attempts:
            try:
                call()
                _log().info('modsListApi entry registered OK via %s', method_name)
                return True
            except TypeError as e:
                last_error = e
            except Exception as e:
                _log().warning('modsListApi.%s failed: %s', method_name, e)
                return False
        _log().warning('modsListApi.%s signature mismatch: %s', method_name, last_error)
        return False

    for method_name in ('addModification', 'addMod', 'add'):
        if _try_register(method_name):
            _MODSLIST_REGISTERED = True
            return

    try:
        methods = [m for m in dir(g_modsListApi) if m.lower().startswith('add')]
    except Exception:
        methods = []
    _log().warning('modsListApi entry registration failed; available add* methods=%s', methods)


def _register_mods_settings_status_now():
    global _MODSSETTINGS_REGISTERED
    if _MODSSETTINGS_REGISTERED:
        return
    try:
        from gui.modsSettingsApi import g_modsSettingsApi
        from gui.modsSettingsApi import templates as t
    except Exception as e:
        _log().info('modsSettingsApi not available for status card: %s', e)
        return

    def _status_callback(linkage, newSettings):
        try:
            if g_controller is not None and 'enabled' in newSettings and hasattr(g_controller, 'setEnabled'):
                g_controller.setEnabled(bool(newSettings.get('enabled')))
        except Exception:
            _log().exception('modsSettingsApi status callback failed')

    try:
        enabled = True
        try:
            enabled = bool(g_controller.isEnabled()) if g_controller is not None and hasattr(g_controller, 'isEnabled') else True
        except Exception:
            enabled = True
        status_text = u'Статус: увімкнено' if enabled else u'Статус: вимкнено'
        template = {
            'modDisplayName': u'Погода на картах',
            'enabled': enabled,
            'column1': [
                t.createLabel(text=status_text),
                t.createEmpty(),
                t.createLabel(text=u'Налаштування відкриваються через:'),
                t.createLabel(text=u'Список модифікацій → Погода на картах'),
            ],
            'column2': [
                t.createLabel(text=u'Ця сторінка лише показує статус мода.'),
                t.createEmpty(),
                t.createLabel(text=u'Слайдери та карти перенесені у власне вікно.'),
            ],
        }
        g_modsSettingsApi.setModTemplate(
            linkage='com.example.weather.status',
            template=template,
            callback=_status_callback,
        )
        _MODSSETTINGS_REGISTERED = True
        _log().info('modsSettingsApi minimal status card registered OK')
    except Exception:
        _log().exception('modsSettingsApi minimal status registration failed')


def _register_ui_when_lobby_ready():
    try:
        BigWorld.callback(8.0, lambda: _run_when_lobby_ready(_register_mods_list_entry_now))
        BigWorld.callback(9.0, lambda: _run_when_lobby_ready(_register_mods_settings_status_now))
    except Exception:
        _run_when_lobby_ready(_register_mods_list_entry_now)
        _run_when_lobby_ready(_register_mods_settings_status_now)


# ---------------------------------------------------------------------------
# Battle hooks / hotkey
# ---------------------------------------------------------------------------

def _extract_space_name_from_arena_type(arena_type):
    if not arena_type:
        return None
    for attr in ('geometryName', 'geometry', 'name'):
        value = getattr(arena_type, attr, None)
        if value and isinstance(value, str):
            name = value.strip().rsplit('/', 1)[-1]
            if name:
                return name
    return None


def _get_space_name_from_avatar(avatar):
    try:
        arena = getattr(avatar, 'arena', None)
        arena_type = getattr(arena, 'arenaType', None) if arena else None
        name = _extract_space_name_from_arena_type(arena_type)
        if name:
            return name
        arena_type_id = getattr(avatar, 'arenaTypeID', None)
        if arena_type_id:
            from ArenaType import g_cache
            arena_type = g_cache.get(arena_type_id)
            return _extract_space_name_from_arena_type(arena_type)
    except Exception:
        pass
    return None


def _install_battle_space_hook():
    global _BATTLE_HOOK_INSTALLED
    if _BATTLE_HOOK_INSTALLED or g_controller is None:
        return
    try:
        import Avatar
        if not hasattr(Avatar, 'PlayerAvatar'):
            return
        cls = Avatar.PlayerAvatar
        if hasattr(cls, 'onBecomePlayer'):
            orig = cls.onBecomePlayer
            if getattr(orig, '_weather_patched', False):
                _BATTLE_HOOK_INSTALLED = True
                return
            def wrapped(self, *args, **kwargs):
                try:
                    space_name = _get_space_name_from_avatar(self)
                    if space_name:
                        _log().info('onBecomePlayer hook: space=%s -> writing files', space_name)
                        g_controller.onSpaceEntered(space_name)
                except Exception:
                    _log().exception('onBecomePlayer hook failed')
                return orig(self, *args, **kwargs)
            wrapped._weather_patched = True
            cls.onBecomePlayer = wrapped
            _BATTLE_HOOK_INSTALLED = True
            _log().info('Installed battle hook: Avatar.PlayerAvatar.onBecomePlayer')
    except Exception:
        _log().exception('Failed to install battle hook')


def _hotkey_matches(key_code):
    return bool(_HARDCODED_TRIGGER_KEY) and key_code == _HARDCODED_TRIGGER_KEY


def _extract_key_event_data(event_or_key):
    key = None
    is_down = True
    try:
        if hasattr(event_or_key, 'key'):
            key = getattr(event_or_key, 'key', None)
            is_down = bool(event_or_key.isKeyDown()) if hasattr(event_or_key, 'isKeyDown') else True
        else:
            key = int(event_or_key)
    except Exception:
        key = None
    return key, is_down


def _on_key_event(event_or_key):
    if not IN_GAME or g_controller is None:
        return
    key_code, is_down = _extract_key_event_data(event_or_key)
    if key_code is None or not is_down or not _hotkey_matches(key_code):
        return
    try:
        player = BigWorld.player()
        in_battle = player is not None and getattr(player, 'arena', None) is not None
        _log().info('hotkey matched: key=%s in_battle=%s', key_code, in_battle)
        if in_battle:
            g_controller.cyclePreset()
    except Exception:
        _log().exception('hotkey handling failed')


def _install_key_hook():
    global _KEY_HOOK_INSTALLED
    if not IN_GAME or _KEY_HOOK_INSTALLED:
        return
    try:
        import AvatarInputHandler as _AIH
        cls = _AIH.AvatarInputHandler
        if hasattr(cls, 'handleKeyEvent'):
            orig = cls.handleKeyEvent
            if getattr(orig, '_weather_patched', False):
                _KEY_HOOK_INSTALLED = True
                return
            def wrapped(self, *args, **kwargs):
                try:
                    if args:
                        _on_key_event(args[0])
                except Exception:
                    _log().exception('AvatarInputHandler hotkey dispatch failed')
                return orig(self, *args, **kwargs)
            wrapped._weather_patched = True
            cls.handleKeyEvent = wrapped
            _KEY_HOOK_INSTALLED = True
            _log().info('Key hook: AvatarInputHandler.handleKeyEvent OK')
            return
    except Exception:
        _log().exception('Failed to install AvatarInputHandler key hook')


# ---------------------------------------------------------------------------
# Entry points expected by mod loaders
# ---------------------------------------------------------------------------

def init(*args, **kwargs):
    global _INIT_DONE
    if _INIT_DONE:
        return
    _install_battle_space_hook()
    _install_key_hook()
    _register_weather_view()
    _register_ui_when_lobby_ready()
    _INIT_DONE = True
    _log().info('weather init done; UI registration is delayed until lobby is ready')


def fini(*args, **kwargs):
    global _INIT_DONE
    _INIT_DONE = False


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


def sendEvent(*args, **kwargs):
    return None


def handleKeyEvent(event=None, *args, **kwargs):
    try:
        if event is not None:
            _on_key_event(event)
    except Exception:
        _log().exception('handleKeyEvent failed')
    return None


def onBecomeNonPlayer(*args, **kwargs):
    return None


def onDisconnected(*args, **kwargs):
    return None


def onConnected(*args, **kwargs):
    return None
