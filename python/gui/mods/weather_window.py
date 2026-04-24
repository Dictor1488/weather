# -*- coding: utf-8 -*-
"""
DAAPI-міст між Flash (WeatherMediator.as) та weather_controller.

Важливо: якщо AS3-кнопка "Закрити" сховала вікно, але Python close callback
не дійшов, SFWindow може залишитись живим. Для цього тримаємо _active_window
і при наступному відкритті просто повторно викликаємо as_setData(), що робить
WeatherMediator.visible = true.
"""

try:
    from gui.Scaleform.framework.entities.View import View as AbstractLobbyView
    IN_GAME = True
except ImportError:
    try:
        from gui.Scaleform.framework.entities.BaseDAAPIModule import BaseDAAPIModule as AbstractLobbyView
        IN_GAME = True
    except ImportError:
        try:
            from gui.Scaleform.daapi.view.lobby.AbstractLobbyView import AbstractLobbyView
            IN_GAME = True
        except ImportError:
            IN_GAME = False
            class AbstractLobbyView(object):
                def __init__(self, *args, **kw): pass
                def _populate(self): pass
                def _dispose(self): pass

from weather_controller import (
    g_controller,
    PRESET_ORDER,
    PRESET_LABELS,
    PRESET_GUIDS,
    DEFAULT_WEIGHT,
)

import logging
LOG = logging.getLogger('weather_mod')

_active_window = None

PRESET_PREVIEW = {
    'standard': 'gui/maps/icons/pro.environment/default.png',
    'midnight': 'gui/maps/icons/pro.environment/15755E11.4090266B.594778B6.B233C12C.png',
    'overcast': 'gui/maps/icons/pro.environment/56BA3213.40FFB1DF.125FBCAD.173E8347.png',
    'sunset':   'gui/maps/icons/pro.environment/6DEE1EBB.44F63FCC.AACF6185.7FBBC34E.png',
    'midday':   'gui/maps/icons/pro.environment/BF040BCB.4BE1D04F.7D484589.135E881B.png',
}

