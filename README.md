# TSG Hoffenheim bilet nöbetçisi

TSG Hoffenheim ticket shop'unda kale arkası / ev sahibi tarafındaki tükenmiş
bloklardan bilet çıktığı anda Telegram'dan mesaj atar. GitHub Actions üzerinde 10 dakikada bir çalışır,
sunucuya gerek yoktur.

Şu an izlenen maç: **TSG Hoffenheim – Borussia Dortmund, 05.09.2026** (performance ID `3188`).

---

## Nasıl çalışıyor?

Shop'un kendi arka uç JSON'unu okur — sayfa kazıma (scraping) veya tarayıcı yok,
üç basit GET isteği var:

1. `GET /shop?shopid=104&wes=empty_session_104&language=1&nextstate=2`
   → sunucu taze bir oturum kimliği (`wes`) verir
2. `GET /shops/104/events/3188?wes=<wes>`
   → oturumu "ürün seçimi" adımına getirir
3. `GET /backend/saalinterface?wes=<wes>&getSaalInfos=3188`
   → her blok için `sitze_frei` (boş koltuk) döner

Her kontrolde son durum `state.json`'a yazılır. Mesaj **yalnızca bir blok
0'dan >0'a geçtiğinde** gider — yani bilet açık kaldığı sürece her turda
spam gelmez. Blok tekrar 0'a düşüp sonra yeniden açılırsa yeni mesaj gelir.

---

## Kurulum (yaklaşık 10 dakika)

### 1. Telegram botunu oluştur

1. Telegram'da **@BotFather**'a yaz.
2. `/newbot` gönder, bota bir isim ve `...bot` ile biten bir kullanıcı adı ver.
3. BotFather sana şuna benzer bir **token** verir:
   `8123456789:AAF3xQ...` — bunu bir kenara not et, kimseyle paylaşma.

### 2. chat_id'ni bul

1. Az önce oluşturduğun bota Telegram'dan **/start** yaz (bot sana mesaj
   atabilsin diye bu şart).
