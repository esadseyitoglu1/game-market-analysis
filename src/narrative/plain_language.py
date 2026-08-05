"""Narrative — Gündelik Dil Yardımcıları

NEDEN BU DOSYA VAR (bkz. plan "AKTİF PLAN 2026-08-05" Adım C — kullanıcı geri
bildirimi): Grafik başlıkları gündelik dile çevrildi ("Boomer Shooter'
taşıyan oyunlar 18 puan daha görünür") ama `templates.py`'deki `claim`
cümleleri hâlâ istatistik jargonu üretiyordu ("etki büyüklüğü +0.49, %95
güven aralığı [+0.42, +0.56]") — LLM bu cümleyi SADAKATLE aktardığı için
jargon script'e sızıyordu. Bu dosya, grafik VE cümle üretiminin AYNI dili
konuşması için ortak bir yer — `chart_selector.py` ve `templates.py` ikisi
de buradan import eder, kod tekrarı olmasın.

KURAL: rank-biserial etki değeri ("+0.49") YÜZDEYE ÇEVRİLEMEZ — farklı bir
istatistik, matematiksel olarak yanlış olur. Bunun yerine iki grubun medyan
percentile'ı arasındaki HAM farkı puan cinsinden ifade ediyoruz — bu dürüst
ve doğrudan anlaşılır.
"""

# numeric_split/boolean_flag bulguları teknik kolon adlarını taşıyor
# (örn. "average_playtime_forever > 0", "achievements > medyan (11.0)") —
# bunlar Finding.label'a generators.py'de kolon adından otomatik üretiliyor,
# editöre hiçbir şey ifade etmiyor. İnsan-okunur karşılığı burada tutuluyor.
COLUMN_PLAIN_NAMES = {
    "average_playtime_forever": "oynanma süresi",
    "median_playtime_forever": "oynanma süresi",
    "achievements": "başarım (achievement) sayısı",
    "dlc_count": "DLC sayısı",
    "required_age": "yaş sınırı",
    "discount": "indirim",
    "peak_ccu": "aynı anda oynayan oyuncu sayısı",
    "metacritic_score": "Metacritic puanı",
}


def plain_language_condition(label: str) -> str:
    """'average_playtime_forever > 0' -> 'Oynanma süresi olan oyunlar' gibi
    bir ifadeye çevirir. Eşleşme bulunamazsa label'ı olduğu gibi döndürür
    (ör. tag/kategori isimleri zaten insan-okunur, buraya hiç girmez)."""
    for col, plain in COLUMN_PLAIN_NAMES.items():
        if label.startswith(col):
            return f"{plain.capitalize()} olan oyunlar"
    return f"'{label}' koşulunu sağlayan oyunlar"


def plain_language_gap(group_median: float, baseline_median: float) -> str:
    """İki medyan percentile arasındaki farkı GÜNDELİK dile çevirir
    (ör. "18 puan daha görünür"). Bkz. modül docstring'i — neden yüzdeye
    çevrilmediği için."""
    gap_points = round((group_median - baseline_median) * 100)
    if gap_points == 0:
        return "aralarında belirgin bir fark yok"
    direction = "daha görünür" if gap_points > 0 else "daha az görünür"
    return f"{abs(gap_points)} puan {direction}"
