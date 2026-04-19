# -*- coding: utf-8 -*-
"""
Weather controller.
v1.8.0 — стабільний мінімум через player + BigWorld timeOfDay
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

# arena period ids from probing in logs: 0,1,2,4 were accepted; overcast kept on 3 for continuity
PRESET_PERIOD_IDS = {
    "standard": 0,
    "midday": 1,
    "sunset": 2,
    "overcast": 3,
    "midnight": 4,
}

# BigWorld.timeOfDay(spaceTimeOfDay) takes unicode like '10:00'
PRESET_TIME_TEXT = {
    "standard": u"12:00",
    "midday": u"12:00",
    "sunset": u"18:30",
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


def _log_ok(step, detail=''):
    if detail:
        logger.info('STEP OK: %s | %s', step, detail)
    else:
        logger.info('STEP OK: %s', step)


def _log_fail(step):
    logger.error('STEP FAIL: %s\n%s', step, _fmt_exc())


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
            for attr in ('weatherPresetID', '_PlayerAvatar__blArenaPeriod', '_PlayerAvatar__isSpaceInitialized', 'spaceID'):
                logger.info('player.%s=%s', attr, _safe_repr(getattr(player, attr, None)))
            logger.info('player._PlayerAvatar__applyTimeAndWeatherSettings callable=%s', callable(getattr(player, '_PlayerAvatar__applyTimeAndWeatherSettings', None)))
        logger.info('BigWorld.timeOfDay callable=%s', callable(getattr(BigWorld, 'timeOfDay', None)))
        logger.info('BigWorld.spaceTimeOfDay callable=%s', callable(getattr(BigWorld, 'spaceTimeOfDay', None)))
        import Weather
        logger.info('Weather.s_weather=%s', _safe_repr(getattr(Weather, 's_weather', None)))
        if hasattr(Weather, 'weather'):
            logger.info('Weather.weather()=%s', _safe_repr(Weather.weather()))
    except Exception:
        logger.error('FOCUS diagnostics failed\n%s', _fmt_exc())
    logger.info('====== FOCUS DIAGNOSTICS END ======')


# kept only for preload path; battle path is player + BigWorld timeOfDay

def apply_preset_to_space(space_name, preset_id):
    guid = PRESET_GUIDS.get(preset_id)
    if guid is None or not IN_GAME:
        return
    try:
        path = 'spaces/%s/space.settings' % space_name
        section = ResMgr.openSection(path)
        if section is None:
            logger.warning('space.settings not found for %s', space_name)
            return
        section.writeString('environment/override', guid)
        # NOTE: section.save() intentionally removed — WoT VFS is read-only at runtime.
        # The writeString patches the in-memory section which is read during space load.
        logger.info('space.settings patched in-memory for %s (guid=%s)', space_name, guid)
    except Exception:
        logger.error('apply_preset_to_space failed for %s\n%s', space_name, _fmt_exc())


def _set_player_values(player, preset_id):
    numeric = PRESET_NUMERIC_IDS.get(preset_id, 0)
    period = PRESET_PERIOD_IDS.get(preset_id, numeric)
    setattr(player, 'weatherPresetID', numeric)
    setattr(player, '_PlayerAvatar__blArenaPeriod', period)
    return numeric, period


def _apply_player_weather(player, preset_id, guid):
    numeric, period = _set_player_values(player, preset_id)
    _log_ok('player values', 'weatherPresetID=%s blArenaPeriod=%s guid=%s' % (numeric, period, guid))

    apply_fn = getattr(player, '_PlayerAvatar__applyTimeAndWeatherSettings', None)
    if callable(apply_fn):
        try:
            apply_fn(period)
            _log_ok('player.apply(period)', _safe_repr(period))
        except Exception:
            _log_fail('player.apply(period=%s)' % period)
        try:
            apply_fn(numeric)
            _log_ok('player.apply(numeric)', _safe_repr(numeric))
        except Exception:
            _log_fail('player.apply(numeric=%s)' % numeric)
        try:
            apply_fn()
            _log_ok('player.apply()')
        except Exception:
            _log_fail('player.apply()')
        if guid:
            try:
                apply_fn(guid)
                _log_ok('player.apply(guid)', guid)
            except Exception:
                _log_fail('player.apply(guid=%s)' % guid)
    else:
        logger.warning('player._PlayerAvatar__applyTimeAndWeatherSettings not callable')

    return numeric, period


def _apply_time_text(player, preset_id):
    tod = PRESET_TIME_TEXT.get(preset_id, u'12:00')
    fn = getattr(BigWorld, 'timeOfDay', None)
    if callable(fn):
        try:
            res = fn(tod)
            _log_ok('BigWorld.timeOfDay', '%s -> %s' % (tod, _safe_repr(res)))
        except Exception:
            _log_fail('BigWorld.timeOfDay(%s)' % tod)

    fn = getattr(BigWorld, 'spaceTimeOfDay', None)
    space_id = getattr(player, 'spaceID', None)
    if callable(fn) and space_id is not None:
        try:
            res = fn(space_id, tod)
            _log_ok('BigWorld.spaceTimeOfDay', 'spaceID=%s tod=%s -> %s' % (space_id, tod, _safe_repr(res)))
        except Exception:
            _log_fail('BigWorld.spaceTimeOfDay(%s, %s)' % (space_id, tod))


def _apply_weather_object(guid):
    """
    Змінює візуальний environment через Weather.override або localOverride.
    Список методів з логу:
    localOverride, override, overridenWeather, summon, system,
    weatherController, newSystemByName, nextWeatherSystem, onChangeSpace
    """
    if not IN_GAME:
        return
    try:
        import Weather
        w = getattr(Weather, 's_weather', None)
        if w is None and hasattr(Weather, 'weather'):
            w = Weather.weather()
        if w is None:
            logger.warning('Weather object not available')
            return

        applied = False

        # Метод 1: localOverride(guid) — локальне перевизначення для клієнта
        if hasattr(w, 'localOverride') and guid:
            try:
                w.localOverride(guid)
                _log_ok('Weather.localOverride', guid)
                applied = True
            except Exception:
                _log_fail('Weather.localOverride(%s)' % guid)

        # Метод 2: override(guid) — глобальне перевизначення
        if not applied and hasattr(w, 'override') and guid:
            try:
                w.override(guid)
                _log_ok('Weather.override', guid)
                applied = True
            except Exception:
                _log_fail('Weather.override(%s)' % guid)

        # Метод 3: summon(guid) — виклик weather system за назвою/guid
        if not applied and hasattr(w, 'summon') and guid:
            try:
                w.summon(guid)
                _log_ok('Weather.summon', guid)
                applied = True
            except Exception:
                _log_fail('Weather.summon(%s)' % guid)

        if not applied:
            logger.warning('Weather: no applicable method found for guid=%s', guid)

    except Exception:
        _log_fail('_apply_weather_object(guid=%s)' % guid)


def apply_preset_in_battle(preset_id):
    if not IN_GAME:
        return False

    _dump_focus_diagnostics()

    guid = PRESET_GUIDS.get(preset_id) or ''
    logger.info('===== APPLY START preset=%s guid=%s numeric=%s period=%s tod=%s =====',
                preset_id, guid, PRESET_NUMERIC_IDS.get(preset_id), PRESET_PERIOD_IDS.get(preset_id), PRESET_TIME_TEXT.get(preset_id))

    try:
        player = BigWorld.player()
    except Exception:
        logger.error('BigWorld.player() failed\n%s', _fmt_exc())
        return False

    if player is None:
        logger.warning('apply_preset_in_battle: no player')
        return False

    # 1) Weather.localOverride — головний механізм зміни рендеру
    #    Це той самий шлях що використовують environments_*.wotmod в рантаймі
    try:
        _apply_weather_object(guid)
    except Exception:
        _log_fail('STEP 1 Weather.localOverride')

    # 2) player state sync
    try:
        numeric, period = _apply_player_weather(player, preset_id, guid)
    except Exception:
        _log_fail('STEP 2 player hard-set')
        numeric = PRESET_NUMERIC_IDS.get(preset_id, 0)
        period = PRESET_PERIOD_IDS.get(preset_id, numeric)

    # 3) time of day
    try:
        _apply_time_text(player, preset_id)
    except Exception:
        _log_fail('STEP 3 time sync')

    # 4) final re-apply
    try:
        apply_fn = getattr(player, '_PlayerAvatar__applyTimeAndWeatherSettings', None)
        if callable(apply_fn):
            apply_fn(period)
            _log_ok('STEP 4 final player.apply(period)', _safe_repr(period))
    except Exception:
        _log_fail('STEP 4 final player.apply(period=%s)' % period)

    logger.info('FINAL STATE: player.weatherPresetID=%s player._PlayerAvatar__blArenaPeriod=%s',
                _safe_repr(getattr(player, 'weatherPresetID', None)),
                _safe_repr(getattr(player, '_PlayerAvatar__blArenaPeriod', None)))
    logger.info('===== APPLY END preset=%s =====', preset_id)
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
