package weather.views
{
    import flash.display.Shape;
    import flash.display.Sprite;
    import flash.events.MouseEvent;
    import flash.geom.Rectangle;

    import weather.components.MapTile;
    import weather.data.MapVO;
    import weather.events.WeatherEvent;

    public class MapGridPanel extends Sprite
    {
        private static const VIEW_W:int = 890;
        private static const VIEW_H:int = 570;
        private static const GAP:int = 6;
        private static const COLS:int = 4;

        private var _holder:Sprite;
        private var _scrollbar:Sprite;
        private var _thumb:Sprite;
        private var _contentHeight:int = 0;
        private var _scrollY:int = 0;

        public function MapGridPanel(maps:Vector.<MapVO>)
        {
            build(maps);
            addEventListener(MouseEvent.MOUSE_WHEEL, onWheel);
        }

        private function build(maps:Vector.<MapVO>):void
        {
            _holder = new Sprite();
            _holder.y = 0;
            // scrollRect замість mask — маска блокує mouse events у Scaleform WoT
            _holder.scrollRect = new flash.geom.Rectangle(0, 0, VIEW_W, VIEW_H);
            addChild(_holder);

            for (var i:int = 0; i < maps.length; i++)
            {
                var tile:MapTile = new MapTile(maps[i]);
                tile.x = (i % COLS) * (MapTile.TILE_W + GAP);
                tile.y = int(i / COLS) * (MapTile.TILE_H + GAP);
                tile.addEventListener(WeatherEvent.MAP_SELECTED, onMapSelected);
                _holder.addChild(tile);
            }

            _contentHeight = int((maps.length + COLS - 1) / COLS) * (MapTile.TILE_H + GAP);
            buildScrollbar();
        }

        private function buildScrollbar():void
        {
            _scrollbar = new Sprite();
            _scrollbar.x = VIEW_W + 6;
            _scrollbar.y = 0;
            addChild(_scrollbar);
            _scrollbar.graphics.lineStyle(1, 0x484440, 0.85);
            _scrollbar.graphics.beginFill(0x080808, 0.70);
            _scrollbar.graphics.drawRect(0, 0, 9, VIEW_H);
            _scrollbar.graphics.endFill();

            _thumb = new Sprite();
            _thumb.graphics.beginFill(0x686460, 0.95);
            _thumb.graphics.drawRect(2, 2, 5, 74);
            _thumb.graphics.endFill();
            _scrollbar.addChild(_thumb);
            _scrollbar.visible = (_contentHeight > VIEW_H);
            updateThumb();
        }

        private function onMapSelected(e:WeatherEvent):void
        {
            dispatchEvent(e.clone());
        }

        private function onWheel(e:MouseEvent):void
        {
            if (_contentHeight <= VIEW_H) return;
            _scrollY -= e.delta * 34;
            clampScroll();
            updateThumb();
        }

        private function clampScroll():void
        {
            var maxY:int = _contentHeight - VIEW_H;
            if (_scrollY < 0) _scrollY = 0;
            if (_scrollY > maxY) _scrollY = maxY;
            _holder.scrollRect = new Rectangle(0, _scrollY, VIEW_W, VIEW_H);
        }

        private function updateThumb():void
        {
            if (!_thumb || _contentHeight <= VIEW_H) return;
            var maxScroll:int = _contentHeight - VIEW_H;
            var ratio:Number = _scrollY / maxScroll;
            var trackH:int = VIEW_H - 78;
            _thumb.y = 2 + ratio * trackH;
        }
    }
}
