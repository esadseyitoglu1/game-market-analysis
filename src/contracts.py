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
from src.narrative.templates import render_claim

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
                              year_range: tuple[int, int] = (2016, 2025)) -> dict:
    return {
        "n": n,
        "filter": f"indie, {year_range[0]}-{year_range[1]}, >={min_reviews} review",
        "metric": "yıl-içi log-review percentile (visibility_pct)",
    }


MAX_PER_FAMILY = 2  # aynı aileden LLM'e gidecek en fazla bulgu sayısı

# AKSİYONA DÖNÜŞMEYEN AİLELER (bkz. plan "AKTİF PLAN 2026-08-05" Adım B).
# Kullanıcı canlı n8n çıktısını inceleyip şu teşhisi koydu: "'Boomer Shooter'
# etiketi koy, 18 puan daha görünür ol" gibi bulgular TUZAK içerik — etiket
# bir SONUÇ, sebep değil. İzleyici etiketi ekleyince görünür olmuyor; o 139
# oyun zaten iyi yapıldığı için hem etiketi hem görünürlüğü kazanmış. Fiyat
# bandı, oyun modu (Co-op/VR/MMO), oynanma süresi gibi bulgular ise
# geliştiricinin GERÇEKTEN karar verdiği/kontrol ettiği şeyler — bu yüzden
# etiket aileleri (tags_list_single, tags_list_pair) LLM'e hiç gönderilmiyor.
#
# ÖLÇÜLDÜ (2026-08-05): etiketleri yasaklamadan önce 276 bulgunun 267'si
# (%97) bu iki aileden geliyordu — filtre öncesi keşif motoru genişletilmeden
# (bkz. Adım A) etiketsiz havuz sadece 9 bulguya düşüyordu, ayda 5 video ile
# 2 ayda tükenirdi. Adım A'daki categories_list/price_band eklemesiyle havuz
# 24'e çıktı. Yine de küçük kalabileceği ihtimaline karşı FALLBACK var
# (aşağıda) — havuz max_n'den azsa etiketler geri devreye girer, sistem asla
# boş/eksik rapor üretmez.
NON_ACTIONABLE_FAMILIES = {
    # Etiket aileleri: istatistiksel olarak güçlü ama "ekle → görünür ol"
    # mantığı YANLIŞ — etiket bir sonuç, sebep değil (bkz. yukarıdaki not).
    "tags_list_single",
    "tags_list_pair",
    # Tautolojik / kontrol edilemez aileler (2026-08-07 eklendi):
    # discount_split: indirim döneminde Steam zaten oyunu öne çıkarıyor
    #   (platformun kendi mekaniği) — n=156 küçük, ilişki anlık/dönemsel.
    #   "İndirime gir → görünür ol" tavsiyesi verilse de geliştiricinin
    #   uzun vadeli bir kararı değil, zaten bilinen kısa vadeli bir taktik.
    "discount_split",
    # peak_ccu_split: popüler oyunun hem CCU'su hem görünürlüğü yüksek —
    #   neden-sonuç tamamen ters, CCU görünürlüğün sonucu, nedeni değil.
    "peak_ccu_split",
    # metacritic_score_split: Metacritic puanı almak geliştiricinin doğrudan
    #   kontrol edebildiği bir şey değil (medya ilgisi gerektirir). İstatistik
    #   güçlü ama "git Metacritic puanı al" denilemez.
    "metacritic_score_split",
    # average_playtime_forever_split: oynanma süresi kaydı = oyun gerçekten
    #   oynandı = zaten yüklenmiş/satılmış. Görünürlük → satış → oynanma
    #   zinciri; özelliği "ekle" denilemez, varlığı başarının göstergesi.
    "average_playtime_forever_split",
    # cliff_80 (Very Positive eşiği): review skoru geliştirici tarafından
    #   doğrudan ayarlanamaz — iyi oyun yapılırsa zaten geliyor.
    "cliff_80",
}


