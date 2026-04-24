package weather.views
{
    import flash.display.Shape;
    import flash.display.Sprite;
    import flash.events.Event;
    import flash.events.MouseEvent;
    import flash.text.TextField;
    import flash.text.TextFormat;

    import weather.data.PresetVO;
    import weather.data.MapVO;
    import weather.events.WeatherEvent;

    public class WeatherView extends Sprite
    {
        public static const TAB_GLOBAL:String = "global";
        public static const TAB_MAPS:String   = "maps";

        private var _globalPresets:Vector.<PresetVO>;
        private var _maps:Vector.<MapVO>;
        private var _hotkeyStr:String;
        private var _hotkeyKeys:Array;
        private var _currentPreset:String;

        private var _bg:Sprite;
        private var _top:Sprite;
        private var _contentHolder:Sprite;
        private var _closeBtn:Sprite;
        private var _tabGlobal:TabButton;
        private var _tabMaps:TabButton;
        private var _currentTab:String;

        public function WeatherView(globalPresets:Vector.<PresetVO>,
                                    maps:Vector.<MapVO>,
                                    hotkey:String = "F12",
                                    hotkeyKeys:Array = null,
                                    currentPreset:String = "standard")
        {
            _globalPresets = globalPresets;
            _maps          = maps;
            _hotkeyStr     = hotkey;
            _hotkeyKeys    = hotkeyKeys || [];
            _currentPreset = currentPreset || "standard";

            addEventListener(Event.ADDED_TO_STAGE, onAdded);
        }

        private function onAdded(e:Event):void
        {
            removeEventListener(Event.ADDED_TO_STAGE, onAdded);
            buildChrome();
            showTab(TAB_GLOBAL);
        }

        private function buildChrome():void
        {
            // Draw oversized full-screen overlay so it covers high-resolution clients too.
            _bg = new Sprite();
            _bg.graphics.beginFill(0x050607, 0.86);
            _bg.graphics.drawRect(0, 0, 4096, 2304);
            _bg.graphics.endFill();
            addChild(_bg);

            // soft vignette
            var shade:Shape = new Shape();
            shade.graphics.beginFill(0x111820, 0.70);
            shade.graphics.drawRect(0, 92, 4096, 2304);
            shade.graphics.endFill();
            addChild(shade);

            _top = new Sprite();
            _top.graphics.beginFill(0x050505, 0.72);
            _top.graphics.drawRect(0, 0, 4096, 92);
            _top.graphics.endFill();
            addChild(_top);

            var title:TextField = new TextField();
            title.defaultTextFormat = new TextFormat("_sans", 25, 0xF2E7CE, true);
            title.selectable  = false;
            title.autoSize    = "left";
            title.text        = "Погода на картах";
            title.x = 36;
            title.y = 20;
            addChild(title);

            var line:Shape = new Shape();
            line.graphics.beginFill(0xC4861B, 1);
            line.graphics.drawRect(0, 91, 4096, 2);
            line.graphics.endFill();
            addChild(line);

            _closeBtn = makeCloseButton();
            _closeBtn.x = 1080;
            _closeBtn.y = 18;
            addChild(_closeBtn);

            _tabGlobal = new TabButton("ЗАГАЛЬНІ НАЛАШТУВАННЯ", 230);
            _tabGlobal.x = 330;
            _tabGlobal.y = 58;
            _tabGlobal.addEventListener(MouseEvent.CLICK, function(e:MouseEvent):void { showTab(TAB_GLOBAL); });
            addChild(_tabGlobal);

            _tabMaps = new TabButton("НАЛАШТУВАННЯ ПО КАРТАХ", 230);
            _tabMaps.x = 560;
            _tabMaps.y = 58;
            _tabMaps.addEventListener(MouseEvent.CLICK, function(e:MouseEvent):void { showTab(TAB_MAPS); });
            addChild(_tabMaps);

            _contentHolder = new Sprite();
            _contentHolder.x = 0;
            _contentHolder.y = 92;
            addChild(_contentHolder);
        }

        private function makeCloseButton():Sprite
        {
            var b:Sprite = new Sprite();
            b.buttonMode = true;
            b.useHandCursor = true;
            b.mouseChildren = false;

            b.graphics.lineStyle(1, 0xC4861B, 0.9);
            b.graphics.beginFill(0x120D08, 0.55);
            b.graphics.drawRect(0, 0, 120, 34);
            b.graphics.endFill();

            var tf:TextField = new TextField();
            tf.defaultTextFormat = new TextFormat("_sans", 13, 0xFFB35A, true);
            tf.selectable = false;
            tf.autoSize = "left";
            tf.text = "ЗАКРИТИ  ✕";
            tf.x = 18;
            tf.y = 8;
            b.addChild(tf);

            b.addEventListener(MouseEvent.CLICK, function(e:MouseEvent):void {
                dispatchEvent(new WeatherEvent(WeatherEvent.CLOSE_REQUESTED));
            });
            return b;
        }

        public function showTab(tab:String):void
        {
            _currentTab = tab;
            _tabGlobal.selected = (tab == TAB_GLOBAL);
            _tabMaps.selected   = (tab == TAB_MAPS);

            while (_contentHolder.numChildren > 0)
                _contentHolder.removeChildAt(0);

            if (tab == TAB_GLOBAL)
            {
                var panel:GlobalSettingsPanel = new GlobalSettingsPanel(
                    _globalPresets, _hotkeyStr, _hotkeyKeys, _currentPreset
                );
                panel.addEventListener(WeatherEvent.HOTKEY_CHANGED, onHotkeyChanged);
                panel.addEventListener(WeatherEvent.PRESET_SELECTED, onGlobalPresetSelected);
                panel.addEventListener(WeatherEvent.PRESET_WEIGHT_CHANGED, onWeightChanged);
                _contentHolder.addChild(panel);
            }
            else
            {
                var grid:MapGridPanel = new MapGridPanel(_maps);
                grid.addEventListener(WeatherEvent.MAP_SELECTED, onMapSelected);
                _contentHolder.addChild(grid);
            }

            dispatchEvent(new WeatherEvent(WeatherEvent.TAB_CHANGED));
        }

        public function showMapDetail(mapId:String):void
        {
            var map:MapVO = findMap(mapId);
            if (!map) return;

            while (_contentHolder.numChildren > 0)
                _contentHolder.removeChildAt(0);

            var detail:MapDetailPanel = new MapDetailPanel(map, _currentPreset);
            detail.addEventListener(WeatherEvent.BACK_TO_MAPS, onBackToMaps);
            detail.addEventListener(WeatherEvent.PRESET_SELECTED, onMapPresetSelected);
            detail.addEventListener(WeatherEvent.PRESET_WEIGHT_CHANGED, onWeightChanged);
            _contentHolder.addChild(detail);
        }

        private function onBackToMaps(e:WeatherEvent):void { showTab(TAB_MAPS); }
        private function onHotkeyChanged(e:WeatherEvent):void { dispatchEvent(e.clone()); }
        private function onWeightChanged(e:WeatherEvent):void { dispatchEvent(e.clone()); }

        private function onGlobalPresetSelected(e:WeatherEvent):void
        {
            _currentPreset = e.presetId;
            dispatchEvent(e.clone());
        }

        private function onMapPresetSelected(e:WeatherEvent):void
        {
            dispatchEvent(e.clone());
        }

        private function onMapSelected(e:WeatherEvent):void
        {
            dispatchEvent(e.clone());
        }

        private function findMap(id:String):MapVO
        {
            for (var i:int = 0; i < _maps.length; i++)
                if (_maps[i].id == id) return _maps[i];
            return null;
        }
    }
}

