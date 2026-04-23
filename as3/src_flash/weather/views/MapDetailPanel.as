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
        private static const CONTENT_X:int = 96;
        private static const ROW_GAP:int = 14;

        public function MapDetailPanel(map:MapVO)
        {
            build(map);
        }

        private function build(map:MapVO):void
        {
            var backBtn:Sprite = new Sprite();
            backBtn.buttonMode = true;
            backBtn.useHandCursor = true;
            backBtn.mouseChildren = false;
            var backTF:TextField = new TextField();
            backTF.defaultTextFormat = new TextFormat("$FieldFont", 14, 0xF4A11A, true);
            backTF.embedFonts = true;
            backTF.selectable = false;
            backTF.autoSize = "left";
            backTF.text = "\u2190 Назад до списку карт";
            backBtn.addChild(backTF);
            backBtn.x = CONTENT_X + 6;
            backBtn.y = 8;
            backBtn.addEventListener(MouseEvent.CLICK, onBackClick);
            addChild(backBtn);

            var header:TextField = new TextField();
            header.defaultTextFormat = new TextFormat("$FieldFont", 20, 0xFFFFFF, true);
            header.embedFonts = true;
            header.selectable = false;
            header.autoSize = "left";
            header.text = "Налаштування карти: " + map.label;
            header.x = CONTENT_X + 18;
            header.y = 44;
            addChild(header);

            var y:int = 96;
            for (var i:int = 0; i < map.presets.length; i++)
            {
                var row:PresetRow = new PresetRow(map.presets[i], map.id);
                row.x = CONTENT_X;
                row.y = y;
                addChild(row);
                y += PresetRow.ROW_HEIGHT + ROW_GAP;
            }
        }

        private function onBackClick(e:MouseEvent):void
        {
            dispatchEvent(new WeatherEvent(WeatherEvent.BACK_TO_MAPS));
        }
    }
}
