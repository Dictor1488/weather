package weather
{
    import flash.display.Sprite;
    import flash.events.Event;
    import flash.display.StageAlign;
    import flash.display.StageScaleMode;

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
            addEventListener(Event.ADDED_TO_STAGE, onAddedToStage);
        }

        private function onAddedToStage(e:Event):void
        {
            removeEventListener(Event.ADDED_TO_STAGE, onAddedToStage);
            if (stage)
            {
                stage.align = StageAlign.TOP_LEFT;
                stage.scaleMode = StageScaleMode.NO_SCALE;
            }

            // Debug/fallback mode. У грі Python одразу викличе as_setData() і замінить ці дані.
            // Якщо SWF відкрито окремо або DAAPI не викликав as_setData, UI не буде порожнім.
            if (!_view)
                as_setData(makeDebugPayload());
        }

        // ========== Python → AS3 ==========

        public function as_setData(payload:Object):void
        {
            if (!payload)
                payload = makeDebugPayload();

            _globalPresets = parsePresets(payload.presets as Array);
            _maps          = parseMaps(payload.maps as Array);
            _currentPreset = String(payload.currentPreset || "standard");

            if (_view)
            {
                if (contains(_view))
                    removeChild(_view);
                _view = null;
            }

            var hotkeyStr:String  = String(payload.hotkey || "F12");
            var hotkeyKeys:Array  = (payload.hotkeyKeys as Array) || [];

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

        // ========== Debug payload ==========

        private function makeDebugPayload():Object
        {
            var presets:Array = [
                {id:"standard", label:"Standard", guid:"", previewSrc:"gui/maps/icons/pro.environment/default.png", weight:20},
                {id:"midnight", label:"Night", guid:"15755E11.4090266B.594778B6.B233C12C", previewSrc:"gui/maps/icons/pro.environment/15755E11.4090266B.594778B6.B233C12C.png", weight:20},
                {id:"overcast", label:"Overcast", guid:"56BA3213.40FFB1DF.125FBCAD.173E8347", previewSrc:"gui/maps/icons/pro.environment/56BA3213.40FFB1DF.125FBCAD.173E8347.png", weight:20},
                {id:"sunset", label:"Sunset", guid:"6DEE1EBB.44F63FCC.AACF6185.7FBBC34E", previewSrc:"gui/maps/icons/pro.environment/6DEE1EBB.44F63FCC.AACF6185.7FBBC34E.png", weight:20},
                {id:"midday", label:"Midday", guid:"BF040BCB.4BE1D04F.7D484589.135E881B", previewSrc:"gui/maps/icons/pro.environment/BF040BCB.4BE1D04F.7D484589.135E881B.png", weight:20}
            ];
            return {
                presets: presets,
                maps: [{id:"05_prohorovka", label:"Prohorovka", thumbSrc:"gui/maps/icons/map/list/05_prohorovka.png", useGlobal:false, presets:presets}],
                hotkey: "F12",
                hotkeyKeys: [],
                currentPreset: "midday"
            };
        }

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
                m.presets = parsePresets(o.presets as Array);
                out.push(m);
            }
            return out;
        }
    }
}
