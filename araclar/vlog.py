"""Kendi çekimlerinden vlog tarzı dikey video kurgusu.

Kullanım: python3 araclar/vlog.py vlog/<ad>.json
Her sahne kendi orijinal sesiyle kesilir (ses seviyesi eşitlenir), üstüne sade yazılar
bindirilir; sonunda bölgesel müzik çok alçak seviyede, konuşma/ortam sesi yükselince
kendiliğinden kısılarak (sidechain) altta çalar.

JSON:
{
  "ad": "luxor-fayton", "kaynak_klasor": "/mnt/user-data/uploads",
  "muzik": {"tarz": "misir", "tohum": 7, "seviye": 0.2},
  "kapanis": "Kaydet, Luxor planına ekle.",
  "sahneler": [
    {"dosya": "IMG_3660.mov", "bas": 0.3, "sure": 2.5,
     "ust": "LUXOR, MISIR", "baslik": "...", "alt": "..."}
  ]
}
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

KOK = Path(__file__).resolve().parent.parent
W, H, FPS = 1080, 1920, 30
FONT = KOK / "fonts"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import muzik  # noqa: E402


def f(ad, boyut):
    return ImageFont.truetype(str(FONT / ad), boyut)


def satirla(metin, fnt, genislik, d):
    kelimeler, satirlar, s = metin.split(), [], ""
    for k in kelimeler:
        dene = (s + " " + k).strip()
        if d.textlength(dene, font=fnt) <= genislik or not s:
            s = dene
        else:
            satirlar.append(s)
            s = k
    if s:
        satirlar.append(s)
    return satirlar


def bindirme(sahne, yol):
    """Sahne yazıları için şeffaf PNG."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    yazi = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(yazi)
    kenar = 90
    gen = W - 2 * kenar
    if sahne.get("ust"):
        fu = f("Inter-SemiBold.otf", 30)
        t = " ".join(sahne["ust"].replace("i", "İ").upper())
        d.text(((W - d.textlength(t, font=fu)) / 2, 300), t, font=fu, fill=(255, 255, 255, 235))
    if sahne.get("baslik"):
        fb = f("InterDisplay-SemiBold.otf", 84)
        y = 360
        for s in satirla(sahne["baslik"], fb, gen, d):
            d.text(((W - d.textlength(s, font=fb)) / 2, y), s, font=fb, fill=(255, 255, 255, 255))
            y += 96
    golge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    golge.putalpha(yazi.getchannel("A").filter(ImageFilter.GaussianBlur(16)).point(lambda a: int(a * 0.7)))
    img = Image.alpha_composite(Image.alpha_composite(img, golge), yazi)
    if sahne.get("alt"):
        fa = f("Inter-Medium.otf", 40)
        d2 = ImageDraw.Draw(img)
        satirlar = satirla(sahne["alt"], fa, gen - 60, d2)
        h = len(satirlar) * 54 + 44
        y0 = H - 430 - h
        for i, s in enumerate(satirlar):
            gw = d2.textlength(s, font=fa)
            x = (W - gw) / 2
            y = y0 + 22 + i * 54
            d2.rounded_rectangle((x - 22, y - 8, x + gw + 22, y + 50), radius=14, fill=(0, 0, 0, 120))
        for i, s in enumerate(satirlar):
            gw = d2.textlength(s, font=fa)
            d2.text(((W - gw) / 2, y0 + 22 + i * 54), s, font=fa, fill=(255, 255, 255, 255))
    img.save(yol)


def kapanis_png(metin, yol):
    img = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    fb = f("InterDisplay-SemiBold.otf", 70)
    y = 820
    for s in satirla(metin, fb, W - 200, d):
        d.text(((W - d.textlength(s, font=fb)) / 2, y), s, font=fb, fill=(255, 255, 255))
        y += 84
    fk = f("Inter-Medium.otf", 36)
    t = "@ugrkrakas"
    d.text(((W - d.textlength(t, font=fk)) / 2, y + 60), t, font=fk, fill=(170, 170, 175))
    img.save(yol)


def calistir(komut):
    r = subprocess.run(komut, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(r.stderr[-2000:])


ORTAK_V = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS)]
ORTAK_A = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


