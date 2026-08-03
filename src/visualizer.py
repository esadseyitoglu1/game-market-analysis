"""Steam Indie Market — Görselleştirme Modülü (v2)

Vizyon:
  - Tüm indie pazarı, TDS odağı YOK
  - Medyan kullanılır, ortalama değil
  - Her grafikte n= örneklem sayısı belirtilir
  - Arz değil, başarı (talep) gösterilir
  - Sade, sosyal medyada paylaşılabilir tasarım

5 grafik:
  1. hype_vs_reality.png  — Hype Balonu vs Gerçek Başarı (tür bazlı)
  2. the_80pct_cliff.png  — %80 Review Uçurumu
  3. price_sweet_spot.png — Fiyat Tatlı Noktası (medyan sahip)
  4. tag_synergy.png      — En İyi Tag Kombinasyonları
  5. top10_paid_indie.png — Ücretli Indie Top 10
"""

import logging
log = logging.getLogger(__name__)

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# ---------------------------------------------------------------------------
# Renk sistemi
# ---------------------------------------------------------------------------
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

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUTPUT_DIR    = Path(__file__).resolve().parent.parent / "outputs" / "charts"

MIN_REVIEWS_FOR_QUALITY = 10    # Kalite analizi için minimum review sayısı
# NOT: Kaggle dataseti pre-filtered — owners_mid düz 10k çıkıyor.
# Başarı proxy olarak review sayısı kullanıyoruz (doğal dağılımlı).
# EŞİK KESİNLİKLE VERİDEN HESAPLANIR — kodda sabit sayı yok.
# calc_success_threshold() fonksiyonu %80 percentile'ı hesaplar.

def calc_success_threshold(df) -> tuple[int, int, int]:
    """
    Başarı eşiğini veriden hesapla: 
      1. Görünürlük: indie oyunların %80 percentile review sayısı (üst %20).
      2. Kalite: %80+ pozitif review oranı (Steam 'Very Positive').
    Döndürür: (review_thresh, quality_thresh, n_indie)
    """
    indie = df[df["is_indie"] & (df["total_reviews"] > 0)]
    review_thresh = int(indie["total_reviews"].quantile(0.80))
    quality_thresh = 80
    n_indie   = len(indie)
    return review_thresh, quality_thresh, n_indie


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _style():
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


def _save(fig, name):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUTPUT_DIR / name
    fig.savefig(p, bbox_inches="tight", facecolor=C["bg"])
    plt.close(fig)
    log.info(f"  Kaydedildi -> {p.name}")
    return p


def _note(ax, text):
    """Grafiğin sol alt köşesine küçük açıklama notu + zorunlu veri kaynağı."""
    full_text = (
        f"{text}\n"
        "Veri: Kaggle (artermiloff/steam-games-dataset, Mart 2025, ~90k oyun) + SteamSpy API  |  "
        "⚠️ Sahip sayıları SteamSpy tahminidir, Valve resmi rakam paylaşmaz."
    )
    ax.text(0.01, -0.10, full_text, transform=ax.transAxes,
            fontsize=7.5, color=C["muted"], va="top", wrap=True)


def _load(snapshot="march2025"):
    """NOT (2026-08-03): src.metrics.load_universe()'e devrediliyor — bkz.
    insight_engine.py:_load() içindeki aynı notu. `owners_mid` burada SADECE
    chart_top10_paid_indie() geriye dönük çalışsın diye korunuyor; o grafiğin
    kendisi owners kova-çökmesi yüzünden anlamsız (bkz. plan — Adım 6'da
    kaldırılacak). `is_free` analyzer.py uyumluluğu için ayrıca ekleniyor.
    """
    from src.metrics import load_universe

    df = load_universe(snapshot)
    df["release_month"] = df["release_date"].dt.month.astype("Int64")
    df["is_free"] = df["price"] == 0

    def _mid(val):
        try:
            p = str(val).split(" - ")
            return (int(p[0]) + int(p[1])) // 2 if len(p) == 2 else 0
        except:
            return 0

    df["owners_mid"] = df.get(
        "estimated_owners_mid",
        df["estimated_owners"].apply(_mid) if "estimated_owners" in df.columns else 0
    )
    df["owners_mid"] = pd.to_numeric(df["owners_mid"], errors="coerce").fillna(0)

    return df


# ---------------------------------------------------------------------------
# Grafik 1 — Hype vs Gerçeklik
# ---------------------------------------------------------------------------

