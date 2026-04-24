package weather.views
{
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

        private static const PANEL_W:int = 916;
        private static const PANEL_H:int = 690;

        private var _globalPresets:Vector.<PresetVO>;
        private var _maps:Vector.<MapVO>;
        private var _hotkeyStr:String;
        private var _hotkeyKeys:Array;
        private var _currentPreset:String;

        private var _overlay:Sprite;
        private var _panel:Sprite;
        private var _contentHolder:Sprite;
        private var _tabGlobal:TabButton;
        private var _tabMaps:TabButton;
        private var _closeBtn:Sprite;

        public function WeatherView(globalPresets:Vector.<PresetVO>, maps:Vector.<MapVO>, hotkey:String = "F12", hotkeyKeys:Array = null, currentPreset:String = "standard")
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
            showTab(TAB_MAPS);
        }

        private function sw():int { return stage ? stage.stageWidth : 1280; }
        private function sh():int { return stage ? stage.stageHeight : 720; }

        private function buildChrome():void
        {
            _overlay = new Sprite();
            _overlay.graphics.beginFill(0x000000, 0.12);
            _overlay.graphics.drawRect(0, 0, 4096, 2304);
            _overlay.graphics.endFill();
            addChild(_overlay);

            _panel = new Sprite();
            _panel.x = Math.max(20, int((sw() - PANEL_W) * 0.5));
            _panel.y = Math.max(20, int((sh() - PANEL_H) * 0.5));
            addChild(_panel);

            drawPanel();

            var title:TextField = makeText("Погода на картах", 26, 0xE8D8B8, true);
            title.x = 10;
            title.y = 10;
            _panel.addChild(title);

            _closeBtn = makeCloseButton();
            _closeBtn.x = PANEL_W - 114;
            _closeBtn.y = 12;
            _panel.addChild(_closeBtn);

            _tabGlobal = new TabButton("ЗАГАЛЬНІ НАЛАШТУВАННЯ", 230);
            _tabGlobal.x = int((PANEL_W - 460) * 0.5);
            _tabGlobal.y = 64;
            _tabGlobal.addEventListener(MouseEvent.CLICK, onGlobalTabClick);
            _panel.addChild(_tabGlobal);

            _tabMaps = new TabButton("НАЛАШТУВАННЯ ПО КАРТАХ", 230);
            _tabMaps.x = _tabGlobal.x + 230;
            _tabMaps.y = 64;
            _tabMaps.addEventListener(MouseEvent.CLICK, onMapsTabClick);
            _panel.addChild(_tabMaps);

            _contentHolder = new Sprite();
            _panel.addChild(_contentHolder);
        }

        private function onGlobalTabClick(e:MouseEvent):void { showTab(TAB_GLOBAL); }
        private function onMapsTabClick(e:MouseEvent):void { showTab(TAB_MAPS); }

        private function drawPanel():void
        {
            _panel.graphics.clear();
            _panel.graphics.lineStyle(1, 0x504632, 0.55);
            _panel.graphics.beginFill(0x0A0D12, 0.86);
            _panel.graphics.drawRect(0, 0, PANEL_W, PANEL_H);
            _panel.graphics.endFill();
            _panel.graphics.lineStyle(1, 0x252A30, 0.65);
            _panel.graphics.beginFill(0x0B1015, 0.38);
            _panel.graphics.drawRect(8, 102, PANEL_W - 16, PANEL_H - 112);
            _panel.graphics.endFill();
            _panel.graphics.beginFill(0xC08820, 1);
            _panel.graphics.drawRect(0, 102, PANEL_W, 2);
            _panel.graphics.endFill();
        }

        private function makeText(text:String, size:int, color:uint, bold:Boolean):TextField
        {
            var tf:TextField = new TextField();
            tf.defaultTextFormat = new TextFormat("_sans", size, color, bold);
            tf.selectable = false;
            tf.autoSize = "left";
            tf.text = text;
            return tf;
        }

        private function makeCloseButton():Sprite
        {
            var b:Sprite = new Sprite();
            b.buttonMode = true;
            b.useHandCursor = true;
            b.mouseChildren = false;

            var tf:TextField = makeText("ЗАКРИТИ ×", 14, 0xE07820, true);
            tf.x = 0;
            tf.y = 0;
            b.addChild(tf);
            b.addEventListener(MouseEvent.CLICK, onCloseClick);
            return b;
        }

        private function onCloseClick(e:MouseEvent):void
        {
            dispatchEvent(new WeatherEvent(WeatherEvent.CLOSE_REQUESTED));
        }

        public function showTab(tab:String):void
        {
            _tabGlobal.selected = (tab == TAB_GLOBAL);
            _tabMaps.selected   = (tab == TAB_MAPS);

            while (_contentHolder.numChildren > 0)
                _contentHolder.removeChildAt(0);

            if (tab == TAB_GLOBAL)
            {
                _contentHolder.x = 60;
                _contentHolder.y = 132;
                var panel:GlobalSettingsPanel = new GlobalSettingsPanel(_globalPresets, _hotkeyStr, _hotkeyKeys, _currentPreset);
                panel.addEventListener(WeatherEvent.HOTKEY_CHANGED, onHotkeyChanged);
                panel.addEventListener(WeatherEvent.PRESET_WEIGHT_CHANGED, onWeightChanged);
                _contentHolder.addChild(panel);
            }
            else
            {
                _contentHolder.x = 10;
                _contentHolder.y = 112;
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
            _contentHolder.x = 60;
            _contentHolder.y = 132;
            var detail:MapDetailPanel = new MapDetailPanel(map, _currentPreset);
            detail.addEventListener(WeatherEvent.BACK_TO_MAPS, onBackToMaps);
            detail.addEventListener(WeatherEvent.PRESET_WEIGHT_CHANGED, onWeightChanged);
            _contentHolder.addChild(detail);
        }

        private function onBackToMaps(e:WeatherEvent):void { showTab(TAB_MAPS); }
        private function onHotkeyChanged(e:WeatherEvent):void { dispatchEvent(e.clone()); }
        private function onWeightChanged(e:WeatherEvent):void { dispatchEvent(e.clone()); }
        private function onMapSelected(e:WeatherEvent):void
        {
            showMapDetail(e.mapId);
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

    public function TabButton(text:String, widthHint:int = 230)
    {
        buttonMode = true;
        useHandCursor = true;
        mouseChildren = false;
        _w = widthHint;
        _tf = new TextField();
        _tf.defaultTextFormat = new TextFormat("_sans", 12, 0x706860, true);
        _tf.selectable = false;
        _tf.width = _w;
        _tf.height = 34;
        _tf.text = text;
        _tf.x = 0;
        _tf.y = 10;
        addChild(_tf);
        redraw(false);
    }

    private function redraw(sel:Boolean):void
    {
        graphics.clear();
        graphics.lineStyle(1, sel ? 0xC08820 : 0x2E3338, 1);
        graphics.beginFill(sel ? 0x120D06 : 0x0C0E12, sel ? 0.9 : 0.6);
        graphics.drawRect(0, 0, _w, 38);
        graphics.endFill();
        if (sel)
        {
            graphics.beginFill(0xC08820, 1);
            graphics.drawRect(0, 35, _w, 3);
            graphics.endFill();
        }
        _tf.textColor = sel ? 0xF0D898 : 0x706860;
        _tf.x = int((_w - _tf.textWidth) * 0.5) - 2;
    }

    public function set selected(v:Boolean):void { _sel = v; redraw(v); }
    public function get selected():Boolean { return _sel; }
}
