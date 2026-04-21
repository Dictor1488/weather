# -*- coding: utf-8 -*-
"""
Точка входу мода.
v1.4.0 — виправлено розсинхронізацію з weather_controller v4.0
         (прибрано всі звернення до g_controller.config,
          виправлено _get_space_name_from_avatar)
"""

try:
    import BigWorld
    import Keys
    IN_GAME = True
except ImportError:
    IN_GAME = False

_InputHandler = None
def _get_input_handler():
    global _InputHandler
    if _InputHandler is None and IN_GAME:
        try:
            from gui import InputHandler as _ih
            _InputHandler = _ih
        except Exception:
            pass
    return _InputHandler

from weather_controller import g_controller

_BATTLE_SPACE_HOOKS = []
_KEY_HOOK_INSTALLED = False
_INIT_DONE = False
_hotkey_codes = []
_DEFAULT_WEIGHT_VALUE = 20
_PRESET_IDS = ['standard', 'midnight', 'overcast', 'sunset', 'midday']
_HARDCODED_TRIGGER_KEY = getattr(Keys, 'KEY_F12', 0) if IN_GAME else 0

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


def _default_weights():
    return dict((pid, _DEFAULT_WEIGHT_VALUE) for pid in _PRESET_IDS)


def _effective_ui_weights(weights):
    result = {}
    source = weights or {}
    total = 0
    for pid in _PRESET_IDS:
        try:
            value = int(source.get(pid, 0))
        except Exception:
            value = 0
        result[pid] = value
        total += value
    if total > 0:
        return result
    return _default_weights()


def _load_hotkey_codes():
    global _hotkey_codes
    if not IN_GAME:
        _hotkey_codes = []
        return
    _hotkey_codes = [_HARDCODED_TRIGGER_KEY] if _HARDCODED_TRIGGER_KEY else []
    try:
        g_controller.setHotkey(True, [], 'KEY_F12')
    except Exception:
        _log().exception('_load_hotkey_codes failed to persist hardcoded F12')


def _extract_space_name_from_arena_type(arena_type):
    if not arena_type:
        return None
    for attr in ('geometryName', 'geometry', 'name'):
        v = getattr(arena_type, attr, None)
        if v and isinstance(v, str):
            name = v.strip()
            if '/' in name:
                name = name.rsplit('/', 1)[-1]
            if name:
                return name
    return None


def _get_space_name_from_avatar(avatar):
    try:
        arena = getattr(avatar, 'arena', None)
        arena_type = getattr(arena, 'arenaType', None) if arena else None
        return _extract_space_name_from_arena_type(arena_type)
    except Exception:
        _log().exception('_get_space_name_from_avatar failed')
    return None


def _get_space_name_for_become_player(avatar):
    """
    Отримує назву карти в момент onBecomePlayer.
    В цей момент avatar.arena.arenaType може не мати geometryName,
    але arenaTypeID + ArenaType.g_cache завжди доступні.
    """
    log = _log()
    
    # Спосіб 1: через стандартний _get_space_name_from_avatar
    name = _get_space_name_from_avatar(avatar)
    if name:
        log.info('_get_space_name_for_become_player: via arena.arenaType.geometryName = %s', name)
        return name

    # Спосіб 2: через arenaTypeID + ArenaType.g_cache
    try:
        arena_type_id = getattr(avatar, 'arenaTypeID', None)
        if arena_type_id:
            try:
                from ArenaType import g_cache
                arena_type = g_cache.get(arena_type_id)
                if arena_type:
                    for attr in ('geometryName', 'geometry', 'name'):
                        v = getattr(arena_type, attr, None)
                        if v and isinstance(v, str):
                            name = v.strip()
                            if '/' in name:
                                name = name.rsplit('/', 1)[-1]
                            if name:
                                log.info('_get_space_name_for_become_player: via ArenaType.g_cache[%s].%s = %s',
                                         arena_type_id, attr, name)
                                return name
            except Exception as e:
                log.warning('_get_space_name_for_become_player: ArenaType.g_cache ERR: %s', e)
    except Exception as e:
        log.warning('_get_space_name_for_become_player: arenaTypeID ERR: %s', e)

    # Спосіб 3: через arena.arenaType напряму (якщо відрізняється від спроби 1)
    try:
        arena = getattr(avatar, 'arena', None)
        if arena:
            arena_type = getattr(arena, 'arenaType', None)
            if arena_type:
                log.info('_get_space_name_for_become_player: arenaType attrs: %s',
                         [a for a in dir(arena_type) if not a.startswith('_')][:20])
    except Exception:
        pass

    log.warning('_get_space_name_for_become_player: all methods failed, space_name=None')
    return None


