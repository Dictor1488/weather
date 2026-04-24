package weather.views
{
    import flash.display.Shape;
    import flash.display.Sprite;
    import flash.events.KeyboardEvent;
    import flash.events.MouseEvent;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.ui.Keyboard;

    import weather.components.PresetButton;
    import weather.data.PresetVO;
    import weather.events.WeatherEvent;

    public class GlobalSettingsPanel extends Sprite
    {
        private static const PAD_LEFT:int = 96;
        private static const PAD_TOP:int  = 28;
        private static const BTN_GAP:int  = 16;

        private var _hotkeyKeys:Array;
        private var _hotkeyStr:String;
        private var _capturing:Boolean = false;
        private var _captureCodes:Array;
        private var _currentPresetId:String;
        private var _buttons:Vector.<PresetButton>;
        private var _chipContainer:Sprite;

        public function GlobalSettingsPanel(presets:Vector.<PresetVO>,
                                            hotkey:String,
                                            hotkeyKeys:Array,
                                            currentPreset:String = "standard")
        {
            _hotkeyStr     = hotkey;
            _hotkeyKeys    = hotkeyKeys ? hotkeyKeys.slice() : [];
            _captureCodes  = [];
            _currentPresetId = currentPreset || "standard";
            _buttons       = new Vector.<PresetButton>();
            build(presets);
        }

        private function build(presets:Vector.<PresetVO>):void
        {
            var hdr:TextField = new TextField();
            hdr.defaultTextFormat = new TextFormat("$FieldFont", 13, 0x888888, false);
            hdr.embedFonts  = true;
            hdr.selectable  = false;
            hdr.autoSize    = "left";
            hdr.text        = "АКТИВНИЙ ПРЕСЕТ ДЛЯ ВСІХ КАРТ";
            hdr.x           = PAD_LEFT;
            hdr.y           = PAD_TOP - 20;
            addChild(hdr);

            var bx:int = PAD_LEFT;
            var by:int = PAD_TOP;
            for (var i:int = 0; i < presets.length; i++)
            {
                var isActive:Boolean = (presets[i].id == _currentPresetId);
                var btn:PresetButton = new PresetButton(presets[i], null, isActive);
                btn.x = bx;
                btn.y = by;
                btn.addEventListener(WeatherEvent.PRESET_SELECTED, onPresetSelected);
                addChild(btn);
                _buttons.push(btn);
                bx += PresetButton.BTN_W + BTN_GAP;
                if ((i + 1) % 5 == 0) { bx = PAD_LEFT; by += PresetButton.BTN_H + BTN_GAP; }
            }

            var dividerY:int = by + PresetButton.BTN_H + 28;
            var divider:Shape = new Shape();
            divider.graphics.lineStyle(1, 0x2A2A2A, 0.9);
            divider.graphics.moveTo(PAD_LEFT, 0);
            divider.graphics.lineTo(1184, 0);
            divider.y = dividerY;
            addChild(divider);

            var hkY:int = dividerY + 22;

            var hkHdr:TextField = new TextField();
            hkHdr.defaultTextFormat = new TextFormat("$FieldFont", 13, 0x888888, false);
            hkHdr.embedFonts  = true;
            hkHdr.selectable  = false;
            hkHdr.autoSize    = "left";
            hkHdr.text        = "ХОТКЕЙ — ЗМІНА ПОГОДИ В БОЮ";
            hkHdr.x           = PAD_LEFT;
            hkHdr.y           = hkY;
            addChild(hkHdr);

            var hkLabel:TextField = new TextField();
            hkLabel.defaultTextFormat = new TextFormat("$FieldFont", 15, 0xCCCCCC, false);
            hkLabel.embedFonts  = true;
            hkLabel.selectable  = false;
            hkLabel.autoSize    = "left";
            hkLabel.text        = "Натиснення в бою циклічно перемикає пресет";
            hkLabel.x           = PAD_LEFT;
            hkLabel.y           = hkY + 22;
            addChild(hkLabel);

            _chipContainer = new Sprite();
            _chipContainer.x = PAD_LEFT + 520;
            _chipContainer.y = hkY + 20;
            addChild(_chipContainer);
            rebuildChipsFromString(_hotkeyStr);

            var editBtn:Sprite = makeEditButton();
            editBtn.x = PAD_LEFT + 700;
            editBtn.y = hkY + 20;
            addChild(editBtn);

            var tip:TextField = new TextField();
            tip.defaultTextFormat = new TextFormat("$FieldFont", 12, 0x555555, false);
            tip.embedFonts  = true;
            tip.selectable  = false;
            tip.autoSize    = "left";
            tip.text        = "Для налаштування погоди на конкретній карті — перейдіть на вкладку \u00abПо картах\u00bb";
            tip.x           = PAD_LEFT;
            tip.y           = hkY + 56;
            addChild(tip);
        }

        private function onPresetSelected(e:WeatherEvent):void
        {
            var newId:String = e.presetId;
            if (newId == _currentPresetId) return;
            _currentPresetId = newId;
            for (var i:int = 0; i < _buttons.length; i++)
                _buttons[i].setSelected(_buttons[i].presetId == _currentPresetId);
            var ev:WeatherEvent = new WeatherEvent(WeatherEvent.PRESET_SELECTED, true);
            ev.mapId    = null;
            ev.presetId = _currentPresetId;
            dispatchEvent(ev);
        }

        private function rebuildChipsFromString(value:String):void
        {
            while (_chipContainer.numChildren > 0) _chipContainer.removeChildAt(0);
            var keys:Array = value ? value.split("+") : [];
            var cx:int = 0;
            for (var i:int = 0; i < keys.length; i++)
            {
                var chip:Sprite = makeKeyChip(String(keys[i]).toUpperCase());
                chip.x = cx;
                _chipContainer.addChild(chip);
                cx += chip.width + 8;
            }
        }

        private function rebuildChipsFromCodes(codes:Array):void
        {
            while (_chipContainer.numChildren > 0) _chipContainer.removeChildAt(0);
            var cx:int = 0;
            for (var i:int = 0; i < codes.length; i++)
            {
                var chip:Sprite = makeKeyChip(getKeyName(int(codes[i])));
                chip.x = cx;
                _chipContainer.addChild(chip);
                cx += chip.width + 8;
            }
        }

        private function makeEditButton():Sprite
        {
            var s:Sprite = new Sprite();
            s.buttonMode    = true;
            s.useHandCursor = true;
            s.graphics.lineStyle(1, 0xF4A11A, 0.6);
            s.graphics.beginFill(0x1A1000, 0.9);
            s.graphics.drawRoundRect(0, 0, 110, 28, 4, 4);
            s.graphics.endFill();
            var tf:TextField = new TextField();
            tf.defaultTextFormat = new TextFormat("$FieldFont", 12, 0xF4A11A, true);
            tf.embedFonts  = true;
            tf.selectable  = false;
            tf.autoSize    = "left";
            tf.text        = "  змінити  ";
            tf.y = 5;
            s.addChild(tf);
            s.addEventListener(MouseEvent.CLICK, onEditClick);
            return s;
        }

        private function onEditClick(e:MouseEvent):void
        {
            if (_capturing || stage == null) return;
            _capturing    = true;
            _captureCodes = [];
            showHint();
            stage.addEventListener(KeyboardEvent.KEY_DOWN, onCaptureKeyDown);
            stage.addEventListener(KeyboardEvent.KEY_UP,   onCaptureKeyUp);
        }

        private function showHint():void
        {
            while (_chipContainer.numChildren > 0) _chipContainer.removeChildAt(0);
            var hint:TextField = new TextField();
            hint.defaultTextFormat = new TextFormat("$FieldFont", 13, 0xFFB84E, true);
            hint.embedFonts  = true;
            hint.selectable  = false;
            hint.autoSize    = "left";
            hint.text        = "Натисни потрібну комбінацію...";
            _chipContainer.addChild(hint);
        }

        private function onCaptureKeyDown(e:KeyboardEvent):void
        {
            if (!_capturing) return;
            var code:int = e.keyCode;
            if (_captureCodes.indexOf(code) == -1) _captureCodes.push(code);
            _captureCodes.sort(Array.NUMERIC);
            rebuildChipsFromCodes(_captureCodes);
        }

        private function onCaptureKeyUp(e:KeyboardEvent):void
        {
            if (!_capturing) return;
            finalizeCapture();
        }

        private function finalizeCapture():void
        {
            if (stage != null)
            {
                stage.removeEventListener(KeyboardEvent.KEY_DOWN, onCaptureKeyDown);
                stage.removeEventListener(KeyboardEvent.KEY_UP,   onCaptureKeyUp);
            }
            _capturing = false;
            if (_captureCodes.length == 0) { rebuildChipsFromString(_hotkeyStr); return; }
            _hotkeyKeys = _captureCodes.slice();
            _hotkeyStr  = buildHotkeyString(_hotkeyKeys);
            dispatchHotkeyChanged();
        }

        private function dispatchHotkeyChanged():void
        {
            rebuildChipsFromString(_hotkeyStr);
            var ev:WeatherEvent = new WeatherEvent(WeatherEvent.HOTKEY_CHANGED);
            ev.payload = _hotkeyKeys.slice();
            ev.mapId   = _hotkeyStr;
            dispatchEvent(ev);
        }

        private function buildHotkeyString(codes:Array):String
        {
            var parts:Array = [];
            for (var i:int = 0; i < codes.length; i++) parts.push(getKeyName(int(codes[i])));
            return parts.join("+");
        }

        private function getKeyName(code:int):String
        {
            switch (code)
            {
                case Keyboard.CONTROL:   return "CTRL";
                case Keyboard.ALTERNATE: return "ALT";
                case Keyboard.SHIFT:     return "SHIFT";
                case Keyboard.SPACE:     return "SPACE";
                case Keyboard.ENTER:     return "ENTER";
                case Keyboard.ESCAPE:    return "ESC";
                case Keyboard.TAB:       return "TAB";
                case Keyboard.BACKSPACE: return "BACKSPACE";
            }
            if (code >= Keyboard.F1 && code <= Keyboard.F15) return "F" + String(code - Keyboard.F1 + 1);
            if (code >= 48 && code <= 57) return String.fromCharCode(code);
            if (code >= 65 && code <= 90) return String.fromCharCode(code);
            return "KEY_" + code;
        }

        private function makeKeyChip(key:String):Sprite
        {
            var s:Sprite = new Sprite();
            var tf:TextField = new TextField();
            tf.defaultTextFormat = new TextFormat("$FieldFont", 13, 0xFFFFFF, true);
            tf.embedFonts  = true;
            tf.selectable  = false;
            tf.autoSize    = "left";
            tf.text = key;
            var w:int = tf.width + 18;
            var h:int = 26;
            s.graphics.beginFill(0x2D220D, 1);
            s.graphics.lineStyle(1, 0xF4A11A, 0.9);
            s.graphics.drawRoundRect(0, 0, w, h, 3, 3);
            s.graphics.endFill();
            tf.x = 9;
            tf.y = 4;
            s.addChild(tf);
            return s;
        }
    }
}
