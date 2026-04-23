# -*- coding: utf-8 -*-
"""
DAAPI-міст між Flash (WeatherMediator.as) та weather_controller.
"""

try:
    from gui.Scaleform.daapi.view.lobby.AbstractLobbyView import AbstractLobbyView
    IN_GAME = True
except ImportError:
    IN_GAME = False
    class AbstractLobbyView(object):
        def __init__(self, *args, **kw): pass
        def _populate(self): pass
        def _dispose(self): pass

from weather_controller import g_controller, PRESET_ORDER, PRESET_LABELS, PRESET_GUIDS, DEFAULT_WEIGHT

MAP_REGISTRY = [
    ("01_karelia",             u"Карелія",            "gui/maps/icons/map/list/01_karelia.png"),
    ("02_malinovka",           u"Малинівка",          "gui/maps/icons/map/list/02_malinovka.png"),
    ("04_himmelsdorf",         u"Хіммельсдорф",       "gui/maps/icons/map/list/04_himmelsdorf.png"),
    ("05_prohorovka",          u"Прохорівка",         "gui/maps/icons/map/list/05_prohorovka.png"),
    ("06_ensk",                u"Єнськ",              "gui/maps/icons/map/list/06_ensk.png"),
    ("07_lakeville",           u"Ласвілль",          "gui/maps/icons/map/list/07_lakeville.png"),
    ("08_ruinberg",            u"Руїнберг",          "gui/maps/icons/map/list/08_ruinberg.png"),
    ("10_hills",               u"Круча",              "gui/maps/icons/map/list/10_hills.png"),
    ("11_murovanka",           u"Мурованка",          "gui/maps/icons/map/list/11_murovanka.png"),
    ("13_erlenberg",           u"Ерленберг",          "gui/maps/icons/map/list/13_erlenberg.png"),
    ("14_siegfried_line",      u"Лінія Зигфріда",     "gui/maps/icons/map/list/14_siegfried_line.png"),
    ("15_komarin",             u"Застава",            "gui/maps/icons/map/list/15_komarin.png"),
    ("17_munster",             u"Крафтверк",          "gui/maps/icons/map/list/17_munster.png"),
    ("18_cliff",               u"Перевал",            "gui/maps/icons/map/list/18_cliff.png"),
    ("19_monastery",           u"Монастир",           "gui/maps/icons/map/list/19_monastery.png"),
    ("23_westfeld",            u"Вестфілд",           "gui/maps/icons/map/list/23_westfeld.png"),
    ("28_desert",              u"Загублене місто",    "gui/maps/icons/map/list/28_desert.png"),
    ("29_el_hallouf",          u"Ель-Халлуф",         "gui/maps/icons/map/list/29_el_hallouf.png"),
    ("31_airfield",            u"Летовище",           "gui/maps/icons/map/list/31_airfield.png"),
    ("33_fjord",               u"Фіорди",             "gui/maps/icons/map/list/33_fjord.png"),
    ("34_redshire",            u"Редшир",             "gui/maps/icons/map/list/34_redshire.png"),
    ("35_steppes",             u"Степи",              "gui/maps/icons/map/list/35_steppes.png"),
    ("36_fishing_bay",         u"Рибальська бухта",   "gui/maps/icons/map/list/36_fishing_bay.png"),
    ("38_mannerheim_line",     u"Лінія Маннергейма",  "gui/maps/icons/map/list/38_mannerheim_line.png"),
    ("39_crimea",              u"Стара гавань",       "gui/maps/icons/map/list/39_crimea.png"),
    ("40_nord_libya",          u"Піщана ріка",        "gui/maps/icons/map/list/40_nord_libya.png"),
    ("42_north_login",         u"Копальні",           "gui/maps/icons/map/list/42_north_login.png"),
    ("44_north_america",       u"Лайв Окс",           "gui/maps/icons/map/list/44_north_america.png"),
    ("45_north_america2",      u"Хайвей",             "gui/maps/icons/map/list/45_north_america2.png"),
    ("47_canada_a",            u"Кордон імперії",     "gui/maps/icons/map/list/47_canada_a.png"),
    ("49_wasatch",             u"Нормандія",          "gui/maps/icons/map/list/49_wasatch.png"),
    ("53_japan",               u"Студзянки",          "gui/maps/icons/map/list/53_japan.png"),
    ("54_Britain",             u"Оверлорд",           "gui/maps/icons/map/list/54_Britain.png"),
    ("57_maps_city",           u"Берлін",             "gui/maps/icons/map/list/57_maps_city.png"),
    ("58_underwater",          u"Тундра",             "gui/maps/icons/map/list/58_underwater.png"),
    ("59_asia",                u"Клондайк",           "gui/maps/icons/map/list/59_asia.png"),
    ("60_order",               u"Провінція",          "gui/maps/icons/map/list/60_order.png"),
    ("62_arktika",             u"Устрична затока",    "gui/maps/icons/map/list/62_arktika.png"),
    ("65_riverfront",          u"Вайдпарк",           "gui/maps/icons/map/list/65_riverfront.png"),
    ("66_water_e1_nation",     u"Промзона",           "gui/maps/icons/map/list/66_water_e1_nation.png"),
    ("67_haven",               u"Фата-моргана",       "gui/maps/icons/map/list/67_haven.png"),
    ("68_yard",                u"Париж",              "gui/maps/icons/map/list/68_yard.png"),
]


