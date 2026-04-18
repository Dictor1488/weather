# -*- coding: utf-8 -*-
"""
Weather controller.
v1.2.0 — кілька fallback-стратегій для перемикання погоди в бою
"""
import json
import os
import random
import logging

try:
    import BigWorld
    import ResMgr
    from gui import SystemMessages
    IN_GAME = True
except ImportError:
    IN_GAME = False

logger = logging.getLogger("weather_mod")
logger.setLevel(logging.INFO)

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

try:
    _prefs = BigWorld.wg_getPreferencesFilePath() if hasattr(BigWorld, 'wg_getPreferencesFilePath') else BigWorld.getPreferencesFilePath()
    CONFIG_PATH = os.path.normpath(os.path.join(os.path.dirname(_prefs), 'mods', 'weather', 'config.json'))
except Exception:
    CONFIG_PATH = os.path.join("mods", "configs", "weather_mod.json")


class WeatherConfig(object):

    def __init__(self):
        self.global_weights = {pid: MAX_WEIGHT if pid == "standard" else 0 for pid in PRESET_ORDER}
        self.map_overrides = {}
        self.hotkey_codes = []
        self.hotkey_str = "ALT+F12"
        self.load()

    def load(self):
        try:
            if os.path.isfile(CONFIG_PATH):
                with open(CONFIG_PATH, 'r') as f:
                    data = json.load(f)
                self.global_weights.update(data.get('global', {}))
                self.map_overrides = data.get('maps', {})
                saved_codes = data.get('hotkey_codes', [])
                if saved_codes:
                    self.hotkey_codes = [int(c) for c in saved_codes]
                    self.hotkey_str = data.get('hotkey_str', self.hotkey_str)
                logger.info("Weather config loaded from %s", CONFIG_PATH)
        except Exception:
            logger.exception("Failed to load weather config")

    def save(self):
        try:
            d = os.path.dirname(CONFIG_PATH)
            if not os.path.isdir(d):
                os.makedirs(d)
            with open(CONFIG_PATH, 'w') as f:
                json.dump({
                    'global': self.global_weights,
                    'maps': self.map_overrides,
                    'hotkey_codes': self.hotkey_codes,
                    'hotkey_str': self.hotkey_str,
                }, f, indent=2)
        except Exception:
            logger.exception("Failed to save weather config")

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


def normalize_space_name(space_name):
    if not space_name:
        return ''
    if not isinstance(space_name, basestring):
        space_name = str(space_name)
    space_name = space_name.replace('\\', '/').strip()
    if space_name.startswith('spaces/'):
        space_name = space_name[len('spaces/'):]
    if space_name.endswith('/space.settings'):
        space_name = space_name[:-len('/space.settings')]
    return space_name.strip('/')


def is_battle_map_space(space_name):
    name = normalize_space_name(space_name)
    if not name:
        return False
    lowered = name.lower()
    blocked_prefixes = ('hangar', 'garage', 'login', 'waiting', 'intro', 'bootcamp', 'story', 'fun_random_hangar')
    if lowered.startswith(blocked_prefixes):
        return False
    return '_' in name


def apply_preset_to_space(space_name, preset_id):
    """Патчимо space.settings перед завантаженням карти (працює для нових карт)."""
    guid = PRESET_GUIDS.get(preset_id)
    if guid is None:
        logger.info("[%s] Standard preset — no override", space_name)
        return
    if not IN_GAME:
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
    except Exception:
        logger.exception("Failed to patch space.settings")


