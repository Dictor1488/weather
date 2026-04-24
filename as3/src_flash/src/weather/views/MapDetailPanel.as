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
        private var _map:MapVO;

        public function MapDetailPanel(map:MapVO, currentPreset:String = "standard")
        {
            _map = map;
            build();
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

        private function build():void
        {
            var backBtn:Sprite = new Sprite();
            backBtn.buttonMode = true;
            backBtn.useHandCursor = true;
            backBtn.mouseChildren = false;

            var backTF:TextField = makeText("‹ назад до карт", 13, 0xD5A45A, true);
            backBtn.addChild(backTF);
            backBtn.x = 0;
            backBtn.y = 0;
            backBtn.addEventListener(MouseEvent.CLICK, onBackClick);
            addChild(backBtn);

            var header:TextField = makeText("Налаштування карти: " + _map.label, 18, 0xF2F2F2, true);
            header.x = 0;
            header.y = 28;
            addChild(header);

            var y:int = 68;
            for (var i:int = 0; i < _map.presets.length; i++)
            {
                var row:PresetRow = new PresetRow(_map.presets[i], _map.id);
                row.x = 0;
                row.y = y;
                row.addEventListener(WeatherEvent.PRESET_WEIGHT_CHANGED, onWeightChanged);
                addChild(row);
                y += PresetRow.ROW_HEIGHT + 10;
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
