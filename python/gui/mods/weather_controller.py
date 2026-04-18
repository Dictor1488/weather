# -*- coding: utf-8 -*-
"""
Weather controller.
v1.3.0 — battle detection + verbose debug
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


def detect_current_battle_space():
    """
    Пробуємо ВСІ відомі способи визначити карту, логуємо ВСІ.
    """
    if not IN_GAME:
        return None

    log = logger

    # Спроба 1: BigWorld.player().arena.arenaType.geometryName
    try:
        player = BigWorld.player()
        if player is None:
            log.info("detect: BigWorld.player() = None")
        else:
            log.info("detect: BigWorld.player() = %s (class %s)", player, type(player).__name__)
            arena = getattr(player, 'arena', None)
            if arena is None:
                log.info("detect: player.arena = None")
            else:
                log.info("detect: player.arena = %s (class %s)", arena, type(arena).__name__)
                arenaType = getattr(arena, 'arenaType', None)
                if arenaType is None:
                    log.info("detect: arena.arenaType = None")
                else:
                    log.info("detect: arenaType = %s (class %s)", arenaType, type(arenaType).__name__)
                    for attr in ('geometryName', 'geometry', 'name', 'mapName'):
                        value = getattr(arenaType, attr, None)
                        if value:
                            log.info("detect: arenaType.%s = %s", attr, value)
                            norm = normalize_space_name(value)
                            if is_battle_map_space(norm):
                                log.info("detect: RESULT from arenaType.%s = %s", attr, norm)
                                return norm
    except Exception:
        log.exception("detect via player.arena failed")

    # Спроба 2: BigWorld.spaceName
    if hasattr(BigWorld, 'spaceName'):
        try:
            name = BigWorld.spaceName()
            log.info("detect: BigWorld.spaceName() = %s", name)
            norm = normalize_space_name(name)
            if is_battle_map_space(norm):
                log.info("detect: RESULT from BigWorld.spaceName = %s", norm)
                return norm
        except Exception as e:
            log.info("detect: BigWorld.spaceName() failed: %s", e)

    # Спроба 3: BigWorld.camera().spaceID
    try:
        camera = BigWorld.camera()
        log.info("detect: BigWorld.camera() = %s", camera)
    except Exception as e:
        log.info("detect: BigWorld.camera() failed: %s", e)

    # Спроба 4: через BattleReplay
    try:
        from helpers import dependency
        from skeletons.gui.battle_session import IBattleSessionProvider
        bsp = dependency.instance(IBattleSessionProvider)
        arenaDP = bsp.getArenaDP() if bsp else None
        log.info("detect: BattleSessionProvider arenaDP = %s", arenaDP)
        if arenaDP:
            for attr in dir(arenaDP):
                if 'arena' in attr.lower() or 'space' in attr.lower() or 'map' in attr.lower():
                    log.info("detect: arenaDP.%s = %s", attr, getattr(arenaDP, attr, None))
    except Exception as e:
        log.info("detect: BattleSessionProvider failed: %s", e)

    log.warning("detect: NO method found current battle space")
    return None


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
        section.save()
        logger.info("[%s] Applied preset %s (guid=%s)", space_name, preset_id, guid)
    except Exception:
        logger.exception("Failed to patch space.settings")


def apply_preset_in_battle(preset_id):
    """
    Пробуємо всі способи + дамп watcher'ів якщо нічого не вийшло.
    """
    if not IN_GAME:
        return False

    guid = PRESET_GUIDS.get(preset_id, "")
    if guid is None:
        guid = ""

    methods_worked = []

    # Метод 1-4: watcher'и
    for watcher_path in ("Client Settings/environmentOverride",
                          "Render/environmentOverride",
                          "Space/environmentOverride",
                          "Environment/override"):
        try:
            BigWorld.setWatcher(watcher_path, guid)
            methods_worked.append("watcher '%s'" % watcher_path)
            logger.info("watcher '%s' = %s", watcher_path, guid)
        except Exception as e:
            logger.debug("watcher '%s' failed: %s", watcher_path, e)

    # Метод 5-7: BWPersonality
    try:
        import BWPersonality
        for attr in ('reloadEnvironment', 'setEnvironment', 'setEnvironmentOverride'):
            if hasattr(BWPersonality, attr):
                try:
                    getattr(BWPersonality, attr)(guid)
                    methods_worked.append("BWPersonality.%s" % attr)
                except Exception as e:
                    logger.debug("BWPersonality.%s failed: %s", attr, e)
    except ImportError:
        pass

    # Метод 8-10: arena methods
    try:
        player = BigWorld.player()
        arena = getattr(player, 'arena', None) if player else None
        if arena:
            for attr in ('setEnvironmentOverride', 'setWeather', 'setEnvironment'):
                if hasattr(arena, attr):
                    try:
                        getattr(arena, attr)(guid)
                        methods_worked.append("arena.%s" % attr)
                    except Exception as e:
                        logger.debug("arena.%s failed: %s", attr, e)
    except Exception:
        pass

    # Метод 11: повторний space.settings patch
    try:
        space = detect_current_battle_space()
        if space:
            apply_preset_to_space(space, preset_id)
            methods_worked.append("re-patched space.settings(%s)" % space)
    except Exception:
        pass

    if methods_worked:
        logger.info("apply_preset_in_battle: worked methods = %s", methods_worked)
        return True
    else:
        logger.warning("apply_preset_in_battle: NO method worked, dumping watchers")
        _dump_watchers()
        return False


def _dump_watchers():
    """Дамп watcher-tree щоб побачити реальні шляхи."""
    if not IN_GAME:
        return
    try:
        for root in ("", "Client Settings", "Render", "Space", "Environment", "Visual", "chunks"):
            try:
                result = BigWorld.getWatcher(root + "/" if root else "")
                logger.info("WATCHER [%s/]: %s", root, repr(result)[:500])
            except Exception as e:
                logger.debug("watcher root '%s' failed: %s", root, e)
    except Exception:
        logger.exception("dump_watchers failed")


class WeatherController(object):

    def __init__(self):
        self.config = WeatherConfig()
        self._current_space = None
        self._current_preset = None
        self._in_battle = False

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

    # ---- Викликається з hook на BattleSpace.enter() / BattleLoadingSpace.enter() ----
    def on_battle_space_entered(self, space_class_name):
        """Входимо в BattleLoadingSpace або BattleSpace."""
        logger.info("on_battle_space_entered: %s", space_class_name)
        self._in_battle = True
        # Тут ще немає arena, тому _current_space визначимо пізніше

    def on_space_about_to_load(self, space_name):
        """Старий hook (legacy), залишено про всяк."""
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
        """
        Натиснуто хоткей. Спочатку детектимо карту.
        """
        # Визначаємо карту зараз
        detected = detect_current_battle_space()

        if not detected and not self._in_battle:
            logger.info("cycle_preset: not in battle (no space detected, _in_battle=False)")
            # Все одно покажемо дебаг-дамп — хочемо бачити, що у нас є
            _dump_watchers()
            return

        if detected:
            self._current_space = detected

        try:
            idx = PRESET_ORDER.index(self._current_preset or "standard")
        except ValueError:
            idx = 0
        next_preset = PRESET_ORDER[(idx + 1) % len(PRESET_ORDER)]
        self._current_preset = next_preset

        logger.info("cycle_preset: switching to %s (space=%s, in_battle=%s)",
                    next_preset, self._current_space, self._in_battle)

        ok = apply_preset_in_battle(next_preset)

        if IN_GAME:
            try:
                msg = u"Погода: %s" % PRESET_LABELS[next_preset]
                if not ok:
                    msg += u" (не вдалося)"
                SystemMessages.pushI18nMessage(
                    msg,
                    type=SystemMessages.SM_TYPE.Information,
                )
            except Exception:
                pass


g_controller = WeatherController()
