#!/usr/bin/env python3
"""@ugrkrakas Reels üreticisi.

icerik/<slug>.json içindeki "reels.sahneler" listesinden 1080x1920, 30 fps MP4 üretir.
Her sahne bir fotoğraf ya da bir video klip olabilir; üstüne konuşur gibi yazılmış,
kısa altyazı tarzı metinler gelir. Sonda siyah bir "kaydet / takip et" kartı vardır.

  "reels": {
    "sahneler": [
      {"video": "roma-sokak.mp4", "baslangic": 2.0, "sure": 3.0,
       "metin": "Roma'ya gidiyorsan bunu kaydet"},
      {"foto": "roma-merdiven.jpg", "etiket": "Kural 1",
       "metin": "Güne erken başla", "alt": "Sabah 8'den önce merdivenler neredeyse boş."}
    ]
  }

Alanlar:
  foto / video   kaynak/ altındaki dosya (biri zorunlu)
  baslangic      video klipte kaçıncı saniyeden alınacağı (varsayılan 0)
  sure           sahne süresi, saniye (varsayılan: alt metin varsa 3.6, yoksa 2.8)
  fotolar        birden fazla fotoğraf: vuruşa denk gelen hızlı kesmelerle art arda gösterilir
                 (her biri "dosya.jpg" ya da {"foto": "dosya.jpg", "odak": [x, y]})
  vurus_basina   çok fotoğraflı sahnede her fotoğrafın kaç vuruş kalacağı (varsayılan 2)
  etiket         küçük üst yazı (Kural 1, 02 gibi)
  metin          ana cümle
  alt            ana cümlenin altında beliren detay cümlesi

  odak          fotoğrafın dikey kırpımda nereden ortalanacağı, ör. [0.4, 0.5]
  kart          arka planda video/foto dönerken altta beliren buzlu cam bilgi kartı
                (otel, restoran, yemek, müze... her şehir için aynı şablon):
                {"tur": "Otel önerisi", "isim": "Hotel Adı", "konum": "Eixample, Barselona",
                 "puan": 4.6, "fiyat": "€145", "fiyat_alt": "gecelik", "not": "Teraslı oda iste"}
                tur, puan, fiyat, fiyat_alt, not isteğe bağlı; isim zorunlu.
                Kartlı sahnede "metin" varsa ekranın üstünde başlık olarak görünür.

Müzik: araclar/muzik.py ile kodla üretilen telifsiz ritim eklenir.
  "muzik": {"tarz": "yaz" | "aksam" | "enerji", "tohum": 7}   kapatmak için "muzik": null
  Hazır telifsiz parça (Pixabay Music vb.), kaynak/ altında:
  "muzik": {"dosya": "muzik/sitar-story.mp3", "bpm": 100, "baslangic": 0, "ses": 1.0}
  Parça videodan kısaysa başa sarılır; sonda 1.5 sn'de kısılır. Kredi caption'a yazılır.

Kullanım:
  python3 araclar/reels.py icerik/<slug>.json
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import muzik  # noqa: E402
import uret  # noqa: E402

KOK = uret.KOK
W, H = uret.STORY
FPS = 30
GECIS = 0.35
YAKINLASMA = 0.06
KENAR = 96
GENISLIK = W - 2 * KENAR


def yumusak(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ---------- görüntü kaynakları ----------

class FotoKaynak:
    def __init__(self, dosya, odak=(0.5, 0.5)):
        bw, bh = int(W * (1 + YAKINLASMA)), int(H * (1 + YAKINLASMA))
        img = ImageOps.exif_transpose(Image.open(KOK / "kaynak" / dosya)).convert("RGB")
        self.img = ImageOps.fit(img, (bw, bh), Image.LANCZOS, centering=tuple(odak))
        if RENK != RENKLER[None]:
            # fotoğraflara da videolarla aynı renk derecelendirmesi (gren hariç)
            vf = ",".join(p for p in RENK.split(",") if not p.startswith("noise"))
            out = subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{bw}x{bh}",
                 "-i", "-", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                input=self.img.tobytes(), capture_output=True, check=True).stdout
            self.img = Image.frombytes("RGB", (bw, bh), out)

    def kare(self, ilerleme):
        # kesmeden sonra hızlı, sonra yavaşlayan bir yakınlaşma hissi
        e = 1 - (1 - ilerleme) ** 2.2
        olcek = 1 + YAKINLASMA * (1 - e)
        cw, ch = int(W * olcek), int(H * olcek)
        bw, bh = self.img.size
        x, y = (bw - cw) // 2, (bh - ch) // 2
        return self.img.crop((x, y, x + cw, y + ch)).resize((W, H), Image.BILINEAR)

    def kapat(self):
        pass


RENKLER = {
    # varsayılan: canlı ve net
    None: "eq=contrast=1.06:saturation=1.12,unsharp=5:5:0.6",
    # film: sıcak, hafif soluk, yumuşak kontrast, ince vinyet ve gren (belgesel / Apple havası)
    "film": ("eq=contrast=1.03:saturation=0.86:gamma=1.03:brightness=0.01,"
             "colorbalance=rs=0.05:bs=-0.05:rm=0.03:bm=-0.03:rh=0.02:bh=-0.03,"
             "curves=all='0/0.03 0.5/0.5 1/0.97',vignette=angle=PI/6,"
             "unsharp=5:5:0.4,noise=alls=3:allf=t"),
}
RENK = RENKLER[None]


class VideoKaynak:
    """Video klip: dikey kadraja kırpılır, istenirse yavaşlatılır (sinematik), hafif renk derecelendirmesi."""
    def __init__(self, dosya, baslangic, sure, hiz=1.0, odak_x=0.5):
        vf = (f"setpts=PTS/{hiz},scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H}:(iw-{W})*{odak_x}:(ih-{H})/2,fps={FPS},"
              + RENK)
        self.p = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-ss", str(baslangic), "-t", str(sure * hiz + 0.5),
             "-i", str(KOK / "kaynak" / dosya), "-vf", vf, "-an",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE,
        )
        self.son = None

    def kare(self, ilerleme):
        veri = self.p.stdout.read(W * H * 3)
        if len(veri) == W * H * 3:
            self.son = Image.frombytes("RGB", (W, H), veri)
        return self.son if self.son is not None else Image.new("RGB", (W, H))

    def kapat(self):
        self.p.kill()
        self.p.wait()
        self.p.stdout.close()


# ---------- yazı katmanları ----------

def _maske():
    m = Image.new("L", (1, H), 0)
    for y in range(H):
        t = y / H
        a = max(0.35 * max(0.0, 1 - t / 0.28) ** 1.6, 0.8 * max(0.0, (t - 0.42) / 0.58) ** 1.5)
        m.putpixel((0, y), int(255 * a))
    return m.resize((W, H))


MASKE = _maske()
SIYAH = Image.new("RGB", (W, H), (0, 0, 0))


MEKTUP = False  # "stil": "mektup" -> yazısız, serif başlıklı sinematik seyahat filmi
MASKE_HAFIF = MASKE.point(lambda v: int(v * 0.35))


def karart(img):
    """Fotoğraf/videonun alt ve üstünü yazı okunacak kadar koyulaştırır."""
    return Image.composite(SIYAH, img, MASKE_HAFIF if MEKTUP else MASKE)


def serif(boyut, agirlik="Medium", italik=False):
    f = ImageFont.truetype(str(uret.FONT / ("CormorantGaramond-Italic.ttf" if italik else "CormorantGaramond.ttf")), boyut)
    f.set_variation_by_axes([{"Light": 300, "Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700}[agirlik]])
    return f


def mektup_katmanlari(sahne, ilk):
    """Mektup stili: ilk sahnede ortada büyük serif başlık, diğerlerinde (varsa) küçük italik not."""
    ana = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    alt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if ilk:
        bf = serif(190, "Medium")
        metin = sahne["metin"].upper()
        c = ImageDraw.Draw(ana)
        # geniş harf aralığı
        ara = 18
        gen = sum(c.textlength(ch, font=bf) for ch in metin) + ara * (len(metin) - 1)
        x, y = (W - gen) / 2, H * 0.40
        for ch in metin:
            c.text((x, y), ch, font=bf, fill=uret.BEYAZ + (245,))
            x += c.textlength(ch, font=bf) + ara
        if sahne.get("alt"):
            uret.yaz(ana, (KENAR, int(y + 240)), sahne["alt"], serif(66, "Medium", True), uret.BEYAZ,
                     GENISLIK, 1.2, hiza="orta")
        return ana, alt
    if sahne.get("metin"):
        uret.yaz(ana, (KENAR, H - 560), sahne["metin"], serif(64, "Regular", True), uret.BEYAZ,
                 GENISLIK, 1.2, hiza="orta")
    return ana, alt


def altyazi_kutusu(metin, fnt, y, katman):
    """Instagram'ın kendi altyazı stilini andıran, yarı saydam yumuşak kutulu metin."""
    c = ImageDraw.Draw(katman)
    sh = int(fnt.size * 1.32)
    for s in uret.satirlar(metin, fnt, GENISLIK - 60):
        tw = c.textlength(s, font=fnt)
        x = (W - tw) / 2
        c.rounded_rectangle((x - 26, y - 12, x + tw + 26, y + sh - 2), radius=18, fill=(0, 0, 0, 125))
        c.text((x, y), s, font=fnt, fill=(255, 255, 255, 255))
        y += sh + 6
    return y


