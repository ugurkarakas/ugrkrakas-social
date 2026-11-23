"""kaynak/ fotoğraflarının Unsplash fotoğrafçıları. icerik JSON'larının
fotograf_kredisi alanını bu tablodan doldurur: python3 araclar/krediler.py"""
import json, glob, os
KREDI = {
 "laponya-aurora-1":"Vincent Guth","laponya-aurora-2":"Vincent Guth","laponya-aurora-3":"Lucas Marcomini","laponya-aurora-4":"Maud Bocquillod",
 "laponya-husky-1":"Robert Tjalondo","laponya-husky-2":"darkroomsg","laponya-husky-3":"Robert Tjalondo",
 "tokyo-shibuya-1":"mos design","tokyo-shibuya-ust":"Jivan Garcha","tokyo-teamlab-1":"Alexander Korte","tokyo-teamlab-2":"Cosmin Serban","tokyo-teamlab-3":"note thanun",
 "viyana-pazar-kemer":"Jeffrey Zhang","viyana-agac":"Mario Tuzon","viyana-rathaus":"Alisa Anton","viyana-karlsplatz":"Sami Ullah","viyana-gluhwein":"Toa Heftiba",
 "kapadokya-balon-1":"Alex Azabache","kapadokya-balon-2":"Luis Barreto D","kapadokya-balon-3":"Igor Sporynin","kapadokya-balon-4":"v2osk",
 "tiflis-gunbatimi":"Aleksandr Popov","tiflis-rike":"K T","tiflis-hacapuri":"Christine Isakzhanova",
 "seul-saray":"Trac Vu","belgrad-kale":"Andjela","bangkok-wat-arun":"Anantachai Saothong",
 "fas-chefchaouen-1":"Milad Alizadeh","fas-chefchaouen-2":"Mauro Lima","fas-chefchaouen-3":"Jaanus Jagomägi","fas-fes-tabakhane":"Aleks",
 "fas-fes-medina":"Kyle Frost","fas-riad-havuz":"Alexander Psiuk","fas-riad-cesme":"Toa Heftiba","fas-marakes-fener":"Miltiadis Fragkidis",
 "fas-cay":"Martin Zangerl","fas-sahra-2":"Mark Kuiper",
 "hindistan-tac-1":"Julian Yu","hindistan-tac-2":"Shan Elahi","hindistan-tac-3":"Hanan Edwards","hindistan-aarti-1":"Pratyush Mishra",
 "hindistan-aarti-2":"Arto Suraj","hindistan-varanasi":"Vizag Explore","hindistan-jaipur-1":"Annie Spratt","hindistan-jaipur-gece":"Martijn Vonk","hindistan-jaipur-2":"Roberto Reposo",
 "sintra-kuyu-1":"Regös Környei","sintra-kuyu-2":"Andrey Masiero","sintra-tunel":"Angel Luciano","meteora-1":"Christos Papadopoulos","meteora-2":"Stefanos Keramaris",
 "matera-1":"Daniel J. Schwarz","matera-2":"Sterling Lanier","msm-1":"Yiming Ma","msm-2":"Andrej A",
 "namibya-1":"Bernd Dittrich","namibya-2":"Bernd Dittrich","victoria-1":"Andreas Vonlanthen","victoria-2":"Ed Wingate",
 "serengeti-1":"Dawn Westveld","serengeti-2":"Jorge Tung","serengeti-aslan":"Crystal McClernon","zanzibar-1":"Javi Lorbada",
}
def fotolar(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("foto",) and isinstance(v, str): yield v
            else: yield from fotolar(v)
    elif isinstance(o, list):
        for v in o: yield from fotolar(v)
    elif isinstance(o, str) and o.endswith(".jpg"): yield o
if __name__ == "__main__":
    for yol in sorted(glob.glob("icerik/*.json")):
        if os.path.basename(yol).startswith("_") or "roma-" in yol: continue
        d = json.load(open(yol))
        adlar = []
        for f in fotolar(d):
            a = KREDI.get(f[:-4])
            if a and a not in adlar: adlar.append(a)
        if adlar:
            d["fotograf_kredisi"] = "Fotoğraflar: Unsplash (" + ", ".join(adlar) + ")"
            open(yol, "w").write(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
        print(os.path.basename(yol), "->", len(adlar), "fotoğrafçı")