def chart_hype_vs_reality(df):
    """
    Tür başına: oyun sayısı (arz) vs başarı oranı (gerçek talep).
    Mesaj: 'Herkesin koştuğu türler genellikle tuzaktır.'
    Eşik: veriden hesaplanır (%80 percentile) — keyfi sayı yok.
    """
    # Eşiği VERİDEN hesapla
    success_threshold, quality_threshold, n_indie_total = calc_success_threshold(df)

    indie = df[df["is_indie"] & df["release_year"].between(2019, 2024)].copy()
    n_total = len(indie)

    # Analiz edilecek türler (yeterli oyun sayısı olan tag'ler)
    target_tags = [
        "Action Roguelike", "Rogue-lite", "Survival", "Battle Royale",
        "Tower Defense", "Metroidvania", "Platformer", "Puzzle",
        "Visual Novel", "Top-Down Shooter", "City Builder", "Simulation",
        "Horror", "Bullet Hell", "Deck Building"
    ]
    # NOT: 'Farming Sim' cikarildi — cok spesifik bir nis (Stardew Valley tipi).
    # Genel simulasyon pazarini temsil etmez. Yerine 'Simulation' kullanildi.

    rows = []
    for tag in target_tags:
        mask   = indie["tags_list"].apply(lambda t: tag in t)
        sub    = indie[mask]
        if len(sub) < 30:
            continue
        total   = len(sub)
        # Eşik veriden gelir: %80 percentile = {success_threshold} review VE %80+ pozitif
        success = (
            (sub["total_reviews"] >= success_threshold) & 
            (sub["review_score"] >= quality_threshold)
        ).sum()
        rate    = success / total * 100
        rows.append({"tag": tag, "total": total, "rate": rate})

    if not rows:
        log.warning("  Hype vs Reality: yeterli veri yok, atlandi.")
        return

    stats = pd.DataFrame(rows).sort_values("rate", ascending=True)

    # Eşikleri VERİ BELİRLİYOR — keyfi değil
    mean_rate = stats["rate"].mean()
    std_rate  = stats["rate"].std()
    low_thresh  = mean_rate - 0.5 * std_rate   # Ortalamanın altı = Balon
    high_thresh = mean_rate + 0.5 * std_rate   # Ortalamanın üstü = Fırsat

    colors = []
    for r in stats["rate"]:
        if r < low_thresh:
            colors.append(C["red"])     # Hype Balonu
        elif r > high_thresh:
            colors.append(C["green"])   # Fırsat
        else:
            colors.append(C["blue"])    # Rekabetli

    fig, ax = plt.subplots(figsize=(11, 8))
    bars = ax.barh(stats["tag"], stats["rate"], color=colors, height=0.6)

    for bar, row in zip(bars, stats.itertuples()):
        ax.text(bar.get_width() + 0.3,
                bar.get_y() + bar.get_height() / 2,
                f"%{row.rate:.1f}  (n={row.total:,})",
                va="center", fontsize=9, color=C["text"])

    # Ortalama çizgisi — eşiğin dayanağı
    ax.axvline(mean_rate, color=C["yellow"], linewidth=1.5, linestyle="--", alpha=0.8,
               label=f"Tüm türler ortalaması: %{mean_rate:.1f}")
    ax.axvline(low_thresh,  color=C["red"],   linewidth=1, linestyle=":", alpha=0.5)
    ax.axvline(high_thresh, color=C["green"], linewidth=1, linestyle=":", alpha=0.5)

    # Efsane
    from matplotlib.patches import Patch
    legend = [
        Patch(color=C["red"],    label=f"Hype Balonu (<%{low_thresh:.1f} — ortalamanın altı)"),
        Patch(color=C["blue"],   label=f"Rekabetli (%{low_thresh:.1f}–{high_thresh:.1f} — ortalama bant)"),
        Patch(color=C["green"],  label=f"Fırsat (>%{high_thresh:.1f} — ortalamanın üstü)"),
        Patch(color=C["yellow"], label=f"Ortalama: %{mean_rate:.1f}", alpha=0.5),
    ]
    ax.legend(handles=legend, framealpha=0.15, edgecolor=C["grid"], loc="lower right")

    ax.set_title("Tür Başına Başarı Oranı: Hype mi, Gerçek mi?\n"
                 f"'Başarı' = {success_threshold}+ review VE %{quality_threshold}+ Pozitif  |  2019-2024 indie oyunlar",
                 fontweight="bold", pad=14)
    ax.set_xlabel(f"Başarı Oranı % ({success_threshold}+ rev & %{quality_threshold}+ pozitif)  |  Eşikler veriden hesaplandı, keyfi değil")
    ax.set_xlim(0, stats["rate"].max() * 1.4)
    ax.grid(True, axis="x", alpha=0.3)
    _note(ax, f"n={n_total:,} indie oyun (2019-2024)  |  "
              f"'Başarı' = {success_threshold}+ review (üst %20) + %{quality_threshold} Pozitif Skor  |  "
              f"Eşik = %80 percentile, veriden hesaplandı")

    fig.tight_layout()
    return _save(fig, "hype_vs_reality.png")


