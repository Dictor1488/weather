# -*- coding: utf-8 -*-
"""
Weather Mods Controller — керування погодними пресетами в World of Tanks.

АРХІТЕКТУРА:
    1. Користувач відкриває панель в ангарі (шестерня → "Погода на картах").
    2. Python надсилає поточний стан (ваги, карти, хоткей) у Flash через DAAPI.
    3. Користувач крутить слайдери — Flash кидає py_onWeightChanged → ми
       оновлюємо словник у пам'яті та зберігаємо на диск (JSON).
    4. Перед завантаженням бою перехоплюємо подію "space about to load" і
       переписуємо <spaceName>/space.settings так, щоб <environment>
       вказував на потрібний GUID (з ремода або оригінал).
    5. Під час бою по хоткею (ALT+F12) перемикаємо пресет "на льоту"
       через BigWorld.setWatcher().

Мод працює разом із твоїми 6 .wotmod файлами — він не *створює* пресети,
лише *вибирає між* наявними GUID'ами.
"""

import json
import os
import random
import logging
from functools import partial

# WoT імпорти — ці модулі доступні лише у грі.
# У режимі розробки/тестів вони підміняються заглушками нижче.
try:
    import BigWorld
    import ResMgr
    from gui import SystemMessages
    from Keys import KEY_F12, KEY_LALT
    IN_GAME = True
except ImportError:
    IN_GAME = False

logger = logging.getLogger("weather_mod")
logger.setLevel(logging.INFO)


# ============================================================================
# КОНСТАНТИ: GUID'и пресетів з .wotmod файлів
# ============================================================================
# Ці значення ми витягнули з розпакованих .wotmod архівів
# (імена папок усередині res/spaces/<map>/environments/).
# standard = None → не підміняти, використати оригінальний environment гри.
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

# Порядок, в якому пресети мають з'являтися у UI (як на скріні)
PRESET_ORDER = ["standard", "midnight", "overcast", "sunset", "midday"]

MAX_WEIGHT = 20

# Шлях, куди зберігаємо вибір користувача
CONFIG_PATH = os.path.join("mods", "configs", "weather_mod.json")


