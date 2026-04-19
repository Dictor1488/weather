# -*- coding: utf-8 -*-
"""
Weather controller.
v2.1.0 — дамп Weather об'єкта + пошук setEnvironmentPreset
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
_DUMP_DONE = False

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


def _dump_weather_object_once():
    """
    Один раз дампаємо повний список атрибутів Weather об'єкта
    та BigWorld щоб знайти правильний метод для перемикання environment.
    """
    global _DUMP_DONE
    if _DUMP_DONE:
        return
    _DUMP_DONE = True

    logger.info("===== WEATHER DUMP START =====")
    try:
        import Weather
        w = getattr(Weather, 's_weather', None)
        if w is None and hasattr(Weather, 'weather'):
            w = Weather.weather()

        if w is not None:
            # Всі атрибути Weather об'єкта
            all_attrs = [a for a in dir(w) if not a.startswith('__')]
            logger.info("Weather attrs: %s", all_attrs)

            # Атрибути що можуть бути списком систем/пресетів
            for attr in all_attrs:
                try:
                    val = getattr(w, attr)
                    if isinstance(val, (list, tuple, dict)) and len(val) > 0:
                        logger.info("Weather.%s = %s", attr, repr(val)[:300])
                    elif callable(val):
                        logger.info("Weather.%s = <callable>", attr)
                    else:
                        logger.info("Weather.%s = %s", attr, repr(val)[:100])
                except Exception as e:
                    logger.info("Weather.%s -> access error: %s", attr, e)
        else:
            logger.warning("No Weather object!")
    except Exception:
        logger.error("Weather dump failed\n%s", _fmt_exc())

    # BigWorld методи для environment
    try:
        bw_env_methods = []
        for attr in dir(BigWorld):
            if any(kw in attr.lower() for kw in
                   ('environment', 'environ', 'preset', 'space', 'reload')):
                val = getattr(BigWorld, attr, None)
                if callable(val):
                    bw_env_methods.append(attr)
        logger.info("BigWorld env methods: %s", bw_env_methods)

        # Спробуємо setEnvironmentPreset і схожі
        player = BigWorld.player()
        space_id = getattr(player, 'spaceID', None) if player else None
        logger.info("player.spaceID=%s", space_id)

        # Дамп weather systems із самого об'єкта
        import Weather
        w = Weather.weather()
        if w:
            # Пробуємо знайти метод що повертає список доступних пресетів
            for method in ('getEnvironments', 'environments', 'getPresets',
                           'presets', 'systems', 'getSystems', 'getWeathers',
                           'currentEnvironment', 'getCurrentEnvironment',
                           'overridenWeather', 'weatherController'):
                if hasattr(w, method):
                    try:
                        val = getattr(w, method)
                        if callable(val):
                            result = val()
                            logger.info("Weather.%s() = %s", method, repr(result)[:300])
                        else:
                            logger.info("Weather.%s = %s", method, repr(val)[:300])
                    except Exception as e:
                        logger.info("Weather.%s -> %s", method, e)

    except Exception:
        logger.error("BigWorld dump failed\n%s", _fmt_exc())

    logger.info("===== WEATHER DUMP END =====")


def apply_preset_in_battle(preset_id):
    if not IN_GAME:
        return False

    _dump_weather_object_once()

    env_name = PRESET_ENV_NAMES.get(preset_id)
    guid = PRESET_GUIDS.get(preset_id, '') or ''
    period = PRESET_PERIOD_IDS.get(preset_id, 0)
    tod = PRESET_TOD.get(preset_id, u'12:00')

    logger.info("apply: preset=%s env_name=%s period=%s", preset_id, env_name, period)

    # Крок 1: BigWorld.setEnvironmentPreset якщо є
    try:
        player = BigWorld.player()
        space_id = getattr(player, 'spaceID', None) if player else None

        for method_name in ('setEnvironmentPreset', 'setSpaceEnvironment',
                            'setCurrentEnvironment', 'reloadEnvironment',
                            'setEnvironment'):
            fn = getattr(BigWorld, method_name, None)
            if fn and callable(fn):
                try:
                    if space_id is not None:
                        fn(space_id, guid)
                        logger.info("OK: BigWorld.%s(%s, %s)", method_name, space_id, guid)
                    else:
                        fn(guid)
                        logger.info("OK: BigWorld.%s(%s)", method_name, guid)
                except Exception as e:
                    logger.debug("FAIL: BigWorld.%s: %s", method_name, e)
    except Exception:
        pass

    # Крок 2: Weather.overridenWeather — встановити override environment
    try:
        import Weather
        w = Weather.weather()
        if w and guid:
            # Пробуємо через overridenWeather property
            ow = getattr(w, 'overridenWeather', None)
            logger.info("Weather.overridenWeather = %s", repr(ow)[:100])

            # Пробуємо newSystemByName з guid як іменем
            if hasattr(w, 'newSystemByName'):
                try:
                    sys = w.newSystemByName(guid)
                    logger.info("Weather.newSystemByName(%s) = %s", guid, repr(sys)[:100])
                    if sys and hasattr(w, 'override'):
                        w.override(sys)
                        logger.info("OK: Weather.override(system from newSystemByName)")
                except Exception as e:
                    logger.debug("newSystemByName failed: %s", e)

            if hasattr(w, 'newSystemByName') and env_name:
                try:
                    sys = w.newSystemByName(env_name)
                    logger.info("Weather.newSystemByName(%s) = %s", env_name, repr(sys)[:100])
                    if sys and hasattr(w, 'override'):
                        w.override(sys)
                        logger.info("OK: Weather.override(system from env_name)")
                except Exception as e:
                    logger.debug("newSystemByName(env_name) failed: %s", e)

    except Exception:
        logger.debug("Weather block 2 failed\n%s", _fmt_exc())

    # Крок 3: player period sync (завжди робимо)
    try:
        player = BigWorld.player()
        if player is not None:
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

    # Крок 4: час доби
    try:
        fn = getattr(BigWorld, 'timeOfDay', None)
        if callable(fn):
            fn(tod)
        player = BigWorld.player()
        fn2 = getattr(BigWorld, 'spaceTimeOfDay', None)
        space_id = getattr(player, 'spaceID', None) if player else None
        if callable(fn2) and space_id:
            fn2(space_id, tod)
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
        logger.info("Hotkey updated: %s codes=%s", hotkey_str, key_codes)

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
            logger.info("cycle_preset: not in battle")
            return
        self._current_space = detected

        try:
            prev = self._current_preset or 'standard'
            idx = PRESET_ORDER.index(prev)
        except ValueError:
            prev = 'standard'
            idx = 0
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
