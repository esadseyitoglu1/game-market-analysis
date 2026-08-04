# Canlı Veri Güncelleme — merge_pipeline.py (2026-08-04)

## Neden bu doküman var

Kullanıcı sordu: "biz bu sistemi nasıl güncel verilerle canlı tutucaz, 2026
bitiyor biz 2024 verisi gösteriyoruz." Araştırma şunu netleştirdi: Kaggle'daki
`artermiloff/steam-games-dataset` sürekli güncellenen canlı bir kaynak DEĞİL
— Mart 2025'te alınmış tek seferlik bir anlık görüntü. Otomatik olarak tekrar
tekrar çeksek bile hep aynı bayat veriyi indiririz.

Gerçek çözüm: **Steam'in kendi resmi Web API'sinden** düzenli veri çekmek.
Bu iş iki parçaya ayrılıyor, bugün SADECE birincisi tamamlandı:

1. **Veri toplama katmanı** (`src/merge_pipeline.py`, `src/fetcher.py`) — TAMAMLANDI.
2. **Discovery motoruna bağlama** (`metrics.py:load_universe()`'in bu canlı
   veriyi de okuması) — YAPILMADI, kasıtlı olarak ertelendi (aşağıda neden).

## Ne yapıldı

### `src/fetcher.py` — `fetch_full_app_list_by_appid()`

Steam'in **resmi** `IStoreService/GetAppList` endpoint'i eklendi. Önemli fark:

| Kaynak | Sıralama | Sonuç |
|---|---|---|
| SteamSpy `fetch_app_list()` (eski, hâlâ var) | **Popülerliğe göre** | İlk sayfalar hep AAA/çok oynanan oyunlar, indie kuyruğu hiç görünmez |
| Steam `fetch_full_app_list_by_appid()` (YENİ) | **appid sırasına göre** | TÜM katalog taranır, indie dahil — popülerlik ayrımı yapmaz |

`ISteamApps/GetAppList` (v2, eski/deprecated) DEĞİL bu — Valve o endpoint'i
"artık ölçeklenmiyor" diyerek kullanımdan kaldırdı, resmi öneri
`IStoreService/GetAppList`. `STEAM_API_KEY` gerektiriyor (`.env`'de, ücretsiz,
`steamcommunity.com/dev/apikey`'den alındı).

### `src/merge_pipeline.py` — `add_new_games()` güncellendi

- `full_catalog=True` (varsayılan) olduğunda "yeni oyun" havuzu artık
  SteamSpy'ın popülerlik listesi değil, Steam'in tam katalogu.
- **Bulunan bug (gerçek veriyle test edilirken):** İlk versiyon `new_ids`'i
  küçükten büyüğe sıralayıp ilk `max_new` kadarını işliyordu — bu, appid=10
  (Counter-Strike, 2000 yılından) gibi ÇOK ESKİ oyunları "yeni" diye
  işletiyordu. Steam'de appid'ler zaman içinde artan sırada atandığı için
  düzeltme: **en BÜYÜK appid'lerden başlanıyor** (`sorted(new_ids, reverse=True)`)
  — bu gerçekten en son eklenen oyunları getiriyor. Test edildi: appid
  5037970/5034420/5033040 gibi "Coming soon" / Ağustos 2026 tarihli, gerçek
  yeni indie oyunlar geldi (biri "Free To Play, Indie, Casual" tag'li).

### CLI kullanımı

```bash
# Sadece mevcut oyunları güncelle (review/fiyat/CCU tazele)
python -m src.merge_pipeline --pages 5

# + yeni oyunları da ekle (Steam'in TAM katalogundan, indie dahil)
python -m src.merge_pipeline --pages 5 --add-new --max-new 200

# Eski davranış (sadece SteamSpy popülerlik listesinden yeni oyun ara)
python -m src.merge_pipeline --add-new --no-full-catalog
```

Çıktı: `data/processed/steam_games_live.csv` (mevcut `march2025`/`may2024`
snapshot dosyalarına DOKUNMUYOR, ayrı bir dosya).

## Neden discovery motoruna HENÜZ bağlanmadı

`src/metrics.py:load_universe()` şu an sadece `march2025`/`may2024` diye iki
sabit snapshot adı biliyor (`processor.py`'deki `snapshots` dict'i). Bunlara
üçüncü bir `"live"` snapshot'ı eklemek — ve `gate.py`'deki tüm istatistiksel
testlerin, yaş-normalizasyonun (`visibility_pct`, kohort bazlı) canlı veriyle
de doğru çalıştığından emin olmak — kendi başına bir doğrulama gerektiren ayrı
bir iş. Yanlış yapılırsa (örn. yeni eklenen oyunların `release_year`'ı
eksik/hatalı gelirse) `add_visibility_pct()`'in kohort ortalaması 0.5'ten
sapabilir, bu da TÜM gate sonuçlarını sessizce bozar. Bilerek ayrı bir
oturuma bırakıldı — bkz. plan dosyasındaki "SONRAKİ OTURUM İÇİN KALAN İŞ".

**Şu an için `steam_games_live.csv` diskte birikiyor ama hiçbir şey onu
okumuyor.** Bu kasıtlı bir ara durum, hata değil.

## n8n'de nasıl kurulur (AYRI workflow, mevcut haftalık/aylık video
pipeline'ından bağımsız)

1. Yeni bir n8n workflow oluştur (mevcut "Game Market Analysis" workflow'una
   dokunma).
2. **Schedule Trigger**: ayda bir (örn. her ayın 1'i, 03:00) — bu haftalık
   video pipeline'ından FARKLI bir ritim, çünkü appdetails çağrıları göreceli
   ağır ve rate limit'e tabi.
3. **SSH Execute Command**:
   ```
   cd /root/game-market-analysis && ./venv/bin/python -m src.merge_pipeline --pages 10 --add-new --max-new 300
   ```
4. Şimdilik bunun ötesi yok — `steam_games_live.csv` sunucuda birikir,
   discovery motoruna bağlanınca (sonraki oturum) otomatik kullanılmaya
   başlar. Telegram'a bir şey gönderilmez, bu adım sessiz çalışır.

## Sunucu kurulumu

`.env` dosyasına `STEAM_API_KEY` eklenmesi gerekiyor — GitHub'a GİTMEDİ
(`.gitignore`'da zaten `.env` var), sunucuda ayrıca elle eklenmesi/SSH ile
kopyalanması gerekiyor.
