"""Steam Indie Market — Insight Engine (Çıkarım Motoru)

Vizyon:
  1. Veriyi tara, anomalileri bul (Hype Balonu, Altın Maden, Co-op çarpanı vb.)
  2. Her anomali için: veri + hikaye şablonu + video hook üret
  3. Çıktıyı outputs/insights/weekly_report.md'ye yaz

Çalıştırma:
  python -m src.insight_engine
  python -m src.insight_engine --snapshot may2024

Her çıkarım (Insight) bir dict döndürür:
  {
    "baslik":   str,    # Grafik/video başlığı
    "veri":     dict,   # Ham sayılar
    "yorum":    str,    # 1 paragraf analitik açıklama
    "hook":     str,    # Video/post için ilk 3 saniye
    "script":   str,    # Video script taslağı
    "grafik":   str,    # Üretilecek grafik dosya adı (veya None)
  }
"""

import logging
log = logging.getLogger(__name__)

import json
import argparse
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

from src.metrics import load_universe

# ---------------------------------------------------------------------------
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUTPUT_DIR    = Path(__file__).resolve().parent.parent / "outputs" / "insights"


# ---------------------------------------------------------------------------
# Veri yükleyici (visualizer'dan bağımsız, standalone)
# ---------------------------------------------------------------------------

def _load(snapshot="march2025") -> pd.DataFrame:
    """NOT (2026-08-03): Bu fonksiyon eskiden kendi tag/genre-parse mantığını
    tekrar yazıyordu (anomaly_detector.py ve analyzer.py'de de birer kopyası
    vardı — bkz. plan Context bölümü, "4 farklı _load() kopyası" sorunu). Artık
    src.metrics.load_universe()'e devrediyor — bu, visibility_pct (yaş-normalize
    görünürlük metriği) hesabını da içeriyor ve families/quality_cliff.py gibi
    yeni discovery modüllerinin ihtiyaç duyduğu ortak veri şemasını sağlıyor.
    `release_month` eklentisi (eski kodda vardı, hiçbir insight'ta kullanılmıyordu)
    ve `is_free` (analyzer.py'de tanımlıydı, burada kullanılmıyordu) burada
    ayrıca eklenmeye devam ediyor — geriye dönük uyumluluk için.
    """
    df = load_universe(snapshot)
    df["release_month"] = df["release_date"].dt.month.astype("Int64")
    df["is_free"] = df["price"] == 0
    return df


def _success_threshold(df: pd.DataFrame) -> tuple[int, int, int]:
    """
    Basari esigi — iki kriter birden:
      1. Gorunurluk: %80 percentile review sayisi (ust %20)
      2. Kalite   : %80+ pozitif review orani (Steam 'Very Positive')
    Ikisini birden saglayanlar 'basarili' sayilir.
    """
    indie = df[df["is_indie"] & (df["total_reviews"] > 0)]
    review_thresh = int(indie["total_reviews"].quantile(0.80))
    quality_thresh = 80.0  # Steam'in 'Very Positive' esigi
    n_indie = len(indie)
    return review_thresh, int(quality_thresh), n_indie


# ---------------------------------------------------------------------------
# INSIGHT 1 — Hype Balonu Tespiti
# ---------------------------------------------------------------------------

