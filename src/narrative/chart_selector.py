"""Narrative — Chart Selector (Bulgu Tipine Göre Otomatik Grafik Seçimi)

NEDEN BU DOSYA VAR (bkz. plan — "Mimari — GENİŞLETİLMİŞ", kullanıcının isteği):
"Bu sonuçları ortaya çıkarırken de buna uygun içerik ve bu içeriği destekleyecek
grafik tarzı şeyler de üretmeli." Eski sistemde her insight için grafik dosya
adı ELLE yazılmıştı ve visualizer'la senkron kalması insana bağlıydı — bu yüzden
`coop_multiplier.png` hiç üretilmediği halde rapor ona işaret ediyordu (bkz.
Context bölümü). Burada bu bağ PROGRAMATIK: her `Finding`, kendi `chart_hint`
alanına göre otomatik bir çizim fonksiyonuna yönlendirilir ve üretilen dosyanın
yolu `Finding.chart_path`'e geri yazılır — ikisi asla birbirinden kopamaz.

Görsel STİL SİSTEMİ (renk paleti, dark tema, `_note()` kaynak damgası)
visualizer.py'den AYNEN alınıyor — sadece hangi verinin hangi çizim
fonksiyonuna gideceğine bu modül karar veriyor.
"""

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from src.discovery.base import Finding

log = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "outputs" / "charts"

# visualizer.py ile BİREBİR AYNI renk paleti — iki modülün ürettiği grafikler
# aynı sistemin parçası gibi görünmeli (bkz. visualizer.py:34-46).
C = {
    "bg":      "#0D1117",
    "panel":   "#161B22",
    "grid":    "#21262D",
    "text":    "#E6EDF3",
    "muted":   "#8B949E",
    "blue":    "#4FC3F7",
    "green":   "#56D364",
    "yellow":  "#E3B341",
    "red":     "#F85149",
    "purple":  "#BC8CFF",
    "gray":    "#30363D",
}


def _style():
    """visualizer.py:_style() ile aynı — dark tema rcParams ayarı."""
    plt.rcParams.update({
        "figure.facecolor": C["bg"],   "axes.facecolor":   C["bg"],
        "axes.edgecolor":   C["grid"], "axes.labelcolor":  C["text"],
        "axes.titlecolor":  C["text"], "xtick.color":      C["text"],
        "ytick.color":      C["text"], "grid.color":       C["grid"],
        "grid.linewidth":   0.7,       "text.color":       C["text"],
        "font.family":      "sans-serif", "font.size":     11,
        "axes.titlesize":   14,        "axes.labelsize":   11,
        "figure.dpi":       150,
    })


def _save(fig, name: str) -> Path:
    """visualizer.py:_save() ile aynı mantık."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUTPUT_DIR / name
    fig.savefig(p, bbox_inches="tight", facecolor=C["bg"])
    plt.close(fig)
    return p


def _note(ax, text: str):
    """visualizer.py:_note() ile aynı — zorunlu kaynak/metodoloji damgası."""
    full_text = (
        f"{text}\n"
        "Veri: Kaggle (artermiloff/steam-games-dataset, Mart 2025, ~90k oyun) + SteamSpy API  |  "
        "Metrik: yıl-içi log-review percentile (visibility_pct) — owners KULLANILMADI."
    )
    ax.text(0.01, -0.14, full_text, transform=ax.transAxes,
            fontsize=7.5, color=C["muted"], va="top", wrap=True)


def _safe_filename(label: str) -> str:
    """Finding.label'dan güvenli bir dosya adı üretir (boşluk/özel karakter temizliği)."""
    safe = "".join(c if c.isalnum() else "_" for c in label.lower())
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_")[:60]


def chart_bar_comparison(finding: Finding) -> Path:
    """tag_single / tag_pair / boolean_flag bulguları için: grup vs baseline
    medyan karşılaştırması, tek bir yatay bar çifti.
    """
    _style()
    fig, ax = plt.subplots(figsize=(8, 3.5))

    labels = [finding.label, "Diğerleri (baseline)"]
    values = [finding.group_median, finding.baseline_median]
    colors = [C["green"] if finding.direction == "positive" else C["red"], C["gray"]]

    bars = ax.barh(labels, values, color=colors, height=0.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2,
                 f"{val:.2f}", va="center", color=C["text"], fontsize=10)

    ax.set_xlabel("Görünürlük percentile (visibility_pct, medyan)")
    ax.set_title(f"{finding.label}\netki={finding.effect:+.2f}  n={finding.n}  q={finding.q_value:.4f}")
    ax.set_xlim(0, 1.1)
    _note(ax, f"n={finding.n} (grup) / n={finding.n_baseline} (baseline)  |  Mann-Whitney U + BH-FDR + bootstrap %95 GA ile doğrulandı")

    return _save(fig, f"finding_{_safe_filename(finding.label)}_bar.png")


def chart_box_plot(finding: Finding) -> Path:
    """numeric_split bulguları için (achievements, playtime, vb.): box plot
    ile iki grubun dağılım karşılaştırması.

    NOT: Finding nesnesi ham dağılımı taşımıyor (sadece medyan/etki), bu yüzden
    burada sentetik/özet bir gösterim kullanılıyor — gerçek ham dağılımlı box
    plot için chart_selector'ı çağıran koda `raw_group`/`raw_baseline`
    array'lerini de geçirmek gerekir (bkz. Adım 5 entegrasyonu).
    """
    _style()
    fig, ax = plt.subplots(figsize=(6, 4))

    color = C["green"] if finding.direction == "positive" else C["red"]
    ax.bar(["Grup\n(koşulu sağlayan)", "Baseline\n(sağlamayan)"],
           [finding.group_median, finding.baseline_median],
           color=[color, C["gray"]], width=0.5)

    ax.set_ylabel("Görünürlük percentile (medyan)")
    ax.set_title(f"{finding.label}\netki={finding.effect:+.2f}  n={finding.n}")
    _note(ax, f"n={finding.n} (grup) / n={finding.n_baseline} (baseline)")

    return _save(fig, f"finding_{_safe_filename(finding.label)}_box.png")


