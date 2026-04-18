package weather.views
{
    import flash.display.Sprite;
    import flash.events.Event;
    import flash.events.MouseEvent;
    import flash.text.TextField;
    import flash.text.TextFormat;

    import weather.components.PresetRow;
    import weather.components.MapTile;
    import weather.data.PresetVO;
    import weather.data.MapVO;
    import weather.events.WeatherEvent;

    /**
     * Головне вікно "Погода на картах".
     * 
     * Структура:
     *   ┌──────────────────────────────────────────────┐
     *   │ [Title: "Погода на картах"]       [X Закрити]│
     *   ├──────────────────────────────────────────────┤
     *   │     [Загальні налаштування] [По картах]      │
     *   ├──────────────────────────────────────────────┤
     *   │                                              │
     *   │              <Активний вміст>                │
     *   │                                              │
     *   └──────────────────────────────────────────────┘
     * 
     * Вміст перемикається між GlobalSettingsPanel і MapGridPanel.
     * Третій стан — MapDetailPanel (клік по карті в сітці).
     */
    public class WeatherView extends Sprite
    {
        public static const TAB_GLOBAL:String = "global";
        public static const TAB_MAPS:String = "maps";

        private var _globalPresets:Vector.<PresetVO>;
        private var _maps:Vector.<MapVO>;
        private var _hotkey:String = "ALT+F12";

        private var _titleTF:TextField;
        private var _closeBtn:Sprite;
        private var _tabGlobal:TabButton;
        private var _tabMaps:TabButton;
        private var _contentHolder:Sprite;
        private var _currentTab:String;

        public function WeatherView(globalPresets:Vector.<PresetVO>, maps:Vector.<MapVO>, hotkey:String = "ALT+F12")
        {
            _globalPresets = globalPresets;
            _maps = maps;
            _hotkey = hotkey;

            buildChrome();
            showTab(TAB_GLOBAL);
        }

        private function buildChrome():void
        {
            // Затемнення-фон
            var backdrop:Sprite = new Sprite();
            backdrop.graphics.beginFill(0x0A0A0A, 0.9);
            backdrop.graphics.drawRect(0, 0, 1280, 720);
            backdrop.graphics.endFill();
            addChild(backdrop);

            // Заголовок
            _titleTF = new TextField();
            _titleTF.defaultTextFormat = new TextFormat("$TitleFont", 22, 0xFFFFFF, true);
            _titleTF.embedFonts = true;
            _titleTF.selectable = false;
            _titleTF.autoSize = "left";
            _titleTF.text = "Погода на картах";
            _titleTF.x = 30;
            _titleTF.y = 20;
            addChild(_titleTF);

            // Кнопка закриття (помаранчева "ЗАКРИТИ  X" як на скріні)
            _closeBtn = new Sprite();
            _closeBtn.buttonMode = true;
            _closeBtn.useHandCursor = true;
            var closeTF:TextField = new TextField();
            closeTF.defaultTextFormat = new TextFormat("$FieldFont", 14, 0xF4A11A, true);
            closeTF.embedFonts = true;
            closeTF.selectable = false;
            closeTF.autoSize = "left";
            closeTF.text = "ЗАКРИТИ  ✕";
            _closeBtn.addChild(closeTF);
            _closeBtn.x = 1280 - 110;
            _closeBtn.y = 24;
            _closeBtn.addEventListener(MouseEvent.CLICK, function(e:MouseEvent):void {
                dispatchEvent(new WeatherEvent(WeatherEvent.CLOSE_REQUESTED));
            });
            addChild(_closeBtn);

            // Вкладки
            _tabGlobal = new TabButton("ЗАГАЛЬНІ НАЛАШТУВАННЯ");
            _tabGlobal.x = 400;
            _tabGlobal.y = 70;
            _tabGlobal.addEventListener(MouseEvent.CLICK, function(e:MouseEvent):void { showTab(TAB_GLOBAL); });
            addChild(_tabGlobal);

            _tabMaps = new TabButton("НАЛАШТУВАННЯ ПО КАРТАХ");
            _tabMaps.x = 620;
            _tabMaps.y = 70;
            _tabMaps.addEventListener(MouseEvent.CLICK, function(e:MouseEvent):void { showTab(TAB_MAPS); });
            addChild(_tabMaps);

            // Контейнер вмісту
            _contentHolder = new Sprite();
            _contentHolder.x = 0;
            _contentHolder.y = 110;
            addChild(_contentHolder);
        }

        public function showTab(tab:String):void
        {
            _currentTab = tab;
            _tabGlobal.selected = (tab == TAB_GLOBAL);
            _tabMaps.selected = (tab == TAB_MAPS);

            while (_contentHolder.numChildren > 0)
                _contentHolder.removeChildAt(0);

            if (tab == TAB_GLOBAL)
                _contentHolder.addChild(new GlobalSettingsPanel(_globalPresets, _hotkey));
            else
                _contentHolder.addChild(new MapGridPanel(_maps));

            dispatchEvent(new WeatherEvent(WeatherEvent.TAB_CHANGED));
        }

        public function showMapDetail(mapId:String):void
        {
            var map:MapVO = findMap(mapId);
            if (!map) return;

            while (_contentHolder.numChildren > 0)
                _contentHolder.removeChildAt(0);

            _contentHolder.addChild(new MapDetailPanel(map));
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

/** Допоміжна кнопка-вкладка (внутрішній клас — тільки для цього файлу). */
class TabButton extends Sprite
{
    private var _tf:TextField;
    private var _underline:Sprite;
    private var _selected:Boolean;

    public function TabButton(text:String)
    {
        buttonMode = true;
        useHandCursor = true;
        mouseChildren = false;

        _tf = new TextField();
        _tf.defaultTextFormat = new TextFormat("$FieldFont", 14, 0x888888, true);
        _tf.embedFonts = true;
        _tf.selectable = false;
        _tf.autoSize = "left";
        _tf.text = text;
        addChild(_tf);

        _underline = new Sprite();
        _underline.graphics.beginFill(0xF4A11A);
        _underline.graphics.drawRect(0, _tf.height + 6, _tf.width, 2);
        _underline.graphics.endFill();
        _underline.visible = false;
        addChild(_underline);
    }

    public function set selected(v:Boolean):void
    {
        _selected = v;
        _underline.visible = v;
        _tf.textColor = v ? 0xFFFFFF : 0x888888;
    }

    public function get selected():Boolean { return _selected; }
}