MAP_REGISTRY = [
    ('01_karelia',             u'Карелія',            'gui/maps/icons/map/list/01_karelia.png'),
    ('02_malinovka',           u'Малинівка',          'gui/maps/icons/map/list/02_malinovka.png'),
    ('04_himmelsdorf',         u'Хіммельсдорф',       'gui/maps/icons/map/list/04_himmelsdorf.png'),
    ('05_prohorovka',          u'Прохорівка',         'gui/maps/icons/map/list/05_prohorovka.png'),
    ('06_ensk',                u'Єнськ',              'gui/maps/icons/map/list/06_ensk.png'),
    ('07_lakeville',           u'Ласвілль',           'gui/maps/icons/map/list/07_lakeville.png'),
    ('08_ruinberg',            u'Руїнберг',           'gui/maps/icons/map/list/08_ruinberg.png'),
    ('10_hills',               u'Копальні',           'gui/maps/icons/map/list/10_hills.png'),
    ('11_murovanka',           u'Мурованка',          'gui/maps/icons/map/list/11_murovanka.png'),
    ('13_erlenberg',           u'Ерленберг',          'gui/maps/icons/map/list/13_erlenberg.png'),
    ('14_siegfried_line',      u'Лінія Зигфріда',     'gui/maps/icons/map/list/14_siegfried_line.png'),
    ('17_munchen',             u'Мюнхен',             'gui/maps/icons/map/list/17_munchen.png'),
    ('18_cliff',               u'Круча',              'gui/maps/icons/map/list/18_cliff.png'),
    ('19_monastery',           u'Монастир',           'gui/maps/icons/map/list/19_monastery.png'),
    ('23_westfeld',            u'Вестфілд',           'gui/maps/icons/map/list/23_westfeld.png'),
    ('28_desert',              u'Піщана ріка',        'gui/maps/icons/map/list/28_desert.png'),
    ('29_el_hallouf',          u'Ель-Халлуф',         'gui/maps/icons/map/list/29_el_hallouf.png'),
    ('31_airfield',            u'Летовище',           'gui/maps/icons/map/list/31_airfield.png'),
    ('33_fjord',               u'Фіорди',             'gui/maps/icons/map/list/33_fjord.png'),
    ('34_redshire',            u'Редшир',             'gui/maps/icons/map/list/34_redshire.png'),
    ('35_steppes',             u'Степи',              'gui/maps/icons/map/list/35_steppes.png'),
    ('36_fishing_bay',         u'Рибальська бухта',   'gui/maps/icons/map/list/36_fishing_bay.png'),
    ('37_caucasus',            u'Кавказ',             'gui/maps/icons/map/list/37_caucasus.png'),
    ('38_mannerheim_line',     u'Лінія Маннергейма',  'gui/maps/icons/map/list/38_mannerheim_line.png'),
    ('44_north_america',       u'Лайв Окс',           'gui/maps/icons/map/list/44_north_america.png'),
    ('45_north_america',       u'Хайвей',             'gui/maps/icons/map/list/45_north_america.png'),
    ('47_canada_a',            u'Перлинна річка',     'gui/maps/icons/map/list/47_canada_a.png'),
    ('59_asia_great_wall',     u'Велика стіна',       'gui/maps/icons/map/list/59_asia_great_wall.png'),
    ('60_asia_miao',           u'Тихий берег',        'gui/maps/icons/map/list/60_asia_miao.png'),
    ('63_tundra',              u'Тундра',             'gui/maps/icons/map/list/63_tundra.png'),
    ('90_minsk',               u'Мінськ',             'gui/maps/icons/map/list/90_minsk.png'),
    ('95_lost_city_ctf',       u'Загублене місто',    'gui/maps/icons/map/list/95_lost_city_ctf.png'),
    ('99_poland',              u'Студзянки',          'gui/maps/icons/map/list/99_poland.png'),
    ('101_dday',               u'Нормандія (D-Day)',  'gui/maps/icons/map/list/101_dday.png'),
    ('105_germany',            u'Берлін',             'gui/maps/icons/map/list/105_germany.png'),
    ('112_eiffel_tower_ctf',   u'Париж',              'gui/maps/icons/map/list/112_eiffel_tower_ctf.png'),
    ('114_czech',              u'Промзона',           'gui/maps/icons/map/list/114_czech.png'),
    ('115_sweden',             u'Кордон імперії',     'gui/maps/icons/map/list/115_sweden.png'),
    ('121_lost_paradise_v',    u'Перевал',            'gui/maps/icons/map/list/121_lost_paradise_v.png'),
    ('127_japort',             u'Стара гавань',       'gui/maps/icons/map/list/127_japort.png'),
    ('128_last_frontier_v',    u'Фата-моргана',       'gui/maps/icons/map/list/128_last_frontier_v.png'),
    ('208_bf_epic_normandy',   u'Оверлорд',           'gui/maps/icons/map/list/208_bf_epic_normandy.png'),
    ('209_wg_epic_suburbia',   u'Крафтверк',          'gui/maps/icons/map/list/209_wg_epic_suburbia.png'),
    ('210_bf_epic_desert',     u'Застава',            'gui/maps/icons/map/list/210_bf_epic_desert.png'),
    ('212_epic_random_valley', u'Долина',             'gui/maps/icons/map/list/212_epic_random_valley.png'),
    ('217_er_alaska',          u'Клондайк',           'gui/maps/icons/map/list/217_er_alaska.png'),
    ('222_er_clime',           u'Вайдпарк',           'gui/maps/icons/map/list/222_er_clime.png'),
]


def _build_presets_for_ui(weights=None):
    weights = weights or {}
    return [
        {
            'id':         pid,
            'label':      PRESET_LABELS.get(pid, pid),
            'guid':       PRESET_GUIDS.get(pid, ''),
            'previewSrc': PRESET_PREVIEW.get(pid, ''),
            'weight':     int(weights.get(pid, DEFAULT_WEIGHT)),
        }
        for pid in PRESET_ORDER
    ]


def _build_hotkey_str(hotkey_dict):
    try:
        key  = hotkey_dict.get('key', 'KEY_F12')
        mods = hotkey_dict.get('mods', [])
        return '+'.join(list(mods) + [key.replace('KEY_', '')])
    except Exception:
        return 'F12'