def select_top_findings(findings: list[Finding], max_n: int = MAX_FINDINGS_FOR_LLM,
                          max_per_family: int = MAX_PER_FAMILY) -> list[Finding]:
    """LLM'e gidecek en fazla max_n bulguyu DETERMİNİSTİK seçer — en yüksek
    |effect| büyüklüğüne göre sıralanır, rastgelelik yok (eski sistemin
    seed'siz random.shuffle sorununun tekrarlanmaması için, bkz. Adım 0).

    AİLE ÇEŞİTLİLİĞİ (2026-08-04 eklendi): Sadece |effect|'e göre sıralamak,
    bir ailenin (özellikle temporal_trend — Spearman ρ değerleri diğer
    ailelerin rank-biserial etkilerinden sistematik olarak daha yüksek çıkıyor)
    TÜM 5 slotu tek başına doldurmasına yol açıyordu — canlı çalıştırmada
    5 bulgunun 5'i de temporal_trend'den ve hepsi "görünürlük kaybı" temalıydı,
    aylık video paketi tekdüze olurdu. Artık her aileden en fazla
    max_per_family (varsayılan 2) bulgu alınır; kalan slotlar, aile sınırına
    takılmamış en güçlü bulgularla (yine |effect| sırasına göre) doldurulur.
    Seçim hâlâ tamamen deterministik — sadece iki geçişli (aile-sınırlı, sonra
    dolgu) bir sıralama, rastgelelik yok.

    AKSİYONA DÖNÜŞMEYEN FİLTRE (2026-08-05 eklendi): önce NON_ACTIONABLE_FAMILIES
    elenir. Elenen havuz max_n'den azsa (fallback), etiket bulguları GERİ
    devreye girer — sistem hiçbir zaman boş/eksik rapor üretmesin diye.
    """
    non_fragile = [f for f in findings if not f.fragile]
    actionable = [f for f in non_fragile if f.family not in NON_ACTIONABLE_FAMILIES]

    pool = actionable if len(actionable) >= max_n else non_fragile
    ranked = sorted(pool, key=lambda f: -abs(f.effect))

    selected: list[Finding] = []
    family_counts: dict[str, int] = {}
    leftover: list[Finding] = []

    for f in ranked:
        if len(selected) >= max_n:
            break
        if family_counts.get(f.family, 0) < max_per_family:
            selected.append(f)
            family_counts[f.family] = family_counts.get(f.family, 0) + 1
        else:
            leftover.append(f)

    # Aile sınırı yüzünden dışarıda kalanlarla eksik slotları doldur
    # (örn. tüm bulgular 2 aileden geliyorsa, max_n'e ulaşmak için sınırı gevşet)
    for f in leftover:
        if len(selected) >= max_n:
            break
        selected.append(f)

    return selected


def attach_alternatives(selected: list[Finding], all_findings: list[Finding],
                          max_alternatives: int = 2) -> None:
    """Seçilen her bulguya, AYNI ETİKETİ içeren en güçlü POZİTİF tag-pair
    kombinasyonlarını "alternatives" alanına ekler — in-place, dönüş yok.

    NEDEN BU FONKSİYON VAR (bkz. plan, kullanıcı geri bildirimi 2026-08-06):
    LLM'e tek bir bulgu gittiği için "Bullet Hell düşüyor" diyebiliyordu ama
    "peki ne yapmalı" sorusuna içi boş tavsiyeler ("tag kombinasyonlarını
    test et") veriyordu — çünkü elinde somut veri yoktu. Kullanıcının kendi
    önerisi: "adam zaten Bullet Hell yapıyorsa temel tag'i değiştiremez, asıl
    soru hangi İKİNCİ tag'i eklerse daha görünür olur." Bu tam olarak
    tags_list_pair ailesinin ölçtüğü şey — bu fonksiyon, seçilen bulgunun
    etiketini tags_list_pair havuzunda arayıp en güçlü pozitif eşleşmeleri
    ekliyor.

    NOT: tags_list_single/tags_list_pair NON_ACTIONABLE_FAMILIES'de olduğu
    için LLM'e ANA bulgu olarak hiç gitmiyor — ama burada YARDIMCI bilgi
    olarak (ana bulgunun "alternatives" alanında) kullanılması, "etiket
    koy görünür ol" tuzağından farklı: burada net bir aksiyon var ("mevcut
    oyununa X'i ekle"), tek başına "bu etiketi tak" tavsiyesi değil.

    Her Finding'in `label`'ından ana etiketi çıkarır (temporal_trend için
    " (pazara göre..." son ekini, diğerleri için olduğu gibi kullanır) ve
    tags_list_pair bulgularında bu etiketi arar.

    GÖRSELLEŞTİRME (2026-08-06 revize edildi): ilk versiyonda her alternatif
    için AYRI bir grafik dosyası üretiliyordu ve n8n'in ikinci bir foto
    zinciri olarak göndermesi planlanıyordu. Kullanıcı daha zarif bir çözüm
    önerdi: ayrı foto yerine, ana bulgunun grafiğine (bkz.
    chart_selector.py:chart_trend_line) ikinci bir panel olarak gömülüyor —
    editör tek görselde her şeyi görüyor, videoda ilgili ana geldiğinde
    zoomlayabiliyor. Bu yüzden burada `chart_path` alanı YOK — grafik
    üretimi `render_chart_for_finding()`'in `alternatives[0]`'ı okuyup ana
    grafiğin içine çizmesiyle oluyor.
    """
    pair_findings = [f for f in all_findings
                      if f.family == "tags_list_pair" and f.direction == "positive"]

    for finding in selected:
        # Ana etiketi çıkar: "Bullet Hell (pazara göre göreli trend, ...)" -> "Bullet Hell"
        main_tag = finding.label.split(" (")[0]

        matches = [f for f in pair_findings if main_tag in f.label.split(" + ")]
        matches.sort(key=lambda f: -f.effect)

        alternatives = []
        for m in matches[:max_alternatives]:
            other_tag = [t for t in m.label.split(" + ") if t != main_tag]
            other_tag = other_tag[0] if other_tag else m.label
            alternatives.append({
                "combo_label": m.label,
                "added_tag": other_tag,
                "main_tag": main_tag,
                "n": m.n,
                "n_baseline": m.n_baseline,
                "gap_points": round((m.group_median - m.baseline_median) * 100),
                "group_median": m.group_median,
                "baseline_median": m.baseline_median,
            })
        finding.alternatives = alternatives


