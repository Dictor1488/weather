package weather.components
{
    import flash.display.Loader;
    import flash.display.Sprite;
    import flash.events.Event;
    import flash.events.MouseEvent;
    import flash.geom.Rectangle;
    import flash.net.URLRequest;
    import flash.text.TextField;
    import flash.text.TextFormat;

    import weather.data.MapVO;
    import weather.events.WeatherEvent;

    public class MapTile extends Sprite
    {
        public static const TILE_W:int = 212;
        public static const TILE_H:int = 104;

        private var _vo:MapVO;
        private var _bg:Sprite;
        private var _thumb:Loader;
        private var _title:TextField;
        private var _hoverOverlay:Sprite;
        private var _footer:Sprite;

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
            _bg.graphics.lineStyle(1, 0x3A3A3A, 1);
            _bg.graphics.beginFill(0x1A1A1A, 1);
            _bg.graphics.drawRect(0, 0, TILE_W, TILE_H);
            _bg.graphics.endFill();
            addChild(_bg);

            if (_vo.thumbSrc)
            {
                _thumb = new Loader();
                _thumb.contentLoaderInfo.addEventListener(Event.COMPLETE, onThumbLoaded);
                try { _thumb.load(new URLRequest(_vo.thumbSrc)); } catch(e:Error) {}
                addChild(_thumb);
            }

            var grad:Sprite = new Sprite();
            grad.graphics.beginFill(0x000000, 0.45);
            grad.graphics.drawRect(0, 0, TILE_W, 30);
            grad.graphics.endFill();
            addChild(grad);

            _title = new TextField();
            _title.defaultTextFormat = new TextFormat("Arial", 15, 0xFFFFFF, true, null, null, null, null, "center");
            _title.embedFonts = false;
            _title.selectable = false;
            _title.mouseEnabled = false;
            _title.width = TILE_W;
            _title.height = 24;
            _title.y = 6;
            _title.text = _vo.label;
            addChild(_title);

            _footer = new Sprite();
            _footer.graphics.beginFill(0x000000, 0.26);
            _footer.graphics.drawRect(0, TILE_H - 20, TILE_W, 20);
            _footer.graphics.endFill();
            addChild(_footer);

            var footerTF:TextField = new TextField();
            footerTF.defaultTextFormat = new TextFormat("Arial", 11, 0xD2D2D2, false, null, null, null, null, "center");
            footerTF.embedFonts = false;
            footerTF.selectable = false;
            footerTF.mouseEnabled = false;
            footerTF.width = TILE_W;
            footerTF.height = 18;
            footerTF.y = TILE_H - 18;
            footerTF.text = "налаштувати";
            addChild(footerTF);

            _hoverOverlay = new Sprite();
            _hoverOverlay.graphics.beginFill(0xF4A11A, 0.16);
            _hoverOverlay.graphics.drawRect(0, 0, TILE_W, TILE_H);
            _hoverOverlay.graphics.endFill();
            _hoverOverlay.visible = false;
            addChild(_hoverOverlay);
        }

        private function onThumbLoaded(e:Event):void
        {
            _thumb.width = TILE_W;
            _thumb.height = TILE_H;
            _thumb.scrollRect = new Rectangle(0, 0, TILE_W, TILE_H);
            _thumb.alpha = 0.86;
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
