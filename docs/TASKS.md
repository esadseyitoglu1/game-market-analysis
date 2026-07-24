# TASKS.md — Görev Takibi

## Faz Durumu

- [x] Faz 1 — Proje scaffold (dizin, git, belgeler)
- [x] Faz 2 — `src/fetcher.py` (SteamSpy + Steam Store API)
- [x] Faz 3 — `src/processor.py` (Kaggle CSV temizleme, her iki snapshot)
- [x] Faz 4 — `src/analyzer.py` (5 analiz fonksiyonu)
- [x] Faz 5 — `src/visualizer.py` (6 indie-focused grafik, koyu tema)
- [x] Faz 6 — `src/merge_pipeline.py` (UPSERT: güncelle + yeni ekle)
- [x] `main.py` güncellendi (`--fetch`, `--snapshot` argümanları)
- [ ] **Faz 7 — Content Brief** (`docs/CONTENT_BRIEF.md`) ← SIRADAKI
- [ ] Faz 8 — Co-op TDS grafiği visualizer'a ekle
- [ ] Faz 9 — n8n otomasyonu

---

## Hemen Yapılacak: Content Brief

`docs/CONTENT_BRIEF.md` oluştur. Her episode için:

```
## Episode 1: Hook
"89,000 Steam oyununun verisini indirdim"

Grafik/Veri: Kaggle dataset ekran görüntüsü
Ana mesaj: "Veri olmadan pazar kararı vermek körlük"
CTA: "Nasıl yaptım? Seri devam ediyor"
```

6 episode için aynı formatı doldur.
CONTEXT.md'deki "Episode planı" bölümüne bak.

---

## Sıradaki Model İçin Talimat

1. `docs/CONTEXT.md` oku — tüm bağlam orada
2. `src/visualizer.py` oku — mevcut 6 grafik ne yapıyor
3. Content Brief'i yaz
4. Co-op grafiğini ekle
5. scratch_coop.py'ı sil (geçici dosya)

## Çalışan Komutlar

```bash
python main.py                           # tam pipeline
python main.py --fetch                   # API + pipeline
python -m src.visualizer                 # 6 grafik üret
python -m src.merge_pipeline --pages 1   # canlı güncelleme
python -m src.analyzer                   # sadece analiz
```
