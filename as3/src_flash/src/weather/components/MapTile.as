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
        public static const TILE_W:int = 480;
        public static const TILE_H:int = 42;

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
            graphics.lineStyle(1, 0x30363C, 0.9);
            graphics.beginFill(0x11161B, 0.82);
            graphics.drawRect(0, 0, TILE_W, TILE_H);
            graphics.endFill();

            _thumbHolder = new Sprite();
            _thumbHolder.x = 4;
            _thumbHolder.y = 4;
            addChild(_thumbHolder);

            _thumbHolder.graphics.lineStyle(1, 0x22272D, 0.95);
            _thumbHolder.graphics.beginFill(0x080A0C, 0.85);
            _thumbHolder.graphics.drawRect(0, 0, 76, 34);
            _thumbHolder.graphics.endFill();

            loadThumb();

            var shade:Shape = new Shape();
            shade.graphics.beginFill(0x000000, 0.26);
            shade.graphics.drawRect(4, 4, 76, 34);
            shade.graphics.endFill();
            addChild(shade);

            _hover = new Sprite();
            _hover.graphics.beginFill(0xC6882A, 0.18);
            _hover.graphics.drawRect(0, 0, TILE_W, TILE_H);
            _hover.graphics.endFill();
            _hover.visible = false;
            addChild(_hover);

            var title:TextField = new TextField();
            title.defaultTextFormat = new TextFormat("_sans", 14, 0xF2F2F2, true);
            title.selectable = false;
            title.autoSize = "left";
            title.text = _vo.label;
            title.x = 92;
            title.y = 11;
            addChild(title);

            var icon:TextField = new TextField();
            icon.defaultTextFormat = new TextFormat("_sans", 12, 0xB98525, true);
            icon.selectable = false;
            icon.autoSize = "left";
            icon.text = "□";
            icon.x = TILE_W - 28;
            icon.y = 12;
            addChild(icon);
        }

        private function loadThumb():void
        {
            if (!_vo.thumbSrc || _vo.thumbSrc == "")
                return;

            _thumb = new Loader();
            _thumb.contentLoaderInfo.addEventListener(Event.COMPLETE, onThumbLoaded);
            _thumb.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, onThumbError);

            try
            {
                _thumb.load(new URLRequest(_vo.thumbSrc));
                _thumbHolder.addChild(_thumb);
            }
            catch (e:Error)
            {
                // Keep placeholder if client resource is not available.
            }
        }

        private function onThumbLoaded(e:Event):void
        {
            _thumb.width = 76;
            _thumb.height = 34;
            _thumb.alpha = 0.84;
            _thumb.scrollRect = new Rectangle(0, 0, 76, 34);
        }

        private function onThumbError(e:IOErrorEvent):void
        {
            try
            {
                if (_thumb && _thumbHolder.contains(_thumb))
                    _thumbHolder.removeChild(_thumb);
            }
            catch (err:Error) {}
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
