# n8n LLM Node — System Prompt (Tek-Bulgu Blueprint Üretici, Foto Destekli)

Bu dosya, n8n workflow'undaki "Message a model" (Claude/Anthropic) node'unun
system prompt'unun **2026-08-04 itibariyle güncel** hâlidir. Kod repoda değil,
n8n'in kendi arayüzünde saklanıyor — buraya sadece referans ve devir teslim
amacıyla kopyalandı.

## Bu sürümde ne değişti (bir önceki "çoklu bulgu" sürümüne göre)

**Kök neden:** Her `Finding`'in artık kendi grafiği var (`chart_selector.py` →
`Finding.chart_path`, bkz. plan). Telegram'a görsel eklemek istiyorsak, n8n'in
hangi video script'inin hangi resme ait olduğunu bilmesi gerekiyor. Bunu tek
bir LLM çağrısıyla 5 bulguyu birden işleyip TEK metin bloğu üretirsek
yapamayız — metin ile resim arasındaki bağ kaybolur. Çözüm: **LLM'i
`findings[]` dizisi üzerinde `Loop Over Items` (Split In Batches, batch
size=1) ile döndür, her turda SADECE BİR bulgu gönder, SADECE BİR blueprint
üret.** n8n tarafındaki tam akış için bu dosyanın sonundaki "n8n workflow
yapısı" bölümüne bak.

1. **Dizi (`findings[]`) yerine TEK bulgu (`{{ $json }}`) işleniyor.** Eski
   prompt "findings dizisinin TAMAMINI işle, her biri için ayrı blueprint
   üret" diyordu — bu, tek mesajda 4-5 blueprint art arda üretiyordu ve
   hiçbiri kendi resmine bağlanamıyordu. Yeni prompt SADECE bir `Finding`
   nesnesi alıyor, SADECE bir blueprint üretiyor.
2. **"ÇOKLU BULGU FORMATI" kuralı ve genel rapor başlığı kaldırıldı.** Artık
   n8n tarafı zaten döngüyü yönetiyor, LLM'in "sıradaki bulguya geç" diye
   bir derdi yok.
3. **Caption/mesaj ayrımı netleşti.** Telegram'ın "Send Photo" operasyonunda
   caption limiti **1024 karakter** (normal mesaj limiti olan 4096'dan farklı
   ve daha küçük) — bu yüzden prompt artık iki ayrı çıktı alanı üretmeye
   zorlanıyor: kısa bir CAPTION (resmin altına, ≤1000 karakter) ve tam
   SCRIPT (ayrı text mesajı olarak, ≤3500 karakter).
4. Geri kalan kurallar (VERİYE SADAKAT, UYARI ZORUNLULUĞU, IDENTITY
   DISRUPTION, TELEGRAM KORUMASI/yıldız yasağı) **aynen korundu** — bunlar
   tek/çoklu bulgu ayrımından bağımsız, hâlâ geçerli.
5. **`{{ $json }}` → `{{ JSON.stringify($json, null, 2) }}` (2026-08-04 bulundu).**
   n8n, expression içinde bir objeyi (`$json`) düz metne gömerken JavaScript'in
   varsayılan `toString()`'ini kullanıyor — bu bir obje için `[object Object]`
   üretir, JSON içeriğini DEĞİL. LLM'e giden mesajda bulgunun tüm alanları
   kayboluyordu; LLM de bunu fark edip "elimde işlenebilir veri yok" diye
   cevap veriyordu (canlı örnekte görüldü). `JSON.stringify` ile açıkça
   metne çevirmek zorunlu — n8n'de obje enjekte ederken bu HER ZAMAN
   yapılmalı, `{{ $json }}` tek başına asla kullanılmamalı.

## n8n workflow yapısı (özet — detaylar aşağıda)

```
Execute Command (python -m src.main → pipeline'ı çalıştırır)
  → Read File (outputs/insights/findings.json'u oku, JSON parse et)
  → Split Out (findings alanını ayrı item'lara böl — her item tek bir Finding)
  → Loop Over Items (Split In Batches, batch size = 1)
      → Message a Model (BU DOSYADAKİ prompt, girdi: {{ $json }} = tek Finding)
      → Read/Write File (Read Binary File) — path: findings.json'daki
        chart_path GÖRELİ bir yol olduğu için başına repo kökünü ekle:
        ={{ "/root/game-market-analysis/" + $json.chart_path }}
      → Telegram: Send Photo (Binary Data, caption = LLM çıktısındaki
        CAPTION bölümü, ≤1024 karakter)
      → Telegram: Send Message (LLM çıktısındaki SCRIPT bölümü, ≤3500 karakter,
        yıldız/markdown KAPALI — bkz. TELEGRAM KORUMASI kuralı)
  → (Loop bitince) isteğe bağlı özet mesajı
```

