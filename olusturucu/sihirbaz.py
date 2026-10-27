"""Tablo doldurmadan bina düzeni üreten sihirbazlar.

Kurum binasını tarif eder (koridor sayısı, hangi tarafta ne var), sihirbaz BAK uygulamasının okuduğu
noktaları, yolları ve hedefleri üretir. Ayrıca 2D plan için her noktanın konumunu (adım birimiyle) verir.

Yön kuralı: kullanıcı girişten içeri bakarken "sağ" ve "sol". Koridorda ilerlerken soldaki kapı "solunuzda".
"""

from __future__ import annotations

from bak_mekan import kisalt

KONUM = dict[str, tuple[float, float]]
# Plan bilgisi QR'a girmez (QR küçük kalsın); düzen dosyasında "plan" alanında saklanır.
# {"konum": {nokta: [x, y]}, "raflar": {nokta: {"sol": "...", "sag": "..."}}}
# Konumlar adım değil çizim birimidir: kutular üst üste binmesin diye sıra numarasıyla düzenli aralanır;
# gerçek adım sayıları plandaki çizgilerin üstünde yazar.
ARALIK = 9
PLAN = dict


def _anahtarlar(ad: str, ek: str = "") -> list[str]:
    """'Süt ürünleri' → ['süt ürünleri', 'süt', 'ürünleri'] + virgülle verilen ek sözcükler"""
    ad = ad.strip()
    sozcukler = [ad.lower(), *[w.lower() for w in ad.split() if len(w) >= 3]]
    sozcukler += [e.strip().lower() for e in ek.split(",") if e.strip()]
    return list(dict.fromkeys(sozcukler))


def _yer(sira: int, adet: int) -> str:
    """Koridordaki sıraya göre: başında / ortasında / sonunda"""
    if adet <= 1:
        return ""
    oran = sira / (adet - 1)
    return "koridorun başında" if oran < 0.34 else "koridorun sonunda" if oran > 0.66 else "koridorun ortasında"


def _benzersiz(kimlik: str, kullanilan: set[str]) -> str:
    aday, i = kimlik or "nokta", 2
    while aday in kullanilan:
        aday, i = f"{kimlik}-{i}", i + 1
    kullanilan.add(aday)
    return aday


# ── Market ────────────────────────────────────────────────

