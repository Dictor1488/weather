package weather.components
{
    import flash.display.Loader;
    import flash.display.Shape;
    import flash.display.Sprite;
    import flash.events.Event;
    import flash.events.MouseEvent;
    import flash.geom.Rectangle;
    import flash.net.URLRequest;
    import flash.text.TextField;
    import flash.text.TextFormat;

    import weather.data.PresetVO;
    import weather.events.WeatherEvent;

    public class PresetRow extends Sprite
    {
        public static const ROW_HEIGHT:int = 74;
        public static const MAX_WEIGHT:Number = 20.0;

        private var _vo:PresetVO;
        private var _mapId:String;
        private var _rowWidth:int = 480;
        private var _sliderW:int = 250;
        private var _sliderTrack:Sprite;
        private var _sliderFill:Shape;
        private var _sliderThumb:Sprite;
        private var _weightText:TextField;
        private var _preview:Loader;
        private var _previewHolder:Sprite;
        private var _dragging:Boolean = false;

        public function PresetRow(vo:PresetVO, mapId:String = null)
        {
            _vo = vo;
            _mapId = mapId;
            if (_vo.label == "Пасмурно" || _vo.label == "Хмарно")
                _vo.label = "Похмуро";
            buildUI();
        }

        private function buildUI():void
        {
            graphics.lineStyle(1, 0x343A40, 0.95);
            graphics.beginFill(0x11161B, 0.82);
            graphics.drawRect(0, 0, _rowWidth, ROW_HEIGHT);
            graphics.endFill();

            var label:TextField = new TextField();
            label.defaultTextFormat = new TextFormat("_sans", 16, 0xF4F4F4, true);
            label.selectable = false;
            label.autoSize = "left";
            label.text = _vo.label;
            label.x = 14;
            label.y = 13;
            addChild(label);

            _weightText = new TextField();
            _weightText.defaultTextFormat = new TextFormat("_sans", 12, 0xDADADA, true);
            _weightText.selectable = false;
            _weightText.autoSize = "left";
            _weightText.x = 366;
            _weightText.y = 13;
            addChild(_weightText);

            buildSlider();

            _previewHolder = new Sprite();
            _previewHolder.x = 342;
            _previewHolder.y = 38;
            addChild(_previewHolder);
            drawPreviewPlaceholder();

            if (_vo.previewSrc)
            {
                _preview = new Loader();
                _preview.contentLoaderInfo.addEventListener(Event.COMPLETE, onPreviewLoaded);
                try { _preview.load(new URLRequest(_vo.previewSrc)); _previewHolder.addChild(_preview); }
                catch (e:Error) {}
            }

            updateWeightText();
        }

        private function buildSlider():void
        {
            _sliderTrack = new Sprite();
            _sliderTrack.x = 14;
            _sliderTrack.y = 50;
            addChild(_sliderTrack);

            _sliderTrack.graphics.beginFill(0x070707, 1);
            _sliderTrack.graphics.drawRect(0, 0, _sliderW, 5);
            _sliderTrack.graphics.endFill();

            for (var i:int = 0; i <= 20; i++)
            {
                _sliderTrack.graphics.lineStyle(1, 0x542018, 0.65);
                _sliderTrack.graphics.moveTo(i * (_sliderW / 20), -4);
                _sliderTrack.graphics.lineTo(i * (_sliderW / 20), 9);
            }

            _sliderFill = new Shape();
            _sliderTrack.addChild(_sliderFill);

            _sliderThumb = new Sprite();
            _sliderThumb.graphics.lineStyle(1, 0xD5C0A2, 1);
            _sliderThumb.graphics.beginFill(0x8C7151, 1);
            _sliderThumb.graphics.drawRect(-5, -10, 10, 24);
            _sliderThumb.graphics.endFill();
            _sliderThumb.y = 2;
            _sliderTrack.addChild(_sliderThumb);

            _sliderTrack.addEventListener(MouseEvent.CLICK, onTrackClick);
            _sliderThumb.addEventListener(MouseEvent.MOUSE_DOWN, onThumbDown);

            updateSliderPos();
        }

        private function drawPreviewPlaceholder():void
        {
            var color:uint = 0x1F2820;
            if (_vo.id == "midnight")      color = 0x15243C;
            else if (_vo.id == "overcast") color = 0x353A40;
            else if (_vo.id == "sunset")   color = 0x54402B;
            else if (_vo.id == "midday")   color = 0x344420;

            _previewHolder.graphics.clear();
            _previewHolder.graphics.beginFill(color, 0.95);
            _previewHolder.graphics.drawRect(0, 0, 122, 38);
            _previewHolder.graphics.endFill();
        }

        private function onPreviewLoaded(e:Event):void
        {
            _preview.width = 122;
            _preview.height = 38;
            _preview.alpha = 0.74;
            _preview.scrollRect = new Rectangle(0, 0, 122, 38);
        }

        private function onTrackClick(e:MouseEvent):void { setSliderValue(_sliderTrack.mouseX); }

        private function onThumbDown(e:MouseEvent):void
        {
            _dragging = true;
            if (stage)
            {
                stage.addEventListener(MouseEvent.MOUSE_MOVE, onStageMove);
                stage.addEventListener(MouseEvent.MOUSE_UP, onStageUp);
            }
            e.stopPropagation();
        }

        private function onStageMove(e:MouseEvent):void
        {
            if (!_dragging) return;
            setSliderValue(_sliderTrack.mouseX);
        }

        private function onStageUp(e:MouseEvent):void
        {
            _dragging = false;
            if (stage)
            {
                stage.removeEventListener(MouseEvent.MOUSE_MOVE, onStageMove);
                stage.removeEventListener(MouseEvent.MOUSE_UP, onStageUp);
            }
        }

        private function setSliderValue(px:Number):void
        {
            px = Math.max(0, Math.min(_sliderW, px));
            _vo.weight = Math.round((px / _sliderW) * MAX_WEIGHT);
            updateSliderPos();
            updateWeightText();

            var ev:WeatherEvent = new WeatherEvent(WeatherEvent.PRESET_WEIGHT_CHANGED);
            ev.mapId = _mapId;
            ev.presetId = _vo.id;
            ev.value = _vo.weight;
            dispatchEvent(ev);
        }

        private function updateSliderPos():void
        {
            var px:int = int((_vo.weight / MAX_WEIGHT) * _sliderW);
            _sliderThumb.x = px;
            _sliderFill.graphics.clear();
            _sliderFill.graphics.beginFill(0x8A2A20, 0.78);
            _sliderFill.graphics.drawRect(0, 0, px, 5);
            _sliderFill.graphics.endFill();
        }

        private function updateWeightText():void
        {
            _weightText.text = String(int(_vo.weight)) + "/20";
        }

        public function get data():PresetVO { return _vo; }
    }
}