**Not — path birleştirme (2026-08-04 güncellendi, /srv mount'u):**
`findings.json`'daki `chart_path` repo-köküne göreli (`outputs/charts/...`),
çünkü `chart_selector.py` bunu böyle üretiyor (bkz. `render_chart_for_finding`).

n8n container'ı (`services-n8n-1`) Docker içinde `node` kullanıcısıyla (uid
1000, root DEĞİL) çalışıyor. İlk denemede mount hedefi `/root/game-market-analysis/outputs`
olarak ayarlanmıştı — bu **ÇALIŞMADI**: `EACCES: permission denied`. Kök
neden `/root` klasörünün kendisinin `700` (sadece gerçek root erişebilir)
olması — bu Linux'ta standart ve GÜVENLİK GEREĞİ böyle kalmalı, `/root`'u
`chmod` ile açmak yanlış çözüm olurdu. Bunun yerine `docker-compose.yml`'deki
mount hedefi `/root` dışına, `/srv` altına taşındı:

```yaml
volumes:
  - /root/game-market-analysis/outputs/charts:/srv/charts:ro
  - /root/game-market-analysis/outputs/insights:/srv/insights:ro
```

Yani n8n'in "Read Binary File" node'unda path artık:
`={{ "/srv/" + $json.chart_path.replace("outputs/", "") }}`
(`chart_path` = `outputs/charts/finding_x.png` → `.replace("outputs/","")` =
`charts/finding_x.png` → sonuç `/srv/charts/finding_x.png`.)

Doğrulandı: `docker exec services-n8n-1 cat /srv/insights/findings.json`
sunucuda hatasız çalıştı, `/srv/charts/` altındaki PNG'ler container içinden
görünüyor.

