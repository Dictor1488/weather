package weather.components
{
    import flash.display.Shape;
    import flash.display.Sprite;
    import flash.events.MouseEvent;
    import flash.text.TextField;
    import flash.text.TextFormat;

    import weather.data.PresetVO;
    import weather.events.WeatherEvent;

    /**
     * Кнопка-картка пресету.
     * Замість слайдерів — великі кнопки з назвою та кольоровим акцентом.
     * Клік вмикає/вимикає пресет (toggle, тільки один активний).
     */
    public class PresetButton extends Sprite
    {
        public static const BTN_W:int = 188;
        public static const BTN_H:int = 88;

        // Кольори фону для кожного пресету
        private static const PRESET_COLORS:Object = {
            "standard": 0x1E2A1E,
            "midnight": 0x0D1A2E,
            "overcast": 0x1E2228,
            "sunset":   0x2E1A0A,
            "midday":   0x1E2A10
        };
        private static const PRESET_ACCENT:Object = {
            "standard": 0x4CAF50,
            "midnight": 0x3D7FCC,
            "overcast": 0x78909C,
            "sunset":   0xFF7043,
            "midday":   0xC8E64C
        };
        // Символ-іконка для пресету
        private static const PRESET_ICON:Object = {
            "standard": "\u2600",   // ☀ 
            "midnight": "\u263D",   // ☽
            "overcast": "\u2601",   // ☁
            "sunset":   "\uD83C\uDF05", // sunset glyph fallback → use text
            "midday":   "\u2605"    // ★
        };
        private static const PRESET_ICON_TEXT:Object = {
            "standard": "STD",
            "midnight": "NIC",
            "overcast": "HMR",
            "sunset":   "ZAH",
            "midday":   "POL"
        };

        private var _vo:PresetVO;
        private var _mapId:String;
        private var _selected:Boolean;

        private var _bg:Sprite;
        private var _accentBar:Shape;
        private var _selectedGlow:Shape;
        private var _labelTF:TextField;
        private var _iconTF:TextField;
        private var _checkmark:Shape;

        public function PresetButton(vo:PresetVO, mapId:String = null, selected:Boolean = false)
        {
            _vo = vo;
            _mapId = mapId;
            _selected = selected;

            buttonMode    = true;
            useHandCursor = true;
            mouseChildren = false;

            buildUI();
            addEventListener(MouseEvent.ROLL_OVER, onOver);
            addEventListener(MouseEvent.ROLL_OUT,  onOut);
            addEventListener(MouseEvent.CLICK,     onClick);
        }

        private function buildUI():void
        {
            var baseColor:uint  = PRESET_COLORS[_vo.id]  || 0x1A1A1A;
            var accentColor:uint = PRESET_ACCENT[_vo.id] || 0xF4A11A;

            // --- фон ---
            _bg = new Sprite();
            _bg.graphics.lineStyle(1, accentColor, _selected ? 0.9 : 0.2);
            _bg.graphics.beginFill(baseColor, _selected ? 1.0 : 0.82);
            _bg.graphics.drawRoundRect(0, 0, BTN_W, BTN_H, 6, 6);
            _bg.graphics.endFill();
            addChild(_bg);

            // --- нижня акцентна смужка ---
            _accentBar = new Shape();
            _accentBar.graphics.beginFill(accentColor, _selected ? 1.0 : 0.25);
            _accentBar.graphics.drawRect(0, BTN_H - 4, BTN_W, 4);
            _accentBar.graphics.endFill();
            addChild(_accentBar);

            // --- іконка (маленький блок ліворуч) ---
            var iconBg:Shape = new Shape();
            iconBg.graphics.beginFill(accentColor, 0.18);
            iconBg.graphics.drawRoundRect(10, 10, 34, 34, 4, 4);
            iconBg.graphics.endFill();
            addChild(iconBg);

            _iconTF = new TextField();
            _iconTF.defaultTextFormat = new TextFormat("$FieldFont", 13, accentColor, true);
            _iconTF.embedFonts  = true;
            _iconTF.selectable  = false;
            _iconTF.autoSize    = "left";
            _iconTF.text        = PRESET_ICON_TEXT[_vo.id] || "???";
            _iconTF.x           = 14;
            _iconTF.y           = 19;
            addChild(_iconTF);

            // --- назва пресету ---
            _labelTF = new TextField();
            _labelTF.defaultTextFormat = new TextFormat("$FieldFont", 16, _selected ? 0xFFFFFF : 0xBBBBBB, true);
            _labelTF.embedFonts  = true;
            _labelTF.selectable  = false;
            _labelTF.autoSize    = "left";
            _labelTF.text        = _vo.label;
            _labelTF.x           = 54;
            _labelTF.y           = 18;
            addChild(_labelTF);

            // --- підпис "активний" ---
            if (_selected)
            {
                var activeTF:TextField = new TextField();
                activeTF.defaultTextFormat = new TextFormat("$FieldFont", 10, accentColor, false);
                activeTF.embedFonts  = true;
                activeTF.selectable  = false;
                activeTF.autoSize    = "left";
                activeTF.text        = "АКТИВНИЙ";
                activeTF.x           = 54;
                activeTF.y           = 38;
                addChild(activeTF);
            }

            // --- checkmark (галочка) ---
            _checkmark = new Shape();
            redrawCheckmark(_selected, accentColor);
            addChild(_checkmark);
        }

        private function redrawCheckmark(show:Boolean, accentColor:uint):void
        {
            _checkmark.graphics.clear();
            if (!show) return;
            _checkmark.graphics.lineStyle(2.5, accentColor, 1);
            _checkmark.graphics.moveTo(BTN_W - 24, 14);
            _checkmark.graphics.lineTo(BTN_W - 18, 20);
            _checkmark.graphics.lineTo(BTN_W - 10, 10);
        }

        private function onOver(e:MouseEvent):void
        {
            if (_selected) return;
            var accentColor:uint = PRESET_ACCENT[_vo.id] || 0xF4A11A;
            _bg.graphics.clear();
            _bg.graphics.lineStyle(1, accentColor, 0.6);
            _bg.graphics.beginFill(PRESET_COLORS[_vo.id] || 0x1A1A1A, 0.98);
            _bg.graphics.drawRoundRect(0, 0, BTN_W, BTN_H, 6, 6);
            _bg.graphics.endFill();
        }

        private function onOut(e:MouseEvent):void
        {
            if (_selected) return;
            var accentColor:uint = PRESET_ACCENT[_vo.id] || 0xF4A11A;
            _bg.graphics.clear();
            _bg.graphics.lineStyle(1, accentColor, 0.2);
            _bg.graphics.beginFill(PRESET_COLORS[_vo.id] || 0x1A1A1A, 0.82);
            _bg.graphics.drawRoundRect(0, 0, BTN_W, BTN_H, 6, 6);
            _bg.graphics.endFill();
        }

        private function onClick(e:MouseEvent):void
        {
            var ev:WeatherEvent = new WeatherEvent(WeatherEvent.PRESET_SELECTED);
            ev.mapId    = _mapId;
            ev.presetId = _vo.id;
            dispatchEvent(ev);
        }

        public function setSelected(v:Boolean):void
        {
            if (_selected == v) return;
            _selected = v;

            var accentColor:uint = PRESET_ACCENT[_vo.id] || 0xF4A11A;
            _bg.graphics.clear();
            _bg.graphics.lineStyle(1, accentColor, _selected ? 0.9 : 0.2);
            _bg.graphics.beginFill(PRESET_COLORS[_vo.id] || 0x1A1A1A, _selected ? 1.0 : 0.82);
            _bg.graphics.drawRoundRect(0, 0, BTN_W, BTN_H, 6, 6);
            _bg.graphics.endFill();

            _accentBar.graphics.clear();
            _accentBar.graphics.beginFill(accentColor, _selected ? 1.0 : 0.25);
            _accentBar.graphics.drawRect(0, BTN_H - 4, BTN_W, 4);
            _accentBar.graphics.endFill();

            _labelTF.textColor = _selected ? 0xFFFFFF : 0xBBBBBB;
            redrawCheckmark(_selected, accentColor);
        }

        public function get presetId():String { return _vo.id; }
    }
}
