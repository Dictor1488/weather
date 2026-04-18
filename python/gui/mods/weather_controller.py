# -*- coding: utf-8 -*-
"""
Weather controller.
v1.5.0 — глибша діагностика реального weather/time API у WoT 2.2
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

# numeric fallback for any APIs that want integer preset ids
PRESET_NUMERIC_IDS = {
    "standard": 0,
    "midday": 1,
    "sunset": 2,
    "overcast": 3,
    "midnight": 4,
}

# time-of-day fallback for any APIs that want time instead of preset guid
PRESET_TIME_OF_DAY = {
    "standard": 12.0,
    "midday": 12.0,
    "sunset": 18.5,
    "overcast": 13.0,
    "midnight": 0.2,
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

_DIAGNOSTICS_DONE = False

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
        logger.exception("detect_current_battle_space failed")
    return None


def _safe_repr(value, limit=240):
    try:
        text = repr(value)
    except Exception as e:
        text = '<repr failed: %s>' % e
    if len(text) > limit:
        text = text[:limit] + '...'
    return text


def _log_callable_probe(obj, obj_name, keywords, limit=100):
    if obj is None:
        logger.info("[%s] = None", obj_name)
        return
    logger.info("[%s] type=%s", obj_name, type(obj).__name__)
    try:
        attrs = dir(obj)
    except Exception as e:
        logger.info("[%s] dir() failed: %s", obj_name, e)
        return
    count = 0
    for attr in attrs:
        if attr.startswith('__'):
            continue
        lower = attr.lower()
        if not any(kw in lower for kw in keywords):
            continue
        count += 1
        if count > limit:
            logger.info("  [%s] ... truncated after %s entries", obj_name, limit)
            break
        try:
            value = getattr(obj, attr)
            if callable(value):
                logger.info("  [%s.%s] CALLABLE", obj_name, attr)
            else:
                logger.info("  [%s.%s] = %s", obj_name, attr, _safe_repr(value))
        except Exception as e:
            logger.info("  [%s.%s] access failed: %s", obj_name, attr, e)


def _probe_call(fn, label, variants):
    for args in variants:
        try:
            result = fn(*args)
            logger.info("PROBE OK: %s args=%s result=%s", label, args, _safe_repr(result))
        except Exception as e:
            logger.info("PROBE FAIL: %s args=%s error=%s", label, args, e)


def run_diagnostics():
    global _DIAGNOSTICS_DONE
    if _DIAGNOSTICS_DONE:
        return
    _DIAGNOSTICS_DONE = True

    logger.info("====== DIAGNOSTICS START ======")
    keywords = (
        'environment', 'weather', 'period', 'timeofday', 'time_of_day',
        'sky', 'light', 'visual', 'space', 'preset', 'apply', 'reload'
    )

    try:
        logger.info("--- BigWorld module ---")
        _log_callable_probe(BigWorld, 'BigWorld', keywords)
    except Exception:
        logger.exception("BigWorld dump failed")

    player = None
    arena = None
    arenaType = None
    try:
        player = BigWorld.player()
        _log_callable_probe(player, 'player', keywords)
    except Exception:
        logger.exception("player dump failed")

    try:
        arena = getattr(player, 'arena', None) if player else None
        _log_callable_probe(arena, 'arena', keywords)
    except Exception:
        logger.exception("arena dump failed")

    try:
        arenaType = getattr(arena, 'arenaType', None) if arena else None
        _log_callable_probe(arenaType, 'arenaType', keywords)
    except Exception:
        logger.exception("arenaType dump failed")

    try:
        import BWPersonality
        _log_callable_probe(BWPersonality, 'BWPersonality', keywords)
    except Exception as e:
        logger.info("BWPersonality unavailable: %s", e)

    try:
        import Weather
        _log_callable_probe(Weather, 'Weather', keywords)
        weather_obj = getattr(Weather, 's_weather', None)
        _log_callable_probe(weather_obj, 'Weather.s_weather', keywords)
        if hasattr(Weather, 'weather'):
            try:
                weather_singleton = Weather.weather()
                logger.info("Weather.weather() -> %s", _safe_repr(weather_singleton))
                _log_callable_probe(weather_singleton, 'Weather.weather()', keywords)
            except Exception as e:
                logger.info("Weather.weather() failed: %s", e)
    except Exception as e:
        logger.info("Weather module import failed: %s", e)

    try:
        if hasattr(BigWorld, 'getWatcher'):
            root = BigWorld.getWatcher('')
            logger.info("WATCHER ROOT: %s", _safe_repr(root, 1200))
    except Exception as e:
        logger.info("WATCHER ROOT failed: %s", e)

    try:
        if player and hasattr(player, 'spaceID'):
            sid = player.spaceID
            logger.info("player.spaceID = %s", sid)
            if hasattr(BigWorld, 'spaceTimeOfDay'):
                _probe_call(BigWorld.spaceTimeOfDay, 'BigWorld.spaceTimeOfDay', [(), (sid,), (sid, PRESET_TIME_OF_DAY['midnight']), (sid, PRESET_TIME_OF_DAY['midday'])])
            if hasattr(BigWorld, 'Space'):
                try:
                    space_obj = BigWorld.Space(sid)
                    _log_callable_probe(space_obj, 'BigWorld.Space(player.spaceID)', keywords)
                except Exception as e:
                    logger.info("BigWorld.Space(%s) failed: %s", sid, e)
    except Exception:
        logger.exception("space diagnostics failed")

    try:
        if hasattr(BigWorld, 'timeOfDay'):
            _probe_call(BigWorld.timeOfDay, 'BigWorld.timeOfDay', [(), (PRESET_TIME_OF_DAY['midnight'],), (PRESET_TIME_OF_DAY['midday'],)])
    except Exception:
        logger.exception("timeOfDay diagnostics failed")

    if player is not None:
        for private_name in (
            '_PlayerAvatar__applyTimeAndWeatherSettings',
            '_PlayerAvatar__onArenaPeriodChange',
        ):
            fn = getattr(player, private_name, None)
            if callable(fn):
                _probe_call(fn, 'player.%s' % private_name, [(), (0,), (1,), (2,), (PRESET_NUMERIC_IDS['midnight'],), (PRESET_GUIDS['midnight'],)])

    logger.info("====== DIAGNOSTICS END ======")


def apply_preset_to_space(space_name, preset_id):
    guid = PRESET_GUIDS.get(preset_id)
    if guid is None:
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
        try:
            save_result = section.save()
            logger.info("space.settings save result for %s: %s", space_name, _safe_repr(save_result))
        except Exception:
            logger.exception("Failed to patch space.settings via section.save() for %s", space_name)
    except Exception:
        logger.exception("apply_preset_to_space failed for %s", space_name)


def _try_set_watchers(guid, preset_id, methods_tried):
    watcher_values = [guid, preset_id, PRESET_NUMERIC_IDS.get(preset_id, 0), PRESET_TIME_OF_DAY.get(preset_id, 12.0)]
    watcher_paths = (
        'Client Settings/environmentOverride',
        'Client Settings/weatherPreset',
        'Client Settings/weatherPresetID',
        'Client Settings/timeOfDay',
        'Client Settings/arenaPeriod',
        'Render/environmentOverride',
        'Render/environmentName',
        'Render/timeOfDay',
        'Render/weatherPreset',
        'Space/environmentOverride',
        'Space/weatherPreset',
        'Space/timeOfDay',
        'Environment/override',
        'Environment/presetName',
        'Environment/presetGUID',
        'Environment/weatherPresetID',
    )
    for path in watcher_paths:
        for value in watcher_values:
            try:
                BigWorld.setWatcher(path, value)
                methods_tried.append('%s=%s' % (path, _safe_repr(value, 80)))
                break
            except Exception:
                pass


def _try_public_api(player, preset_id, guid, methods_tried):
    numeric = PRESET_NUMERIC_IDS.get(preset_id, 0)
    tod = PRESET_TIME_OF_DAY.get(preset_id, 12.0)
    arena = getattr(player, 'arena', None) if player else None

    if hasattr(BigWorld, 'timeOfDay'):
        for args in ((tod,), (float(tod),), (int(tod),)):
            try:
                BigWorld.timeOfDay(*args)
                methods_tried.append('BigWorld.timeOfDay%s' % (args,))
                break
            except Exception:
                pass

    if player and hasattr(player, 'spaceID') and hasattr(BigWorld, 'spaceTimeOfDay'):
        for args in ((player.spaceID, tod), (player.spaceID, float(tod)), (player.spaceID, int(tod))):
            try:
                BigWorld.spaceTimeOfDay(*args)
                methods_tried.append('BigWorld.spaceTimeOfDay%s' % (args,))
                break
            except Exception:
                pass

    if player:
        for attr_name, value in (('weatherPresetID', numeric), ('_PlayerAvatar__blArenaPeriod', numeric)):
            try:
                setattr(player, attr_name, value)
                methods_tried.append('player.%s=%s' % (attr_name, value))
            except Exception:
                pass

        for method_name in (
            'setEnvironmentOverride', 'setArenaEnvironment', 'setTimeOfDay',
            'reloadEnvironment', 'applyTimeAndWeatherSettings',
        ):
            if hasattr(player, method_name):
                fn = getattr(player, method_name)
                for args in ((guid,), (preset_id,), (numeric,), (tod,), (numeric, tod), (guid, tod)):
                    try:
                        fn(*args)
                        methods_tried.append('player.%s%s' % (method_name, args))
                        break
                    except Exception:
                        pass

        private_apply = getattr(player, '_PlayerAvatar__applyTimeAndWeatherSettings', None)
        if callable(private_apply):
            for args in ((numeric,), (numeric, tod), (tod,), (), (guid,), (preset_id,)):
                try:
                    private_apply(*args)
                    methods_tried.append('player._PlayerAvatar__applyTimeAndWeatherSettings%s' % (args,))
                    break
                except Exception:
                    pass

    if arena:
        for method_name in (
            'setArenaPeriod', 'setPeriod', 'setEnvironmentOverride', 'setWeather',
            'setEnvironment', 'setTimeOfDay', 'reloadEnvironment'
        ):
            if hasattr(arena, method_name):
                fn = getattr(arena, method_name)
                for args in ((guid,), (preset_id,), (numeric,), (tod,), (numeric, tod)):
                    try:
                        fn(*args)
                        methods_tried.append('arena.%s%s' % (method_name, args))
                        break
                    except Exception:
                        pass

    try:
        import BWPersonality
        for method_name in ('reloadEnvironment', 'setEnvironment', 'setEnvironmentOverride', 'forceEnvironment', 'setSpaceEnvironment'):
            if hasattr(BWPersonality, method_name):
                fn = getattr(BWPersonality, method_name)
                for args in ((guid,), (preset_id,), (numeric,), (tod,)):
                    try:
                        fn(*args)
                        methods_tried.append('BWPersonality.%s%s' % (method_name, args))
                        break
                    except Exception:
                        pass
    except Exception:
        pass

    try:
        import game
        if hasattr(game, 'onChangeEnvironments'):
            fn = game.onChangeEnvironments
            for args in ((guid,), (preset_id,), (numeric,), (tod,), ()):
                try:
                    fn(*args)
                    methods_tried.append('game.onChangeEnvironments%s' % (args,))
                    break
                except Exception:
                    pass
    except Exception:
        pass

    try:
        import Weather
        for target_name, target in (('Weather', Weather), ('Weather.s_weather', getattr(Weather, 's_weather', None)), ('Weather.weather()', Weather.weather() if hasattr(Weather, 'weather') else None)):
            if target is None:
                continue
            try:
                attrs = dir(target)
            except Exception:
                continue
            for attr in attrs:
                lower = attr.lower()
                if not any(token in lower for token in ('weather', 'environment', 'preset', 'apply', 'reload', 'time')):
                    continue
                try:
                    fn = getattr(target, attr)
                except Exception:
                    continue
                if not callable(fn):
                    continue
                for args in ((guid,), (preset_id,), (numeric,), (tod,), (numeric, tod), ()):
                    try:
                        fn(*args)
                        methods_tried.append('%s.%s%s' % (target_name, attr, args))
                        break
                    except Exception:
                        pass
    except Exception:
        pass


def apply_preset_in_battle(preset_id):
    if not IN_GAME:
        return False

    run_diagnostics()

    guid = PRESET_GUIDS.get(preset_id, '')
    if guid is None:
        guid = ''

    methods_tried = []
    player = None
    try:
        player = BigWorld.player()
    except Exception:
        pass

    _try_set_watchers(guid, preset_id, methods_tried)
    _try_public_api(player, preset_id, guid, methods_tried)

    logger.info('apply_preset_in_battle(%s): tried methods = %s', preset_id, methods_tried)
    return bool(methods_tried)


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
        self.hotkey_str = hotkey_str
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
        apply_preset_to_space(normalized, preset)
        return preset

    def cycle_preset_in_battle(self):
        detected = detect_current_battle_space()
        if not detected:
            logger.info("cycle_preset: not in battle")
            return
        self._current_space = detected

        try:
            prev_name = self._current_preset or 'standard'
            idx = PRESET_ORDER.index(prev_name)
        except ValueError:
            prev_name = 'standard'
            idx = 0
        next_preset = PRESET_ORDER[(idx + 1) % len(PRESET_ORDER)]
        self._current_preset = next_preset

        logger.info("cycle: %s -> %s on %s", prev_name, next_preset, self._current_space)

        apply_preset_in_battle(next_preset)

        try:
            SystemMessages.pushI18nMessage(
                u"Погода: %s" % PRESET_LABELS[next_preset],
                type=SystemMessages.SM_TYPE.Information,
            )
        except Exception:
            pass


g_controller = WeatherController()
