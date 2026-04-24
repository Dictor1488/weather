package weather.views
{
    import flash.display.Shape;
    import flash.display.Sprite;
    import flash.events.MouseEvent;

    import weather.components.MapTile;
    import weather.data.MapVO;
    import weather.events.WeatherEvent;

    public class MapGridPanel extends Sprite
    {
        private static const VIEW_H:int = 420;

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
            var hdr:flash.text.TextField = new flash.text.TextField();
            hdr.defaultTextFormat = new flash.text.TextFormat("_sans", 16, 0xF2F2F2, true);
            hdr.selectable = false;
            hdr.autoSize = "left";
            hdr.text = "Налаштування по картах";
            hdr.x = 0;
            hdr.y = 0;
            addChild(hdr);

            _holder = new Sprite();
            _holder.y = 30;
            addChild(_holder);

            _maskShape = new Shape();
            _maskShape.graphics.beginFill(0xFFFFFF, 1);
            _maskShape.graphics.drawRect(0, 30, 394, VIEW_H);
            _maskShape.graphics.endFill();
            addChild(_maskShape);
            _holder.mask = _maskShape;

            for (var i:int = 0; i < maps.length; i++)
            {
                var tile:MapTile = new MapTile(maps[i]);
                tile.y = i * (MapTile.TILE_H + 7);
                tile.addEventListener(WeatherEvent.MAP_SELECTED, onMapSelected);
                _holder.addChild(tile);
            }

            _contentHeight = maps.length * (MapTile.TILE_H + 7);
            buildScrollbar();
        }

        private function buildScrollbar():void
        {
            _scrollbar = new Sprite();
            _scrollbar.x = 400;
            _scrollbar.y = 30;
            addChild(_scrollbar);

            _scrollbar.graphics.lineStyle(1, 0x5A554B, 0.85);
            _scrollbar.graphics.beginFill(0x141414, 0.55);
            _scrollbar.graphics.drawRect(0, 0, 10, VIEW_H);
            _scrollbar.graphics.endFill();

            _thumb = new Sprite();
            _thumb.graphics.beginFill(0x7A7364, 0.9);
            _thumb.graphics.drawRect(2, 2, 6, 70);
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

            _holder.y += e.delta * 22;
            var maxY:int = 30;
            var minY:int = 30 + VIEW_H - _contentHeight;
            if (_holder.y > maxY) _holder.y = maxY;
            if (_holder.y < minY) _holder.y = minY;

            updateThumb();
        }

        private function updateThumb():void
        {
            if (!_thumb || _contentHeight <= VIEW_H) return;

            var maxScroll:int = _contentHeight - VIEW_H;
            var ratio:Number = (30 - _holder.y) / maxScroll;
            var trackH:int = VIEW_H - 76;
            _thumb.y = 2 + ratio * trackH;
        }
    }
}
