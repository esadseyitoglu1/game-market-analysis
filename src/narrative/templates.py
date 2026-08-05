"""Narrative — Yön-Nötr Şablonlar

NEDEN "YÖN-NÖTR" (bkz. plan — "İddia→kanıt bağlama"):
Eski sistemde (insight_engine.py'nin 7 sabit fonksiyonu) anlatı çerçevesi
ÖNCEDEN yazılmıştı — "Kalite Tuzağı", "Hype Balonu" gibi hikayeler önce
kurgulanıp sonra veri buna uydurulmaya çalışılıyordu. Veri tersini gösterse
bile cümlenin yönü değişmiyordu (bkz. Context — insight_80pct_cliff, df'i hiç
okumadan "kalite tuzağı" iddiası üretiyordu).

Burada TERSİNE çalışıyoruz: şablon iki versiyon içerir ("positive"/"negative"),
hangisinin kullanılacağına `Finding.direction` karar verir — yani veri
söylüyor, şablon veriye uyuyor, tersi değil. Her sayı `Finding` nesnesinin bir
alanından gelir; şablonda TEK BİR serbest/hardcoded sayı yoktur.

GÜNDELİK DİL (2026-08-05 eklendi, bkz. plan "AKTİF PLAN 2026-08-05" Adım C):
Kullanıcı canlı n8n çıktısını inceleyip şablonların istatistikçiye konuştuğunu
fark etti — "etki büyüklüğü +0.49, %95 güven aralığı [+0.42, +0.56]" gibi
cümleler LLM'e SADAKATLE aktarıldığı için doğrudan script'e sızıyordu, editör
bunu ekran yazısı olarak kullanamıyordu. Şablonlar artık `plain_language.py`
üzerinden ("18 puan daha görünür" gibi) HAM PUAN FARKINI kullanıyor — etki
büyüklüğü, güven aralığı, p/q-değeri gibi teknik terimler artık `claim`
cümlesinde HİÇ geçmiyor (istatistiksel titizlik kaybolmuyor — bunlar hâlâ
`evidence` alanında, findings.json'da duruyor, sadece izleyiciye giden
cümleden çıkarıldı).
"""

from src.discovery.base import Finding
from src.narrative.plain_language import plain_language_condition, plain_language_gap

# Nedensellik/abartı iması taşıyan, kanıtlanmamış iddialara yol açan kelimeler.
# tests/test_narrative.py bunları üretilen metinde arar — biri geçerse test kırılır.
FORBIDDEN_WORDS = [
    "katlar", "patlar", "kesinlikle", "her zaman", "garanti",
    "altın maden", "şaheser", "mucize", "asla başarısız",
    "kesin", "mutlaka", "hep",
]

# Şablon anahtarı -> (özne cümlesi üreten fonksiyon). Her fonksiyon
# finding.label'dan "bu grubu ne yaptı" ifadesini üretir; gap_desc (ham puan
# farkı, plain_language_gap'ten) ile birleşip tam cümleyi oluşturur.
_SUBJECT_BUILDERS = {
    "tags_list_single": lambda f: f"'{f.label}' etiketini taşıyan {f.n:,} oyun, taşımayanlara göre",
    "tags_list_pair": lambda f: f"'{f.label}' birleşimini birlikte taşıyan {f.n:,} oyun, benzerlerine göre",
    "categories_list_single": lambda f: f"'{f.label}' özelliğine sahip {f.n:,} oyun, sahip olmayanlara göre",
    "boolean_flag": lambda f: f"'{f.label}' özelliğine sahip {f.n:,} oyun, sahip olmayanlara göre",
    "price_band": lambda f: f"'{f.label}' fiyat bandındaki {f.n:,} oyun, diğer bantlara göre",
    "numeric_split": lambda f: f"{plain_language_condition(f.label)} ({f.n:,} oyun), sağlamayanlara göre",
    "entity_repeat": lambda f: f"{f.n:,} tekrar-stüdyonun sonraki oyunları, ilk oyunlarına göre",
    "default": lambda f: f"'{f.label}' grubundaki {f.n:,} oyun, karşılaştırma grubuna göre",
}


def _template_key_for_family(family: str) -> str:
    """Finding.family (örn. 'tags_list_single', 'categories_list_pair',
    'achievements_split') değerinden en uygun şablon anahtarını bulur.
    """
    if family.endswith("_single") and "tags" in family:
        return "tags_list_single"
    if family.endswith("_pair"):
        return "tags_list_pair"
    if family == "categories_list_single":
        return "categories_list_single"
    if family == "boolean_flag":
        return "boolean_flag"
    if family == "price_band":
        return "price_band"
    if family.endswith("_split"):
        return "numeric_split"
    if family == "entity_repeat":
        return "entity_repeat"
    if family == "temporal_trend":
        return "temporal_trend"
    return "default"


def render_claim(finding: Finding) -> str:
    """Bir Finding'i tek bir kanıta-bağlı, GÜNDELİK dilde cümleye çevirir.

    KURAL (bkz. plan): şablon seçimi finding.direction'a göre yapılır (veri
    tersine dönerse cümle de döner); her sayı finding'in kendi alanından
    gelir, serbest metin YOK. İstatistiksel jargon (etki büyüklüğü, güven
    aralığı, p/q-değeri, percentile) cümlede HİÇ geçmez — bunlar
    findings.json'un `evidence` alanında ayrıca duruyor.
    """
    key = _template_key_for_family(finding.family)

    if key == "temporal_trend":
        # GA/etki içermez — bu aile bootstrap uygulamıyor (effect_ci her
        # zaman NaN, bkz. families/temporal.py). "Farkını açıyor/kaybediyor"
        # zaten yön+büyüklük taşıyan gündelik bir ifade.
        verb = "farkını pazara karşı açıyor" if finding.direction == "positive" else "farkını pazara karşı kaybediyor"
        return f"'{finding.label}' grubundaki {finding.n:,} oyun, pazarın genel trendine göre zamanla {verb}."

    subject_fn = _SUBJECT_BUILDERS.get(key, _SUBJECT_BUILDERS["default"])
    subject = subject_fn(finding)
    gap_desc = plain_language_gap(finding.group_median, finding.baseline_median)

    return f"{subject} {gap_desc} ({finding.n:,} oyun üzerinden doğrulandı)."


def contains_forbidden_words(text: str) -> list[str]:
    """Metinde yasak kelimelerden hangileri geçiyor — test ve içerik denetimi için."""
    lowered = text.lower()
    return [w for w in FORBIDDEN_WORDS if w in lowered]
