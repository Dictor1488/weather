# -*- coding: utf-8 -*-
"""
Weather controller v2.2
Ключова знахідка з дампу:
- Weather.currentSpaceID = -1 (не ініціалізований для простору)
- Weather._weatherSystemsForCurrentSpace = <callable> (дасть список доступних систем)
- Weather.onChangeSpace = <callable> (ініціалізує Weather для простору)
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

PRESET_ENV_NAMES = {
    "standard": None,
    "midday":   "03_midday",
    "sunset":   "02_Sunset",
    "overcast": "01_Overcast",
    "midnight": "RexpTM",
}

PRESET_PERIOD_IDS = {
    "standard": 0,
    "midday":   1,
    "sunset":   2,
    "overcast": 3,
    "midnight": 4,
}

PRESET_TOD = {
    "standard": u"12:00",
    "midday":   u"12:00",
    "sunset":   u"18:30",
    "overcast": u"13:00",
    "midnight": u"00:12",
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
_SYSTEMS_DUMPED = False

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


def _fmt_exc():
    try:
        return traceback.format_exc()
    except Exception:
        return ''


def _get_weather():
    """Повертає Weather об'єкт, ініціалізований для поточного простору."""
    try:
        import Weather
        w = getattr(Weather, 's_weather', None)
        if w is None and hasattr(Weather, 'weather'):
            w = Weather.weather()
        if w is None:
            return None

        # Якщо Weather не ініціалізований для поточного простору — ініціалізуємо
        player = BigWorld.player()
        space_id = getattr(player, 'spaceID', None) if player else None

        if space_id is not None:
            current = getattr(w, 'currentSpaceID', -1)
            if current != space_id:
                # Ініціалізуємо Weather для поточного простору
                on_change = getattr(w, 'onChangeSpace', None)
                if callable(on_change):
                    try:
                        on_change(space_id)
                        logger.info("Weather.onChangeSpace(%s) -> currentSpaceID now=%s",
                                    space_id, getattr(w, 'currentSpaceID', '?'))
                    except Exception as e:
                        logger.debug("onChangeSpace failed: %s", e)

        return w
    except Exception:
        return None


def _dump_weather_systems_once(w):
    """Показуємо список доступних weather systems для поточного простору."""
    global _SYSTEMS_DUMPED
    if _SYSTEMS_DUMPED:
        return
    _SYSTEMS_DUMPED = True

    try:
        fn = getattr(w, '_weatherSystemsForCurrentSpace', None)
        if callable(fn):
            systems = fn()
            logger.info("_weatherSystemsForCurrentSpace() = %s", repr(systems)[:500])
            # Якщо повернув список — виведемо імена кожної системи
            if systems:
                for i, s in enumerate(systems):
                    name = getattr(s, 'name', None) or getattr(s, '_name', None)
                    logger.info("  system[%d]: name=%s type=%s repr=%s",
                                i, name, type(s).__name__, repr(s)[:100])
        else:
            logger.info("_weatherSystemsForCurrentSpace not callable")

        # Також перевіримо поточний стан
        logger.info("After onChangeSpace: currentSpaceID=%s system=%s overridenWeather=%s",
                    getattr(w, 'currentSpaceID', '?'),
                    repr(getattr(w, 'system', None))[:100],
                    repr(getattr(w, 'overridenWeather', None))[:100])

        # Пробуємо newSystemByName з різними варіантами після ініціалізації
        for test_name in ('03_midday', '02_Sunset', '01_Overcast', 'RexpTM',
                          'standard', 'default', 'clear', 'day', 'night'):
            fn2 = getattr(w, 'newSystemByName', None)
            if callable(fn2):
                try:
                    result = fn2(test_name)
                    if result is not None:
                        logger.info("newSystemByName(%s) = %s (name=%s)",
                                    test_name, type(result).__name__,
                                    getattr(result, 'name', '?'))
                    else:
                        logger.debug("newSystemByName(%s) = None", test_name)
                except Exception as e:
                    logger.debug("newSystemByName(%s) failed: %s", test_name, e)

    except Exception:
        logger.error("systems dump failed\n%s", _fmt_exc())


