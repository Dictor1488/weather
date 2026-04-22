package weather.components
{
    import flash.display.Sprite;
    import flash.display.Loader;
    import flash.display.Bitmap;
    import flash.events.Event;
    import flash.net.URLRequest;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.geom.Rectangle;

    import scaleform.clik.controls.Slider;
    import scaleform.clik.events.SliderEvent;

    import weather.data.PresetVO;
    import weather.events.WeatherEvent;

    /**
     * Один рядок налаштування пресета:
     *   [ Лейбл ]   [ ====[]========= ]   вес: 12 (20.0)   [ preview ]
     * 
     * MAX_WEIGHT = 20 — як на скріні ("(20.0)" — це стеля).
     * Ширина підганяється з батька через setWidth().
     */
    public class PresetRow extends Sprite
    {
        public static const ROW_HEIGHT:int = 64;
        public static const MAX_WEIGHT:Number = 20.0;

        private var _vo:PresetVO;
        private var _mapId:String;  // null = global
        private var _bg:Sprite;
        private var _label:TextField;
        private var _weightText:TextField;
        private var _slider:Slider;
        private var _preview:Loader;
        private var _width:int;

        public function PresetRow(vo:PresetVO, mapId:String = null)
        {
            _vo = vo;
            _mapId = mapId;
            _width = 820;
            buildUI();
        }

        private function buildUI():void
        {
            // Фон рядка (темна панель із рамкою як на скрінах)
            _bg = new Sprite();
            addChild(_bg);
            drawBg();

            // Лейбл зліва ("Стандарт", "Ніч" і т.д.) — жирний білий
            _label = new TextField();
            _label.defaultTextFormat = new TextFormat("$FieldFont", 18, 0xFFFFFF, true);
            _label.embedFonts = true;
            _label.selectable = false;
            _label.autoSize = "left";
            _label.text = _vo.label;
            _label.x = 20;
            _label.y = (ROW_HEIGHT - 24) / 2;
            addChild(_label);

            // Слайдер 0..20 (scaleform CLIK Slider)
            _slider = new Slider();
            _slider.minimum = 0;
            _slider.maximum = MAX_WEIGHT;
            _slider.snapInterval = 1;
            _slider.snapping = true;
            _slider.value = _vo.weight;
            _slider.x = 180;
            _slider.y = (ROW_HEIGHT - 16) / 2;
            _slider.width = 340;
            _slider.addEventListener(SliderEvent.VALUE_CHANGE, onSliderChanged);
            addChild(_slider);

            // Текст "вес: X (20.0)"
            _weightText = new TextField();
            _weightText.defaultTextFormat = new TextFormat("$FieldFont", 16, 0xC8C8C8, false);
            _weightText.embedFonts = true;
            _weightText.selectable = false;
            _weightText.autoSize = "left";
            _weightText.x = 540;
            _weightText.y = (ROW_HEIGHT - 20) / 2;
            addChild(_weightText);
            updateWeightText();

            // Preview-мініатюра праворуч (44x60 — як видно на скріні)
            if (_vo.previewSrc)
            {
                _preview = new Loader();
                _preview.contentLoaderInfo.addEventListener(Event.COMPLETE, onPreviewLoaded);
                try
                {
                    _preview.load(new URLRequest(_vo.previewSrc));
                }
                catch (e:Error) { /* ігнорувати відсутність картинки */ }
                addChild(_preview);
            }
        }

        private function drawBg():void
        {
            _bg.graphics.clear();
            _bg.graphics.lineStyle(1, 0x3C3C3C, 1);
            _bg.graphics.beginFill(0x1A1A1A, 0.55);
            _bg.graphics.drawRect(0, 0, _width, ROW_HEIGHT);
            _bg.graphics.endFill();
        }

        private function onPreviewLoaded(e:Event):void
        {
            var bmp:Bitmap = _preview.content as Bitmap;
            if (bmp)
            {
                _preview.width = 220;
                _preview.height = ROW_HEIGHT;
                _preview.x = _width - 220;
                _preview.y = 0;
                // прямокутник обрізки, щоб не виходило за межі рядка
                _preview.scrollRect = new Rectangle(0, 0, 220, ROW_HEIGHT);
            }
        }

        private function onSliderChanged(e:SliderEvent):void
        {
            _vo.weight = Math.round(_slider.value);
            updateWeightText();

            // кидаємо подію вгору — її зловить Mediator і прокине в Python через DAAPI
            var ev:WeatherEvent = new WeatherEvent(WeatherEvent.PRESET_WEIGHT_CHANGED);
            ev.mapId = _mapId;
            ev.presetId = _vo.id;
            ev.value = _vo.weight;
            dispatchEvent(ev);
        }

        private function updateWeightText():void
        {
            _weightText.text = "вес: " + _vo.weight.toFixed(0) + " (" + MAX_WEIGHT.toFixed(1) + ")";
        }

        public function setWidth(w:int):void
        {
            _width = w;
            drawBg();
            if (_preview && _preview.content)
            {
                _preview.x = _width - 220;
            }
        }

        public function get data():PresetVO { return _vo; }
    }
}