def insight_hype_balloon(df: pd.DataFrame) -> dict:
    """
    Soru: Hangi türlerde oyun sayısı (arz) çok ama başarı oranı düşük?
    Cevap: Tür başına başarı oranı, veri-tabanlı eşikle sınıflandırılır.
    """
    thresh, quality_thresh, n_indie_total = _success_threshold(df)
    indie = df[df["is_indie"] & df["release_year"].between(2019, 2024)].copy()

    target_tags = [
        "Action Roguelike", "Rogue-lite", "Survival", "Battle Royale",
        "Tower Defense", "Metroidvania", "Platformer", "Puzzle",
        "Visual Novel", "Top-Down Shooter", "City Builder", "Simulation",
        "Horror", "Bullet Hell", "Deck Building", "Strategy",
        "RPG", "Shooter", "Adventure",
    ]
    # NOT: 'Farming Sim' cikartildi — cok spesifik bir nis (Stardew Valley tipi).
    # Genel simulasyon pazarini temsil etmez. Yerine 'Simulation' kullaniliyor.

    rows = []
    for tag in target_tags:
        mask = indie["tags_list"].apply(lambda t: tag in t)
        sub  = indie[mask]
        if len(sub) < 30: continue
        total = len(sub)
        # BASARI = gorunurluk (171+ review) VE kalite (%80+ pozitif) — ikisi birden
        success = (
            (sub["total_reviews"] >= thresh) &
            (sub["review_score"]  >= quality_thresh)
        ).sum()
        rate = round(success / total * 100, 1)
        rows.append({"tag": tag, "total": total, "success": success, "rate": rate})

    if not rows:
        return {}

    stats      = pd.DataFrame(rows).sort_values("rate", ascending=False)
    mean_rate  = stats["rate"].mean()
    std_rate   = stats["rate"].std()
    low_thresh  = round(mean_rate - 0.5 * std_rate, 1)
    high_thresh = round(mean_rate + 0.5 * std_rate, 1)

    balloons   = stats[stats["rate"] < low_thresh].to_dict("records")
    fırsatlar  = stats[stats["rate"] > high_thresh].to_dict("records")
    en_balon   = balloons[-1] if balloons else None   # en düşük oran
    en_firsat  = fırsatlar[0] if fırsatlar else None  # en yüksek oran

    yorum = (
        f"2019-2024 arasinda cikan {len(indie):,} indie oyun analiz edildi. "
        f"Basari tanimi: {thresh}+ review (gorunurluk, ust %20) "
        f"VE %{quality_thresh:.0f}+ pozitif review (Steam 'Very Positive' esigi). "
        f"Her iki kriteri birden saglayan oyunlar 'basarili' sayildi. "
        f"Tum turlerin ortalama basari orani %{mean_rate:.1f}. "
    )
    if en_balon:
        yorum += (
            f"En kötü performans gösteren tür: '{en_balon['tag']}' — "
            f"{en_balon['total']:,} oyun çıkmış ama yalnızca %{en_balon['rate']} başarıya ulaşmış. "
        )
    if en_firsat:
        yorum += (
            f"Buna karşın '{en_firsat['tag']}' türü %{en_firsat['rate']} başarı oranıyla öne çıkıyor."
        )

    hook = ""
    if en_balon and en_firsat:
        hook = (
            f"'{en_balon['tag']}' türünde {en_balon['total']:,} oyun var, "
            f"sadece %{en_balon['rate']}'i görünür olmuş. "
            f"Ama '{en_firsat['tag']}' türünde bu oran %{en_firsat['rate']}. "
            f"Aradaki fark ne?"
        )

    script = ""
    if en_balon and en_firsat:
        script = (
            f"[HOOK - 0:00-0:05]\n"
            f"'{en_balon['tag']}' yapıyorum diyenler, dur bir dakika.\n\n"
            f"[VERİ - 0:05-0:20]\n"
            f"Steam'deki 52 bin indie oyunu analiz ettim. "
            f"Başarıyı 'oyunların üst %20'sine girmek' olarak tanımladım — "
            f"yani {thresh}+ review almak. "
            f"'{en_balon['tag']}' türünde {en_balon['total']:,} oyun çıkmış, "
            f"sadece %{en_balon['rate']}'i bu eşiği geçebilmiş.\n\n"
            f"[KIRILMA - 0:20-0:35]\n"
            f"Neden? Çünkü herkes bu türe koşuyor. "
            f"Arz arttıkça, Steam algoritmasının pastadan her oyuna ayırdığı pay küçülüyor.\n\n"
            f"[FIRSAT - 0:35-0:50]\n"
            f"Peki akıllı geliştiriciler nereye bakıyor? "
            f"'{en_firsat['tag']}' türüne. "
            f"Aynı dönemde %{en_firsat['rate']} başarı oranı. "
            f"Rakam az oyunla çok daha yüksek görünürlük.\n\n"
            f"[CTA - 0:50-1:00]\n"
            f"Veri kaynağı: Kaggle Steam dataset + SteamSpy API (~90k oyun). "
            f"Hangi türde çalışıyorsunuz? Aşağıya yazın."
        )

    return {
        "baslik":  "Hype Balonu Tespiti: Hangi Türlere Girme",
        "veri":    {
            "n_indie_2019_2024": len(indie),
            "n_indie_total":     n_indie_total,
            "basari_esigi_review": thresh,
            "ortalama_basari_orani": round(mean_rate, 1),
            "balon_esigi": low_thresh,
            "firsat_esigi": high_thresh,
            "tum_turler": stats.to_dict("records"),
            "balonlar":   balloons,
            "firsatlar":  fırsatlar,
        },
        "yorum":  yorum,
        "hook":   hook,
        "script": script,
        "grafik": "hype_vs_reality.png",
    }


# ---------------------------------------------------------------------------
# INSIGHT 2 — Co-op Çarpanı
# ---------------------------------------------------------------------------

