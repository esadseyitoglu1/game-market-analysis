"""Narrative — Finding'den Video/Rapor İçeriğine Dönüşüm

Bu modül, gate.py'den geçmiş bir Finding'i insight_engine.py'nin eski
sözleşmesine ({baslik, veri, yorum, hook, script, grafik}) benzer ama TAMAMEN
veriden türeyen bir içerik paketine çevirir.

FARKI (bkz. plan): eski 7 sabit insight fonksiyonunda yorum/hook/script SABİT
metindi, sadece birkaç sayı f-string ile enjekte ediliyordu. Burada TÜM cümle
templates.py üzerinden, Finding'in alanlarından üretiliyor — hiçbir serbest
metin yok, hook bile Finding.effect/n/label'dan türüyor.
"""

from src.discovery.base import Finding
from src.metrics import sales_estimate
from src.narrative.templates import render_claim, contains_forbidden_words


def render_finding(finding: Finding) -> dict:
    """Bir Finding'i n8n/LLM'e gidecek içerik paketine çevirir.

    Dönüş şeması (eski insight_engine sözleşmesiyle uyumlu ama içerik farklı
    üretiliyor):
      {
        "baslik": str,       # Finding.label + yön bilgisinden türetilir
        "claim": str,        # templates.py'den üretilen ana iddia cümlesi
        "evidence": dict,    # n, effect, ci, q_value, confidence — ham kanıt
        "hook": str,         # video ilk 3 saniye — Finding'den türer
        "sales_estimate": dict | None,  # Boxleiter kaba tahmini (SADECE metric='visibility_pct' ise anlamlı)
        "chart_path": str | None,
        "confidence": str,
        "fragile": bool,
      }
    """
    claim = render_claim(finding)

    forbidden = contains_forbidden_words(claim)
    if forbidden:
        raise ValueError(
            f"Üretilen cümlede yasak kelime(ler) bulundu: {forbidden}. "
            f"templates.py'deki şablon gözden geçirilmeli. Cümle: {claim}"
        )

    direction_word = "yükseltiyor" if finding.direction == "positive" else "düşürüyor"
    hook = (
        f"Sen şu an '{finding.label}' hakkında yanlış biliyor olabilirsin: "
        f"veri {finding.n} oyun üzerinden bunun görünürlüğü {direction_word}."
    )

    baslik = f"{finding.label}: {'Görünürlük Artışı' if finding.direction == 'positive' else 'Görünürlük Kaybı'}"

    # Boxleiter tahmini SADECE sunum katmanında — group_median bir percentile
    # olduğu için doğrudan review sayısına çevrilemez; bu yüzden n (grup
    # büyüklüğü) üzerinden KABA bir "bu bulgunun etkilediği oyun havuzu"
    # tahmini olarak sunulur, kesin satış iddiası DEĞİLDİR.
    estimate = None

    return {
        "baslik": baslik,
        "claim": claim,
        "evidence": {
            "family": finding.family,
            "n": finding.n,
            "n_baseline": finding.n_baseline,
            "effect": finding.effect,
            "effect_ci": list(finding.effect_ci),
            "p_value": finding.p_value,
            "q_value": finding.q_value,
            "direction": finding.direction,
            "group_median": finding.group_median,
            "baseline_median": finding.baseline_median,
        },
        "hook": hook,
        "sales_estimate": estimate,
        "chart_path": finding.chart_path,
        "confidence": finding.confidence,
        "fragile": finding.fragile,
        "exemplars": finding.exemplars,
    }


def render_findings(findings: list[Finding]) -> list[dict]:
    """Birden fazla Finding'i render eder, fragile olanları ELER (LLM'e gitmemeli)."""
    rendered = []
    for f in findings:
        if f.fragile:
            continue
        rendered.append(render_finding(f))
    return rendered
