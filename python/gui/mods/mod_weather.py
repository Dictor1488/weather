# -*- coding: utf-8 -*-
"""
Точка входу мода погоди.

АРХІТЕКТУРА (v2 — через modsSettingsApi від izeberg):
    1. На старті реєструємо мод у g_modsSettingsApi.
    2. Віддаємо API шаблон налаштувань (слайдери + хоткей + дропдаун карт).
    3. API САМ малює нам панель у своєму вікні — AS3 не потрібен.
    4. Коли користувач змінює щось — API шле нам dict зі значеннями
       через callback, який ми перетворюємо на команди для controller.
    5. Контролер зберігає стан і патчить space.settings перед боєм.

ЗАЛЕЖНОСТІ:
    - izeberg.modssettingsapi >= 1.7.0
    - environments_*.wotmod
"""
import logging

try:
    import BigWorld
    import Keys
    from gui.modsSettingsApi import g_modsSettingsApi
    from gui.modsSettingsApi import templates as t
    from gui import InputHandler
    IN_GAME = True
except ImportError:
    IN_GAME = False

from weather_controller import g_controller, PRESET_ORDER, PRESET_LABELS, MAX_WEIGHT

logger = logging.getLogger("weather_mod")

MOD_LINKAGE = "com.example.weather"
MOD_VERSION = "1.0.0"


# ============================================================================
# Побудова шаблону налаштувань
# ============================================================================
def build_settings_template():
    if not IN_GAME:
        return {}

    # === Глобальні слайдери ===
    global_controls = [
        t.createLabel(text=u"Загальні налаштування для всіх карт"),
        t.createEmpty(),
    ]
    for pid in PRESET_ORDER:
        global_controls.append(t.createSlider(
            varName="global_" + pid,
            text=PRESET_LABELS[pid],
            value=g_controller.config.global_weights.get(pid, 0),
            minimum=0,
            maximum=MAX_WEIGHT,
            snapInterval=1,
        ))

    # === Хоткей ===
    global_controls.append(t.createEmpty())
    global_controls.append(t.createHotkey(
        varName="hotkey",
        text=u"Смена погоды в бою",
        value={
            "keyCode": Keys.KEY_F12,
            "isKeyDown": True,
            "hasAlt": True,
            "hasShift": False,
            "hasCtrl": False,
        },
    ))

    template = {
        "modDisplayName": u"Погода на картах",
        "enabled": True,
        "column1": global_controls,
        "column2": _build_maps_column(),
    }
    return template


def _build_maps_column():
    controls = [
        t.createLabel(text=u"Налаштування по картах"),
        t.createEmpty(),
        t.createDropdown(
            varName="active_map",
            text=u"Карта",
            options=[
                {"label": u"— Оберіть карту —", "value": ""},
                {"label": u"Малинівка",    "value": "02_malinovka"},
                {"label": u"Хіммельсдорф", "value": "04_himmelsdorf"},
                {"label": u"Прохорівка",   "value": "05_prohorovka"},
                {"label": u"Енськ",        "value": "06_ensk"},
            ],
            value="",
        ),
    ]
    for pid in PRESET_ORDER:
        controls.append(t.createSlider(
            varName="map_" + pid,
            text=u"[карта] " + PRESET_LABELS[pid],
            value=0,
            minimum=0,
            maximum=MAX_WEIGHT,
            snapInterval=1,
        ))
    return controls


# ============================================================================
# Callback від API
# ============================================================================
def on_settings_changed(linkage, newSettings):
    logger.info("[weather] settings changed: %s", newSettings)

    for pid in PRESET_ORDER:
        key = "global_" + pid
        if key in newSettings:
            g_controller.config.set_global_weight(pid, newSettings[key])

    if "hotkey" in newSettings:
        g_controller.config.hotkey = _hotkey_dict_to_list(newSettings["hotkey"])
        g_controller.config.save()

    active_map = newSettings.get("active_map", "")
    if active_map:
        for pid in PRESET_ORDER:
            key = "map_" + pid
            if key in newSettings:
                g_controller.config.set_map_weight(active_map, pid, newSettings[key])


def _hotkey_dict_to_list(hk):
    out = []
    if hk.get("hasAlt"):   out.append("KEY_LALT")
    if hk.get("hasCtrl"):  out.append("KEY_LCONTROL")
    if hk.get("hasShift"): out.append("KEY_LSHIFT")
    out.append("KEY_%d" % hk.get("keyCode", Keys.KEY_F12 if IN_GAME else 0))
    return out


# ============================================================================
# Хуки у грі
# ============================================================================
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
        logger.info("[weather] space hook installed")
    except Exception as e:
        logger.exception("[weather] failed to install space hook: %s", e)


def _on_key_event(event):
    if not IN_GAME or not event.isKeyDown():
        return
    if event.key == Keys.KEY_F12 and BigWorld.isKeyDown(Keys.KEY_LALT):
        g_controller.cycle_preset_in_battle()


def _install_key_hook():
    if not IN_GAME:
        return
    try:
        InputHandler.g_instance.onKeyDown += _on_key_event
    except Exception as e:
        logger.exception("[weather] failed to install key hook: %s", e)


# ============================================================================
# WoT Mod Loader API — повний набір методів, які викликає personality.py
# ============================================================================
def init():
    """Викликається WoT при завантаженні клієнта."""
    if not IN_GAME:
        logger.info("[weather] dev-mode: skipping in-game hooks")
        return

    try:
        template = build_settings_template()
        saved = g_modsSettingsApi.setModTemplate(
            linkage=MOD_LINKAGE,
            template=template,
            callback=on_settings_changed,
        )
        if saved:
            on_settings_changed(MOD_LINKAGE, saved)
        logger.info("[weather] registered in modsSettingsApi")
    except Exception as e:
        logger.exception("[weather] modsSettingsApi registration failed: %s", e)
        logger.error("[weather] Is izeberg.modssettingsapi installed?")

    _install_space_hook()
    _install_key_hook()


def fini():
    """Викликається WoT при виході з клієнта."""
    if IN_GAME:
        try:
            g_controller.config.save()
        except Exception:
            pass


def sendEvent(*args, **kwargs):
    """
    Стандартний точка WoT mod API: певні event-и від клієнта проходять
    через усі зареєстровані mod_*.py модулі.
    Нам нічого тут оброблювати не потрібно.
    """
    pass


def onHangarSpaceCreate(*args, **kwargs):
    """Ангар створено."""
    pass


def onHangarSpaceDestroy(*args, **kwargs):
    """Ангар знищено."""
    pass