def sahne_render(s, kaynak, png, cikis):
    d = s["sure"]
    renk = s.get("renk", "eq=contrast=1.06:saturation=1.12:brightness=0.01,unsharp=5:5:0.4")
    vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
          f"crop={W}:{H}:(iw-{W})*{s.get('odak_x', 0.5)}:(ih-{H})*{s.get('odak_y', 0.5)},fps={FPS},{renk}[v];"
          f"[1:v]format=rgba,fade=t=in:st=0.12:d=0.3:alpha=1,fade=t=out:st={max(0.2, d - 0.28):.2f}:d=0.25:alpha=1[o];"
          f"[v][o]overlay=format=auto,format=yuv420p[vo];"
          f"[0:a:0]aresample=48000,loudnorm=I=-19:TP=-2:LRA=9,volume={s.get('ses', 1.0)},"
          f"afade=t=in:d=0.06,afade=t=out:st={d - 0.09:.2f}:d=0.09[ao]")
    tmp = str(cikis) + ".tmp.mp4"
    calistir(["ffmpeg", "-y", "-v", "error", "-ss", str(s["bas"]), "-t", str(d), "-i", str(kaynak),
              "-loop", "1", "-t", str(d), "-i", str(png), "-filter_complex", vf,
              "-map", "[vo]", "-map", "[ao]", *ORTAK_V, *ORTAK_A, "-t", str(d), tmp])
    os.replace(tmp, cikis)


def kapanis_render(png, cikis, sure=2.2):
    tmp = str(cikis) + ".tmp.mp4"
    calistir(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", str(png),
              "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
              "-vf", f"format=yuv420p,loop=-1:1,trim=duration={sure},fade=t=in:d=0.3",
              *ORTAK_V, *ORTAK_A, "-t", str(sure), tmp])
    os.replace(tmp, cikis)


def main(yol):
    v = json.load(open(yol))
    kaynak_klasor = Path(v.get("kaynak_klasor", "/mnt/user-data/uploads"))
    cikti = KOK / "vlog" / "cikti"
    cikti.mkdir(parents=True, exist_ok=True)
    gecici = Path(tempfile.mkdtemp(prefix="vlog-"))
    parcalar = []
    for i, s in enumerate(v["sahneler"]):
        png = gecici / f"o{i}.png"
        bindirme(s, png)
        p = gecici / f"s{i:02d}.mp4"
        sahne_render(s, kaynak_klasor / s["dosya"], png, p)
        parcalar.append(p)
        print("sahne", i, s["dosya"], s["sure"])
    kp = gecici / "kapanis.png"
    kapanis_png(v.get("kapanis", "Kaydet, sonra izle."), kp)
    k = gecici / "s99.mp4"
    kapanis_render(kp, k)
    parcalar.append(k)
    liste = gecici / "liste.txt"
    liste.write_text("".join(f"file '{p}'\n" for p in parcalar))
    birlesik = gecici / "birlesik.mp4"
    calistir(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(liste), "-c", "copy", str(birlesik)])
    sure = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(birlesik)], capture_output=True, text=True).stdout)
    m = v.get("muzik", {"tarz": "misir"})
    wav = gecici / "muzik.wav"
    muzik.kaydet(muzik.uret(sure, m.get("tarz", "misir"), m.get("tohum", 7)), str(wav))
    seviye = m.get("seviye", 0.2)
    son = cikti / f"{v['ad']}.mp4"
    tmp = str(son) + ".tmp.mp4"
    calistir(["ffmpeg", "-y", "-v", "error", "-i", str(birlesik), "-i", str(wav), "-filter_complex",
              f"[1:a]aresample=48000,volume={seviye},afade=t=out:st={sure - 1.5:.2f}:d=1.5[m];"
              f"[0:a]asplit=2[a1][key];"
              f"[m][key]sidechaincompress=threshold=0.04:ratio=5:attack=30:release=400[md];"
              f"[a1][md]amix=inputs=2:normalize=0,alimiter=limit=0.95[ao]",
              "-map", "0:v", "-map", "[ao]", "-c:v", "copy", *ORTAK_A, "-movflags", "+faststart", tmp])
    os.replace(tmp, son)
    print(son, round(sure, 1), "sn")


if __name__ == "__main__":
    main(sys.argv[1])
