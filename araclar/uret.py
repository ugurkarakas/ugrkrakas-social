#!/usr/bin/env python3
"""@ugrkrakas görsel üreticisi.

icerik/<slug>.json dosyasını okuyup kaynak/ klasöründeki fotoğraflardan
yayına hazır görselleri üretir:

  post/<slug>.jpg              1080x1350  tek görsel gönderi / kapak
  carousel/<slug>/01.jpg ...   1080x1350  carousel slaytları (kapak + içerik + kapanış)
  story/<slug>-story.jpg       1080x1920  günün gönderisini duyuran story
  anket/<slug>-anket.jpg       1080x1920  anket story'si (alt kısım sticker için boş)

Kullanım:
  python3 araclar/uret.py icerik/roma-yerel-lokanta.json
  python3 araclar/uret.py --hepsi
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

KOK = Path(__file__).resolve().parent.parent
FONT = KOK / "fonts"
HANDLE = "@ugrkrakas"

# Renkler: kum zemin, koyu lacivert metin, turuncu vurgu
KUM = (244, 239, 230)
LACIVERT = (20, 33, 51)
VURGU = (232, 106, 51)
BEYAZ = (255, 255, 255)

POST = (1080, 1350)
STORY = (1080, 1920)


def font(agirlik, boyut):
    return ImageFont.truetype(str(FONT / f"Poppins-{agirlik}.ttf"), boyut)


def doldur(foto_yolu, boyut):
    """Fotoğrafı kırpıp hedef boyutu tam dolduracak şekilde yerleştirir."""
    img = Image.open(foto_yolu)
    img = ImageOps.exif_transpose(img).convert("RGB")
    return ImageOps.fit(img, boyut, Image.LANCZOS, centering=(0.5, 0.45))


def alt_karartma(img, baslangic=0.45, guc=235):
    """Alt kısma yazının okunması için yumuşak bir karartma ekler."""
    w, h = img.size
    maske = Image.new("L", (1, h), 0)
    for y in range(h):
        oran = max(0.0, (y / h - baslangic) / (1 - baslangic))
        maske.putpixel((0, y), int(guc * oran ** 1.4))
    maske = maske.resize((w, h))
    siyah = Image.new("RGB", (w, h), (8, 14, 24))
    return Image.composite(siyah, img, maske)


def satirlara_bol(metin, fnt, genislik, cizim):
    kelimeler, satirlar, satir = metin.split(), [], ""
    for k in kelimeler:
        deneme = f"{satir} {k}".strip()
        if cizim.textlength(deneme, font=fnt) <= genislik:
            satir = deneme
        else:
            if satir:
                satirlar.append(satir)
            satir = k
    if satir:
        satirlar.append(satir)
    return satirlar


def metin_yaz(cizim, xy, metin, fnt, renk, genislik, aralik=1.12):
    x, y = xy
    satirlar = satirlara_bol(metin, fnt, genislik, cizim)
    yukseklik = int(fnt.size * aralik)
    for s in satirlar:
        cizim.text((x, y), s, font=fnt, fill=renk)
        y += yukseklik
    return y


def metin_yuksekligi(cizim, metin, fnt, genislik, aralik=1.12):
    return len(satirlara_bol(metin, fnt, genislik, cizim)) * int(fnt.size * aralik)


def etiket(cizim, xy, metin, zemin=VURGU, renk=BEYAZ, boyut=30):
    fnt = font("Bold", boyut)
    x, y = xy
    w = cizim.textlength(metin, font=fnt)
    pad_x, pad_y = 22, 12
    cizim.rounded_rectangle(
        (x, y, x + w + 2 * pad_x, y + boyut + 2 * pad_y), radius=999, fill=zemin
    )
    cizim.text((x + pad_x, y + pad_y - 4), metin, font=fnt, fill=renk)
    return y + boyut + 2 * pad_y


def kapak(veri, boyut=POST, story_modu=False):
    img = doldur(KOK / "kaynak" / veri["foto"], boyut)
    img = alt_karartma(img, 0.35 if story_modu else 0.4)
    c = ImageDraw.Draw(img)
    w, h = boyut
    kenar = 80
    genislik = w - 2 * kenar

    baslik_f = font("Bold", 88)
    alt_f = font("Regular", 40)
    sehir_f = font("Medium", 32)

    alt_bosluk = 150 if not story_modu else 420
    alt_h = metin_yuksekligi(c, veri.get("alt_baslik", ""), alt_f, genislik, 1.3)
    baslik_h = metin_yuksekligi(c, veri["baslik"], baslik_f, genislik, 1.15)
    y = h - alt_bosluk - alt_h - baslik_h - 110

    y = etiket(c, (kenar, y), veri["seri"].upper()) + 28
    y = metin_yaz(c, (kenar, y), veri["baslik"], baslik_f, BEYAZ, genislik, 1.15) + 24
    if veri.get("alt_baslik"):
        metin_yaz(c, (kenar, y), veri["alt_baslik"], alt_f, (225, 228, 232), genislik, 1.3)

    alt_y = h - 110 if not story_modu else h - 380
    konum = veri.get("konum", "")
    if konum:
        c.text((kenar, alt_y), konum.upper(), font=sehir_f, fill=(225, 228, 232))
    hw = c.textlength(HANDLE, font=sehir_f)
    c.text((w - kenar - hw, alt_y), HANDLE, font=sehir_f, fill=BEYAZ)
    return img


def icerik_slayti(slayt, sira, toplam):
    w, h = POST
    kenar = 90
    img = Image.new("RGB", POST, KUM)
    c = ImageDraw.Draw(img)

    foto_h = 0
    if slayt.get("foto"):
        foto_h = 620
        foto = doldur(KOK / "kaynak" / slayt["foto"], (w, foto_h))
        img.paste(foto, (0, 0))

    genislik = w - 2 * kenar
    no_f = font("Bold", 72 if foto_h else 150)
    baslik_f = font("Bold", 62 if foto_h else 78)
    metin_f = font("Regular", 38 if foto_h else 46)
    no_h = 90 if foto_h else 190
    blok_h = (
        no_h
        + metin_yuksekligi(c, slayt["baslik"], baslik_f, genislik, 1.15)
        + 30
        + metin_yuksekligi(c, slayt["metin"], metin_f, genislik, 1.42)
    )
    if foto_h:
        y = foto_h + 70
    else:
        y = max(140, (h - 120 - blok_h) // 2)
    c.text((kenar, y - 20), f"{sira:02d}", font=no_f, fill=VURGU)
    y += no_h
    y = metin_yaz(c, (kenar, y), slayt["baslik"], baslik_f, LACIVERT, genislik, 1.15) + 30
    metin_yaz(c, (kenar, y), slayt["metin"], metin_f, (60, 70, 84), genislik, 1.42)

    alt_f = font("Medium", 28)
    c.text((kenar, h - 90), HANDLE, font=alt_f, fill=LACIVERT)
    sayac = f"{sira + 1} / {toplam}"
    sw = c.textlength(sayac, font=alt_f)
    c.text((w - kenar - sw, h - 90), sayac, font=alt_f, fill=(120, 128, 140))
    return img


def kapanis_slayti(veri):
    w, h = POST
    kenar = 90
    img = Image.new("RGB", POST, LACIVERT)
    c = ImageDraw.Draw(img)
    cta = veri.get("cta", "Kaydet, gidince aç.")
    y = 470
    c.text((kenar, y), "Bu rehberi", font=font("Regular", 50), fill=(200, 206, 214))
    y = metin_yaz(c, (kenar, y + 70), cta, font("Bold", 88), BEYAZ, w - 2 * kenar, 1.08) + 40
    c.line((kenar, y, kenar + 140, y), fill=VURGU, width=8)
    y += 50
    metin_yaz(
        c,
        (kenar, y),
        "Daha fazla rota ve durak için takip et",
        font("Regular", 38),
        (200, 206, 214),
        w - 2 * kenar,
        1.4,
    )
    c.text((kenar, h - 150), HANDLE, font=font("Bold", 46), fill=BEYAZ)
    return img


def anket_story(veri):
    img = doldur(KOK / "kaynak" / veri["foto"], STORY)
    w, h = STORY
    # Üst yarı fotoğraf, alt kısım anket sticker'ı için düz zemin
    alt = Image.new("RGB", (w, 760), KUM)
    img.paste(alt, (0, h - 760))
    c = ImageDraw.Draw(img)
    kenar = 80
    soru = veri.get("anket", {}).get("soru", veri["baslik"])
    y = h - 700
    y = etiket(c, (kenar, y), "ANKET") + 30
    metin_yaz(c, (kenar, y), soru, font("Bold", 64), LACIVERT, w - 2 * kenar, 1.1)
    c.text((kenar, h - 120), HANDLE, font=font("Medium", 32), fill=LACIVERT)
    return img


def kaydet(img, yol):
    yol.parent.mkdir(parents=True, exist_ok=True)
    img.save(yol, "JPEG", quality=90, optimize=True, progressive=True)
    print("  ", yol.relative_to(KOK))


def uret(json_yolu):
    veri = json.loads(Path(json_yolu).read_text(encoding="utf-8"))
    slug = veri["slug"]
    print(slug)

    kapak_img = kapak(veri)
    if veri["tur"] == "carousel":
        slaytlar = veri["slaytlar"]
        toplam = len(slaytlar) + 2
        kaydet(kapak_img, KOK / "carousel" / slug / "01.jpg")
        for i, s in enumerate(slaytlar, start=1):
            kaydet(icerik_slayti(s, i, toplam), KOK / "carousel" / slug / f"{i + 1:02d}.jpg")
        kaydet(kapanis_slayti(veri), KOK / "carousel" / slug / f"{toplam:02d}.jpg")
    else:
        kaydet(kapak_img, KOK / "post" / f"{slug}.jpg")

    kaydet(kapak(veri, STORY, story_modu=True), KOK / "story" / f"{slug}-story.jpg")
    if veri.get("anket"):
        kaydet(anket_story(veri), KOK / "anket" / f"{slug}-anket.jpg")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    dosyalar = sorted(d for d in (KOK / "icerik").glob("*.json") if not d.name.startswith("_")) if sys.argv[1] == "--hepsi" else sys.argv[1:]
    for d in dosyalar:
        uret(d)
