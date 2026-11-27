#!/usr/bin/env python3
"""Seslendirmeyi harita videosuna oturtur.

icerik JSON'undaki harita.ses = {"dosya": "ses/x.mp3", "satirlar": [[bas, bit], ...]}
(satır sırası: giriş, her kategori için [kategori, durakları...], kapanış)
Seslendirmede okunmayan bir bölüm (ör. kategori adı) için satır yerine null yazılır: o bölüm sessiz kalır.

1. Her satırın süresine göre bölüm sürelerini hesaplar ve harita.sureler'e yazar.
2. Satırları bu zamanlara yerleştirip tek bir ses izi (wav) üretir.
3. Müzikle karıştırır (müzik, konuşma sırasında kısılır).

  python3 araclar/harita_video/seslendirme.py icerik/<slug>.json zaman   -> sadece süreleri yazar
  python3 araclar/harita_video/seslendirme.py icerik/<slug>.json ses <sessiz.mp4> <cikis.mp4>
"""
import json, subprocess, sys, tempfile, os
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent.parent
yol = Path(sys.argv[1]); mod = sys.argv[2]
v = json.loads(yol.read_text(encoding="utf-8")); h = v["harita"]
satir = h["ses"]["satirlar"]
kat_sira = []
for s in h["duraklar"]:
    if s["kat"] not in kat_sira: kat_sira.append(s["kat"])

# bölüm listesi ve her bölümde konuşmanın başlayacağı an (bölüm içi)
kat_ekrani = h.get("kategori_ekrani", len(kat_sira) > 1)  # sablon.html ile aynı kural
plan = [("giris", 0.2)]
for k in kat_sira:
    if kat_ekrani:
        plan.append(("kat", 0.15))
    plan += [("durak", 0.75)] * sum(1 for s in h["duraklar"] if s["kat"] == k)
plan.append(("son", 1.35))
assert len(plan) == len(satir), f"{len(plan)} bölüm ama {len(satir)} satır"

ENAZ = {"giris": 4.4, "kat": 1.35, "durak": 3.3, "son": 4.0}
SON_BOSLUK = {"giris": 0.1, "kat": 0.1, "durak": 0.12, "son": 1.0}
sureler, yerler, t = [], [], 0.0
for (tip, ofs), ab in zip(plan, satir):
    a, b = ab if ab else (0.0, 0.0)
    d = max(ENAZ[tip], ofs + (b - a) + SON_BOSLUK[tip]) if ab else ENAZ[tip]
    sureler.append(round(d, 3)); yerler.append(round(t + ofs, 3)); t += d
h["sureler"] = sureler
yol.write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("toplam", round(t, 2), "sn")
if mod == "zaman": sys.exit()

sessiz, cikis = sys.argv[3], sys.argv[4]
kaynak = KOK / "kaynak" / h["ses"]["dosya"]
m = h.get("muzik", {})
with tempfile.TemporaryDirectory() as td:
    muz = os.path.join(td, "m.wav")
    subprocess.run([sys.executable, str(KOK / "araclar" / "muzik.py"), muz, str(int(t) + 2), m.get("tarz", "yaz"), str(m.get("tohum", 7))], check=True, capture_output=True)
    girdiler, fc = ["-i", str(kaynak)], []
    dolu = [(ab, y) for ab, y in zip(satir, yerler) if ab]
    satir = [ab for ab, _ in dolu]
    for i, ((a, b), y) in enumerate(dolu):
        fc.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st={max(0, b - a - 0.04):.3f}:d=0.04,adelay={int(y * 1000)}:all=1[s{i}]")
    fc.append("".join(f"[s{i}]" for i in range(len(satir))) + f"amix=inputs={len(satir)}:normalize=0,aresample=48000,pan=stereo|c0=c0|c1=c0,"
              "highpass=f=70,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,loudnorm=I=-16:TP=-1.5:LRA=7[ses]")
    fc.append(f"[ses]apad,atrim=0:{t:.3f},asplit=2[ses1][ses2]")
    fc.append(f"[2:a]aresample=48000,volume=0.32,afade=t=in:d=0.6,afade=t=out:st={t - 1.6:.2f}:d=1.5[muz]")
    fc.append("[muz][ses2]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=450[muzk]")
    fc.append(f"[ses1][muzk]amix=inputs=2:normalize=0:duration=longest,apad,atrim=0:{t:.3f}[a]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", sessiz, *girdiler, "-i", muz, "-filter_complex", ";".join(fc).replace("[0:a]", "[1:a]"),
                    "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "slow", "-b:v", "11M", "-maxrate", "14M", "-bufsize", "22M",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{t:.3f}", "-movflags", "+faststart", cikis], check=True)
print(cikis)
