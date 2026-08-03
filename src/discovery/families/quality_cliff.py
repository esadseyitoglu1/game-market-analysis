"""Discovery Family — Kalite Uçurumu ve 'Kalite Tuzağı' (GERÇEK HESABA ÇEVRİLDİ)

BU DOSYA, insight_engine.py:741 insight_80pct_cliff(df)'in YERİNE GEÇER.

NEDEN GEREKLİYDİ (bkz. plan — Context bölümü, en kritik bulgu): eski fonksiyon
`df` parametresini ALIYORDU AMA GÖVDESİNDE BİR KEZ BİLE KULLANMIYORDU. "Kalite
Tuzağı" iddiası (90-95% bandının 85-90%'dan düşük görünürlükte olduğu) ve "her
review 30-50 satışa eşittir" gibi rakamlar TAMAMEN ELLE YAZILMIŞTI. Aynı iddia
visualizer.py:302-306'da da KOŞULSUZ bir ok/annotation olarak çiziliyordu.

GERÇEK VERİYLE TEST SONUCU (2026-08-03, bu dosya yazılırken yapıldı):
  85-90% bandı medyan visibility_pct: 0.782
  90-95% bandı medyan visibility_pct: 0.778
  Ham fark küçük ve pozitif yönde ("tuzak" iddiasıyla aynı yönde) ama
  Mann-Whitney U + etki büyüklüğü + bootstrap testinden GEÇEMEDİ — yani bu
  snapshot'ta "Kalite Tuzağı" iddiası İSTATİSTİKSEL OLARAK DOĞRULANAMADI.
  Bu, eski sistemin kanıtlanmamış bir iddiayı kesin gerçek gibi sunduğunun
  somut bir örneğidir.

Bu fonksiyon artık HER ÇALIŞTIRMADA gerçek hesabı yapar. Snapshot değişirse
(yeni oyunlar eklenirse) sonuç değişebilir — o yüzden statik değil, dinamiktir.
"""

import logging

import numpy as np
import pandas as pd

from src.discovery.base import Hypothesis, Finding
from src.discovery.gate import evaluate

log = logging.getLogger(__name__)

SCORE_BANDS = [0, 50, 60, 70, 75, 80, 85, 90, 95, 100]
SCORE_BAND_LABELS = ["<50%", "50-60%", "60-70%", "70-75%", "75-80%",
                     "80-85%", "85-90%", "90-95%", "95%+"]


def compute_score_band_stats(df: pd.DataFrame, min_reviews: int = 10) -> pd.DataFrame:
    """Her skor bandı için medyan görünürlük + örneklem büyüklüğünü hesaplar.
    visualizer.py:chart_80pct_cliff'in kullandığı gruplamanın AYNISI, ama
    review sayısı yerine (yaş yanlılığına açık) visibility_pct kullanıyor.
    """
    indie = df[df["is_indie"] & (df["total_reviews"] >= min_reviews)].copy()
    indie["score_band"] = pd.cut(indie["review_score"], bins=SCORE_BANDS,
                                   labels=SCORE_BAND_LABELS, right=False)
    stats = indie.groupby("score_band", observed=True).agg(
        medyan_review=("total_reviews", "median"),
        medyan_visibility=("visibility_pct", "median"),
        n=("total_reviews", "count"),
    ).reset_index()
    return stats


def test_quality_trap(df: pd.DataFrame, min_reviews: int = 10, min_n: int = 100) -> Finding | None:
    """'Kalite Tuzağı' iddiasını (90-95% bandı 85-90%'dan düşük görünürlükte)
    gerçek bir istatistiksel testle sınar. Bulgu gate'ten geçerse Finding
    döner, geçmezse None döner — yani iddia YALNIZCA kanıtlanırsa üretilir.
    """
    indie = df[df["is_indie"] & (df["total_reviews"] >= min_reviews)].copy()
    indie["score_band"] = pd.cut(indie["review_score"], bins=SCORE_BANDS,
                                   labels=SCORE_BAND_LABELS, right=False)

    combined_mask = indie["score_band"].isin(["85-90%", "90-95%"])
    sub = indie[combined_mask].reset_index(drop=True)
    if len(sub) < min_n * 2:
        return None

    values = sub["visibility_pct"].values
    group_mask = (sub["score_band"] == "90-95%").values

    hyp = Hypothesis(
        family="quality_trap", label="90-95% vs 85-90% skor bandı",
        mask=group_mask, baseline="matched", metric="visibility_pct",
        chart_hint="bar_comparison",
    )
    return evaluate(hyp, values, min_n=min_n)


def test_cliff_at_80(df: pd.DataFrame, min_reviews: int = 10, min_n: int = 100) -> Finding | None:
    """'%80 Uçurumu' iddiasını sınar: %80 üstü (Very Positive) oyunlar, %80
    altı oyunlara göre gerçekten daha görünür mü?
    """
    indie = df[df["is_indie"] & (df["total_reviews"] >= min_reviews)].copy().reset_index(drop=True)
    if len(indie) < min_n * 2:
        return None

    values = indie["visibility_pct"].values
    mask = (indie["review_score"] >= 80).values

    hyp = Hypothesis(
        family="cliff_80", label="Review skoru >=80% (Very Positive)",
        mask=mask, baseline="rest", metric="visibility_pct",
        chart_hint="bar_comparison",
    )
    return evaluate(hyp, values, min_n=min_n)
