# -*- coding: utf-8 -*-
"""
Weather controller.
v1.6.0 — точковий probe реального weather API у WoT 2.2
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

PRESET_NUMERIC_IDS = {
    "standard": 0,
    "midday": 1,
    "sunset": 2,
    "overcast": 3,
    "midnight": 4,
}

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


def _fmt_exc():
    try:
        return traceback.format_exc()
    except Exception:
        return '<traceback unavailable>'


def _log_probe_ok(label, args, result):
    logger.info('PROBE OK: %s args=%s result=%s', label, _safe_repr(args), _safe_repr(result))


def _log_probe_fail(label, args):
    logger.error('PROBE FAIL: %s args=%s\n%s', label, _safe_repr(args), _fmt_exc())


def _probe_call(fn, label, variants):
    for args in variants:
        try:
            result = fn(*args)
            _log_probe_ok(label, args, result)
        except Exception:
            _log_probe_fail(label, args)


def _dump_focus_diagnostics():
    global _DIAGNOSTICS_DONE
    if _DIAGNOSTICS_DONE:
        return
    _DIAGNOSTICS_DONE = True

    logger.info('====== FOCUS DIAGNOSTICS START ======')
    try:
        player = BigWorld.player()
        logger.info('player=%s', _safe_repr(player))
        if player is not None:
            for attr in ('weatherPresetID', '_PlayerAvatar__blArenaPeriod', '_PlayerAvatar__isSpaceInitialized'):
                try:
                    logger.info('player.%s=%s', attr, _safe_repr(getattr(player, attr)))
                except Exception:
                    _log_probe_fail('getattr(player, %s)' % attr, ())
            for name in ('_PlayerAvatar__applyTimeAndWeatherSettings', '_PlayerAvatar__onArenaPeriodChange'):
                fn = getattr(player, name, None)
                logger.info('player.%s callable=%s', name, callable(fn))
    except Exception:
        logger.error('FOCUS player diagnostics failed\n%s', _fmt_exc())

    try:
        logger.info('BigWorld.timeOfDay callable=%s', callable(getattr(BigWorld, 'timeOfDay', None)))
        logger.info('BigWorld.spaceTimeOfDay callable=%s', callable(getattr(BigWorld, 'spaceTimeOfDay', None)))
    except Exception:
        logger.error('FOCUS BigWorld diagnostics failed\n%s', _fmt_exc())

    try:
        import Weather
        logger.info('Weather=%s', _safe_repr(Weather))
        logger.info('Weather.s_weather=%s', _safe_repr(getattr(Weather, 's_weather', None)))
        if hasattr(Weather, 'weather'):
            try:
                logger.info('Weather.weather()=%s', _safe_repr(Weather.weather()))
            except Exception:
                _log_probe_fail('Weather.weather', ())
    except Exception:
        logger.error('FOCUS Weather diagnostics failed\n%s', _fmt_exc())

    logger.info('====== FOCUS DIAGNOSTICS END ======')


# kept only for hangar/preload path; in battle ResMgr save is not the main path

def apply_preset_to_space(space_name, preset_id):
    guid = PRESET_GUIDS.get(preset_id)
    if guid is None:
        return
    if not IN_GAME:
        return
    try:
        path = 'spaces/%s/space.settings' % space_name
        section = ResMgr.openSection(path)
        if section is None:
            logger.warning('space.settings not found for %s', space_name)
            return
        section.writeString('environment/override', guid)
        try:
            save_result = section.save()
            logger.info('space.settings save result for %s: %s', space_name, _safe_repr(save_result))
        except Exception:
            logger.error('space.settings save failed for %s\n%s', space_name, _fmt_exc())
    except Exception:
        logger.error('apply_preset_to_space failed for %s\n%s', space_name, _fmt_exc())


def _try_weather_api(guid, methods_tried):
    try:
        import Weather
    except Exception:
        logger.error('Weather import failed\n%s', _fmt_exc())
        return

    candidates = []
    if getattr(Weather, 's_weather', None) is not None:
        candidates.append(('Weather.s_weather', Weather.s_weather))
    if hasattr(Weather, 'weather'):
        try:
            candidates.append(('Weather.weather()', Weather.weather()))
        except Exception:
            _log_probe_fail('Weather.weather', ())

    for target_name, target in candidates:
        toggle = getattr(target, 'toggleRandomWeather', None)
        if callable(toggle):
            for args in ((), (guid,)):
                try:
                    res = toggle(*args)
                    methods_tried.append('%s.toggleRandomWeather%s' % (target_name, _safe_repr(args)))
                    _log_probe_ok('%s.toggleRandomWeather' % target_name, args, res)
                except Exception:
                    _log_probe_fail('%s.toggleRandomWeather' % target_name, args)

        for method_name in ('nextWeatherSystem', '_randomWeather'):
            fn = getattr(target, method_name, None)
            if callable(fn):
                for args in ((guid,),):
                    try:
                        res = fn(*args)
                        methods_tried.append('%s.%s%s' % (target_name, method_name, _safe_repr(args)))
                        _log_probe_ok('%s.%s' % (target_name, method_name), args, res)
                    except Exception:
                        _log_probe_fail('%s.%s' % (target_name, method_name), args)

        fn = getattr(target, '_weatherSystemsForCurrentSpace', None)
        if callable(fn):
            try:
                res = fn()
                methods_tried.append('%s._weatherSystemsForCurrentSpace()' % target_name)
                _log_probe_ok('%s._weatherSystemsForCurrentSpace' % target_name, (), res)
            except Exception:
                _log_probe_fail('%s._weatherSystemsForCurrentSpace' % target_name, ())


def _try_player_api(player, preset_id, guid, methods_tried):
    if player is None:
        return

    numeric = PRESET_NUMERIC_IDS.get(preset_id, 0)

    for attr_name, value in (('weatherPresetID', numeric), ('_PlayerAvatar__blArenaPeriod', numeric)):
        try:
            setattr(player, attr_name, value)
            methods_tried.append('set player.%s=%s' % (attr_name, value))
            logger.info('SET OK: player.%s=%s', attr_name, value)
        except Exception:
            logger.error('SET FAIL: player.%s=%s\n%s', attr_name, value, _fmt_exc())

    private_apply = getattr(player, '_PlayerAvatar__applyTimeAndWeatherSettings', None)
    if callable(private_apply):
        for args in ((numeric,), (), (guid,)):
            try:
                res = private_apply(*args)
                methods_tried.append('player._PlayerAvatar__applyTimeAndWeatherSettings%s' % _safe_repr(args))
                _log_probe_ok('player._PlayerAvatar__applyTimeAndWeatherSettings', args, res)
            except Exception:
                _log_probe_fail('player._PlayerAvatar__applyTimeAndWeatherSettings', args)


def _try_time_api(player, preset_id, methods_tried):
    tod = PRESET_TIME_OF_DAY.get(preset_id, 12.0)

    fn = getattr(BigWorld, 'timeOfDay', None)
    if callable(fn):
        for args in ((tod,), (float(tod),), (int(tod),)):
            try:
                res = fn(*args)
                methods_tried.append('BigWorld.timeOfDay%s' % _safe_repr(args))
                _log_probe_ok('BigWorld.timeOfDay', args, res)
            except Exception:
                _log_probe_fail('BigWorld.timeOfDay', args)

    if player is not None and hasattr(player, 'spaceID'):
        fn = getattr(BigWorld, 'spaceTimeOfDay', None)
        if callable(fn):
            for args in ((player.spaceID, tod), (player.spaceID, float(tod)), (player.spaceID, int(tod))):
                try:
                    res = fn(*args)
                    methods_tried.append('BigWorld.spaceTimeOfDay%s' % _safe_repr(args))
                    _log_probe_ok('BigWorld.spaceTimeOfDay', args, res)
                except Exception:
                    _log_probe_fail('BigWorld.spaceTimeOfDay', args)


def apply_preset_in_battle(preset_id):
    if not IN_GAME:
        return False

    _dump_focus_diagnostics()

    guid = PRESET_GUIDS.get(preset_id, '')
    if guid is None:
        guid = ''

    methods_tried = []
    try:
        player = BigWorld.player()
    except Exception:
        player = None
        logger.error('BigWorld.player() failed\n%s', _fmt_exc())

    logger.info('===== APPLY START preset=%s guid=%s numeric=%s tod=%s =====',
                preset_id, guid, PRESET_NUMERIC_IDS.get(preset_id), PRESET_TIME_OF_DAY.get(preset_id))

    _try_weather_api(guid, methods_tried)
    _try_player_api(player, preset_id, guid, methods_tried)
    _try_time_api(player, preset_id, methods_tried)

    logger.info('apply_preset_in_battle(%s): tried methods = %s', preset_id, methods_tried)
    logger.info('===== APPLY END preset=%s =====', preset_id)
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
        apply_preset_to_space(normalized, preset)
        return preset

    def cycle_preset_in_battle(self):
        detected = detect_current_battle_space()
        if not detected:
            logger.info('cycle_preset: not in battle')
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

        logger.info('cycle: %s -> %s on %s', prev_name, next_preset, self._current_space)
        apply_preset_in_battle(next_preset)

        try:
            SystemMessages.pushI18nMessage(
                u'Погода: %s' % PRESET_LABELS[next_preset],
                type=SystemMessages.SM_TYPE.Information,
            )
        except Exception:
            pass


g_controller = WeatherController()
