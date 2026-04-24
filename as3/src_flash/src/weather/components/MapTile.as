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
        public static const TILE_W:int = 232;
        public static const TILE_H:int = 96;

        private var _vo:MapVO;
        private var _bg:Sprite;
        private var _thumb:Loader;
        private var _title:TextField;
        private var _hoverOverlay:Sprite;
        private var _paths:Array;
        private var _pathIndex:int = 0;

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
            _bg = new Sprite();
            _bg.graphics.lineStyle(1, 0x41444A, 1);
            _bg.graphics.beginFill(0x151719, 0.95);
            _bg.graphics.drawRect(0, 0, TILE_W, TILE_H);
            _bg.graphics.endFill();
            addChild(_bg);

            _paths = [
                "img://gui/maps/icons/map/stats/" + _vo.id + ".png",
                "img://gui/maps/icons/map/loading/" + _vo.id + ".png",
                "img://gui/maps/icons/map/large/" + _vo.id + ".png",
                "gui/maps/icons/map/stats/" + _vo.id + ".png",
                "gui/maps/icons/map/loading/" + _vo.id + ".png",
                _vo.thumbSrc
            ];
            loadNextThumb();

            var darkTop:Shape = new Shape();
            darkTop.graphics.beginFill(0x000000, 0.42);
            darkTop.graphics.drawRect(0, 0, TILE_W, 28);
            darkTop.graphics.endFill();
            addChild(darkTop);

            var darkBottom:Shape = new Shape();
            darkBottom.graphics.beginFill(0x000000, 0.34);
            darkBottom.graphics.drawRect(0, TILE_H - 24, TILE_W, 24);
            darkBottom.graphics.endFill();
            addChild(darkBottom);

            _title = new TextField();
            _title.defaultTextFormat = new TextFormat("_sans", 16, 0xF2F2F2, true, null, null, null, null, "center");
            _title.selectable = false;
            _title.mouseEnabled = false;
            _title.width = TILE_W;
            _title.height = 26;
            _title.y = 5;
            _title.text = _vo.label;
            addChild(_title);

            drawSettingsIcon();

            _hoverOverlay = new Sprite();
            _hoverOverlay.graphics.beginFill(0xE7A134, 0.16);
            _hoverOverlay.graphics.drawRect(0, 0, TILE_W, TILE_H);
            _hoverOverlay.graphics.endFill();
            _hoverOverlay.visible = false;
            addChild(_hoverOverlay);
        }

        private function loadNextThumb():void
        {
            if (_pathIndex >= _paths.length) return;

            var p:String = String(_paths[_pathIndex++]);
            if (!p || p == "null") { loadNextThumb(); return; }

            _thumb = new Loader();
            _thumb.contentLoaderInfo.addEventListener(Event.COMPLETE, onThumbLoaded);
            _thumb.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, onThumbError);
            try
            {
                _thumb.load(new URLRequest(p));
                addChildAt(_thumb, 1);
            }
            catch(e:Error)
            {
                loadNextThumb();
            }
        }

        private function onThumbError(e:IOErrorEvent):void
        {
            try
            {
                if (_thumb && contains(_thumb)) removeChild(_thumb);
            }
            catch(err:Error) {}
            loadNextThumb();
        }

        private function onThumbLoaded(e:Event):void
        {
            _thumb.width = TILE_W;
            _thumb.height = TILE_H;
            _thumb.scrollRect = new Rectangle(0, 0, TILE_W, TILE_H);
            _thumb.alpha = 0.82;
        }

        private function drawSettingsIcon():void
        {
            var icon:Sprite = new Sprite();
            icon.x = TILE_W / 2 - 20;
            icon.y = 40;
            icon.graphics.lineStyle(2, 0xFFFFFF, 0.85);

            icon.graphics.moveTo(0, 6);
            icon.graphics.lineTo(40, 6);
            icon.graphics.drawCircle(12, 6, 4);

            icon.graphics.moveTo(0, 16);
            icon.graphics.lineTo(40, 16);
            icon.graphics.drawCircle(28, 16, 4);

            icon.graphics.moveTo(0, 26);
            icon.graphics.lineTo(40, 26);
            icon.graphics.drawCircle(18, 26, 4);

            addChild(icon);
        }

        private function onOver(e:MouseEvent):void { _hoverOverlay.visible = true; }
        private function onOut(e:MouseEvent):void  { _hoverOverlay.visible = false; }

        private function onClick(e:MouseEvent):void
        {
            var ev:WeatherEvent = new WeatherEvent(WeatherEvent.MAP_SELECTED);
            ev.mapId = _vo.id;
            dispatchEvent(ev);
        }

        public function get data():MapVO { return _vo; }
    }
}
