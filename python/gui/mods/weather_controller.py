# -*- coding: utf-8 -*-
"""
Weather controller.
v1.4.0 — агресивна діагностика щоб знайти реальний API
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

# Флаг, щоб дамп зробити тільки один раз
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
    """Мінімум логів — просто повертаємо карту."""
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


def run_diagnostics():
    """
    Один раз при першому натисканні хоткея — дампимо ВСЕ, що могло б
    керувати погодою. Шукаємо в об'єктах методи, що містять 'environment',
    'weather', 'period', 'time', 'sky', 'light', 'visual'.
    """
    global _DIAGNOSTICS_DONE
    if _DIAGNOSTICS_DONE:
        return
    _DIAGNOSTICS_DONE = True

    log = logger
    log.info("====== DIAGNOSTICS START ======")

    keywords = ('environment', 'weather', 'period', 'timeofday', 'time_of_day',
                'sky', 'light', 'visual', 'space')

    def dump_object_methods(obj, obj_name):
        if obj is None:
            log.info("[%s] = None", obj_name)
            return
        log.info("[%s] type=%s", obj_name, type(obj).__name__)
        try:
            attrs = dir(obj)
        except Exception:
            return
        for attr in attrs:
            if attr.startswith('__'):
                continue
            lower = attr.lower()
            if any(kw in lower for kw in keywords):
                try:
                    value = getattr(obj, attr)
                    if callable(value):
                        log.info("  [%s.%s] CALLABLE", obj_name, attr)
                    else:
                        vstr = repr(value)[:150]
                        log.info("  [%s.%s] = %s", obj_name, attr, vstr)
                except Exception as e:
                    log.info("  [%s.%s] access failed: %s", obj_name, attr, e)

    # 1. BigWorld module
    if IN_GAME:
        try:
            log.info("--- BigWorld module ---")
            dump_object_methods(BigWorld, 'BigWorld')
        except Exception:
            log.exception("BigWorld dump failed")

        # 2. BigWorld.player()
        try:
            player = BigWorld.player()
            dump_object_methods(player, 'player')
        except Exception:
            log.exception("player dump failed")

        # 3. player.arena
        try:
            arena = BigWorld.player().arena if BigWorld.player() else None
            dump_object_methods(arena, 'arena')
        except Exception:
            pass

        # 4. arena.arenaType
        try:
            arenaType = BigWorld.player().arena.arenaType
            dump_object_methods(arenaType, 'arenaType')
        except Exception:
            pass

        # 5. BWPersonality
        try:
            import BWPersonality
            dump_object_methods(BWPersonality, 'BWPersonality')
        except Exception:
            pass

        # 6. Namespace of all watchers
        try:
            result = BigWorld.getWatcher("")
            log.info("WATCHER ROOT: %s", repr(result)[:2000])
        except Exception as e:
            log.info("WATCHER ROOT failed: %s", e)

        # 7. Try common weather control modules
        for modname in ('PlayerAvatar', 'Weather', 'WeatherController',
                        'ArenaPeriodController', 'game', 'Helpers.environment'):
            try:
                mod = __import__(modname)
                dump_object_methods(mod, modname)
            except ImportError:
                log.info("Module '%s' not importable", modname)
            except Exception as e:
                log.info("Module '%s' failed: %s", modname, e)

    log.info("====== DIAGNOSTICS END ======")


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
        # section.save() — може падати якщо файл read-only.
        # ResMgr в бою часто read-only, тому тут просто логуємо.
        try:
            section.save()
        except Exception as e:
            logger.info("section.save() failed (expected in battle): %s", e)
    except Exception:
        logger.debug("Failed to patch space.settings")


def apply_preset_in_battle(preset_id):
    """
    Нова стратегія: ReadyMgr-подібний підхід.
    Пробуємо більше API-точок + інформативний лог.
    """
    if not IN_GAME:
        return False

    # При ПЕРШОМУ виклику — дамп діагностики
    run_diagnostics()

    guid = PRESET_GUIDS.get(preset_id, "")
    if guid is None:
        guid = ""

    log = logger
    methods_tried = []

    # 1. BigWorld.setWatcher — багато шляхів
    for path in (
        "Client Settings/environmentOverride",
        "Render/environmentOverride",
        "Space/environmentOverride",
        "Environment/override",
        "Environment/presetName",
        "Render/timeOfDay",
        "Render/environmentName",
        "Client Settings/timeOfDay",
    ):
        try:
            BigWorld.setWatcher(path, guid)
            methods_tried.append(path)
        except Exception:
            pass

    # 2. player.arena.setArenaPeriod / setPeriod
    try:
        player = BigWorld.player()
        arena = getattr(player, 'arena', None) if player else None
        if arena:
            for method_name in ('setArenaPeriod', 'setPeriod',
                                'setEnvironmentOverride', 'setWeather',
                                'setEnvironment', 'setTimeOfDay'):
                if hasattr(arena, method_name):
                    try:
                        getattr(arena, method_name)(guid)
                        methods_tried.append("arena.%s" % method_name)
                    except Exception as e:
                        log.debug("arena.%s(%s) failed: %s", method_name, guid, e)
    except Exception:
        pass

    # 3. BWPersonality
    try:
        import BWPersonality
        for method_name in ('reloadEnvironment', 'setEnvironment',
                            'setEnvironmentOverride', 'forceEnvironment',
                            'setSpaceEnvironment'):
            if hasattr(BWPersonality, method_name):
                try:
                    getattr(BWPersonality, method_name)(guid)
                    methods_tried.append("BWPersonality.%s" % method_name)
                except Exception as e:
                    log.debug("BWPersonality.%s(%s) failed: %s", method_name, guid, e)
    except ImportError:
        pass

    # 4. BigWorld.reloadClientScripts? BigWorld.reloadEnvironment?
    for method_name in ('reloadEnvironment', 'setEnvironment',
                        'reloadSpace', 'setSpaceEnvironment'):
        if hasattr(BigWorld, method_name):
            try:
                getattr(BigWorld, method_name)(guid)
                methods_tried.append("BigWorld.%s" % method_name)
            except Exception as e:
                log.debug("BigWorld.%s(%s) failed: %s", method_name, guid, e)

    # 5. PlayerAvatar.setEnvironmentOverride
    try:
        player = BigWorld.player()
        if player:
            for method_name in ('setEnvironmentOverride', 'setArenaEnvironment',
                                'setTimeOfDay', 'reloadEnvironment'):
                if hasattr(player, method_name):
                    try:
                        getattr(player, method_name)(guid)
                        methods_tried.append("player.%s" % method_name)
                    except Exception as e:
                        log.debug("player.%s failed: %s", method_name, e)
    except Exception:
        pass

    log.info("apply_preset_in_battle(%s): tried methods = %s",
             preset_id, methods_tried)
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
        apply_preset_to_space(normalized, preset)
        return preset

    def cycle_preset_in_battle(self):
        detected = detect_current_battle_space()
        if not detected:
            logger.info("cycle_preset: not in battle")
            return
        self._current_space = detected

        try:
            idx = PRESET_ORDER.index(self._current_preset or "standard")
        except ValueError:
            idx = 0
        next_preset = PRESET_ORDER[(idx + 1) % len(PRESET_ORDER)]
        self._current_preset = next_preset

        logger.info("cycle: %s -> %s on %s",
                    PRESET_ORDER[idx], next_preset, self._current_space)

        apply_preset_in_battle(next_preset)

        try:
            SystemMessages.pushI18nMessage(
                u"Погода: %s" % PRESET_LABELS[next_preset],
                type=SystemMessages.SM_TYPE.Information,
            )
        except Exception:
            pass


g_controller = WeatherController()
