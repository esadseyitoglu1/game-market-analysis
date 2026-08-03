"""Discovery — Feature Registry (Kolon Sınıflandırma)

NEDEN BU DOSYA VAR (bkz. plan — "Mimari — GENİŞLETİLMİŞ"):
Kullanıcının isteği: sistem tag'lerle sınırlı kalmasın, "istediği sütunları
kullanıp zibilyon tane" hipotez üretebilsin. Bunu elle yazılmış 9 fonksiyon
yerine, kolonun TİPİNE bakıp otomatik uygun jeneratörü çağıran genel bir
mekanizmayla yapıyoruz. Yeni bir kolon eklendiğinde (processor.py'nin ürettiği
CSV şeması değişirse) burada bir satır eklemek yeterli — generators.py'ye veya
gate.py'ye HİÇ dokunulmaz.

Dört kolon tipi:
  - categorical_list: bir oyunun BİRDEN FAZLA değer taşıyabildiği liste kolonu
    (tags_list, categories_list, genres_list). Jeneratör: her benzersiz değeri
    "var/yok" grubu olarak dener (tag_single), ikili kombinasyonları da dener
    (tag_pair).
  - numeric: sürekli/ayrık sayısal kolon (achievements, dlc_count,
    average_playtime_forever, required_age, discount, peak_ccu,
    metacritic_score). Jeneratör: medyandan veya ampirik eşiklerden ikiye
    böler (düşük/yüksek), karşılaştırır.
  - boolean: zaten 0/1 veya True/False olan kolon (windows, mac, linux).
    Jeneratör: direkt var/yok karşılaştırması.
  - entity: bir "kimlik" kolonu (developers_list, publishers_list) — aynı
    stüdyonun/yayıncının birden fazla oyunu olabilir. Jeneratör: entity'nin
    İLK oyunu ile SONRAKİ oyunlarını karşılaştırır (studio_repeat ailesi).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnSpec:
    kind: str        # "categorical_list" | "numeric" | "boolean" | "entity"
    min_n: int        # bu kolon tipi için minimum grup büyüklüğü
    chart_hint: str   # narrative/chart_selector.py'nin varsayılan seçimi


# NOT — min_n değerleri plan'daki ilk 9-aile tablosundan ampirik olarak
# doğrulanmış değerlerdir (bkz. plan: tag_single=50, tag_pair=30, price_band=100,
# category_effect=100, studio_repeat=2, critic_gap=30, playtime_success=100).
# categorical_list ve entity için tag_pair/studio_repeat değerleri; numeric ve
# boolean için price_band/category_effect değerleri kullanıldı.
COLUMN_REGISTRY: dict[str, ColumnSpec] = {
    "tags_list":                    ColumnSpec("categorical_list", min_n=50, chart_hint="bar_comparison"),
    "categories_list":              ColumnSpec("categorical_list", min_n=100, chart_hint="bar_comparison"),
    "genres_list":                  ColumnSpec("categorical_list", min_n=50, chart_hint="bar_comparison"),

    "achievements":                 ColumnSpec("numeric", min_n=100, chart_hint="box_plot"),
    "dlc_count":                    ColumnSpec("numeric", min_n=100, chart_hint="box_plot"),
    "average_playtime_forever":     ColumnSpec("numeric", min_n=100, chart_hint="box_plot"),
    "median_playtime_forever":      ColumnSpec("numeric", min_n=100, chart_hint="box_plot"),
    "required_age":                 ColumnSpec("numeric", min_n=100, chart_hint="box_plot"),
    "discount":                     ColumnSpec("numeric", min_n=100, chart_hint="box_plot"),
    "peak_ccu":                     ColumnSpec("numeric", min_n=100, chart_hint="box_plot"),
    "price":                        ColumnSpec("numeric", min_n=100, chart_hint="box_plot"),

    "windows":                      ColumnSpec("boolean", min_n=100, chart_hint="bar_comparison"),
    "mac":                          ColumnSpec("boolean", min_n=100, chart_hint="bar_comparison"),
    "linux":                        ColumnSpec("boolean", min_n=100, chart_hint="bar_comparison"),

    "developers_list":              ColumnSpec("entity", min_n=2, chart_hint="before_after"),
    "publishers_list":              ColumnSpec("entity", min_n=2, chart_hint="before_after"),
}

# categorical_list kolonlarında "tür" olarak SAYILMAMASI gereken meta-etiketler.
# Eski anomaly_detector.py bunları hiç filtrelemiyordu — "Cats", "1980s", "Cozy"
# gibi tanımlayıcı ama tür-olmayan etiketleri "pazar anomalisi" ilan ediyordu.
# Bu liste her jeneratörde (tag_single, tag_pair) uygulanmalı.
IGNORE_VALUES = {
    "Indie", "Singleplayer", "Multiplayer", "2D", "3D", "Casual",
    "Great Soundtrack", "Atmospheric", "Story Rich", "Colorful",
    "Cute", "Relaxing", "Family Friendly", "Difficult",
    # Meta-tag'ler + gereksiz genellemeler; tür/mekanik olmayan tanımlayıcılar
    "Steam Achievements", "Steam Cloud", "Steam Trading Cards",
    "Full controller support", "Partial Controller Support",
    "Stats", "Steam Leaderboards", "Steam Workshop",
}

# İÇERİK UYGUNLUĞU FİLTRESİ — bunlar meta-tag değil, gerçek/istatistiksel olarak
# geçerli bulgular üretebilir (bkz. Adım 4: "Hentai" tag'i gate'ten gerçekten
# geçti, effect=+0.47, tamamen doğru bir istatistik). Ama Ribat Games Studio
# markasının Reels/TikTok içeriğinde kullanılması UYGUNSUZ. Bu, IGNORE_VALUES'tan
# AYRI bir liste — IGNORE_VALUES "bu bir tür değil" derken, bu liste "bu bir
# tür ama marka için uygun değil" der. generators.py'de İKİSİ birden uygulanır.
BRAND_UNSAFE_VALUES = {
    "Hentai", "Nudity", "Sexual Content", "NSFW", "Mature",
    "Gore", "Violent", "Sexual Content", "Adult Only",
}


def get_spec(column: str) -> ColumnSpec | None:
    return COLUMN_REGISTRY.get(column)


def columns_by_kind(kind: str) -> list[str]:
    return [col for col, spec in COLUMN_REGISTRY.items() if spec.kind == kind]
