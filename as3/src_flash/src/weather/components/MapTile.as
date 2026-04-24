package weather.components
{
    import flash.display.Sprite;
    import flash.events.MouseEvent;
    import flash.text.TextField;
    import flash.text.TextFormat;

    import weather.data.MapVO;
    import weather.events.WeatherEvent;

    public class MapTile extends Sprite
    {
        public static const TILE_W:int = 394;
        public static const TILE_H:int = 34;

        private var _vo:MapVO;
        private var _hover:Sprite;

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

            _hover = new Sprite();
            _hover.graphics.beginFill(0xC6882A, 0.18);
            _hover.graphics.drawRect(0, 0, TILE_W, TILE_H);
            _hover.graphics.endFill();
            _hover.visible = false;
            addChild(_hover);

            var title:TextField = new TextField();
            title.defaultTextFormat = new TextFormat("_sans", 13, 0xF2F2F2, true);
            title.selectable = false;
            title.autoSize = "left";
            title.text = _vo.label;
            title.x = 12;
            title.y = 7;
            addChild(title);

            var icon:TextField = new TextField();
            icon.defaultTextFormat = new TextFormat("_sans", 14, 0xD5A45A, true);
            icon.selectable = false;
            icon.autoSize = "left";
            icon.text = "⚙";
            icon.x = TILE_W - 28;
            icon.y = 7;
            addChild(icon);
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
