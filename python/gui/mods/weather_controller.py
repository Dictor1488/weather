# -*- coding: utf-8 -*-
"""
Weather Panel — панель керування погодними пресетами для World of Tanks.

Все в одному файлі у стилі MAsters / ProTanki:
 - WoT виконує лише файли gui/mods/mod_*.py, інших модулів він сам не імпортує
 - Жодних додаткових файлів типу __init__.py чи допоміжних модулів
 - Експортуємо дві точки входу: init() і fini()

ЗАЛЕЖНОСТІ:
 - izeberg.modssettingsapi >= 1.7.0  (для панелі налаштувань)
 - environments_*.wotmod              (для самих пресетів погоди)
"""
import json
import logging
import os
import random

import BigWorld
import Keys
import ResMgr
from gui import SystemMessages, InputHandler
from gui.modsSettingsApi import g_modsSettingsApi
from gui.modsSettingsApi import templates as t

logger = logging.getLogger("weather_mod")
logger.setLevel(logging.DEBUG if os.path.isfile('.debug_mods') else logging.INFO)

__version__ = '1.0.0'


# ============================================================================
# КОНСТАНТИ
# ============================================================================
MOD_LINKAGE = "com.example.weather"

# GUID'и пресетів, витягнуті з environments_*.wotmod
PRESET_GUIDS = {
    "standard": None,  # None = не перезаписувати, використати оригінал гри
    "midday":   "BF040BCB-4BE1D04F-7D484589-135E881B",
    "sunset":   "6DEE1EBB-44F63FCC-AACF6185-7FBBC34E",
    "overcast": "56BA3213-40FFB1DF-125FBCAD-173E8347",
    "midnight": "15755E11-4090266B-594778B6-B233C12C",
}

PRESET_LABELS = {
    "standard": u"Стандарт",
    "midnight": u"Ніч",
    "overcast": u"Пасмурно",
    "sunset":   u"Закат",
    "midday":   u"Полдень",
}

PRESET_ORDER = ["standard", "midnight", "overcast", "sunset", "midday"]
MAX_WEIGHT = 20

# Шлях для збереження конфігу користувача
try:
    _prefsFilePath = BigWorld.wg_getPreferencesFilePath()
except AttributeError:
    _prefsFilePath = BigWorld.getPreferencesFilePath()

_CONFIG_DIR = os.path.normpath(os.path.join(os.path.dirname(_prefsFilePath), 'mods', 'weather'))
_CONFIG_FILE = os.path.join(_CONFIG_DIR, 'config.json')


# ============================================================================
# CONFIG
# ============================================================================
class WeatherConfig(object):

    def __init__(self):
        self.global_weights = {pid: (MAX_WEIGHT if pid == "standard" else 0)
                               for pid in PRESET_ORDER}
        self.map_overrides = {}
        self.load()

    def load(self):
        try:
            if os.path.isfile(_CONFIG_FILE):
                with open(_CONFIG_FILE, 'r') as fh:
                    data = json.load(fh)
                self.global_weights.update(data.get('global', {}))
                self.map_overrides = data.get('maps', {})
                logger.debug('config loaded from %s', _CONFIG_FILE)
        except Exception:
            logger.exception('config load failed')

    def save(self):
        try:
            if not os.path.isdir(_CONFIG_DIR):
                os.makedirs(_CONFIG_DIR)
            with open(_CONFIG_FILE, 'w') as fh:
                json.dump({
                    'global': self.global_weights,
                    'maps':   self.map_overrides,
                }, fh, indent=2)
        except Exception:
            logger.exception('config save failed')


# ============================================================================
# RANDOMIZER
# ============================================================================
def pick_preset(weights):
    """Зважений випадковий вибір пресета (roulette wheel)."""
    total = sum(weights.values())
    if total <= 0:
        return "standard"
    roll = random.uniform(0, total)
    cursor = 0
    for pid in PRESET_ORDER:
        cursor += weights.get(pid, 0)
        if roll <= cursor:
            return pid
    return "standard"


# ============================================================================
# APPLY PRESET TO SPACE (патч space.settings перед завантаженням карти)
# ============================================================================
def apply_preset_to_space(space_name, preset_id):
    guid = PRESET_GUIDS.get(preset_id)
    if guid is None:
        logger.debug('[%s] standard preset — no override', space_name)
        return
    try:
        path = "spaces/%s/space.settings" % space_name
        section = ResMgr.openSection(path)
        if section is None:
            logger.warning('space.settings not found for %s', space_name)
            return
        section.writeString("environment/override", guid)
        section.save()
        logger.info('[%s] applied preset %s (guid=%s)', space_name, preset_id, guid)
    except Exception:
        logger.exception('apply preset failed')


