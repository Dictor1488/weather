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
        private static const COLS:int = 4;
        private static const GAP_X:int = 42;
        private static const GAP_Y:int = 34;
        private static const PAD_LEFT:int = 68;
        private static const PAD_TOP:int = 60;
        private static const VIEW_H:int = 590;

        private var _holder:Sprite;
        private var _maskShape:Shape;
        private var _scrollbar:Sprite;
        private var _thumb:Sprite;
        private var _contentHeight:int = 0;

        public function MapGridPanel(maps:Vector.<MapVO>)
        {
            build(maps);
            addEventListener(MouseEvent.MOUSE_WHEEL, onWheel);
        }

        private function build(maps:Vector.<MapVO>):void
        {
            _holder = new Sprite();
            addChild(_holder);

            _maskShape = new Shape();
            _maskShape.graphics.beginFill(0xFFFFFF, 1);
            _maskShape.graphics.drawRect(0, 0, 1140, VIEW_H);
            _maskShape.graphics.endFill();
            _maskShape.x = 0;
            _maskShape.y = 0;
            addChild(_maskShape);
            _holder.mask = _maskShape;

            for (var i:int = 0; i < maps.length; i++)
            {
                var tile:MapTile = new MapTile(maps[i]);
                tile.addEventListener(WeatherEvent.MAP_SELECTED, onMapSelected);

                var col:int = i % COLS;
                var row:int = int(i / COLS);
                tile.x = PAD_LEFT + col * (MapTile.TILE_W + GAP_X);
                tile.y = PAD_TOP + row * (MapTile.TILE_H + GAP_Y);
                _holder.addChild(tile);
            }

            _contentHeight = PAD_TOP + Math.ceil(maps.length / COLS) * (MapTile.TILE_H + GAP_Y);
            buildScrollbar();
        }

        private function buildScrollbar():void
        {
            _scrollbar = new Sprite();
            _scrollbar.x = 1168;
            _scrollbar.y = 14;
            addChild(_scrollbar);

            _scrollbar.graphics.lineStyle(1, 0x5A554B, 0.85);
            _scrollbar.graphics.beginFill(0x141414, 0.55);
            _scrollbar.graphics.drawRect(0, 0, 14, VIEW_H - 8);
            _scrollbar.graphics.endFill();

            _thumb = new Sprite();
            _thumb.graphics.beginFill(0x5D584E, 0.9);
            _thumb.graphics.drawRect(2, 2, 10, 88);
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
            _holder.y += e.delta * 26;

            var minY:int = VIEW_H - _contentHeight;
            if (_holder.y > 0) _holder.y = 0;
            if (_holder.y < minY) _holder.y = minY;

            updateThumb();
        }

        private function updateThumb():void
        {
            if (!_thumb || _contentHeight <= VIEW_H) return;

            var maxScroll:int = _contentHeight - VIEW_H;
            var ratio:Number = -_holder.y / maxScroll;
            var trackH:int = VIEW_H - 100;
            _thumb.y = 2 + ratio * trackH;
        }
    }
}
