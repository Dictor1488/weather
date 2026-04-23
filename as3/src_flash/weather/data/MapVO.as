package weather.data
{
    /**
     * Value Object для однієї карти.
     * 
     * id         - внутрішня назва директорії ("02_malinovka", "04_himmelsdorf" ...)
     *              відповідає імені папки в res/spaces/
     * label      - локалізована назва для UI ("Малинівка", "Хіммельсдорф")
     * thumbSrc   - мініатюра карти для сітки в Tab #2
     * presets    - масив PresetVO з вагами *саме для цієї карти*
     * useGlobal  - якщо true, карта ігнорує свої presets і використовує глобальні
     *              (за замовчуванням true для всіх карт — поки користувач не зайшов у деталі)
     */
    public class MapVO
    {
        public var id:String;
        public var label:String;
        public var thumbSrc:String;
        public var presets:Vector.<PresetVO>;
        public var useGlobal:Boolean = true;

        public function MapVO(id:String, label:String, thumbSrc:String = null)
        {
            this.id = id;
            this.label = label;
            this.thumbSrc = thumbSrc;
            this.presets = new Vector.<PresetVO>();
            this.useGlobal = true;
        }

        public function toObject():Object
        {
            var arr:Array = [];
            for (var i:int = 0; i < presets.length; i++)
                arr.push(presets[i].toObject());
            return { id: id, label: label, useGlobal: useGlobal, presets: arr };
        }
    }
}
