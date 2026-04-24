package weather.views
{
    import flash.display.Sprite;
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

        private var _titleTF:TextField;
        private var _closeBtn:Sprite;
        private var _tabGlobal:TabButton;
        private var _tabMaps:TabButton;
        private var _contentHolder:Sprite;
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

            buildChrome();
            showTab(TAB_GLOBAL);
        }

        private function buildChrome():void
        {
            // --- фон ---
            var backdrop:Sprite = new Sprite();
            backdrop.graphics.beginFill(0x080808, 0.96);
            backdrop.graphics.drawRect(0, 0, 1280, 720);
            backdrop.graphics.endFill();
            addChild(backdrop);

            // --- верхня смуга ---
            var headerBg:Sprite = new Sprite();
            headerBg.graphics.beginFill(0x000000, 0.3);
            headerBg.graphics.drawRect(0, 0, 1280, 108);
            headerBg.graphics.endFill();
            addChild(headerBg);

            // --- акцентна лінія під хедером ---
            var headerLine:Sprite = new Sprite();
            headerLine.graphics.beginFill(0xF4A11A, 1);
            headerLine.graphics.drawRect(0, 106, 1280, 2);
            headerLine.graphics.endFill();
            addChild(headerLine);

            // --- заголовок ---
            _titleTF = new TextField();
            _titleTF.defaultTextFormat = new TextFormat("$TitleFont", 24, 0xFFFFFF, true);
            _titleTF.embedFonts  = true;
            _titleTF.selectable  = false;
            _titleTF.autoSize    = "left";
            _titleTF.text        = "Погода на картах";
            _titleTF.x = 32;
            _titleTF.y = 18;
            addChild(_titleTF);

            // --- підзаголовок ---
            var subTF:TextField = new TextField();
            subTF.defaultTextFormat = new TextFormat("$FieldFont", 12, 0x666666, false);
            subTF.embedFonts  = true;
            subTF.selectable  = false;
            subTF.autoSize    = "left";
            subTF.text        = "World of Tanks — налаштування environment";
            subTF.x = 34;
            subTF.y = 52;
            addChild(subTF);

            // --- кнопка закрити ---
            _closeBtn = new Sprite();
            _closeBtn.buttonMode    = true;
            _closeBtn.useHandCursor = true;
            _closeBtn.mouseChildren = false;

            _closeBtn.graphics.lineStyle(1, 0xF4A11A, 0.7);
            _closeBtn.graphics.beginFill(0x1A1000, 0.95);
            _closeBtn.graphics.drawRoundRect(0, 0, 120, 34, 4, 4);
            _closeBtn.graphics.endFill();

            var closeTF:TextField = new TextField();
            closeTF.defaultTextFormat = new TextFormat("$FieldFont", 13, 0xF4A11A, true);
            closeTF.embedFonts  = true;
            closeTF.selectable  = false;
            closeTF.autoSize    = "left";
            closeTF.text        = "ЗАКРИТИ  \u2715";
            closeTF.x = 14;
            closeTF.y = 8;
            _closeBtn.addChild(closeTF);
            _closeBtn.x = 1280 - 148;
            _closeBtn.y = 22;
            _closeBtn.addEventListener(MouseEvent.CLICK, function(e:MouseEvent):void {
                dispatchEvent(new WeatherEvent(WeatherEvent.CLOSE_REQUESTED));
            });
            addChild(_closeBtn);

            // --- таби ---
            _tabGlobal = new TabButton("ЗАГАЛЬНІ НАЛАШТУВАННЯ", 230);
            _tabGlobal.x = 340;
            _tabGlobal.y = 66;
            _tabGlobal.addEventListener(MouseEvent.CLICK, function(e:MouseEvent):void { showTab(TAB_GLOBAL); });
            addChild(_tabGlobal);

            _tabMaps = new TabButton("НАЛАШТУВАННЯ ПО КАРТАХ", 238);
            _tabMaps.x = 582;
            _tabMaps.y = 66;
            _tabMaps.addEventListener(MouseEvent.CLICK, function(e:MouseEvent):void { showTab(TAB_MAPS); });
            addChild(_tabMaps);

            // --- контент ---
            _contentHolder = new Sprite();
            _contentHolder.x = 0;
            _contentHolder.y = 124;
            addChild(_contentHolder);
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
                panel.addEventListener(WeatherEvent.HOTKEY_CHANGED,  onHotkeyChanged);
                panel.addEventListener(WeatherEvent.PRESET_SELECTED, onGlobalPresetSelected);
                _contentHolder.addChild(panel);
            }
            else
            {
                _contentHolder.addChild(new MapGridPanel(_maps));
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
            detail.addEventListener(WeatherEvent.BACK_TO_MAPS,     onBackToMaps);
            detail.addEventListener(WeatherEvent.PRESET_SELECTED,  onMapPresetSelected);
            _contentHolder.addChild(detail);
        }

        private function onBackToMaps(e:WeatherEvent):void   { showTab(TAB_MAPS); }

        private function onHotkeyChanged(e:WeatherEvent):void { dispatchEvent(e.clone()); }

        private function onGlobalPresetSelected(e:WeatherEvent):void
        {
            _currentPreset = e.presetId;
            dispatchEvent(e.clone());
        }

        private function onMapPresetSelected(e:WeatherEvent):void
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
    private var _underline:Sprite;
    private var _bg:Sprite;
    private var _w:int;
    private var _sel:Boolean = false;

    public function TabButton(text:String, widthHint:int = 220)
    {
        buttonMode    = true;
        useHandCursor = true;
        mouseChildren = false;
        _w = widthHint;

        _bg = new Sprite();
        addChild(_bg);

        _tf = new TextField();
        _tf.defaultTextFormat = new TextFormat("$FieldFont", 13, 0x8D8D8D, true);
        _tf.embedFonts  = true;
        _tf.selectable  = false;
        _tf.width       = _w;
        _tf.height      = 28;
        _tf.text        = text;
        _tf.y           = 7;
        addChild(_tf);

        _underline = new Sprite();
        addChild(_underline);

        redraw(false);
    }

    private function redraw(sel:Boolean):void
    {
        _bg.graphics.clear();
        _bg.graphics.lineStyle(1, sel ? 0x3C2A10 : 0x2A2A2A, sel ? 0.95 : 0.5);
        _bg.graphics.beginFill(sel ? 0x16110B : 0x0E0E0E, sel ? 0.99 : 0.85);
        _bg.graphics.drawRect(0, 0, _w, 34);
        _bg.graphics.endFill();

        _underline.graphics.clear();
        if (sel)
        {
            _underline.graphics.beginFill(0xF4A11A, 1);
            _underline.graphics.drawRect(0, 34, _w, 2);
            _underline.graphics.endFill();
        }
        _tf.textColor = sel ? 0xF7D3A1 : 0x7E7E7E;
    }

    public function set selected(v:Boolean):void { _sel = v; redraw(v); }
    public function get selected():Boolean { return _sel; }
}