# ============================================================================
# ПЕРЕМИКАННЯ ПОГОДИ В БОЮ — fallback-стратегії
# ============================================================================
# WoT 2.2 не має публічного API для зміни environment у бою.
# Пробуємо кілька відомих механізмів по черзі, беремо той, який спрацює.
def apply_preset_in_battle(preset_id):
    """
    Пробуємо по черзі кілька способів змінити погоду в бою.
    Повертає True якщо хоча б один спрацював.
    """
    if not IN_GAME:
        return False

    guid = PRESET_GUIDS.get(preset_id, "")
    if guid is None:
        guid = ""

    # --- Спроба 1: Watcher "Client Settings/environmentOverride" ---
    try:
        BigWorld.setWatcher("Client Settings/environmentOverride", guid)
        logger.info("apply_preset_in_battle: used Watcher 'Client Settings/environmentOverride'")
        return True
    except Exception as e:
        logger.debug("Watcher 'Client Settings/environmentOverride' failed: %s", e)

    # --- Спроба 2: Watcher "Render/environmentOverride" ---
    try:
        BigWorld.setWatcher("Render/environmentOverride", guid)
        logger.info("apply_preset_in_battle: used Watcher 'Render/environmentOverride'")
        return True
    except Exception as e:
        logger.debug("Watcher 'Render/environmentOverride' failed: %s", e)

    # --- Спроба 3: BWPersonality.reloadEnvironment (якщо існує) ---
    try:
        import BWPersonality
        if hasattr(BWPersonality, 'reloadEnvironment'):
            BWPersonality.reloadEnvironment(guid)
            logger.info("apply_preset_in_battle: used BWPersonality.reloadEnvironment")
            return True
    except Exception as e:
        logger.debug("BWPersonality.reloadEnvironment failed: %s", e)

    # --- Спроба 4: Arena.environmentType ---
    try:
        if hasattr(BigWorld, 'player'):
            player = BigWorld.player()
            arena = getattr(player, 'arena', None)
            if arena and hasattr(arena, 'setEnvironmentOverride'):
                arena.setEnvironmentOverride(guid)
                logger.info("apply_preset_in_battle: used arena.setEnvironmentOverride")
                return True
    except Exception as e:
        logger.debug("arena.setEnvironmentOverride failed: %s", e)

    # --- Якщо нічого не спрацювало — дампаємо доступні watcher'и для дебагу ---
    try:
        logger.warning("apply_preset_in_battle: NO method worked for preset=%s", preset_id)
        # Показуємо в логах що є доступне
        try:
            watchers = BigWorld.getWatcher("Render/")
            logger.info("Available Render/ watchers: %s", watchers)
        except Exception:
            pass
        try:
            watchers = BigWorld.getWatcher("Client Settings/")
            logger.info("Available Client Settings/ watchers: %s", watchers)
        except Exception:
            pass
    except Exception:
        pass

    return False


class WeatherController(object):

    def __init__(self):
        self.config = WeatherConfig()
        self._current_space = None
        self._current_preset = None

    def on_weight_changed(self, map_id, preset_id, value):
        if not map_id:
            self.config.set_global_weight(preset_id, value)
        else:
            self.config.set_map_weight(map_id, preset_id, value)

    def on_map_selected(self, map_id):
        logger.info("map_selected: %s", map_id)

    def on_close_requested(self):
        self.config.save()

    def on_hotkey_changed(self, key_codes, hotkey_str):
        self.config.hotkey_codes = [int(c) for c in key_codes]
        self.config.hotkey_str = hotkey_str
        self.config.save()
        logger.info("Hotkey updated: %s codes=%s", hotkey_str, key_codes)

    def on_space_about_to_load(self, space_name):
        normalized = normalize_space_name(space_name)
        logger.info("Space about to load: raw=%s normalized=%s", space_name, normalized)
        if not is_battle_map_space(normalized):
            logger.info("Skipping non-battle space: %s", normalized or space_name)
            return None
        self._current_space = normalized
        weights = self.config.get_weights_for_map(normalized)
        preset = pick_preset(weights)
        self._current_preset = preset
        apply_preset_to_space(normalized, preset)
        return preset

    def cycle_preset_in_battle(self):
        """
        ALT+F12 у бою — перемикаємо пресет.
        Якщо ми НЕ в бою (_current_space порожній), просто нічого не робимо.
        """
        if not self._current_space:
            logger.info("cycle_preset: not in battle, ignoring")
            return

        try:
            idx = PRESET_ORDER.index(self._current_preset or "standard")
        except ValueError:
            idx = 0
        next_preset = PRESET_ORDER[(idx + 1) % len(PRESET_ORDER)]
        self._current_preset = next_preset

        ok = apply_preset_in_battle(next_preset)

        if IN_GAME:
            try:
                msg = u"Погода: %s" % PRESET_LABELS[next_preset]
                if not ok:
                    msg += u" (не вдалося застосувати — дивись python.log)"
                SystemMessages.pushI18nMessage(
                    msg,
                    type=SystemMessages.SM_TYPE.Information,
                )
            except Exception:
                pass
        logger.info("Cycled to preset: %s (applied=%s)", next_preset, ok)


g_controller = WeatherController()
