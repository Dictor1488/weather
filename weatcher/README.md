# Weather Panel — WoT Mod

Панель керування погодними пресетами для World of Tanks. Працює поверх `environments_*.wotmod` модів (midday / sunset / overcast / midnight).

## Структура репо (в стилі UnderPressurePH7/Mastery)

```
.
├── .github/workflows/build.yml       # Авто-збірка на push тега vX.Y.Z
├── as3/
│   ├── src/weather/                  # ActionScript 3 сирці
│   │   ├── data/                     # PresetVO, MapVO
│   │   ├── events/                   # WeatherEvent
│   │   ├── components/               # PresetRow, MapTile
│   │   ├── views/                    # WeatherView + 3 panels
│   │   └── WeatherMediator.as        # Entry point (DAAPI bridge)
│   └── libs/                         # ⚠️ WoT SWC-файли — у .gitignore
├── python/gui/mods/                  # Python 2.7 сирці
│   ├── mod_weather.py                # Loader (WoT авто-завантажує все з mod_*.py)
│   ├── weather_controller.py         # Ядро: конфіг + рандомайзер
│   └── weather_window.py             # DAAPI view
├── resources/in/mods/com.example.weather/
│   ├── meta.xml                      # Метадані моду
│   ├── configs/weather_mod.json      # Дефолтний конфіг
│   └── gui/flash/                    # (тут опиниться скомпільований .swf)
├── build.py                          # Локальна збірка
└── .gitignore
```

## Як це працює (принцип Mastery)

### Збірка локально

```bash
# 1. Витягти WoT SWC з клієнта у as3/libs/:
#    scaleformgfx.swc, wg_framework.swc, wg_gui.swc і подібні
#    (зазвичай у World_of_Tanks/res/scripts/ або у res_mods)

# 2. Встановити Apache Flex SDK (4.16.1 або новіший)
export FLEX_HOME=/path/to/flex-sdk

# 3. Збудувати
python2.7 build.py
# → dist/com.example.weather_0.0.1.wotmod
```

### Збірка через GitHub Actions

Репо налаштоване на **автозбірку на теги**:

```bash
git tag v0.0.1
git push origin v0.0.1
```

Actions:
1. Стягне Flex SDK (кешується між білдами)
2. Встановить Python 2.7
3. Запустить `build.py --version 0.0.1`
4. Опублікує `.wotmod` як артефакт і створить GitHub Release

## ⚠️ Що треба доробити перед першою збіркою

1. **Покласти WoT SWC у `as3/libs/`**
   Flex-компілятор без них не зможе знайти класи типу `net.wg.infrastructure.base.AbstractView` чи `scaleform.clik.controls.Slider`. Ці файли не комітяться у репо (див. `.gitignore`) — кожен розробник дістає їх зі своєї інсталяції WoT.

2. **Поміняти `com.example` на свій author_id**
   - `resources/in/mods/com.example.weather/` → перейменувати папку
   - `meta.xml` → правити `<id>`
   - `build.py` → константа `MOD_ID_DIR`

3. **Допилити `apply_preset_to_space()` у `weather_controller.py`**
   Це єдина частина, яка залежить від поточної версії WoT — там треба точний патч `space.settings`. У поточному коді — скелет з коментарями.

4. **Іконка моду** (необов'язково)
   Для `modsListAPI` треба додати 48×48 PNG у `resources/in/mods/com.example.weather/gui/flash/icon.png`.

## Встановлення зібраного `.wotmod`

```
World_of_Tanks/mods/<game_version>/com.example.weather_0.0.1.wotmod
```

Разом з цим мають бути встановлені **оригінальні погодні моди**:
- `environments_common_1_7.wotmod`
- `environments_midday_1_9.wotmod`
- `environments_sunset_1_9.wotmod`
- `environments_overcast_1_9.wotmod`
- `environments_midnight_1_9.wotmod`
- `environments_spaces_wg_1_6.wotmod`

Моя панель сама нічого не малює — вона тільки керує вибором між GUID'ами, які лежать у цих модах.

## Ліцензія

MIT (або що обереш).
