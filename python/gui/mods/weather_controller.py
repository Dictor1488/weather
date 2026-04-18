# -*- coding: utf-8 -*-
"""
Weather Mods Controller — керування погодними пресетами в World of Tanks.
"""

import json
import os
import random
import logging

try:
    import BigWorld
    import ResMgr
    from gui import SystemMessages
    from Keys import KEY_F12, KEY_LALT
    IN_GAME = True
except ImportError:
    IN_GAME = False

logger = logging.getLogger("weather_mod")
logger.setLevel(logging.INFO)


# ============================================================================
# GUID'и пресетів із .wotmod файлів
# ============================================================================
PRESET_GUIDS = {
    "standard": None,
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

CONFIG_PATH = os.path.join("mods", "configs", "weather_mod.json")


# ============================================================================
# MODEL
# ============================================================================
class WeatherConfig(object):

    def __init__(self):
        self.global_weights = {pid: MAX_WEIGHT if pid == "standard" else 0
                               for pid in PRESET_ORDER}
        self.map_overrides = {}
        self.hotkey = ["KEY_LALT", "KEY_F12"]
        self.load()

    def load(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r") as f:
                    data = json.load(f)
                self.global_weights.update(data.get("global", {}))
                self.map_overrides = data.get("maps", {})
                self.hotkey = data.get("hotkey", self.hotkey)
                logger.info("Weather config loaded from %s", CONFIG_PATH)
        except Exception as e:
            logger.exception("Failed to load weather config: %s", e)

    def save(self):
        try:
            if not os.path.exists(os.path.dirname(CONFIG_PATH)):
                os.makedirs(os.path.dirname(CONFIG_PATH))
            data = {
                "global": self.global_weights,
                "maps": self.map_overrides,
                "hotkey": self.hotkey,
            }
            with open(CONFIG_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.exception("Failed to save weather config: %s", e)

    def set_global_weight(self, preset_id, value):
        if preset_id in PRESET_ORDER:
            self.global_weights[preset_id] = max(0, min(MAX_WEIGHT, int(value)))
            self.save()

    def set_map_weight(self, map_id, preset_id, value):
        if preset_id not in PRESET_ORDER:
            return
        entry = self.map_overrides.setdefault(map_id, {
            "useGlobal": False,
            "weights": {pid: 0 for pid in PRESET_ORDER},
        })
        entry["useGlobal"] = False
        entry["weights"][preset_id] = max(0, min(MAX_WEIGHT, int(value)))
        self.save()

    def get_weights_for_map(self, map_id):
        override = self.map_overrides.get(map_id)
        if override and not override.get("useGlobal", True):
            return override["weights"]
        return self.global_weights


# ============================================================================
# RANDOMIZER
# ============================================================================
def pick_preset(weights):
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
# ENVIRONMENT PATCHER
# ============================================================================
def apply_preset_to_space(space_name, preset_id):
    guid = PRESET_GUIDS.get(preset_id)
    if guid is None:
        logger.info("[%s] Standard preset — no override", space_name)
        return

    if not IN_GAME:
        logger.info("[DEV] Would apply %s (guid=%s) to %s", preset_id, guid, space_name)
        return

    try:
        path = "spaces/%s/space.settings" % space_name
        section = ResMgr.openSection(path)
        if section is None:
            logger.warning("space.settings not found for %s", space_name)
            return
        section.writeString("environment/override", guid)
        section.save()
        logger.info("[%s] Applied preset %s (guid=%s)", space_name, preset_id, guid)
    except Exception as e:
        logger.exception("Failed to patch space.settings: %s", e)


# ============================================================================
# CONTROLLER
# ============================================================================
class WeatherController(object):

    def __init__(self):
        self.config = WeatherConfig()
        self._current_space = None
        self._current_preset = None

    def on_weight_changed(self, map_id, preset_id, value):
        logger.info("weight_changed: map=%s preset=%s value=%s", map_id, preset_id, value)
        if map_id is None:
            self.config.set_global_weight(preset_id, value)
        else:
            self.config.set_map_weight(map_id, preset_id, value)

    def on_map_selected(self, map_id):
        logger.info("map_selected: %s", map_id)

    def on_close_requested(self):
        logger.info("user closed weather panel")
        self.config.save()

    def build_payload(self, available_maps):
        def presets_for(weights, previews=None):
            previews = previews or {}
            return [{
                "id": pid,
                "label": PRESET_LABELS[pid],
                "guid": PRESET_GUIDS[pid],
                "weight": weights.get(pid, 0),
                "previewSrc": previews.get(pid, ""),
            } for pid in PRESET_ORDER]

        maps_payload = []
        for map_id, label, thumb in available_maps:
            override = self.config.map_overrides.get(map_id, {})
            weights = override.get("weights", {pid: 0 for pid in PRESET_ORDER})
            maps_payload.append({
                "id": map_id,
                "label": label,
                "thumbSrc": thumb,
                "useGlobal": override.get("useGlobal", True),
                "presets": presets_for(weights),
            })

        return {
            "presets": presets_for(self.config.global_weights),
            "maps": maps_payload,
            "hotkey": "+".join(k.replace("KEY_", "").replace("L", "") for k in self.config.hotkey),
        }

    def on_space_about_to_load(self, space_name):
        self._current_space = space_name
        weights = self.config.get_weights_for_map(space_name)
        preset = pick_preset(weights)
        self._current_preset = preset
        apply_preset_to_space(space_name, preset)
        return preset

    def cycle_preset_in_battle(self):
        if not self._current_space:
            return
        try:
            idx = PRESET_ORDER.index(self._current_preset or "standard")
        except ValueError:
            idx = 0
        next_preset = PRESET_ORDER[(idx + 1) % len(PRESET_ORDER)]
        self._current_preset = next_preset
        apply_preset_to_space(self._current_space, next_preset)
        if IN_GAME:
            SystemMessages.pushI18nMessage(
                "Погода: %s" % PRESET_LABELS[next_preset],
                type=SystemMessages.SM_TYPE.Information,
            )


# Синглтон
g_controller = WeatherController()


# ============================================================================
# WoT Mod Loader API — повний набір заглушок.
# WoT перебирає усі .py у gui/mods/ і викликає у кожному ці функції.
# Без цих stub-ів клієнт падає з AttributeError ще на старті.
# ============================================================================
def init():
    pass


def fini():
    pass


def sendEvent(*args, **kwargs):
    pass


def onHangarSpaceCreate(*args, **kwargs):
    pass


def onHangarSpaceDestroy(*args, **kwargs):
    pass
