package weather.events
{
    import flash.events.Event;

    /**
     * Події, які бродять між View → Mediator → Python.
     * 
     * В WoT Scaleform вихід у Python робиться через DAAPI (call з JS-like API).
     * Mediator слухає ці Event'и та викликає DAAPI-методи контролера.
     */
    public class WeatherEvent extends Event
    {
        // Користувач змінив вагу одного з пресетів (глобально або для карти)
        public static const PRESET_WEIGHT_CHANGED:String = "presetWeightChanged";

        // Клік по карті в сітці — відкрити екран детальних налаштувань
        public static const MAP_SELECTED:String = "mapSelected";

        // Перемикання вкладок "Загальні" / "По картах"
        public static const TAB_CHANGED:String = "tabChanged";

        // Закрити вікно (хрестик праворуч вгорі)
        public static const CLOSE_REQUESTED:String = "closeRequested";

        // Користувач перепризначив хоткей зміни погоди в бою
        public static const HOTKEY_CHANGED:String = "hotkeyChanged";

        public var mapId:String;       // null якщо global tab
        public var presetId:String;
        public var value:Number;
        public var payload:Object;

        public function WeatherEvent(type:String, bubbles:Boolean = true, cancelable:Boolean = false)
        {
            super(type, bubbles, cancelable);
        }

        override public function clone():Event
        {
            var e:WeatherEvent = new WeatherEvent(type, bubbles, cancelable);
            e.mapId = mapId;
            e.presetId = presetId;
            e.value = value;
            e.payload = payload;
            return e;
        }
    }
}
