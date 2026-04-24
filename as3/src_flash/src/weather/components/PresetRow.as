package weather.components
{
    import flash.display.Bitmap;
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
        public static const ROW_HEIGHT:int = 62;
        public static const MAX_WEIGHT:Number = 20.0;

        private var _vo:PresetVO;
        private var _mapId:String;
        private var _rowWidth:int = 796;
        private var _labelW:int = 128;
        private var _sliderW:int = 390;
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
            if (_vo.label == "Пасмурно" || _vo.label == "Хмарно" || _vo.label == "Overcast")
                _vo.label = "Похмуро";
            buildUI();
        }

        private function buildUI():void
        {
            graphics.lineStyle(1, 0x2A2E34, 0.95);
            graphics.beginFill(0x0C0F14, 0.92);
            graphics.drawRect(0, 0, _rowWidth, ROW_HEIGHT);
            graphics.endFill();

            var label:TextField = new TextField();
            label.defaultTextFormat = new TextFormat("_sans", 16, 0xF0F0F0, true);
            label.selectable = false;
            label.width = _labelW - 14;
            label.height = 24;
            label.text = _vo.label;
            label.x = 14;
            label.y = 20;
            addChild(label);

            buildSlider();

            _weightText = new TextField();
            _weightText.defaultTextFormat = new TextFormat("_sans", 13, 0xC8C8C8, true);
            _weightText.selectable = false;
            _weightText.width = 108;
            _weightText.height = 22;
            _weightText.x = 550;
            _weightText.y = 22;
            addChild(_weightText);

            buildPreview();
            updateWeightText();
        }

        private function buildSlider():void
        {
            var zoneX:int = _labelW + 8;

            var startMark:Shape = new Shape();
            startMark.graphics.lineStyle(2, 0x888888, 0.65);
            startMark.graphics.moveTo(0, 0);
            startMark.graphics.lineTo(0, 20);
            startMark.graphics.moveTo(8, 0);
            startMark.graphics.lineTo(8, 20);
            startMark.x = zoneX;
            startMark.y = 21;
            addChild(startMark);

            _sliderTrack = new Sprite();
            _sliderTrack.x = zoneX + 16;
            _sliderTrack.y = 31;
            addChild(_sliderTrack);

            _sliderTrack.graphics.beginFill(0x060606, 1);
            _sliderTrack.graphics.drawRect(0, 0, _sliderW, 5);
            _sliderTrack.graphics.endFill();

            for (var i:int = 0; i <= 20; i++)
            {
                _sliderTrack.graphics.lineStyle(1, 0x50160C, 0.72);
                _sliderTrack.graphics.moveTo(i * (_sliderW / 20), -5);
                _sliderTrack.graphics.lineTo(i * (_sliderW / 20), 10);
            }

            _sliderFill = new Shape();
            _sliderTrack.addChild(_sliderFill);

            _sliderThumb = new Sprite();
            _sliderThumb.graphics.lineStyle(1, 0xC8A880, 1);
            _sliderThumb.graphics.beginFill(0x8C7050, 1);
            _sliderThumb.graphics.drawRect(-5, -10, 10, 24);
            _sliderThumb.graphics.endFill();
            _sliderThumb.y = 2;
            _sliderTrack.addChild(_sliderThumb);

            _sliderTrack.addEventListener(MouseEvent.CLICK, onTrackClick);
            _sliderThumb.addEventListener(MouseEvent.MOUSE_DOWN, onThumbDown);

            updateSliderPos();
        }

        private function buildPreview():void
        {
            _previewHolder = new Sprite();
            _previewHolder.x = _rowWidth - 138;
            _previewHolder.y = 0;
            addChild(_previewHolder);

            drawPreviewPlaceholder();

            if (_vo.previewSrc)
            {
                _preview = new Loader();
                _preview.contentLoaderInfo.addEventListener(Event.COMPLETE, onPreviewLoaded);
                try
                {
                    _preview.load(new URLRequest(_vo.previewSrc));
                    _previewHolder.addChild(_preview);
                }
                catch (e:Error) {}
            }
        }

        private function drawPreviewPlaceholder():void
        {
            var color:uint = 0x1F2820;
            if (_vo.id == "midnight")      color = 0x15243C;
            else if (_vo.id == "overcast") color = 0x353A40;
            else if (_vo.id == "sunset")   color = 0x54402B;
            else if (_vo.id == "midday")   color = 0x344420;

            _previewHolder.graphics.clear();
            _previewHolder.graphics.beginFill(color, 0.82);
            _previewHolder.graphics.drawRect(0, 0, 138, ROW_HEIGHT);
            _previewHolder.graphics.endFill();
        }

        private function onPreviewLoaded(e:Event):void
        {
            var bw:Number = _preview.contentLoaderInfo.width;
            var bh:Number = _preview.contentLoaderInfo.height;
            if (bw <= 0 || bh <= 0)
            {
                _preview.width = 138;
                _preview.height = ROW_HEIGHT;
            }
            else
            {
                var scale:Number = Math.max(138 / bw, ROW_HEIGHT / bh);
                _preview.scaleX = _preview.scaleY = scale;
                _preview.x = int((138 - bw * scale) * 0.5);
                _preview.y = int((ROW_HEIGHT - bh * scale) * 0.5);
            }
            try
            {
                var bmp:Bitmap = _preview.content as Bitmap;
                if (bmp) bmp.smoothing = true;
            }
            catch (err:Error) {}
            _preview.alpha = 0.82;
            _previewHolder.scrollRect = new Rectangle(0, 0, 138, ROW_HEIGHT);
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

            var parentSprite:Sprite = parent as Sprite;
            if (parentSprite)
            {
                for (var i:int = 0; i < parentSprite.numChildren; i++)
                {
                    var sibling:PresetRow = parentSprite.getChildAt(i) as PresetRow;
                    if (sibling && sibling != this) sibling.refreshWeightText();
                }
            }

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
            _sliderFill.graphics.beginFill(0x802016, 0.85);
            _sliderFill.graphics.drawRect(0, 0, px, 5);
            _sliderFill.graphics.endFill();
        }

        private function updateWeightText():void
        {
            _weightText.text = "вага: " + String(int(_vo.weight)) + " (" + MAX_WEIGHT.toFixed(1) + ")";
        }

        public function refreshWeightText():void
        {
            updateWeightText();
        }

        public function get data():PresetVO { return _vo; }
    }
}
