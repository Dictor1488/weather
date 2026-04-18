package weather.data
{
    /**
     * Value Object для одного пресета погоди.
     * 
     * id         - внутрішній ідентифікатор ("standard", "midnight", "overcast", "sunset", "midday")
     * label      - текст, який бачить користувач ("Стандарт", "Ніч" ...)
     * weight     - вага у рандомайзері (0..20). 0 = ніколи, 20 = завжди (якщо інші 0)
     * previewSrc - шлях до preview-картинки для цього пресета (44px висота праворуч слайдера)
     * guid       - GUID папки середовища в space.settings ("BF040BCB-..." для midday тощо)
     *              null для "standard" — бо це оригінальне середовище гри без замін
     */
    public class PresetVO
    {
        public var id:String;
        public var label:String;
        public var weight:Number = 0;
        public var previewSrc:String;
        public var guid:String;

        public function PresetVO(id:String, label:String, guid:String = null, previewSrc:String = null)
        {
            this.id = id;
            this.label = label;
            this.guid = guid;
            this.previewSrc = previewSrc;
            this.weight = 0;
        }

        public function clone():PresetVO
        {
            var p:PresetVO = new PresetVO(id, label, guid, previewSrc);
            p.weight = weight;
            return p;
        }

        public function toObject():Object
        {
            return { id: id, label: label, weight: weight, guid: guid, previewSrc: previewSrc };
        }
    }
}