def _replace_nan_with_none(obj):
    """JSON'a yazmadan önce ağacı gezip float NaN'ları None'a çevirir.

    NEDEN GEREKLİ (2026-08-06 bulundu, n8n canlı testinde): Python'un
    json.dumps'u varsayılan olarak NaN'ı ham `NaN` token'ı olarak yazıyor
    (allow_nan=True) — bu geçerli JSON DEĞİL, sadece Python/JS'in gevşek
    parser'ları kabul ediyor. n8n'in "Parse findings JSON" node'u standart
    JSON.parse() kullanıyor, `NaN` görünce "Unexpected token 'N'" ile
    çöküyordu. temporal_trend ailesi effect_ci=(NaN, NaN) ve q_value=NaN
    üretiyor (bootstrap uygulamıyor, bkz. families/temporal.py) — bu değerler
    findings.json'a giden tek NaN kaynağı. `null` standart JSON'da geçerli
    ve n8n/JS tarafında sorunsuz parse ediliyor.
    """
    if isinstance(obj, float) and obj != obj:  # NaN != NaN, en hızlı NaN kontrolü
        return None
    if isinstance(obj, dict):
        return {k: _replace_nan_with_none(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_nan_with_none(v) for v in obj]
    return obj


def select_actionable_findings(findings: list[Finding]) -> list[Finding]:
    """NON_ACTIONABLE_FAMILIES'i eleyip geriye kalan TÜM aksiyona-dönüşen
    bulguları döndürür (5'lik LLM seçimi DEĞİL — bu, kütüphaneyi doldurmak
    için kullanılıyor, bkz. write_findings_library).

    fragile olanlar da elenir (select_top_findings'teki non_fragile filtresiyle
    tutarlı — kırılgan bulgular hiçbir yere gitmemeli, ne haftalık seçime ne
    kütüphaneye).
    """
    non_fragile = [f for f in findings if not f.fragile]
    return [f for f in non_fragile if f.family not in NON_ACTIONABLE_FAMILIES]


def write_findings_library(actionable: list[Finding]) -> Path:
    """TÜM aksiyona-dönüşen bulguları (o hafta seçilen 5 değil, hepsi) tek bir
    depo dosyasına (findings_library.json) yazar — her biri kendi grafiğiyle.

    NEDEN BU FONKSİYON VAR (kullanıcı isteği, 2026-08-07): "24 koca veride
    bulgular neye benziyor, hepsini direkt üretip bir yerde depo olarak
    tutalım." Eskiden ~24 aksiyona-dönüşen bulgudan sadece o haftaki 5'i
    grafik alıp findings.json'a yazılıyordu, geri kalan ~19'u her çalıştırmada
    hesaplanıp atılıyordu. Artık hepsi diskte duruyor — havuzun ne durumda
    olduğunu görmek veya ileride bir "aylık rapor" için buradan çekmek için.

    NOT: attach_alternatives ÇAĞIRICI TARAFINDAN, grafik üretiminden ÖNCE
    yapılmış olmalı (bkz. run_all.py'deki 2026-08-07 düzeltmesi — sıralama
    ters olursa grafiğe alternatives paneli hiç yansımıyor).
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rendered = render_findings(actionable)
    library = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "schema_version": SCHEMA_VERSION,
        "total": len(rendered),
        "findings": rendered,
    }
    library = _replace_nan_with_none(library)

    path = OUTPUT_DIR / "findings_library.json"
    path.write_text(json.dumps(library, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    log.info(f"  findings_library.json yazıldı: {len(rendered)} aksiyona-dönüşen bulgu, hepsi grafikli -> {path}")
    return path


FAMILY_EXPLANATIONS = {
    "categories_list_single": "Oyun modu/platform özelliği (Co-op, VR, Remote Play...) — "
        "geliştiricinin doğrudan karar verip ekleyebildiği bir şey.",
    "price_band": "Fiyat aralığı. DİKKAT: fiyat ile görünürlük arasındaki bağ muhtemelen "
        "kaliteden değil, o fiyatı hak edecek İÇERİK MİKTARINDAN geliyor — 'fiyatını "
        "yükselt' tavsiyesi tek başına yanıltıcı, bkz. aşağıdaki uyarı.",
    "achievements_split": "Achievement sayısı medyanın üstünde mi altında mı.",
    "dlc_count_split": "DLC'si var mı yok mu.",
    "average_playtime_forever_split": "Oyunun hiç oynanma süresi kaydı var mı (0'dan büyük mü).",
    "discount_split": "Şu an indirimde mi değil mi.",
    "peak_ccu_split": "Aynı anda oynanan en yüksek oyuncu sayısı (peak CCU) 0'dan büyük mü.",
    "metacritic_score_split": "Metacritic puanı var mı yok mu (eleştirmen değerlendirmesi almış mı).",
    "temporal_trend": "Bu tag'in yıllar içindeki görünürlüğü, PAZARIN GENELİNE göre "
        "açılıyor mu daralıyor mu (mutlak seviye değil, pazarla arasındaki FARKIN eğimi).",
    "cliff_80": "Review skoru %80 (Steam'in 'Very Positive' eşiği) üstünde mi altında mı.",
}

METRIC_GLOSSARY = """## Bu tabloyu nasıl okumalı

Her satır, istatistiksel bir testten geçmiş bir karşılaştırmayı özetliyor:
"bu özelliği taşıyan oyunlar" (grup) vs "taşımayanlar" (n_base/baseline).

- **Yön**: `+` = bu özelliği taşıyanlar DAHA görünür, `-` = DAHA AZ görünür.
- **effect** (etki büyüklüğü, -1 ile +1 arası): aradaki farkın büyüklüğü.
  |0.20|'nin altındaki farklar zaten elenmiş (gate'i geçemez) — yani burada
  gördüğün her satır önemsiz olamayacak kadar büyük bir fark taşıyor.
  Kabaca: 0.20-0.35 orta, 0.35-0.55 güçlü, 0.55+ çok güçlü fark.
