"""Tablo doldurmadan bina düzeni üreten sihirbazlar.

Kurum binasını tarif eder (koridor sayısı, hangi tarafta ne var), sihirbaz BAK uygulamasının okuduğu
noktaları, yolları ve hedefleri üretir. Ayrıca 2D plan için her noktanın konumunu (adım birimiyle) verir.

Yön kuralı: kullanıcı girişten içeri bakarken "sağ" ve "sol". Koridorda ilerlerken soldaki kapı "solunuzda".
"""

from __future__ import annotations

import re

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

# Katlar arası geçiş seçenekleri. AVM'lerde çoğunlukla yürüyen merdiven ve asansör olur.
DIKEY_SECENEKLERI = {"ikisi": ["merdiven", "asansor"], "merdiven": ["merdiven"], "asansor": ["asansor"],
                     "yuruyen": ["yuruyen-merdiven", "asansor"]}
DIKEY_ADLARI = {"merdiven": ("Merdiven başı", "merdivene", "Merdivenden"),
                "asansor": ("Asansör önü", "asansöre", "Asansörden"),
                "yuruyen-merdiven": ("Yürüyen merdiven başı", "yürüyen merdivene", "Yürüyen merdivenden")}


# ── Hastane sitelerindeki kat listesini okuma ─────────────
# Birçok hastane "Kat Planı" sayfasında hangi birimin hangi katta olduğunu yazıyor. Kurum bu metni yapıştırır;
# katlar ve birimler sihirbaza dolar. Sağ/sol ve adım sayısı bu sayfalarda yoktur, sahada girilmelidir.

_KAT_BASLIGI = re.compile(
    r"^\s*(?:[-–•*·]\s+)?(?P<kat>zemin|giriş|giris|bodrum|(?:eksi\s*)?[-–]?\s*\d+\s*\.?\s*(?:bodrum)?)\s*kat[ıi]?\b"
    r"\s*[:\-–.]?\s*(?P<kalan>.*)$", re.IGNORECASE)
_BLOK_BASLIGI = re.compile(r"^\s*[A-ZÇĞİÖŞÜ0-9]{1,3}\s*[- ]?\s*blok\w*\s*:?\s*$", re.IGNORECASE)
_MADDE_ISARETI = re.compile(r"^\s*(?:[-–•*·▪►]|\d+[.)])\s*")


def _kat_numarasi(metin: str) -> int:
    m = metin.lower().replace("–", "-").replace(" ", "")
    if m in ("zemin", "giriş", "giris"):
        return 0
    if m == "bodrum":
        return -1
    sayi = int(re.search(r"\d+", m).group())
    return -sayi if m.startswith("-") or m.startswith("eksi") or "bodrum" in m else sayi


def kat_listesi_coz(metin: str) -> dict[int, list[str]]:
    """"Zemin Kat: Danışma, Vezne" ya da başlık altında alt alta maddeler → {0: ["Danışma", "Vezne"], ...}.
    Blok başlıkları ("A BLOK") atlanır; aynı katta tekrar eden birim bir kez alınır."""
    katlar: dict[int, list[str]] = {}
    gecerli: int | None = None

    def ekle(parca: str) -> None:
        for ad in re.split(r"[,;]| - ", parca):
            ad = _MADDE_ISARETI.sub("", ad).strip(" .:\t")
            if gecerli is not None and len(ad) >= 2 and ad not in katlar[gecerli] and ad != "-":
                katlar[gecerli].append(ad)

    for satir in metin.splitlines():
        if not satir.strip() or _BLOK_BASLIGI.match(satir):
            continue
        baslik = _KAT_BASLIGI.match(satir)
        if baslik:
            gecerli = _kat_numarasi(baslik.group("kat"))
            katlar.setdefault(gecerli, [])
            ekle(baslik.group("kalan"))
        else:
            ekle(satir)
    return {k: v for k, v in sorted(katlar.items())}