def _install_battle_space_hook():
    if not IN_GAME or _BATTLE_SPACE_HOOKS:
        return

    log = _log()
    installed_any = False

    try:
        import ClientArena

        if hasattr(ClientArena, 'ClientArena'):
            cls_arena = ClientArena.ClientArena
            if hasattr(cls_arena, 'onNewVehicleListReceived'):
                orig_nvlr = cls_arena.onNewVehicleListReceived

                def make_arena_wrapper(orig):
                    def wrapped(self, *args, **kwargs):
                        try:
                            arena_type = getattr(self, 'arenaType', None)
                            space_name = _extract_space_name_from_arena_type(arena_type)
                            if space_name:
                                log.info('ClientArena.onNewVehicleListReceived hook: space=%s', space_name)
                                g_controller.onSpaceEntered(space_name)
                        except Exception:
                            log.exception('ClientArena hook failed')
                        return orig(self, *args, **kwargs)
                    return wrapped

                cls_arena.onNewVehicleListReceived = make_arena_wrapper(orig_nvlr)
                _BATTLE_SPACE_HOOKS.append((cls_arena, 'onNewVehicleListReceived', orig_nvlr))
                log.info('Installed EARLY hook: ClientArena.onNewVehicleListReceived')
                installed_any = True
            else:
                log.warning('ClientArena.onNewVehicleListReceived not found')
        else:
            log.warning('ClientArena.ClientArena class not found')
    except ImportError:
        log.warning('ClientArena module not available, skipping early hook')
    except Exception:
        log.exception('Failed to install ClientArena hook')

    try:
        import Avatar

        if not hasattr(Avatar, 'PlayerAvatar'):
            log.warning('Avatar.PlayerAvatar not found')
        else:
            cls = Avatar.PlayerAvatar

            # --- Хук onBecomePlayer: найраніший момент, ДО завантаження простору ---
            # Лог підтверджує: Avatar.onBecomePlayer → [SPACE] Loading space → Avatar.onEnterWorld
            # Тут ми вже знаємо arena_type і можемо записати файли ДО того як рушій
            # починає завантажувати простір. Тоді перезавантаження не потрібне взагалі.
            if hasattr(cls, 'onBecomePlayer'):
                orig_bp = cls.onBecomePlayer

                def make_bp_wrapper(orig):
                    def wrapped_bp(self, *a, **kw):
                        try:
                            space_name = _get_space_name_for_become_player(self)
                            if space_name:
                                log.info('onBecomePlayer hook: space=%s (writing files BEFORE space load)', space_name)
                                g_controller.onSpaceEntered(space_name)
                            else:
                                log.warning('onBecomePlayer hook: could not get space name, files will be written in onEnterWorld')
                        except Exception:
                            log.exception('onBecomePlayer hook failed')
                        return orig(self, *a, **kw)
                    return wrapped_bp

                cls.onBecomePlayer = make_bp_wrapper(orig_bp)
                _BATTLE_SPACE_HOOKS.append((cls, 'onBecomePlayer', orig_bp))
                installed_any = True
                log.info('Installed EARLY hook: Avatar.PlayerAvatar.onBecomePlayer')
            else:
                log.warning('Avatar.PlayerAvatar.onBecomePlayer not found')

            # --- Хук onEnterWorld: запасний, якщо onBecomePlayer не спрацював ---
            if hasattr(cls, 'onEnterWorld'):
                original = cls.onEnterWorld

                def make_wrapper(orig, early_installed):
                    def wrapped(self, *args, **kwargs):
                        try:
                            space_name = _get_space_name_from_avatar(self)
                            if space_name:
                                if early_installed:
                                    # onBecomePlayer ran - but did it successfully write files?
                                    # Check by seeing if files were written (log shows 'wrote')
                                    # For safety: always write in onEnterWorld too
                                    # (writing twice is harmless, missing once breaks everything)
                                    log.info('onEnterWorld: space=%s (writing files, early hook was=%s)',
                                             space_name, early_installed)
                                    g_controller.onSpaceEntered(space_name)
                                else:
                                    log.info('onEnterWorld fallback: space=%s (writing space.settings)', space_name)
                                    g_controller.onSpaceEntered(space_name)
                        except Exception:
                            log.exception('onEnterWorld hook failed')
                        return orig(self, *args, **kwargs)
                    return wrapped

                cls.onEnterWorld = make_wrapper(original, installed_any)
                _BATTLE_SPACE_HOOKS.append((cls, 'onEnterWorld', original))
                log.info('Installed FALLBACK hook: Avatar.PlayerAvatar.onEnterWorld (early_installed=%s)', installed_any)
            else:
                log.warning('PlayerAvatar.onEnterWorld not found')

    except Exception:
        log.exception('Failed to install Avatar hook')