# ---------------------------------------------------------------------------
# Grafik 2 — %80 Review Uçurumu
# ---------------------------------------------------------------------------

def chart_80pct_cliff(df):
    """
    Review skoru bantlarına göre medyan sahip sayısı — tüm indie pazarı.
    Mesaj: '%80 Very Positive eşiğini geçmek satışları katlar.'
    """
    indie = df[df["is_indie"] & (df["total_reviews"] >= MIN_REVIEWS_FOR_QUALITY)].copy()
    n_total = len(indie)

    bins   = [0, 50, 60, 70, 75, 80, 85, 90, 95, 100]
    labels = ["<50%", "50-60%", "60-70%", "70-75%", "75-80%",
              "80-85%", "85-90%", "90-95%", "95%+"]

    indie["score_band"] = pd.cut(indie["review_score"], bins=bins, labels=labels, right=False)
    # Medyan review sayısı: review sayısı doğal dağılımlı, owners_mid değil
    stats = indie.groupby("score_band", observed=True).agg(
        medyan_review=("total_reviews", "median"),
        n=("total_reviews", "count")
    ).reset_index()

    colors = [C["red"] if str(b) in ["<50%", "50-60%", "60-70%"]
              else (C["yellow"] if str(b) in ["70-75%", "75-80%"]
              else (C["blue"] if str(b) == "90-95%" else C["green"])) for b in stats["score_band"]]

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(stats["score_band"].astype(str), stats["medyan_review"],
                  color=colors, width=0.65)

    for bar, row in zip(bars, stats.itertuples()):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 5,
                f"{row.medyan_review:.0f}\n({row.n:,} oyun)",
                ha="center", va="bottom", fontsize=9, color=C["text"])

    # %80 eşiği vurgusu
    ax.axvline(x=4.5, color=C["yellow"], linewidth=2, linestyle="--", alpha=0.8)
    ax.text(4.6, ax.get_ylim()[1] * 0.85, "Very Positive\nEşiği (%80)",
            color=C["yellow"], fontsize=10, fontweight="bold")

    # Kalite Tuzağı vurgusu (90-95% bandı) — KOŞULLU (bkz. plan Adım 4).
    # Eskiden bu annotation KOŞULSUZ çiziliyordu — veri tersini gösterse bile
    # ok her zaman burada belirirdi. Gerçek veriyle test edildi (bkz.
    # discovery/families/quality_cliff.py): 90-95% bandı ile 85-90% bandı
    # arasındaki fark İSTATİSTİKSEL OLARAK ANLAMLI değilse (Mann-Whitney U +
    # etki büyüklüğü + bootstrap testi geçmezse), bu ok artık ÇİZİLMEZ.
    from src.discovery.families.quality_cliff import test_quality_trap
    trap_finding = test_quality_trap(df)
    title_suffix = ""
    if trap_finding is not None:
        trap_y = stats.loc[stats["score_band"] == "90-95%", "medyan_review"].values[0]
        ax.annotate("KALİTE TUZAĞI\nAşırı niş oyunlar\nskoru şişirir,\ngörünürlüğü düşürür.",
                    xy=(7, trap_y + 15), xytext=(7, trap_y + 40),
                    ha="center", color=C["blue"], fontweight="bold", fontsize=9,
                    arrowprops=dict(facecolor=C["blue"], edgecolor=C["blue"], arrowstyle="->", lw=1.5))
        title_suffix = " ve Steam'in 'Kalite Tuzağı'"

    ax.set_title(f"Kalite Uçurumu: %80 Barajı{title_suffix}\n"
                 "%80'i geçmek görünürlüğü patlatır. Ancak %90+ skor her zaman başarı demek değildir.",
                 fontweight="bold", pad=14)
    ax.set_xlabel("Steam Oyuncu Memnuniyeti Skoru (%)")
    ax.set_ylabel("Ortalama Yorum Sayısı (Görünürlük)")
    
    # Y ekseni limitini yükseltelim ki yazılar (Kalite Tuzağı notu vs.) başlığa çarpmasın
    ax.set_ylim(0, stats["medyan_review"].max() * 1.4)
    
    ax.grid(True, axis="y", alpha=0.3)
    _note(ax, f"n={n_total:,} indie oyun (min {MIN_REVIEWS_FOR_QUALITY} review)  |  "
              f"'Kalite' = Steam oyuncu memnuniyeti skoru  |  "
              f"Medyan review sayısı: popülerlik proxy'si")
    fig.tight_layout()
    return _save(fig, "the_80pct_cliff.png")


