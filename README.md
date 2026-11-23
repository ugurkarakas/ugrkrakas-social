# ugrkrakas-social

@ugrkrakas (Instagram) ve Uğur Karakaş (Facebook sayfası) için içerik deposu ve paylaşım otomasyonu.

Strateji: [@ugrkrakas İçerik Stratejisi](https://claude.ai/artifact/8q9BQq1rx9doYfjoWsbftj)

## Nasıl çalışır

1. Ham fotoğraf ve videolar `kaynak/` klasörüne konur.
2. Her içerik için `icerik/<slug>.json` yazılır (başlık, slaytlar, caption, soru, hashtag, anket).
3. `python3 araclar/uret.py icerik/<slug>.json` yayına hazır görselleri, `python3 araclar/reels.py icerik/<slug>.json` Reels videosunu üretir.
4. İçerik `takvim.csv`'ye tarihiyle eklenir ve `durum` = `hazir` yapılır.
5. Zamanlanmış görev her gün takvimdeki içeriği Windsor.ai üzerinden Instagram ve Facebook'a paylaşır.

Takvime yeni satır eklemek için zamanlanmış görevi değiştirmek gerekmez; görev takvimi her gün bu depodan okur.

## Klasörler

| Klasör | İçerik | Boyut |
| --- | --- | --- |
| `kaynak/` | Ham fotoğraf ve videolar | - |
| `icerik/` | İçerik tanımları (`_sablon.json` örnektir, yayınlanmaz) | - |
| `post/` | Tek görselli gönderiler | 1080x1350 |
| `carousel/<slug>/` | Carousel slaytları `01.jpg`, `02.jpg`... | 1080x1350 |
| `reels/` | Reels videoları `<slug>.mp4` | 1080x1920, 3-90 sn |
| `story/` | Günün gönderisini duyuran story | 1080x1920 |
| `anket/` | Anket story'leri (sticker elle eklenir) | 1080x1920 |
| `araclar/` | Görsel (`uret.py`) ve Reels (`reels.py`) üreticileri | - |
| `fonts/` | Inter (SIL Open Font License) | - |

## İçerik türleri (`tur`)

- `gorsel`: tek görsel gönderi, `post/<slug>.jpg`
- `carousel`: kapak + içerik slaytları + kapanış, `carousel/<slug>/`
- `reels`: `reels/<slug>.mp4`, kapak olarak `post/<slug>.jpg` kullanılır

## Takvim (`takvim.csv`)

| Sütun | Açıklama |
| --- | --- |
| `tarih` | YYYY-MM-DD (İstanbul saatine göre) |
| `slug` | `icerik/<slug>.json` dosyasının adı |
| `durum` | `hazir` olanlar paylaşılır, `taslak` olanlar atlanır |

## Günlük paylaşım akışı

1. Facebook sayfası: gönderi görseli + caption
2. Instagram: tür neyse o (görsel, carousel ya da Reels) + caption
3. Instagram ilk yorum: `ilk_yorum` hashtag'leri
4. Instagram story: `story/<slug>-story.jpg`
5. Anket story'si varsa: görsel otomatik atılmaz; anket sticker'ı API ile eklenemediği için uygulamadan elle paylaşılır.

Caption = `caption` + boş satır + `soru`.

## Tasarım dili

Sade ve premium: bol boşluk, Inter yazı tipi, siyah / beyaz / açık gri (#F5F5F7), fotoğraf ön planda.
Reels: yavaş yakınlaşan fotoğraflar ya da video klipler, konuşur gibi başlıklar ve altyazı tarzı detay cümleleri, siyah kapanış kartı.
Müzik `araclar/muzik.py` ile kodla sentezlenir (hazır parça kullanılmaz, telif sorunu yoktur); tarzlar: `yaz`, `aksam`, `enerji`.

İçerik tonu: dikkat çeken rotalar, unutulmaz deneyimler, iyi restoranlar ve özel anlar. Fiyat, ücret ve bütçe konuşulmaz. Mekan ve kural bilgileri yayından önce güncel kaynaktan doğrulanır.

## Fotoğraf kuralları

- Kendi fotoğrafların her zaman önceliklidir.
- Stok fotoğraf yalnızca [Unsplash](https://unsplash.com/license) gibi ticari kullanıma açık kaynaklardan alınır; Google Görseller kullanılmaz.
- Stok fotoğraf kullanılan içeriklerde `fotograf_kredisi` doldurulur ve caption'ın sonuna eklenir.
- Stok fotoğraf kullanılan içerik "ben gittim, ben çektim" gibi sunulmaz.


## Günlük akış (takvim.csv: tarih,slot,slug,durum)

- ogle (12:04): kaydırmalı gönderi (carousel) + öğlen hikayesi (akşam reels'inin "Biliyor muydun?" kartı).
- aksam (~19:00): reels + duyuru hikayesi.

## Günlük hikayeler

- Öğlen: `story/<slug>-ogle.jpg` (içerik dosyasındaki `ogle` alanından: "Biliyor muydun?" bilgisi + akşamki gönderinin duyurusu).
- Akşam: `story/<slug>-story.jpg` (günün gönderisiyle birlikte).
- Anket görseli `anket/<slug>-anket.jpg` isteğe bağlı olarak elle, anket çıkartmasıyla paylaşılır.