def _remove_battle_space_hook():
    while _BATTLE_SPACE_HOOKS:
        cls, attr, original = _BATTLE_SPACE_HOOKS.pop()
        try:
            setattr(cls, attr, original)
        except Exception:
            _log().exception('Failed to remove battle space hook')


def _extract_key_event_data(event_or_key):
    key = None
    is_down = True
    try:
        if hasattr(event_or_key, 'key'):
            key = getattr(event_or_key, 'key', None)
            if hasattr(event_or_key, 'isKeyDown'):
                is_down = bool(event_or_key.isKeyDown())
        else:
            key = int(event_or_key)
            is_down = True
    except Exception:
        key = None
        is_down = False
    return key, is_down


def _hotkey_matches(key_code):
    return bool(_HARDCODED_TRIGGER_KEY) and key_code == _HARDCODED_TRIGGER_KEY


def _handle_hotkey_trigger(key_code):
    in_battle = False
    try:
        player = BigWorld.player()
        in_battle = player is not None and getattr(player, 'arena', None) is not None
    except Exception:
        pass

    _log().info('hotkey matched: key=%s in_battle=%s action=cycle', key_code, in_battle)
    if in_battle:
        g_controller.cycleWeatherInBattle()


def _on_key_event(event_or_key):
    if not IN_GAME:
        return

    key_code, is_down = _extract_key_event_data(event_or_key)
    if key_code is None or not is_down:
        return
    if not _hotkey_matches(key_code):
        return
    _handle_hotkey_trigger(key_code)


def _install_key_hook():
    global _KEY_HOOK_INSTALLED
    if not IN_GAME or _KEY_HOOK_INSTALLED:
        return
    log = _log()
    installed = False

    try:
        import AvatarInputHandler as _AIH
        cls_aih = _AIH.AvatarInputHandler
        if hasattr(cls_aih, 'handleKeyEvent'):
            _orig_aih = cls_aih.handleKeyEvent

            def _make_aih_wrapper(orig):
                def _aih_patched(self, *a, **kw):
                    try:
                        if a:
                            _on_key_event(a[0])
                    except Exception:
                        log.exception('AvatarInputHandler hotkey dispatch failed')
                    return orig(self, *a, **kw)
                return _aih_patched

            cls_aih.handleKeyEvent = _make_aih_wrapper(_orig_aih)
            installed = True
            log.info('Key hook installed: AvatarInputHandler.handleKeyEvent (battle)')
        else:
            log.warning('AvatarInputHandler.handleKeyEvent not found')
    except ImportError:
        log.warning('AvatarInputHandler not available')
    except Exception:
        log.exception('Failed to install AvatarInputHandler key hook')

    try:
        _ih = _get_input_handler()
        if _ih is not None and getattr(_ih, 'g_instance', None) is not None:
            _ih.g_instance.onKeyDown += _on_key_event
            installed = True
            log.info('Key hook installed: InputHandler.g_instance.onKeyDown (global)')
    except Exception:
        log.exception('Failed to install InputHandler key hook')

    _KEY_HOOK_INSTALLED = installed


def _remove_key_hook():
    global _KEY_HOOK_INSTALLED
    if not IN_GAME or not _KEY_HOOK_INSTALLED:
        return
    try:
        _ih = _get_input_handler()
        if _ih is not None and getattr(_ih, 'g_instance', None) is not None:
            _ih.g_instance.onKeyDown -= _on_key_event
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