# ---------------------------------------------------------------------------
# Grafik 4 — En İyi Tag Kombinasyonları (Tag Sinerjisi)
# ---------------------------------------------------------------------------

def chart_tag_synergy(df):
    """GERÇEK HESABA ÇEVRİLDİ (2026-08-03) — eskiden bu fonksiyon KENDİ ham
    tag-çifti hesabını yapıyordu (medyan review'a göre sırala, en yükseği al),
    hiçbir istatistiksel test yoktu. Bu, insight_engine.py'deki AYNI hesabın
    ikinci bir kopyasıydı — pipeline'ın %58'i bu tekrarlı hesaba gidiyordu
    (bkz. plan Context bölümü).

    Artık discovery/generators.py + discovery/gate.py üzerinden GERÇEK
    istatistiksel geçitten geçmiş tag_pair bulgularını kullanıyor — aynı
    hesap insight_engine.py'de de kullanılıyor (src.metrics.engaged_universe +
    generate_pairwise_hypotheses + evaluate_batch), burada TEKRARLANMIYOR.
    """
    from src.metrics import engaged_universe
    from src.discovery.generators import generate_pairwise_hypotheses
    from src.discovery.gate import evaluate_batch

    universe = engaged_universe(df).reset_index(drop=True)
    n_total = len(universe)
    values = universe["visibility_pct"].values

    hyps = generate_pairwise_hypotheses(universe, "tags_list", top_n=40, min_count=30)
    findings = evaluate_batch(hyps, values, min_n=30)

    if not findings:
        log.warning("  Tag Synergy: gate'ten geçen bulgu yok, grafik atlandı.")
        return

    top_findings = sorted(findings, key=lambda f: -abs(f.effect))[:12]
    top_findings.sort(key=lambda f: f.effect)  # barh için küçükten büyüğe

    fig, ax = plt.subplots(figsize=(12, 8))

    colors = [C["green"] if f.effect > 0 else C["red"] for f in top_findings]
    labels = [f.label for f in top_findings]
    effects = [f.effect for f in top_findings]

    bars = ax.barh(labels, effects, color=colors, height=0.6)

    for bar, f in zip(bars, top_findings):
        offset = ax.get_xlim()[1] * 0.02 if f.effect >= 0 else -ax.get_xlim()[1] * 0.02
        ha = "left" if f.effect >= 0 else "right"
        ax.text(bar.get_width() + offset, bar.get_y() + bar.get_height() / 2,
                 f"{f.effect:+.2f}  (n={f.n})", va="center", ha=ha, fontsize=9, color=C["text"])

    ax.set_title("Hangi İki Tür Bir Arada Olunca Görünürlük Değişiyor?\n"
                 "Yalnızca istatistiksel geçitten (Mann-Whitney U + BH-FDR + etki büyüklüğü + bootstrap) geçen çiftler gösteriliyor.",
                 fontweight="bold", pad=14)
    ax.set_xlabel("Etki Büyüklüğü (rank-biserial, karşılaştırma grubuna göre)")
    ax.axvline(x=0, color=C["gray"], linewidth=1)
    ax.grid(True, axis="x", alpha=0.3)
    _note(ax, f"n={n_total:,} indie oyun (>=10 review, 2016-2024)  |  Min 30 oyunlu kombinasyonlar  |  "
              f"Meta-tagler ve marka-uygunsuz etiketler hariç tutuldu")
    fig.tight_layout()
    return _save(fig, "tag_synergy.png")


# ---------------------------------------------------------------------------
# Grafik 5 — Ücretli Indie Top 10
# ---------------------------------------------------------------------------