# ---------- bilgi kartı (otel / restoran / yemek, şehirden bağımsız şablon) ----------

KART_KENAR = 64
KART_ALT = 400          # Instagram'ın alt arayüzüne (caption, butonlar) girmesin
KART_IC = 52


def _yildiz(c, cx, cy, r, renk):
    import math
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    c.polygon(pts, fill=renk)


def _pin(c, x, y, boy, renk):
    r = boy * 0.36
    cx, cy = x + r, y + r
    c.polygon([(cx - r * 0.82, cy + r * 0.45), (cx + r * 0.82, cy + r * 0.45), (cx, y + boy)], fill=renk)
    c.ellipse((cx - r, cy - r, cx + r, cy + r), fill=renk)
    c.ellipse((cx - r * 0.4, cy - r * 0.4, cx + r * 0.4, cy + r * 0.4), fill=(0, 0, 0, 0))


def kart_hazirla(kart):
    """Kartın (içerik katmanı, şekil maskesi, kutu) üçlüsünü bir kez çizer; her karede sadece bulanıklık değişir."""
    kw = W - 2 * KART_KENAR
    ic = kw - 2 * KART_IC
    gri = (215, 215, 220)
    tur_f = uret.font(uret.ARA, 28)
    isim_f = uret.font(uret.BASLIK, 66)
    konum_f = uret.font(uret.KUCUK, 36)
    puan_f = uret.font(uret.ARA, 34)
    fiyat_f = uret.font(uret.BASLIK, 72)
    falt_f = uret.font(uret.KUCUK, 32)
    not_f = uret.font(uret.GOVDE, 34)

    # yükseklik hesabı
    isim_h = uret.blok_yuksekligi(kart["isim"], isim_f, ic, 1.08)
    not_h = uret.blok_yuksekligi(kart.get("not", ""), not_f, ic, 1.3) if kart.get("not") else 0
    y = KART_IC
    if kart.get("tur") or kart.get("puan"):
        y += 58
    y += isim_h + 10
    if kart.get("konum"):
        y += 56
    if kart.get("fiyat"):
        y += 40 + 2 + 36 + 80
    if not_h:
        y += (24 if kart.get("fiyat") else 36) + not_h
    kh = y + KART_IC - 8

    x0 = KART_KENAR
    y0 = H - KART_ALT - kh
    kutu = (x0, y0, x0 + kw, y0 + kh)

    maske = Image.new("L", (W, H), 0)
    ImageDraw.Draw(maske).rounded_rectangle(kutu, radius=44, fill=255)

    k = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    c = ImageDraw.Draw(k)
    c.rounded_rectangle(kutu, radius=44, fill=(12, 12, 16, 110), outline=(255, 255, 255, 60), width=2)
    x, y = x0 + KART_IC, y0 + KART_IC

    if kart.get("tur") or kart.get("puan"):
        if kart.get("tur"):
            uret.harfli(k, (x, y), kart["tur"], tur_f, uret.BEYAZ, seffaflik=200)
        if kart.get("puan"):
            pm = f"{kart['puan']:.1f}".replace(".", ",") if isinstance(kart["puan"], (int, float)) else str(kart["puan"])
            tw = c.textlength(pm, font=puan_f)
            px = x0 + kw - KART_IC - tw
            c.text((px, y - 6), pm, font=puan_f, fill=uret.BEYAZ + (255,))
            _yildiz(c, px - 30, y + 14, 17, (255, 204, 77, 255))
        y += 58

    y = uret.yaz(k, (x, y), kart["isim"], isim_f, uret.BEYAZ, ic, 1.08) + 10

    if kart.get("konum"):
        _pin(c, x, y + 4, 36, gri + (255,))
        c.text((x + 40, y), kart["konum"], font=konum_f, fill=gri + (255,))
        y += 56

    if kart.get("fiyat"):
        y += 20
        c.line((x, y, x + ic, y), fill=(255, 255, 255, 55), width=2)
        y += 2 + 36
        c.text((x, y - 8), kart["fiyat"], font=fiyat_f, fill=uret.BEYAZ + (255,))
        if kart.get("fiyat_alt"):
            fw = c.textlength(kart["fiyat"], font=fiyat_f)
            c.text((x + fw + 18, y + 30), kart["fiyat_alt"], font=falt_f, fill=gri + (255,))
        y += 80

    if not_h:
        y += 24 if kart.get("fiyat") else 36
        uret.yaz(k, (x, y), kart["not"], not_f, gri, ic, 1.3)

    return k, maske, kutu