def insight_coop_multiplier(df: pd.DataFrame) -> dict:
    """
    Soru: Hangi türlerde Co-op eklemek başarıyı en çok artırıyor?
    Cevap: Tür başına Solo vs Co-op medyan review karşılaştırması.
    """
    indie = df[df["is_indie"] & (df["total_reviews"] >= 5)].copy()
    coop_tags = ["Co-op", "Online Co-Op", "Local Co-Op", "Multiplayer"]

    indie["has_coop"] = indie["tags_list"].apply(
        lambda t: any(ct in t for ct in coop_tags)
    )

    target_tags = [
        "Action Roguelike", "Rogue-lite", "Survival", "Horror",
        "Top-Down Shooter", "Platformer", "Shooter", "Strategy",
        "Simulation", "Adventure", "RPG",
    ]

    rows = []
    for tag in target_tags:
        mask  = indie["tags_list"].apply(lambda t: tag in t)
        sub   = indie[mask]
        solo  = sub[~sub["has_coop"]]
        coop  = sub[sub["has_coop"]]
        if len(solo) < 20 or len(coop) < 10:
            continue
        med_solo = solo["total_reviews"].median()
        med_coop = coop["total_reviews"].median()
        if med_solo == 0:
            continue
        carpan = round(med_coop / med_solo, 1)
        rows.append({
            "tag":       tag,
            "n_solo":    len(solo),
            "n_coop":    len(coop),
            "med_solo":  round(med_solo, 0),
            "med_coop":  round(med_coop, 0),
            "carpan":    carpan,
        })

    if not rows:
        return {}

    stats    = pd.DataFrame(rows).sort_values("carpan", ascending=False)
    en_yuksek = stats.iloc[0]
    en_dusuk  = stats.iloc[-1]

    yorum = (
        f"'Co-op' veya 'Multiplayer' etiketi olan indie oyunlar ile olmayanlar karşılaştırıldı. "
        f"Başarı ölçütü: medyan review sayısı. "
        f"En yüksek Co-op çarpanı: '{en_yuksek['tag']}' türünde — "
        f"solo oyunların medyanı {en_yuksek['med_solo']:.0f} review iken, "
        f"co-op eklenmiş olanlar {en_yuksek['med_coop']:.0f} review alıyor. "
        f"Bu {en_yuksek['carpan']}x fark demek."
    )

    hook = (
        f"'{en_yuksek['tag']}' türü yapıyorsanız ve co-op yok, "
        f"potansiyelinizin {en_yuksek['carpan']}x'ini bırakıyorsunuz masada."
    )

    script = (
        f"[HOOK - 0:00-0:05]\n"
        f"Oyununuza tek bir özellik ekleyerek review sayınızı "
        f"{en_yuksek['carpan']}x artırabilirsiniz.\n\n"
        f"[VERİ - 0:05-0:25]\n"
        f"'{en_yuksek['tag']}' türünde {en_yuksek['n_solo']+en_yuksek['n_coop']:,} oyun analiz ettim. "
        f"Co-op olmayan oyunların medyan review sayısı: {en_yuksek['med_solo']:.0f}. "
        f"Co-op olan oyunların: {en_yuksek['med_coop']:.0f}. "
        f"Aradaki çarpan: {en_yuksek['carpan']}x. "
        f"Co-op oyunlar streamer ve arkadaş grupları için çok daha cazip — bu muhtemelen büyük bir etken.\n\n"
        f"[ÖNEMLİ UYARI - 0:25-0:40]\n"
        f"Ama bu bir korelasyon, nedensellik değil. "
        f"Co-op eklemek mi başarı getiriyor? "
        f"Yoksa zaten büyük ekipler co-op yapabiliyor ve onların pazarlama bütçesi de büyük mü? "
        f"Her iki senaryo da mümkün. Veri ikisini ayıramıyor.\n\n"
        f"[BAĞLAM - 0:40-0:50]\n"
        + (
            f"Analiz ettiğim {len(stats)} türün TAMAMINDA co-op pozitif bir çarpan etkisi yaratıyor "
            f"(en düşük çarpan bile '{en_dusuk['tag']}' türünde {en_dusuk['carpan']}x). Pattern tutarlı.\n\n"
            if en_dusuk["carpan"] > 1
            else
            f"Ancak bu pattern tüm türlerde geçerli değil — '{en_dusuk['tag']}' türünde çarpan "
            f"sadece {en_dusuk['carpan']}x (bazı türlerde etkinin zayıfladığını gösteriyor).\n\n"
        )
        +
        f"[CTA - 0:50-1:00]\n"
        f"Co-op eklemek tabii ki kolay değil — ama veriler bunu hak ettiğini söylüyor. "
        f"Oyununuzda co-op var mı? Neden var, neden yok? Yorumlara yazın."
    )

    return {
        "baslik":  "Co-op Çarpanı: Hangi Türlerde Co-op Altın?",
        "veri":    stats.to_dict("records"),
        "yorum":   yorum,
        "hook":    hook,
        "script":  script,
        "grafik":  "coop_multiplier.png",   # insight_engine visualizer'ı çağırabilir
    }



# INSIGHT 4 — Görünmez Kayıplar (Dead on Arrival)
# ---------------------------------------------------------------------------