def chart_top10_paid_indie(df):
    """DÜZELTİLDİ (2026-08-03) — eskiden `owners_mid`'e göre sıralıyordu.
    SteamSpy'ın owners alanı kova/aralık formatında geldiği için (bkz. plan
    Context bölümü) 10 oyunun 9'u AYNI kovaya (dolayısıyla aynı owners_mid
    değerine, ör. "35.0M") düşüyordu — sıralama pratikte anlamsızdı, barlar
    görsel olarak özdeşti. Artık `total_reviews` kullanılıyor (gerçek, sürekli
    bir dağılıma sahip, kova yok) — grafiğin konsepti ("en başarılı ücretli
    indie oyunlar") korunuyor, sadece ölçüm düzeltildi.
    """
    paid_indie = df[
        df["is_indie"] & ~df["is_free"] & (df["price"] > 0) &
        (df["total_reviews"] >= 100)
    ].copy()

    top10 = paid_indie.nlargest(10, "total_reviews").sort_values("total_reviews", ascending=True)
    n_total = len(paid_indie)

    # Fiyat bandına göre renk
    def price_color(p):
        if p <= 5:   return C["yellow"]
        if p <= 15:  return C["blue"]
        return C["green"]

    colors = [price_color(p) for p in top10["price"]]

    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(top10["name"], top10["total_reviews"], color=colors, height=0.65)

    for bar, row in zip(bars, top10.itertuples()):
        label = (f"{row.total_reviews:,} review  |  "
                 f"${row.price:.2f}  |  %{row.review_score:.0f} poz.")
        ax.text(bar.get_width() + (ax.get_xlim()[1] * 0.01),
                bar.get_y() + bar.get_height() / 2,
                label, va="center", fontsize=8.5, color=C["text"])

    from matplotlib.patches import Patch
    legend = [
        Patch(color=C["yellow"], label="$1-5"),
        Patch(color=C["blue"],   label="$5-15"),
        Patch(color=C["green"],  label="$15+"),
    ]
    ax.legend(handles=legend, framealpha=0.15, edgecolor=C["grid"],
              title="Fiyat Bandı", loc="lower right")

    ax.set_title("Ücretli Indie Oyunlar — En Çok Review Alan 10 Oyun\n"
                 "Ücretsiz ve F2P oyunlar hariç tutuldu",
                 fontweight="bold", pad=14)
    ax.set_xlabel("Toplam Review Sayısı (görünürlük proxy'si)")
    ax.grid(True, axis="x", alpha=0.3)
    _note(ax, f"n={n_total:,} ücretli indie oyun (min 100 review)  |  "
              f"Ücretsiz/F2P oyunlar hariç: adil karşılaştırma için  |  "
              f"Owners (sahip sayısı) KULLANILMADI — SteamSpy kova formatı çözünürlüksüz")
    fig.tight_layout()
    return _save(fig, "top10_paid_indie.png")


# ---------------------------------------------------------------------------
# Grafik 6 — Eleştirmenler vs Oyuncular
# ---------------------------------------------------------------------------

