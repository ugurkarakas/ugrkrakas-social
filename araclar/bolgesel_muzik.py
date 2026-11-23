"""Bölgeye göre arka plan müziği: her rota kendi enstrümanları ve ritmiyle.

Hepsi kodla sentezlenir (örnek/sample yok), telif sorunu yoktur.
muzik.uret() tarafından çağrılır; tarzlar: fas, hindistan, laponya, viyana, kapadokya, tiflis.
"""
import numpy as np
from scipy.signal import fftconvolve

from muzik import (SR, TARZLAR, bas_nota, clap, filtre, frek, kick, pad, shaker, testere,
                   yanki, yanki_ir, yerlestir)

# ---------- ölçekler ----------
HICAZ = [0, 1, 4, 5, 7, 8, 10]
BHAIRAV = [0, 1, 4, 5, 7, 8, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]
MAJOR = [0, 2, 4, 5, 7, 9, 11]
DORIAN = [0, 2, 3, 5, 7, 9, 10]


def derece(kok, olcek, d):
    o, i = divmod(d, len(olcek))
    return kok + 12 * o + olcek[i]


# ---------- enstrümanlar ----------

def ks(nota, sure, rng, parlak=0.6, sonum=0.6, guc=0.3):
    """Karplus-Strong telli çalgı (ud, bağlama, panduri, pizzicato)."""
    n = int(sure * SR)
    N = max(2, int(SR / frek(nota)))
    gurultu = rng.uniform(-1, 1, N)
    if parlak < 1:
        gurultu = filtre(gurultu, 800 + 9000 * parlak)
    out = np.zeros(n)
    out[: min(N, n)] = gurultu[: min(N, n)]
    d = np.exp(-N / SR / sonum)
    i = N
    while i < n:
        onceki = out[i - N:i]
        yeni = 0.5 * (onceki + np.roll(onceki, 1)) * d
        L = min(N, n - i)
        out[i:i + L] = yeni[:L]
        i += N
    a = int(0.002 * SR)
    out[:a] *= np.linspace(0, 1, a)
    return out * guc


def sitar(nota, sure, rng, guc=0.28):
    x = ks(nota, sure, rng, parlak=0.9, sonum=0.9, guc=1.0)
    buzz = filtre(np.tanh(x * 5), [1800, 6000], "band")  # jawari vızıltısı
    return (x * 0.7 + buzz * 0.35) * guc


def darbuka(tip, rng, guc=1.0):
    if tip == "D":  # dum
        n = int(0.35 * SR)
        t = np.arange(n) / SR
        f = 85 + 110 * np.exp(-t * 40)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
        x += filtre(rng.standard_normal(n), 400) * np.exp(-t * 60) * 0.4
        return x * 0.9 * guc
    n = int(0.12 * SR)  # tek / ka
    t = np.arange(n) / SR
    x = filtre(rng.standard_normal(n), [2500, 8000], "band") * np.exp(-t * 70)
    x += np.sin(2 * np.pi * 620 * t) * np.exp(-t * 55) * 0.5
    return x * (0.55 if tip == "T" else 0.22) * guc


def bendir(tip, rng, guc=1.0):
    if tip == "D":
        n = int(0.6 * SR)
        t = np.arange(n) / SR
        f = 60 + 50 * np.exp(-t * 25)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5)
    else:
        n = int(0.25 * SR)
        t = np.arange(n) / SR
        x = filtre(rng.standard_normal(n), [800, 3000], "band") * np.exp(-t * 40) * 0.6
    tel = filtre(rng.standard_normal(n), 3000, "high") * np.exp(-np.arange(n) / SR * 18) * 0.12  # zar teli
    return (x + tel) * guc


def tabla(bol, kok, rng, guc=1.0):
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    f0 = frek(kok + 12)
    if bol in ("na", "dha", "dhin", "ta"):  # sağ el, akortlu çınlama
        sonum = 9 if bol in ("na", "ta") else 5
        for h, a in ((1, 1.0), (2, 0.5), (3, 0.3), (4, 0.15)):
            x += a * np.sin(2 * np.pi * f0 * h * t) * np.exp(-t * sonum * (1 + 0.3 * h))
        x += filtre(rng.standard_normal(n), 3000, "high") * np.exp(-t * 120) * 0.3
        x *= 0.35
    if bol in ("ge", "dha", "dhin"):  # sol el, yükselen bas
        f = 75 + 45 * (1 - np.exp(-t * 8))
        x += np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6) * 0.6
    if bol == "tin":
        x += np.sin(2 * np.pi * f0 * t) * np.exp(-t * 25) * 0.2
    return x * guc


