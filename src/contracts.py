"""Contracts — n8n/LLM'e Giden Çıktı Sözleşmesi

Bu dosya, gate.py'den geçmiş Finding'leri n8n'in okuyacağı `findings.json`
dosyasına yazar. Eski sistemdeki `autonomous_anomalies.json` (bkz. Context
bölümü — 3 alanlı, kanıtsız şema: type/tag/finding) yerine gelir.

ŞEMA FARKI (eskiye göre):
  Eski:  {"type": ..., "tag": ..., "finding": "...", "optimal_price_band": ...,
          "median_owners": ...}  <- optimal_price_band ve median_owners
          KANITSIZDI (bkz. Context — 60-80. persentil, satışla ilgisi yok;
          owners kova-ortası, çözünürlüksüz).
  Yeni:  her finding artık n, effect, effect_ci, q_value, confidence taşıyor
         — LLM'in HERHANGİ bir sayıyı uydurmasına gerek kalmıyor, hepsi hazır.

LLM'İN UYDURMASINI ENGELLEYEN MEKANİZMALAR (bkz. plan):
  - En fazla 5 bulgu gönderilir (deterministik seçim — en yüksek |effect|).
  - Her bulguda `exemplars` (gerçek oyun adları) varsa dahil edilir.
  - `caveats` listesi her zaman dahil — "korelasyon nedensellik değildir" vb.
  - `universe` bilgisi (n, filtre, metrik tanımı) her zaman dahil.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from src.discovery.base import Finding
from src.narrative.render import render_findings

log = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "insights"

SCHEMA_VERSION = "2.0"
MAX_FINDINGS_FOR_LLM = 5

CAVEATS = [
    "Korelasyon, nedensellik değildir. Bir bulgunun 'X özelliği görünürlüğü artırıyor' "
    "demesi, X'i eklerseniz otomatik başarı gelir demek değildir.",
    "Owners (sahip sayısı) verisi KULLANILMADI — SteamSpy bu alanı kova/aralık "
    "formatında verir ve indie evreninin büyük kısmı tek kovaya düşer, çözünürlüksüzdür. "
    "Görünürlük metriği yerine review sayısının yıl-içi percentile'ı kullanıldı.",
    "Her bulgu istatistiksel bir geçitten (Mann-Whitney U + Benjamini-Hochberg FDR + "
    "etki büyüklüğü ≥0.20 + bootstrap %95 güven aralığı) geçmiştir, ama örneklem "
    "büyüklüğü küçük olan bulgularda (confidence='medium') temkinli dil kullanılmalıdır.",
]


def build_universe_metadata(n: int, min_reviews: int = 10,
                              year_range: tuple[int, int] = (2016, 2024)) -> dict:
    return {
        "n": n,
        "filter": f"indie, {year_range[0]}-{year_range[1]}, >={min_reviews} review",
        "metric": "yıl-içi log-review percentile (visibility_pct)",
    }


def select_top_findings(findings: list[Finding], max_n: int = MAX_FINDINGS_FOR_LLM) -> list[Finding]:
    """LLM'e gidecek en fazla max_n bulguyu DETERMİNİSTİK seçer — en yüksek
    |effect| büyüklüğüne göre sıralanır. Rastgelelik yok (eski sistemin
    seed'siz random.shuffle sorununun tekrarlanmaması için, bkz. Adım 0).
    """
    non_fragile = [f for f in findings if not f.fragile]
    ranked = sorted(non_fragile, key=lambda f: -abs(f.effect))
    return ranked[:max_n]


def write_findings_contract(all_findings: list[Finding], universe_n: int,
                              snapshot: str = "march2025") -> Path:
    """findings.json'u yazar — n8n'in okuyacağı tam kanıt sözleşmesi."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    top_findings = select_top_findings(all_findings)
    rendered = render_findings(top_findings)

    contract = {
        "run_id": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "schema_version": SCHEMA_VERSION,
        "snapshot": snapshot,
        "universe": build_universe_metadata(universe_n),
        "caveats": CAVEATS,
        "total_findings_discovered": len(all_findings),
        "total_findings_sent": len(rendered),
        "findings": rendered,
    }

    path = OUTPUT_DIR / "findings.json"
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    log.info(f"  findings.json yazıldı: {len(all_findings)} bulgudan {len(rendered)} tanesi LLM'e gönderiliyor -> {path}")
    return path