# ============================================================================
# CONTROLLER (синглтон)
# ============================================================================
class WeatherController(object):

    def __init__(self):
        self.config = WeatherConfig()
        self._current_space = None
        self._current_preset = None

    def on_space_about_to_load(self, space_name):
        self._current_space = space_name
        weights = self._weights_for_map(space_name)
        preset = pick_preset(weights)
        self._current_preset = preset
        apply_preset_to_space(space_name, preset)
        return preset

    def _weights_for_map(self, map_id):
        override = self.config.map_overrides.get(map_id)
        if override and not override.get("useGlobal", True):
            return override["weights"]
        return self.config.global_weights

    def cycle_preset_in_battle(self):
        """Викликається по хоткею ALT+F12 — перемикає пресет на наступний."""
        if not self._current_space:
            return
        try:
            idx = PRESET_ORDER.index(self._current_preset or "standard")
        except ValueError:
            idx = 0
        nxt = PRESET_ORDER[(idx + 1) % len(PRESET_ORDER)]
        self._current_preset = nxt
        apply_preset_to_space(self._current_space, nxt)
        try:
            SystemMessages.pushI18nMessage(
                u"Погода: %s" % PRESET_LABELS[nxt],
                type=SystemMessages.SM_TYPE.Information,
            )
        except Exception:
            logger.exception('SystemMessages failed')

    def set_global_weight(self, preset_id, value):
        if preset_id in PRESET_ORDER:
            self.config.global_weights[preset_id] = max(0, min(MAX_WEIGHT, int(value)))
            self.config.save()

    def set_map_weight(self, map_id, preset_id, value):
        if preset_id not in PRESET_ORDER:
            return
        entry = self.config.map_overrides.setdefault(map_id, {
            "useGlobal": False,
            "weights":   {pid: 0 for pid in PRESET_ORDER},
        })
        entry["useGlobal"] = False
        entry["weights"][preset_id] = max(0, min(MAX_WEIGHT, int(value)))
        self.config.save()


_g_ctrl = WeatherController()


# ============================================================================
# ШАБЛОН НАЛАШТУВАНЬ ДЛЯ modsSettingsApi
# ============================================================================
def _build_template():
    # Колонка 1 — глобальні налаштування
    col1 = [
        t.createLabel(text=u"Загальні налаштування для всіх карт"),
        t.createEmpty(),
    ]
    for pid in PRESET_ORDER:
        col1.append(t.createSlider(
            varName="global_" + pid,
            text=PRESET_LABELS[pid],
            value=_g_ctrl.config.global_weights.get(pid, 0),
            minimum=0,
            maximum=MAX_WEIGHT,
            snapInterval=1,
        ))

    col1.append(t.createEmpty())
    col1.append(t.createHotkey(
        varName="hotkey",
        text=u"Смена погоды в бою",
        value={
            "keyCode":   Keys.KEY_F12,
            "isKeyDown": True,
            "hasAlt":    True,
            "hasShift":  False,
            "hasCtrl":   False,
        },
    ))

    # Колонка 2 — налаштування по картах
    col2 = [
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
        col2.append(t.createSlider(
            varName="map_" + pid,
            text=u"[карта] " + PRESET_LABELS[pid],
            value=0,
            minimum=0,
            maximum=MAX_WEIGHT,
            snapInterval=1,
        ))

    return {
        "modDisplayName": u"Погода на картах",
        "enabled":        True,
        "column1":        col1,
        "column2":        col2,
    }


def _on_settings_changed(linkage, newSettings):
    """Викликається modsSettingsApi при зміні слайдера/дропдауна."""
    logger.debug('settings changed: %s', newSettings)
    for pid in PRESET_ORDER:
        key = "global_" + pid
        if key in newSettings:
            _g_ctrl.set_global_weight(pid, newSettings[key])

    active_map = newSettings.get("active_map", "")
    if active_map:
        for pid in PRESET_ORDER:
            key = "map_" + pid
            if key in newSettings:
                _g_ctrl.set_map_weight(active_map, pid, newSettings[key])


# ============================================================================
# ХУКИ ГРИ
# ============================================================================
def _install_space_hook():
    try:
        import BWPersonality
        original = BWPersonality.onSpaceLoaded

        def wrapped(spaceName):
            _g_ctrl.on_space_about_to_load(spaceName)
            return original(spaceName)

        BWPersonality.onSpaceLoaded = wrapped
        logger.info('space hook installed')
    except Exception:
        logger.exception('space hook install failed')


def _on_key_event(event):
    if not event.isKeyDown():
        return
    if event.key == Keys.KEY_F12 and BigWorld.isKeyDown(Keys.KEY_LALT):
        _g_ctrl.cycle_preset_in_battle()


def _install_key_hook():
    try:
        InputHandler.g_instance.onKeyDown += _on_key_event
        logger.info('key hook installed')
    except Exception:
        logger.exception('key hook install failed')


# ============================================================================
# WoT MOD LOADER — точки входу, які викликає personality.py
# ============================================================================
def init():
    try:
        logger.info('initializing weather mod v%s', __version__)

        g_modsSettingsApi.setModTemplate(
            linkage=MOD_LINKAGE,
            template=_build_template(),
            callback=_on_settings_changed,
        )
        logger.info('registered in modsSettingsApi')

        _install_space_hook()
        _install_key_hook()

        logger.info('weather mod initialized')
    except Exception:
        logger.exception('init failed')


def fini():
    try:
        _g_ctrl.config.save()
        logger.info('weather mod finalized')
    except Exception:
        logger.exception('fini failed')
