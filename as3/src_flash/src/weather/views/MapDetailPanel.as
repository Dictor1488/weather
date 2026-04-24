package weather.views
{
    import flash.display.Shape;
    import flash.display.Sprite;
    import flash.events.MouseEvent;
    import flash.text.TextField;
    import flash.text.TextFormat;

    import weather.components.PresetButton;
    import weather.data.MapVO;
    import weather.events.WeatherEvent;

    /**
     * Деталізована панель налаштувань карти.
     * Замість слайдерів — кнопки-пресети (один активний).
     */
    public class MapDetailPanel extends Sprite
    {
        private static const PAD_LEFT:int = 96;
        private static const BTN_GAP:int  = 16;

        private var _map:MapVO;
        private var _currentPresetId:String;
        private var _buttons:Vector.<PresetButton>;

        public function MapDetailPanel(map:MapVO, currentPreset:String = "standard")
        {
            _map = map;
            _buttons = new Vector.<PresetButton>();
            // Визначаємо поточний пресет карти: перший з вагою > 0, або "standard"
            _currentPresetId = currentPreset || _getActivePreset() || "standard";
            build();
        }

        private function _getActivePreset():String
        {
            var maxW:Number = -1;
            var maxId:String = "standard";
            for (var i:int = 0; i < _map.presets.length; i++)
            {
                if (_map.presets[i].weight > maxW)
                {
                    maxW  = _map.presets[i].weight;
                    maxId = _map.presets[i].id;
                }
            }
            return maxId;
        }

        private function build():void
        {
            // --- Кнопка «Назад» ---
            var backBtn:Sprite = new Sprite();
            backBtn.buttonMode    = true;
            backBtn.useHandCursor = true;
            backBtn.mouseChildren = false;
            var backTF:TextField = new TextField();
            backTF.defaultTextFormat = new TextFormat("$FieldFont", 14, 0xF4A11A, true);
            backTF.embedFonts  = true;
            backTF.selectable  = false;
            backTF.autoSize    = "left";
            backTF.text        = "\u2190  Назад до списку карт";
            backBtn.addChild(backTF);
            backBtn.x = PAD_LEFT + 6;
            backBtn.y = 8;
            backBtn.addEventListener(MouseEvent.CLICK, onBackClick);
            addChild(backBtn);

            // --- Назва карти ---
            var header:TextField = new TextField();
            header.defaultTextFormat = new TextFormat("$FieldFont", 22, 0xFFFFFF, true);
            header.embedFonts  = true;
            header.selectable  = false;
            header.autoSize    = "left";
            header.text        = _map.label;
            header.x = PAD_LEFT + 6;
            header.y = 40;
            addChild(header);

            // --- Підзаголовок ---
            var subHdr:TextField = new TextField();
            subHdr.defaultTextFormat = new TextFormat("$FieldFont", 13, 0x888888, false);
            subHdr.embedFonts  = true;
            subHdr.selectable  = false;
            subHdr.autoSize    = "left";
            subHdr.text        = "ПРЕСЕТ ПОГОДИ ДЛЯ ЦІЄЇ КАРТИ";
            subHdr.x = PAD_LEFT + 6;
            subHdr.y = 80;
            addChild(subHdr);

            // --- Роздільник ---
            var div:Shape = new Shape();
            div.graphics.lineStyle(1, 0x2A2A2A, 0.9);
            div.graphics.moveTo(PAD_LEFT, 0);
            div.graphics.lineTo(1184, 0);
            div.y = 74;
            addChild(div);

            // --- Кнопки пресетів ---
            var bx:int = PAD_LEFT + 6;
            var by:int = 106;
            for (var i:int = 0; i < _map.presets.length; i++)
            {
                var isActive:Boolean = (_map.presets[i].id == _currentPresetId);
                var btn:PresetButton = new PresetButton(_map.presets[i], _map.id, isActive);
                btn.x = bx;
                btn.y = by;
                btn.addEventListener(WeatherEvent.PRESET_SELECTED, onPresetSelected);
                addChild(btn);
                _buttons.push(btn);
                bx += PresetButton.BTN_W + BTN_GAP;
                if ((i + 1) % 5 == 0) { bx = PAD_LEFT + 6; by += PresetButton.BTN_H + BTN_GAP; }
            }

            // --- Підказка внизу ---
            var tip:TextField = new TextField();
            tip.defaultTextFormat = new TextFormat("$FieldFont", 12, 0x555555, false);
            tip.embedFonts  = true;
            tip.selectable  = false;
            tip.autoSize    = "left";
            tip.text        = "Якщо пресет не підтримується для цієї карти — буде використана глобальна погода";
            tip.x           = PAD_LEFT + 6;
            tip.y           = by + PresetButton.BTN_H + 20;
            addChild(tip);
        }

        private function onPresetSelected(e:WeatherEvent):void
        {
            var newId:String = e.presetId;
            if (newId == _currentPresetId) return;
            _currentPresetId = newId;

            for (var i:int = 0; i < _buttons.length; i++)
                _buttons[i].setSelected(_buttons[i].presetId == _currentPresetId);

            // Диспатчимо з mapId — Python збереже для конкретної карти
            var ev:WeatherEvent = new WeatherEvent(WeatherEvent.PRESET_SELECTED, true);
            ev.mapId    = _map.id;
            ev.presetId = _currentPresetId;
            dispatchEvent(ev);
        }

        private function onBackClick(e:MouseEvent):void
        {
            dispatchEvent(new WeatherEvent(WeatherEvent.BACK_TO_MAPS));
        }
    }
}