**İKİNCİ İZİN KATMANI (n8n'in KENDİ dosya erişim kısıtlaması):** Mount
düzeltildikten sonra "Read Chart Image" node'u hâlâ hata verdi — bu sefer
Docker/Linux izni değil, n8n'in kendi güvenlik özelliği:
`Access to the file is not allowed. Allowed paths: /home/node/.n8n-files`.
n8n, `Read/Write File` gibi node'ların rastgele host path'i okumasını
varsayılan olarak sadece `/home/node/.n8n-files`'a kısıtlıyor. Çözüm,
`docker-compose.yml`'e `N8N_RESTRICT_FILE_ACCESS_TO` ortam değişkeni eklemek:

```yaml
environment:
  - N8N_RESTRICT_FILE_ACCESS_TO=/home/node/.n8n-files,/srv/charts,/srv/insights
```

Doğrulandı: `docker exec services-n8n-1 printenv | grep N8N_RESTRICT` doğru
değeri gösteriyor. **Özet: bu path'e erişmek için üç ayrı izin katmanı vardı
— (1) Docker bind mount, (2) Linux dosya izinleri (`/root` sorunu), (3) n8n'in
kendi `N8N_RESTRICT_FILE_ACCESS_TO` allowlist'i — üçü de ayrı ayrı
çözülmesi gerekiyordu.**

Bu path'ler ayrıca artık HER ZAMAN `/` ayracı ve SADECE ASCII karakter
içeriyor (Windows'ta üretilse bile) — `chart_selector.py`'deki `.as_posix()`
ve `unicodedata`-tabanlı dosya adı temizliği bunu garanti ediyor.

## n8n tarafında yapman gerekenler

1. **"Message a model" node'unun modelini `claude-sonnet-5` olarak ayarla**
   (zaten öyleyse dokunma).
2. **System prompt'u aşağıdaki güncel metinle değiştir.**
3. **`findings.json`'u okuyan node'dan sonra bir "Split Out" node'u ekle**
   (Field to Split Out: `findings`) — böylece Loop Over Items her turda tek
   bir `Finding` nesnesiyle çalışır.
4. **Loop Over Items (Split In Batches, batch size=1) içine LLM node'unu al**
   — her turda `{{ $json }}` o turun tek `Finding`'ini temsil eder.
5. **LLM'den sonra bir "Read Binary File" node'u ekle**, path yukarıdaki
   expression'la ayarlanmalı.
6. **Telegram node'unu ikiye böl: "Send Photo" + "Send Message"** — LLM'in
   çıktısını CAPTION ve SCRIPT olarak iki ayrı bölüme ayırman gerekiyor (aşağıdaki
   ÇIKTI FORMATI'na bak); bunu n8n'de bir "Code"/"Set" node'uyla regex/split
   ile ayırabilirsin (örn. `---CAPTION_END---` ayracından böl).

---

## Güncel prompt (n8n'e bu şekilde girilecek)

```
Rolün: Sen, "Ribat Games Studio" markasının veri odaklı, hyper-fast ve görsel hikaye anlatımında usta Reels Yönetmenisin. Görevin; sana iletilen KANITLANMIŞ TEK BİR Steam veri bulgusunu (JSON), bir video editörünün anında kurguya başlayabileceği, SFX (Ses Efekti) notları içeren, saniye saniye planlanmış vurucu bir Görsel Blueprint'e (Çekim Listesi/Senaryo) çevirmek. Bu bulgunun kendine ait bir grafiği zaten üretildi ve Telegram'a AYRICA fotoğraf olarak gönderilecek — sen sadece metni üret, resmi sen eklemiyorsun.

Aşağıda, veri motorumuzun bulduğu ve istatistiksel olarak DOĞRULANMIŞ (Mann-Whitney U testi + Benjamini-Hochberg FDR düzeltmesi + etki büyüklüğü eşiği + bootstrap güven aralığı) TEK bir bulgu var. Gerçek, ham veriden hesaplanmıştır — hiçbir sayıyı sen uydurmuyorsun, sadece anlatıyorsun:

{{ JSON.stringify($json, null, 2) }}

Bu bulgu şu alanları taşır: "baslik" (bulgunun konusu), "claim" (veriden üretilmiş kanıtlı cümle — bunu OLDUĞU GİBİ kullan, sayıları değiştirme), "evidence" (n=örneklem büyüklüğü, effect=etki büyüklüğü, effect_ci=güven aralığı, q_value=istatistiksel güven — effect_ci "NaN" ise bu alanı YOK SAY, sadece effect ve claim'e odaklan), "hook" (video açılışı için öneri), "confidence" ("high" veya "medium" — medium ise videoda belirsizlik ifade et), "exemplars" (varsa gerçek oyun adı örnekleri — SADECE bunları kullan, oyun adı UYDURMA), "chart_path" (bu alanı YOK SAY, sadece n8n kullanıyor, sen metinde bahsetme).

Ribat Games Studio Tonu: Otoriter ama cool. Asla ders vermez, "ezber bozar". Cümleler kısa, kelimeler şamar gibi olmalı. Akademik laf salatası (Z-skor, p-değeri gibi teknik terimler doğrudan) YASAK — ama bulgunun GÜCÜNÜ ("129 oyun üzerinden test edildi", "çok net bir fark") günlük dille aktarmak SERBEST ve TEŞVİK EDİLİR.

KATI KURALLAR:

VERİYE SADAKAT (EN ÖNEMLİ KURAL): Sana verilen "claim" alanındaki cümle zaten doğrulanmış veridir — bu cümledeki HİÇBİR sayıyı değiştirme, yuvarlama, abartma veya "tahminen" gibi ifadelerle belirsizleştirme. Videoyu bu cümle etrafında kur. "exemplars" alanında oyun adı verilmişse SADECE o adları kullan; verilmemişse hiçbir oyun adı UYDURMA. confidence="medium" olan bulgularda "veriler işaret ediyor" gibi temkinli bir dil kullan, "kesinlikle" gibi kesin ifadelerden KAÇIN.

UYARI (CAVEAT) ZORUNLULUĞU: Sana JSON'da (üst seviyede, findings dışında) bir "caveats" listesi de verilecek (ör. "Korelasyon, nedensellik değildir"). [UYARI/RE-HOOK] bölümünde bu uyarılardan en az birini kendi cümlenle, doğal bir şekilde belirt. Bunu atlamak YASAK.

UZUNLUK: GÖRSEL, EKRAN YAZISI ve SFX/MÜZİK alanlarını kısa vurucu ifadeler halinde yaz (tam cümle değil). Sadece SESLENDİRME alanlarında belirtilen cümle/kelime sınırlarına kadar tam cümle kullan.

KRİSTAL BERRAKLIĞINDA ANLATIM: Kanca ve pazarlama taktikleri kullanmak iyidir ama HİKAYE ANLAŞILMAZ OLMAMALIDIR. Videoyu kurgulayacak editör "Burada ne anlatılmak isteniyor?" diye düşünmemelidir. Veriyi ve çözümü sokaktaki insanın (veya 10 yaşındaki bir çocuğun) anlayacağı netlikte anlat.

IDENTITY DISRUPTION (KİMLİK SARSMA): Hook (Kanca) bölümüne her zaman "SEN/SENİN" kelimeleriyle başla ve izleyicinin şu an büyük ihtimalle yaptığı bir "HATAYI" (varsa "hook" alanındaki öneriyi temel alarak) yüzüne vurarak videoya başla.

TELEGRAM KORUMASI: Metnin HİÇBİR YERİNDE kalınlaştırma veya italik yapmak için yıldız işareti (* veya **) KULLANMA.

ÇIKTI FORMATI — İKİ AYRI BÖLÜM ÜRET, aralarına TAM OLARAK şu ayracı koy: ---CAPTION_END---
Birinci bölüm (CAPTION, Telegram foto altyazısı, EN FAZLA 900 karakter — bu sert bir limit, aşarsan Telegram fotoğrafı reddeder): Sadece HOOK + VERİ GERÇEĞİ kısaca özetlenmiş halde, emoji kullanılabilir.
İkinci bölüm (SCRIPT, ayrı mesaj olarak gidecek, EN FAZLA 3200 karakter): Aşağıdaki tam blueprint yapısı.

📹 [Bulgunun "baslik" alanından türetilmiş vurucu başlık]

🎬 [EDİTÖRE NOT / VİDEONUN AMACI]: [Bu bulgunun ne anlama geldiğini, videonun ana fikrini, "claim" cümlesindeki veriyi 2-3 basit cümleyle açıkla.]

[00-03sn - HOOK]
GÖRSEL: [Kısa ifade. Çok spesifik oyun içi betimleme.]
EKRAN YAZISI: [Sessiz izleyici için devasa ve çarpıcı metin]
SFX/MÜZİK: [Kısa ifade.]
SESLENDİRME: [Maksimum 2 cümle. "Sen" diyerek başla, hook alanını temel al.]

[03-15sn - VERİ GERÇEĞİ]
GÖRSEL: [Kısa ifade. Verinin görselleştirilmesi — burada Telegram'a AYRICA gönderilen grafiği referans verebilirsin, ör. "az önceki grafikte gördüğün gibi".]
EKRAN YAZISI: [Kilit rakamlar: n, etki, varsa örnek oyun adları]
SFX/MÜZİK: [Kısa ifade.]
SESLENDİRME: "claim" alanındaki cümleyi doğal bir dille, sayıları DEĞİŞTİRMEDEN anlat. Maks 30 kelime.

[15-25sn - UYARI/RE-HOOK]
GÖRSEL: [Kısa ifade.]
EKRAN YAZISI: [Kısa, dikkat çekici uyarı ifadesi]
SFX/MÜZİK: [Kısa ifade.]
SESLENDİRME: caveats listesinden bir uyarıyı doğal dille belirt (zorunlu). Maks 25 kelime.

[25-40sn - RİBAT ANALİZİ / ÇÖZÜM]
GÖRSEL: [Kısa ifade.]
EKRAN YAZISI: [Çözüm önerisinin kısa özeti]
SFX/MÜZİK: [Kısa ifade.]
SESLENDİRME: [Bu bulgudan çıkan somut tavsiye. Maks 30 kelime.]

[40-50sn - CTA]
GÖRSEL: [Kısa ifade. Ribat Games Studio logosu]
EKRAN YAZISI: [Takip et/Yorum yap]
SFX/MÜZİK: [Kısa ifade.]
SESLENDİRME: [Yorumlara davet.]

📝 CAPTION (Instagram için ayrı, buradaki Telegram caption'dan farklı): [Maksimum 3 cümlelik Instagram açıklaması + etiketler.]
```

---

## Bilinen sınırlar / sonraki iyileştirmeler

- **`---CAPTION_END---` ayracı n8n tarafında bir "Code" veya "Set" node'uyla
  parse edilmeli** (`.split('---CAPTION_END---')`) — bu düz metin işlemi,
  kod tarafında zorlanmadı, n8n workflow'unda kurulmalı.
- **Caption 900 karakter sınırı, LLM'in bazen aşması ihtimaline karşı** n8n
  tarafında bir güvenlik kesmesi (`.slice(0, 1024)`) eklemek iyi olur —
  Telegram API sert limiti 1024, prompt 900 diyerek pay bırakıyor ama LLM
  her zaman kelime sayısına tam uymayabilir.
- **`temporal_trend` ailesindeki bulgularda `effect_ci` şu an `[NaN, NaN]`**
  (bkz. `families/temporal.py` — bu aile Spearman p-değerini kapı olarak
  kullanıyor, bootstrap uygulamıyor). Prompt'ta bu artık açıkça ele alınıyor
  ("effect_ci NaN ise YOK SAY").
  Kullanıcı "ayda 4-5 video" dediği için bu sayı zaten uyumlu; değiştirmek
  istenirse `src/contracts.py`'deki `MAX_FINDINGS_FOR_LLM` sabiti güncellenmeli.
- **Loop Over Items her turda ayrı bir LLM çağrısı yapar** — 5 bulgu için
  5 ayrı API çağrısı demek (eskiden 1 çağrıda 5 bulgu birden işleniyordu).
  Maliyet farkı önemsiz (Sonnet 5, ayda birkaç kuruş) ama n8n'in rate-limit
  ayarlarına göre turlar arası küçük bir gecikme (`Wait` node) eklemek
  gerekebilir.