# ============================================================================
# MODEL: WeatherConfig — зберігає та завантажує налаштування користувача
# ============================================================================
class WeatherConfig(object):
    """
    Структура:
        {
            "global": {"standard": 20, "midnight": 0, "overcast": 0, "sunset": 0, "midday": 0},
            "maps": {
                "02_malinovka": {
                    "useGlobal": False,
                    "weights": {"standard": 10, "midnight": 0, "overcast": 0, "sunset": 10, "midday": 0}
                }
            },
            "hotkey": ["KEY_LALT", "KEY_F12"]
        }
    """

    def __init__(self):
        self.global_weights = {pid: MAX_WEIGHT if pid == "standard" else 0
                               for pid in PRESET_ORDER}
        self.map_overrides = {}   # mapId -> {"useGlobal": bool, "weights": {pid: int}}
        self.hotkey = ["KEY_LALT", "KEY_F12"]
        self.load()

    def load(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r") as f:
                    data = json.load(f)
                self.global_weights.update(data.get("global", {}))
                self.map_overrides = data.get("maps", {})
                self.hotkey = data.get("hotkey", self.hotkey)
                logger.info("Weather config loaded from %s", CONFIG_PATH)
        except Exception as e:
            logger.exception("Failed to load weather config: %s", e)

    def save(self):
        try:
            if not os.path.exists(os.path.dirname(CONFIG_PATH)):
                os.makedirs(os.path.dirname(CONFIG_PATH))
            data = {
                "global": self.global_weights,
                "maps": self.map_overrides,
                "hotkey": self.hotkey,
            }
            with open(CONFIG_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.exception("Failed to save weather config: %s", e)

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
        """Повертає активний набір ваг для конкретної карти (з fallback на global)."""
        override = self.map_overrides.get(map_id)
        if override and not override.get("useGlobal", True):
            return override["weights"]
        return self.global_weights


# ============================================================================
# RANDOMIZER: зважений вибір пресета за "рулеткою"
# ============================================================================
def pick_preset(weights):
    """
    weights: {"standard": 10, "midnight": 0, ...}
    Повертає preset_id за ймовірностями (roulette wheel).
    Якщо всі ваги 0 — повертає 'standard'.
    """
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


# ============================================================================
# ENVIRONMENT PATCHER: переписуємо space.settings перед завантаженням карти
# ============================================================================
def apply_preset_to_space(space_name, preset_id):
    """
    WoT-специфіка: клієнт читає <space>/space.settings, там є секція,
    що визначає environment. Нам треба перед завантаженням карти
    підкласти нашу версію space.settings, яка прив'яже гру до потрібного GUID.

    У реальному моді це робиться через перехоплення
    BWPersonality.onSpaceLoaded або через ResMgr hook.

    Нижче — спрощена логіка: ми формуємо патч у вигляді XML-дочірнього
    елемента і запихаємо його в ResMgr. В продакшені замість прямого
    запису файлу на диск використовують ResMgr.DataSection.writeString().
    """
    guid = PRESET_GUIDS.get(preset_id)
    if guid is None:
        logger.info("[%s] Standard preset — no override", space_name)
        return

    if not IN_GAME:
        logger.info("[DEV] Would apply %s (guid=%s) to %s", preset_id, guid, space_name)
        return

    try:
        path = "spaces/%s/space.settings" % space_name
        section = ResMgr.openSection(path)
        if section is None:
            logger.warning("space.settings not found for %s", space_name)
            return
        # У реальності тут прописується шлях до папки environments/<guid>/
        # у секції <environment> або <timeOfDay>. Точні теги залежать від
        # версії клієнта; цей код — demonstration scaffolding.
        section.writeString("environment/override", guid)
        section.save()
        logger.info("[%s] Applied preset %s (guid=%s)", space_name, preset_id, guid)
    except Exception as e:
        logger.exception("Failed to patch space.settings: %s", e)


# ============================================================================
# CONTROLLER: єдиний інстанс, до якого звертаються і AS3, і хоткеї
# ============================================================================
class WeatherController(object):

    def __init__(self):
        self.config = WeatherConfig()
        self._current_space = None
        self._current_preset = None

    # ---------- API, яке викликає AS3 через DAAPI ----------

    def on_weight_changed(self, map_id, preset_id, value):
        """
        Викликається з Flash, коли користувач рухає слайдер.
        map_id=None → глобальна вага; інакше — для конкретної карти.
        """
        logger.info("weight_changed: map=%s preset=%s value=%s", map_id, preset_id, value)
        if map_id is None:
            self.config.set_global_weight(preset_id, value)
        else:
            self.config.set_map_weight(map_id, preset_id, value)

    def on_map_selected(self, map_id):
        logger.info("map_selected: %s", map_id)

    def on_close_requested(self):
        logger.info("user closed weather panel")
        self.config.save()

    # ---------- API для AS3: що показати при відкритті вікна ----------

    def build_payload(self, available_maps):
        """
        available_maps: список (map_id, label, thumb_src) — у реальному моді
        він витягається з ResMgr.openSection("spaces/").ls().

        Повертає dict, який летить у AS3 через as_setData().
        """
        def presets_for(weights, previews=None):
            previews = previews or {}
            return [{
                "id": pid,
                "label": PRESET_LABELS[pid],
                "guid": PRESET_GUIDS[pid],
                "weight": weights.get(pid, 0),
                "previewSrc": previews.get(pid, ""),
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
            "hotkey": "+".join(k.replace("KEY_", "").replace("L", "") for k in self.config.hotkey),
        }

    # ---------- Life-cycle: коли гра завантажує карту ----------

    def on_space_about_to_load(self, space_name):
        """
        Хук з BWPersonality / ArenaInfoHolder. Тут ми вирішуємо,
        який пресет застосувати до карти, що вантажиться.
        """
        self._current_space = space_name
        weights = self.config.get_weights_for_map(space_name)
        preset = pick_preset(weights)
        self._current_preset = preset
        apply_preset_to_space(space_name, preset)
        return preset

    # ---------- Hotkey: перемикання в бою ----------

    def cycle_preset_in_battle(self):
        """Викликається з keyboard-хендлера. Міняє пресет на наступний."""
        if not self._current_space:
            return
        try:
            idx = PRESET_ORDER.index(self._current_preset or "standard")
        except ValueError:
            idx = 0
        next_preset = PRESET_ORDER[(idx + 1) % len(PRESET_ORDER)]
        self._current_preset = next_preset
        apply_preset_to_space(self._current_space, next_preset)
        if IN_GAME:
            SystemMessages.pushI18nMessage(
                "Погода: %s" % PRESET_LABELS[next_preset],
                type=SystemMessages.SM_TYPE.Information,
            )


# Синглтон контролера — використовується з усіх точок входу
g_controller = WeatherController()