def tanpura(nota, sure, guc=0.09):
    n = int(sure * SR)
    t = np.arange(n) / SR
    f = frek(nota)
    x = np.zeros(n)
    for h in range(1, 13):
        lfo = 0.6 + 0.4 * np.sin(2 * np.pi * (0.3 + 0.07 * h) * t + h)
        x += (1 / h) * lfo * np.sin(2 * np.pi * f * h * t)
    z = np.minimum(1, t / 0.05) * np.exp(-t / (sure * 0.6))
    return x * z * guc


def ney(nota, sure, rng, guc=0.22):
    n = int(sure * SR)
    t = np.arange(n) / SR
    f = frek(nota) * (1 + 0.004 * np.sin(2 * np.pi * 5.2 * t) * np.minimum(1, t / 0.4))
    faz = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(faz) + 0.25 * np.sin(2 * faz) + 0.08 * np.sin(3 * faz)
    nefes = filtre(rng.standard_normal(n), [frek(nota) * 0.8, frek(nota) * 3], "band") * 0.35
    z = np.minimum(1, t / 0.09) * np.minimum(1, (sure - t) / 0.12)
    return (x + nefes) * np.clip(z, 0, 1) * guc


def can(nota, sure=1.2, guc=0.16):
    """Glockenspiel / çan."""
    n = int(sure * SR)
    t = np.arange(n) / SR
    f = frek(nota)
    x = np.zeros(n)
    for o, a, s in ((1, 1.0, 1.6), (2.76, 0.4, 4), (5.4, 0.2, 8), (8.93, 0.1, 14)):
        x += a * np.sin(2 * np.pi * f * o * t) * np.exp(-t * s)
    a = int(0.001 * SR)
    x[:a] *= np.linspace(0, 1, a)
    return x * guc


def kizak_zili(rng, guc=0.08):
    n = int(0.18 * SR)
    x = np.zeros(n)
    for o in rng.uniform(0, 0.03, 4):
        i = int(o * SR)
        m = n - i
        tt = np.arange(m) / SR
        x[i:] += filtre(rng.standard_normal(m), 7000, "high") * np.exp(-tt * 45)
        x[i:] += 0.3 * np.sin(2 * np.pi * rng.uniform(5000, 8000) * tt) * np.exp(-tt * 40)
    return x * guc


def koro(notalar, sure, guc=0.1):
    """'Aa' sesli koro pedi (formant filtreli testere dişleri)."""
    n = int(sure * SR)
    x = np.zeros(n)
    for nt in notalar:
        x += testere(frek(nt), n, 0.006)
    x /= len(notalar)
    y = (filtre(x, [600, 850], "band") + 0.6 * filtre(x, [1050, 1350], "band")
         + 0.25 * filtre(x, [2400, 2800], "band"))
    a = int(0.35 * SR)
    z = np.ones(n)
    z[:a] = np.linspace(0, 1, a)
    z[-a:] = np.linspace(1, 0, a)
    return y * z * guc * 3


def pompala(pompa, t, uz, derin=0.5):
    b = int(t * SR)
    e = min(len(pompa), b + int(uz * SR))
    if e > b:
        pompa[b:e] = np.minimum(pompa[b:e], 1 - derin * np.exp(-np.arange(e - b) / SR / 0.1))


def bitir(katmanlar, rng, yankilar, saniye, genislik=0.18):
    """katmanlar: {ad: (iz, kazanç, pompalı_mı)}; yankilar: {ad: oran}."""
    ir = yanki_ir(1.8, rng)
    n = int(saniye * SR)
    sol = np.zeros(n)
    sag = np.zeros(n)
    pompa = katmanlar.pop("_pompa", None)
    for i, (ad, (iz, kaz, pmp)) in enumerate(katmanlar.items()):
        if ad in yankilar:
            iz = yanki(iz, ir, yankilar[ad])
        if pmp and pompa is not None:
            iz = iz * pompa
        iz = iz[:n] * kaz
        if i % 2 and genislik:
            g = int((0.009 + 0.004 * i) * SR)
            sol += iz
            sag[g:] += iz[:-g]
            sol[g:] += genislik * iz[:-g]
        else:
            sol += iz
            sag += iz
    return np.stack([sol, sag], axis=1)


def izler(n, *adlar):
    return {a: np.zeros(n) for a in adlar}


