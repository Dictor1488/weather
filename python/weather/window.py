# -*- coding: utf-8 -*-
"""
DAAPI-міст між Flash (WeatherMediator.as) та weather_controller.
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

from weather.controller import (
    g_controller,
    PRESET_ORDER,
    PRESET_LABELS,
    PRESET_GUIDS,
    DEFAULT_WEIGHT,
)

import logging
import os

LOG = logging.getLogger('weather_mod')

_active_window = None

PRESET_PREVIEW = {
    'standard': 'img://gui/maps/icons/pro.environment/default.png',
    'midnight': 'img://gui/maps/icons/pro.environment/15755E11.4090266B.594778B6.B233C12C.png',
    'overcast': 'img://gui/maps/icons/pro.environment/56BA3213.40FFB1DF.125FBCAD.173E8347.png',
    'sunset':   'img://gui/maps/icons/pro.environment/6DEE1EBB.44F63FCC.AACF6185.7FBBC34E.png',
    'midday':   'img://gui/maps/icons/pro.environment/BF040BCB.4BE1D04F.7D484589.135E881B.png',
}

# Картинки карт лежать у res/gui/maps/icons/weather/maps/<map_id>.png
# Витягуються заздалегідь скриптом extract_map_stats.py (не в рантаймі).
# img:// — внутрішній протокол Flash GUI, відносний до res/gui/
_MAP_THUMB_URL_TEMPLATE = 'img://maps/icons/weather/maps/{map_id}.png'


def _map_icon(map_id):
    return _MAP_THUMB_URL_TEMPLATE.format(map_id=map_id)


# Карти що є в грі (EU/NA WG клієнт).
# map_id відповідає імені файлу у res/packages/<map_id>.pkg
# і імені PNG у gui/maps/icons/map/stats/<map_id>.png
MAP_REGISTRY = [
    ('01_karelia',                  u'Карелія'),
    ('02_malinovka',                u'Малинівка'),
    ('04_himmelsdorf',              u'Хіммельсдорф'),
    ('05_prohorovka',               u'Прохорівка'),
    ('06_ensk',                     u'Єнськ'),
    ('07_lakeville',                u'Ласвілль'),
    ('08_ruinberg',                 u'Руїнберг'),
    ('10_hills',                    u'Копальні'),
    ('11_murovanka',                u'Мурованка'),
    ('13_erlenberg',                u'Ерленберг'),
    ('14_siegfried_line',           u'Лінія Зигфріда'),
    ('17_munchen',                  u'Мюнхен'),
    ('18_cliff',                    u'Круча'),
    ('19_monastery',                u'Монастир'),
    ('23_westfeld',                 u'Вестфілд'),
    ('28_desert',                   u'Піщана ріка'),
    ('29_el_hallouf',               u'Ель-Халлуф'),
    ('31_airfield',                 u'Летовище'),
    ('33_fjord',                    u'Фіорди'),
    ('34_redshire',                 u'Редшир'),
    ('35_steppes',                  u'Степи'),
    ('36_fishing_bay',              u'Рибальська бухта'),
    ('37_caucasus',                 u'Кавказ'),
    ('38_mannerheim_line',          u'Лінія Маннергейма'),
    ('44_north_america',            u'Лайв Окс'),
    ('45_north_america',            u'Хайвей'),
    ('47_canada_a',                 u'Перлинна річка'),
    ('59_asia_great_wall',          u'Велика стіна'),
    ('60_asia_miao',                u'Тихий берег'),
    ('63_tundra',                   u'Тундра'),
    ('95_lost_city_ctf',            u'Загублене місто'),
    ('99_poland',                   u'Студзянки'),
    ('101_dday',                    u'Нормандія (D-Day)'),
    ('105_germany',                 u'Берлін'),
    ('112_eiffel_tower_ctf',        u'Париж'),
    ('114_czech',                   u'Промзона'),
    ('115_sweden',                  u'Кордон імперії'),
    ('121_lost_paradise_v',         u'Перевал'),
    ('127_japort',                  u'Стара гавань'),
    ('128_last_frontier_v',         u'Фата-моргана'),
    ('208_bf_epic_normandy',        u'Оверлорд'),
    ('209_wg_epic_suburbia',        u'Крафтверк'),
    ('210_bf_epic_desert',          u'Застава'),
    ('212_epic_random_valley_sm25', u'Долина'),
    ('217_er_alaska',               u'Клондайк'),
    ('222_er_clime',                u'Вайдпарк'),
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
    for map_id, label in MAP_REGISTRY:
        map_weights = g_controller.getMapWeights(map_id) or {}
        maps.append({
            'id': map_id,
            'label': label,
            'thumbSrc': _map_icon(map_id),
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
        return True
    except Exception:
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
            pass

    def py_onPresetSelected(self, mapId, presetId):
        try:
            preset_id = str(presetId) if presetId else 'standard'
            map_id = str(mapId) if mapId else None
            if not map_id:
                self._ctrl.setPreset(preset_id)
            else:
                from weather.controller import apply_preset
                apply_preset(map_id, preset_id)
        except Exception:
            pass

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
            pass

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

    def py_onHotkeyChanged(self, keyCodes, hotkeyStr):
        try:
            parts = str(hotkeyStr).split('+')
            key = 'KEY_' + parts[-1] if parts else 'KEY_F12'
            mods = parts[:-1] if len(parts) > 1 else []
            self._ctrl.on_hotkey_changed(list(keyCodes or []), str(hotkeyStr))
            from weather.controller import set_hotkey
            set_hotkey(True, mods, key)
        except Exception:
            pass

    def _dispose(self):
        global _active_window
        if _active_window is self:
            _active_window = None
        self._ctrl.on_close_requested()
        super(WeatherWindowMeta, self)._dispose()
