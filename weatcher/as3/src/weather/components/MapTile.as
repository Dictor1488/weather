package weather.components
{
    import flash.display.Sprite;
    import flash.display.Loader;
    import flash.display.Bitmap;
    import flash.events.Event;
    import flash.events.MouseEvent;
    import flash.net.URLRequest;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.geom.Rectangle;

    import weather.data.MapVO;
    import weather.events.WeatherEvent;

    /**
     * Плитка однієї карти в сітці 4xN (Tab #2).
     * 
     * Розміри з скріна: ~210x100, усередині — мініатюра + назва + іконка "налаштувати".
     * Клік будь-де по плитці → відкрити деталі цієї карти.
     */
    public class MapTile extends Sprite
    {
        public static const TILE_W:int = 210;
        public static const TILE_H:int = 100;

        private var _vo:MapVO;
        private var _bg:Sprite;
        private var _thumb:Loader;
        private var _title:TextField;
        private var _hoverOverlay:Sprite;

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
            _bg.graphics.lineStyle(1, 0x3A3A3A);
            _bg.graphics.beginFill(0x1A1A1A);
            _bg.graphics.drawRect(0, 0, TILE_W, TILE_H);
            _bg.graphics.endFill();
            addChild(_bg);

            // Мініатюра на весь розмір плитки
            if (_vo.thumbSrc)
            {
                _thumb = new Loader();
                _thumb.contentLoaderInfo.addEventListener(Event.COMPLETE, onThumbLoaded);
                try { _thumb.load(new URLRequest(_vo.thumbSrc)); } catch(e:Error) {}
                addChild(_thumb);
            }

            // Градієнт-затемнення зверху для читабельності тексту
            var grad:Sprite = new Sprite();
            grad.graphics.beginFill(0x000000, 0.5);
            grad.graphics.drawRect(0, 0, TILE_W, 28);
            grad.graphics.endFill();
            addChild(grad);

            // Назва карти
            _title = new TextField();
            _title.defaultTextFormat = new TextFormat("$FieldFont", 15, 0xFFFFFF, true, null, null, null, null, "center");
            _title.embedFonts = true;
            _title.selectable = false;
            _title.mouseEnabled = false;
            _title.width = TILE_W;
            _title.y = 6;
            _title.text = _vo.label;
            addChild(_title);

            // Оверлей hover
            _hoverOverlay = new Sprite();
            _hoverOverlay.graphics.beginFill(0xFFAA00, 0.18);
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
            // підняти градієнт і назву поверх
            setChildIndex(_thumb, 1);
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
