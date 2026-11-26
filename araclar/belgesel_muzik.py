#!/usr/bin/env python3
"""Belgesel için kodla sentezlenen, umut dolu / büyüleyici sinematik müzik (telifsiz).

"parlak": majör tonda (I-V-vi-IV), bölümlere göre büyüyen düzenleme.
  giriş     sıcak yaylı ped + seyrek müzik kutusu notaları
  bölüm 1   parmakla çalınan gitar arpejleri + bas eklenir
  bölüm 2   müzik kutusu 8'likleri, üst oktav yaylılar, yumuşak nabız (tom + shaker)
  son       tonik akorda açık bir kapanış

uret(saniye, bolumler=[t1, t2, ...], bpm=84, kok=50, tohum=7) -> (n, 2) stereo
"""
import numpy as np

from bolgesel_muzik import can, ks
from muzik import SR, filtre, frek, yanki, yanki_ir

# I - V - vi - IV  (kök D3=50 için: D, A, Bm, G)
AKORLAR = [(0, [0, 4, 7]), (7, [0, 4, 7]), (9, [0, 3, 7]), (5, [0, 4, 7])]


def yayli(notalar, sure, guc=0.08, atak=0.9):
    n = int(sure * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for nt in notalar:
        f = frek(nt)
        vib = 1 + 0.0025 * np.sin(2 * np.pi * 5.0 * t + nt)
        for d, g in ((-0.004, 0.5), (0.0, 1.0), (0.004, 0.5)):
            faz = 2 * np.pi * np.cumsum(f * (1 + d) * vib) / SR
            x += g * (np.sin(faz) + 0.35 * np.sin(2 * faz) + 0.15 * np.sin(3 * faz))
    x = filtre(x / (len(notalar) * 2), 2200)
    z = np.minimum(1, t / atak) ** 1.5
    r = int(0.6 * SR)
    z[-r:] *= np.linspace(1, 0, r)
    return x * z * guc


def tom(guc=0.5):
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    f = 70 + 40 * np.exp(-t * 18)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6)
    return filtre(x, 400) * guc


def shaker(rng, guc=0.03):
    n = int(0.08 * SR)
    g = filtre(rng.standard_normal(n), 6000, "high")
    z = np.minimum(1, np.arange(n) / (0.015 * SR)) * np.exp(-np.arange(n) / SR / 0.03)
    return g * z * guc


def koy(iz, ses, t):
    b = int(t * SR)
    if b < 0 or b >= len(iz):
        return
    e = min(len(iz), b + len(ses))
    iz[b:e] += ses[: e - b]


