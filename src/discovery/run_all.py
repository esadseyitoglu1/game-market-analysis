"""Discovery — Tüm Aileleri Birlikte Çalıştıran Orkestratör

NEDEN BU DOSYA VAR (bkz. plan — "SONRAKİ OTURUM İÇİN KALAN İŞ", madde 3):
Adım 3 ve 5'te her aile (tag_single, tag_pair, numeric_split, boolean_flag,
studio_repeat, temporal) AYRI AYRI test edildi, her biri kendi evaluate_batch
çağrısıyla kendi BH-FDR düzeltmesini uyguladı. Ama BH-FDR'nin gücü TÜM test
grubunu BİRLİKTE görmesinden gelir (bkz. gate.py:benjamini_hochberg docstring'i)
— ayrı ayrı çalıştırmak, her ailenin kendi küçük test grubunda daha gevşek bir
q-değeri eşiğine sahip olması demek. Bu dosya TÜM adayları TEK BİR HAVUZDA
toplayıp BH-FDR'yi bir kez, hepsine birden uyguluyor.

Bu aynı zamanda kullanıcının "sistem kendi kendine zibilyon insight üretsin"
isteğinin (bkz. plan Context bölümü) somut karşılığı — artık tek bir
run_discovery() çağrısı yüzlerce hipotezi tarayıp gate'ten geçenleri
findings.json'a yazıyor.
"""

import logging
import os
from pathlib import Path

from src.metrics import load_universe, engaged_universe
from src.discovery.base import Finding
from src.discovery.gate import evaluate_batch
from src.discovery.generators import (
    generate_categorical_group_hypotheses,
    generate_pairwise_hypotheses,
    generate_numeric_split_hypotheses,
    generate_boolean_flag_hypotheses,
    generate_price_band_hypotheses,
)
from src.discovery.families.studio_repeat import test_studio_repeat
from src.discovery.families.temporal import test_temporal_trend
from src.discovery.families.quality_cliff import test_cliff_at_80, test_quality_trap
from src.narrative.chart_selector import render_chart_for_finding
from src.contracts import write_findings_contract, select_top_findings, attach_alternatives

log = logging.getLogger(__name__)

INSIGHTS_DIR = Path(__file__).resolve().parent.parent.parent / "outputs" / "insights"
HISTORY_FILE = INSIGHTS_DIR / "finding_history.txt"
HISTORY_RESET_THRESHOLD = 5  # taze bulgu sayısı bunun altına düşerse hafıza sıfırlanır

# NOT (2026-08-04): "median_playtime_forever" bilerek burada YOK.
# average_playtime_forever > 0 ve median_playtime_forever > 0 neredeyse HER
# ZAMAN aynı oyun kümesini seçiyor (doğrulandı: engaged_universe'de ikisi de
# birebir aynı 4011 oyun) — bir oyunun ortalama oynanma süresi 0'dan büyükse
# medyanı da öyle olur, istatistiksel olarak eş anlamlı iki kolon. İkisini
# birden taramak select_top_findings'e neredeyse birebir aynı cümleyi iki kez
# "farklı bulgu" gibi sunma riski taşıyordu (canlı n8n testinde görüldü —
# iki ayrı video script'i, %90 aynı içerik). average_playtime_forever
# temsilci olarak bırakıldı (playtime ailesinin daha yaygın kullanılan alanı).
NUMERIC_COLUMNS = ["achievements", "dlc_count", "average_playtime_forever",
                    "required_age", "discount", "peak_ccu", "metacritic_score"]
BOOLEAN_COLUMNS = ["windows", "mac", "linux"]