def insight_dead_on_arrival(df: pd.DataFrame) -> dict:
    """
    Soru: Kaç indie oyun çıktı ama hiç görünmedi?
    Cevap: 10'dan az review alan oyunların oranı ve tür dağılımı.
    """
    indie = df[df["is_indie"]].copy()
    paid  = indie[~indie["is_free"] & (indie["price"] > 0)]

    dead_thresh = 10
    dead   = paid[paid["total_reviews"] < dead_thresh]
    alive  = paid[paid["total_reviews"] >= dead_thresh]

    dead_rate = round(len(dead) / len(paid) * 100, 1)

    # Hangi yılda daha çok "ölü" oyun çıkmış?
    yearly = paid.groupby("release_year", observed=True).apply(
        lambda x: round((x["total_reviews"] < dead_thresh).mean() * 100, 1),
        include_groups=False
    ).reset_index(name="dead_rate")
    yearly = yearly[yearly["release_year"].between(2018, 2024)]

    yorum = (
        f"{len(paid):,} ücretli indie oyunun {len(dead):,} tanesi "
        f"(%{dead_rate}) hiç görünür olmadı — {dead_thresh}'den az review aldı. "
        f"Bu oyunların çoğu çıktıktan sonra sessizce yok oldu."
    )

    hook = (
        f"Her 100 ücretli indie oyundan {dead_rate:.0f} tanesi "
        f"hiç görünür olmadan yok oluyor. Sebebi ne?"
    )

    script = (
        f"[HOOK - 0:00-0:05]\n"
        f"Steam'deki ücretli indie oyunların %{dead_rate}'i hiç kimseye ulaşamadan yok oldu.\n\n"
        f"[VERİ - 0:05-0:25]\n"
        f"{len(paid):,} ücretli indie oyunu inceledim. "
        f"'Görünür' olmayı {dead_thresh}+ review almak olarak tanımladım. "
        f"{len(dead):,} oyun bu eşiği geçemedi. Pratik olarak kimse görmedi.\n\n"
        f"[SORU - 0:25-0:45]\n"
        f"Peki bu oyunlar neden başarısız oldu? Kalite mi? Pazarlama mı? Zamanlama mı? "
        f"Büyük ihtimalle üçü birden. Ama veri bize şunu söylüyor: "
        f"Her yıl bu oran artıyor — pazar doyuyor.\n\n"
        f"[CTA - 0:45-1:00]\n"
        f"Oyununuzu çıkarmadan önce bu veriyi görmenizi istedim. "
        f"Wishliste eklemek için bağlantı biyografide."
    )

    return {
        "baslik": "Görünmez Kayıplar: Steam'de Her 100 Oyundan Kaçı Yok Oluyor?",
        "veri": {
            "n_ucretli_indie": len(paid),
            "n_dead": len(dead),
            "dead_rate_pct": dead_rate,
            "dead_threshold": dead_thresh,
            "yillik_trend": yearly.to_dict("records"),
        },
        "yorum":  yorum,
        "hook":   hook,
        "script": script,
        "grafik": None,   # Bu insight için grafik ayrıca eklenecek
    }


# ---------------------------------------------------------------------------
# INSIGHT 5 — Kalite Tuzağı (Çok Satan ama Üzen Oyunlar)
# ---------------------------------------------------------------------------

def insight_quality_trap(df: pd.DataFrame) -> dict:
    """
    Soru: Hangi türlerde oyunlar görünürlük kazanıyor ama kalite beklentisini karşılamıyor?
    Cevap: Sadece görünürlük (171+ rev) ile Görünürlük+Kalite (%80+ pozitif) oranları arasındaki fark.
    """
    review_thresh, quality_thresh, n_indie_total = _success_threshold(df)
    indie = df[df["is_indie"] & df["release_year"].between(2019, 2024)].copy()

    target_tags = [
        "Action Roguelike", "Rogue-lite", "Survival", "Battle Royale",
        "Tower Defense", "Metroidvania", "Platformer", "Puzzle",
        "Visual Novel", "Top-Down Shooter", "City Builder", "Simulation",
        "Horror", "Bullet Hell", "Deck Building", "Strategy",
        "RPG", "Shooter", "Adventure",
    ]

    rows = []
    for tag in target_tags:
        mask = indie["tags_list"].apply(lambda t: tag in t)
        sub  = indie[mask]
        if len(sub) < 30: continue
        total = len(sub)
        
        # Sadece görünürlük (eski metrik)
        visible_only = (sub["total_reviews"] >= review_thresh).sum()
        
        # Görünürlük + Kalite (yeni metrik)
        true_success = (
            (sub["total_reviews"] >= review_thresh) &
            (sub["review_score"]  >= quality_thresh)
        ).sum()
        
        rate_visible = visible_only / total * 100
        rate_true    = true_success / total * 100
        drop_pct     = rate_visible - rate_true
        
        rows.append({
            "tag": tag, 
            "total": total, 
            "rate_visible": round(rate_visible, 1),
            "rate_true": round(rate_true, 1),
            "drop_pct": round(drop_pct, 1)
        })

    if not rows: return {}

    stats = pd.DataFrame(rows).sort_values("drop_pct", ascending=False)
    en_buyuk_tuzak = stats.iloc[0]
    ikinci_tuzak   = stats.iloc[1]

    yorum = (
        f"Görünürlük ({review_thresh}+ review) kazandığı halde, oyuncuları memnun etmediği için "
        f"(<%{quality_thresh} skor) 'gerçek başarı' sayılamayan oyunların oranı analiz edildi. "
        f"En büyük kalite tuzağı '{en_buyuk_tuzak['tag']}' türünde. Görünürlük oranı %{en_buyuk_tuzak['rate_visible']}, "
        f"ama kalite filtresi eklenince başarı oranı %{en_buyuk_tuzak['rate_true']}'ye düşüyor "
        f"(%{en_buyuk_tuzak['drop_pct']} kayıp). Pazarlama satıyor ama oyun üzüyor."
    )

    hook = (
        f"'{en_buyuk_tuzak['tag']}' türünde oyun yapmak çok kârlı görünebilir, "
        f"ama oyuncuların en çok iade ettiği/kızdığı tür de bu."
    )

    script = (
        f"[HOOK - 0:00-0:05]\n"
        f"Geliştiricilerin en çok kandığı 'Kalite Tuzağı'ndan bahsedelim.\n\n"
        f"[VERİ - 0:05-0:20]\n"
        f"Dışarıdan bakınca '{en_buyuk_tuzak['tag']}' türü harika duruyor. "
        f"Çıkan oyunların %{en_buyuk_tuzak['rate_visible']}'si Steam'de görünürlük kazanıyor. "
        f"Peki sorun ne? Bu oyunların çok büyük bir kısmı 'Very Positive' alamıyor.\n\n"
        f"[KIRILMA - 0:20-0:35]\n"
        f"Kalite filtresini eklediğimizde, gerçek başarı oranı aniden %{en_buyuk_tuzak['rate_true']}'ye çakılıyor. "
        f"Aynı şey '{ikinci_tuzak['tag']}' türü için de geçerli. Orada da %{ikinci_tuzak['drop_pct']} kayıp var.\n\n"
        f"[ANALİZ - 0:35-0:50]\n"
        f"Bu bize şunu söylüyor: Oyuncular bu türlere AÇ. Buldukları an alıyorlar. "
        f"Ama çoğu oyun vaadini yerine getiremiyor ve oyuncuyu kızdırıyor. "
        f"Eğer kaliteli bir '{en_buyuk_tuzak['tag']}' yaparsanız, sadece satmakla kalmaz, pazarı domine edersiniz.\n\n"
        f"[CTA - 0:50-1:00]\n"
        f"Sizce neden '{en_buyuk_tuzak['tag']}' oyunları genellikle beklentinin altında kalıyor? Fikirlerinizi yazın."
    )

    return {
        "baslik": "Kalite Tuzağı: Pazarlaması İyi Ama Oyuncuyu Üzen Türler",
        "veri": {
            "en_tuzak_tag": en_buyuk_tuzak["tag"],
            "drop": en_buyuk_tuzak["drop_pct"],
            "tum_liste": stats.head(5).to_dict("records"),
        },
        "yorum":  yorum,
        "hook":   hook,
        "script": script,
        "grafik": "hype_vs_reality.png",
    }