def uret(saniye, bolumler=(), bpm=84, kok=50, tohum=7):
    rng = np.random.default_rng(tohum)
    v = 60 / bpm
    olcu = 4 * v
    n = int((saniye + 4) * SR)
    ped, gitar, kutu, bas, dav = (np.zeros(n) for _ in range(5))
    b1 = bolumler[0] if len(bolumler) > 0 else olcu * 2
    b2 = bolumler[1] if len(bolumler) > 1 else saniye * 0.55
    son = saniye - 3.2  # kapanış kartı

    o = 0
    while o * olcu < saniye:
        t0 = o * olcu
        ak, ar = AKORLAR[o % 4]
        r = kok + ak
        if r > kok + 6:
            r -= 12
        akor = [r + a for a in ar]
        bitis = t0 >= son
        if bitis:
            # tonik akorda açık kapanış
            akor = [kok + a for a in (0, 4, 7)]
        evre = 0 if t0 < b1 - 0.01 else (1 if t0 < b2 - 0.01 else 2)

        # yaylılar: her zaman; 2. bölümde üst oktav eklenir
        notalar = [x + 12 for x in akor] + [akor[0]]
        if evre == 2:
            notalar += [akor[1] + 24]
        koy(ped, yayli(notalar, olcu + 0.8 if not bitis else 4.5, 0.09 if evre else 0.07), t0)

        if bitis:
            koy(bas, filtre(yayli([akor[0] - 12], 4.5, 0.12), 300), t0)
            for k, nt in enumerate([akor[0] + 24, akor[1] + 24, akor[2] + 24, akor[0] + 36]):
                koy(kutu, can(nt, 2.5, 0.10), t0 + k * v / 2)
            break

        # müzik kutusu
        if evre == 0:
            for k in (0, 2):
                koy(kutu, can(akor[[0, 2][k // 2]] + 24, 1.8, 0.07), t0 + k * v)
        elif evre == 2:
            desen = [0, 1, 2, 1, 2, 0, 1, 2]
            for k in range(8):
                koy(kutu, can(akor[desen[k]] + 24 + (12 if k == 4 else 0), 1.3, 0.06 if k % 2 else 0.085),
                    t0 + k * v / 2)

        # gitar arpeji (bölüm 1'den itibaren)
        if evre >= 1:
            desen = [akor[0] - 12, akor[2], akor[1] + 12, akor[2], akor[0] + 12, akor[2], akor[1] + 12, akor[2]]
            for k, nt in enumerate(desen):
                kuv = 0.22 if k == 0 else (0.15 if k % 2 == 0 else 0.11)
                koy(gitar, ks(nt, 1.6, rng, parlak=0.35, sonum=0.9, guc=kuv), t0 + k * v / 2 + rng.uniform(0, 0.012))
            koy(bas, filtre(yayli([akor[0] - 12], olcu + 0.3, 0.16, 0.05), 350), t0)

        # yumuşak nabız (bölüm 2)
        if evre == 2:
            for k in (0, 2):
                koy(dav, tom(0.42 if k == 0 else 0.3), t0 + k * v)
            for k in range(8):
                koy(dav, shaker(rng, 0.03 if k % 2 else 0.02), t0 + k * v / 2)
        o += 1

    ir = yanki_ir(2.6, rng)
    ped = yanki(ped, ir, 0.5)
    kutu = yanki(kutu, ir, 0.7)
    gitar = yanki(filtre(gitar, 3800), ir, 0.3)
    sol = ped * 1.0 + kutu * 0.7 + gitar * 1.0 + bas * 0.9 + dav * 0.8
    sag = ped * 1.0 + kutu * 1.0 + gitar * 0.75 + bas * 0.9 + dav * 0.8
    sag = 0.85 * sag + 0.15 * np.roll(sag, int(0.012 * SR))
    st = np.stack([sol, sag], axis=1)[: int(saniye * SR)]
    a = int(1.5 * SR)
    st[:a] *= np.linspace(0, 1, a)[:, None]
    st = np.tanh(st / (np.max(np.abs(st)) or 1) * 1.2)
    return st / np.max(np.abs(st)) * 0.9


# ---------- "yumusak": kulak yormayan, sıcak piyano + ped (perküsyon ve çan yok) ----------

def piyano(nota, sure=2.5, guc=0.2):
    n = int(sure * SR)
    t = np.arange(n) / SR
    f = frek(nota)
    x = (np.sin(2 * np.pi * f * t) + 0.28 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 2.5)
         + 0.08 * np.sin(2 * np.pi * 3 * f * t) * np.exp(-t * 4))
    z = np.minimum(1, t / 0.006) * np.exp(-t * (0.9 + nota / 120))
    r = int(0.08 * SR)
    z[-r:] *= np.linspace(1, 0, r)
    return filtre(x * z, 2400) * guc


def sicak_ped(notalar, sure, guc=0.06, atak=1.2):
    n = int(sure * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for nt in notalar:
        f = frek(nt)
        for d in (-0.002, 0.002):
            x += np.sin(2 * np.pi * f * (1 + d) * t) + 0.12 * np.sin(2 * np.pi * 2 * f * (1 + d) * t)
    x = filtre(x / (2 * len(notalar)), 1500)
    z = np.minimum(1, t / atak) ** 2
    r = int(min(1.0, sure / 3) * SR)
    z[-r:] *= np.linspace(1, 0, r)
    return x * z * guc


def yumusak(saniye, bolumler=(), bpm=76, kok=50, tohum=7):
    rng = np.random.default_rng(tohum)
    v = 60 / bpm
    olcu = 4 * v
    n = int((saniye + 5) * SR)
    ped, pi, bas = np.zeros(n), np.zeros(n), np.zeros(n)
    b1 = bolumler[0] if len(bolumler) > 0 else olcu * 2
    b2 = bolumler[1] if len(bolumler) > 1 else saniye * 0.55
    son = saniye - 3.2
    o = 0
    while o * olcu < saniye:
        t0 = o * olcu
        ak, ar = AKORLAR[o % 4]
        r = kok + ak
        if r > kok + 6:
            r -= 12
        akor = [r + a for a in ar]
        if t0 >= son:
            akor = [kok + a for a in (0, 4, 7)]
            koy(ped, sicak_ped([akor[0], akor[1] + 12, akor[2] + 12], 5.0, 0.07), t0)
            koy(bas, sicak_ped([akor[0] - 12], 5.0, 0.10, 0.3), t0)
            for k, nt in enumerate([akor[0] + 12, akor[1] + 12, akor[2] + 12, akor[0] + 24]):
                koy(pi, piyano(nt, 4.0, 0.16), t0 + k * v / 2)
            break
        evre = 0 if t0 < b1 - 0.01 else (1 if t0 < b2 - 0.01 else 2)
        koy(ped, sicak_ped([akor[0], akor[1] + 12, akor[2] + 12] + ([akor[0] + 24] if evre == 2 else []),
                           olcu + 1.0, 0.055 + 0.01 * evre), t0)
        if evre == 0:
            for k, nt in enumerate([akor[0] + 12, akor[2] + 12]):
                koy(pi, piyano(nt, 3.0, 0.13), t0 + k * 2 * v)
        else:
            desen = [akor[0], akor[2], akor[1] + 12, akor[2]] if evre == 1 else \
                    [akor[0], akor[2], akor[1] + 12, akor[2] + 12, akor[0] + 24, akor[2] + 12, akor[1] + 12, akor[2]]
            adim = olcu / len(desen)
            for k, nt in enumerate(desen):
                kuv = 0.16 if k == 0 else 0.11
                koy(pi, piyano(nt, 2.4, kuv), t0 + k * adim + rng.uniform(0, 0.01))
            if evre == 2 and o % 2 == 1:  # ara sıra üstte tek melodi notası
                koy(pi, piyano(akor[1] + 24, 3.0, 0.08), t0 + 2 * v)
            koy(bas, sicak_ped([akor[0] - 12], olcu + 0.4, 0.11, 0.15), t0)
        o += 1
    ir = yanki_ir(3.0, rng)
    ped = yanki(ped, ir, 0.4)
    pi = yanki(pi, ir, 0.45)
    sol = ped + pi * 1.0 + bas
    sag = ped + pi * 0.85 + bas
    sag = 0.85 * sag + 0.15 * np.roll(sag, int(0.015 * SR))
    st = np.stack([sol, sag], axis=1)[: int(saniye * SR)]
    a = int(1.2 * SR)
    st[:a] *= np.linspace(0, 1, a)[:, None]
    st = filtre(st.T, 5000).T
    return st / (np.max(np.abs(st)) or 1) * 0.85