import flash.display.Sprite;
import flash.text.TextField;
import flash.text.TextFormat;

class TabButton extends Sprite
{
    private var _tf:TextField;
    private var _w:int;
    private var _sel:Boolean = false;

    public function TabButton(text:String, widthHint:int = 220)
    {
        buttonMode = true;
        useHandCursor = true;
        mouseChildren = false;
        _w = widthHint;

        _tf = new TextField();
        _tf.defaultTextFormat = new TextFormat("_sans", 13, 0x807A70, true);
        _tf.selectable = false;
        _tf.width = _w;
        _tf.height = 28;
        _tf.text = text;
        _tf.x = 0;
        _tf.y = 7;
        addChild(_tf);

        redraw(false);
    }

    private function redraw(sel:Boolean):void
    {
        graphics.clear();
        graphics.lineStyle(1, sel ? 0xB97A28 : 0x1A1A1A, sel ? 1 : 0.8);
        graphics.beginFill(sel ? 0x170F09 : 0x0B0C0D, sel ? 0.95 : 0.45);
        graphics.drawRect(0, 0, _w, 34);
        graphics.endFill();

        if (sel)
        {
            graphics.beginFill(0xE19A24, 1);
            graphics.drawRect(0, 33, _w, 2);
            graphics.endFill();
        }

        _tf.textColor = sel ? 0xF5D7A0 : 0x807A70;
    }

    public function set selected(v:Boolean):void { _sel = v; redraw(v); }
    public function get selected():Boolean { return _sel; }
}
