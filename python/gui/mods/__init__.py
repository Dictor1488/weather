# -*- coding: utf-8 -*-
"""
Точка входу мода.
v1.2.0 — повний список карт (48 штук)
"""

try:
    import BigWorld
    import Keys
    from gui import InputHandler
    IN_GAME = True
except ImportError:
    IN_GAME = False

from weather_controller import g_controller


_SPACE_HOOKS = []
_KEY_HOOK_INSTALLED = False
_INIT_DONE = False


# ============================================================================
# Повний список карт (id, локалізована назва)
# ============================================================================
# Використовується і в dropdown панелі налаштувань, і для per-map ваг.
# MAP_IDS — список id у тому ж порядку, що й пункти dropdown.
# MAP_LABELS — відображувані назви.
# Перший елемент — порожній плейсхолдер "Оберіть карту".
ALL_MAPS = [
    ('',                       u'— Оберіть карту —'),
    ('01_karelia',             u'Карелія'),
    ('02_malinovka',           u'Малинівка'),
    ('03_campania_big',        u'Кампанія'),
    ('04_himmelsdorf',         u'Хіммельсдорф'),
    ('05_prohorovka',          u'Прохорівка'),
    ('06_ensk',                u'Енськ'),
    ('07_lakeville',           u'Лейквіль'),
    ('08_ruinberg',            u'Руїнберг'),
    ('10_hills',               u'Рудники'),
    ('11_murovanka',           u'Мурованка'),
    ('13_erlenberg',           u'Ерленберг'),
    ('14_siegfried_line',      u'Лінія Зігфріда'),
    ('17_munchen',             u'Мюнхен'),
    ('18_cliff',               u'Круча'),
    ('19_monastery',           u'Монастир'),
    ('23_westfeld',            u'Вестфілд'),
    ('28_desert',              u'Піщана ріка'),
    ('29_el_hallouf',          u'Ель-Халлуф'),
    ('31_airfield',            u'Летовище'),
    ('33_fjord',               u'Фіорди'),
    ('34_redshire',            u'Редшир'),
    ('35_steppes',             u'Степи'),
    ('36_fishing_bay',         u'Рибальська бухта'),
    ('37_caucasus',            u'Кавказ'),
    ('38_mannerheim_line',     u'Лінія Маннергейма'),
    ('44_north_america',       u'Лайв Окс'),
    ('45_north_america',       u'Хайвей'),
    ('47_canada_a',            u'Перлинна річка'),
    ('59_asia_great_wall',     u'Велика стіна'),
    ('60_asia_miao',           u'Тихий берег'),
    ('63_tundra',              u'Тундра'),
    ('90_minsk',               u'Мінськ'),
    ('95_lost_city_ctf',       u'Загублене місто'),
    ('99_poland',              u'Студзянки'),
    ('101_dday',               u'Нормандія (D-Day)'),
    ('105_germany',            u'Берлін'),
    ('112_eiffel_tower_ctf',   u'Париж'),
    ('114_czech',              u'Промзона'),
    ('115_sweden',             u'Кордон імперії'),
    ('121_lost_paradise_v',    u'Перевал'),
    ('127_japort',             u'Стара гавань'),
    ('128_last_frontier_v',    u'Фата-моргана'),
    ('208_bf_epic_normandy',   u'Оверлорд'),
    ('209_wg_epic_suburbia',   u'Крафтверк'),
    ('210_bf_epic_desert',     u'Застава'),
    ('212_epic_random_valley', u'Долина'),
    ('217_er_alaska',          u'Устрична затока'),
    ('222_er_clime',           u'Вайдпарк'),
]

MAP_IDS    = [m[0] for m in ALL_MAPS]
MAP_LABELS = [m[1] for m in ALL_MAPS]


def _log():
    import logging
    return logging.getLogger('weather_mod')


def _extract_space_name(args, kwargs):
    candidates = []
    if args:
        candidates.extend(args)
    if kwargs:
        for key in ('spaceName', 'space_name', 'spaceID', 'spaceId', 'name', 'path'):
            if key in kwargs:
                candidates.append(kwargs[key])
    for value in candidates:
        if isinstance(value, basestring):
            return value
    return None


def _patch_callable(module, attr_name):
    original = getattr(module, attr_name, None)
    if original is None or not callable(original):
        return False

    for entry in _SPACE_HOOKS:
        if entry[0] is module and entry[1] == attr_name:
            return True

    def wrapped(*args, **kwargs):
        space_name = _extract_space_name(args, kwargs)
        if space_name:
            try:
                g_controller.on_space_about_to_load(space_name)
            except Exception:
                _log().exception('space pre-load hook failed for %s', space_name)
        return original(*args, **kwargs)

    setattr(module, attr_name, wrapped)
    _SPACE_HOOKS.append((module, attr_name, original))
    _log().info('Installed weather space hook: %s.%s', getattr(module, '__name__', module), attr_name)
    return True


