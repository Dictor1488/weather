package weather.components
{
    import flash.display.Loader;
    import flash.display.Shape;
    import flash.display.Sprite;
    import flash.events.Event;
    import flash.events.IOErrorEvent;
    import flash.events.MouseEvent;
    import flash.geom.Rectangle;
    import flash.net.URLRequest;
    import flash.text.TextField;
    import flash.text.TextFormat;

    import weather.data.MapVO;
    import weather.events.WeatherEvent;

    public class MapTile extends Sprite
    {
        public static const TILE_W:int = 218;
        public static const TILE_H:int = 108;

        private var _vo:MapVO;
        private var _hover:Sprite;
        private var _thumb:Loader;
        private var _thumbHolder:Sprite;

        public function MapTile(vo:MapVO)
        {
            _vo = vo;
            buttonMode = true;
            useHandCursor = true;
            mouseChildren = false;
            buildUI();

            addEventListener(MouseEvent.ROLL_OVER, onOver);
            addEventListener(MouseEvent.ROLL_OUT, onOut);
            addEventListener(MouseEvent.CLICK, onClick);
        }

        private function buildUI():void
        {
            graphics.lineStyle(1, 0x28303A, 0.95);
            graphics.beginFill(0x14181E, 0.88);
            graphics.drawRect(0, 0, TILE_W, TILE_H);
            graphics.endFill();

            _thumbHolder = new Sprite();
            _thumbHolder.x = 0;
            _thumbHolder.y = 0;
            addChild(_thumbHolder);

            drawFallbackBackground();
            loadThumb();

            var shade:Shape = new Shape();
            shade.graphics.beginFill(0x000000, 0.34);
            shade.graphics.drawRect(0, 0, TILE_W, TILE_H);
            shade.graphics.endFill();
            addChild(shade);

            _hover = new Sprite();
            _hover.graphics.beginFill(0xAA6E14, 0.14);
            _hover.graphics.drawRect(0, 0, TILE_W, TILE_H);
            _hover.graphics.endFill();
            _hover.visible = false;
            addChild(_hover);

            var title:TextField = new TextField();
            title.defaultTextFormat = new TextFormat("_sans", 13, 0xF0F0F0, true);
            title.selectable = false;
            title.width = TILE_W - 18;
            title.height = 26;
            title.text = _vo.label;
            title.x = 9;
            title.y = 8;
            addChild(title);

            var icon:Sprite = makeSlidersIcon();
            icon.x = int((TILE_W - icon.width) * 0.5);
            icon.y = 66;
            addChild(icon);
        }

        private function drawFallbackBackground():void
        {
            var seed:int = Math.abs(hash(_vo.id));
            var colors:Array = [0x1E2F3C, 0x2B3524, 0x3E3023, 0x252A30, 0x273541];
            var c:uint = colors[seed % colors.length];
            _thumbHolder.graphics.beginFill(c, 0.82);
            _thumbHolder.graphics.drawRect(0, 0, TILE_W, TILE_H);
            _thumbHolder.graphics.endFill();
            _thumbHolder.graphics.beginFill(0xFFFFFF, 0.04);
            _thumbHolder.graphics.drawRect(0, 0, TILE_W, 38);
            _thumbHolder.graphics.endFill();
        }

        private function hash(s:String):int
        {
            var h:int = 0;
            if (!s) return 0;
            for (var i:int = 0; i < s.length; i++) h = h * 31 + s.charCodeAt(i);
            return h;
        }

        private function loadThumb():void
        {
            if (!_vo.thumbSrc || _vo.thumbSrc == "") return;
            _thumb = new Loader();
            _thumb.contentLoaderInfo.addEventListener(Event.COMPLETE, onThumbLoaded);
            _thumb.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, onThumbError);
            try
            {
                _thumb.load(new URLRequest(_vo.thumbSrc));
                _thumbHolder.addChild(_thumb);
            }
            catch (e:Error) {}
        }

        private function onThumbLoaded(e:Event):void
        {
            _thumb.width = TILE_W;
            _thumb.height = TILE_H;
            _thumb.alpha = 0.58;
            _thumb.scrollRect = new Rectangle(0, 0, TILE_W, TILE_H);
        }

        private function onThumbError(e:IOErrorEvent):void
        {
            try
            {
                if (_thumb && _thumbHolder.contains(_thumb)) _thumbHolder.removeChild(_thumb);
            }
            catch (err:Error) {}
        }

        private function makeSlidersIcon():Sprite
        {
            var s:Sprite = new Sprite();
            for (var i:int = 0; i < 3; i++)
            {
                var y:int = i * 7;
                s.graphics.lineStyle(2, 0xD0D0D0, 0.86);
                s.graphics.moveTo(0, y);
                s.graphics.lineTo(28, y);
                s.graphics.beginFill(0xD0D0D0, 0.92);
                s.graphics.drawCircle((i == 0 ? 7 : (i == 1 ? 17 : 12)), y, 3.5);
                s.graphics.endFill();
            }
            return s;
        }

        private function onOver(e:MouseEvent):void { _hover.visible = true; }
        private function onOut(e:MouseEvent):void  { _hover.visible = false; }

        private function onClick(e:MouseEvent):void
        {
            var ev:WeatherEvent = new WeatherEvent(WeatherEvent.MAP_SELECTED);
            ev.mapId = _vo.id;
            dispatchEvent(ev);
        }

        public function get data():MapVO { return _vo; }
    }
}
