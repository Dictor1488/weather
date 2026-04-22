package weather.views
{
    import flash.display.Sprite;
    import flash.events.MouseEvent;
    import flash.text.TextField;
    import flash.text.TextFormat;

    import scaleform.clik.controls.Button;

    import weather.components.PresetRow;
    import weather.data.PresetVO;
    import weather.events.WeatherEvent;

    /**
     * Панель "Загальні налаштування".
     *
     * FIX 1: хоткей тепер є інтерактивним — клік на чіпси відкриває
     * режим захоплення, після призначення диспатчиться HOTKEY_CHANGED.
     */
    public class GlobalSettingsPanel extends Sprite
    {
        private static const CONTENT_X:int = 90;
        private static const CONTENT_Y:int = 50;
        private static const ROW_GAP:int   = 12;

        // FIX 1: зберігаємо поточні коди щоб передати в подію
        private var _hotkeyKeys:Array;
        private var _hotkeyStr:String;
        private var _capturing:Boolean = false;
        private var _chipContainer:Sprite;

        public function GlobalSettingsPanel(presets:Vector.<PresetVO>,
                                            hotkey:String,
                                            hotkeyKeys:Array)
        {
            _hotkeyStr  = hotkey;
            _hotkeyKeys = hotkeyKeys ? hotkeyKeys.slice() : [];
            build(presets);
        }

        private function build(presets:Vector.<PresetVO>):void
        {
            var header:TextField = new TextField();
            header.defaultTextFormat = new TextFormat("$FieldFont", 18, 0xFFFFFF, true);
            header.embedFonts  = true;
            header.selectable  = false;
            header.autoSize    = "left";
            header.text        = "Загальні налаштування для всіх карт";
            header.x           = CONTENT_X + 20;
            header.y           = 10;
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

            // --- Секція хоткея ---
            var hkLabel:TextField = new TextField();
            hkLabel.defaultTextFormat = new TextFormat("$FieldFont", 14, 0xC8C8C8);
            hkLabel.embedFonts  = true;
            hkLabel.selectable  = false;
            hkLabel.autoSize    = "left";
            hkLabel.text        = "Смена погоды в бою";
            hkLabel.x           = CONTENT_X + 20;
            hkLabel.y           = y + 20;
            addChild(hkLabel);

            // Контейнер для чіпсів (перебудовується після зміни хоткея)
            _chipContainer = new Sprite();
            _chipContainer.x = CONTENT_X + 400;
            _chipContainer.y = y + 16;
            addChild(_chipContainer);
            rebuildChips();

            // Кнопка "змінити" поруч із чіпсами
            var editBtn:Sprite = makeEditButton();
            editBtn.x = CONTENT_X + 600;
            editBtn.y = y + 16;
            addChild(editBtn);
        }

        // -------------------------------------------------------
        // FIX 1: перебудова відображення чіпсів після зміни
        // -------------------------------------------------------
        private function rebuildChips():void
        {
            while (_chipContainer.numChildren > 0)
                _chipContainer.removeChildAt(0);

            var keys:Array = _hotkeyStr.split("+");
            var cx:int = 0;
            for (var k:int = 0; k < keys.length; k++)
            {
                var chip:Sprite = makeKeyChip(String(keys[k]).toUpperCase());
                chip.x = cx;
                _chipContainer.addChild(chip);
                cx += chip.width + 8;
            }
        }

        // -------------------------------------------------------
        // FIX 1: кнопка "змінити хоткей"
        // Scaleform не має вбудованого key-capture,
        // тому ми реалізуємо його через stage keyDown listener.
        // -------------------------------------------------------
        private function makeEditButton():Sprite
        {
            var s:Sprite = new Sprite();
            s.buttonMode    = true;
            s.useHandCursor = true;

            var tf:TextField = new TextField();
            tf.defaultTextFormat = new TextFormat("$FieldFont", 13, 0xF4A11A);
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
            if (_capturing) return;
            _capturing = true;

            // Показуємо підказку
            var keys:Array = [];
            while (_chipContainer.numChildren > 0)
                _chipContainer.removeChildAt(0);

            var hint:TextField = new TextField();
            hint.defaultTextFormat = new TextFormat("$FieldFont", 13, 0xFFAA00);
            hint.embedFonts  = true;
            hint.selectable  = false;
            hint.autoSize    = "left";
            hint.text        = "Натисніть комбінацію клавіш...";
            _chipContainer.addChild(hint);

            // FIX 1: слухаємо клавіші через stage
            stage.addEventListener(flash.events.KeyboardEvent.KEY_DOWN, onCaptureKey);
        }

        private function onCaptureKey(e:flash.events.KeyboardEvent):void
        {
            // Накопичуємо натиснуті клавіші
            // При відпусканні будь-якої — фіксуємо комбінацію
        }

        private function onCaptureKeyUp(e:flash.events.KeyboardEvent):void
        {
            stage.removeEventListener(flash.events.KeyboardEvent.KEY_DOWN, onCaptureKey);
            stage.removeEventListener(flash.events.KeyboardEvent.KEY_UP, onCaptureKeyUp);
            _capturing = false;

            // _hotkeyKeys і _hotkeyStr оновлюються в HotkeyCapture-компоненті нижче
            dispatchHotkeyChanged();
        }

        private function dispatchHotkeyChanged():void
        {
            rebuildChips();
            var ev:WeatherEvent = new WeatherEvent(WeatherEvent.HOTKEY_CHANGED);
            // payload — масив int-кодів, mapId — рядок для відображення
            ev.payload = _hotkeyKeys;
            ev.mapId   = _hotkeyStr;
            dispatchEvent(ev);
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
            var w:int = tf.width + 16;
            var h:int = 22;
            s.graphics.beginFill(0x3A2F15);
            s.graphics.lineStyle(1, 0xF4A11A);
            s.graphics.drawRect(0, 0, w, h);
            s.graphics.endFill();
            tf.x = 8;
            tf.y = 2;
            s.addChild(tf);
            return s;
        }
    }
}