def chart_critics_vs_players(df):
    """
    Metacritic vs Steam Review Score.
    Mesaj: 'Eleştirmene mi yapıyorsun, oyuncuya mı?'
    """
    sub = df[df["is_indie"] & (df["metacritic_score"] > 0) & (df["total_reviews"] >= 100)].copy()
    
    # Sadece anlamlı uçurumları bulmak için sapma (disconnect) hesapla
    sub["disconnect"] = sub["review_score"] - sub["metacritic_score"]
    
    n_total = len(sub)
    
    fig, ax = plt.subplots(figsize=(10, 10))
    
    # Scatter plot
    ax.scatter(sub["metacritic_score"], sub["review_score"], 
               alpha=0.4, color=C["blue"], edgecolor="none", s=30)
               
    # y = x çizgisi
    ax.plot([0, 100], [0, 100], color=C["gray"], linestyle="--", linewidth=1.5, alpha=0.7)
    
    # 1. Mutlak Uç Noktalar (Herhangi bir kitle boyutu, maksimum kopuş)
    true_player_champs = sub.nlargest(4, "disconnect")
    true_critic_darlings = sub.nsmallest(4, "disconnect")
    
    # 2. Popüler Uç Noktalar (Min 5000 review - ünlü oyunlar)
    popular_sub = sub[sub["total_reviews"] >= 5000]
    pop_player_champs = popular_sub.nlargest(4, "disconnect") if not popular_sub.empty else pd.DataFrame()
    pop_critic_darlings = popular_sub.nsmallest(4, "disconnect") if not popular_sub.empty else pd.DataFrame()
    
    # İkisini birleştir ve aynı oyunlar varsa (drop_duplicates ile) teke düşür
    player_champs = pd.concat([true_player_champs, pop_player_champs]).drop_duplicates(subset=["appid"])
    critic_darlings = pd.concat([true_critic_darlings, pop_critic_darlings]).drop_duplicates(subset=["appid"])
    
    # Noktaları farklı renk ve boyutta belirginleştir
    ax.scatter(player_champs["metacritic_score"], player_champs["review_score"], 
               color=C["green"], edgecolor="white", s=80, zorder=5)
               
    ax.scatter(critic_darlings["metacritic_score"], critic_darlings["review_score"], 
               color=C["red"], edgecolor="white", s=80, zorder=5)
    
    # Yazıların üst üste binmesini engellemek için listeye alıp adjustText kullanacağız
    texts = []
    
    # Yazıların noktaların (dot) tam üstüne binmemesi için X ve Y koordinatlarını toplayacağız
    x_coords = []
    y_coords = []
    
    for _, row in player_champs.iterrows():
        x_coords.append(row["metacritic_score"])
        y_coords.append(row["review_score"])
        texts.append(ax.text(row["metacritic_score"], row["review_score"], row["name"],
                             fontsize=9, color=C["green"], fontweight="bold"))
                    
    for _, row in critic_darlings.iterrows():
        x_coords.append(row["metacritic_score"])
        y_coords.append(row["review_score"])
        texts.append(ax.text(row["metacritic_score"], row["review_score"], row["name"],
                             fontsize=9, color=C["red"], fontweight="bold"))

    # Başlık yazılarını en köşelere al ve değişkenlere ata (Eksenler 10'a genişletildi)
    t1 = ax.text(98, 12, "Eleştirmenin Gözdeleri\n(Yüksek Metacritic, Düşük Steam)", 
                 color=C["red"], fontsize=10, ha="right", va="bottom", alpha=0.8, fontweight="bold")
    t2 = ax.text(12, 98, "Oyuncunun Şampiyonları\n(Düşük Metacritic, Yüksek Steam)", 
                 color=C["green"], fontsize=10, ha="left", va="top", alpha=0.8, fontweight="bold")

    try:
        from adjustText import adjust_text
        # Noktaların kendisinden (x_coords, y_coords) ve köşedeki başlıklardan (t1, t2) kaç!
        adjust_text(texts, x=x_coords, y=y_coords, objects=[t1, t2], 
                    arrowprops=dict(arrowstyle="-", color=C["grid"], lw=0.5), 
                    expand=(1.2, 1.3), force_text=(0.4, 0.4), force_static=(0.2, 0.2))
    except ImportError:
        log.warning("  Uyarı: adjustText yüklü değil, yazılar üst üste binebilir.")
            
    ax.set_xlim(10, 100)
    ax.set_ylim(10, 100)
    ax.set_title("Eleştirmenler vs Oyuncular: Kime Oyun Yapıyorsunuz?\n"
                 "Metacritic Puanı ile Steam Oyuncu Puanı Arasındaki Kopuş",
                 fontweight="bold", pad=14)
    ax.set_xlabel("Metacritic Skoru (Profesyonel Eleştirmenler)")
    ax.set_ylabel("Steam Pozitif Review Oranı (Gerçek Oyuncular)")
    ax.grid(True, alpha=0.2)
    _note(ax, f"n={n_total:,} indie oyun (min 100 review ve Metacritic notu olanlar)")
    fig.tight_layout()
    return _save(fig, "critics_vs_players.png")


# ---------------------------------------------------------------------------
# Ana çalıştırıcı
# ---------------------------------------------------------------------------

def run_charts(snapshot="march2025"):
    _style()
    log.info(f"Veri yukleniyor ({snapshot})...")
    df = _load(snapshot)
    indie = df[df["is_indie"]]
    log.info(f"  {len(df):,} oyun  |  Indie: {len(indie):,}  |  "
          f"Ucretli Indie: {len(indie[~indie['is_free']]):,}\n")
    log.info("Grafikler olusturuluyor...")

    chart_hype_vs_reality(df)
    chart_80pct_cliff(df)
    chart_tag_synergy(df)
    chart_top10_paid_indie(df)
    chart_critics_vs_players(df)

    log.info(f"\nTumu hazir -> {OUTPUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="march2025",
                        choices=["march2025", "may2024", "live"])
    args = parser.parse_args()
    run_charts(args.snapshot)
