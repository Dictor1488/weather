# -*- coding: utf-8 -*-
"""
Weather controller.
v2.0.0 — використовуємо правильні імена environment для Weather.override()
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

# GUID'и папок з environments_*.wotmod
PRESET_GUIDS = {
    "standard": None,
    "midday":   "BF040BCB-4BE1D04F-7D484589-135E881B",
    "sunset":   "6DEE1EBB-44F63FCC-AACF6185-7FBBC34E",
    "overcast": "56BA3213-40FFB1DF-125FBCAD-173E8347",
    "midnight": "15755E11-4090266B-594778B6-B233C12C",
}

# Імена з тегу <name> в environment.xml — потрібні для Weather.override()
# Взяті безпосередньо з environment.xml кожного пресету (поле <n>)
PRESET_ENV_NAMES = {
    "standard": None,        # стандарт — скидаємо override
    "midday":   "03_midday",
    "sunset":   "02_Sunset",
    "overcast": "01_Overcast",
    "midnight": "RexpTM",    # так виглядає в midnight/environment.xml <n> тег
}

# Period IDs для player.__applyTimeAndWeatherSettings
PRESET_PERIOD_IDS = {
    "standard": 0,
    "midday":   1,
    "sunset":   2,
    "overcast": 3,
    "midnight": 4,
}

# Час доби для BigWorld.timeOfDay / BigWorld.spaceTimeOfDay
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
    blocked_prefixes = ('hangar', 'garage', 'login', 'waiting', 'intro',
                        'bootcamp', 'story', 'fun_random_hangar')
    if lowered.startswith(blocked_prefixes):
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
        return '<traceback unavailable>'


def apply_preset_in_battle(preset_id):
    """
    Головна функція перемикання environment у бою.

    Стратегія (в порядку пріоритету):
    1. Weather.override(env_name) — головний метод, використовує ім'я з <name> тегу
    2. Weather.summon(env_name)   — fallback через summon з тим самим іменем
    3. player.__applyTimeAndWeatherSettings(period) — зміна period ID
    4. BigWorld.timeOfDay / spaceTimeOfDay — зміна часу доби

    env_name береться з PRESET_ENV_NAMES — це реальне ім'я з <name> тегу
    у файлі environment.xml всередині .wotmod мода.
    """
    if not IN_GAME:
        return False

    env_name = PRESET_ENV_NAMES.get(preset_id)
    guid = PRESET_GUIDS.get(preset_id, '')
    if guid is None:
        guid = ''
    period = PRESET_PERIOD_IDS.get(preset_id, 0)
    tod = PRESET_TOD.get(preset_id, u'12:00')

    logger.info('apply preset=%s env_name=%s guid=%s period=%s',
                preset_id, env_name, guid, period)

    # ---- Крок 1: Weather.override(env_name) --------------------------------
    try:
        import Weather
        w = getattr(Weather, 's_weather', None)
        if w is None and hasattr(Weather, 'weather'):
            w = Weather.weather()

        if w is not None:
            if env_name:
                # Спробуємо override з іменем environment
                if hasattr(w, 'override') and callable(w.override):
                    try:
                        w.override(env_name)
                        logger.info('OK: Weather.override(%s)', env_name)
                    except Exception:
                        logger.warning('FAIL: Weather.override(%s)\n%s', env_name, _fmt_exc())

                # Спробуємо summon з іменем environment
                if hasattr(w, 'summon') and callable(w.summon):
                    try:
                        w.summon(env_name)
                        logger.info('OK: Weather.summon(%s)', env_name)
                    except Exception:
                        logger.debug('FAIL: Weather.summon(%s)\n%s', env_name, _fmt_exc())

            else:
                # Для standard — скидаємо override (якщо є метод)
                for reset_method in ('clearOverride', 'resetOverride', 'clearLocalOverride'):
                    if hasattr(w, reset_method) and callable(getattr(w, reset_method)):
                        try:
                            getattr(w, reset_method)()
                            logger.info('OK: Weather.%s()', reset_method)
                            break
                        except Exception:
                            pass
        else:
            logger.warning('Weather object not available')

    except ImportError:
        logger.warning('Weather module not importable')
    except Exception:
        logger.error('Weather block failed\n%s', _fmt_exc())

    # ---- Крок 2: player period + applyTimeAndWeatherSettings ----------------
    try:
        player = BigWorld.player()
        if player is not None:
            setattr(player, 'weatherPresetID', period)
            setattr(player, '_PlayerAvatar__blArenaPeriod', period)

            apply_fn = getattr(player, '_PlayerAvatar__applyTimeAndWeatherSettings', None)
            if callable(apply_fn):
                try:
                    apply_fn(period)
                    logger.info('OK: player.apply(period=%s)', period)
                except Exception:
                    logger.debug('FAIL: player.apply(%s)\n%s', period, _fmt_exc())
    except Exception:
        logger.error('player block failed\n%s', _fmt_exc())

    # ---- Крок 3: час доби --------------------------------------------------
    try:
        fn = getattr(BigWorld, 'timeOfDay', None)
        if callable(fn):
            fn(tod)
            logger.info('OK: BigWorld.timeOfDay(%s)', tod)

        player = BigWorld.player()
        fn2 = getattr(BigWorld, 'spaceTimeOfDay', None)
        space_id = getattr(player, 'spaceID', None) if player else None
        if callable(fn2) and space_id is not None:
            fn2(space_id, tod)
            logger.info('OK: BigWorld.spaceTimeOfDay(%s, %s)', space_id, tod)
    except Exception:
        logger.debug('timeOfDay block failed\n%s', _fmt_exc())

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
        logger.info('Hotkey updated: %s codes=%s', hotkey_str, key_codes)

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
        # space.settings patch залишаємо для pre-load (нешкідливо навіть якщо VFS read-only)
        try:
            if IN_GAME:
                guid = PRESET_GUIDS.get(preset)
                if guid:
                    path = 'spaces/%s/space.settings' % normalized
                    section = ResMgr.openSection(path)
                    if section is not None:
                        section.writeString('environment/override', guid)
                        logger.info('pre-load patch: %s -> %s', normalized, preset)
        except Exception:
            pass
        return preset

    def cycle_preset_in_battle(self):
        detected = detect_current_battle_space()
        if not detected:
            logger.info('cycle_preset: not in battle')
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

        logger.info('cycle: %s -> %s on %s', prev, next_preset, self._current_space)
        apply_preset_in_battle(next_preset)

        try:
            SystemMessages.pushI18nMessage(
                u'Погода: %s' % PRESET_LABELS[next_preset],
                type=SystemMessages.SM_TYPE.Information,
            )
        except Exception:
            pass


g_controller = WeatherController()
