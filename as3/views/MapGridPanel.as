package weather.views
{
    import flash.display.Sprite;

    import weather.components.MapTile;
    import weather.data.MapVO;

    /**
     * Сітка карт 4 в ряду. Висота контейнера зростає за потреби —
     * Scaleform сам додасть вертикальний скрол, якщо вміст вищий за вікно.
     */
    public class MapGridPanel extends Sprite
    {
        private static const COLS:int = 4;
        private static const GAP_X:int = 20;
        private static const GAP_Y:int = 18;
        private static const PAD_LEFT:int = 80;

        public function MapGridPanel(maps:Vector.<MapVO>)
        {
            build(maps);
        }

        private function build(maps:Vector.<MapVO>):void
        {
            for (var i:int = 0; i < maps.length; i++)
            {
                var tile:MapTile = new MapTile(maps[i]);
                var col:int = i % COLS;
                var row:int = i / COLS;
                tile.x = PAD_LEFT + col * (MapTile.TILE_W + GAP_X);
                tile.y = row * (MapTile.TILE_H + GAP_Y);
                addChild(tile);
            }
        }
    }
}
