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
        private static const CONTENT_X:int = 96;
        private static const CONTENT_Y:int = 54;
        private static const ROW_GAP:int   = 14;

        private var _hotkeyKeys:Array;
        private var _hotkeyStr:String;
        private var _capturing:Boolean = false;
        private var _chipContainer:Sprite;
        private var _captureCodes:Array;

        public function GlobalSettingsPanel(presets:Vector.<PresetVO>,
                                            hotkey:String,
                                            hotkeyKeys:Array)
        {
            _hotkeyStr  = hotkey;
            _hotkeyKeys = hotkeyKeys ? hotkeyKeys.slice() : [];
            _captureCodes = [];
            build(presets);
        }

        private function build(presets:Vector.<PresetVO>):void
        {
            var header:TextField = new TextField();
            header.defaultTextFormat = new TextFormat("$FieldFont", 20, 0xFFFFFF, true);
            header.embedFonts  = true;
            header.selectable  = false;
            header.autoSize    = "left";
            header.text        = "Загальні налаштування для всіх карт";
            header.x           = CONTENT_X + 18;
            header.y           = 8;
            addChild(header);

            var y:int = CONTENT_Y;
            for (var i:int = 0; i < presets.length; i++)
            {
                var row:PresetRow = new PresetRow(presets[i], null);
                row.x = CONTENT_X;
                row.y = y;
                addChild(row);
                y += PresetRow.ROW_HEIGHT + ROW_GAP;
            }

            var hkLabel:TextField = new TextField();
            hkLabel.defaultTextFormat = new TextFormat("$FieldFont", 15, 0xCCCCCC);
            hkLabel.embedFonts  = true;
            hkLabel.selectable  = false;
            hkLabel.autoSize    = "left";
            hkLabel.text        = "Зміна погоди в бою";
            hkLabel.x           = CONTENT_X + 10;
            hkLabel.y           = y + 18;
            addChild(hkLabel);

            _chipContainer = new Sprite();
            _chipContainer.x = CONTENT_X + 520;
            _chipContainer.y = y + 12;
            addChild(_chipContainer);
            rebuildChipsFromString(_hotkeyStr);

            var editBtn:Sprite = makeEditButton();
            editBtn.x = CONTENT_X + 680;
            editBtn.y = y + 12;
            addChild(editBtn);
        }

        private function rebuildChipsFromString(value:String):void
        {
            while (_chipContainer.numChildren > 0)
                _chipContainer.removeChildAt(0);

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
            while (_chipContainer.numChildren > 0)
                _chipContainer.removeChildAt(0);

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

            var tf:TextField = new TextField();
            tf.defaultTextFormat = new TextFormat("$FieldFont", 13, 0xF4A11A, true);
            tf.embedFonts  = true;
            tf.selectable  = false;
            tf.autoSize    = "left";
            tf.text        = "[ змінити ]";
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
            while (_chipContainer.numChildren > 0)
                _chipContainer.removeChildAt(0);

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
            if (_captureCodes.indexOf(code) == -1)
                _captureCodes.push(code);
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

            if (_captureCodes.length == 0)
            {
                rebuildChipsFromString(_hotkeyStr);
                return;
            }

            _hotkeyKeys = _captureCodes.slice();
            _hotkeyStr = buildHotkeyString(_hotkeyKeys);
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
            for (var i:int = 0; i < codes.length; i++)
                parts.push(getKeyName(int(codes[i])));
            return parts.join("+");
        }

        private function getKeyName(code:int):String
        {
            switch (code)
            {
                case Keyboard.CONTROL: return "CTRL";
                case Keyboard.ALTERNATE: return "ALT";
                case Keyboard.SHIFT: return "SHIFT";
                case Keyboard.SPACE: return "SPACE";
                case Keyboard.ENTER: return "ENTER";
                case Keyboard.ESCAPE: return "ESC";
                case Keyboard.TAB: return "TAB";
                case Keyboard.BACKSPACE: return "BACKSPACE";
            }

            if (code >= Keyboard.F1 && code <= Keyboard.F15)
                return "F" + String(code - Keyboard.F1 + 1);
            if (code >= 48 && code <= 57)
                return String.fromCharCode(code);
            if (code >= 65 && code <= 90)
                return String.fromCharCode(code);
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
            var h:int = 24;
            s.graphics.beginFill(0x2D220D, 1);
            s.graphics.lineStyle(1, 0xF4A11A, 1);
            s.graphics.drawRect(0, 0, w, h);
            s.graphics.endFill();
            tf.x = 9;
            tf.y = 3;
            s.addChild(tf);
            return s;
        }
    }
}