def _install_space_hook():
    if not IN_GAME or _SPACE_HOOKS:
        return

    installed = False

    try:
        import game
        for attr_name in ('loadSpace', 'startLoadingSpace', 'switchSpace', 'changeSpace', 'onSpaceLoaded'):
            installed = _patch_callable(game, attr_name) or installed
    except Exception:
        _log().exception('Failed while probing game module for space hooks')

    if not installed:
        try:
            import gui.app_loader.loader as app_loader_module
            for attr_name in ('notifySpaceChanged', 'onSpaceChanged'):
                installed = _patch_callable(app_loader_module, attr_name) or installed
        except Exception:
            _log().exception('Failed while probing app loader for space hooks')

    if not installed:
        _log().warning('No compatible space hook target found for WoT 2.2')


def _remove_space_hook():
    while _SPACE_HOOKS:
        module, attr_name, original = _SPACE_HOOKS.pop()
        try:
            setattr(module, attr_name, original)
        except Exception:
            _log().exception('Failed to remove space hook: %s.%s', getattr(module, '__name__', module), attr_name)


# ============================================================================
# Хоткей: обробка КЛАВІАТУРИ у БОЮ
# ============================================================================
# У бою InputHandler.g_instance.onKeyDown може не працювати.
# Тому слухаємо ще й через BigWorld.player() events, якщо вдасться.
def _on_key_event(event):
    if not IN_GAME:
        return
    if not hasattr(event, 'isKeyDown') or not event.isKeyDown():
        return

    codes = g_controller.config.hotkey_codes
    if not codes:
        # Дефолт ALT+F12
        if event.key == Keys.KEY_F12 and BigWorld.isKeyDown(Keys.KEY_LALT):
            g_controller.cycle_preset_in_battle()
        return

    trigger_key = codes[-1]
    modifiers = codes[:-1]
    if event.key != trigger_key:
        return
    for mod in modifiers:
        if not BigWorld.isKeyDown(mod):
            return
    g_controller.cycle_preset_in_battle()


def _install_key_hook():
    global _KEY_HOOK_INSTALLED
    if not IN_GAME or _KEY_HOOK_INSTALLED:
        return
    try:
        if getattr(InputHandler, 'g_instance', None) is not None:
            InputHandler.g_instance.onKeyDown += _on_key_event
            _KEY_HOOK_INSTALLED = True
            _log().info('Key hook installed (InputHandler.g_instance.onKeyDown)')
    except Exception:
        _log().exception('Failed to install key hook')


def _remove_key_hook():
    global _KEY_HOOK_INSTALLED
    if not IN_GAME or not _KEY_HOOK_INSTALLED:
        return
    try:
        if getattr(InputHandler, 'g_instance', None) is not None:
            InputHandler.g_instance.onKeyDown -= _on_key_event
    except Exception:
        _log().exception('Failed to remove key hook')
    _KEY_HOOK_INSTALLED = False


def open_weather_window():
    """Викликається з кнопки "..." у modsSettingsApi. Для MVP — нічого."""
    pass


# ============================================================================
# modsSettingsApi callback
# ============================================================================
def _on_settings_changed(linkage, newSettings):
    log = _log()
    log.debug('settings changed: %s', newSettings)

    preset_order = ['standard', 'midnight', 'overcast', 'sunset', 'midday']
    for pid in preset_order:
        key = 'global_' + pid
        if key in newSettings:
            g_controller.config.set_global_weight(pid, newSettings[key])

    map_idx = newSettings.get('active_map', 0)
    try:
        active_map = MAP_IDS[int(map_idx)]
    except (IndexError, TypeError, ValueError):
        active_map = ''

    if active_map:
        for pid in preset_order:
            key = 'map_' + pid
            if key in newSettings:
                g_controller.config.set_map_weight(active_map, pid, newSettings[key])

    if 'hotkey' in newSettings:
        raw = newSettings['hotkey']
        if isinstance(raw, (list, tuple)):
            codes = [int(c) for c in raw]
            try:
                import Keys as K
                name_map = {
                    K.KEY_LALT: 'ALT', K.KEY_RALT: 'ALT',
                    K.KEY_LCONTROL: 'CTRL', K.KEY_RCONTROL: 'CTRL',
                    K.KEY_LSHIFT: 'SHIFT', K.KEY_RSHIFT: 'SHIFT'
                }
                parts = [name_map.get(c, 'KEY_%d' % c) for c in codes]
                hotkey_str = '+'.join(parts)
            except Exception:
                hotkey_str = '+'.join(str(c) for c in codes)
            g_controller.on_hotkey_changed(codes, hotkey_str)


