# Weather Mods Panel — AS3 + Python для World of Tanks

Панель керування погодними пресетами на картах. Інтегрується з уже встановленими `environments_*.wotmod` модами (midday / sunset / overcast / midnight).

## Що робить

- Вкладка **"Загальні налаштування"** — зважений рандомайзер пресетів для всіх карт одразу
- Вкладка **"Налаштування по картах"** — сітка 4×N, клік по карті → індивідуальні ваги
- Хоткей **ALT+F12** — перемикання пресета прямо в бою
- Зберігає вибір у `mods/configs/weather_mod.json`

## Структура

```
weather_mod/
├── as3/                          # Flash/Scaleform UI
│   ├── data/
│   │   ├── PresetVO.as           # Value object пресета (id, weight, guid, preview)
│   │   └── MapVO.as              # Value object карти (id, label, thumb, presets)
│   ├── events/
│   │   └── WeatherEvent.as       # Типізовані кастомні події
│   ├── components/
│   │   ├── PresetRow.as          # Рядок "Лейбл | Слайдер | вес: N | preview"
│   │   └── MapTile.as            # Плитка карти в сітці
│   ├── views/
│   │   ├── WeatherView.as        # Корінь: tabs + close + content holder
│   │   ├── GlobalSettingsPanel.as  # Вкладка "Загальні" (5 слайдерів + hotkey)
│   │   ├── MapGridPanel.as       # Вкладка "По картах" (сітка 4×N)
│   │   └── MapDetailPanel.as     # Деталі однієї карти (5 слайдерів)
│   └── WeatherMediator.as        # DAAPI-міст Flash ⇄ Python
│
└── python/
    ├── weather_controller.py     # Core: конфіг, рандомайзер, патч space.settings
    ├── weather_window.py         # DAAPI view з py_* колбеками
    └── __init__.py               # Хуки на завантаження карти та хоткей
```

## Архітектура (dataflow)

```
┌─────────────────┐       as_setData()        ┌──────────────────┐
│ weather_window  │──────────────────────────>│  WeatherView.as  │
│     (Python)    │                            │                  │
│                 │<──  py_onWeightChanged ────│  PresetRow.as    │
└────────┬────────┘                            └──────────────────┘
         │ on_weight_changed()
         ▼
┌─────────────────┐
│ WeatherConfig   │  ──── зберігає у weather_mod.json
└────────┬────────┘
         │ get_weights_for_map()
         ▼
┌─────────────────┐       pick_preset()        ┌──────────────────┐
│ on_space_about  │──────────────────────────>│ apply_preset_to  │
│   _to_load()    │                            │   _space()       │
└─────────────────┘                            └──────┬───────────┘
                                                      ▼
                                           патч space.settings
                                           → гра вантажить потрібний GUID
```

## Ключові моменти реалізації

### 1. GUID пресетів
У `weather_controller.py` захардкоджено GUID'и, які ми витягли з `.wotmod` файлів:
```python
PRESET_GUIDS = {
    "standard": None,                                       # не підміняти
    "midday":   "BF040BCB-4BE1D04F-7D484589-135E881B",
    "sunset":   "6DEE1EBB-44F63FCC-AACF6185-7FBBC34E",
    "overcast": "56BA3213-40FFB1DF-125FBCAD-173E8347",
    "midnight": "15755E11-4090266B-594778B6-B233C12C",
}
```
Якщо завтра оновиш environments-мод — поміняй GUID тут.

### 2. Рандомайзер
`pick_preset(weights)` — класична "рулетка": чим більша вага, тим вища ймовірність. Сума всіх ваг = 100% незалежно від абсолютних значень. Протестовано:
- всі по 20 → рівноймовірний розподіл
- midday=15, sunset=5 → 75% midday, 25% sunset
- усі 0 → завжди `standard`

### 3. DAAPI bridge
AS3 `WeatherMediator` успадковує `AbstractView`. Python-клас `WeatherWindowMeta` має методи `py_onWeightChanged`, `py_onMapSelected` тощо — WoT сам маршрутизує виклики з AS3 через `self.flashObject`.

### 4. Хоткей у бою
Хукаємо `InputHandler.g_instance.onKeyDown`. Коли натиснуто ALT+F12 — `cycle_preset_in_battle()` циклічно перемикає пресети і показує повідомлення через `SystemMessages`.

## TODO для продакшену

- ⚠️ `apply_preset_to_space()` зараз містить демо-реалізацію патчу `space.settings`. Точні теги (`<environment>` / `<timeOfDay>`) залежать від поточної версії WoT — треба звіряти з актуальним клієнтом.
- 📋 `MAP_REGISTRY` у `weather_window.py` заповнений тільки для 4 карт як приклад. У продакшені замість хардкоду парсити `ResMgr.openSection("spaces/").keys()` і підтягувати імена з `text/LC_MESSAGES/arenas.mo`.
- 🖼 Preview-картинки пресетів (`previewSrc`) треба покласти у `gui/maps/weather_previews/` — 220×64 кропи тих 5 скріншотів з різною погодою.
- 🎨 Шрифти `$FieldFont` / `$TitleFont` — це аліаси, зареєстровані в Scaleform шаблоні WoT. У standalone-збірці їх треба замінити на звичайні системні.
- 🔌 `izeberg.modssettingsapi` API змінюється між версіями. Перевір актуальну сигнатуру `registerCallback()` у тій версії API, яка в тебе встановлена (у нас `1.7.0`).

## Збірка

1. **AS3**: відкрити у Flash Builder / IntelliJ Flash, скомпілювати в `WeatherMediator.swf` з Scaleform SDK WoT.
2. **Python**: скопіювати весь `python/` у `mods/<version>/weather_mod/`.
3. **SWF**: покласти `WeatherMediator.swf` у `mods/<version>/weather_mod/gui/flash/`.
4. Перепакувати як `.wotmod` (це ж zip).

## Тест без гри

Python-частина перевіряється без клієнта — заглушки `IN_GAME = False` дозволяють імпортувати модулі та ганяти рандомайзер:

```bash
cd python/
python -c "from weather_controller import pick_preset, PRESET_ORDER; \
           print(pick_preset({p: 20 for p in PRESET_ORDER}))"
```
