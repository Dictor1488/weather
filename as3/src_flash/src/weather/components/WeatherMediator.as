package weather
{
    import flash.display.StageAlign;
    import flash.display.StageScaleMode;
    import flash.external.ExternalInterface;

    import net.wg.infrastructure.base.AbstractView;

    import weather.views.WeatherView;
    import weather.data.PresetVO;
    import weather.data.MapVO;
    import weather.events.WeatherEvent;

    public class WeatherMediator extends AbstractView
    {
        private var _view:WeatherView;
        private var _globalPresets:Vector.<PresetVO>;
        private var _maps:Vector.<MapVO>;
        private var _currentPreset:String;

        public function WeatherMediator()
        {
            super();
        }

        override protected function configUI():void
        {
            super.configUI();

            if (stage)
            {
                stage.align = StageAlign.TOP_LEFT;
                stage.scaleMode = StageScaleMode.NO_SCALE;
            }

            if (!_view)
                as_setData(makeDebugPayload());
        }

        override protected function onDispose():void
        {
            removeView();

            _globalPresets = null;
            _maps = null;

            super.onDispose();
        }

        private function removeView():void
        {
            if (_view)
            {
                _view.removeEventListener(WeatherEvent.PRESET_SELECTED, onPresetSelected);
                _view.removeEventListener(WeatherEvent.PRESET_WEIGHT_CHANGED, onWeightChanged);
                _view.removeEventListener(WeatherEvent.MAP_SELECTED, onMapSelected);
                _view.removeEventListener(WeatherEvent.TAB_CHANGED, onTabChanged);
                _view.removeEventListener(WeatherEvent.CLOSE_REQUESTED, onCloseRequested);
                _view.removeEventListener(WeatherEvent.HOTKEY_CHANGED, onHotkeyChanged);

                if (contains(_view))
                    removeChild(_view);

                _view = null;
            }
        }

        // ========== Python → AS3 ==========

        public function as_setData(payload:Object):void
        {
            if (!payload)
                payload = makeDebugPayload();

            visible = true;

            _globalPresets = parsePresets(payload.presets as Array);
            _maps          = parseMaps(payload.maps as Array);
            _currentPreset = String(payload.currentPreset || "standard");

            removeView();

            var hotkeyStr:String  = String(payload.hotkey || "F12");
            var hotkeyKeys:Array  = (payload.hotkeyKeys as Array) || [];

            _view = new WeatherView(_globalPresets, _maps, hotkeyStr, hotkeyKeys, _currentPreset);
            _view.addEventListener(WeatherEvent.PRESET_SELECTED, onPresetSelected);
            _view.addEventListener(WeatherEvent.PRESET_WEIGHT_CHANGED, onWeightChanged);
            _view.addEventListener(WeatherEvent.MAP_SELECTED, onMapSelected);
            _view.addEventListener(WeatherEvent.TAB_CHANGED, onTabChanged);
            _view.addEventListener(WeatherEvent.CLOSE_REQUESTED, onCloseRequested);
            _view.addEventListener(WeatherEvent.HOTKEY_CHANGED, onHotkeyChanged);
            addChild(_view);
        }

        public function as_showMapDetail(mapId:String):void
        {
            if (_view) _view.showMapDetail(mapId);
        }

        // ========== AS3 → Python ==========

        private function onPresetSelected(e:WeatherEvent):void
        {
            tryCallPython("py_onPresetSelected", [e.mapId, e.presetId]);
        }

        private function onWeightChanged(e:WeatherEvent):void
        {
            tryCallPython("py_onWeightChanged", [e.mapId, e.presetId, e.value]);
        }

        private function onMapSelected(e:WeatherEvent):void
        {
            tryCallPython("py_onMapSelected", [e.mapId]);
            if (_view) _view.showMapDetail(e.mapId);
        }

        private function onTabChanged(e:WeatherEvent):void
        {
            tryCallPython("py_onTabChanged", ["tab"]);
        }

        private function onCloseRequested(e:WeatherEvent):void
        {
            tryCallPython("py_onCloseRequested", []);
            removeView();
            visible = false;
        }

        private function onHotkeyChanged(e:WeatherEvent):void
        {
            tryCallPython("py_onHotkeyChanged", [e.payload as Array, String(e.mapId)]);
        }

        private function tryCallPython(methodName:String, args:Array):void
        {
            try
            {
                if (ExternalInterface.available)
                    ExternalInterface.call.apply(null, [methodName].concat(args));
            }
            catch (err:Error)
            {
                // Fallback to local stub so old clients do not throw from UI event handlers.
                if (methodName == "py_onPresetSelected") py_onPresetSelected(args[0], args[1]);
                else if (methodName == "py_onWeightChanged") py_onWeightChanged(args[0], args[1], Number(args[2]));
                else if (methodName == "py_onMapSelected") py_onMapSelected(args[0]);
                else if (methodName == "py_onTabChanged") py_onTabChanged(args[0]);
                else if (methodName == "py_onCloseRequested") py_onCloseRequested();
                else if (methodName == "py_onHotkeyChanged") py_onHotkeyChanged(args[0] as Array, String(args[1]));
            }
        }

        // DAAPI proxy fallback stubs.
        private function py_onPresetSelected(mapId:String, presetId:String):void {}
        private function py_onWeightChanged(mapId:String, presetId:String, value:Number):void {}
        private function py_onMapSelected(mapId:String):void {}
        private function py_onTabChanged(tab:String):void {}
        private function py_onCloseRequested():void {}
        private function py_onHotkeyChanged(keyCodes:Array, hotkeyStr:String):void {}

        // ========== Debug payload ==========

        private function makeDebugPayload():Object
        {
            var presets:Array = [
                {id:"standard", label:"Стандарт",  guid:"",                                    previewSrc:"../maps/icons/pro.environment/default.png",                              weight:20},
                {id:"midnight", label:"Ніч",       guid:"15755E11.4090266B.594778B6.B233C12C", previewSrc:"../maps/icons/pro.environment/15755E11.4090266B.594778B6.B233C12C.png", weight:20},
                {id:"overcast", label:"Похмуро",   guid:"56BA3213.40FFB1DF.125FBCAD.173E8347", previewSrc:"../maps/icons/pro.environment/56BA3213.40FFB1DF.125FBCAD.173E8347.png", weight:20},
                {id:"sunset",   label:"Захід",     guid:"6DEE1EBB.44F63FCC.AACF6185.7FBBC34E", previewSrc:"../maps/icons/pro.environment/6DEE1EBB.44F63FCC.AACF6185.7FBBC34E.png", weight:20},
                {id:"midday",   label:"Полудень",  guid:"BF040BCB.4BE1D04F.7D484589.135E881B", previewSrc:"../maps/icons/pro.environment/BF040BCB.4BE1D04F.7D484589.135E881B.png", weight:20}
            ];
            return {
                presets: presets,
                maps: [{id:"05_prohorovka", label:"Прохорівка", thumbSrc:"../maps/icons/map/list/05_prohorovka.png", useGlobal:false, presets:presets}],
                hotkey: "F12",
                hotkeyKeys: [],
                currentPreset: "standard"
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
                var p:PresetVO = new PresetVO(o.id, normalizeLabel(String(o.label)), o.guid, o.previewSrc);
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

        private function normalizeLabel(s:String):String
        {
            if (s == "Пасмурно" || s == "Хмарно" || s == "Overcast") return "Похмуро";
            if (s == "Закат"    || s == "Sunset")   return "Захід";
            if (s == "Полдень"  || s == "Midday")   return "Полудень";
            if (s == "Midnight" || s == "Ночь")     return "Ніч";
            if (s == "Standard" || s == "Стандарт") return "Стандарт";
            return s;
        }
    }
}
