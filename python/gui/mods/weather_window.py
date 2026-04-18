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

from weather_controller import g_controller

# Повний список карт (id, українська назва, шлях до мініатюри)
MAP_REGISTRY = [
    ("01_karelia",         u"Карелія",           "gui/maps/icons/map/list/01_karelia.png"),
    ("02_malinovka",       u"Малинівка",          "gui/maps/icons/map/list/02_malinovka.png"),
    ("03_campania",        u"Монастир",           "gui/maps/icons/map/list/03_campania.png"),
    ("04_himmelsdorf",     u"Хіммельсдорф",       "gui/maps/icons/map/list/04_himmelsdorf.png"),
    ("05_prohorovka",      u"Прохорівка",         "gui/maps/icons/map/list/05_prohorovka.png"),
    ("06_ensk",            u"Єнськ",              "gui/maps/icons/map/list/06_ensk.png"),
    ("07_lakeville",       u"Лейквілль",          "gui/maps/icons/map/list/07_lakeville.png"),
    ("08_ruinberg",        u"Руінберг",           "gui/maps/icons/map/list/08_ruinberg.png"),
    ("10_hills",           u"Круча",              "gui/maps/icons/map/list/10_hills.png"),
    ("11_murovanka",       u"Мурованка",          "gui/maps/icons/map/list/11_murovanka.png"),
    ("13_erlenberg",       u"Ерленберг",          "gui/maps/icons/map/list/13_erlenberg.png"),
    ("14_siegfried_line",  u"Лінія Зигфріда",     "gui/maps/icons/map/list/14_siegfried_line.png"),
    ("15_komarin",         u"Застава",            "gui/maps/icons/map/list/15_komarin.png"),
    ("17_munster",         u"Крафтверк",          "gui/maps/icons/map/list/17_munster.png"),
    ("18_cliff",           u"Перевал",            "gui/maps/icons/map/list/18_cliff.png"),
    ("19_monastery",       u"Редшир",             "gui/maps/icons/map/list/19_monastery.png"),
    ("22_slaughter",       u"Рибальська бухта",   "gui/maps/icons/map/list/22_slaughter.png"),
    ("23_westfeld",        u"Вестфілд",           "gui/maps/icons/map/list/23_westfeld.png"),
    ("25_el_hallouf",      u"Ель-Халлуф",         "gui/maps/icons/map/list/25_el_hallouf.png"),
    ("28_desert",          u"Загублене місто",    "gui/maps/icons/map/list/28_desert.png"),
    ("29_el_hallouf",      u"Провінція",          "gui/maps/icons/map/list/29_el_hallouf.png"),
    ("31_airfield",        u"Летовище",           "gui/maps/icons/map/list/31_airfield.png"),
    ("32_ offline_af",      u"Перлинна річка",     "gui/maps/icons/map/list/32_ offline_af.png"),
    ("33_fjord",           u"Фіорди",             "gui/maps/icons/map/list/33_fjord.png"),
    ("34_redshire",        u"Степи",              "gui/maps/icons/map/list/34_redshire.png"),
    ("35_steppes",         u"Степ",               "gui/maps/icons/map/list/35_steppes.png"),
    ("36_fishing_bay",     u"Тихий берег",        "gui/maps/icons/map/list/36_fishing_bay.png"),
    ("37_caucasus",        u"Перевал",            "gui/maps/icons/map/list/37_caucasus.png"),
    ("38_mannerheim_line", u"Лінія Маннергейма",  "gui/maps/icons/map/list/38_mannerheim_line.png"),
    ("39_crimea",          u"Стара гавань",       "gui/maps/icons/map/list/39_crimea.png"),
    ("40_nord_libya",      u"Піщана ріка",        "gui/maps/icons/map/list/40_nord_libya.png"),
    ("42_north_login",     u"Копальні",           "gui/maps/icons/map/list/42_north_login.png"),
    ("44_north_america",   u"Лайв Окс",           "gui/maps/icons/map/list/44_north_america.png"),
    ("45_north_america2",  u"Хайвей",             "gui/maps/icons/map/list/45_north_america2.png"),
    ("47_canada_a",        u"Кордон імперії",     "gui/maps/icons/map/list/47_canada_a.png"),
    ("49_wasatch",         u"Нормандія",          "gui/maps/icons/map/list/49_wasatch.png"),
    ("51_italy",           u"Монастир",           "gui/maps/icons/map/list/51_italy.png"),
    ("53_japan",           u"Студзянки",          "gui/maps/icons/map/list/53_japan.png"),
    ("54_Britain",         u"Оверлорд",           "gui/maps/icons/map/list/54_Britain.png"),
    ("57_maps_city",       u"Берлін",             "gui/maps/icons/map/list/57_maps_city.png"),
    ("58_underwater",      u"Тундра",             "gui/maps/icons/map/list/58_underwater.png"),
    ("59_asia",            u"Клондайк",           "gui/maps/icons/map/list/59_asia.png"),
    ("60_order",           u"Ласвілль",           "gui/maps/icons/map/list/60_order.png"),
    ("62_arktika",         u"Устрична затока",    "gui/maps/icons/map/list/62_arktika.png"),
    ("63_tundra",          u"Прохорівка",         "gui/maps/icons/map/list/63_tundra.png"),
    ("65_riverfront",      u"Вайдпарк",           "gui/maps/icons/map/list/65_riverfront.png"),
    ("66_water_e1_nation", u"Промзона",           "gui/maps/icons/map/list/66_water_e1_nation.png"),
    ("67_haven",           u"Фата-моргана",       "gui/maps/icons/map/list/67_haven.png"),
    ("68_yard",            u"Париж",              "gui/maps/icons/map/list/68_yard.png"),
]


class WeatherWindowMeta(AbstractLobbyView):

    def __init__(self, *args, **kwargs):
        super(WeatherWindowMeta, self).__init__(*args, **kwargs)
        self._ctrl = g_controller

    def _populate(self):
        super(WeatherWindowMeta, self)._populate()
        payload = self._ctrl.build_payload(MAP_REGISTRY)
        self.flashObject.as_setData(payload)

    # ========== AS3 → Python ==========

    def py_onWeightChanged(self, mapId, presetId, value):
        map_id = mapId if mapId else None
        self._ctrl.on_weight_changed(map_id, presetId, float(value))

    def py_onMapSelected(self, mapId):
        self._ctrl.on_map_selected(mapId)

    def py_onTabChanged(self, tab):
        pass

    def py_onCloseRequested(self):
        self._ctrl.on_close_requested()
        self.destroy()

    def py_onHotkeyChanged(self, keyCodes, hotkeyStr):
        """
        FIX 1: AS3 надсилає новий хоткей після того як користувач
        переназначив клавіші в UI. keyCodes — масив int.
        """
        if isinstance(keyCodes, (list, tuple)):
            codes = [int(c) for c in keyCodes]
        else:
            codes = []
        self._ctrl.on_hotkey_changed(codes, str(hotkeyStr))

    def _dispose(self):
        self._ctrl.on_close_requested()
        super(WeatherWindowMeta, self)._dispose()
