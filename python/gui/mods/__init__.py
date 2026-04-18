# -*- coding: utf-8 -*-
"""
Точка входу мода.

Сумісний lifecycle для нових клієнтів WoT:
- init()
- fini()
- sendEvent(...)
- додаткові no-op hooks з гнучкими сигнатурами

Важливо:
- init() не викликається автоматично при імпорті;
- всі публічні hooks безпечні при повторних викликах;
- сигнатури зроблені через *args/**kwargs, щоб не падати при змінах API клієнта.
"""

try:
    import BigWorld
    import Keys
    from gui import InputHandler
    IN_GAME = True
except ImportError:
    IN_GAME = False

from weather_controller import g_controller


_ORIGINAL_ON_SPACE_LOADED = None
_KEY_HOOK_INSTALLED = False
_INIT_DONE = False


def _log():
    import logging
    return logging.getLogger('weather_mod')


def _install_space_hook():
    global _ORIGINAL_ON_SPACE_LOADED
    if not IN_GAME or _ORIGINAL_ON_SPACE_LOADED is not None:
        return
    try:
        import BWPersonality
        _ORIGINAL_ON_SPACE_LOADED = BWPersonality.onSpaceLoaded

        def wrapped(spaceName):
            g_controller.on_space_about_to_load(spaceName)
            return _ORIGINAL_ON_SPACE_LOADED(spaceName)

        BWPersonality.onSpaceLoaded = wrapped
    except Exception:
        _ORIGINAL_ON_SPACE_LOADED = None
        _log().exception('Failed to install space hook')


def _remove_space_hook():
    global _ORIGINAL_ON_SPACE_LOADED
    if not IN_GAME or _ORIGINAL_ON_SPACE_LOADED is None:
        return
    try:
        import BWPersonality
        BWPersonality.onSpaceLoaded = _ORIGINAL_ON_SPACE_LOADED
    except Exception:
        _log().exception('Failed to remove space hook')
    _ORIGINAL_ON_SPACE_LOADED = None


def _on_key_event(event):
    if not IN_GAME:
        return
    if not hasattr(event, 'isKeyDown') or not event.isKeyDown():
        return

    codes = g_controller.config.hotkey_codes
    if not codes:
        if event.key == Keys.KEY_F12 and BigWorld.isKeyDown(Keys.KEY_LALT):
            g_controller.cycle_preset_in_battle()
        return

    trigger_key = codes[-1]
    modifiers = codes[:-1]
    if event.key != trigger_key:
        return
    for mod in modifiers:
        if not BigWorld.isKeyDown(mod):
            return
    g_controller.cycle_preset_in_battle()


def _install_key_hook():
    global _KEY_HOOK_INSTALLED
    if not IN_GAME or _KEY_HOOK_INSTALLED:
        return
    try:
        if getattr(InputHandler, 'g_instance', None) is not None:
            InputHandler.g_instance.onKeyDown += _on_key_event
            _KEY_HOOK_INSTALLED = True
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
        _log().exception('Failed to remove key hook')
    _KEY_HOOK_INSTALLED = False


def open_weather_window():
    if not IN_GAME:
        return
    try:
        from gui.app_loader import g_appLoader
        from weather_window import WeatherWindowMeta
        app = g_appLoader.getDefLobbyApp()
        if app and hasattr(app, 'containerManager'):
            app.containerManager.load(WeatherWindowMeta())
    except Exception:
        _log().exception('Failed to open weather window')


MAP_IDS = ['', '02_malinovka', '04_himmelsdorf', '05_prohorovka', '06_ensk']


