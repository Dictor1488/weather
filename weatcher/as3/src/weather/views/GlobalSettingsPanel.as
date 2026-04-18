package weather.views
{
    import flash.display.Sprite;
    import flash.events.Event;
    import flash.text.TextField;
    import flash.text.TextFormat;

    import weather.components.PresetRow;
    import weather.data.PresetVO;
    import weather.events.WeatherEvent;

    /**
     * Панель вкладки "Загальні налаштування".
     * 
     * Показує 5 пресетів зі слайдерами + внизу хоткей "Смена погоды в бою: [ALT] [F12]"
     * mapId = null у всіх рядках (сигнал "це глобальні ваги").
     */
    public class GlobalSettingsPanel extends Sprite
    {
        private static const CONTENT_X:int = 90;
        private static const CONTENT_Y:int = 50;
        private static const ROW_GAP:int = 12;

        public function GlobalSettingsPanel(presets:Vector.<PresetVO>, hotkey:String)
        {
            build(presets, hotkey);
        }

        private function build(presets:Vector.<PresetVO>, hotkey:String):void
        {
            // Заголовок секції
            var header:TextField = new TextField();
            header.defaultTextFormat = new TextFormat("$FieldFont", 18, 0xFFFFFF, true);
            header.embedFonts = true;
            header.selectable = false;
            header.autoSize = "left";
            header.text = "Загальні налаштування для всіх карт";
            header.x = CONTENT_X + 20;
            header.y = 10;
            addChild(header);

            // Ряди пресетів
            var y:int = CONTENT_Y;
            for (var i:int = 0; i < presets.length; i++)
            {
                var row:PresetRow = new PresetRow(presets[i], null);
                row.x = CONTENT_X;
                row.y = y;
                // подія з рядка спливає — її зловить Mediator на рівні WeatherView
                addChild(row);
                y += PresetRow.ROW_HEIGHT + ROW_GAP;
            }

            // Секція хоткея внизу
            var hkLabel:TextField = new TextField();
            hkLabel.defaultTextFormat = new TextFormat("$FieldFont", 14, 0xC8C8C8);
            hkLabel.embedFonts = true;
            hkLabel.selectable = false;
            hkLabel.autoSize = "left";
            hkLabel.text = "Смена погоды в бою";
            hkLabel.x = CONTENT_X + 20;
            hkLabel.y = y + 20;
            addChild(hkLabel);

            // Парсимо хоткей на окремі клавіші та малюємо їх як чипси
            var keys:Array = hotkey.split("+");
            var chipX:int = CONTENT_X + 400;
            for (var k:int = 0; k < keys.length; k++)
            {
                var chip:Sprite = makeKeyChip(String(keys[k]).toUpperCase());
                chip.x = chipX;
                chip.y = y + 16;
                addChild(chip);
                chipX += chip.width + 8;
            }
        }

        private function makeKeyChip(key:String):Sprite
        {
            var s:Sprite = new Sprite();
            var tf:TextField = new TextField();
            tf.defaultTextFormat = new TextFormat("$FieldFont", 13, 0xFFFFFF, true);
            tf.embedFonts = true;
            tf.selectable = false;
            tf.autoSize = "left";
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