# ---------- Fas: hicaz, ud, darbuka (maksum) ----------

def fas(saniye, tohum=7):
    rng = np.random.default_rng(tohum)
    v = 60 / TARZLAR["fas"]["bpm"]
    s16 = v / 4
    olcu = 4 * v
    n = int(saniye * SR) + SR
    z = izler(n, "dav", "bas", "ud", "ped", "kick")
    pompa = np.ones(n)
    kok = 62
    akor_kok = [0, 1, 0, -2]
    maksum = {0: "D", 2: "T", 6: "T", 8: "D", 12: "T"}
    motif_a = [(0, 4), (2, 5), (3, 4), (4, 3), (6, 2), (8, 1), (10, 2), (12, 0), (14, 1)]
    motif_b = [(0, 7), (2, 6), (4, 5), (6, 4), (8, 5), (9, 4), (10, 3), (12, 1), (14, 0)]
    for o in range(int(np.ceil(saniye / olcu)) + 1):
        t0 = o * olcu
        ak = kok + akor_kok[o % 4]
        yerlestir(z["ped"], pad([ak - 12, ak - 5, ak], int(olcu * SR), 0.08), t0 * SR)
        for k in range(16):
            t = t0 + k * s16
            if k in maksum:
                yerlestir(z["dav"], darbuka(maksum[k], rng), t * SR)
            elif k % 2:
                yerlestir(z["dav"], darbuka("K", rng, 0.8 + 0.4 * rng.random()), t * SR)
            if k % 4 == 0:
                yerlestir(z["kick"], kick(0.7), t * SR)
                pompala(pompa, t, v, 0.45)
            if k in (4, 12):
                yerlestir(z["dav"], clap(rng) * 0.5, t * SR)
        for k, uz in ((0, 3), (3, 1), (6, 2), (8, 2), (11, 1), (14, 2)):
            yerlestir(z["bas"], bas_nota(ak - 24 + (7 if k == 6 else 0), uz * s16), (t0 + k * s16) * SR)
        if o >= 1:
            motif = motif_a if o % 2 else motif_b
            for k, d in motif:
                nt = derece(kok, HICAZ, d)
                yerlestir(z["ud"], ks(nt, 0.6, rng, parlak=0.55, sonum=0.5, guc=0.32), (t0 + k * s16) * SR)
                if k % 4 == 0:  # ud'un tipik çift vuruşu
                    yerlestir(z["ud"], ks(nt, 0.3, rng, 0.5, 0.3, 0.15), (t0 + (k + 1) * s16) * SR)
    return bitir({"dav": (z["dav"], 0.75, False), "kick": (z["kick"], 0.7, False), "bas": (z["bas"], 1.0, True),
                  "ud": (z["ud"], 1.1, True), "ped": (z["ped"], 1.0, True), "_pompa": pompa},
                 rng, {"ud": 0.4, "ped": 0.3, "dav": 0.08}, saniye)


# ---------- Hindistan: bhairav, sitar, tabla, tanpura ----------