def _on_settings_changed(linkage, newSettings):
    log = _log()
    log.debug('settings changed: %s', newSettings)

    current_general = g_controller.getGeneralWeights()
    changed_general = False
    for pid in _PRESET_IDS:
        key = 'global_' + pid
        if key in newSettings:
            current_general[pid] = int(newSettings[key])
            changed_general = True
    if changed_general:
        g_controller.setGeneralWeights(current_general)

    map_idx = newSettings.get('active_map', 0)
    try:
        active_map = MAP_IDS[int(map_idx)]
    except (IndexError, TypeError, ValueError):
        active_map = ''

    if active_map:
        current_map = g_controller.getMapWeights(active_map)
        changed_map = False
        for pid in _PRESET_IDS:
            key = 'map_' + pid
            if key in newSettings:
                current_map[pid] = int(newSettings[key])
                changed_map = True
        if changed_map:
            g_controller.setMapWeights(active_map, current_map)


def _update_hotkey_from_codes(int_codes):
    global _hotkey_codes
    _hotkey_codes = [_HARDCODED_TRIGGER_KEY] if _HARDCODED_TRIGGER_KEY else []
    try:
        g_controller.setHotkey(True, [], 'KEY_F12')
    except Exception:
        _log().exception('_update_hotkey_from_codes failed')


def _apply_saved_settings(saved):
    current_general = g_controller.getGeneralWeights()
    changed = False
    for pid in _PRESET_IDS:
        key = 'global_' + pid
        if key in saved:
            current_general[pid] = int(saved[key])
            changed = True
    if changed:
        g_controller.setGeneralWeights(current_general)

    map_idx = saved.get('active_map', 0)
    try:
        active_map = MAP_IDS[int(map_idx)]
    except (IndexError, TypeError, ValueError):
        active_map = ''
    if active_map:
        current_map = g_controller.getMapWeights(active_map)
        changed_map = False
        for pid in _PRESET_IDS:
            key = 'map_' + pid
            if key in saved:
                current_map[pid] = int(saved[key])
                changed_map = True
        if changed_map:
            g_controller.setMapWeights(active_map, current_map)

    _load_hotkey_codes()


def init(*args, **kwargs):
    global _INIT_DONE
    if _INIT_DONE:
        return

    _load_hotkey_codes()
    _install_battle_space_hook()
    _install_key_hook()

    try:
        from gui.modsSettingsApi import g_modsSettingsApi
        from gui.modsSettingsApi import templates as t
        import Keys as K

        current_codes = [_HARDCODED_TRIGGER_KEY] if _HARDCODED_TRIGGER_KEY else [K.KEY_F12]
        general_weights = _effective_ui_weights(g_controller.getGeneralWeights())
        default_map_weights = _default_weights()

        def make_sliders(prefix, values):
            weights = _effective_ui_weights(values)
            return [
                t.createSlider(varName=prefix + 'standard', text=u'Стандарт' if prefix == 'global_' else u'[карта] Стандарт', value=weights.get('standard', _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'midnight', text=u'Ніч' if prefix == 'global_' else u'[карта] Ніч', value=weights.get('midnight', _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'overcast', text=u'Хмарно' if prefix == 'global_' else u'[карта] Хмарно', value=weights.get('overcast', _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'sunset', text=u'Захід' if prefix == 'global_' else u'[карта] Захід', value=weights.get('sunset', _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
                t.createSlider(varName=prefix + 'midday', text=u'Полудень' if prefix == 'global_' else u'[карта] Полудень', value=weights.get('midday', _DEFAULT_WEIGHT_VALUE), min=0, max=20, interval=1),
            ]

        column1 = [
            t.createLabel(text=u'Загальні налаштування для всіх карт'),
            t.createEmpty(),
        ]
        column1.extend(make_sliders('global_', general_weights))
        column1.append(t.createEmpty())
        column1.append(t.createHotkey(varName='hotkey', text=u'Зміна погоди в бою', value=current_codes))

        column2 = [
            t.createLabel(text=u'Налаштування по картах'),
            t.createEmpty(),
            t.createDropdown(varName='active_map', text=u'Карта', options=MAP_LABELS, value=0),
        ]
        column2.extend(make_sliders('map_', default_map_weights))

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
