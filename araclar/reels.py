#!/usr/bin/env python3
"""@ugrkrakas Reels üreticisi.

icerik/<slug>.json içindeki sahnelerden 1080x1920, 30 fps, sessiz bir MP4 üretir:
yavaş yakınlaşan fotoğraflar, yumuşak geçişler, sade yazılar ve siyah kapanış kartı.

Sahneler "reels.sahneler" alanından okunur. Yoksa kapak + fotoğraflı slaytlar kullanılır.

  "reels": {
    "sahneler": [
      {"foto": "roma-sokak-turuncu.jpg", "ust": "Roma, İtalya", "metin": "Roma'yı yavaş gezmenin 4 kuralı"},
      {"foto": "roma-ispanyol-merdivenleri.jpg", "ust": "01", "metin": "Güne erken başla"}
    ],
    "sahne_suresi": 2.6
  }

Müzik eklenmez: Instagram'da telifsiz / trend müzik uygulamadan eklenebilir.

Kullanım:
  python3 araclar/reels.py icerik/<slug>.json
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import uret  # noqa: E402

KOK = uret.KOK
W, H = uret.STORY
FPS = 30
GECIS = 0.45  # saniye
YAKINLASMA = 0.07


def sahneleri_al(veri):
    r = veri.get("reels") or {}
    if r.get("sahneler"):
        return r["sahneler"], r.get("sahne_suresi", 2.6)
    sahneler = [{"foto": veri["foto"], "ust": veri.get("konum", ""), "metin": veri["baslik"]}]
    for i, s in enumerate(veri.get("slaytlar", []), start=1):
        if s.get("foto"):
            sahneler.append({"foto": s["foto"], "ust": f"{i:02d}", "metin": s["baslik"]})
    return sahneler, r.get("sahne_suresi", 2.6)


def taban(foto):
    """Yakınlaşma için hedeften biraz büyük, alttan karartılmış fotoğraf."""
    bw, bh = int(W * (1 + YAKINLASMA)), int(H * (1 + YAKINLASMA))
    img = Image.open(KOK / "kaynak" / foto)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, (bw, bh), Image.LANCZOS)
    return uret.karartma(img, ust=0.35, alt=0.85)


def yazi_katmani(sahne):
    kenar = 90
    genislik = W - 2 * kenar
    k = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bf = uret.font(uret.BASLIK, 104)
    bh = uret.blok_yuksekligi(sahne["metin"], bf, genislik, 1.08)
    y = H - 560 - bh
    if sahne.get("ust"):
        uret.harfli(k, (kenar, y - 70), sahne["ust"], uret.font(uret.ARA, 30), uret.BEYAZ,
                    seffaflik=225, hiza="orta", genislik=genislik)
    uret.yaz(k, (kenar, y), sahne["metin"], bf, uret.BEYAZ, genislik, 1.08, hiza="orta")
    return k


def kapanis(veri):
    k = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    kenar = 90
    genislik = W - 2 * kenar
    cta = veri.get("cta", "Kaydet, gidince aç.")
    bf = uret.font(uret.BASLIK, 96)
    bh = uret.blok_yuksekligi(cta, bf, genislik, 1.08)
    y = (H - bh) // 2 - 60
    y = uret.yaz(k, (kenar, y), cta, bf, uret.BEYAZ, genislik, 1.08, hiza="orta") + 36
    uret.yaz(k, (kenar, y), "Daha fazla rota için takip et.", uret.font(uret.GOVDE, 40),
             (161, 161, 166), genislik, 1.4, hiza="orta")
    uret.harfli(k, (kenar, H - 460), uret.HANDLE, uret.font(uret.ARA, 34), uret.BEYAZ,
                aralik=0.04, hiza="orta", genislik=genislik, buyuk=False)
    return k.convert("RGB")


def yumusak(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def kare(tabani, katman, ilerleme, yazi_alfa):
    olcek = 1 + YAKINLASMA * (1 - ilerleme)  # kırpma küçüldükçe görüntü yavaşça yaklaşır
    cw, ch = int(W * olcek), int(H * olcek)
    bw, bh = tabani.size
    x, y = (bw - cw) // 2, (bh - ch) // 2
    img = tabani.crop((x, y, x + cw, y + ch)).resize((W, H), Image.BILINEAR).convert("RGBA")
    if yazi_alfa > 0:
        if yazi_alfa < 1:
            a = katman.getchannel("A").point(lambda v: int(v * yazi_alfa))
            gecici = katman.copy()
            gecici.putalpha(a)
            img.alpha_composite(gecici)
        else:
            img.alpha_composite(katman)
    return img.convert("RGB")


def uret_reels(json_yolu):
    veri = json.loads(Path(json_yolu).read_text(encoding="utf-8"))
    sahneler, sure = sahneleri_al(veri)
    cikis = KOK / "reels" / f"{veri['slug']}.mp4"
    cikis.parent.mkdir(exist_ok=True)

    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(cikis)],
        stdin=subprocess.PIPE,
    )

    hazir = [(taban(s["foto"]), yazi_katmani(s)) for s in sahneler]
    son = kapanis(veri)
    n = int(sure * FPS)
    g = int(GECIS * FPS)
    onceki_son = None

    for idx, (tb, kt) in enumerate(hazir):
        for f in range(n):
            ilerleme = f / (n - 1)
            alfa = yumusak((f - 6) / 12)  # yazı 0.2 sn sonra 0.4 sn'de belirir
            img = kare(tb, kt, ilerleme, alfa)
            if onceki_son is not None and f < g:
                img = Image.blend(onceki_son, img, yumusak(f / g))
            if f == n - 1:
                onceki_son = img
            ffmpeg.stdin.write(img.tobytes())

    for f in range(int(2.2 * FPS)):
        img = son if f >= g else Image.blend(onceki_son, son, yumusak(f / g))
        ffmpeg.stdin.write(img.tobytes())

    ffmpeg.stdin.close()
    ffmpeg.wait()
    print("  ", cikis.relative_to(KOK))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for d in sys.argv[1:]:
        uret_reels(d)