def kart_uygula(img, hazir, a):
    """a: 0..1 giriş animasyonu. Kart alttan kayarak ve belirerek gelir, arkası buzlu cam gibi bulanık."""
    if a <= 0:
        return img
    k, maske, kutu = hazir
    kay = int(70 * (1 - a))
    x0, y0, x1, y1 = kutu
    bolge = (x0, max(0, y0 - 40), x1, min(H, y1 + 40))
    bulanik = img.crop(bolge).filter(ImageFilter.GaussianBlur(28))
    tam = img.copy()
    tam.paste(bulanik, (bolge[0], bolge[1] - kay))
    m = maske.transform(maske.size, Image.AFFINE, (1, 0, 0, 0, 1, kay))
    if a < 1:
        m = m.point(lambda v: int(v * a))
    img = Image.composite(tam, img, m)
    kk = k.transform(k.size, Image.AFFINE, (1, 0, 0, 0, 1, kay))
    img.alpha_composite(alfali(kk, a))
    return img


def sahne_katmanlari(sahne, ilk):
    """(ana metin katmanı, detay metin katmanı) döndürür."""
    if MEKTUP:
        return mektup_katmanlari(sahne, ilk)
    ana = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    alt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    etiket_f = uret.font(uret.ARA, 30)
    if sahne.get("kart"):
        # kartlı sahne: metin ekranın üstünde kısa başlık, bilgiler kartta
        if sahne.get("metin"):
            y = 300
            if sahne.get("etiket"):
                uret.harfli(ana, (KENAR, y - 70), sahne["etiket"], etiket_f, uret.BEYAZ,
                            seffaflik=235, hiza="orta", genislik=GENISLIK)
            uret.yaz(ana, (KENAR, y), sahne["metin"], uret.font(uret.BASLIK, 84 if ilk else 72),
                     uret.BEYAZ, GENISLIK, 1.08, hiza="orta")
        return ana, alt
    if ilk:
        # İlk sahne: büyük, net bir giriş cümlesi (hook) ekranın üst kısmında
        y = 380
        if sahne.get("etiket"):
            uret.harfli(ana, (KENAR, y - 80), sahne["etiket"], etiket_f, uret.BEYAZ,
                        seffaflik=230, hiza="orta", genislik=GENISLIK)
        uret.yaz(ana, (KENAR, y), sahne["metin"], uret.font(uret.BASLIK, 108), uret.BEYAZ,
                 GENISLIK, 1.08, hiza="orta")
        if sahne.get("alt"):
            altyazi_kutusu(sahne["alt"], uret.font(uret.KUCUK, 42), H - 640, alt)
        return ana, alt

    bf = uret.font(uret.BASLIK, 78)
    af = uret.font(uret.KUCUK, 42)
    bh = uret.blok_yuksekligi(sahne["metin"], bf, GENISLIK, 1.1)
    ah = len(uret.satirlar(sahne.get("alt", ""), af, GENISLIK - 60)) * (int(af.size * 1.32) + 6)
    y = H - 520 - ah - (40 if ah else 0) - bh
    if sahne.get("etiket"):
        uret.harfli(ana, (KENAR, y - 70), sahne["etiket"], etiket_f, uret.BEYAZ,
                    seffaflik=235, hiza="orta", genislik=GENISLIK)
    y = uret.yaz(ana, (KENAR, y), sahne["metin"], bf, uret.BEYAZ, GENISLIK, 1.1, hiza="orta") + 40
    if sahne.get("alt"):
        altyazi_kutusu(sahne["alt"], af, y, alt)
    return ana, alt