def hindistan(saniye, tohum=7):
    rng = np.random.default_rng(tohum)
    v = 60 / TARZLAR["hindistan"]["bpm"]
    s16 = v / 4
    olcu = 4 * v
    n = int(saniye * SR) + 3 * SR
    z = izler(n, "tabla", "tan", "sitar", "bas", "kick", "sh")
    kok = 60
    teka = {0: "dha", 2: "dhin", 4: "dhin", 6: "dha", 8: "dha", 10: "dhin", 12: "dhin", 14: "dha"}
    teka2 = {0: "dha", 2: "tin", 4: "tin", 6: "na", 8: "ta", 10: "dhin", 12: "dhin", 14: "dha"}
    motif_a = [(0, 4), (3, 5), (4, 4), (6, 2), (8, 1), (10, 2), (11, 1), (12, 0)]
    motif_b = [(0, 7), (2, 6), (4, 5), (6, 4), (7, 5), (8, 4), (10, 2), (12, 1), (14, 0)]
    for o in range(int(np.ceil(saniye / olcu)) + 1):
        t0 = o * olcu
        for i, nt in enumerate((kok - 5, kok, kok, kok - 12)):  # Pa Sa Sa Sa
            yerlestir(z["tan"], tanpura(nt, 2.6), (t0 + i * v) * SR)
        desen = teka if o % 2 == 0 else teka2
        for k in range(16):
            t = t0 + k * s16
            if k in desen:
                yerlestir(z["tabla"], tabla(desen[k], kok, rng), t * SR)
            elif k % 2:
                yerlestir(z["tabla"], tabla("na" if k % 4 == 1 else "ge", kok, rng, 0.35), t * SR)
            yerlestir(z["sh"], shaker(rng, 0.05 if k % 2 else 0.03), t * SR)
            if k in (0, 8):
                yerlestir(z["kick"], kick(0.6), t * SR)
        for k in (0, 6, 10):
            yerlestir(z["bas"], bas_nota(kok - 24, 3 * s16), (t0 + k * s16) * SR)
        if o >= 1:
            motif = motif_a if o % 2 else motif_b
            for j, (k, d) in enumerate(motif):
                nt = derece(kok, BHAIRAV, d)
                if j % 3 == 0:  # meend: alttan süsleme notası
                    yerlestir(z["sitar"], sitar(nt - 1, 0.08, rng, 0.2), (t0 + k * s16 - 0.06) * SR)
                yerlestir(z["sitar"], sitar(nt, 0.8, rng), (t0 + k * s16) * SR)
    return bitir({"tabla": (z["tabla"], 0.9, False), "tan": (z["tan"], 1.0, False), "kick": (z["kick"], 0.6, False),
                  "sitar": (z["sitar"], 1.1, False), "bas": (z["bas"], 0.8, False), "sh": (z["sh"], 1.0, False)},
                 rng, {"sitar": 0.45, "tabla": 0.12, "tan": 0.3}, saniye)


# ---------- Laponya: çanlar, geniş ped, yumuşak nabız ----------