# ---------------------------------------------------------------------------
# INSIGHT 5 — Tag Sinerjisi
# ---------------------------------------------------------------------------

def insight_tag_synergy(df: pd.DataFrame) -> dict:
    """GERÇEK HESABA ÇEVRİLDİ (2026-08-03) — eskiden bu fonksiyon SADECE
    max(medyan_review) tag-çiftini seçip "altın madeni" ilan ediyordu, HİÇBİR
    istatistiksel test/confounding kontrolü yoktu. Bu tam olarak "Visual Novel
    + FPS" gibi sahte bulguların kaynağıydı (bkz. plan Context bölümü —
    çok-tag'li oyunların zaten daha "ilgilenilmiş" olduğu confounding sorunu,
    Spearman 0.64→0.208).

    Artık discovery/generators.py + discovery/gate.py üzerinden GERÇEK bir
    istatistiksel geçitten geçiyor: Mann-Whitney U + BH-FDR + etki büyüklüğü
    (>=0.20) + bootstrap %95 GA. Sadece gate'i geçen bir çift varsa, o çift
    "sinerji" olarak sunulur — geçmiyorsa bu insight hiç üretilmez (eskiden
    hep bir "top" vardı, artık kanıt yoksa iddia da yok).
    """
    from src.metrics import engaged_universe
    from src.discovery.generators import generate_pairwise_hypotheses
    from src.discovery.gate import evaluate_batch
    from src.narrative.templates import render_claim

    universe = engaged_universe(df).reset_index(drop=True)
    values = universe["visibility_pct"].values

    hyps = generate_pairwise_hypotheses(universe, "tags_list", top_n=40, min_count=30)
    findings = evaluate_batch(hyps, values, min_n=30)

    if not findings:
        return {}

    top = max(findings, key=lambda f: abs(f.effect))
    claim = render_claim(top)
    t1, t2 = top.label.split(" + ")

    yorum = claim

    hook = (
        f"Sen şu an '{t1}' ile '{t2}' türlerini birlikte kullanmanın rastgele olduğunu düşünüyor olabilirsin. "
        f"Veri {top.n} oyun üzerinden bunun tersini gösteriyor."
    )

    script = (
        f"[HOOK - 0:00-0:05]\n"
        f"'{t1}' ve '{t2}' türlerini birlikte kullanan oyunlar tesadüfen mi öne çıkıyor? Veriyle bakalım.\n\n"
        f"[VERİ - 0:05-0:25]\n"
        f"{claim}\n\n"
        f"[UYARI]\n"
        f"Bu bir korelasyondur, nedensellik değildir — çok tag taşıyan oyunlar zaten geliştiricisinin "
        f"daha çok ilgilendiği oyunlar olabilir.\n\n"
        f"[CTA]\n"
        f"Sizce '{t1}' ve '{t2}' neden birlikte iyi çalışıyor? Yorumlarda tartışalım."
    )

    return {
        "baslik": f"Tag Sinerjisi: {top.label}",
        "veri": top.as_dict(),
        "yorum": yorum,
        "hook": hook,
        "script": script,
        "grafik": "tag_synergy.png"
    }