def _on_settings_changed(linkage, newSettings):
    log = _log()
    log.debug('settings changed: %s', newSettings)

    preset_order = ['standard', 'midnight', 'overcast', 'sunset', 'midday']
    for pid in preset_order:
        key = 'global_' + pid
        if key in newSettings:
            g_controller.config.set_global_weight(pid, newSettings[key])

    map_idx = newSettings.get('active_map', 0)
    try:
        active_map = MAP_IDS[int(map_idx)]
    except (IndexError, TypeError, ValueError):
        active_map = ''

    if active_map:
        for pid in preset_order:
            key = 'map_' + pid
            if key in newSettings:
                g_controller.config.set_map_weight(active_map, pid, newSettings[key])

    if 'hotkey' in newSettings:
        raw = newSettings['hotkey']
        if isinstance(raw, (list, tuple)):
            codes = [int(c) for c in raw]
            try:
                import Keys as K
                name_map = {
                    K.KEY_LALT: 'ALT', K.KEY_RALT: 'ALT',
                    K.KEY_LCONTROL: 'CTRL', K.KEY_RCONTROL: 'CTRL',
                    K.KEY_LSHIFT: 'SHIFT', K.KEY_RSHIFT: 'SHIFT'
                }
                parts = [name_map.get(c, 'KEY_%d' % c) for c in codes]
                hotkey_str = '+'.join(parts)
            except Exception:
                hotkey_str = '+'.join(str(c) for c in codes)
            g_controller.on_hotkey_changed(codes, hotkey_str)


def _apply_saved_settings(saved):
    preset_order = ['standard', 'midnight', 'overcast', 'sunset', 'midday']
    for pid in preset_order:
        key = 'global_' + pid
        if key in saved:
            g_controller.config.global_weights[pid] = int(saved[key])
    if 'hotkey' in saved:
        raw = saved['hotkey']
        if isinstance(raw, (list, tuple)) and raw:
            _on_settings_changed('com.example.weather', {'hotkey': raw})


def init(*args, **kwargs):
    global _INIT_DONE
    if _INIT_DONE:
        return

    _install_space_hook()
    _install_key_hook()

    try:
        from gui.modsSettingsApi import g_modsSettingsApi
        from gui.modsSettingsApi import templates as t
        import Keys as K

        current_codes = g_controller.config.hotkey_codes or [K.KEY_LALT, K.KEY_F12]

        template = {
            'modDisplayName': u'Погода на картах',
            'enabled': True,
            'column1': [
                t.createLabel(text=u'Загальні налаштування для всіх карт'),
                t.createEmpty(),
                t.createSlider(varName='global_standard', text=u'Стандарт',
                               value=g_controller.config.global_weights.get('standard', 20),
                               min=0, max=20, interval=1),
                t.createSlider(varName='global_midnight', text=u'Ніч',
                               value=g_controller.config.global_weights.get('midnight', 0),
                               min=0, max=20, interval=1),
                t.createSlider(varName='global_overcast', text=u'Пасмурно',
                               value=g_controller.config.global_weights.get('overcast', 0),
                               min=0, max=20, interval=1),
                t.createSlider(varName='global_sunset', text=u'Закат',
                               value=g_controller.config.global_weights.get('sunset', 0),
                               min=0, max=20, interval=1),
                t.createSlider(varName='global_midday', text=u'Полдень',
                               value=g_controller.config.global_weights.get('midday', 0),
                               min=0, max=20, interval=1),
                t.createEmpty(),
                t.createHotkey(varName='hotkey', text=u'Смена погоды в бою',
                               value=current_codes),
            ],
            'column2': [
                t.createLabel(text=u'Налаштування по картах'),
                t.createEmpty(),
                t.createDropdown(
                    varName='active_map',
                    text=u'Карта',
                    options=[u'— Оберіть карту —', u'Малинівка', u'Хіммельсдорф', u'Прохорівка', u'Енськ'],
                    value=0,
                ),
                t.createSlider(varName='map_standard', text=u'[карта] Стандарт', value=0, min=0, max=20, interval=1),
                t.createSlider(varName='map_midnight', text=u'[карта] Ніч', value=0, min=0, max=20, interval=1),
                t.createSlider(varName='map_overcast', text=u'[карта] Пасмурно', value=0, min=0, max=20, interval=1),
                t.createSlider(varName='map_sunset', text=u'[карта] Закат', value=0, min=0, max=20, interval=1),
                t.createSlider(varName='map_midday', text=u'[карта] Полдень', value=0, min=0, max=20, interval=1),
            ],
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
    _remove_space_hook()
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