def golgeli(katman, guc=0.6, yaricap=18):
    """Yazının arkasına yumuşak bir gölge ekler; açık renkli fotoğraflarda okunurluğu korur."""
    a = katman.getchannel("A").filter(ImageFilter.GaussianBlur(yaricap)).point(lambda v: int(min(255, v * guc * 1.6)))
    golge = Image.new("RGBA", katman.size, (0, 0, 0, 0))
    golge.putalpha(a)
    golge.alpha_composite(katman)
    return golge


def alfali(katman, alfa):
    if alfa >= 1:
        return katman
    k = katman.copy()
    k.putalpha(katman.getchannel("A").point(lambda v: int(v * alfa)))
    return k


def isaret_katmani(konum=""):
    """Sol üstte konum, sağ üstte @ugrkrakas imzası (kapanış kartı hariç tüm karelerde)."""
    k = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    c = ImageDraw.Draw(k)
    if konum:
        uret.harfli(k, (KENAR - 6, 152), konum, uret.font(uret.ARA, 30), uret.BEYAZ, seffaflik=225)
    f = uret.font(uret.KUCUK, 34)
    hw = c.textlength(uret.HANDLE, font=f)
    c.text((W - KENAR + 6 - hw, 150), uret.HANDLE, font=f, fill=uret.BEYAZ + (225,))
    return golgeli(k, guc=0.5, yaricap=10)


