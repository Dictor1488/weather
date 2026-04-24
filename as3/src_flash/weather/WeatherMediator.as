package weather
{
    import flash.display.Sprite;
    import flash.events.Event;

    import weather.views.WeatherView;
    import weather.data.PresetVO;
    import weather.data.MapVO;
    import weather.events.WeatherEvent;

    public class WeatherMediator extends Sprite
    {
        private var _view:WeatherView;
        private var _globalPresets:Vector.<PresetVO>;
        private var _maps:Vector.<MapVO>;
        private var _currentPreset:String;

        public function WeatherMediator()
        {
            super();
        }

        // ========== Python → AS3 ==========

        public function as_setData(payload:Object):void
        {
            _globalPresets = parsePresets(payload.presets);
            _maps          = parseMaps(payload.maps);
            _currentPreset = String(payload.currentPreset || "standard");

            if (_view)
            {
                removeChild(_view);
                _view = null;
            }

            var hotkeyStr:String  = String(payload.hotkey || "F12");
            var hotkeyKeys:Array  = payload.hotkeyKeys as Array || [];

            _view = new WeatherView(_globalPresets, _maps, hotkeyStr, hotkeyKeys, _currentPreset);
            _view.addEventListener(WeatherEvent.PRESET_SELECTED,     onPresetSelected);
            _view.addEventListener(WeatherEvent.MAP_SELECTED,        onMapSelected);
            _view.addEventListener(WeatherEvent.TAB_CHANGED,         onTabChanged);
            _view.addEventListener(WeatherEvent.CLOSE_REQUESTED,     onCloseRequested);
            _view.addEventListener(WeatherEvent.HOTKEY_CHANGED,      onHotkeyChanged);
            addChild(_view);
        }

        public function as_showMapDetail(mapId:String):void
        {
            if (_view) _view.showMapDetail(mapId);
        }

        // ========== AS3 → Python ==========

        private function onPresetSelected(e:WeatherEvent):void
        {
            // mapId == null → глобальний пресет; mapId != null → пресет для конкретної карти
            py_onPresetSelected(e.mapId, e.presetId);
        }

        private function onMapSelected(e:WeatherEvent):void
        {
            py_onMapSelected(e.mapId);
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

        private function onHotkeyChanged(e:WeatherEvent):void
        {
            py_onHotkeyChanged(e.payload as Array, String(e.mapId));
        }

        // DAAPI proxy — підміняються WoT інфраструктурою
        private function py_onPresetSelected(mapId:String, presetId:String):void {}
        private function py_onMapSelected(mapId:String):void {}
        private function py_onTabChanged(tab:String):void {}
        private function py_onCloseRequested():void {}
        private function py_onHotkeyChanged(keyCodes:Array, hotkeyStr:String):void {}

        // ========== Парсери ==========

        private function parsePresets(src:Array):Vector.<PresetVO>
        {
            var out:Vector.<PresetVO> = new Vector.<PresetVO>();
            if (!src) return out;
            for (var i:int = 0; i < src.length; i++)
            {
                var o:Object = src[i];
                var p:PresetVO = new PresetVO(o.id, o.label, o.guid, o.previewSrc);
                p.weight = Number(o.weight || 0);
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