def _apply_saved_settings(saved):
    preset_order = ['standard', 'midnight', 'overcast', 'sunset', 'midday']
    for pid in preset_order:
        key = 'global_' + pid
        if key in saved:
            g_controller.config.global_weights[pid] = int(saved[key])
    if 'hotkey' in saved:
        raw = saved['hotkey']
        if isinstance(raw, (list, tuple)) and raw:
            _on_settings_changed('com.example.weather', {'hotkey': raw})


def init(*args, **kwargs):
    global _INIT_DONE
    if _INIT_DONE:
        return

    _install_space_hook()
    _install_key_hook()

    try:
        from gui.modsSettingsApi import g_modsSettingsApi
        from gui.modsSettingsApi import templates as t
        import Keys as K

        current_codes = g_controller.config.hotkey_codes or [K.KEY_LALT, K.KEY_F12]

        # Слайдери для глобальних налаштувань
        def make_preset_sliders(prefix, values_from_config):
            return [
                t.createSlider(varName=prefix + 'standard', text=u'Стандарт',
                               value=values_from_config.get('standard', 0),
                               min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'midnight', text=u'Ніч',
                               value=values_from_config.get('midnight', 0),
                               min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'overcast', text=u'Пасмурно',
                               value=values_from_config.get('overcast', 0),
                               min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'sunset', text=u'Закат',
                               value=values_from_config.get('sunset', 0),
                               min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'midday', text=u'Полдень',
                               value=values_from_config.get('midday', 0),
                               min=0, max=20, interval=1),
            ]

        column1 = [
            t.createLabel(text=u'Загальні налаштування для всіх карт'),
            t.createEmpty(),
        ]
        column1.extend(make_preset_sliders('global_', g_controller.config.global_weights))
        column1.append(t.createEmpty())
        column1.append(t.createHotkey(varName='hotkey', text=u'Смена погоды в бою',
                                      value=current_codes))

        column2 = [
            t.createLabel(text=u'Налаштування по картах'),
            t.createEmpty(),
            t.createDropdown(
                varName='active_map',
                text=u'Карта',
                options=MAP_LABELS,
                value=0,
            ),
        ]
        column2.extend(make_preset_sliders('map_', {pid: 0 for pid in
                                                     ['standard', 'midnight', 'overcast', 'sunset', 'midday']}))
        # Робимо слайдери карт з префіксом [карта] у лейблі
        for slider in column2[-5:]:
            if 'text' in slider and slider['text'].startswith(u'Стандарт'):
                slider['text'] = u'[карта] Стандарт'
            elif 'text' in slider and slider['text'].startswith(u'Ніч'):
                slider['text'] = u'[карта] Ніч'
            elif 'text' in slider and slider['text'].startswith(u'Пасмурно'):
                slider['text'] = u'[карта] Пасмурно'
            elif 'text' in slider and slider['text'].startswith(u'Закат'):
                slider['text'] = u'[карта] Закат'
            elif 'text' in slider and slider['text'].startswith(u'Полдень'):
                slider['text'] = u'[карта] Полдень'

        template = {
            'modDisplayName': u'Погода на картах',
            'enabled': True,
            'column1': column1,
            'column2': column2,
        }

        saved = g_modsSettingsApi.setModTemplate(
            linkage='com.example.weather',
            template=template,
            callback=_on_settings_changed,
            buttonHandler=open_weather_window,
        )
        if saved:
            _apply_saved_settings(saved)
    except Exception:
        _log().exception('modsSettingsApi registration failed')

    _INIT_DONE = True


def fini(*args, **kwargs):
    global _INIT_DONE
    _remove_key_hook()
    _remove_space_hook()
    _INIT_DONE = False


def sendEvent(*args, **kwargs):
    return None


def handleKeyEvent(event=None, *args, **kwargs):
    try:
        if event is not None:
            _on_key_event(event)
    except Exception:
        _log().exception('handleKeyEvent failed')
    return None


def onAccountBecomePlayer(*args, **kwargs):
    if not _INIT_DONE:
        init()
    return None


def onBecomePlayer(*args, **kwargs):
    if not _INIT_DONE:
        init()
    return None


def startGUI(*args, **kwargs):
    if not _INIT_DONE:
        init()
    return None


def destroyGUI(*args, **kwargs):
    return None


def onDisconnected(*args, **kwargs):
    return None


def onConnected(*args, **kwargs):
    return None
