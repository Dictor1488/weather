# -*- coding: utf-8 -*-
"""
Точка входу мода.
v1.3.0 — hook на gui.app_loader.loader.BattleSpace + fallback через player.arena
"""

try:
    import BigWorld
    import Keys
    from gui import InputHandler
    IN_GAME = True
except ImportError:
    IN_GAME = False

from weather_controller import g_controller


_BATTLE_SPACE_HOOKS = []  # list of (cls, attr_name, original_func)
_KEY_HOOK_INSTALLED = False
_INIT_DONE = False


# ============================================================================
# Повний список карт
# ============================================================================
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


# ============================================================================
# Hook на BattleSpace / BattleLoadingSpace з gui.app_loader.loader
# ============================================================================
def _get_space_name_from_avatar(avatar):
    """Витягує назву карти з Avatar через arena.arenaType."""
    try:
        arena = getattr(avatar, 'arena', None)
        arena_type = getattr(arena, 'arenaType', None) if arena else None
        if not arena_type:
            return None
        from weather_controller import normalize_space_name, is_battle_map_space
        for attr in ('geometryName', 'geometry', 'name'):
            v = getattr(arena_type, attr, None)
            if v:
                norm = normalize_space_name(v)
                if is_battle_map_space(norm):
                    return norm
    except Exception:
        pass
    return None


def _install_battle_space_hook():
    """
    Хукаємо Avatar.PlayerAvatar.onEnterWorld — це до завантаження геометрії.

    Хронологія з логу:
      22:31:34.768 [SPACE] Loading space: spaces/31_airfield  <- space.settings читається
      22:31:34.796 Avatar.onEnterWorld                        <- НАШ ХУК (до/під час)
      22:31:38.990 Avatar.onSpaceLoaded                       <- пізно, вже завантажено
    """
    if not IN_GAME or _BATTLE_SPACE_HOOKS:
        return

    log = _log()

    try:
        import Avatar

        if not hasattr(Avatar, 'PlayerAvatar'):
            log.warning('Avatar.PlayerAvatar not found')
            return

        cls = Avatar.PlayerAvatar

        if not hasattr(cls, 'onEnterWorld'):
            log.warning('PlayerAvatar.onEnterWorld not found')
            return

        original = cls.onEnterWorld

        def make_wrapper(orig):
            def wrapped(self, *args, **kwargs):
                try:
                    space_name = _get_space_name_from_avatar(self)
                    if space_name:
                        log.info('onEnterWorld pre-hook: space=%s', space_name)
                        g_controller.on_space_entered(space_name)
                except Exception:
                    log.exception('onEnterWorld pre-hook failed')
                result = orig(self, *args, **kwargs)
                return result
            return wrapped

        cls.onEnterWorld = make_wrapper(original)
        _BATTLE_SPACE_HOOKS.append((cls, 'onEnterWorld', original))
        log.info('Installed hook: Avatar.PlayerAvatar.onEnterWorld')

    except Exception:
        log.exception('Failed to install battle space hook')

def _remove_battle_space_hook():
    while _BATTLE_SPACE_HOOKS:
        cls, attr, original = _BATTLE_SPACE_HOOKS.pop()
        try:
            setattr(cls, attr, original)
        except Exception:
            _log().exception('Failed to remove battle space hook')


# ============================================================================
# Key hook
# ============================================================================
def _on_key_event(event):
    if not IN_GAME:
        return
    if not hasattr(event, 'isKeyDown') or not event.isKeyDown():
        return

    codes = g_controller.config.hotkey_codes
    if not codes:
        if event.key == Keys.KEY_F12 and BigWorld.isKeyDown(Keys.KEY_LALT):
            g_controller.cycle_weather_in_battle()
        return

    trigger_key = codes[-1]
    modifiers = codes[:-1]
    if event.key != trigger_key:
        return
    for mod in modifiers:
        if not BigWorld.isKeyDown(mod):
            return
    g_controller.cycle_weather_in_battle()


def _install_key_hook():
    global _KEY_HOOK_INSTALLED
    if not IN_GAME or _KEY_HOOK_INSTALLED:
        return
    try:
        if getattr(InputHandler, 'g_instance', None) is not None:
            InputHandler.g_instance.onKeyDown += _on_key_event
            _KEY_HOOK_INSTALLED = True
            _log().info('Key hook installed')
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
        pass
    _KEY_HOOK_INSTALLED = False


def open_weather_window():
    try:
        from gui import SystemMessages
        SystemMessages.pushI18nMessage(
            u'Окреме вікно ще не підключене. Користуйся панеллю Mod Settings.',
            type=SystemMessages.SM_TYPE.Information
        )
    except Exception:
        pass


# ============================================================================
# Settings callback
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

    _install_battle_space_hook()
    _install_key_hook()

    try:
        from gui.modsSettingsApi import g_modsSettingsApi
        from gui.modsSettingsApi import templates as t
        import Keys as K

        current_codes = g_controller.config.hotkey_codes or [K.KEY_LALT, K.KEY_F12]

        def make_sliders(prefix, values):
            return [
                t.createSlider(varName=prefix + 'standard', text=u'Стандарт' if prefix == 'global_' else u'[карта] Стандарт',
                               value=values.get('standard', 0), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'midnight', text=u'Ніч' if prefix == 'global_' else u'[карта] Ніч',
                               value=values.get('midnight', 0), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'overcast', text=u'Пасмурно' if prefix == 'global_' else u'[карта] Пасмурно',
                               value=values.get('overcast', 0), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'sunset', text=u'Закат' if prefix == 'global_' else u'[карта] Закат',
                               value=values.get('sunset', 0), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'midday', text=u'Полдень' if prefix == 'global_' else u'[карта] Полдень',
                               value=values.get('midday', 0), min=0, max=20, interval=1),
            ]

        column1 = [
            t.createLabel(text=u'Загальні налаштування для всіх карт'),
            t.createEmpty(),
        ]
        column1.extend(make_sliders('global_', g_controller.config.global_weights))
        column1.append(t.createEmpty())
        column1.append(t.createHotkey(varName='hotkey', text=u'Смена погоды в бою',
                                      value=current_codes))

        column2 = [
            t.createLabel(text=u'Налаштування по картах'),
            t.createEmpty(),
            t.createDropdown(varName='active_map', text=u'Карта',
                             options=MAP_LABELS, value=0),
        ]
        column2.extend(make_sliders('map_', {pid: 0 for pid in
                                              ['standard', 'midnight', 'overcast', 'sunset', 'midday']}))

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
    _remove_battle_space_hook()
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