def _normalize_hotkey(codes):
    try:
        normalized = [int(code) for code in (codes or [])]
    except Exception:
        normalized = []
    return normalized


def _build_presets(weights):
    data = []
    weights = weights or {}
    for preset_id in PRESET_ORDER:
        data.append({
            'id': preset_id,
            'label': PRESET_LABELS.get(preset_id, preset_id),
            'guid': PRESET_GUIDS.get(preset_id),
            'previewSrc': '',
            'weight': int(weights.get(preset_id, DEFAULT_WEIGHT))
        })
    return data


def _build_payload(map_registry):
    general = g_controller.getGeneralWeights() or {}
    maps = []
    for map_id, label, thumb in map_registry:
        map_weights = g_controller.getMapWeights(map_id) or {}
        maps.append({
            'id': map_id,
            'label': label,
            'thumbSrc': thumb,
            'useGlobal': False,
            'presets': _build_presets(map_weights)
        })

    hotkey_codes = _normalize_hotkey(g_controller.getHotkey())
    hotkey_str = 'ALT+F12'
    if hotkey_codes:
        parts = []
        for code in hotkey_codes:
            if code == 18:
                parts.append('ALT')
            elif code == 17:
                parts.append('CTRL')
            elif code == 16:
                parts.append('SHIFT')
            elif 112 <= code <= 126:
                parts.append('F%s' % (code - 111))
            elif 48 <= code <= 57 or 65 <= code <= 90:
                parts.append(chr(code))
            else:
                parts.append('KEY_%s' % code)
        hotkey_str = '+'.join(parts)

    return {
        'presets': _build_presets(general),
        'maps': maps,
        'hotkey': hotkey_str,
        'hotkeyKeys': hotkey_codes,
    }


class WeatherWindowMeta(AbstractLobbyView):

    def __init__(self, *args, **kwargs):
        super(WeatherWindowMeta, self).__init__(*args, **kwargs)
        self._ctrl = g_controller

    def _populate(self):
        super(WeatherWindowMeta, self)._populate()
        payload = _build_payload(MAP_REGISTRY)
        self.flashObject.as_setData(payload)

    def py_onWeightChanged(self, mapId, presetId, value):
        map_id = mapId if mapId else None
        weights = self._ctrl.getGeneralWeights() if map_id is None else self._ctrl.getMapWeights(map_id)
        if weights is None:
            weights = {}
        weights[str(presetId)] = int(float(value))
        if map_id is None:
            self._ctrl.setGeneralWeights(weights)
        else:
            self._ctrl.setMapWeights(map_id, weights)

    def py_onMapSelected(self, mapId):
        pass

    def py_onTabChanged(self, tab):
        pass

    def py_onCloseRequested(self):
        self._ctrl.on_close_requested()
        self.destroy()

    def py_onHotkeyChanged(self, keyCodes, hotkeyStr):
        codes = _normalize_hotkey(keyCodes)
        self._ctrl.on_hotkey_changed(codes, str(hotkeyStr))

    def _dispose(self):
        self._ctrl.on_close_requested()
        super(WeatherWindowMeta, self)._dispose()
