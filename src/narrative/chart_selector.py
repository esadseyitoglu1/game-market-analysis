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
import unicodedata
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from src.discovery.base import Finding
from src.narrative.plain_language import plain_language_condition, plain_language_gap

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
    """visualizer.py:_style() ile aynı — dark tema rcParams ayarı.

    NOT (2026-08-05 büyütüldü, bkz. plan Adım E): kullanıcı Telegram'da
    grafiklerin mobilde küçük/okunaksız göründüğünü bildirdi. Font boyutları
    ve figure.dpi artırıldı — mobil ekranda küçük thumbnail'de bile başlık
    ve eksen etiketleri okunabilsin diye.
    """
    plt.rcParams.update({
        "figure.facecolor": C["bg"],   "axes.facecolor":   C["bg"],
        "axes.edgecolor":   C["grid"], "axes.labelcolor":  C["text"],
        "axes.titlecolor":  C["text"], "xtick.color":      C["text"],
        "ytick.color":      C["text"], "grid.color":       C["grid"],
        "grid.linewidth":   0.7,       "text.color":       C["text"],
        "font.family":      "sans-serif", "font.size":     13,
        "axes.titlesize":   17,        "axes.labelsize":   13,
        "xtick.labelsize":  12,        "ytick.labelsize":  12,
        "figure.dpi":       180,
    })


