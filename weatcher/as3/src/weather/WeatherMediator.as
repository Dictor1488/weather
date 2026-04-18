package weather
{
    import flash.events.Event;

    import net.wg.infrastructure.base.AbstractView;

    import weather.views.WeatherView;
    import weather.data.PresetVO;
    import weather.data.MapVO;
    import weather.events.WeatherEvent;

    /**
     * Медіатор, який WoT-інфраструктура інстанціює, коли Python відкриває вікно.
     * 
     * ВХІД з Python (python викликає AS3 методи):
     *   as_setData(payload:Object)       — віддати масив presets + maps
     *   as_showMapDetail(mapId:String)   — відкрити деталі карти
     *   as_setHotkey(hotkey:String)      — оновити хоткей
     * 
     * ВИХІД в Python (AS3 викликає py-методи через DAAPI proxy):
     *   py_onWeightChanged(mapId, presetId, value)
     *   py_onMapSelected(mapId)
     *   py_onTabChanged(tab)
     *   py_onCloseRequested()
     * 
     * В WoT ці py_* прокидаються через this.flashObject.<funcName>(...) з Python,
     * і AS3 викликає їх просто як звичайні методи класу (DAAPI маршрутизує сам).
     */
    public class WeatherMediator extends AbstractView
    {
        private var _view:WeatherView;
        private var _globalPresets:Vector.<PresetVO>;
        private var _maps:Vector.<MapVO>;

        public function WeatherMediator()
        {
            super();
        }

        // ========== Вхідні (Python → AS3) ==========

        /**
         * Викликається Python'ом одразу після відкриття вікна.
         * payload = { presets: [...], maps: [...], hotkey: "ALT+F12" }
         */
        public function as_setData(payload:Object):void
        {
            _globalPresets = parsePresets(payload.presets);
            _maps = parseMaps(payload.maps);

            if (_view)
            {
                removeChild(_view);
                _view = null;
            }

            _view = new WeatherView(_globalPresets, _maps, String(payload.hotkey || "ALT+F12"));
            _view.addEventListener(WeatherEvent.PRESET_WEIGHT_CHANGED, onWeightChanged);
            _view.addEventListener(WeatherEvent.MAP_SELECTED, onMapSelected);
            _view.addEventListener(WeatherEvent.TAB_CHANGED, onTabChanged);
            _view.addEventListener(WeatherEvent.CLOSE_REQUESTED, onCloseRequested);
            addChild(_view);
        }

        public function as_showMapDetail(mapId:String):void
        {
            if (_view) _view.showMapDetail(mapId);
        }

        // ========== Вихідні (AS3 → Python) ==========

        private function onWeightChanged(e:WeatherEvent):void
        {
            // py_onWeightChanged — метод, зареєстрований DAAPI-скриптом з python-боку
            py_onWeightChanged(e.mapId, e.presetId, e.value);
        }

        private function onMapSelected(e:WeatherEvent):void
        {
            py_onMapSelected(e.mapId);
            // одразу локально показуємо деталі (щоб не чекати round-trip в python)
            if (_view) _view.showMapDetail(e.mapId);
        }

        private function onTabChanged(e:WeatherEvent):void
        {
            py_onTabChanged("tab");
        }

        private function onCloseRequested(e:WeatherEvent):void
        {
            py_onCloseRequested();
        }

        // Ці методи виглядають як звичайні private, але DAAPI підмінить їх
        // на RPC-проксі до Python. У Python-стороні реєструються колбеки
        // з такими ж іменами.
        private function py_onWeightChanged(mapId:String, presetId:String, value:Number):void {}
        private function py_onMapSelected(mapId:String):void {}
        private function py_onTabChanged(tab:String):void {}
        private function py_onCloseRequested():void {}

        // ========== Парсери (Python шле plain Object / Array) ==========

        private function parsePresets(src:Array):Vector.<PresetVO>
        {
            var out:Vector.<PresetVO> = new Vector.<PresetVO>();
            if (!src) return out;
            for (var i:int = 0; i < src.length; i++)
            {
                var o:Object = src[i];
                var p:PresetVO = new PresetVO(o.id, o.label, o.guid, o.previewSrc);
                p.weight = Number(o.weight);
                out.push(p);
            }
            return out;
        }

        private function parseMaps(src:Array):Vector.<MapVO>
        {
            var out:Vector.<MapVO> = new Vector.<MapVO>();
            if (!src) return out;
            for (var i:int = 0; i < src.length; i++)
            {
                var o:Object = src[i];
                var m:MapVO = new MapVO(o.id, o.label, o.thumbSrc);
                m.useGlobal = Boolean(o.useGlobal);
                m.presets = parsePresets(o.presets);
                out.push(m);
            }
            return out;
        }
    }
}
