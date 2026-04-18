# -*- coding: utf-8 -*-
"""
Точка входу мода. Тут ми:
  1. Хукаємо подію "завантаження простору" (щоб застосувати випадковий пресет)
  2. Реєструємо хоткей ALT+F12 для перемикання в бою
  3. Додаємо пункт у налаштування izeberg.modssettingsapi → відкрити WeatherWindow
"""

try:
    import BigWorld
    import Keys
    from gui import InputHandler
    from gui.app_loader.decorators import sf_lobby
    IN_GAME = True
except ImportError:
    IN_GAME = False

from weather_controller import g_controller


# ===== 1. Реакція на завантаження простору =====
# У реальному моді хукаємо BWPersonality.onSpaceLoaded або ArenaInfoHolder.
# Приклад з monkey-patching:
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
        pass  # fail-silent: мод працює в режимі UI-only, якщо хук не встав


# ===== 2. Глобальний хоткей у бою =====
def _on_key_event(event):
    if not IN_GAME:
        return
    if not event.isKeyDown():
        return
    # ALT + F12 — спрощено; у продакшені треба читати g_controller.config.hotkey
    if event.key == Keys.KEY_F12 and BigWorld.isKeyDown(Keys.KEY_LALT):
        g_controller.cycle_preset_in_battle()


def _install_key_hook():
    if not IN_GAME:
        return
    InputHandler.g_instance.onKeyDown += _on_key_event


# ===== 3. Відкриття вікна з пункту меню =====
def open_weather_window():
    """Викликається кнопкою з меню налаштувань модів."""
    if not IN_GAME:
        print("[DEV] Would open WeatherWindow now")
        return
    from gui.app_loader import g_appLoader
    from weather_window import WeatherWindowMeta
    app = g_appLoader.getDefLobbyApp()
    if app and app.containerManager:
        app.containerManager.load(WeatherWindowMeta())


# ===== Init =====
def init():
    _install_space_hook()
    _install_key_hook()
    # Реєстрація в izeberg.modssettingsapi (якщо встановлено)
    try:
        from gui.modsSettingsApi import g_modsSettingsApi
        g_modsSettingsApi.registerCallback("weather_mod_open", open_weather_window)
    except ImportError:
        pass


# Автозапуск при завантаженні мода
init()
