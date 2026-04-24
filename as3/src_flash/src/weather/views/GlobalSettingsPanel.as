package weather.views
{
    import flash.display.Sprite;
    import flash.events.KeyboardEvent;
    import flash.events.MouseEvent;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.ui.Keyboard;

    import weather.components.PresetRow;
    import weather.data.PresetVO;
    import weather.events.WeatherEvent;

    public class GlobalSettingsPanel extends Sprite
    {
        private var _hotkeyKeys:Array;
        private var _hotkeyStr:String;
        private var _capturing:Boolean = false;
        private var _captureCodes:Array;
        private var _chipContainer:Sprite;

        public function GlobalSettingsPanel(presets:Vector.<PresetVO>,
                                            hotkey:String,
                                            hotkeyKeys:Array,
                                            currentPreset:String = "standard")
        {
            _hotkeyStr = hotkey;
            _hotkeyKeys = hotkeyKeys ? hotkeyKeys.slice() : [];
            _captureCodes = [];
            build(presets);
        }

        private function build(presets:Vector.<PresetVO>):void
        {
            var hdr:TextField = makeText("Загальні налаштування", 18, 0xF2F2F2, true);
            hdr.x = 2;
            hdr.y = 0;
            addChild(hdr);

            var y:int = 36;
            for (var i:int = 0; i < presets.length; i++)
            {
                var row:PresetRow = new PresetRow(presets[i], null);
                row.x = 0;
                row.y = y;
                row.addEventListener(WeatherEvent.PRESET_WEIGHT_CHANGED, onWeightChanged);
                addChild(row);
                y += PresetRow.ROW_HEIGHT + 10;
            }

            var hk:TextField = makeText("Гаряча клавіша в бою", 14, 0xDADADA, false);
            hk.x = 2;
            hk.y = y + 10;
            addChild(hk);

            _chipContainer = new Sprite();
            _chipContainer.x = 232;
            _chipContainer.y = y + 5;
            addChild(_chipContainer);
            rebuildChipsFromString(_hotkeyStr);

            var editBtn:Sprite = makeEditButton();
            editBtn.x = 342;
            editBtn.y = y + 2;
            addChild(editBtn);
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

        private function onWeightChanged(e:WeatherEvent):void
        {
            dispatchEvent(e.clone());
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
                cx += chip.width + 5;
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
                cx += chip.width + 5;
            }
        }

        private function makeEditButton():Sprite
        {
            var s:Sprite = new Sprite();
            s.buttonMode = true;
            s.useHandCursor = true;
            s.graphics.lineStyle(1, 0xAF741E, 0.9);
            s.graphics.beginFill(0x0E0B08, 0.85);
            s.graphics.drawRect(0, 0, 84, 26);
            s.graphics.endFill();

            var tf:TextField = makeText("змінити", 12, 0xE6A13A, true);
            tf.x = 17;
            tf.y = 5;
            s.addChild(tf);

            s.addEventListener(MouseEvent.CLICK, onEditClick);
            return s;
        }

        private function onEditClick(e:MouseEvent):void
        {
            if (_capturing || stage == null) return;
            _capturing = true;
            _captureCodes = [];
            showHint();
            stage.addEventListener(KeyboardEvent.KEY_DOWN, onCaptureKeyDown);
            stage.addEventListener(KeyboardEvent.KEY_UP, onCaptureKeyUp);
        }

        private function showHint():void
        {
            while (_chipContainer.numChildren > 0) _chipContainer.removeChildAt(0);
            _chipContainer.addChild(makeText("натисни...", 12, 0xFFB84E, true));
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
                stage.removeEventListener(KeyboardEvent.KEY_UP, onCaptureKeyUp);
            }
            _capturing = false;
            if (_captureCodes.length == 0) { rebuildChipsFromString(_hotkeyStr); return; }

            _hotkeyKeys = _captureCodes.slice();
            _hotkeyStr = buildHotkeyString(_hotkeyKeys);
            rebuildChipsFromString(_hotkeyStr);

            var ev:WeatherEvent = new WeatherEvent(WeatherEvent.HOTKEY_CHANGED);
            ev.payload = _hotkeyKeys.slice();
            ev.mapId = _hotkeyStr;
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
            var tf:TextField = makeText(key, 12, 0xFFFFFF, true);

            var w:int = tf.width + 14;
            s.graphics.beginFill(0x261D0E, 0.90);
            s.graphics.lineStyle(1, 0xB98525, 1);
            s.graphics.drawRect(0, 0, w, 24);
            s.graphics.endFill();

            tf.x = 7;
            tf.y = 4;
            s.addChild(tf);
            return s;
        }
    }
}