def market_olustur(ad: str, koridorlar: list[dict], giris_adim: int = 8, koridor_arasi_adim: int = 6,
                   koridor_boyu_adim: int = 15, kasa_adim: int = 10, siralama: str = "sag") -> tuple[dict, PLAN]:
    """koridorlar: [{"sol": "Süt, Peynir", "sag": "Ekmek"}...] girişten itibaren sırayla.
    Her taraftaki reyonlar koridor girişinden sonuna doğru virgülle yazılır.
    siralama: koridorlar ön koridorda girişin sağına mı ("sag") soluna mı ("sol") doğru sıralı."""
    yon, geri = ("sağa", "sola") if siralama == "sag" else ("sola", "sağa")
    noktalar = [{"id": "giris", "ad": "Giriş"}]
    yollar = []
    hedefler = []
    konum: KONUM = {"giris": (0, -6)}
    isaret = 1 if siralama == "sag" else -1

    onceki = "giris"
    for i, k in enumerate(koridorlar, 1):
        nid = f"k{i}"
        noktalar.append({"id": nid, "ad": f"{i}. koridor başı"})
        konum[nid] = (isaret * (i - 1) * ARALIK, 0)
        if i == 1:
            yollar.append({"a": "giris", "b": nid, "adim": giris_adim,
                           "tarif": "Girişten düz ilerleyin, ön koridora ulaşın",
                           "geriTarif": "Girişe doğru düz ilerleyin"})
        else:
            yollar.append({"a": onceki, "b": nid, "adim": koridor_arasi_adim,
                           "tarif": f"Ön koridorda {yon} doğru ilerleyin",
                           "geriTarif": f"Ön koridorda {geri} doğru ilerleyin"})
        for taraf, taraf_adi in (("sol", "solunuzda"), ("sag", "sağınızda")):
            reyonlar = [r.strip() for r in str(k.get(taraf) or "").split(",") if r.strip()]
            for sira, reyon in enumerate(reyonlar):
                yer = _yer(sira, len(reyonlar))
                hedefler.append({
                    "ad": reyon, "nokta": nid, "koridor": str(i),
                    "tarif": f"{i}. koridora girin. {reyon} {(yer + ', ') if yer else ''}{taraf_adi}.",
                    "anahtarlar": _anahtarlar(reyon),
                })
        onceki = nid

    if koridorlar:
        noktalar.append({"id": "kasa", "ad": "Kasalar"})
        konum["kasa"] = (isaret * len(koridorlar) * ARALIK, -6)
        yollar.append({"a": onceki, "b": "kasa", "adim": kasa_adim,
                       "tarif": f"Ön koridorun sonundan {yon} kasalara doğru ilerleyin",
                       "geriTarif": "Kasalardan ön koridora doğru ilerleyin"})
        yollar.append({"a": "kasa", "b": "giris", "adim": max(4, giris_adim // 2),
                       "tarif": "Kasalardan çıkışa doğru ilerleyin", "tekYon": True})
        hedefler.append({"ad": "Kasa", "nokta": "kasa", "tarif": "Kasalar önünüzde.",
                         "anahtarlar": ["kasa", "ödeme", "çıkış"]})

    mekan = {"id": "", "ad": ad, "tur": "magaza", "surum": 1, "giris": "giris",
             **({"kasa": "kasa"} if koridorlar else {}),
             "noktalar": noktalar, "baglantilar": yollar, "hedefler": hedefler}
    raflar = {f"k{i}": {"sol": k.get("sol", ""), "sag": k.get("sag", "")} for i, k in enumerate(koridorlar, 1)}
    return mekan, {"konum": konum, "raflar": raflar, "koridorBoyu": koridor_boyu_adim}


# ── Koridorlu bina (hastane, okul, kamu) ──────────────────

def bina_olustur(ad: str, tur: str, katlar: list[list[dict]], giris_adim: int = 8, dikey: str = "ikisi",
                 basamak: int = 22, kat_adlari: list[int] | None = None) -> tuple[dict, PLAN]:
    """katlar: her kat için koridor boyunca sırayla kapılar:
        [{"ad": "Kardiyoloji", "taraf": "sol"|"sag", "adim": 6, "oda": "112", "kisiler": "Dr. A, Dr. B",
          "anahtarlar": "kalp"}...]
    "adim": bir önceki kapıdan (ilk kapı için koridor başından) bu kapıya adım sayısı.
    dikey: "merdiven", "asansor", "ikisi" (kat sayısı 1 ise yok sayılır).
    kat_adlari: katların numarası (varsayılan 0, 1, 2...)."""
    kat_no = kat_adlari or list(range(len(katlar)))
    kullanilan: set[str] = {"giris"}
    noktalar = [{"id": "giris", "ad": "Ana giriş", **({"kat": kat_no[0]} if kat_no[0] else {})}]
    yollar = []
    hedefler = []
    konum: KONUM = {"giris": (0, -7)}
    cok_katli = len(katlar) > 1
    dikeyler = [] if not cok_katli else (["merdiven", "asansor"] if dikey == "ikisi" else [dikey])
    KAT_ARALIGI = 16   # plan çiziminde katlar arası boşluk
    onceki_dikey: dict[str, str] = {}

    for f, kapilar in enumerate(katlar):
        kat = kat_no[f]
        ust = f * KAT_ARALIGI
        kat_ek = {"kat": kat} if kat else {}
        kat_yazi = "Zemin kat" if kat == 0 else f"{kat}. kat"
        bas = _benzersiz(f"koridor-{f}", kullanilan)
        noktalar.append({"id": bas, "ad": f"{kat_yazi} koridor başı" if cok_katli else "Koridor başı", **kat_ek})
        konum[bas] = (0, ust)
        if f == 0:
            yollar.append({"a": "giris", "b": bas, "adim": giris_adim,
                           "tarif": "Girişten düz ilerleyin, koridorun başına ulaşın",
                           "geriTarif": "Çıkışa doğru düz ilerleyin"})
        for d_i, d in enumerate(dikeyler):
            did = _benzersiz(f"{d}-{f}", kullanilan)
            noktalar.append({"id": did, "ad": "Merdiven başı" if d == "merdiven" else "Asansör önü", **kat_ek})
            konum[did] = (-ARALIK * (d_i + 1), ust)
            taraf = "solunuzdaki" if d_i == 0 else "sağınızdaki"
            yollar.append({"a": bas, "b": did, "adim": 3,
                           "tarif": f"Koridorun başında {taraf} {'merdivene' if d == 'merdiven' else 'asansöre'} yönelin",
                           "geriTarif": f"{'Merdivenden' if d == 'merdiven' else 'Asansörden'} çıkınca koridora doğru ilerleyin"})
            if d in onceki_dikey:
                yollar.append({"a": onceki_dikey[d], "b": did, "adim": 30 if d == "merdiven" else 35, "tur": d,
                               **({"basamak": basamak} if d == "merdiven" else
                                  {"tarif": "Düğmelerde kabartma yazı olabilir; sorabilirsiniz."})})
            onceki_dikey[d] = did

        onceki, sira = bas, 0
        for kapi in kapilar:
            oda_ad = str(kapi.get("ad") or "").strip()
            if not oda_ad:
                continue
            adim = int(kapi.get("adim") or 5)
            sol = str(kapi.get("taraf") or "sol").startswith("sol")
            taraf_adi = "solunuzda" if sol else "sağınızda"
            oda = str(kapi.get("oda") or "").strip()
            kid = _benzersiz(kisalt(oda_ad)[:30] or "oda", kullanilan)
            noktalar.append({"id": kid, "ad": f"{oda_ad} kapısı", **kat_ek})
            sira += 1
            konum[kid] = (sira * ARALIK, ust + (3.5 if sol else -3.5))
            yollar.append({"a": onceki, "b": kid, "adim": adim,
                           "tarif": f"Koridorda düz ilerleyin, {oda_ad} {taraf_adi}",
                           "geriTarif": "Koridorda geri dönün"})
            hedef = {"ad": oda_ad, "nokta": kid,
                     "tarif": f"{oda_ad} kapısı {taraf_adi}{f', oda {oda}' if oda else ''}.",
                     "anahtarlar": _anahtarlar(oda_ad, str(kapi.get("anahtarlar") or ""))}
            if oda:
                hedef["oda"] = oda
            kisiler = [k.strip() for k in str(kapi.get("kisiler") or "").split(",") if k.strip()]
            if kisiler:
                hedef["kisiler"] = kisiler
            hedefler.append(hedef)
            onceki = kid

    mekan = {"id": "", "ad": ad, "tur": tur, "surum": 1, "giris": "giris",
             "noktalar": noktalar, "baglantilar": yollar, "hedefler": hedefler}
    return mekan, {"konum": konum}
