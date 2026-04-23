package weather.events
{
    import flash.events.Event;

    public class WeatherEvent extends Event
    {
        public static const PRESET_WEIGHT_CHANGED:String = "presetWeightChanged";
        public static const MAP_SELECTED:String = "mapSelected";
        public static const TAB_CHANGED:String = "tabChanged";
        public static const CLOSE_REQUESTED:String = "closeRequested";
        public static const HOTKEY_CHANGED:String = "hotkeyChanged";
        public static const BACK_TO_MAPS:String = "backToMaps";

        public var mapId:String;
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