def _build_payload():
    current_preset = g_controller.getCurrentPreset()
    general = g_controller.getGeneralWeights() or {}

    maps = []
    for map_id, label, thumb in MAP_REGISTRY:
        map_weights = g_controller.getMapWeights(map_id) or {}
        maps.append({
            'id': map_id,
            'label': label,
            'thumbSrc': thumb,
            'useGlobal': False,
            'presets': _build_presets_for_ui(map_weights),
        })

    hk = g_controller.getHotkey()
    hotkey_str = _build_hotkey_str(hk)
    hotkey_keys = []
    try:
        import Keys
        key_name = hk.get('key', 'KEY_F12')
        code = getattr(Keys, key_name, 0)
        if code:
            hotkey_keys.append(code)
    except Exception:
        pass

    return {
        'presets': _build_presets_for_ui(general),
        'maps': maps,
        'hotkey': hotkey_str,
        'hotkeyKeys': hotkey_keys,
        'currentPreset': current_preset,
    }


def show_existing_window():
    """Повертає True, якщо вже існуюче приховане вікно вдалося показати знову."""
    global _active_window
    win = _active_window
    if win is None:
        return False
    try:
        flash = getattr(win, 'flashObject', None)
        if flash is None:
            _active_window = None
            return False
        flash.as_setData(_build_payload())
        LOG.info('show_existing_window: reused active weatherPanel')
        return True
    except Exception:
        LOG.exception('show_existing_window failed')
        _active_window = None
        return False


class WeatherWindowMeta(AbstractLobbyView):

    def __init__(self, *args, **kwargs):
        super(WeatherWindowMeta, self).__init__(*args, **kwargs)
        self._ctrl = g_controller

    def _populate(self):
        global _active_window
        _active_window = self
        super(WeatherWindowMeta, self)._populate()
        try:
            self.flashObject.as_setData(_build_payload())
        except Exception:
            LOG.exception('WeatherWindowMeta._populate failed')

    def py_onPresetSelected(self, mapId, presetId):
        try:
            preset_id = str(presetId) if presetId else 'standard'
            map_id = str(mapId) if mapId else None
            if not map_id:
                LOG.info('py_onPresetSelected: global preset=%s', preset_id)
                self._ctrl.setPreset(preset_id)
            else:
                LOG.info('py_onPresetSelected: map=%s preset=%s', map_id, preset_id)
                from weather_controller import apply_preset
                apply_preset(map_id, preset_id)
        except Exception:
            LOG.exception('py_onPresetSelected failed')

    def py_onWeightChanged(self, mapId, presetId, value):
        try:
            map_id = str(mapId) if mapId else None
            if not map_id:
                weights = self._ctrl.getGeneralWeights() or {}
                weights[str(presetId)] = int(float(value))
                self._ctrl.setGeneralWeights(weights)
            else:
                weights = self._ctrl.getMapWeights(map_id) or {}
                weights[str(presetId)] = int(float(value))
                self._ctrl.setMapWeights(map_id, weights)
        except Exception:
            LOG.exception('py_onWeightChanged failed')

    def py_onMapSelected(self, mapId):
        pass

    def py_onTabChanged(self, tab):
        pass

    def py_onCloseRequested(self):
        global _active_window
        self._ctrl.on_close_requested()
        _active_window = None
        try:
            self.destroy()
            return
        except Exception:
            pass
        try:
            self._destroy()
            return
        except Exception:
            pass
        try:
            self.onWindowClose()
            return
        except Exception:
            pass
        LOG.info('py_onCloseRequested: close requested, no destroy method succeeded')

    def py_onHotkeyChanged(self, keyCodes, hotkeyStr):
        try:
            parts = str(hotkeyStr).split('+')
            key = 'KEY_' + parts[-1] if parts else 'KEY_F12'
            mods = parts[:-1] if len(parts) > 1 else []
            self._ctrl.on_hotkey_changed(list(keyCodes or []), str(hotkeyStr))
            from weather_controller import set_hotkey
            set_hotkey(True, mods, key)
        except Exception:
            LOG.exception('py_onHotkeyChanged failed')

    def _dispose(self):
        global _active_window
        if _active_window is self:
            _active_window = None
        self._ctrl.on_close_requested()
        super(WeatherWindowMeta, self)._dispose()