def apply_preset_in_battle(preset_id):
    if not IN_GAME:
        return False

    env_name = PRESET_ENV_NAMES.get(preset_id)
    guid = PRESET_GUIDS.get(preset_id, '') or ''
    period = PRESET_PERIOD_IDS.get(preset_id, 0)
    tod = PRESET_TOD.get(preset_id, u'12:00')

    logger.info("apply: preset=%s env=%s period=%s", preset_id, env_name, period)

    # ---- 1. Ініціалізуємо Weather для простору і беремо системи ----
    w = _get_weather()
    if w is not None:
        _dump_weather_systems_once(w)

        # Пробуємо override через систему яку знайде _weatherSystemsForCurrentSpace
        try:
            fn = getattr(w, '_weatherSystemsForCurrentSpace', None)
            if callable(fn):
                systems = fn()
                if systems:
                    # Шукаємо потрібну систему за іменем або беремо першу
                    target = None
                    for s in systems:
                        sname = getattr(s, 'name', None) or getattr(s, '_name', None)
                        if sname and (sname == env_name or sname == guid):
                            target = s
                            break
                    # Якщо не знайшли за іменем — беремо по period ID
                    if target is None and len(systems) > period:
                        target = systems[period]
                    if target is None and systems:
                        target = systems[0]

                    if target is not None:
                        override_fn = getattr(w, 'override', None)
                        if callable(override_fn):
                            try:
                                override_fn(target)
                                logger.info("OK: Weather.override(system=%s)",
                                            getattr(target, 'name', repr(target)[:50]))
                            except Exception as e:
                                logger.warning("FAIL: Weather.override(system): %s", e)
        except Exception:
            logger.debug("systems override failed\n%s", _fmt_exc())

        # Спробуємо summon зі списку доступних систем за іменем
        summon_fn = getattr(w, 'summon', None)
        if callable(summon_fn) and env_name:
            try:
                fn = getattr(w, '_weatherSystemsForCurrentSpace', None)
                systems = fn() if callable(fn) else []
                for s in (systems or []):
                    sname = getattr(s, 'name', None)
                    if sname == env_name:
                        summon_fn(s)
                        logger.info("OK: Weather.summon(system %s)", env_name)
                        break
            except Exception as e:
                logger.debug("summon by system failed: %s", e)

    # ---- 2. player period sync ----
    try:
        player = BigWorld.player()
        if player:
            setattr(player, 'weatherPresetID', period)
            setattr(player, '_PlayerAvatar__blArenaPeriod', period)
            apply_fn = getattr(player, '_PlayerAvatar__applyTimeAndWeatherSettings', None)
            if callable(apply_fn):
                try:
                    apply_fn(period)
                    logger.info("OK: player.apply(period=%s)", period)
                except Exception:
                    pass
    except Exception:
        pass

    # ---- 3. час доби ----
    try:
        fn = getattr(BigWorld, 'timeOfDay', None)
        if callable(fn):
            fn(tod)
        player = BigWorld.player()
        fn2 = getattr(BigWorld, 'spaceTimeOfDay', None)
        sid = getattr(player, 'spaceID', None) if player else None
        if callable(fn2) and sid:
            fn2(sid, tod)
    except Exception:
        pass

    return True


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

    def on_space_about_to_load(self, space_name):
        normalized = normalize_space_name(space_name)
        if not is_battle_map_space(normalized):
            return None
        self._current_space = normalized
        weights = self.config.get_weights_for_map(normalized)
        preset = pick_preset(weights)
        self._current_preset = preset
        return preset

    def cycle_preset_in_battle(self):
        detected = detect_current_battle_space()
        if not detected:
            logger.info("cycle: not in battle")
            return
        self._current_space = detected

        try:
            prev = self._current_preset or 'standard'
            idx = PRESET_ORDER.index(prev)
        except ValueError:
            prev, idx = 'standard', 0

        next_preset = PRESET_ORDER[(idx + 1) % len(PRESET_ORDER)]
        self._current_preset = next_preset

        logger.info("cycle: %s -> %s on %s", prev, next_preset, self._current_space)
        apply_preset_in_battle(next_preset)

        try:
            SystemMessages.pushI18nMessage(
                u"Погода: %s" % PRESET_LABELS[next_preset],
                type=SystemMessages.SM_TYPE.Information,
            )
        except Exception:
            pass


g_controller = WeatherController()
