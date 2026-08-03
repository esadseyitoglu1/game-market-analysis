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
"""

from src.discovery.base import Finding

# Nedensellik/abartı iması taşıyan, kanıtlanmamış iddialara yol açan kelimeler.
# tests/test_narrative.py bunları üretilen metinde arar — biri geçerse test kırılır.
FORBIDDEN_WORDS = [
    "katlar", "patlar", "kesinlikle", "her zaman", "garanti",
    "altın maden", "şaheser", "mucize", "asla başarısız",
    "kesin", "mutlaka", "hep",
]

TEMPLATES: dict[str, dict[str, str]] = {
    "tags_list_single": {
        "positive": (
            "'{label}' etiketini taşıyan {n} indie oyun, taşımayanlara göre "
            "daha yüksek görünürlükte (medyan percentile {group_median:.2f} vs "
            "{baseline_median:.2f}, etki büyüklüğü {effect:+.2f}, "
            "%95 güven aralığı [{ci_lo:+.2f}, {ci_hi:+.2f}])."
        ),
        "negative": (
            "'{label}' etiketini taşıyan {n} indie oyun, taşımayanlara göre "
            "daha DÜŞÜK görünürlükte (medyan percentile {group_median:.2f} vs "
            "{baseline_median:.2f}, etki büyüklüğü {effect:+.2f}, "
            "%95 güven aralığı [{ci_lo:+.2f}, {ci_hi:+.2f}])."
        ),
    },
    "tags_list_pair": {
        "positive": (
            "'{label}' birleşimini birlikte taşıyan {n} oyun, benzerlerine göre "
            "daha yüksek görünürlük diliminde (etki {effect:+.2f}, "
            "%95 GA [{ci_lo:+.2f}, {ci_hi:+.2f}])."
        ),
        "negative": (
            "'{label}' birleşimini birlikte taşıyan {n} oyun, benzerlerine göre "
            "daha DÜŞÜK görünürlük diliminde (etki {effect:+.2f}, "
            "%95 GA [{ci_lo:+.2f}, {ci_hi:+.2f}])."
        ),
    },
    "boolean_flag": {
        "positive": (
            "'{label}' özelliğine sahip {n} oyun, sahip olmayanlara göre daha "
            "yüksek görünürlükte (etki {effect:+.2f}, %95 GA [{ci_lo:+.2f}, {ci_hi:+.2f}])."
        ),
        "negative": (
            "'{label}' özelliğine sahip {n} oyun, sahip olmayanlara göre daha "
            "DÜŞÜK görünürlükte (etki {effect:+.2f}, %95 GA [{ci_lo:+.2f}, {ci_hi:+.2f}])."
        ),
    },
    "numeric_split": {
        "positive": (
            "'{label}' koşulunu sağlayan {n} oyun, sağlamayanlara göre daha "
            "yüksek görünürlükte (etki {effect:+.2f}, %95 GA [{ci_lo:+.2f}, {ci_hi:+.2f}])."
        ),
        "negative": (
            "'{label}' koşulunu sağlayan {n} oyun, sağlamayanlara göre daha "
            "DÜŞÜK görünürlükte (etki {effect:+.2f}, %95 GA [{ci_lo:+.2f}, {ci_hi:+.2f}])."
        ),
    },
    "entity_repeat": {
        "positive": (
            "{n} tekrar-stüdyonun sonraki oyunları, ilk oyunlarına göre daha "
            "yüksek görünürlükte (etki {effect:+.2f}, %95 GA [{ci_lo:+.2f}, {ci_hi:+.2f}])."
        ),
        "negative": (
            "{n} tekrar-stüdyonun sonraki oyunları, ilk oyunlarına göre daha "
            "DÜŞÜK görünürlükte (etki {effect:+.2f}, %95 GA [{ci_lo:+.2f}, {ci_hi:+.2f}])."
        ),
    },
    # Tag-tek/tag-çift/vb. dışında kalan aileler için genel şablon (fallback)
    "default": {
        "positive": (
            "'{label}' grubundaki {n} oyun, karşılaştırma grubuna göre daha "
            "yüksek görünürlükte (etki {effect:+.2f}, %95 GA [{ci_lo:+.2f}, {ci_hi:+.2f}])."
        ),
        "negative": (
            "'{label}' grubundaki {n} oyun, karşılaştırma grubuna göre daha "
            "DÜŞÜK görünürlükte (etki {effect:+.2f}, %95 GA [{ci_lo:+.2f}, {ci_hi:+.2f}])."
        ),
    },
}


def _template_key_for_family(family: str) -> str:
    """Finding.family (örn. 'tags_list_single', 'categories_list_pair',
    'achievements_split') değerinden en uygun şablon anahtarını bulur.
    """
    if family.endswith("_single") and "tags" in family:
        return "tags_list_single"
    if family.endswith("_pair"):
        return "tags_list_pair"
    if family == "boolean_flag":
        return "boolean_flag"
    if family.endswith("_split"):
        return "numeric_split"
    if family == "entity_repeat":
        return "entity_repeat"
    return "default"


def render_claim(finding: Finding) -> str:
    """Bir Finding'i tek bir kanıta-bağlı cümleye çevirir.

    KURAL (bkz. plan): şablon seçimi finding.direction'a göre yapılır (veri
    tersine dönerse cümle de döner); her sayı finding'in kendi alanından
    f-string ile enjekte edilir, serbest metin YOK.
    """
    key = _template_key_for_family(finding.family)
    template_group = TEMPLATES.get(key, TEMPLATES["default"])
    template = template_group[finding.direction]

    return template.format(
        label=finding.label,
        n=finding.n,
        effect=finding.effect,
        ci_lo=finding.effect_ci[0],
        ci_hi=finding.effect_ci[1],
        group_median=finding.group_median,
        baseline_median=finding.baseline_median,
    )


def contains_forbidden_words(text: str) -> list[str]:
    """Metinde yasak kelimelerden hangileri geçiyor — test ve içerik denetimi için."""
    lowered = text.lower()
    return [w for w in FORBIDDEN_WORDS if w in lowered]
