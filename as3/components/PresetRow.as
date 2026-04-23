package weather.components
{
    import flash.display.Loader;
    import flash.display.Sprite;
    import flash.events.Event;
    import flash.geom.Rectangle;
    import flash.net.URLRequest;
    import flash.text.TextField;
    import flash.text.TextFormat;

    import scaleform.clik.controls.Slider;
    import scaleform.clik.events.SliderEvent;

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
        private var _slider:Slider;
        private var _preview:Loader;
        private var _previewPlaceholder:Sprite;
        private var _width:int;

        public function PresetRow(vo:PresetVO, mapId:String = null)
        {
            _vo = vo;
            _mapId = mapId;
            _width = 860;
            buildUI();
        }

        private function buildUI():void
        {
            _bg = new Sprite();
            addChild(_bg);
            drawBg();

            _label = new TextField();
            _label.defaultTextFormat = new TextFormat("$FieldFont", 17, 0xFFFFFF, true);
            _label.embedFonts = true;
            _label.selectable = false;
            _label.autoSize = "left";
            _label.text = _vo.label;
            _label.x = 18;
            _label.y = 18;
            addChild(_label);

            _slider = new Slider();
            _slider.minimum = 0;
            _slider.maximum = MAX_WEIGHT;
            _slider.snapInterval = 1;
            _slider.snapping = true;
            _slider.value = _vo.weight;
            _slider.x = 170;
            _slider.y = 24;
            _slider.width = 320;
            _slider.addEventListener(SliderEvent.VALUE_CHANGE, onSliderChanged);
            addChild(_slider);

            _weightText = new TextField();
            _weightText.defaultTextFormat = new TextFormat("$FieldFont", 15, 0xD6D6D6, false);
            _weightText.embedFonts = true;
            _weightText.selectable = false;
            _weightText.autoSize = "left";
            _weightText.x = 510;
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
                try
                {
                    _preview.load(new URLRequest(_vo.previewSrc));
                    addChild(_preview);
                }
                catch (e:Error)
                {
                }
            }
        }

        private function drawBg():void
        {
            _bg.graphics.clear();
            _bg.graphics.lineStyle(1, 0x3C3C3C, 1);
            _bg.graphics.beginFill(0x1A1A1A, 0.58);
            _bg.graphics.drawRect(0, 0, _width, ROW_HEIGHT);
            _bg.graphics.endFill();
        }

        private function drawPreviewPlaceholder():void
        {
            var color:uint = 0x243025;
            if (_vo.id == "midnight") color = 0x13233D;
            else if (_vo.id == "overcast") color = 0x39424B;
            else if (_vo.id == "sunset") color = 0x61452A;
            else if (_vo.id == "midday") color = 0x485B33;

            _previewPlaceholder.graphics.clear();
            _previewPlaceholder.graphics.beginFill(color, 0.88);
            _previewPlaceholder.graphics.drawRect(0, 0, 180, ROW_HEIGHT);
            _previewPlaceholder.graphics.endFill();
            _previewPlaceholder.x = _width - 180;
            _previewPlaceholder.y = 0;
        }

        private function onPreviewLoaded(e:Event):void
        {
            _preview.width = 180;
            _preview.height = ROW_HEIGHT;
            _preview.x = _width - 180;
            _preview.y = 0;
            _preview.scrollRect = new Rectangle(0, 0, 180, ROW_HEIGHT);
        }

        private function onSliderChanged(e:SliderEvent):void
        {
            _vo.weight = Math.round(_slider.value);
            updateWeightText();

            var ev:WeatherEvent = new WeatherEvent(WeatherEvent.PRESET_WEIGHT_CHANGED);
            ev.mapId = _mapId;
            ev.presetId = _vo.id;
            ev.value = _vo.weight;
            dispatchEvent(ev);
        }

        private function updateWeightText():void
        {
            _weightText.text = "вага: " + _vo.weight.toFixed(0) + " (" + MAX_WEIGHT.toFixed(1) + ")";
        }

        public function setWidth(w:int):void
        {
            _width = w;
            drawBg();
            drawPreviewPlaceholder();
            if (_preview)
                _preview.x = _width - 180;
        }

        public function get data():PresetVO { return _vo; }
    }
}
