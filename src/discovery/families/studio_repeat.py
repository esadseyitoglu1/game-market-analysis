"""Discovery Family — Stüdyo Tekrarı (Entity Repeat)

Bu, kullanıcının "benim de görmediğim malzeme" isteğinin doğrudan karşılığı:
`developers` kolonu eski sistemde (anomaly_detector.py, insight_engine.py)
HİÇ KULLANILMAMIŞTI. Soru: bir stüdyonun İKİNCİ (ve sonraki) oyunları, İLK
oyununa göre daha mı görünür?

NEDEN AYRI BİR DOSYA (generators.py'de değil): generate_entity_repeat_hypotheses()
sadece aday ÜRETİR ama "ilk oyun" ve "sonraki oyunlar" grupları evrenin GERİ
KALANINA göre değil, BİRBİRİNE göre karşılaştırılmalı (tek-oyunluk stüdyolar
karşılaştırmaya hiç girmemeli). Bu, generic evaluate_batch akışına tam
uymuyor — bu yüzden mask'leri doğru evrende kurup gate.evaluate()'i doğrudan
çağıran özel bir fonksiyon gerekiyor.
"""

import logging

import pandas as pd

from src.discovery.base import Hypothesis
from src.discovery.gate import evaluate

log = logging.getLogger(__name__)


def test_studio_repeat(df: pd.DataFrame, entity_column: str = "developers_list",
                        min_games: int = 2, min_n: int = 50, metric: str = "visibility_pct"):
    """Bir stüdyonun ilk oyunu ile sonraki oyunlarının görünürlüğünü karşılaştırır.

    Döndürür: Finding | None. Sadece tekrar-stüdyoların (>=min_games oyunlu)
    oyunları evren olarak kullanılır — tek-oyunluk stüdyolar "ilk oyun"
    kavramına sahip olmadığı için karşılaştırmaya hiç girmez.
    """
    work = df.copy()
    work["_entity"] = work[entity_column].apply(lambda lst: lst[0] if lst else None)
    work = work.dropna(subset=["_entity", "release_date"])
    work = work.sort_values("release_date")

    studio_counts = work["_entity"].value_counts()
    repeat_studios = studio_counts[studio_counts >= min_games].index
    if len(repeat_studios) == 0:
        return None

    is_first_game = pd.Series(False, index=work.index)
    for studio in repeat_studios:
        studio_rows = work[work["_entity"] == studio]
        is_first_game.loc[studio_rows.index[0]] = True

    relevant = work["_entity"].isin(repeat_studios)
    sub = work[relevant].reset_index(drop=True)

    # sub üzerinde ilk-oyun bayrağını yeniden hesapla (index'ler reset edildiği
    # için work'teki is_first_game doğrudan taşınamıyor — release_date'e göre
    # zaten sıralı olduğundan, her stüdyonun sub içinde İLK GÖRÜLEN satırı
    # onun ilk oyunudur).
    sub_is_first = pd.Series(False, index=sub.index)
    seen = set()
    for i, studio in enumerate(sub["_entity"]):
        if studio not in seen:
            sub_is_first.iloc[i] = True
            seen.add(studio)

    if len(sub) < min_n * 2:
        log.info(f"  [{entity_column}] studio_repeat: evren çok küçük (n={len(sub)}), atlandı")
        return None

    values = sub[metric].values
    mask_later = (~sub_is_first).values  # "sonraki oyunlar" = grup

    hyp = Hypothesis(
        family="entity_repeat",
        label=f"{entity_column.replace('_list', '')}: ilk oyun vs sonraki oyunlar",
        mask=mask_later, baseline="matched", metric=metric,
        chart_hint="before_after",
    )
    finding = evaluate(hyp, values, min_n=min_n)
    if finding:
        finding.evidence["n_studios"] = len(repeat_studios)
    return finding
