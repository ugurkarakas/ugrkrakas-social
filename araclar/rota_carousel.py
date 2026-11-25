#!/usr/bin/env python3
"""Kendi gezi fotoğraflarından tam ekran "rota" carousel'i.

Her slayt tam ekran fotoğraf; üstte siyah başlık etiketi, altında beyaz durak kartı.
Kapakta büyük serif şehir adı ve italik alt başlık, sonda kaydet/takip kartı.

  python3 araclar/rota_carousel.py icerik/<slug>.json  ->  carousel/<slug>/01.jpg ...

JSON'da "rota" alanı:
  "rota": {
    "sehir": "LUKSOR", "alt": "Tapınak Rehberi", "ust": "Mısır", "kapak": "foto.jpg",
    "duraklar": [{"etiket": "1. DURAK - GİRİŞ", "maddeler": ["...", "..."],
                  "foto": "foto.jpg", "odak": [0.5, 0.5], "konum": 0.16}],
    "kapanis": {"foto": "foto.jpg", "metin": "Kaydet", "alt": "..."}
  }
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from uret import HANDLE, KOK, birlestir, doldur, karartma, kaydet, satirlar  # noqa: E402

W, H = 1080, 1350
FONT = KOK / "fonts"
KUM = (232, 200, 150)  # vurgu rengi


def f(ad, boyut):
    return ImageFont.truetype(str(FONT / ad), boyut)


def sayac(d, sira, toplam):
    fnt = f("Inter-Medium.otf", 30)
    t = f"{sira}/{toplam}"
    tw = d.textlength(t, font=fnt)
    x1, y0 = W - 48, 48
    d.rounded_rectangle((x1 - tw - 44, y0, x1, y0 + 58), radius=29, fill=(0, 0, 0, 120))
    d.text((x1 - tw - 22, y0 + 12), t, font=fnt, fill=(255, 255, 255, 255))


def kapak(r, toplam):
    img = karartma(doldur(KOK / "kaynak" / r["kapak"], (W, H), tuple(r.get("kapak_odak", (0.5, 0.5)))), ust=0.55, alt=0.5)
    k = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(k)
    sayac(d, 1, toplam)
    sf = f("CormorantGaramond.ttf", 210)
    try:
        sf.set_variation_by_axes([700])
    except Exception:
        pass
    af = f("CormorantGaramond-Italic.ttf", 92)
    uf = f("Inter-SemiBold.otf", 30)
    y = 250
    ust = " ".join(r.get("ust", "").upper())
    d.text(((W - d.textlength(ust, font=uf)) / 2, y), ust, font=uf, fill=(255, 255, 255, 235))
    y += 50
    sw = d.textlength(r["sehir"], font=sf)
    # hafif gölge
    for dx, dy in ((0, 6),):
        d.text(((W - sw) / 2 + dx, y + dy), r["sehir"], font=sf, fill=(0, 0, 0, 90))
    d.text(((W - sw) / 2, y), r["sehir"], font=sf, fill=(255, 255, 255, 255))
    y += 205
    aw = d.textlength(r["alt"], font=af)
    d.text(((W - aw) / 2, y + 4), r["alt"], font=af, fill=(0, 0, 0, 200))
    d.text(((W - aw) / 2, y), r["alt"], font=af, fill=(255, 255, 255, 255))
    hf = f("Inter-Medium.otf", 30)
    d.text(((W - d.textlength(HANDLE, font=hf)) / 2, H - 90), HANDLE, font=hf, fill=(255, 255, 255, 220))
    return birlestir(img, k)


def durak(s, sira, toplam):
    img = doldur(KOK / "kaynak" / s["foto"], (W, H), tuple(s.get("odak", (0.5, 0.5))))
    k = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(k)
    sayac(d, sira, toplam)
    ef = f("Inter-SemiBold.otf", 36)
    mf = f("Inter-Regular.otf", 34)
    y = int(H * s.get("konum", 0.16))
    # siyah etiket
    et = s["etiket"]
    ew = d.textlength(et, font=ef)
    pad_x, eh = 40, 84
    ex0 = (W - ew) / 2 - pad_x
    d.rectangle((ex0, y, ex0 + ew + 2 * pad_x, y + eh), fill=(0, 0, 0, 240))
    d.text((ex0 + pad_x, y + 22), et, font=ef, fill=(255, 255, 255, 255))
    # beyaz kart
    kart_gen = 860
    satir = []
    for m in s["maddeler"]:
        for i, sat in enumerate(satirlar(m, mf, kart_gen - 80)):
            satir.append(("• " if i == 0 else "  ") + sat)
    sh = 48
    kh = len(satir) * sh + 56
    kx0 = (W - kart_gen) / 2
    ky0 = y + eh
    d.rectangle((kx0, ky0, kx0 + kart_gen, ky0 + kh), fill=(255, 255, 255, 245))
    yy = ky0 + 30
    for sat in satir:
        tw = d.textlength(sat.strip(), font=mf)
        d.text(((W - tw) / 2, yy), sat.strip(), font=mf, fill=(20, 20, 22, 255))
        yy += sh
    return birlestir(img, k)


def kapanis(c, toplam):
    img = karartma(doldur(KOK / "kaynak" / c["foto"], (W, H), tuple(c.get("odak", (0.5, 0.5)))), ust=0.0, alt=0.0)
    img = Image.blend(img, Image.new("RGB", (W, H), (0, 0, 0)), 0.45)
    k = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(k)
    sayac(d, toplam, toplam)
    bf = f("CormorantGaramond-Italic.ttf", 84)
    af = f("Inter-Regular.otf", 36)
    hf = f("Inter-SemiBold.otf", 40)
    y = H // 2 - 140
    for sat in satirlar(c["metin"], bf, W - 200):
        d.text(((W - d.textlength(sat, font=bf)) / 2, y), sat, font=bf, fill=(255, 255, 255, 255))
        y += 92
    y += 24
    for sat in satirlar(c.get("alt", ""), af, W - 220):
        d.text(((W - d.textlength(sat, font=af)) / 2, y), sat, font=af, fill=(255, 255, 255, 220))
        y += 48
    y += 40
    d.text(((W - d.textlength(HANDLE, font=hf)) / 2, y), HANDLE, font=hf, fill=KUM + (255,))
    return birlestir(img, k)


def uret(yol):
    veri = json.loads(Path(yol).read_text(encoding="utf-8"))
    r = veri["rota"]
    toplam = len(r["duraklar"]) + 2
    hedef = KOK / "carousel" / veri["slug"]
    hedef.mkdir(parents=True, exist_ok=True)
    kaydet(kapak(r, toplam), hedef / "01.jpg")
    for i, s in enumerate(r["duraklar"], start=2):
        kaydet(durak(s, i, toplam), hedef / f"{i:02d}.jpg")
    kaydet(kapanis(r["kapanis"], toplam), hedef / f"{toplam:02d}.jpg")
    print(hedef)


if __name__ == "__main__":
    uret(sys.argv[1])