# ---------------------------------------------------------------------------
# INSIGHT 6 — Eleştirmenler vs Oyuncular
# ---------------------------------------------------------------------------

def insight_critics_vs_players(df: pd.DataFrame) -> dict:
    sub = df[df["is_indie"] & (df["metacritic_score"] > 0) & (df["total_reviews"] >= 100)].copy()
    if sub.empty:
        return {}
        
    sub["disconnect"] = sub["review_score"] - sub["metacritic_score"]
    
    # Senaryo için bilindik (popüler) oyunları seçelim
    popular_sub = sub[sub["total_reviews"] >= 5000]
    if popular_sub.empty:
        popular_sub = sub
        
    player_champ = popular_sub.loc[popular_sub["disconnect"].idxmax()]
    critic_darling = popular_sub.loc[popular_sub["disconnect"].idxmin()]
    
    yorum = (
        f"{len(sub)} adet Metacritic notu olan indie oyun incelendi. "
        f"Oyuncuların en çok sevip eleştirmenlerin gömdüğü oyun: {player_champ['name']} "
        f"(Metacritic: {player_champ['metacritic_score']}, Steam: %{player_champ['review_score']}). "
        f"Eleştirmenlerin bayılıp oyuncuların nefret ettiği oyun: {critic_darling['name']} "
        f"(Metacritic: {critic_darling['metacritic_score']}, Steam: %{critic_darling['review_score']})."
    )
    
    hook = (
        f"Oyununuzu kime beğendirmeye çalışıyorsunuz? Eleştirmenlere mi, yoksa cüzdanıyla oy veren oyunculara mı? "
        f"Steam verilerine göre ikisini birden mutlu etmek neredeyse imkansız."
    )
    
    script = (
        f"[HOOK - 0:00-0:05]\n"
        f"Eğer Metacritic'ten 90 puan aldıysanız, Steam'de kesin başarılı olur musunuz? Veriler tam tersini söylüyor!\n\n"
        f"[VERİ - 0:05-0:25]\n"
        f"Steam'de hem Metacritic notu hem de yeterince oyuncu yorumu olan {len(sub)} indie oyunu inceledim. "
        f"Sonuç inanılmaz bir 'Kopuş' (Disconnect). Örneğin '{critic_darling['name']}'... "
        f"Eleştirmenler oyuna aşık olmuş ve {critic_darling['metacritic_score']} basmış. Ama oyuncular? Steam'de %{critic_darling['review_score']} ile oyunu gömmüşler.\n\n"
        f"[ANALİZ - 0:25-0:45]\n"
        f"Tam tersine de bakalım: '{player_champ['name']}'. Eleştirmenler {player_champ['metacritic_score']} vermiş, "
        f"yani 'eh işte' demişler. Ama oyuncular %{player_champ['review_score']} olumlu yorumla oyunu şampiyon yapmış. "
        f"Neden? Çünkü eleştirmenler 'teknik kusursuzluk ve inovasyon' ararken, oyuncular sadece 'eğlence ve parasının karşılığını' arıyor.\n\n"
        f"[CTA - 0:45-1:00]\n"
        f"Eğer indie geliştiriciyseniz sormanız gereken tek soru var: Oyununuzu kime yapıyorsunuz? IGN'e mi, oyunculara mı?"
    )
    
    return {
        "baslik": "Eleştirmenler vs Oyuncular: Kime Oyun Yapıyorsunuz?",
        "veri": {
            "n_oyun": len(sub),
            "oyuncu_sampiyonu": {
                "name": player_champ["name"],
                "metacritic": player_champ["metacritic_score"],
                "steam": player_champ["review_score"]
            },
            "elestirmen_gozdesi": {
                "name": critic_darling["name"],
                "metacritic": critic_darling["metacritic_score"],
                "steam": critic_darling["review_score"]
            }
        },
        "yorum": yorum,
        "hook": hook,
        "script": script,
        "grafik": "critics_vs_players.png"
    }


# ---------------------------------------------------------------------------
# Rapor Üretici
# ---------------------------------------------------------------------------