def chart_before_after(finding: Finding) -> Path:
    """entity_repeat bulguları için (stüdyonun ilk oyunu vs sonrakiler):
    öncesi/sonrası çizgi grafiği.
    """
    _style()
    fig, ax = plt.subplots(figsize=(6, 4))

    color = C["green"] if finding.direction == "positive" else C["red"]
    x = ["İlk oyun", "Sonraki oyunlar"]
    y = [finding.baseline_median, finding.group_median]

    ax.plot(x, y, marker="o", markersize=10, linewidth=2, color=color)
    for xi, yi in zip(x, y):
        ax.text(xi, yi + 0.02, f"{yi:.2f}", ha="center", color=C["text"])

    ax.set_ylabel("Görünürlük percentile (medyan)")
    ax.set_title(f"{finding.label}\netki={finding.effect:+.2f}  n={finding.n}")
    ax.set_ylim(0, 1.1)
    _note(ax, f"n={finding.n} tekrar-stüdyo karşılaştırması")

    return _save(fig, f"finding_{_safe_filename(finding.label)}_before_after.png")


def chart_trend_line(finding: Finding) -> Path:
    """temporal bulguları için: yıllara göre trend çizgisi.

    NOT: Finding nesnesi yıl-bazlı seriyi taşımıyor (sadece özet istatistik).
    Bu fonksiyon families/temporal.py tarafından `evidence` alanına konan
    yıllık seriyi kullanır (bkz. Adım 5).
    """
    _style()
    fig, ax = plt.subplots(figsize=(7, 4))

    yearly = finding.evidence.get("yearly_series", {})
    if yearly:
        years = sorted(yearly.keys())
        vals = [yearly[y] for y in years]
        color = C["green"] if finding.direction == "positive" else C["red"]
        ax.plot(years, vals, marker="o", color=color, linewidth=2)
    else:
        ax.text(0.5, 0.5, "Yıllık seri verisi yok", ha="center", va="center",
                transform=ax.transAxes, color=C["muted"])

    ax.set_xlabel("Yıl")
    ax.set_ylabel("Medyan görünürlük / kalite")
    ax.set_title(f"{finding.label}\netki={finding.effect:+.2f}  n={finding.n}")
    _note(ax, f"n={finding.n}")

    return _save(fig, f"finding_{_safe_filename(finding.label)}_trend.png")


def chart_scatter_gap(finding: Finding) -> Path:
    """critic_gap bulguları için: metacritic vs review_score scatter (kopuş
    gösterimi). visualizer.py'nin mevcut chart_critics_vs_players'ına benzer
    ama tek bir Finding etrafında kurulmuş minimal versiyon.
    """
    _style()
    fig, ax = plt.subplots(figsize=(6, 6))

    ax.axline((0, 0), slope=1, color=C["gray"], linestyle="--", linewidth=1)
    color = C["green"] if finding.direction == "positive" else C["red"]
    ax.scatter([finding.baseline_median], [finding.group_median],
               s=200, color=color, zorder=3)
    ax.annotate(finding.label, (finding.baseline_median, finding.group_median),
                textcoords="offset points", xytext=(10, 10), color=C["text"])

    ax.set_xlabel("Metacritic (baseline)")
    ax.set_ylabel("Steam review_score (grup)")
    ax.set_title(f"Eleştirmen-Oyuncu Kopuşu\netki={finding.effect:+.2f}  n={finding.n}")
    _note(ax, f"n={finding.n}")

    return _save(fig, f"finding_{_safe_filename(finding.label)}_scatter.png")


# chart_hint -> çizim fonksiyonu eşlemesi. Yeni bir chart_hint eklemek için
# sadece burada bir satır eklemek yeterli — generators.py veya narrative/render.py
# hiçbir şey bilmez, sadece "chart_hint" string'ini taşır.
CHART_FUNCTIONS = {
    "bar_comparison": chart_bar_comparison,
    "box_plot": chart_box_plot,
    "before_after": chart_before_after,
    "trend_line": chart_trend_line,
    "scatter_gap": chart_scatter_gap,
}


def render_chart_for_finding(finding: Finding) -> Finding:
    """Finding.chart_hint'e bakıp uygun grafiği üretir, Finding.chart_path'i
    doldurur ve AYNI finding nesnesini döndürür (in-place güncelleme + dönüş,
    çağıran kodun akışını kolaylaştırmak için).

    chart_hint tanınmıyorsa veya boşsa, grafik ÜRETİLMEZ — chart_path None
    kalır. Bu, "her bulgu mutlaka bir grafik almalı" varsayımını dayatmaz;
    bazı bulgular (ör. tek satırlık bir istatistik) grafiksiz de anlamlı olabilir.
    """
    hint = finding.chart_hint
    fn = CHART_FUNCTIONS.get(hint)
    if fn is None:
        log.info(f"  chart_selector: '{finding.label}' için chart_hint='{hint}' tanınmıyor, grafik atlandı")
        return finding

    try:
        path = fn(finding)
        finding.chart_path = str(path.relative_to(path.parent.parent.parent))
        log.info(f"  chart_selector: '{finding.label}' -> {path.name}")
    except Exception as e:
        log.warning(f"  chart_selector: '{finding.label}' için grafik üretilemedi: {e}")
    return finding