# temporal_trend ailesi için taranacak popüler tag'ler — tüm tag'leri taramak
# yerine (yüzlerce Spearman testi + çoklu-karşılaştırma riski büyür) en sık
# geçen sabit bir liste kullanılıyor. Bu liste feature_registry.IGNORE_VALUES
# ile çakışmayan, gerçek tür/mekanik etiketlerinden oluşuyor.
TEMPORAL_CANDIDATE_TAGS = [
    "Roguelike", "Metroidvania", "City Builder", "Visual Novel",
    "Top-Down Shooter", "Survival", "Puzzle", "Battle Royale",
    "Tower Defense", "Zombies", "Deck Building", "Bullet Hell",
]


def _load_history() -> set[str]:
    if not HISTORY_FILE.exists():
        return set()
    return set(line.strip() for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines() if line.strip())


def _save_history(labels: list[str]) -> None:
    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        for label in labels:
            f.write(label + "\n")


def collect_all_findings(snapshot: str = "march2025") -> tuple[list[Finding], int]:
    """Tüm hipotez ailelerini üretir, TEK bir BH-FDR havuzunda değerlendirir.

    Döndürür: (findings, engaged_universe_büyüklüğü)
    """
    df = load_universe(snapshot)
    universe = engaged_universe(df).reset_index(drop=True)
    values = universe["visibility_pct"].values
    n_universe = len(universe)

    # --- 1. Batch-uyumlu aileler: tek evren, tek values dizisi, TEK BH-FDR havuzu ---
    all_hypotheses = []
    all_hypotheses += generate_categorical_group_hypotheses(universe, "tags_list", min_count=50)
    # top_n 40'tan 100'e çıkarıldı (2026-08-06, bkz. plan "alternatives"
    # özelliği) — 40'ta orta-popülerlikte tag'ler (ör. "Bullet Hell", rank 84)
    # hiç kombinasyon havuzuna girmiyordu, bu yüzden o tag'in tekil bulgusuna
    # eşlik edecek "birlikte kullan" önerisi bulunamıyordu. 100 hem Bullet
    # Hell'i kapsıyor hem hesaplama süresini makul tutuyor (~6x kombinasyon
    # adayı, ama gate.py çoğunu min_count'ta eliyor).
    all_hypotheses += generate_pairwise_hypotheses(universe, "tags_list", top_n=100, min_count=30)
    # categories_list = oyun modu/platform özellikleri (Co-op, VR Only,
    # Remote Play...) — tags_list'ten AYRI bir kolon, ikisi de generic
    # jeneratörü çağırıyor (bkz. plan Adım A: prototiple 10 bulgu doğrulandı,
    # hepsi aksiyona dönüşen özellik kararları).
    all_hypotheses += generate_categorical_group_hypotheses(universe, "categories_list", min_count=100)
    all_hypotheses += generate_price_band_hypotheses(universe, "price", min_count=100)
    for col in NUMERIC_COLUMNS:
        all_hypotheses += generate_numeric_split_hypotheses(universe, col, min_count=100)
    all_hypotheses += generate_boolean_flag_hypotheses(universe, BOOLEAN_COLUMNS, min_count=100)

    log.info(f"  Toplam {len(all_hypotheses)} hipotez üretildi, tek BH-FDR havuzunda değerlendiriliyor...")
    batch_findings = evaluate_batch(all_hypotheses, values, min_n=30)
    log.info(f"  Batch ailelerden {len(batch_findings)} bulgu gate'i geçti")

    # --- 2. Özel evrenli aileler (kendi baseline'ları farklı, batch'e giremez) ---
    special_findings = []

    studio_finding = test_studio_repeat(universe, "developers_list", min_games=2, min_n=50)
    if studio_finding:
        special_findings.append(studio_finding)

    for tag in TEMPORAL_CANDIDATE_TAGS:
        indie = df[df["is_indie"]]
        trend_finding = test_temporal_trend(indie, tag)
        if trend_finding:
            special_findings.append(trend_finding)

    cliff_finding = test_cliff_at_80(df)
    if cliff_finding:
        special_findings.append(cliff_finding)

    trap_finding = test_quality_trap(df)
    if trap_finding:
        special_findings.append(trap_finding)

    log.info(f"  Özel ailelerden (studio_repeat/temporal/quality_cliff) {len(special_findings)} bulgu geçti")

    return batch_findings + special_findings, n_universe


