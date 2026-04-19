# -*- coding: utf-8 -*-
"""
Weather controller v3.0
======================
ДВІ НЕЗАЛЕЖНІ СИСТЕМИ:

1. РАНДОМІЗАТОР ENVIRONMENTS (midday/sunset/overcast/midnight)
   - Спрацьовує при Avatar.onEnterWorld (хук в __init__.py)
   - Вибирає пресет за вагами з налаштувань
   - Записує GUID через ResMgr.writeString (патч у пам'яті VFS)
   - Примітка: WoT читає space.settings ДО Python, тому патч для
     НАСТУПНОГО бою. Або використати фізичний запис у res_mods/.

2. WEATHER SYSTEMS ХОТКЕЙ (Clear/Cloudy/Stormy/Hail)
   - F12 у бою → циклічно перемикає Weather system
   - Використовує Weather._weatherSystemsForCurrentSpace() +
     Weather.override(system_object)
   - Це РЕАЛЬНО ПРАЦЮЄ і дає живу зміну атмосфери
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

# ============================================================================
# Environment пресети (midday/sunset/overcast/midnight)
# GUID — папка у environments_*.wotmod
# ============================================================================
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

# ============================================================================
# Weather Systems (Clear/Cloudy/Stormy/Hail)
# Реальні імена з _weatherSystemsForCurrentSpace() у бою
# ============================================================================
# Стандартні імена weather systems у WoT (карта може мати різний підбір)
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


# ============================================================================
# Config
# ============================================================================
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


# ============================================================================
# Helpers
# ============================================================================
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


# ============================================================================
# Weather Systems API (реально працює у бою)
# ============================================================================
def _get_weather_for_space():
    """
    Повертає ініціалізований Weather об'єкт для поточного простору.
    Weather.currentSpaceID має збігатись з player.spaceID.
    """
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
            current = getattr(w, 'currentSpaceID', -1)
            if current != space_id:
                on_change = getattr(w, 'onChangeSpace', None)
                if callable(on_change):
                    try:
                        on_change(space_id)
                    except Exception:
                        pass
        return w
    except Exception:
        return None


def get_available_weather_systems():
    """Повертає список доступних weather systems для поточної карти."""
    w = _get_weather_for_space()
    if w is None:
        return []
    try:
        fn = getattr(w, '_weatherSystemsForCurrentSpace', None)
        if callable(fn):
            return fn() or []
    except Exception:
        pass
    return []


def apply_weather_system(system_obj):
    """Застосовує weather system через Weather.override(system_object)."""
    w = _get_weather_for_space()
    if w is None or system_obj is None:
        return False
    try:
        override_fn = getattr(w, 'override', None)
        if callable(override_fn):
            override_fn(system_obj)
            name = getattr(system_obj, 'name', repr(system_obj)[:30])
            logger.info("OK: Weather.override(%s)", name)
            return True
    except Exception as e:
        logger.warning("Weather.override failed: %s", e)
    return False


# ============================================================================
# Environment preset apply (при вході в бій)
# ============================================================================
def apply_environment_preset(space_name, preset_id):
    """
    Патчимо space.settings в пам'яті VFS.
    Спрацьовує при Avatar.onEnterWorld — але WoT вже прочитав space.settings
    до цього хука. Тому цей патч впливатиме на наступний бій (якщо простір
    перезавантажується) або не матиме ефекту (якщо VFS кешований).

    TODO для повної роботи: записувати в res_mods/<ver>/spaces/<map>/
    фізичний файл з потрібним GUID перед боєм.
    """
    guid = PRESET_GUIDS.get(preset_id)
    if not guid or not IN_GAME:
        return

    try:
        path = 'spaces/%s/space.settings' % space_name
        section = ResMgr.openSection(path)
        if section is None:
            logger.warning("space.settings not found for %s", space_name)
            return
        section.writeString('environment/override', guid)
        logger.info("preset %s applied to %s (guid=%s) — active next battle",
                    preset_id, space_name, guid)
    except Exception:
        logger.debug("apply_environment_preset failed\n%s", _fmt_exc())


# ============================================================================
# Controller
# ============================================================================
class WeatherController(object):

    def __init__(self):
        self.config = WeatherConfig()
        self._current_space = None
        self._current_preset = None
        self._current_weather_idx = 0   # індекс у списку weather systems

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
        """
        Викликається з Avatar.onEnterWorld хука.
        Вибираємо environment пресет і патчимо VFS.
        """
        normalized = normalize_space_name(space_name)
        if not is_battle_map_space(normalized):
            return

        self._current_space = normalized
        self._current_weather_idx = 0  # скидаємо індекс weather при вхді в новий бій

        weights = self.config.get_weights_for_map(normalized)
        preset = pick_preset(weights)
        self._current_preset = preset

        logger.info("onEnterWorld: space=%s -> preset=%s", normalized, preset)
        apply_environment_preset(normalized, preset)

    def cycle_weather_in_battle(self):
        """
        Хоткей F12 у бою: перемикаємо WEATHER SYSTEM (Clear/Cloudy/Stormy/Hail).
        Це реально змінює атмосферні ефекти в реальному часі.
        """
        if not detect_current_battle_space():
            logger.info("cycle_weather: not in battle")
            return

        systems = get_available_weather_systems()
        if not systems:
            logger.warning("No weather systems available for current space")
            return

        # Циклічно перемикаємо
        self._current_weather_idx = (self._current_weather_idx + 1) % len(systems)
        target = systems[self._current_weather_idx]
        name = getattr(target, 'name', str(self._current_weather_idx))

        ok = apply_weather_system(target)

        # Показуємо повідомлення
        try:
            label = WEATHER_SYSTEM_LABELS.get(name, name)
            msg = u"Атмосфера: %s" % label
            if not ok:
                msg += u" (помилка)"
            SystemMessages.pushI18nMessage(
                msg,
                type=SystemMessages.SM_TYPE.Information,
            )
        except Exception:
            pass

        logger.info("cycle_weather: [%d/%d] %s -> ok=%s",
                    self._current_weather_idx + 1, len(systems), name, ok)


g_controller = WeatherController()