def generate_report(insights: list[dict], snapshot: str) -> Path:
    """Tüm çıkarımları Markdown raporuna dönüştür."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / "weekly_report.md"

    lines = [
        f"# Steam Indie Pazar Zekası Raporu",
        f"**Üretildi:** {datetime.now().strftime('%d %B %Y, %H:%M')}  |  "
        f"**Veri:** Kaggle steam-games-dataset ({snapshot})  |  "
        f"**Uyarı:** SteamSpy verileri tahminidir, Valve resmi rakam paylaşmaz.",
        "",
        "---",
        "",
    ]

    for i, ins in enumerate(insights, 1):
        if not ins:
            continue
        lines += [
            f"## {i}. {ins['baslik']}",
            "",
            f"**📊 Analitik Yorum**",
            ins["yorum"],
            "",
            f"**🎣 Video Hook (İlk 3 Saniye)**",
            f"> {ins['hook']}",
            "",
            f"**📝 Script Taslağı**",
            "```",
            ins["script"],
            "```",
            "",
            f"**📈 Grafik:** `{ins.get('grafik') or 'Henüz yok'}`",
            "",
            "---",
            "",
        ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ---------------------------------------------------------------------------
# Telegram Digest — YEDEK çıktı, GERÇEK n8n akışında KULLANILMIYOR
# ---------------------------------------------------------------------------
# NOT (2026-08-03): Gerçek n8n akışı şu şekilde çalıştığı doğrulandı: Python
# autonomous_anomalies.json'u (ham anomaliler) üretir -> bu doğrudan n8n'deki
# LLM (Claude) node'una gider -> LLM kendi yaratıcı script'ini yazar (bkz.
# docs/n8n_system_prompt.md) -> Telegram'a o gider. Yani seçim ve metin üretimi
# LLM'e ait, Python'a değil — bu bilinçli/onaylanmış tasarım.
#
# Bu fonksiyon, Telegram'ın 4096 karakter sert limitine karşı bir GÜVENLİK AĞI
# olarak yazıldı ("Bad Request: message is too long" hatasına karşı), ama asıl
# çözüm n8n'deki LLM system prompt'una eklenen "UZUNLUK LİMİTİ" kuralı oldu
# (LLM kendi çıktısını 3500 karakterle sınırlıyor). Yani bu fonksiyonun ürettiği
# telegram_digest.md dosyası ŞU AN n8n workflow'una BAĞLI DEĞİL. Silinmedi çünkü
# ileride Python'un kendi metnini doğrudan yollamak istenirse hazır dursun diye.
# Yeni bir asistan bu fonksiyonu görüp "n8n bunu kullanıyor" varsaymasın.
TELEGRAM_CHAR_LIMIT = 4096
TELEGRAM_SAFE_LIMIT = 3500  # başlık/emoji gibi n8n'in ekleyebileceği payı için marj


def generate_telegram_digest(insights: list[dict]) -> Path:
    """weekly_report'taki insight'lardan Telegram'a güvenle gönderilebilecek
    tek bir kısa özet üretir ve outputs/insights/telegram_digest.md'ye yazar.
    """
    valid = [ins for ins in insights if ins]
    digest_path = OUTPUT_DIR / "telegram_digest.md"

    if not valid:
        digest_path.write_text("Bu hafta üretilecek bir içerik bulunamadı.", encoding="utf-8")
        return digest_path

    # Script'i en uzun olan (=en detaylı anlatılan) insight'ı seç — genelde en
    # "dolu" olan budur. Deterministik: aynı girdide her zaman aynı seçim.
    chosen = max(valid, key=lambda ins: len(ins.get("script", "")))

    parts = [
        f"🔥 HAFTANIN RİBAT VERİ ANOMALİSİ: {chosen['baslik']}",
        "",
        f"🎬 [EDİTÖRE NOT]: {chosen['yorum']}",
        "",
        chosen["script"],
        "",
        f"📈 Grafik: {chosen.get('grafik') or 'Henüz yok'}",
    ]
    text = "\n".join(parts)

    if len(text) > TELEGRAM_SAFE_LIMIT:
        # Sahneleri SİLMEK yerine sondan kırpıyoruz — CTA/son sahne kaybolsa
        # bile hook + veri gerçeği (en kritik kısım) korunur.
        text = text[:TELEGRAM_SAFE_LIMIT - 20].rstrip() + "\n\n[...devamı kırpıldı]"

    digest_path.write_text(text, encoding="utf-8")
    log.info(f"  Telegram digest: {len(text)} karakter (limit {TELEGRAM_SAFE_LIMIT})")
    return digest_path


# ---------------------------------------------------------------------------
# INSIGHT 7 — Kalite Uçurumu ve %80 Barajı
# ---------------------------------------------------------------------------

def insight_80pct_cliff(df: pd.DataFrame) -> dict:
    """GERÇEK HESABA ÇEVRİLDİ (2026-08-03) — eskiden bu fonksiyon `df`
    parametresini hiç kullanmıyordu, tüm iddialar (özellikle "Kalite Tuzağı")
    elle yazılmıştı. Şimdi src/discovery/families/quality_cliff.py üzerinden
    GERÇEK istatistiksel testler çalıştırılıyor; her iddia SADECE gate'ten
    geçerse metne dökülüyor. Test sonucu (bu yazılırken, march2025 snapshot'ında):
    "%80 Uçurumu" GERÇEKTEN doğrulandı (effect=+0.277, n=19.219), ama "Kalite
    Tuzağı" (90-95 bandının 85-90'dan düşük olduğu) istatistiksel olarak
    DOĞRULANAMADI — eski sistem bunu kanıtsız, kesin bir gerçek gibi sunuyordu.
    """
    from src.discovery.families.quality_cliff import test_cliff_at_80, test_quality_trap
    from src.narrative.templates import render_claim

    cliff_finding = test_cliff_at_80(df)
    trap_finding = test_quality_trap(df)

    if cliff_finding is None:
        # Evren çok küçükse (min_n altında) bu insight hiç üretilemez —
        # eski sistemin "her zaman statik metin döndür" davranışının aksine.
        return {}

    cliff_claim = render_claim(cliff_finding)

    if trap_finding is not None:
        trap_claim = render_claim(trap_finding)
        trap_section = (
            f"[KALİTE TUZAĞI - 0:20-0:40]\n"
            f"Veri ayrıca şunu gösteriyor: {trap_claim} "
            f"Bu, çok dar bir kitleye hitap eden oyunların skoru şişirip ana akıma ulaşamadığı anlamına gelebilir "
            f"(korelasyon, nedensellik değildir)."
        )
    else:
        trap_section = (
            f"[NOT]\n"
            f"90-95% bandı ile 85-90% bandı arasında, bu veri setinde istatistiksel olarak anlamlı bir "
            f"görünürlük farkı TESPİT EDİLEMEDİ. 'Kalite Tuzağı' iddiası bu snapshot'ta desteklenmiyor."
        )

    yorum = (
        f"{cliff_claim} "
        + ("Ayrıca 90-95% bandında istatistiksel olarak doğrulanmış bir düşüş eğilimi var."
           if trap_finding else
           "90-95% bandında ise anlamlı bir 'tuzak' etkisi bu snapshot'ta bulunamadı.")
    )

    hook = (
        f"Sen şu an Steam'in %80 (Very Positive) barajını sadece bir rozet sanıyor olabilirsin. "
        f"Veri {cliff_finding.n} oyun üzerinden gösteriyor ki bu eşiği geçmek görünürlüğü gerçekten değiştiriyor."
    )

    script = (
        f"[VERİ GERÇEĞİ - 0:00-0:20]\n"
        f"{cliff_claim}\n\n"
        f"{trap_section}\n\n"
        f"[CTA]\n"
        f"Bu bulgular Mann-Whitney U testi + Benjamini-Hochberg FDR düzeltmesi + bootstrap güven aralığı "
        f"ile doğrulanmıştır (q={cliff_finding.q_value if not np.isnan(cliff_finding.q_value) else 'hesaplanmadı'})."
    )

    return {
        "baslik": "Kalite Uçurumu: %80 Barajı" + (" ve Kalite Tuzağı" if trap_finding else ""),
        "veri": {
            "cliff": cliff_finding.as_dict() if cliff_finding else None,
            "quality_trap": trap_finding.as_dict() if trap_finding else None,
        },
        "yorum": yorum,
        "hook": hook,
        "script": script,
        "grafik": "the_80pct_cliff.png"
    }

# ---------------------------------------------------------------------------
# Ana çalıştırıcı
# ---------------------------------------------------------------------------

def run(snapshot="march2025"):
    log.info(f"Veri yukleniyor ({snapshot})...")
    df = _load(snapshot)
    indie = df[df["is_indie"]]
    log.info(f"  {len(df):,} oyun  |  Indie: {len(indie):,}\n")

    log.info("Cikarimlari hesaplaniyor...")
    insights = []

    log.info("  [1/7] Hype Balonu Tespiti...")
    insights.append(insight_hype_balloon(df))

    log.info("  [2/7] Co-op Carpani...")
    insights.append(insight_coop_multiplier(df))

    log.info("  [3/7] Gorünmez Kayiplar (Dead on Arrival)...")
    insights.append(insight_dead_on_arrival(df))

    log.info("  [4/7] Kalite Tuzagi (Pazarlama)...")
    insights.append(insight_quality_trap(df))

    log.info("  [5/7] Tag Sinerjisi...")
    insights.append(insight_tag_synergy(df))
    
    log.info("  [6/7] Eleştirmenler vs Oyuncular...")
    insights.append(insight_critics_vs_players(df))

    log.info("  [7/7] %80 Kalite Uçurumu...")
    insights.append(insight_80pct_cliff(df))

    log.info("\nRapor yaziliyor...")
    report_path = generate_report(insights, snapshot)
    log.info(f"  -> {report_path}")

    # JSON da çıkar (n8n'in okuyacağı Kati Kontrat formatinda)
    run_id = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

    # total_insights: SADECE boş olmayan insight'ları say. Eskiden len(insights)
    # kullanılıyordu — bir insight fonksiyonu erken çıkıp {} döndürürse (bkz.
    # insight_coop_multiplier, insight_quality_trap vb. birden fazla erken-return
    # noktası var) generate_report bu boş kaydı atlıyor ama sayaç yine de 7
    # diyordu. n8n/LLM tarafı "insights dizisinde 7 öğe var" bekleyip aslında
    # 6 gerçek insight bulunca şaşırabiliyordu.
    valid_insights = [ins for ins in insights if ins]

    n8n_contract = {
        "run_id": run_id,
        "status": "success",
        "content_ready": True,
        "total_insights": len(valid_insights),
        "insights": valid_insights
    }

    json_path = OUTPUT_DIR / "weekly_report.json"
    json_path.write_text(
        json.dumps(n8n_contract, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8"
    )
    log.info(f"  -> {json_path}")

    # Telegram'a GÜVENLE gönderilebilecek kırpılmış özet (bkz. generate_telegram_digest
    # docstring'i — Telegram'ın 4096 karakter sert sınırı yüzünden eklendi).
    digest_path = generate_telegram_digest(insights)
    log.info(f"  -> {digest_path}")

    log.info("\nTamamlandi.")
    return insights


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="march2025",
                        choices=["march2025", "may2024", "live"])
    args = parser.parse_args()
    run(args.snapshot)