2. Tarayıcıda şu adresi aç (`<TOKEN>` yerine kendi token'ın):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Gelen JSON'da `"chat":{"id":123456789,...}` kısmındaki sayı senin
   **chat_id**'in. (Eksi ile başlıyorsa bir grup demektir, o da olur.)

### 3. Repoyu oluştur

Repo **private** olacak. Kota hesabı önemli, kısaca:

GitHub Free planda private repolar için ayda **2.000 Actions dakikası** var ve
her çalışma en az 1 dakika sayılır. 10 dakikalık aralık = günde 144 çalışma
≈ **144 dakika/gün**. Tek maç için (05.09.2026'ya kadar ~6 gün) toplam
~900 dakika → ücretsiz kotanın içinde, rahat. Ama bunu **ay boyunca sürekli
açık bırakırsan kota biter** (~14 günde). Maçtan sonra iş akışını durdur
(Actions → ⋯ → Disable workflow) veya repoyu public yap; public repolarda
Actions dakikaları sınırsızdır.

**gh CLI ile (en kolay — repoyu da secret'ları da tek seferde kurar):**

```bash
cd tsg-ticket-watcher
git init -b main
git add .
git commit -m "TSG bilet nöbetçisi"

gh repo create tsg-ticket-watcher --private --source=. --remote=origin --push

gh secret set TELEGRAM_BOT_TOKEN     # sorunca token'ı yapıştır
gh secret set TELEGRAM_CHAT_ID       # sorunca chat_id'yi yapıştır
```

**gh yoksa, elle:** github.com → New repository → adı `tsg-ticket-watcher`,
görünürlük **Private**, README/gitignore ekleme → Create. Sonra:

```bash
cd tsg-ticket-watcher
git init -b main
git add .
git commit -m "TSG bilet nöbetçisi"
git remote add origin https://github.com/<kullanıcı-adın>/tsg-ticket-watcher.git
git push -u origin main
```

### 4. Secrets'ları gir

`gh secret set` kullandıysan bu adım bitti. Elle yaptıysan repoda
**Settings → Secrets and variables → Actions → New repository secret**:

| İsim | Değer |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather'ın verdiği token |
| `TELEGRAM_CHAT_ID` | 2. adımda bulduğun sayı |

### 5. Actions'ı aç ve test et

1. **Actions** sekmesine git, uyarı çıkarsa
   *"I understand my workflows, go ahead and enable them"* de.
2. Soldan **TSG bilet nöbetçisi** → sağ üstte **Run workflow**.
3. `test` kutusunu **işaretle** ve çalıştır → Telegram'a test mesajı gelmeli.
4. Sonra `test` işaretsiz bir kez daha çalıştır → gerçek kontrolü yapar.

> İlk gerçek çalıştırmada büyük ihtimalle **"Blok F: 1 yer"** mesajı gelecek —
> depodaki başlangıç durumu hepsini 0 kabul ediyor, F'de ise şu an 1 koltuk var.
> Bu bir hata değil, sistemin çalıştığının kanıtı.

---

## Ayarlar

`.github/workflows/watch.yml` içindeki `env` bloğundan:

- `WATCH_BLOCKS` — izlenecek bloklar, virgülle. Varsayılan:
  `"B,C,D,E,F,G1,G2,H1,H2,I,O,Q,R,S1,S2,T,U,V"` — yani 30.08.2026 itibarıyla
  **tükenmiş olan tüm ev sahibi blokları**. Mantık:
  - **O, P, Q, R, S1, S2, T, U, V** = kale arkası / ev sahibi tarafı. Bunu
    shop'un kendi uyarısından biliyoruz: *"Zutritt in die Blöcke O, P, Q, R,
    S1, S2, T, U und V mit Gästefankleidung nicht gestattet"* (bu bloklara
    deplasman forması ile giriş yok).
  - **A** ve **W** listede yok — deplasman bölgesi (şu an yer var).
  - **J, K, L, M, N, P** listede yok — zaten bilet satışta, beklemeye gerek yok.
    Sadece maça girmek istiyorsan bunları şimdi alabilirsin.
  - **101–104 / 201–223 / 301–322** listede yok — bunlar loca, pahalı.

  Tüm blokları fiyat ve doluluk ile görmek için: `python list_blocks.py`
  Çıktının sonunda kopyalayıp yapıştırabileceğin hazır bir `WATCH_BLOCKS`
  satırı var.
- `PERFORMANCE_ID` — maç kimliği. Başka bir maça geçmek için
  `https://tickets.tsg-hoffenheim.de/shop?shopid=104&wes=empty_session_104&language=1&nextstate=2&lpShortcutId=46`
  adresini aç, maçın **Tickets** bağlantısına tıkla, açılan sayfanın
  kaynağında `data-performanceid="...."` değerini al.
- Kontrol sıklığı — `cron: "*/10 * * * *"`. GitHub'ın alt sınırı 5 dakikadır
  (`*/5`), yoğun saatlerde birkaç dakika gecikebilir; daha hızlısı için
  script'i kendi bilgisayarında veya bir VPS'te 30–60 saniyede bir çalıştırman
  gerekir. Private repoda aralığı düşürmek kotayı da hızlandırır (bkz. 3. adım).

## Anahtarlar nereye giriyor?

İki ayrı yer var, karıştırma:

| Nerede çalışıyor | Anahtarlar nereden geliyor |
|---|---|
| **GitHub Actions** (asıl kullanım) | Repo **Secrets**. `.env` dosyası yok ve olmamalı. |
| **Kendi bilgisayarın** (deneme) | Klasördeki `.env` dosyası (veya `export`). |

GitHub tarafında `.env` kullanmıyoruz çünkü repoya konan her dosya repoda
kalır — token'ı oraya yazmak onu commit geçmişine gömmek demek. Bunun yerine
GitHub'ın şifreli Secrets deposuna koyuyoruz; workflow çalışırken
`${{ secrets.TELEGRAM_BOT_TOKEN }}` satırı onu ortam değişkeni olarak enjekte
ediyor, log'larda da otomatik olarak `***` diye maskeleniyor.

## Yerelde çalıştırma

```bash
pip install requests
cp .env.example .env       # sonra .env'i açıp kendi değerlerini yaz
python check_tickets.py --dry-run   # mesaj atmadan durumu göster
python check_tickets.py --test      # sadece Telegram'ı test et
python check_tickets.py             # normal kontrol
python list_blocks.py               # tüm blokları fiyatıyla listele
```

`.env` `.gitignore`'da olduğu için GitHub'a gitmez. İstersen `.env` yerine
`export TELEGRAM_BOT_TOKEN="..."` da kullanabilirsin.

## Mac'te yerel nöbetçi (daha güvenilir, daha hızlı)

GitHub'ın cron'u tembel: yeni repolarda ilk zamanlanmış çalışma saatler
sonra başlayabiliyor, `*/10` gibi tam dakikalar zamanlayıcının en yoğun
anlarına denk geldiği için çalışmalar geciktiriliyor ya da tamamen atlanıyor.
İade bilet saniyeler içinde gidiyorsa bu iyi değil.

Aynı script'i Mac'inde 2 dakikada bir çalıştırmak için:

```bash
cp .env.example .env      # token ve chat_id'yi doldur
bash local/install.sh     # ya da: bash local/install.sh 60
```

Kurulum bir sanal ortam açar, `launchd` görevi yazar ve hemen başlatır.

```bash
tail -f ~/Library/Logs/tsg-ticket-watcher.log   # canlı log
bash local/uninstall.sh                          # kaldır
```

Mac uykuya geçerse kontrol durur, uyanınca devam eder; sürekli açık tutmak
için ayrı bir terminalde `caffeinate -i` çalıştır.

**İkisini birden açık bırakırsan** aynı bilet için iki mesaj gelebilir
(durum dosyaları ayrı). Yerel kurulum çalışmaya başladıktan sonra GitHub
tarafını kapatmak en temizi: Actions → sağdaki ⋯ → Disable workflow.

## Bilinmesi gerekenler

- **Bekleme odası:** shop yoğun olduğunda SAP'ın sanal bekleme odasına
  (`waitingroom.ticketing.cloud.sap`) yönlendiriyor. Script bunu tanır, o turu
  sessizce atlar, durumu bozmaz ve bir sonraki çalışmada tekrar dener. Log'da
  *"Shop yogun -- SAP bekleme odasina yonlendirildik"* yazar; bu hata değildir.

- GitHub, **60 gün commit gelmeyen** repolarda zamanlanmış iş akışlarını
  otomatik durdurur. Bu script durum değiştikçe `state.json`'u commit'lediği
  için normalde sorun olmaz; yine de uzun sessizlikten sonra Actions
  sekmesinden açık olduğunu kontrol et.
- Bildirim, biletin **satın alındığını** garanti etmez; sadece haber verir.
  Popüler maçlarda iade biletler saniyeler içinde gidebilir.
- Shop yazılımı güncellenirse üç adımdan biri bozulabilir; o durumda Actions
  çalışması kırmızıya döner (`HATA: ...` satırıyla).
- Script dakikada bir istekten daha seyrek, kibar bir hızda çalışır. Aralığı
  agresif biçimde düşürmemekte fayda var.
