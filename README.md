# Weather Mods Panel — українська збірка інтерфейсу

У цій збірці:
- увесь інтерфейс переведений українською;
- `Пасмурно` замінено на `Похмуро`;
- додано окремий пункт у нижньому меню модів через `modsListApi`;
- `open_weather_window()` тепер намагається відкрити окреме вікно `weather/WeatherPanel.swf`;
- оновлено AS3-екрани під стиль зі скрінів;
- додано локальний payload builder для DAAPI-вікна.

## Файли для заміни

Замінюй ці файли у своєму проєкті:

- `as3/WeatherMediator.as`
- `as3/components/MapTile.as`
- `as3/components/PresetRow.as`
- `as3/events/WeatherEvent.as`
- `as3/views/GlobalSettingsPanel.as`
- `as3/views/MapDetailPanel.as`
- `as3/views/MapGridPanel.as`
- `as3/views/WeatherView.as`
- `python/gui/mods/__init__.py`
- `python/gui/mods/weather_controller.py`
- `python/gui/mods/weather_window.py`

## Важливо

Щоб окреме вікно реально відкривалося, потрібно зібрати SWF і покласти його в:

`res_mods/<версія>/gui/flash/weather/WeatherPanel.swf`

або в ту структуру, яку ти використовуєш у своїй збірці.

## Іконка для нижнього меню модів

У код вже вбудовано base64-іконку з `modsList.png`.
Якщо `modsListApi` у клієнті відсутній, окремий пункт меню не з'явиться.
