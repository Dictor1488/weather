package weather.views
{
    import flash.display.Sprite;
    import flash.text.TextField;
    import flash.text.TextFormat;

    import weather.components.PresetRow;
    import weather.data.MapVO;

    /**
     * Екран "Настройка карты: <Ім'я>" — такий самий набір з 5 слайдерів,
     * але з mapId, прив'язаним до конкретної карти.
     */
    public class MapDetailPanel extends Sprite
    {
        private static const CONTENT_X:int = 90;
        private static const ROW_GAP:int = 12;

        public function MapDetailPanel(map:MapVO)
        {
            build(map);
        }

        private function build(map:MapVO):void
        {
            var header:TextField = new TextField();
            header.defaultTextFormat = new TextFormat("$FieldFont", 18, 0xFFFFFF, true);
            header.embedFonts = true;
            header.selectable = false;
            header.autoSize = "left";
            header.text = "Настройка карты: " + map.label;
            header.x = CONTENT_X + 20;
            header.y = 10;
            addChild(header);

            var y:int = 60;
            for (var i:int = 0; i < map.presets.length; i++)
            {
                var row:PresetRow = new PresetRow(map.presets[i], map.id);
                row.x = CONTENT_X;
                row.y = y;
                addChild(row);
                y += PresetRow.ROW_HEIGHT + ROW_GAP;
            }
        }
    }
}
