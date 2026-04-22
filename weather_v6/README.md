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