def kat_adi(kat: int) -> str:
    if kat == 0:
        return "Zemin kat"
    return "Bodrum kat" if kat == -1 else (f"Eksi {-kat}. kat" if kat < 0 else f"{kat}. kat")


def bina_olustur(ad: str, tur: str, katlar: list[list[dict]], giris_adim: int = 8, dikey: str = "ikisi",
                 basamak: int = 22, ilk_kat: int = 0) -> tuple[dict, PLAN]:
    """katlar: her kat için koridor boyunca sırayla kapılar:
        [{"ad": "Kardiyoloji", "taraf": "sol"|"sag", "adim": 6, "oda": "112", "kisiler": "Dr. A, Dr. B",
          "anahtarlar": "kalp"}...]
    "adim": bir önceki kapıdan (ilk kapı için koridor başından) bu kapıya adım sayısı.
    dikey: DIKEY_SECENEKLERI anahtarlarından biri (kat sayısı 1 ise yok sayılır).
    ilk_kat: listedeki ilk katın numarası; bodrumlu binada -1 ya da -2. Giriş zemin kata (yoksa ilk kata) bağlanır."""
    kat_no = [ilk_kat + i for i in range(len(katlar))]
    giris_kati = kat_no.index(0) if 0 in kat_no else 0
    kullanilan: set[str] = {"giris"}
    noktalar = [{"id": "giris", "ad": "Ana giriş", **({"kat": kat_no[giris_kati]} if kat_no[giris_kati] else {})}]
    yollar = []
    hedefler = []
    cok_katli = len(katlar) > 1
    dikeyler = DIKEY_SECENEKLERI.get(dikey, ["merdiven"]) if cok_katli else []
    KAT_ARALIGI = 11   # plan çiziminde katlar arası boşluk
    konum: KONUM = {"giris": (0, giris_kati * KAT_ARALIGI - 7)}
    onceki_dikey: dict[str, str] = {}

    for f, kapilar in enumerate(katlar):
        kat = kat_no[f]
        ust = f * KAT_ARALIGI
        kat_ek = {"kat": kat} if kat else {}
        kat_yazi = kat_adi(kat)
        bas = _benzersiz(f"koridor-{f}", kullanilan)
        noktalar.append({"id": bas, "ad": f"{kat_yazi} koridor başı" if cok_katli else "Koridor başı", **kat_ek})
        konum[bas] = (0, ust)
        if f == giris_kati:
            yollar.append({"a": "giris", "b": bas, "adim": giris_adim,
                           "tarif": "Girişten düz ilerleyin, koridorun başına ulaşın",
                           "geriTarif": "Çıkışa doğru düz ilerleyin"})
        for d_i, d in enumerate(dikeyler):
            did = _benzersiz(f"{d}-{f}", kullanilan)
            nokta_adi, yonelme, cikis = DIKEY_ADLARI[d]
            noktalar.append({"id": did, "ad": nokta_adi, **kat_ek})
            konum[did] = (-ARALIK * (d_i + 1), ust)
            taraf = "solunuzdaki" if d_i == 0 else "sağınızdaki"
            yollar.append({"a": bas, "b": did, "adim": 3,
                           "tarif": f"Koridorun başında {taraf} {yonelme} yönelin",
                           "geriTarif": f"{cikis} çıkınca koridora doğru ilerleyin"})
            if d in onceki_dikey:
                not_ = {"asansor": "Düğmelerde kabartma yazı olabilir; sorabilirsiniz.",
                        "yuruyen-merdiven": "Binmeden önce yan tutamağı bulun; inişte bant bitince "
                                            "adımınızı uzatın."}.get(d)
                # Not iki yönde de okunsun: inerken de gerekli
                ek = {"basamak": basamak} if d == "merdiven" else {"tarif": not_, "geriTarif": not_}
                yollar.append({"a": onceki_dikey[d], "b": did, "adim": {"merdiven": 30, "asansor": 35, "yuruyen-merdiven": 25}[d], "tur": d, **ek})
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
