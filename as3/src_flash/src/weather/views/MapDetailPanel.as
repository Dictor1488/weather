package weather.views
{
    import flash.display.Sprite;
    import flash.events.MouseEvent;
    import flash.text.TextField;
    import flash.text.TextFormat;

    import weather.components.PresetRow;
    import weather.data.MapVO;
    import weather.events.WeatherEvent;

    public class MapDetailPanel extends Sprite
    {
        private static const ROW_X:int = 120;
        private static const ROW_Y:int = 125;
        private static const ROW_GAP:int = 26;
        private static const ROW_W:int = 880;

        private var _map:MapVO;

        public function MapDetailPanel(map:MapVO, currentPreset:String = "standard")
        {
            _map = map;
            build();
        }

        private function build():void
        {
            var backBtn:Sprite = new Sprite();
            backBtn.buttonMode = true;
            backBtn.useHandCursor = true;
            backBtn.mouseChildren = false;

            var backTF:TextField = new TextField();
            backTF.defaultTextFormat = new TextFormat("_sans", 14, 0xCBA060, true);
            backTF.selectable = false;
            backTF.autoSize = "left";
            backTF.text = "‹  Назад до списку карт";
            backBtn.addChild(backTF);
            backBtn.x = 118;
            backBtn.y = 32;
            backBtn.addEventListener(MouseEvent.CLICK, onBackClick);
            addChild(backBtn);

            var header:TextField = new TextField();
            header.defaultTextFormat = new TextFormat("_sans", 23, 0xF2F2F2, true);
            header.selectable = false;
            header.autoSize = "left";
            header.text = "Налаштування карти: " + _map.label;
            header.x = 180;
            header.y = 68;
            addChild(header);

            var y:int = ROW_Y;
            for (var i:int = 0; i < _map.presets.length; i++)
            {
                var row:PresetRow = new PresetRow(_map.presets[i], _map.id);
                row.setWidth(ROW_W);
                row.x = ROW_X;
                row.y = y;
                row.addEventListener(WeatherEvent.PRESET_WEIGHT_CHANGED, onWeightChanged);
                addChild(row);
                y += PresetRow.ROW_HEIGHT + ROW_GAP;
            }
        }

        private function onWeightChanged(e:WeatherEvent):void
        {
            dispatchEvent(e.clone());
        }

        private function onBackClick(e:MouseEvent):void
        {
            dispatchEvent(new WeatherEvent(WeatherEvent.BACK_TO_MAPS));
        }
    }
}
