# -*- coding: utf-8 -*-
"""
DAAPI-міст між Flash (WeatherMediator.as) та weather_controller.

У WoT мод-UI будується на DAAPI (DirectAccessApi) — механізмі, що
експонує Python-методи у ActionScript. Ми успадковуємо від
LobbySubView / AbstractWindowView залежно від того, як інтегруємося.
"""

try:
    from gui.Scaleform.daapi.view.lobby.AbstractLobbyView import AbstractLobbyView
    from gui.Scaleform.framework.entities.View import View
    IN_GAME = True
except ImportError:
    IN_GAME = False
    class AbstractLobbyView(object):  # заглушка для розробки поза грою
        def __init__(self, *args, **kw): pass
        def _populate(self): pass
        def _dispose(self): pass

from weather_controller import g_controller


# Маппінг id карти → локалізована назва → шлях до превью.
# У продакшен-моді це тягнеться з ResMgr / i18n.
MAP_REGISTRY = [
    ("02_malinovka",   u"Малинівка",       "gui/maps/icons/maps/02_malinovka.dds"),
    ("04_himmelsdorf", u"Хіммельсдорф",    "gui/maps/icons/maps/04_himmelsdorf.dds"),
    ("05_prohorovka",  u"Прохорівка",      "gui/maps/icons/maps/05_prohorovka.dds"),
    ("06_ensk",        u"Енськ",           "gui/maps/icons/maps/06_ensk.dds"),
    # ... усі 48 карт з архіву, лінь переписувати
]


class WeatherWindowMeta(AbstractLobbyView):
    """
    Вікно "Погода на картах". Відкривається з налаштувань модів
    або по хоткею (наприклад, через izeberg.modssettingsapi).
    """

    def __init__(self, *args, **kwargs):
        super(WeatherWindowMeta, self).__init__(*args, **kwargs)
        self._ctrl = g_controller

    def _populate(self):
        super(WeatherWindowMeta, self)._populate()
        # Відправляємо початковий стан у Flash
        payload = self._ctrl.build_payload(MAP_REGISTRY)
        self.flashObject.as_setData(payload)

    # ========================================================
    # Методи, які викликає AS3 (через py_* у WeatherMediator.as)
    # ========================================================

    def py_onWeightChanged(self, mapId, presetId, value):
        # mapId може бути None → глобальна вкладка
        if mapId == "" or mapId is None:
            mapId = None
        self._ctrl.on_weight_changed(mapId, presetId, value)

    def py_onMapSelected(self, mapId):
        self._ctrl.on_map_selected(mapId)

    def py_onTabChanged(self, tab):
        pass  # поки нічого не робимо, достатньо для логування

    def py_onCloseRequested(self):
        self._ctrl.on_close_requested()
        self.destroy()

    def _dispose(self):
        self._ctrl.on_close_requested()
        super(WeatherWindowMeta, self)._dispose()
