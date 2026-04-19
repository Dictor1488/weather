# -*- coding: utf-8 -*-
"""
Weather controller v3.2
- summon(DataSection) працює (не падає)
- nextWeatherSystem(fadeSpeed) виправлено
- Чистий код без зайвого логування
"""
import json
import os
import random
import logging
import traceback

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

WEATHER_SYSTEM_LABELS = {
    "Clear":   u"Ясно",
    "Cloudy":  u"Хмарно",
    "Cloudy2": u"Хмарно 2",
    "Cloudy3": u"Хмарно 3",
    "Cloudy4": u"Хмарно 4",
    "Urban":   u"Місто",
    "Stormy":  u"Шторм",
    "Hail":    u"Град",
}

try:
    _prefs = (BigWorld.wg_getPreferencesFilePath()
              if hasattr(BigWorld, 'wg_getPreferencesFilePath')
              else BigWorld.getPreferencesFilePath())
    CONFIG_PATH = os.path.normpath(
        os.path.join(os.path.dirname(_prefs), 'mods', 'weather', 'config.json'))
except Exception:
    CONFIG_PATH = os.path.join("mods", "configs", "weather_mod.json")


class WeatherConfig(object):

    def __init__(self):
        self.global_weights = {pid: (MAX_WEIGHT if pid == "standard" else 0)
                               for pid in PRESET_ORDER}
        self.map_overrides = {}
        self.hotkey_codes = []
        self.hotkey_str = "F12"
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
                logger.info("config loaded from %s", CONFIG_PATH)
        except Exception:
            logger.exception("config load failed")

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
            logger.exception("config save failed")

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
    blocked = ('hangar', 'garage', 'login', 'waiting', 'intro',
               'bootcamp', 'story', 'fun_random_hangar')
    if lowered.startswith(blocked):
        return False
    return '_' in name


def detect_current_battle_space():
    if not IN_GAME:
        return None
    try:
        player = BigWorld.player()
        if player is None:
            return None
        arena = getattr(player, 'arena', None)
        if arena is None:
            return None
        arenaType = getattr(arena, 'arenaType', None)
        if arenaType is None:
            return None
        for attr in ('geometryName', 'geometry', 'name'):
            value = getattr(arenaType, attr, None)
            if value:
                norm = normalize_space_name(value)
                if is_battle_map_space(norm):
                    return norm
    except Exception:
        pass
    return None


def _get_weather():
    """Weather об'єкт ініціалізований для поточного простору."""
    try:
        import Weather
        w = getattr(Weather, 's_weather', None)
        if w is None and hasattr(Weather, 'weather'):
            w = Weather.weather()
        if w is None:
            return None
        player = BigWorld.player()
        space_id = getattr(player, 'spaceID', None) if player else None
        if space_id is not None:
            if getattr(w, 'currentSpaceID', -1) != space_id:
                fn = getattr(w, 'onChangeSpace', None)
                if callable(fn):
                    try:
                        fn(space_id)
                    except Exception:
                        pass
        return w
    except Exception:
        return None


def cycle_weather_system():
    """
    Циклічно перемикає weather system.
    Повертає (success, system_name).

    Стратегія:
    1. nextWeatherSystem(fadeSpeed) — вбудований цикл WoT
    2. summon(DataSection) — пряма передача секції конфігу
    """
    w = _get_weather()
    if w is None:
        return False, None

    # --- Спроба 1: nextWeatherSystem(fadeSpeed) ---
    # Потребує як мінімум 2 аргументи: self + fadeSpeed
    fn_next = getattr(w, 'nextWeatherSystem', None)
    if callable(fn_next):
        for fade in (15.0, 5.0, 1.0, 0.0):
            try:
                fn_next(fade)
                current = getattr(w, 'system', None)
                name = getattr(current, 'name', None) if current else None
                logger.info("OK: nextWeatherSystem(%.1f) -> %s", fade, name)
                return True, name
            except Exception as e:
                err = str(e)
                if 'takes at least' in err or 'argument' in err.lower():
                    continue  # спробуємо інший аргумент
                logger.debug("nextWeatherSystem(%.1f) failed: %s", fade, e)
                break

    # --- Спроба 2: summon(DataSection) ---
    fn_systems = getattr(w, '_weatherSystemsForCurrentSpace', None)
    systems = fn_systems() if callable(fn_systems) else []
    if systems:
        current_idx = getattr(w, '_mod_weather_idx', 0)
        next_idx = (current_idx + 1) % len(systems)
        w._mod_weather_idx = next_idx
        target = systems[next_idx]
        target_name = getattr(target, 'name', str(next_idx))

        fn_summon = getattr(w, 'summon', None)
        if callable(fn_summon):
            try:
                fn_summon(target)
                logger.info("OK: summon(DataSection[%d] '%s')", next_idx, target_name)
                return True, target_name
            except Exception as e:
                logger.warning("summon(DataSection) failed: %s", e)

            # Fallback: summon(name_string)
            try:
                fn_summon(target_name)
                logger.info("OK: summon('%s')", target_name)
                return True, target_name
            except Exception as e:
                logger.debug("summon(name) failed: %s", e)

    return False, None


def apply_environment_preset(space_name, preset_id):
    """Патчимо VFS при вході в бій."""
    guid = PRESET_GUIDS.get(preset_id)
    if not guid or not IN_GAME:
        return
    try:
        section = ResMgr.openSection('spaces/%s/space.settings' % space_name)
        if section is not None:
            section.writeString('environment/override', guid)
            logger.info("env: %s -> %s (guid=%s)", space_name, preset_id, guid)
    except Exception:
        pass


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
        pass

    def on_close_requested(self):
        self.config.save()

    def on_hotkey_changed(self, key_codes, hotkey_str):
        self.config.hotkey_codes = [int(c) for c in key_codes]
        self.config.hotkey_str = hotkey_str
        self.config.save()
        logger.info("Hotkey: %s %s", hotkey_str, key_codes)

    def on_battle_space_entered(self, space_class_name):
        pass

    def on_space_entered(self, space_name):
        normalized = normalize_space_name(space_name)
        if not is_battle_map_space(normalized):
            return
        self._current_space = normalized
        weights = self.config.get_weights_for_map(normalized)
        preset = pick_preset(weights)
        self._current_preset = preset
        logger.info("onEnterWorld: %s -> env=%s", normalized, preset)
        apply_environment_preset(normalized, preset)

    def cycle_weather_in_battle(self):
        """F12: перемикаємо weather system у бою."""
        if not detect_current_battle_space():
            logger.info("cycle_weather: not in battle")
            return

        ok, name = cycle_weather_system()

        try:
            if name:
                label = WEATHER_SYSTEM_LABELS.get(name, name)
                msg = u"Атмосфера: %s" % label
            else:
                msg = u"Атмосфера: перемкнуто"
            if not ok:
                msg = u"Атмосфера: не вдалось"
            SystemMessages.pushI18nMessage(
                msg, type=SystemMessages.SM_TYPE.Information)
        except Exception:
            pass

        logger.info("cycle_weather: name=%s ok=%s", name, ok)


g_controller = WeatherController()