def laponya(saniye, tohum=7):
    rng = np.random.default_rng(tohum)
    v = 60 / TARZLAR["laponya"]["bpm"]
    s16 = v / 4
    olcu = 4 * v
    n = int(saniye * SR) + 2 * SR
    z = izler(n, "ped", "koro", "can", "bas", "dav", "zil")
    pompa = np.ones(n)
    kok = 57
    akorlar = [(0, [0, 3, 7, 14]), (-4, [0, 4, 7, 14]), (3, [0, 4, 7, 14]), (-2, [0, 4, 7, 14])]
    for o in range(int(np.ceil(saniye / olcu)) + 1):
        t0 = o * olcu
        ak, ar = akorlar[o % 4]
        notalar = [kok + ak + a for a in ar]
        yerlestir(z["ped"], pad([x - 12 for x in notalar], int(olcu * SR) + SR // 2, 0.12), t0 * SR)
        yerlestir(z["koro"], koro([kok + ak, kok + ak + 7], olcu + 0.5, 0.08), t0 * SR)
        yerlestir(z["bas"], bas_nota(kok + ak - 24, olcu * 0.95), t0 * SR)
        for k in range(16):
            t = t0 + k * s16
            if k in (0, 10):
                yerlestir(z["dav"], kick(0.8), t * SR)
                pompala(pompa, t, v, 0.4)
            if k in (4, 12):
                yerlestir(z["dav"], clap(rng) * 0.45, t * SR)
            yerlestir(z["zil"], kizak_zili(rng, 0.035 if k % 2 else 0.05), t * SR)
            if k % 2 == 0:
                sira = [0, 2, 1, 3, 2, 1, 3, 2][(k // 2) % 8]
                yerlestir(z["can"], can(notalar[sira] + 24, 1.4, 0.12 if o else 0.08), t * SR)
    return bitir({"ped": (z["ped"], 1.0, True), "koro": (z["koro"], 1.0, True), "can": (z["can"], 1.0, False),
                  "bas": (z["bas"], 0.9, True), "dav": (z["dav"], 0.8, False), "zil": (z["zil"], 1.0, False),
                  "_pompa": pompa}, rng, {"can": 0.7, "ped": 0.5, "koro": 0.6, "dav": 0.25}, saniye, 0.25)


# ---------- Viyana: 3/4 vals, pizzicato, glockenspiel, kızak zilleri ----------

def viyana(saniye, tohum=7):
    rng = np.random.default_rng(tohum)
    v = 60 / TARZLAR["viyana"]["bpm"]
    s8 = v / 2
    olcu = 3 * v
    n = int(saniye * SR) + 2 * SR
    z = izler(n, "pizz", "can", "bas", "zil", "dav", "ped")
    kok = 55
    akorlar = [(0, [0, 4, 7]), (-3, [0, 3, 7]), (-7, [0, 4, 7]), (2, [0, 4, 7])]  # G Em C D
    motif_a = [(0, 4, 2), (2, 2, 2), (4, 4, 2), (6, 7, 4), (10, 6, 2)]
    motif_b = [(0, 8, 2), (2, 7, 2), (4, 5, 2), (6, 4, 4), (10, 2, 2)]
    for o in range(int(np.ceil(saniye / olcu)) + 1):
        t0 = o * olcu
        ak, ar = akorlar[(o // 2) % 4]
        notalar = [kok + ak + a for a in ar]
        if o % 2 == 0:
            yerlestir(z["ped"], pad([x for x in notalar], int(2 * olcu * SR), 0.06), t0 * SR)
        # um-pa-pa
        yerlestir(z["bas"], ks(kok + ak - 24, 0.6, rng, 0.35, 0.4, 0.5), t0 * SR)
        yerlestir(z["dav"], kick(0.55), t0 * SR)
        for b in (1, 2):
            for nt in notalar:
                yerlestir(z["pizz"], ks(nt, 0.3, rng, 0.45, 0.18, 0.14), (t0 + b * v) * SR)
        for b in range(3):
            yerlestir(z["zil"], kizak_zili(rng, 0.09 if b == 0 else 0.06), (t0 + b * v) * SR)
            yerlestir(z["zil"], kizak_zili(rng, 0.035), (t0 + b * v + s8) * SR)
        if True:
            motif = motif_a if (o // 2) % 2 == 0 else motif_b
            yari = 0 if o % 2 == 0 else 6
            for k, d, uz in motif:
                if yari <= k < yari + 6:
                    yerlestir(z["can"], can(derece(kok + 12, MAJOR, d), 1.2, 0.17), (t0 + (k - yari) * s8) * SR)
    return bitir({"pizz": (z["pizz"], 1.0, False), "can": (z["can"], 1.0, False), "bas": (z["bas"], 1.0, False),
                  "zil": (z["zil"], 1.0, False), "dav": (z["dav"], 0.7, False), "ped": (z["ped"], 1.0, False)},
                 rng, {"can": 0.55, "pizz": 0.35, "ped": 0.5}, saniye, 0.22)


# ---------- Kapadokya: hicaz, ney, bağlama, bendir ----------

def kapadokya(saniye, tohum=7):
    rng = np.random.default_rng(tohum)
    v = 60 / TARZLAR["kapadokya"]["bpm"]
    s16 = v / 4
    olcu = 4 * v
    n = int(saniye * SR) + 2 * SR
    z = izler(n, "ney", "saz", "dav", "bas", "ped", "kick")
    pompa = np.ones(n)
    kok = 57
    usul = {0: "D", 4: "T", 6: "T", 8: "D", 10: "D", 12: "T"}
    saz_desen = [0, 0, 4, 0, 0, 0, 3, 1, 0, 0, 4, 0, 5, 4, 3, 1]
    motif_a = [(0, 4, 4), (4, 5, 2), (6, 4, 2), (8, 2, 4), (12, 1, 2), (14, 0, 2)]
    motif_b = [(0, 7, 6), (6, 5, 2), (8, 4, 4), (12, 2, 4)]
    for o in range(int(np.ceil(saniye / olcu)) + 1):
        t0 = o * olcu
        yerlestir(z["ped"], pad([kok - 12, kok - 5], int(olcu * SR) + SR // 3, 0.1), t0 * SR)
        for k in range(16):
            t = t0 + k * s16
            if k in usul:
                yerlestir(z["dav"], bendir(usul[k], rng), t * SR)
            elif k % 2:
                yerlestir(z["dav"], darbuka("K", rng, 0.7), t * SR)
            if k in (0, 8):
                yerlestir(z["kick"], kick(0.75), t * SR)
                pompala(pompa, t, v, 0.35)
            yerlestir(z["saz"], ks(derece(kok, HICAZ, saz_desen[k]), 0.25, rng, 0.8, 0.25, 0.13), t * SR)
        for k in (0, 6, 8, 14):
            yerlestir(z["bas"], bas_nota(kok - 24, 2 * s16), (t0 + k * s16) * SR)
        if True:
            motif = motif_a if o % 2 else motif_b
            for k, d, uz in motif:
                yerlestir(z["ney"], ney(derece(kok + 12, HICAZ, d), uz * s16 + 0.08, rng), (t0 + k * s16) * SR)
    return bitir({"ney": (z["ney"], 1.0, False), "saz": (z["saz"], 1.0, True), "dav": (z["dav"], 0.8, False),
                  "kick": (z["kick"], 0.6, False), "bas": (z["bas"], 0.9, True), "ped": (z["ped"], 1.0, True),
                  "_pompa": pompa}, rng, {"ney": 0.6, "saz": 0.3, "ped": 0.4, "dav": 0.1}, saniye)


# ---------- Tiflis: 6/8 Gürcü dansı, panduri, koro, doli ----------

def tiflis(saniye, tohum=7):
    rng = np.random.default_rng(tohum)
    v = 60 / TARZLAR["tiflis"]["bpm"]  # noktalı dörtlük
    s8 = v / 3
    olcu = 2 * v  # 6/8
    n = int(saniye * SR) + 2 * SR
    z = izler(n, "doli", "pand", "koro", "bas", "mel")
    kok = 62
    akorlar = [0, -2, 0, -5]  # Dm C Dm Am (dorian)
    motif_a = [(0, 4), (1, 3), (2, 2), (3, 4), (5, 2)]
    motif_b = [(0, 7), (2, 6), (3, 4), (4, 3), (5, 1)]
    for o in range(int(np.ceil(saniye / olcu)) + 1):
        t0 = o * olcu
        ak = akorlar[(o // 2) % 4]
        nota_akor = [kok + ak + a for a in ([0, 3, 7] if ak in (0, -5) else [0, 4, 7])]
        if o % 2 == 0:
            yerlestir(z["koro"], koro([kok + ak - 12, kok + ak - 5, kok + ak], 2 * olcu + 0.4, 0.09), t0 * SR)
        for k in range(6):
            t = t0 + k * s8
            if k in (0, 3):
                yerlestir(z["doli"], darbuka("D", rng, 1.0), t * SR)
                yerlestir(z["doli"], kick(0.5), t * SR)
            elif k in (2, 5):
                yerlestir(z["doli"], darbuka("T", rng, 0.9), t * SR)
            else:
                yerlestir(z["doli"], darbuka("K", rng, 0.9), t * SR)
            # panduri: aşağı-yukarı tıngırtı
            for j, nt in enumerate(nota_akor if k % 3 == 0 else nota_akor[1:]):
                yerlestir(z["pand"], ks(nt, 0.35, rng, 0.6, 0.25, 0.09), (t + j * 0.012) * SR)
        yerlestir(z["bas"], bas_nota(kok + ak - 24, v * 0.9), t0 * SR)
        yerlestir(z["bas"], bas_nota(kok + ak - 17, v * 0.9), (t0 + v) * SR)
        if o >= 1:
            motif = motif_a if (o // 2) % 2 == 0 else motif_b
            for k, d in motif:
                yerlestir(z["mel"], ks(derece(kok + 12, DORIAN, d), 0.5, rng, 0.75, 0.4, 0.24), (t0 + k * s8) * SR)
    return bitir({"doli": (z["doli"], 0.8, False), "pand": (z["pand"], 1.0, False), "koro": (z["koro"], 1.0, False),
                  "bas": (z["bas"], 0.9, False), "mel": (z["mel"], 1.0, False)},
                 rng, {"koro": 0.6, "mel": 0.4, "pand": 0.3, "doli": 0.1}, saniye)


BOLGELER = {"fas": fas, "hindistan": hindistan, "laponya": laponya, "viyana": viyana,
            "kapadokya": kapadokya, "tiflis": tiflis}


# ---------- Paris: manouche caz / musette, akordeon, pompe gitar, fırça davul ----------

def akordeon(nota, sure, guc=0.13):
    n = int(sure * SR)
    t = np.arange(n) / SR
    f = frek(nota)
    x = testere(f, n, 0.004) + 0.6 * testere(f * 1.004, n) + 0.4 * np.sign(np.sin(2 * np.pi * f * 0.5 * t)) * 0.3
    x = filtre(x, [300, 3200], "band")
    tremolo = 1 + 0.18 * np.sin(2 * np.pi * 5.8 * t)
    z = np.minimum(1, t / 0.03) * np.minimum(1, np.maximum(0, (sure - t) / 0.06))
    return x * tremolo * z * guc


def firca(rng, guc=0.08):
    n = int(0.18 * SR)
    t = np.arange(n) / SR
    return filtre(rng.standard_normal(n), [2000, 7000], "band") * np.minimum(1, t / 0.02) * np.exp(-t * 14) * guc


def paris(saniye, tohum=7):
    rng = np.random.default_rng(tohum)
    v = 60 / TARZLAR["paris"]["bpm"]
    olcu = 4 * v
    sw = v * 0.62  # swing: ikinci sekizlik geç gelir
    n = int(saniye * SR) + 2 * SR
    z = izler(n, "gitar", "bas", "ako", "dav")
    kok = 57  # La minör
    akorlar = [(0, [0, 3, 7, 12]), (5, [0, 3, 7, 10]), (7, [0, 4, 7, 10]), (0, [0, 3, 7, 9])]  # Am Dm7 E7 Am6
    HARM = [0, 2, 3, 5, 7, 8, 11]
    motif_a = [(0, 0, 7), (1, 0, 6), (1, 1, 4), (2, 0, 7), (3, 0, 9), (3, 1, 7)]
    motif_b = [(0, 0, 11), (0, 1, 10), (1, 0, 9), (2, 0, 7), (2, 1, 6), (3, 0, 4)]
    for o in range(int(np.ceil(saniye / olcu)) + 1):
        t0 = o * olcu
        ak, ar = akorlar[o % 4]
        notalar = [kok + ak - 12 + a for a in ar]
        for b in range(4):
            tb = t0 + b * v
            # pompe: 1 ve 3 bas, 2 ve 4 kısa vurulan akor
            if b % 2 == 0:
                yerlestir(z["bas"], ks(kok + ak - 24 + (7 if b == 2 else 0), v * 0.9, rng, 0.35, 0.35, 0.55), tb * SR)
            for j, nt in enumerate(notalar):
                yerlestir(z["gitar"], ks(nt + 12, 0.12 if b % 2 else 0.2, rng, 0.75, 0.07 if b % 2 else 0.12,
                                         0.12 if b % 2 else 0.07), (tb + j * 0.006) * SR)
            yerlestir(z["dav"], firca(rng, 0.09 if b % 2 else 0.05), tb * SR)
            yerlestir(z["dav"], firca(rng, 0.04), (tb + sw) * SR)
        motif = motif_a if (o // 2) % 2 == 0 else motif_b
        for b, yari, d in motif:
            tt = t0 + b * v + (sw if yari else 0)
            uz = (v - sw) if yari else sw
            yerlestir(z["ako"], akordeon(derece(kok + 12, HARM, d), uz * 1.6 + 0.05), tt * SR)
    return bitir({"gitar": (z["gitar"], 1.0, False), "bas": (z["bas"], 0.9, False), "ako": (z["ako"], 1.0, False),
                  "dav": (z["dav"], 1.0, False)}, rng, {"ako": 0.35, "gitar": 0.2, "dav": 0.15}, saniye)




# ---------- Paris (romantik): yumuşak piyano, naylon telli gitar, sıcak akordeon pedi ----------

def piyano(nota, sure, guc=0.16):
    n = int(sure * SR)
    t = np.arange(n) / SR
    f = frek(nota)
    x = np.zeros(n)
    for h, a in ((1, 1.0), (2, 0.42), (3, 0.18), (4, 0.08), (5, 0.04)):
        x += a * np.sin(2 * np.pi * f * h * (1 + 0.0004 * h * h) * t) * np.exp(-t * (1.1 + 0.9 * h))
    a = int(0.008 * SR)
    x[:a] *= np.linspace(0, 1, a)
    return x * guc


def sicak_ped(notalar, sure, guc=0.05):
    """Akordeon/yaylı benzeri, yumuşatılmış sıcak ped (sinüs ağırlıklı)."""
    n = int(sure * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for nt in notalar:
        f = frek(nt)
        x += np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t) + 0.08 * np.sin(2 * np.pi * 3 * f * t)
    x *= 1 + 0.08 * np.sin(2 * np.pi * 4.5 * t)
    a = int(0.6 * SR)
    z = np.ones(n)
    z[:a] = np.linspace(0, 1, a)
    z[-a:] = np.linspace(1, 0, a)
    return x / len(notalar) * z * guc


def paris(saniye, tohum=7):
    rng = np.random.default_rng(tohum)
    v = 60 / TARZLAR["paris"]["bpm"]
    olcu = 4 * v
    s8 = v / 2
    n = int(saniye * SR) + 3 * SR
    z = izler(n, "piyano", "gitar", "ped", "bas", "mel")
    kok = 53  # Fa majör
    akorlar = [(0, [0, 4, 7, 11]), (-3, [0, 3, 7, 10]), (2, [0, 3, 7, 10]), (7, [0, 4, 7, 10])]  # Fmaj7 Dm7 Gm7 C7
    motif_a = [(0, 9, 3), (3, 7, 1), (4, 4, 2), (6, 2, 2)]
    motif_b = [(0, 7, 2), (2, 9, 2), (4, 11, 3), (7, 9, 1)]
    for o in range(int(np.ceil(saniye / olcu)) + 1):
        t0 = o * olcu
        ak, ar = akorlar[o % 4]
        notalar = [kok + ak + a for a in ar]
        yerlestir(z["ped"], sicak_ped([x + 12 for x in notalar[:3]], olcu + 0.8), t0 * SR)
        yerlestir(z["bas"], piyano(kok + ak - 12, 2.5, 0.22), t0 * SR)
        yerlestir(z["bas"], piyano(kok + ak - 5, 2.0, 0.14), (t0 + 2 * v) * SR)
        # naylon gitar arpeji (sekizlikler)
        sira = [0, 1, 2, 3, 2, 1, 2, 3]
        for k in range(8):
            yerlestir(z["gitar"], ks(notalar[sira[k]] + 12, 1.2, rng, 0.3, 0.9, 0.09), (t0 + k * s8) * SR)
        if o >= 1:
            motif = motif_a if (o // 2) % 2 == 0 else motif_b
            for k, d, uz in motif:
                nt = derece(kok + 12, MAJOR, d)
                yerlestir(z["mel"], piyano(nt, uz * s8 + 1.2, 0.2), (t0 + k * s8) * SR)
    st = bitir({"piyano": (z["piyano"], 1.0, False), "gitar": (z["gitar"], 1.0, False), "ped": (z["ped"], 1.0, False),
                "bas": (z["bas"], 1.0, False), "mel": (z["mel"], 1.0, False)},
               rng, {"mel": 0.5, "gitar": 0.35, "ped": 0.5, "bas": 0.2}, saniye, 0.25)
    return np.stack([filtre(st[:, 0], 5500), filtre(st[:, 1], 5500)], axis=1)  # tiz yumuşatma


BOLGELER["paris"] = paris


# ---------- Mısır: hicaz, ud, ney, hafif rık/def (vlog altı için sakin) ----------

def misir(saniye, tohum=7):
    rng = np.random.default_rng(tohum)
    v = 60 / TARZLAR["misir"]["bpm"]
    s16 = v / 4
    olcu = 4 * v
    n = int(saniye * SR) + 2 * SR
    z = izler(n, "ud", "ney", "dav", "ped", "bas")
    kok = 62
    usul = {0: "D", 6: "T", 8: "D", 12: "T"}  # yumuşak maksum
    ud_desen = [(0, 0), (3, 1), (4, 2), (6, 1), (8, 0), (10, 4), (11, 3), (12, 2), (14, 1)]
    ney_a = [(0, 4, 8), (8, 5, 4), (12, 4, 4)]
    ney_b = [(0, 7, 6), (6, 5, 2), (8, 4, 8)]
    for o in range(int(np.ceil(saniye / olcu)) + 1):
        t0 = o * olcu
        yerlestir(z["ped"], pad([kok - 12, kok - 5, kok], int(olcu * SR) + SR // 3, 0.08), t0 * SR)
        yerlestir(z["bas"], bas_nota(kok - 24, olcu * 0.9), t0 * SR)
        for k in range(16):
            t = t0 + k * s16
            if k in usul:
                yerlestir(z["dav"], darbuka(usul[k], rng, 0.6), t * SR)
            elif k % 2:
                yerlestir(z["dav"], darbuka("K", rng, 0.4), t * SR)
        for k, d in ud_desen:
            yerlestir(z["ud"], ks(derece(kok, HICAZ, d), 0.7, rng, 0.5, 0.55, 0.26), (t0 + k * s16) * SR)
        if o >= 2:
            for k, d, uz in (ney_a if o % 2 else ney_b):
                yerlestir(z["ney"], ney(derece(kok + 12, HICAZ, d), uz * s16 + 0.1, rng, 0.16), (t0 + k * s16) * SR)
    return bitir({"ud": (z["ud"], 1.0, False), "ney": (z["ney"], 1.0, False), "dav": (z["dav"], 0.7, False),
                  "ped": (z["ped"], 0.9, False), "bas": (z["bas"], 0.8, False)},
                 rng, {"ud": 0.4, "ney": 0.6, "ped": 0.4, "dav": 0.1}, saniye)


BOLGELER["misir"] = misir
