package weather.views
{
    import flash.display.Sprite;

    import weather.components.MapTile;
    import weather.data.MapVO;

    public class MapGridPanel extends Sprite
    {
        private static const COLS:int = 4;
        private static const GAP_X:int = 22;
        private static const GAP_Y:int = 20;
        private static const PAD_LEFT:int = 72;
        private static const PAD_TOP:int = 10;

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
                var row:int = int(i / COLS);
                tile.x = PAD_LEFT + col * (MapTile.TILE_W + GAP_X);
                tile.y = PAD_TOP + row * (MapTile.TILE_H + GAP_Y);
                addChild(tile);
            }
        }
    }
}
