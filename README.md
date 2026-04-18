# Weather Panel — WoT Mod (v2)

Панель керування погодними пресетами для World of Tanks. Працює поверх `environments_*.wotmod` модів (midday / sunset / overcast / midnight).

## 🎯 Що змінилось у v2

Спочатку план був робити власний AS3 UI через Scaleform + DAAPI. Після розпакування прикладів (`izeberg.modssettingsapi`, `tv.protanki.stuff`) зрозуміли, що існує готовий фреймворк **modsSettingsApi**, який сам малює UI налаштувань з dict-шаблону.

**Результат:** AS3 не потрібен. Компілюється тільки Python. GitHub Actions зберуть все за ~30 секунд без жодних додаткових файлів.

## Структура

```
.
├── .github/workflows/build.yml      # Auto-build на тег vX.Y.Z
├── python/gui/mods/                 # Python 2.7 сирці
│   ├── __init__.py                  # Маркер пакета
│   ├── mod_weather.py               # Entry: реєстрація в modsSettingsApi
│   └── weather_controller.py        # Ядро: конфіг + рандомайзер + патч карт
├── resources/in/mods/com.example.weather/
│   ├── meta.xml                     # Метадані моду
│   └── configs/weather_mod.json     # Дефолтний конфіг
├── build.py                         # Локальна збірка
├── .gitignore
└── README.md
```

## Як це працює

1. При старті гри `mod_weather.py` викликає `g_modsSettingsApi.setModTemplate(...)` із dict-шаблоном: слайдери пресетів + дропдаун карт + хоткей
2. modsSettingsApi сам малює панель у своєму вікні (те саме, що відкривається шестернею в ангарі)
3. Користувач крутить слайдери — API викликає наш callback → контролер зберігає зміни в `weather_mod.json`
4. Перед завантаженням карти `BWPersonality.onSpaceLoaded` хук запитує у контролера "який пресет на цю карту?" — рандомайзер обирає за вагами, потім `apply_preset_to_space()` підкладає GUID у `space.settings`
5. У бою ALT+F12 циклічно перемикає пресет через `cycle_preset_in_battle()`

## Залежності (клієнт гравця мусить мати)

- **`izeberg.modssettingsapi`** (>= 1.7.0) — інакше наш виклик `g_modsSettingsApi.setModTemplate(...)` кине `ImportError` і панель не з'явиться.
- **`environments_*.wotmod`** — саме погодні пресети (`midday_1_9`, `sunset_1_9`, `overcast_1_9`, `midnight_1_9`, `common_1_7`, `spaces_wg_1_6`). Без них GUID'и порожні.

## Локальна збірка

```bash
# На Python 2.7 (Linux/Mac)
python2.7 build.py

# → dist/com.example.weather_0.0.1.wotmod
```

## Збірка через GitHub Actions

```bash
git tag v0.0.1
git push origin v0.0.1
```

Actions встановлять Python 2.7, запустять `build.py`, створять GitHub Release.

## TODO перед першим релізом

1. **Змінити `com.example` на свій author_id**
   - `resources/in/mods/com.example.weather/` — перейменувати папку
   - `meta.xml` — правити `<id>`
   - `build.py` — константа `MOD_ID_DIR`
   - `mod_weather.py` — константа `MOD_LINKAGE`

2. **Допилити `apply_preset_to_space()` у `weather_controller.py`**
   Єдине місце, яке залежить від версії клієнта — там треба точний патч `space.settings` через `ResMgr`.

3. **Підтягнути всі 48 карт з `ResMgr`** замість хардкоду 4-х у `_build_maps_column()`.

## Встановлення

Покласти в `World_of_Tanks/mods/<game_version>/` разом з:
- `izeberg.modssettingsapi_X.X.X.wotmod`
- `environments_common_1_7.wotmod`
- `environments_midday_1_9.wotmod`
- `environments_sunset_1_9.wotmod`
- `environments_overcast_1_9.wotmod`
- `environments_midnight_1_9.wotmod`
- `environments_spaces_wg_1_6.wotmod`

## Ліцензія

MIT
