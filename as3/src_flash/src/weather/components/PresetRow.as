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
        public static const ROW_HEIGHT:int = 64;
        public static const MAX_WEIGHT:Number = 20.0;

        private var _vo:PresetVO;
        private var _mapId:String;
        private var _bg:Sprite;
        private var _label:TextField;
        private var _weightText:TextField;
        private var _sliderTrack:Sprite;
        private var _sliderFill:Shape;
        private var _sliderThumb:Sprite;
        private var _preview:Loader;
        private var _previewPlaceholder:Sprite;
        private var _rowWidth:int;
        private var _sliderW:int = 310;
        private var _dragging:Boolean = false;

        public function PresetRow(vo:PresetVO, mapId:String = null)
        {
            _vo = vo;
            _mapId = mapId;
            if (_vo.label == "Пасмурно" || _vo.label == "Хмарно")
                _vo.label = "Похмуро";
            _rowWidth = 880;
            buildUI();
        }

        private function buildUI():void
        {
            _bg = new Sprite();
            addChild(_bg);
            drawBg();

            _label = new TextField();
            _label.defaultTextFormat = new TextFormat("_sans", 20, 0xFFFFFF, true);
            _label.selectable = false;
            _label.autoSize = "left";
            _label.text = _vo.label;
            _label.x = 18;
            _label.y = 18;
            addChild(_label);

            buildSlider();

            _weightText = new TextField();
            _weightText.defaultTextFormat = new TextFormat("_sans", 15, 0xE2E2E2, true);
            _weightText.selectable = false;
            _weightText.autoSize = "left";
            _weightText.x = 520;
            _weightText.y = 21;
            addChild(_weightText);
            updateWeightText();

            _previewPlaceholder = new Sprite();
            addChild(_previewPlaceholder);
            drawPreviewPlaceholder();

            if (_vo.previewSrc)
            {
                _preview = new Loader();
                _preview.contentLoaderInfo.addEventListener(Event.COMPLETE, onPreviewLoaded);
                try { _preview.load(new URLRequest(_vo.previewSrc)); addChild(_preview); }
                catch (e:Error) {}
            }
        }

        private function buildSlider():void
        {
            _sliderTrack = new Sprite();

            _sliderTrack.graphics.lineStyle(1, 0x111111, 1);
            _sliderTrack.graphics.beginFill(0x0A0A0A, 1);
            _sliderTrack.graphics.drawRect(0, 0, _sliderW, 6);
            _sliderTrack.graphics.endFill();

            // tiny red ticks, WoT-like
            for (var i:int = 0; i < 32; i++)
            {
                _sliderTrack.graphics.lineStyle(1, 0x4D1611, 0.65);
                _sliderTrack.graphics.moveTo(i * 10, -2);
                _sliderTrack.graphics.lineTo(i * 10, 8);
            }

            _sliderTrack.x = 175;
            _sliderTrack.y = 30;
            addChild(_sliderTrack);

            _sliderFill = new Shape();
            _sliderTrack.addChild(_sliderFill);

            _sliderThumb = new Sprite();
            _sliderThumb.graphics.lineStyle(1, 0xE0C29B, 1);
            _sliderThumb.graphics.beginFill(0x8B6F50, 1);
            _sliderThumb.graphics.drawRect(-4, -8, 8, 22);
            _sliderThumb.graphics.endFill();
            _sliderThumb.y = 3;
            _sliderTrack.addChild(_sliderThumb);

            _sliderThumb.addEventListener(MouseEvent.MOUSE_DOWN, onThumbDown);
            _sliderTrack.addEventListener(MouseEvent.CLICK, onTrackClick);

            updateSliderPos();
        }

        private function updateSliderPos():void
        {
            var ratio:Number = _vo.weight / MAX_WEIGHT;
            var px:int = int(ratio * _sliderW);
            _sliderThumb.x = px;

            _sliderFill.graphics.clear();
            _sliderFill.graphics.beginFill(0x8A2A20, 0.75);
            _sliderFill.graphics.drawRect(0, 0, px, 6);
            _sliderFill.graphics.endFill();
        }

        private function onTrackClick(e:MouseEvent):void
        {
            setSliderValue(_sliderTrack.mouseX);
        }

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

        private function drawBg():void
        {
            _bg.graphics.clear();
            _bg.graphics.lineStyle(1, 0x50545A, 0.9);
            _bg.graphics.beginFill(0x171A1D, 0.72);
            _bg.graphics.drawRect(0, 0, _rowWidth, ROW_HEIGHT);
            _bg.graphics.endFill();
        }

        private function drawPreviewPlaceholder():void
        {
            var color:uint = 0x1F2820;
            if (_vo.id == "midnight")      color = 0x15243C;
            else if (_vo.id == "overcast") color = 0x353A40;
            else if (_vo.id == "sunset")   color = 0x54402B;
            else if (_vo.id == "midday")   color = 0x344420;

            _previewPlaceholder.graphics.clear();
            _previewPlaceholder.graphics.beginFill(color, 0.90);
            _previewPlaceholder.graphics.drawRect(0, 0, 230, ROW_HEIGHT);
            _previewPlaceholder.graphics.endFill();
            _previewPlaceholder.x = _rowWidth - 230;
        }

        private function onPreviewLoaded(e:Event):void
        {
            _preview.width = 230;
            _preview.height = ROW_HEIGHT;
            _preview.x = _rowWidth - 230;
            _preview.scrollRect = new Rectangle(0, 0, 230, ROW_HEIGHT);
            _preview.alpha = 0.70;
        }

        private function updateWeightText():void
        {
            _weightText.text = "вага: " + _vo.weight.toFixed(0) + " (" + MAX_WEIGHT.toFixed(1) + ")";
        }

        public function setWidth(w:int):void
        {
            _rowWidth = w;
            drawBg();
            drawPreviewPlaceholder();
            if (_preview) _preview.x = _rowWidth - 230;
        }

        public function get data():PresetVO { return _vo; }
    }
}
