"""Discovery — ortak veri yapıları: Hypothesis ve Finding.

Bu dosya, keşif motorunun "sözleşmesi"dir. Her hipotez üretici (generators.py,
ileride families/*.py) bir Hypothesis nesnesi üretir; gate.py bunu değerlendirip
ya bir Finding döndürür ya da None (bulgu reddedildi) döndürür.

NEDEN BÖYLE TASARLANDI (bkz. plan — "Mimari — GENİŞLETİLMİŞ"):
Kullanıcı sistemin tag'lerle sınırlı kalmayıp "istediği sütunları kullanıp
zibilyon tane" hipotez üretebilmesini istedi. Bunu güvenli yapmanın yolu,
hipotezin NEREDEN geldiğini (tag mi, achievements sayısı mı, stüdyo tekrarı mı)
gate.py'nin hiç bilmemesidir — gate sadece bir bool mask (grup üyeliği) görür.
Yani yeni bir hipotez türü eklemek, gate.py'ye HİÇBİR dokunuş gerektirmez.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class Hypothesis:
    """Test EDİLECEK bir aday — henüz istatistiksel olarak doğrulanmamış.

    Bir generator fonksiyonu (örn. "co-op'lu oyunlar vs olmayanlar") bu nesneyi
    üretir. `mask`, evrendeki (universe DataFrame) hangi satırların bu grubun
    ÜYESİ olduğunu gösteren bir bool array'dir — grup büyüklüğü mask.sum().

    Örnek: "Co-op etiketi olan oyunlar daha mı görünür?" sorusu için:
        Hypothesis(
            family="category_effect",
            label="Co-op",
            mask=df["categories_list"].apply(lambda c: "Co-op" in c).values,
            baseline="rest",
            metric="visibility_pct",
        )
    """
    family: str          # "tag_single", "tag_pair", "numeric_split", "entity_repeat", ...
    label: str            # İnsan-okunur isim: "Visual Novel + FPS", "Co-op", "achievements>20"
    mask: np.ndarray       # bool array, evren üzerinde grup üyeliği (True = grupta)
    baseline: str          # "rest" (evrenin geri kalanı) | "matched" (eşleştirilmiş taban)
    metric: str            # hangi kolonu karşılaştıracağız: "visibility_pct" | "review_score"
    chart_hint: str = ""   # narrative/chart_selector.py bunu doldurur, generator boş bırakabilir


@dataclass
class Finding:
    """Gate'ten GEÇMİŞ, kanıtlanmış bir bulgu. LLM'e / narrative render'a giden
    tek veri kaynağı budur — hiçbir serbest metin, sadece bu alanlardan üretilir.
    """
    family: str
    label: str
    metric: str

    n: int                          # grup büyüklüğü
    n_baseline: int                 # karşılaştırılan taban büyüklüğü

    effect: float                   # rank-biserial correlation, [-1, 1]
    effect_ci: tuple[float, float]  # bootstrap %95 güven aralığı

    p_value: float
    q_value: float                  # BH-FDR düzeltilmiş p-değeri

    direction: str                  # "positive" | "negative" — YÖN VERİDEN GELİR
    group_median: float
    baseline_median: float

    confidence: str = "medium"      # "high" | "medium" — narrative bunu kullanır
    fragile: bool = False           # confound kontrolünden geçemedi, LLM'e gitmemeli

    evidence: dict = field(default_factory=dict)     # ham destekleyici sayılar
    exemplars: list[dict] = field(default_factory=list)  # 3 gerçek oyun adı (LLM'in uydurmasını önler)

    chart_hint: Optional[str] = None  # "bar_comparison" | "box_plot" | "trend_line" | ...
    chart_path: Optional[str] = None  # chart_selector.py doldurur

    def as_dict(self) -> dict:
        """findings.json'a yazılacak sözlük — tuple'ları listeye çevirir (JSON uyumu)."""
        d = self.__dict__.copy()
        d["effect_ci"] = list(self.effect_ci)
        return d