ISARET = None


def kapanis(veri):
    r = veri.get("reels", {})
    if MEKTUP:
        k = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        y = uret.yaz(k, (KENAR, H // 2 - 140), r.get("kapanis", ""), serif(96, "Medium", True),
                     uret.BEYAZ, GENISLIK, 1.15, hiza="orta") + 50
        uret.yaz(k, (KENAR, y), r.get("kapanis_alt", ""), uret.font(uret.GOVDE, 38), (161, 161, 166),
                 GENISLIK, 1.4, hiza="orta")
        uret.harfli(k, (KENAR, H - 460), uret.HANDLE, uret.font(uret.ARA, 34), uret.BEYAZ,
                    aralik=0.04, hiza="orta", genislik=GENISLIK, buyuk=False)
        return k.convert("RGB")
    k = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    cta = r.get("kapanis", veri.get("cta", "Kaydet, gidince aç."))
    bf = uret.font(uret.BASLIK, 96)
    bh = uret.blok_yuksekligi(cta, bf, GENISLIK, 1.08)
    y = (H - bh) // 2 - 80
    y = uret.yaz(k, (KENAR, y), cta, bf, uret.BEYAZ, GENISLIK, 1.08, hiza="orta") + 40
    uret.yaz(k, (KENAR, y), r.get("kapanis_alt", "Daha fazla rota için takip et."),
             uret.font(uret.GOVDE, 42), (161, 161, 166), GENISLIK, 1.4, hiza="orta")
    uret.harfli(k, (KENAR, H - 460), uret.HANDLE, uret.font(uret.ARA, 34), uret.BEYAZ,
                aralik=0.04, hiza="orta", genislik=GENISLIK, buyuk=False)
    return k.convert("RGB")


# ---------- üretim ----------

def sahneleri_al(veri):
    r = veri.get("reels") or {}
    if r.get("sahneler"):
        return r["sahneler"]
    sahneler = [{"foto": veri["foto"], "metin": veri["baslik"], "alt": veri.get("alt_baslik", "")}]
    for i, s in enumerate(veri.get("slaytlar", []), start=1):
        if s.get("foto"):
            sahneler.append({"foto": s["foto"], "etiket": f"{i:02d}", "metin": s["baslik"], "alt": s["metin"]})
    return sahneler


def uret_reels(json_yolu):
    global ISARET, RENK, MEKTUP
    veri = json.loads(Path(json_yolu).read_text(encoding="utf-8"))
    ISARET = isaret_katmani(veri.get("reels", {}).get("konum", veri.get("konum", "")))
    RENK = RENKLER[veri.get("reels", {}).get("renk")]
    MEKTUP = veri.get("reels", {}).get("stil") == "mektup"
    sahneler = sahneleri_al(veri)
    cikis = KOK / "reels" / f"{veri['slug']}.mp4"
    cikis.parent.mkdir(exist_ok=True)

    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(cikis)],
        stdin=subprocess.PIPE,
    )
    ayar = veri.get("reels", {}).get("muzik", {"tarz": "tropik", "tohum": 7})
    if ayar and ayar.get("dosya"):
        # Hazır, telifsiz parça (ör. Pixabay Music): kesmeler parçanın bpm'ine oturur
        _tarz = {"bpm": ayar.get("bpm", 100), "kesim": ayar.get("kesim", 1)}
    else:
        _tarz = muzik.TARZLAR[(ayar or {}).get("tarz", "tropik")]
    vurus = 60 / _tarz["bpm"] * _tarz.get("kesim", 1)  # kesim: hızlı tempolarda (vals) kesmeleri seyrelt
    g = int(GECIS * FPS)
    onceki = None
    zaman = 0.0  # kesmeleri vuruşa oturtmak için birikimli süre

    for idx, s in enumerate(sahneler):
        if s.get("fotolar"):
            # Çok fotoğraflı sahne: her fotoğraf "vurus_basina" vuruş sürer, kesmeler vuruşa denk gelir
            vb = s.get("vurus_basina", 2)
            ana, alt = sahne_katmanlari(s, idx == 0)
            ana = golgeli(ana)
            sahne_kare = 0
            for fi, foto in enumerate(s["fotolar"]):
                ovb = foto.get("vurus", vb) if isinstance(foto, dict) else vb
                bitis = zaman + ovb * vurus
                if isinstance(foto, dict) and foto.get("video"):
                    kaynak = VideoKaynak(foto["video"], foto.get("baslangic", 0), bitis - zaman,
                                         foto.get("hiz", 0.8), foto.get("odak_x", 0.5))
                else:
                    dosya, odak = (foto, (0.5, 0.5)) if isinstance(foto, str) else (foto["foto"], foto.get("odak", (0.5, 0.5)))
                    kaynak = FotoKaynak(dosya, odak)
                n = int(round(bitis * FPS)) - int(round(zaman * FPS))
                for f in range(n):
                    img = karart(kaynak.kare(f / max(1, n - 1))).convert("RGBA")
                    if idx == 0:
                        # kanca: ilk karede başlık hazır, detay hemen ardından (ilk 3 sn'de kaybetmemek için)
                        a1 = 1.0
                        a2 = yumusak((sahne_kare - 6) / 6)
                    else:
                        a1 = yumusak((sahne_kare - 3) / 7)
                        a2 = yumusak((sahne_kare - 18) / 8)
                    if a1 > 0:
                        img.alpha_composite(alfali(ana, a1))
                    if a2 > 0:
                        img.alpha_composite(alfali(alt, a2))
                    img.alpha_composite(ISARET)
                    img = img.convert("RGB")
                    onceki = img
                    ff.stdin.write(img.tobytes())
                    sahne_kare += 1
                kaynak.kapat()
                zaman = bitis
            continue

        sure = s.get("sure", 3.6 if s.get("alt") else 2.8)
        sure = max(1, round(sure / vurus)) * vurus  # süreyi vuruşa yuvarla
        n = int(round((zaman + sure) * FPS)) - int(round(zaman * FPS))
        zaman += sure
        if s.get("video"):
            kaynak = VideoKaynak(s["video"], s.get("baslangic", 0), sure, s.get("hiz", 0.8), s.get("odak_x", 0.5))
        else:
            kaynak = FotoKaynak(s["foto"], s.get("odak", (0.5, 0.5)))
        ana, alt = sahne_katmanlari(s, idx == 0)
        ana = golgeli(ana)
        kart = kart_hazirla(s["kart"]) if s.get("kart") else None
        for f in range(n):
            img = karart(kaynak.kare(f / max(1, n - 1))).convert("RGBA")
            if idx == 0:
                a1, a2 = 1.0, yumusak((f - 6) / 6)  # kanca: başlık ilk karede
            else:
                a1 = yumusak((f - 4) / 9)
                a2 = yumusak((f - 22) / 9)  # detay cümlesi ~0.7 sn sonra gelir
            if kart:
                img = kart_uygula(img, kart, yumusak((f - (4 if idx == 0 else 10)) / 12))
            if a1 > 0:
                img.alpha_composite(alfali(ana, a1))
            if a2 > 0:
                img.alpha_composite(alfali(alt, a2))
            img.alpha_composite(ISARET)
            img = img.convert("RGB")
            if onceki is not None and f < g:
                img = Image.blend(onceki, img, yumusak(f / g))
            if f == n - 1:
                onceki = img
            ff.stdin.write(img.tobytes())
        kaynak.kapat()

    son = kapanis(veri)
    for f in range(int(round(4 * vurus * FPS))):
        ff.stdin.write(son.tobytes())

    ff.stdin.close()
    ff.wait()

    if ayar and ayar.get("dosya"):
        sure = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(cikis)]))
        parca = KOK / "kaynak" / ayar["dosya"]
        bas = float(ayar.get("baslangic", 0))
        sonmak = max(sure - 1.5, 0)
        gecici = cikis.with_name(cikis.stem + "-sessiz.mp4")
        cikis.rename(gecici)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(gecici),
                        "-stream_loop", "-1", "-ss", str(bas), "-i", str(parca),
                        "-filter_complex",
                        f"[1:a]volume={ayar.get('ses', 1.0)},afade=t=in:d=0.3,"
                        f"afade=t=out:st={sonmak}:d=1.5,atrim=0:{sure}[a]",
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", "-movflags", "+faststart", str(cikis)], check=True)
        gecici.unlink()
    elif ayar:
        sure = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(cikis)]))
        wav = cikis.with_suffix(".wav")
        muzik.kaydet(muzik.uret(sure, ayar.get("tarz", "tropik"), ayar.get("tohum", 7)), wav)
        gecici = cikis.with_name(cikis.stem + "-sessiz.mp4")
        cikis.rename(gecici)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(gecici), "-i", str(wav),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", str(cikis)], check=True)
        gecici.unlink()
        wav.unlink()
    print("  ", cikis.relative_to(KOK))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for d in sys.argv[1:]:
        uret_reels(d)
