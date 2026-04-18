# -*- coding: utf-8 -*-
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
    "standard": u"\u0421\u0442\u0430\u043d\u0434\u0430\u0440\u0442",
    "midnight": u"\u041d\u0456\u0447",
    "overcast": u"\u041f\u0430\u0441\u043c\u0443\u0440\u043d\u043e",
    "sunset":   u"\u0417\u0430\u043a\u0430\u0442",
    "midday":   u"\u041f\u043e\u043b\u0434\u0435\u043d\u044c",
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
        # FIX 1: hotkey зберігається як список int-кодів BigWorld Keys
        # за замовчуванням — ALT+F12
        self.hotkey_codes = []  # заповнюється після load(), бо Keys може не бути поза грою
        self.hotkey_str = "ALT+F12"  # для відображення в UI
        self.load()

    def load(self):
        try:
            if os.path.isfile(CONFIG_PATH):
                with open(CONFIG_PATH, 'r') as f:
                    data = json.load(f)
                self.global_weights.update(data.get('global', {}))
                self.map_overrides = data.get('maps', {})
                # hotkey зберігається як список BigWorld Key-кодів (int)
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
        space_name = space_name[len('spaces/'): ]
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

def apply_preset_to_space(space_name, preset_id):
    """Патчимо space.settings перед завантаженням карти."""
    guid = PRESET_GUIDS.get(preset_id)
    if guid is None:
        logger.info("[%s] Standard preset — no override", space_name)
        return
    if not IN_GAME:
        logger.info("[DEV] Would apply %s to %s", preset_id, space_name)
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
    FIX 2: Зміна погоди під час бою — через BigWorld.setWatcher,
    який змінює environment на льоту без перезавантаження карти.
    """
    guid = PRESET_GUIDS.get(preset_id)
    if not IN_GAME:
        logger.info("[DEV] Would switch battle preset to %s", preset_id)
        return
    try:
        if guid is not None:
            # Шлях watcher'а для override середовища — актуальний для WoT 2.x
            BigWorld.setWatcher("Client Settings/environmentOverride", guid)
        else:
            # Скидаємо override (стандарт)
            BigWorld.setWatcher("Client Settings/environmentOverride", "")
        logger.info("Battle preset switched to %s (guid=%s)", preset_id, guid)
    except Exception:
        logger.exception("Failed to switch battle preset")


class WeatherController(object):

    def __init__(self):
        self.config = WeatherConfig()
        self._current_space = None
        self._current_preset = None

    # ---------- API для AS3 через DAAPI ----------

    def on_weight_changed(self, map_id, preset_id, value):
        logger.info("weight_changed: map=%s preset=%s value=%s", map_id, preset_id, value)
        if not map_id:
            self.config.set_global_weight(preset_id, value)
        else:
            self.config.set_map_weight(map_id, preset_id, value)

    def on_map_selected(self, map_id):
        logger.info("map_selected: %s", map_id)

    def on_close_requested(self):
        logger.info("user closed weather panel")
        self.config.save()

    def on_hotkey_changed(self, key_codes, hotkey_str):
        """
        FIX 1: Зберігаємо новий хоткей з UI.
        key_codes — список int (BigWorld Key codes)
        hotkey_str — рядок для відображення ("ALT+F12")
        """
        self.config.hotkey_codes = [int(c) for c in key_codes]
        self.config.hotkey_str = hotkey_str
        self.config.save()
        logger.info("Hotkey updated: %s codes=%s", hotkey_str, key_codes)

    def build_payload(self, available_maps):
        def presets_for(weights):
            return [{
                "id": pid,
                "label": PRESET_LABELS[pid],
                "guid": PRESET_GUIDS[pid] or "",
                "weight": weights.get(pid, 0),
                "previewSrc": "",
            } for pid in PRESET_ORDER]

        maps_payload = []
        for map_id, label, thumb in available_maps:
            override = self.config.map_overrides.get(map_id, {})
            weights = override.get("weights", {pid: 0 for pid in PRESET_ORDER})
            maps_payload.append({
                "id": map_id,
                "label": label,
                "thumbSrc": thumb,
                "useGlobal": override.get("useGlobal", True),
                "presets": presets_for(weights),
            })

        return {
            "presets": presets_for(self.config.global_weights),
            "maps": maps_payload,
            "hotkey": self.config.hotkey_str,
            # передаємо коди щоб AS3 міг показати правильні клавіші
            "hotkeyKeys": self.config.hotkey_codes,
        }

    # ---------- Завантаження карти ----------

    def on_space_about_to_load(self, space_name):
        normalized = normalize_space_name(space_name)
        logger.info("Space about to load: raw=%s normalized=%s", space_name, normalized)
        if not is_battle_map_space(normalized):
            logger.info("Skipping non-battle space: %s", normalized or space_name)
            return None
        self._current_space = normalized
        weights = self.config.get_weights_for_map(normalized)
        preset = pick_preset(weights)
        self._current_preset = preset
        apply_preset_to_space(normalized, preset)
        return preset

    # ---------- Хоткей у бою ----------

    def cycle_preset_in_battle(self):
        """FIX 2: перемикаємо пресет через BigWorld.setWatcher, не через space.settings."""
        if not self._current_space:
            return
        try:
            idx = PRESET_ORDER.index(self._current_preset or "standard")
        except ValueError:
            idx = 0
        next_preset = PRESET_ORDER[(idx + 1) % len(PRESET_ORDER)]
        self._current_preset = next_preset
        apply_preset_in_battle(next_preset)
        if IN_GAME:
            try:
                SystemMessages.pushI18nMessage(
                    u"Погода: %s" % PRESET_LABELS[next_preset],
                    type=SystemMessages.SM_TYPE.Information,
                )
            except Exception:
                pass
        logger.info("Cycled to preset: %s", next_preset)


g_controller = WeatherController()