def _save(fig, name: str) -> Path:
    """visualizer.py:_save() ile aynı mantık."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUTPUT_DIR / name
    fig.savefig(p, bbox_inches="tight", facecolor=C["bg"])
    plt.close(fig)
    return p


def _note(ax, text: str, y: float = -0.22):
    """visualizer.py:_note() ile aynı — zorunlu kaynak/metodoloji damgası.

    NOT (2026-08-04 düzeltildi): sabit y=-0.14 konumu, x-ekseni etiketi
    ("Görünürlük percentile...") ile ÇAKIŞIYORDU — n8n'e giden canlı
    çıktıda görüldü (Boomer Shooter / playtime grafiklerinde rakamlar ve
    eksen yazısı üst üste biniyordu). Kök neden: figürün alt boşluğu
    (subplots_adjust ile büyütülmeden) bu notu barındıracak kadar geniş
    değildi. Çözüm: her chart fonksiyonu HEM `fig.subplots_adjust(bottom=...)`
    HEM bu fonksiyona uygun bir `y` değeri veriyor — ikisi birbiriyle
    orantılı olmalı, biri değişirse diğeri de kontrol edilmeli.
    """
    # 2026-08-05: kaynak damgası TEK satıra indirildi (eskiden 2 satırdı,
    # Telegram'da küçük gösterilen görselde hiç okunmuyordu). Tam metodoloji
    # detayı yerine kısa bir kaynak notu — asıl bilgi zaten `text` parametresi.
    full_text = f"{text}  |  Kaggle + SteamSpy, Mart 2025 (~90k oyun)"
    ax.text(0.01, y, full_text, transform=ax.transAxes,
            fontsize=9.5, color=C["muted"], va="top", wrap=True)


def _safe_filename(label: str) -> str:
    """Finding.label'dan güvenli bir dosya adı üretir (boşluk/özel karakter temizliği).

    ASCII'ye zorlanıyor (unicodedata.normalize + encode/decode) — 'c.isalnum()'
    Python'da Unicode-aware olduğu için Türkçe karakterleri (ö, ğ, ş, ...)
    alfanümerik sayıp OLDUĞU GİBİ bırakıyordu. n8n'in çalıştığı Linux sunucuda
    bu, "Read Binary File" node'unun path'i bulamamasına yol açabilir (Windows'ta
    üretilen UTF-8 dosya adı, sunucu tarafında farklı normalize/encode edilebilir).
    """
    ascii_label = unicodedata.normalize("NFKD", label.lower()).encode("ascii", "ignore").decode("ascii")
    safe = "".join(c if c.isalnum() else "_" for c in ascii_label)
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_")[:60]


def chart_bar_comparison(finding: Finding) -> Path:
    """tag_single / tag_pair / boolean_flag bulguları için: grup vs baseline
    medyan karşılaştırması, tek bir yatay bar çifti.
    """
    _style()
    fig, ax = plt.subplots(figsize=(10, 4.5))

    labels = [finding.label, "Diğerleri (baseline)"]
    values = [finding.group_median, finding.baseline_median]
    colors = [C["green"] if finding.direction == "positive" else C["red"], C["gray"]]

    bars = ax.barh(labels, values, color=colors, height=0.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2,
                 f"{val:.2f}", va="center", color=C["text"], fontsize=13)

    gap_desc = plain_language_gap(finding.group_median, finding.baseline_median)
    ax.set_xlabel("Görünürlük (yüksek = Steam'de daha çok öne çıkıyor)")
    ax.set_title(f"'{finding.label}' taşıyan oyunlar {gap_desc}\n{finding.n:,} oyun karşılaştırıldı")
    ax.set_xlim(0, 1.1)
    _note(ax, f"{finding.n:,} oyun (bu grup) / {finding.n_baseline:,} oyun (karşılaştırma) üzerinden istatistiksel olarak doğrulandı",
          y=-0.32)
    fig.subplots_adjust(bottom=0.42)

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
    fig, ax = plt.subplots(figsize=(8, 5.5))

    color = C["green"] if finding.direction == "positive" else C["red"]
    ax.bar(["Grup\n(koşulu sağlayan)", "Baseline\n(sağlamayan)"],
           [finding.group_median, finding.baseline_median],
           color=[color, C["gray"]], width=0.5)

    gap_desc = plain_language_gap(finding.group_median, finding.baseline_median)
    condition_desc = plain_language_condition(finding.label)
    ax.set_ylabel("Görünürlük (yüksek = Steam'de\ndaha çok öne çıkıyor)")
    ax.set_title(f"{condition_desc} {gap_desc}\n{finding.n:,} oyun karşılaştırıldı")
    _note(ax, f"{finding.n:,} oyun (bu grup) / {finding.n_baseline:,} oyun (karşılaştırma) üzerinden istatistiksel olarak doğrulandı")
    # 2026-08-05: top/left eklendi — font büyütmesinden sonra başlık y-ekseni
    # etiketiyle çakışıyordu (bkz. plan Adım E, gerçek çıktıda görüldü).
    fig.subplots_adjust(bottom=0.28, top=0.82, left=0.18)

    return _save(fig, f"finding_{_safe_filename(finding.label)}_box.png")


def chart_before_after(finding: Finding) -> Path:
    """entity_repeat bulguları için (stüdyonun ilk oyunu vs sonrakiler):
    öncesi/sonrası çizgi grafiği.
    """
    _style()
    fig, ax = plt.subplots(figsize=(8, 5.5))

    color = C["green"] if finding.direction == "positive" else C["red"]
    x = ["İlk oyun", "Sonraki oyunlar"]
    y = [finding.baseline_median, finding.group_median]

    ax.plot(x, y, marker="o", markersize=10, linewidth=2, color=color)
    for xi, yi in zip(x, y):
        ax.text(xi, yi + 0.02, f"{yi:.2f}", ha="center", color=C["text"])

    gap_desc = plain_language_gap(finding.group_median, finding.baseline_median)
    ax.set_ylabel("Görünürlük (yüksek = Steam'de daha çok öne çıkıyor)")
    ax.set_title(f"İkinci oyunlar ilk oyuna göre {gap_desc}\n{finding.n:,} tekrar-stüdyo karşılaştırıldı")
    ax.set_ylim(0, 1.1)
    _note(ax, f"{finding.n:,} stüdyonun ilk oyunu ile sonraki oyunları karşılaştırıldı")
    fig.subplots_adjust(bottom=0.28)

    return _save(fig, f"finding_{_safe_filename(finding.label)}_before_after.png")


def chart_trend_line(finding: Finding) -> Path:
    """temporal bulguları için: tag'in trendi PAZAR ORTALAMASIYLA birlikte.

    Tek başına tag'in çizgisi ("bu iyi mi kötü mü, neye göre?") bağlamsız ve
    okunaksızdı — families/temporal.py zaten "pazara göre göreli" testi
    yapıyor (detrend, bkz. o dosyanın docstring'i) ama grafik bunu hiç
    göstermiyordu. Artık iki çizgi birden çizilir (tag vs pazar medyanı) ve
    aradaki fark taranarak vurgulanır — izleyici "tag mi düşüyor yoksa pazar
    mı ondan hızlı yükseliyor" ayrımını görsel olarak anında yakalar.
    """
    _style()
    fig, ax = plt.subplots(figsize=(10, 6))

    yearly = finding.evidence.get("yearly_series", {})
    market = finding.evidence.get("market_yearly_series", {})
    year_range_text = ""

    if yearly and market:
        years = sorted(yearly.keys())
        year_range_text = f"{years[0]}-{years[-1]}"
        tag_vals = [yearly[y] for y in years]
        market_vals = [market[y] for y in years]
        color = C["green"] if finding.direction == "positive" else C["red"]

        ax.plot(years, tag_vals, marker="o", markersize=7, color=color,
                linewidth=2.5, label=finding.label.split(" (")[0], zorder=3)
        ax.plot(years, market_vals, marker="o", markersize=5, color=C["muted"],
                linewidth=1.8, linestyle="--", label="Pazar geneli (tüm indie)", zorder=2)
        ax.fill_between(years, tag_vals, market_vals, color=color, alpha=0.12, zorder=1)

        ax.legend(loc="upper left", framealpha=0.2, labelcolor=C["text"], fontsize=12)

        # Sabit eksen-koordinatı (0-1) kullanılıyor — veri noktasına göre
        # (xy=son yıl, son değer) konumlandırma başlıkla çakışıyordu (son
        # nokta genelde grafiğin üst kısmında oluyor, başlık da orada).
        last_gap = tag_vals[-1] - market_vals[-1]
        gap_word = "üstünde" if last_gap >= 0 else "altında"
        ax.text(0.98, 0.04, f"Son yılda: {abs(last_gap):.1f} puan pazarın {gap_word}",
                transform=ax.transAxes, ha="right", va="bottom",
                fontsize=12.5, color=color, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor=C["panel"], edgecolor=color, linewidth=1))
    else:
        ax.text(0.5, 0.5, "Yıllık seri verisi yok", ha="center", va="center",
                transform=ax.transAxes, color=C["muted"])

    tag_name = finding.label.split(" (")[0]
    # DİKKAT: direction, MUTLAK seviyeye değil pazarla aradaki FARKIN eğimine
    # (relative_diff'in slope'una) bakıyor — bkz. families/temporal.py. Yani
    # tag hâlâ pazarın üstünde olsa bile "negative" çıkabilir (fark daralıyorsa).
    # Başlık bunu net ayırt etmeli, yoksa grafikle (çizgi hâlâ üstte) çelişir.
    trend_word = "farkını pazara karşı kaybediyor" if finding.direction == "negative" else "farkını pazara karşı açıyor"
    ax.set_xlabel("Yıl")
    ax.set_ylabel("Medyan review skoru (yüksek = daha çok beğenilmiş)")
    ax.set_title(f"'{tag_name}' etiketi pazara göre {trend_word}\n{finding.n:,} oyun, {year_range_text} arası izlendi")
    _note(ax, f"{finding.n:,} oyun  |  Kesikli çizgi = tüm indie pazarının aynı yıllardaki medyanı  |  "
              f"Kırmızı/yeşil çizgi ile kesikli çizgi arasındaki fark, bu türün pazardan ne kadar geride/önde olduğunu gösterir")
    fig.subplots_adjust(bottom=0.26)

    return _save(fig, f"finding_{_safe_filename(finding.label)}_trend.png")


def chart_scatter_gap(finding: Finding) -> Path:
    """critic_gap bulguları için: metacritic vs review_score scatter (kopuş
    gösterimi). visualizer.py'nin mevcut chart_critics_vs_players'ına benzer
    ama tek bir Finding etrafında kurulmuş minimal versiyon.
    """
    _style()
    fig, ax = plt.subplots(figsize=(8, 8))

    ax.axline((0, 0), slope=1, color=C["gray"], linestyle="--", linewidth=1)
    color = C["green"] if finding.direction == "positive" else C["red"]
    ax.scatter([finding.baseline_median], [finding.group_median],
               s=200, color=color, zorder=3)
    ax.annotate(finding.label, (finding.baseline_median, finding.group_median),
                textcoords="offset points", xytext=(10, 10), color=C["text"])

    ax.set_xlabel("Eleştirmen puanı (Metacritic)")
    ax.set_ylabel("Oyuncu puanı (Steam review)")
    ax.set_title(f"Eleştirmenler ve Oyuncular Aynı Fikirde Değil\n{finding.n:,} oyun karşılaştırıldı")
    _note(ax, f"{finding.n:,} oyun üzerinden istatistiksel olarak doğrulandı  |  Kesikli çizgi = eleştirmen ve oyuncunun aynı fikirde olduğu nokta")
    fig.subplots_adjust(bottom=0.28)

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
        # NOT: as_posix() kullanılıyor — Path'in string haline (Windows'ta
        # otomatik ters slash \ üretir) DEĞİL. n8n sunucusu Linux'ta çalışıyor,
        # bu yol n8n'in "Read Binary File" node'una doğrudan verileceği için
        # işletim-sistemi-bağımsız (/ ile ayrılmış) olmak ZORUNDA. Bu olmadan
        # yerelde (Windows) üretilen findings.json sunucuda çalışmıyordu.
        finding.chart_path = path.relative_to(path.parent.parent.parent).as_posix()
        log.info(f"  chart_selector: '{finding.label}' -> {path.name}")
    except Exception as e:
        log.warning(f"  chart_selector: '{finding.label}' için grafik üretilemedi: {e}")
    return finding