- **q**: Benjamini-Hochberg FDR düzeltmeli p-değeri — "bu fark şans eseri mi"
  sorusunun cevabı, ne kadar 0'a yakınsa o kadar güvenilir. `nan` görünüyorsa
  (temporal_trend ailesinde) o aile bootstrap yerine farklı bir test kullanıyor,
  q-value hesaplanmıyor ama effect ve n yine de geçerli.
- **n**: bu özelliği taşıyan kaç oyun test edildi. **n_base**: karşılaştırılan
  taban kaç oyundu (temporal_trend'de 0 görünür — bu aile "taban" yerine
  pazarın kendisiyle kıyaslıyor, ayrı bir mantık).
- **VERİ NE DİYOR**: her satırın altında, sayının gündelik dile çevrilmiş hali
  (n8n'in sosyal medya içeriğinde kullandığı `claim` cümlesiyle AYNI kaynaktan).

**Görünürlük (`visibility_pct`) ne demek:** SATIŞ veya KALİTE puanı DEĞİL —
oyunun review SAYISININ (kaç kişi yorum yazdı, review puanı değil), aynı çıkış
yılındaki diğer oyunlara göre yüzdelik dilimi. "22 puan daha görünür" =
"bu grup, aynı yıl çıkan oyunlara kıyasla review alma sıralamasında ortalama
%22 daha üst dilimde" — ilgi/bilinirlik ölçer, satış rakamı değil.

**UYARI — korelasyon nedensellik değildir:** Özellikle `price_band` ve
`categories_list_single` ailelerinde, "bu özelliği ekle → görünür olursun"
şeklinde okuma YANLIŞ olabilir. Çoğu zaman neden-sonuç ters: zaten iyi/kapsamlı
bir oyun yapan geliştirici hem bu özelliği ekliyor hem görünür oluyor — özelliğin
kendisi sebep değil, iyi oyunun bir belirtisi. `outputs/insights/findings_library.json`
içindeki `caveats` listesi bu uyarıyı tam metin olarak taşıyor.

---

"""


def write_markdown_report(actionable: list[Finding], universe_n: int,
                            total_discovered: int, snapshot: str = "march2025",
                            end_year: int = 2025) -> Path:
    """Kullanıcının (Ribat Games kurucusu) kendi okuması için teknik rapor
    üretir — outputs/insights/rapor.md. İstatistik dili (effect, n, q-value)
    KORUNUR ama her sütun ve her aile açıklanır — bu dosya LLM'e veya sosyal
    medyaya gitmiyor, editöryel/teknik denetim için. Her run_discovery()
    çağrısında yeniden yazılır (üzerine yazar, biriktirmez).

    2026-08-07 GENİŞLETİLDİ: kullanıcı ilk versiyonu (çıplak effect/q/n tablosu)
    görünce "bu ne, açıklama olması lazım" dedi — haklı, sütun başlıkları
    tek başına anlam taşımıyordu. Artık üstte METRIC_GLOSSARY (her sütunun ne
    anlama geldiği + görünürlük tanımı + korelasyon/nedensellik uyarısı) ve
    her aile başlığının yanında FAMILY_EXPLANATIONS'tan gündelik açıklama var,
    her satırın altında da render_claim() ile üretilen "VERİ NE DİYOR" cümlesi
    (n8n'e giden claim ile AYNI kaynak) ekleniyor.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    by_family: dict[str, list[Finding]] = {}
    for f in actionable:
        by_family.setdefault(f.family, []).append(f)

    lines = [
        f"# Bulgu Raporu — {snapshot}",
        "",
        f"Üretim zamanı: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Evren: {universe_n:,} oyun (indie, 2016-{end_year}, >=10 review)",
        f"Toplam taranan hipotez: {total_discovered:,} | Aksiyona-dönüşen bulgu: {len(actionable)}",
        "",
        METRIC_GLOSSARY,
    ]

    for family in sorted(by_family.keys()):
        items = sorted(by_family[family], key=lambda f: -abs(f.effect))
        explanation = FAMILY_EXPLANATIONS.get(family, "")
        lines.append(f"## {family} ({len(items)})")
        lines.append("")
        if explanation:
            lines.append(f"*{explanation}*")
            lines.append("")
        lines.append("| Bulgu | Yön | effect | q | n | n_base | grafik |")
        lines.append("|---|---|---|---|---|---|---|")
        for f in items:
            direction = "+" if f.direction == "positive" else "-"
            chart = Path(f.chart_path).name if f.chart_path else "-"
            q_str = "nan" if f.q_value != f.q_value else f"{f.q_value:.4f}"  # NaN != NaN
            lines.append(
                f"| {f.label} | {direction} | {f.effect:+.3f} | {q_str} | "
                f"{f.n:,} | {f.n_baseline:,} | {chart} |"
            )
        lines.append("")
        for f in items:
            try:
                claim = render_claim(f)
                lines.append(f"> **{f.label}** — {claim}")
                lines.append(">")
            except ValueError:
                pass  # yasak kelime denetiminden geçemedi, rapora eklenmiyor
        lines.append("")

    path = OUTPUT_DIR / "rapor.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"  rapor.md yazıldı ({len(actionable)} bulgu, {len(by_family)} aile) -> {path}")
    return path


def write_findings_contract(all_findings: list[Finding], universe_n: int,
                              snapshot: str = "march2025", end_year: int = 2025) -> Path:
    """findings.json'u yazar — n8n'in okuyacağı tam kanıt sözleşmesi.

    end_year: evrenin gerçek üst yıl sınırı (bkz. metrics.engaged_universe —
    artık sabit 2024 değil, snapshot'taki en son yıl). Sadece metadata
    metnine ("filter": "indie, 2016-X, ...") yansıması için taşınıyor,
    çağıran (run_all.py) engaged_universe()'in hesapladığı gerçek değeri
    geçirmeli — burada tekrar sabit kodlanmamalı.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    top_findings = select_top_findings(all_findings)
    attach_alternatives(top_findings, all_findings)
    rendered = render_findings(top_findings)

    contract = {
        "run_id": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "schema_version": SCHEMA_VERSION,
        "snapshot": snapshot,
        "universe": build_universe_metadata(universe_n, year_range=(2016, end_year)),
        "caveats": CAVEATS,
        "total_findings_discovered": len(all_findings),
        "total_findings_sent": len(rendered),
        "findings": rendered,
    }
    contract = _replace_nan_with_none(contract)

    path = OUTPUT_DIR / "findings.json"
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    log.info(f"  findings.json yazıldı: {len(all_findings)} bulgudan {len(rendered)} tanesi LLM'e gönderiliyor -> {path}")
    return path
