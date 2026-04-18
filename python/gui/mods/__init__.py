# -*- coding: utf-8 -*-
"""
Точка входу мода.
"""

try:
    import BigWorld
    import Keys
    from gui import InputHandler
    IN_GAME = True
except ImportError:
    IN_GAME = False

from weather_controller import g_controller


def _install_space_hook():
    if not IN_GAME:
        return
    try:
        import BWPersonality
        original = BWPersonality.onSpaceLoaded

        def wrapped(spaceName):
            g_controller.on_space_about_to_load(spaceName)
            return original(spaceName)

        BWPersonality.onSpaceLoaded = wrapped
    except Exception:
        pass


def _on_key_event(event):
    """
    FIX 1: читаємо хоткей з конфігу, а не хардкодимо ALT+F12.
    Якщо hotkey_codes не збережено — fallback на KEY_LALT + KEY_F12.
    """
    if not IN_GAME:
        return
    if not event.isKeyDown():
        return

    codes = g_controller.config.hotkey_codes

    # Fallback якщо хоткей ще не зберігався
    if not codes:
        if event.key == Keys.KEY_F12 and BigWorld.isKeyDown(Keys.KEY_LALT):
            g_controller.cycle_preset_in_battle()
        return

    # Перевіряємо: останній код — натиснута клавіша, решта — модифікатори
    trigger_key = codes[-1]
    modifiers = codes[:-1]

    if event.key != trigger_key:
        return

    for mod in modifiers:
        if not BigWorld.isKeyDown(mod):
            return

    g_controller.cycle_preset_in_battle()


def _install_key_hook():
    if not IN_GAME:
        return
    try:
        InputHandler.g_instance.onKeyDown += _on_key_event
    except Exception:
        pass


def open_weather_window():
    """Відкриває кастомне вікно через modsSettingsApi buttonHandler."""
    if not IN_GAME:
        return
    try:
        from gui.app_loader import g_appLoader
        from weather_window import WeatherWindowMeta
        app = g_appLoader.getDefLobbyApp()
        if app and hasattr(app, 'containerManager'):
            app.containerManager.load(WeatherWindowMeta())
    except Exception:
        import logging
        logging.getLogger("weather_mod").exception("Failed to open weather window")


def init():
    _install_space_hook()
    _install_key_hook()

    try:
        from gui.modsSettingsApi import g_modsSettingsApi
        from gui.modsSettingsApi import templates as t
        import Keys as K

        # FIX 1: передаємо поточний hotkey_codes з конфігу в modsSettingsApi
        current_codes = g_controller.config.hotkey_codes or [K.KEY_LALT, K.KEY_F12]

        template = {
            "modDisplayName": u"Погода на картах",
            "enabled": True,
            "column1": [
                t.createLabel(text=u"Загальні налаштування для всіх карт"),
                t.createEmpty(),
                t.createSlider(varName="global_standard", text=u"Стандарт",
                               value=g_controller.config.global_weights.get("standard", 20),
                               min=0, max=20, interval=1),
                t.createSlider(varName="global_midnight", text=u"Ніч",
                               value=g_controller.config.global_weights.get("midnight", 0),
                               min=0, max=20, interval=1),
                t.createSlider(varName="global_overcast", text=u"Пасмурно",
                               value=g_controller.config.global_weights.get("overcast", 0),
                               min=0, max=20, interval=1),
                t.createSlider(varName="global_sunset", text=u"Закат",
                               value=g_controller.config.global_weights.get("sunset", 0),
                               min=0, max=20, interval=1),
                t.createSlider(varName="global_midday", text=u"Полдень",
                               value=g_controller.config.global_weights.get("midday", 0),
                               min=0, max=20, interval=1),
                t.createEmpty(),
                # FIX 1: value — список key codes (int), не dict
                t.createHotkey(varName="hotkey", text=u"Смена погоды в бою",
                               value=current_codes),
            ],
            "column2": [
                t.createLabel(text=u"Налаштування по картах"),
                t.createEmpty(),
                t.createDropdown(
                    varName="active_map",
                    text=u"Карта",
                    options=[
                        u"— Оберіть карту —",
                        u"Малинівка", u"Хіммельсдорф",
                        u"Прохорівка", u"Енськ",
                    ],
                    value=0,
                ),
                t.createSlider(varName="map_standard", text=u"[карта] Стандарт",
                               value=0, min=0, max=20, interval=1),
                t.createSlider(varName="map_midnight", text=u"[карта] Ніч",
                               value=0, min=0, max=20, interval=1),
                t.createSlider(varName="map_overcast", text=u"[карта] Пасмурно",
                               value=0, min=0, max=20, interval=1),
                t.createSlider(varName="map_sunset", text=u"[карта] Закат",
                               value=0, min=0, max=20, interval=1),
                t.createSlider(varName="map_midday", text=u"[карта] Полдень",
                               value=0, min=0, max=20, interval=1),
            ],
        }

        saved = g_modsSettingsApi.setModTemplate(
            linkage="com.example.weather",
            template=template,
            callback=_on_settings_changed,
        )
        if saved:
            _apply_saved_settings(saved)

    except Exception:
        import logging
        logging.getLogger("weather_mod").exception("modsSettingsApi registration failed")


MAP_IDS = ["", "02_malinovka", "04_himmelsdorf", "05_prohorovka", "06_ensk"]


def _on_settings_changed(linkage, newSettings):
    import logging
    log = logging.getLogger("weather_mod")
    log.debug("settings changed: %s", newSettings)

    PRESET_ORDER = ["standard", "midnight", "overcast", "sunset", "midday"]

    for pid in PRESET_ORDER:
        key = "global_" + pid
        if key in newSettings:
            g_controller.config.set_global_weight(pid, newSettings[key])

    map_idx = newSettings.get("active_map", 0)
    try:
        active_map = MAP_IDS[int(map_idx)]
    except (IndexError, TypeError, ValueError):
        active_map = ""

    if active_map:
        for pid in PRESET_ORDER:
            key = "map_" + pid
            if key in newSettings:
                g_controller.config.set_map_weight(active_map, pid, newSettings[key])

    # FIX 1: зберігаємо новий хоткей якщо змінився
    if "hotkey" in newSettings:
        raw = newSettings["hotkey"]
        # modsSettingsApi повертає список int-кодів
        if isinstance(raw, (list, tuple)):
            codes = [int(c) for c in raw]
            # будуємо рядок для відображення
            try:
                import Keys as K
                name_map = {K.KEY_LALT: "ALT", K.KEY_RALT: "ALT",
                            K.KEY_LCONTROL: "CTRL", K.KEY_RCONTROL: "CTRL",
                            K.KEY_LSHIFT: "SHIFT", K.KEY_RSHIFT: "SHIFT"}
                parts = [name_map.get(c, "KEY_%d" % c) for c in codes]
                hotkey_str = "+".join(parts)
            except Exception:
                hotkey_str = "+".join(str(c) for c in codes)
            g_controller.on_hotkey_changed(codes, hotkey_str)


def _apply_saved_settings(saved):
    """Застосовуємо збережені налаштування при старті."""
    PRESET_ORDER = ["standard", "midnight", "overcast", "sunset", "midday"]
    for pid in PRESET_ORDER:
        key = "global_" + pid
        if key in saved:
            g_controller.config.global_weights[pid] = int(saved[key])
    if "hotkey" in saved:
        raw = saved["hotkey"]
        if isinstance(raw, (list, tuple)) and raw:
            _on_settings_changed("com.example.weather", {"hotkey": raw})


init()