def run_discovery(snapshot: str = "march2025") -> Path:
    """Tüm keşif motorunu çalıştırır, hafıza mekanizmasını uygular, LLM'e
    gidecek bulguların grafiklerini üretir ve findings.json yazar.

    Hafıza mekanizması eski anomaly_detector.py'deki used_tags.txt ile AYNI
    mantık (bkz. o dosyadaki NOT) ama artık tag yerine Finding.label bazlı —
    çünkü artık tag-dışı bulgular da var (numeric_split, studio_repeat, temporal).

    GRAFİK ÜRETİMİ (bkz. plan — kullanıcının isteği: "bu içeriği destekleyecek
    grafik tarzı şeyler de üretmeli"): chart_selector.py zaten yazılmıştı ama
    hiçbir yerden çağrılmıyordu — findings.json'a chart_path hiç girmiyordu,
    n8n'e giden video script'lerinin hiçbir görseli yoktu. Burada SADECE
    LLM'e gidecek (en fazla 5) bulgu için grafik üretiliyor — 277 bulgunun
    hepsi için değil, çünkü her grafik matplotlib çizimi gerektiriyor ve
    gereksiz 272 dosya üretmenin bir faydası yok.
    """
    all_findings, n_universe = collect_all_findings(snapshot)

    used_labels = _load_history()
    fresh = [f for f in all_findings if f.label not in used_labels]

    if len(fresh) < HISTORY_RESET_THRESHOLD:
        log.info(f"  Taze bulgu sayısı ({len(fresh)}) eşiğin altında, hafıza sıfırlanıyor.")
        if HISTORY_FILE.exists():
            os.remove(HISTORY_FILE)
        fresh = all_findings

    # LLM'e gidecek bulguları ÖNCE seç (deterministik, en yüksek |effect|),
    # SONRA sadece bunlar için grafik üret — write_findings_contract zaten
    # aynı seçimi kendi içinde tekrar yapıyor (select_top_findings saf/yan
    # etkisiz bir fonksiyon, aynı girdide her zaman aynı 5'i seçer), bu yüzden
    # burada üretilen chart_path'lerin contract'a giden Finding'lerle
    # eşleştiğinden emin olabiliyoruz.
    to_chart = select_top_findings(fresh)

    # 2026-08-07 DÜZELTİLDİ (canlı testte bulunan bug): attach_alternatives
    # grafik üretiminden ÖNCE çağrılmalı — chart_trend_line, finding.alternatives
    # doluysa ikinci bir panel çiziyor (bkz. chart_selector.py). Eskiden bu
    # sıralama tersti: grafik önce çizilip (alternatives hâlâ boşken) sonra
    # write_findings_contract() içinde attach_alternatives çağrılıyordu —
    # findings.json'a doğru "alternatives" verisi giriyordu ama GRAFİK hep
    # tek panelli kalıyordu, çünkü zaten diskteki PNG'ye yazılmıştı.
    attach_alternatives(to_chart, fresh)

    log.info(f"  {len(to_chart)} bulgu için grafik üretiliyor...")
    for finding in to_chart:
        render_chart_for_finding(finding)

    path = write_findings_contract(fresh, universe_n=n_universe, snapshot=snapshot)

    # findings.json'a GİDEN bulguların etiketlerini hafızaya yaz — sadece
    # görülenler tekrar önerilmesin.
    _save_history([f.label for f in to_chart])

    return path


def run(snapshot: str = "march2025"):
    """src/main.py'nin çağıracağı giriş noktası (eski anomaly_detector.run ile
    aynı imza)."""
    log.info("Discovery motoru başlatılıyor (run_all)...")
    path = run_discovery(snapshot)
    log.info(f"  Tamamlandı -> {path}")
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run()
