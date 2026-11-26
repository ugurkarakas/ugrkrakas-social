#!/usr/bin/env python3
"""@ugrkrakas görsel üreticisi.

icerik/<slug>.json dosyasını okuyup kaynak/ klasöründeki fotoğraflardan
yayına hazır görselleri üretir:

  post/<slug>.jpg              1080x1350  tek görsel gönderi / Reels kapağı
  carousel/<slug>/01.jpg ...   1080x1350  carousel (kapak + içerik + kapanış)
  story/<slug>-story.jpg       1080x1920  günün gönderisini duyuran story
  story/<slug>-ogle.jpg        1080x1920  'Biliyor muydun?' bilgi kartı
  story/<slug>-sabah.jpg       1080x1920  sabah konum kartı
  anket/<slug>-anket.jpg       1080x1920  anket story'si (alt kısım sticker için boş)

Tasarım dili: sade, bol boşluk, Inter yazı tipi, siyah / beyaz / açık gri.

Kullanım:
  python3 araclar/uret.py icerik/<slug>.json
  python3 araclar/uret.py --hepsi
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

KOK = Path(__file__).resolve().parent.parent
FONT = KOK / "fonts"
HANDLE = "@ugrkrakas"

ZEMIN = (245, 245, 247)  # açık gri
METIN = (29, 29, 31)  # neredeyse siyah
IKINCIL = (110, 110, 115)  # gri metin
BEYAZ = (255, 255, 255)
SIYAH = (0, 0, 0)

POST = (1080, 1350)
STORY = (1080, 1920)

BASLIK = "InterDisplay-SemiBold"
ARA = "Inter-SemiBold"
GOVDE = "Inter-Regular"
KUCUK = "Inter-Medium"


def font(ad, boyut):
    return ImageFont.truetype(str(FONT / f"{ad}.otf"), boyut)


def doldur(foto_yolu, boyut, odak=(0.5, 0.5)):
    img = Image.open(foto_yolu)
    img = ImageOps.exif_transpose(img).convert("RGB")
    return ImageOps.fit(img, boyut, Image.LANCZOS, centering=odak)


def karartma(img, ust=0.0, alt=0.0):
    """Üstten ve alttan yumuşak geçişli karartma (yazı okunurluğu için)."""
    w, h = img.size
    maske = Image.new("L", (1, h), 0)
    for y in range(h):
        t = y / h
        a = 0.0
        if ust:
            a = max(a, ust * max(0.0, 1 - t / 0.28) ** 1.6)
        if alt:
            a = max(a, alt * max(0.0, (t - 0.42) / 0.58) ** 1.5)
        maske.putpixel((0, y), int(255 * a))
    maske = maske.resize((w, h))
    return Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), img, maske)


def satirlar(metin, fnt, genislik):
    olcer = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    sonuc, satir = [], ""
    for k in metin.split():
        deneme = f"{satir} {k}".strip()
        if olcer.textlength(deneme, font=fnt) <= genislik:
            satir = deneme
        else:
            if satir:
                sonuc.append(satir)
            satir = k
    if satir:
        sonuc.append(satir)
    return sonuc


def blok_yuksekligi(metin, fnt, genislik, aralik):
    return len(satirlar(metin, fnt, genislik)) * int(fnt.size * aralik)


def yaz(katman, xy, metin, fnt, renk, genislik, aralik=1.18, hiza="sol", seffaflik=255):
    c = ImageDraw.Draw(katman)
    x, y = xy
    for s in satirlar(metin, fnt, genislik):
        sx = x
        if hiza == "orta":
            sx = x + (genislik - c.textlength(s, font=fnt)) / 2
        c.text((sx, y), s, font=fnt, fill=renk + (seffaflik,))
        y += int(fnt.size * aralik)
    return y


def harfli(katman, xy, metin, fnt, renk, aralik=0.12, seffaflik=255, hiza="sol", genislik=0, buyuk=True):
    """Harf aralığı açılmış küçük üst başlık (ROMA, İTALYA gibi)."""
    c = ImageDraw.Draw(katman)
    if buyuk:
        metin = metin.replace("i", "İ").upper()
    bosluk = fnt.size * aralik
    toplam = sum(c.textlength(h, font=fnt) for h in metin) + bosluk * (len(metin) - 1)
    x, y = xy
    if hiza == "orta":
        x = x + (genislik - toplam) / 2
    for h in metin:
        c.text((x, y), h, font=fnt, fill=renk + (seffaflik,))
        x += c.textlength(h, font=fnt) + bosluk
    return toplam


def ust_yazi(katman, w, kenar, y, sol, renk, seffaflik=230):
    harfli(katman, (kenar, y), sol, font(ARA, 26), renk, seffaflik=seffaflik)
    c = ImageDraw.Draw(katman)
    f = font(KUCUK, 26)
    hw = c.textlength(HANDLE, font=f)
    c.text((w - kenar - hw, y), HANDLE, font=f, fill=renk + (seffaflik,))


def birlestir(taban, katman):
    taban = taban.convert("RGBA")
    taban.alpha_composite(katman)
    return taban.convert("RGB")


def kapak(veri):
    w, h = POST
    kenar = 84
    genislik = w - 2 * kenar
    img = karartma(doldur(KOK / "kaynak" / veri["foto"], POST, (0.5, 0.45)), ust=0.45, alt=0.82)
    k = Image.new("RGBA", POST, (0, 0, 0, 0))
    ust_yazi(k, w, kenar, 78, veri.get("konum", ""), BEYAZ)

    bf, af = font(BASLIK, 92), font(GOVDE, 36)
    bh = blok_yuksekligi(veri["baslik"], bf, genislik, 1.08)
    ah = blok_yuksekligi(veri["alt_baslik"], af, genislik, 1.35) if veri.get("alt_baslik") else 0
    y = h - 104 - ah - (28 if ah else 0) - bh
    y = yaz(k, (kenar, y), veri["baslik"], bf, BEYAZ, genislik, 1.08) + 28
    if ah:
        yaz(k, (kenar, y), veri["alt_baslik"], af, BEYAZ, genislik, 1.35, seffaflik=215)
    return birlestir(img, k)


def icerik_slayti(slayt, sira, toplam, konum):
    w, h = POST
    kenar = 84
    genislik = w - 2 * kenar
    img = Image.new("RGB", POST, ZEMIN)
    k = Image.new("RGBA", POST, (0, 0, 0, 0))
    ust_yazi(k, w, kenar, 78, f"{sira:02d}  ·  {konum}" if konum else f"{sira:02d}", IKINCIL, 255)

    if slayt.get("fotolar"):
        return kolaj_slayti(slayt, sira, toplam, konum)
    foto_var = bool(slayt.get("foto"))
    bf = font(BASLIK, 64 if foto_var else 80)
    gf = font(GOVDE, 36 if foto_var else 42)

    if foto_var:
        y = 170
        y = yaz(k, (kenar, y), slayt["baslik"], bf, METIN, genislik, 1.1) + 22
        y = yaz(k, (kenar, y), slayt["metin"], gf, IKINCIL, genislik, 1.42) + 44
        foto_h = h - y - 110
        if foto_h > 260:
            foto = doldur(KOK / "kaynak" / slayt["foto"], (genislik, foto_h))
            maske = Image.new("L", foto.size, 0)
            ImageDraw.Draw(maske).rounded_rectangle((0, 0, foto.size[0] - 1, foto.size[1] - 1), radius=36, fill=255)
            img.paste(foto, (kenar, y), maske)
    else:
        bh = blok_yuksekligi(slayt["baslik"], bf, genislik, 1.1)
        gh = blok_yuksekligi(slayt["metin"], gf, genislik, 1.45)
        y = (h - bh - 30 - gh) // 2
        y = yaz(k, (kenar, y), slayt["baslik"], bf, METIN, genislik, 1.1) + 30
        yaz(k, (kenar, y), slayt["metin"], gf, IKINCIL, genislik, 1.45)

    c = ImageDraw.Draw(k)
    nokta, ara = 10, 14
    tx = w / 2 - (toplam * nokta + (toplam - 1) * ara) / 2
    for i in range(toplam):
        renk = METIN + (255,) if i == sira else (199, 199, 204, 255)
        x = tx + i * (nokta + ara)
        c.ellipse((x, h - 62, x + nokta, h - 62 + nokta), fill=renk)
    return birlestir(img, k)


def yuvarlak_yapistir(img, foto, xy, r=28):
    maske = Image.new("L", foto.size, 0)
    ImageDraw.Draw(maske).rounded_rectangle((0, 0, foto.size[0] - 1, foto.size[1] - 1), radius=r, fill=255)
    img.paste(foto, xy, maske)


def kolaj_slayti(slayt, sira, toplam, konum):
    """Başlık + 2 ya da 3 fotoğraflı kolaj (büyük solda, iki küçük sağda)."""
    w, h = POST
    kenar = 84
    genislik = w - 2 * kenar
    img = Image.new("RGB", POST, ZEMIN)
    k = Image.new("RGBA", POST, (0, 0, 0, 0))
    ust_yazi(k, w, kenar, 78, f"{sira:02d}  ·  {konum}" if konum else f"{sira:02d}", IKINCIL, 255)
    y = 170
    y = yaz(k, (kenar, y), slayt["baslik"], font(BASLIK, 64), METIN, genislik, 1.1) + 22
    y = yaz(k, (kenar, y), slayt["metin"], font(GOVDE, 34), IKINCIL, genislik, 1.42) + 40

    def foto(ad, boyut):
        if isinstance(ad, dict):
            return doldur(KOK / "kaynak" / ad["foto"], boyut, tuple(ad.get("odak", (0.5, 0.5))))
        return doldur(KOK / "kaynak" / ad, boyut)

    fotolar = slayt["fotolar"][:3]
    alan_h = h - y - 110
    ara = 16
    if len(fotolar) >= 3:
        sol_w = int((genislik - ara) * 0.6)
        sag_w = genislik - ara - sol_w
        kucuk_h = (alan_h - ara) // 2
        yuvarlak_yapistir(img, foto(fotolar[0], (sol_w, alan_h)), (kenar, y))
        yuvarlak_yapistir(img, foto(fotolar[1], (sag_w, kucuk_h)), (kenar + sol_w + ara, y))
        yuvarlak_yapistir(img, foto(fotolar[2], (sag_w, alan_h - kucuk_h - ara)), (kenar + sol_w + ara, y + kucuk_h + ara))
    else:
        yarim = (genislik - ara) // 2
        for i, f in enumerate(fotolar):
            yuvarlak_yapistir(img, foto(f, (yarim, alan_h)), (kenar + i * (yarim + ara), y))

    c = ImageDraw.Draw(k)
    nokta, bosluk = 10, 14
    tx = w / 2 - (toplam * nokta + (toplam - 1) * bosluk) / 2
    for i in range(toplam):
        renk = METIN + (255,) if i == sira else (199, 199, 204, 255)
        x = tx + i * (nokta + bosluk)
        c.ellipse((x, h - 62, x + nokta, h - 62 + nokta), fill=renk)
    return birlestir(img, k)


def kapanis_slayti(veri):
    w, h = POST
    kenar = 84
    genislik = w - 2 * kenar
    img = Image.new("RGB", POST, SIYAH)
    k = Image.new("RGBA", POST, (0, 0, 0, 0))
    bf, gf = font(BASLIK, 88), font(GOVDE, 38)
    cta = veri.get("cta", "Kaydet, gidince aç.")
    alt = veri.get("cta_alt", "Daha fazla rota ve durak için takip et.")
    bh = blok_yuksekligi(cta, bf, genislik, 1.08)
    gh = blok_yuksekligi(alt, gf, genislik, 1.4)
    y = (h - bh - 32 - gh) // 2
    y = yaz(k, (kenar, y), cta, bf, BEYAZ, genislik, 1.08, hiza="orta") + 32
    yaz(k, (kenar, y), alt, gf, (161, 161, 166), genislik, 1.4, hiza="orta")
    harfli(k, (kenar, h - 120), HANDLE, font(ARA, 28), BEYAZ, aralik=0.04, hiza="orta",
           genislik=genislik, buyuk=False)
    return birlestir(img, k)


def story(veri):
    w, h = STORY
    kenar = 90
    genislik = w - 2 * kenar
    img = karartma(doldur(KOK / "kaynak" / veri["foto"], STORY), ust=0.55, alt=0.8)
    k = Image.new("RGBA", STORY, (0, 0, 0, 0))
    harfli(k, (kenar, 250), veri.get("story_ust", "Yeni gönderi"), font(ARA, 28), BEYAZ,
           seffaflik=225, hiza="orta", genislik=genislik)
    bf = font(BASLIK, 96)
    bh = blok_yuksekligi(veri["baslik"], bf, genislik, 1.08)
    y = h - 520 - bh
    y = yaz(k, (kenar, y), veri["baslik"], bf, BEYAZ, genislik, 1.08, hiza="orta") + 48
    if veri.get("konum"):
        harfli(k, (kenar, y), veri["konum"], font(ARA, 28), BEYAZ, seffaflik=215, hiza="orta", genislik=genislik)
    return birlestir(img, k)


def ogle_story(veri):
    """Öğlen hikayesi: tek bir çarpıcı bilgi + akşamki gönderinin duyurusu."""
    w, h = STORY
    kenar = 90
    genislik = w - 2 * kenar
    o = veri["ogle"]
    img = karartma(doldur(KOK / "kaynak" / o.get("foto", veri["foto"]), STORY, tuple(o.get("odak", (0.5, 0.5)))), ust=0.6, alt=0.85)
    img = Image.blend(img.convert("RGB"), Image.new("RGB", STORY, (0, 0, 0)), 0.32)
    k = Image.new("RGBA", STORY, (0, 0, 0, 0))
    harfli(k, (kenar, 250), o.get("ust", "Biliyor muydun?"), font(ARA, 30), BEYAZ,
           seffaflik=230, hiza="orta", genislik=genislik)
    bf = font(BASLIK, 80)
    bh = blok_yuksekligi(o["metin"], bf, genislik, 1.1)
    y = (h - bh) // 2 - 60
    yazi = Image.new("RGBA", STORY, (0, 0, 0, 0))
    yaz(yazi, (kenar, y), o["metin"], bf, BEYAZ, genislik, 1.1, hiza="orta")
    golge = Image.new("RGBA", STORY, (0, 0, 0, 0))
    golge.putalpha(yazi.getchannel("A").filter(ImageFilter.GaussianBlur(18)).point(lambda a: int(a * 0.75)))
    k = Image.alpha_composite(Image.alpha_composite(k, golge), yazi)
    alt = o.get("duyuru", "Bu akşam: " + veri["baslik"])
    af = font(ARA, 34)
    ah = blok_yuksekligi(alt, af, genislik - 80, 1.2)
    kutu_y = h - 420
    # kutu yazıyı sarsın: genişlik = en uzun satır + iç boşluk
    d = ImageDraw.Draw(k)
    tw = max(d.textlength(s, font=af) for s in satirlar(alt, af, genislik - 80))
    kx0 = (w - tw) / 2 - 64
    d.rounded_rectangle((kx0, kutu_y, w - kx0, kutu_y + ah + 64), radius=(ah + 64) // 2 if ah < 60 else 36, fill=(255, 255, 255, 46))
    yaz(k, (kenar + 40, kutu_y + 32), alt, af, BEYAZ, genislik - 80, 1.2, hiza="orta")
    return birlestir(img, k)


def konum_story(veri):
    """Sabah hikayesi: konum kartı (yer adı, bölge, tek cümlelik tanıtım)."""
    w, h = STORY
    kenar = 90
    genislik = w - 2 * kenar
    o = veri["sabah"]
    img = karartma(doldur(KOK / "kaynak" / o.get("foto", veri["foto"]), STORY, tuple(o.get("odak", (0.5, 0.5)))), ust=0.5, alt=0.9)
    k = Image.new("RGBA", STORY, (0, 0, 0, 0))
    ust_yazi(k, w, kenar, 150, o.get("ust", "Rota önerisi"), BEYAZ)
    c = ImageDraw.Draw(k)
    mf = font(GOVDE, 40)
    mh = blok_yuksekligi(o["metin"], mf, genislik, 1.3)
    bf = font(BASLIK, 112)
    bh = blok_yuksekligi(o["yer"], bf, genislik, 1.04)
    y = h - 330 - mh - 70 - bh - 90
    # konum pini + bölge
    pf = font(ARA, 32)
    r = 15
    px, py = kenar + r, y + 4 + r
    c.ellipse((px - r, py - r, px + r, py + r), fill=BEYAZ + (240,))
    c.polygon([(px - r * 0.82, py + r * 0.55), (px + r * 0.82, py + r * 0.55), (px, py + r * 2.1)], fill=BEYAZ + (240,))
    c.ellipse((px - 6, py - 6, px + 6, py + 6), fill=(0, 0, 0, 0))
    harfli(k, (kenar + 2 * r + 20, y), o["bolge"], pf, BEYAZ, seffaflik=235)
    y += 90
    y = yaz(k, (kenar, y), o["yer"], bf, BEYAZ, genislik, 1.04) + 70
    c.line((kenar, y - 36, kenar + 90, y - 36), fill=BEYAZ + (200,), width=3)
    yaz(k, (kenar, y), o["metin"], mf, BEYAZ, genislik, 1.3, seffaflik=235)
    golge = Image.new("RGBA", STORY, (0, 0, 0, 0))
    golge.putalpha(k.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda a: int(a * 0.7)))
    return birlestir(img, Image.alpha_composite(golge, k))


def anket_story(veri):
    w, h = STORY
    kenar = 90
    genislik = w - 2 * kenar
    alan = 820
    img = Image.new("RGB", STORY, ZEMIN)
    foto = doldur(KOK / "kaynak" / veri["anket"].get("foto", veri["foto"]), (w, h - alan))
    img.paste(foto, (0, 0))
    k = Image.new("RGBA", STORY, (0, 0, 0, 0))
    y = h - alan + 90
    harfli(k, (kenar, y), "Anket", font(ARA, 28), IKINCIL, hiza="orta", genislik=genislik)
    yaz(k, (kenar, y + 70), veri["anket"]["soru"], font(BASLIK, 68), METIN, genislik, 1.1, hiza="orta")
    return birlestir(img, k)


def kaydet(img, yol):
    yol.parent.mkdir(parents=True, exist_ok=True)
    img.save(yol, "JPEG", quality=92, optimize=True, progressive=True)
    print("  ", yol.relative_to(KOK))


def uret(json_yolu):
    veri = json.loads(Path(json_yolu).read_text(encoding="utf-8"))
    slug = veri["slug"]
    print(slug)
    if veri["tur"] == "carousel":
        slaytlar = veri["slaytlar"]
        toplam = len(slaytlar) + 2
        kaydet(kapak(veri), KOK / "carousel" / slug / "01.jpg")
        for i, s in enumerate(slaytlar, start=1):
            kaydet(icerik_slayti(s, i, toplam, veri.get("konum", "")),
                   KOK / "carousel" / slug / f"{i + 1:02d}.jpg")
        kaydet(kapanis_slayti(veri), KOK / "carousel" / slug / f"{toplam:02d}.jpg")
    else:
        kaydet(kapak(veri), KOK / "post" / f"{slug}.jpg")
    kaydet(story(veri), KOK / "story" / f"{slug}-story.jpg")
    if veri.get("ogle"):
        kaydet(ogle_story(veri), KOK / "story" / f"{slug}-ogle.jpg")
    if veri.get("sabah"):
        kaydet(konum_story(veri), KOK / "story" / f"{slug}-sabah.jpg")
    if veri.get("anket"):
        kaydet(anket_story(veri), KOK / "anket" / f"{slug}-anket.jpg")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "--hepsi":
        dosyalar = sorted(d for d in (KOK / "icerik").glob("*.json") if not d.name.startswith("_"))
    else:
        dosyalar = sys.argv[1:]
    for d in dosyalar:
        uret(d)
