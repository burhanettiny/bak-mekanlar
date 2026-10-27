"""BAK QR Oluşturucu'nun Streamlit'ten bağımsız mantığı.

Bir kurumun bina düzenini (noktalar, yollar, hedefler) doğrular, BAK uygulamasının okuyacağı
giriş QR verisini üretir ve yazdırılabilir etiket sayfası hazırlar.

QR biçimi uygulamadaki src/mekan/qrVeri.ts ile aynı olmalıdır:
    "BAK:VERI:1:" + base45(raw deflate(JSON))
Nokta etiketleri: "BAK:NOKTA:<mekan kimliği>:<nokta kimliği>"
"""

from __future__ import annotations

import base64
import html
import io
import json
import re
import secrets
import unicodedata
import zlib
from collections import deque
from pathlib import Path

import pandas as pd
import qrcode
from qrcode.constants import ERROR_CORRECT_M

VERI_QR_ONEKI = "BAK:VERI:1:"
KURUM_ONEKI = "q-"
BASE45 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"

DIKEY_GECISLER = ("merdiven", "yuruyen-merdiven", "asansor")
BAGLANTI_TURLERI = ("yuru", "rampa", "kapi", *DIKEY_GECISLER)
MEKAN_TURLERI = ("magaza", "hastane", "kurum", "diger")

# Telefon kameraları bu boyuttan büyük QR'ları A4'e basılınca zor okur
ONERILEN_EN_BUYUK_QR_SURUMU = 30

# Girişte yer listesi uygulamada onar onar okunur (src/mekan/hedefListesi.ts SAYFA_BOYU)
SAYFA_BOYU = 10
# Bundan uzun adlar için kısa ad önerilir
UZUN_AD = 22

SABLON_KLASORU = Path(__file__).parent / "sablonlar"


# ── Kimlikler ─────────────────────────────────────────────

_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def kisalt(metin: str) -> str:
    """'Kardiyoloji Polikliniği' → 'kardiyoloji-poliklinigi'"""
    sade = unicodedata.normalize("NFKD", metin.translate(_TR)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sade.lower()).strip("-")


def kimlik_uret(ad: str) -> str:
    """Kurum kimliği: aynı adlı iki kurum (ör. iki 'Atatürk İlkokulu') karışmasın diye rastgele ek alır."""
    govde = kisalt(ad)[:40].strip("-") or "kurum"
    return f"{KURUM_ONEKI}{govde}-{secrets.token_hex(2)}"


# ── base45 ve QR verisi ───────────────────────────────────

def base45(veri: bytes) -> str:
    """RFC 9285 base45: QR'ın harf-rakam kipine sığar."""
    sonuc = []
    for i in range(0, len(veri), 2):
        parca = veri[i:i + 2]
        if len(parca) == 2:
            n = parca[0] * 256 + parca[1]
            n, c = divmod(n, 45)
            e, d = divmod(n, 45)
            sonuc.append(BASE45[c] + BASE45[d] + BASE45[e])
        else:
            d, c = divmod(parca[0], 45)
            sonuc.append(BASE45[c] + BASE45[d])
    return "".join(sonuc)


def base45_coz(metin: str) -> bytes:
    sonuc = bytearray()
    for i in range(0, len(metin), 3):
        degerler = [BASE45.index(h) for h in metin[i:i + 3]]
        if len(degerler) == 3:
            n = degerler[0] + degerler[1] * 45 + degerler[2] * 45 * 45
            sonuc += bytes(divmod(n, 256))
        else:
            sonuc.append(degerler[0] + degerler[1] * 45)
    return bytes(sonuc)


def sade_json(mekan: dict) -> str:
    return json.dumps(mekan, ensure_ascii=False, separators=(",", ":"))


def qr_verisi(mekan: dict) -> str:
    # 2D plan bilgisi uygulamanın işine yaramaz, QR'ı büyütür: dışarıda bırakılır
    mekan = {k: v for k, v in mekan.items() if k != "plan"}
    sikistirici = zlib.compressobj(9, zlib.DEFLATED, -15)
    sikisik = sikistirici.compress(sade_json(mekan).encode("utf-8")) + sikistirici.flush()
    return VERI_QR_ONEKI + base45(sikisik)


def qr_verisini_coz(metin: str) -> dict:
    if not metin.startswith(VERI_QR_ONEKI):
        raise ValueError("BAK giriş QR verisi değil")
    return json.loads(zlib.decompress(base45_coz(metin[len(VERI_QR_ONEKI):]), -15).decode("utf-8"))


def nokta_qr_verisi(mekan_id: str, nokta_id: str) -> str:
    return f"BAK:NOKTA:{mekan_id}:{nokta_id}"


def qr_olustur(metin: str) -> qrcode.QRCode:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=8, border=4)
    qr.add_data(metin, optimize=0)
    qr.make(fit=True)
    return qr


def qr_png(metin: str, kutu: int = 8) -> bytes:
    qr = qr_olustur(metin)
    qr.box_size = kutu
    tampon = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(tampon, format="PNG")
    return tampon.getvalue()


# ── Doğrulama ─────────────────────────────────────────────
# Uygulamadaki yerlesimDogrula ile aynı kurallar, kurumun anlayacağı Türkçe hata mesajlarıyla.
# Uygulama hatalı bir düzeni hiç yüklemez; bu yüzden hata varsa QR üretilmez.

def dogrula(mekan: dict) -> tuple[list[str], list[str]]:
    """(hatalar, uyarılar) döndürür. Hata varsa QR üretilmemeli."""
    hatalar: list[str] = []
    uyarilar: list[str] = []

    if not str(mekan.get("ad", "")).strip():
        hatalar.append("Kurumun adını yazın.")
    kimlik = str(mekan.get("id", ""))
    if not re.fullmatch(r"q-[a-z0-9-]+", kimlik):
        hatalar.append("Kurum kimliği 'q-' ile başlamalı ve yalnızca küçük harf, rakam ve '-' içermeli.")
    if mekan.get("tur") not in MEKAN_TURLERI:
        hatalar.append("Kurum türünü seçin.")

    noktalar = mekan.get("noktalar") or []
    baglantilar = mekan.get("baglantilar") or []
    hedefler = mekan.get("hedefler") or []
    idler = [n.get("id") for n in noktalar]
    idler_kume = set(idler)

    if not noktalar:
        hatalar.append("En az bir nokta ekleyin (örneğin giriş).")
    for n in noktalar:
        if not n.get("id") or not re.fullmatch(r"[a-z0-9-]+", str(n["id"])):
            hatalar.append(f"'{n.get('ad', '?')}' noktasının kimliği geçersiz.")
        if not str(n.get("ad", "")).strip():
            hatalar.append(f"'{n.get('id', '?')}' noktasına bir ad verin.")
    tekrarlar = sorted({i for i in idler if idler.count(i) > 1})
    if tekrarlar:
        hatalar.append("Aynı kimlikle birden fazla nokta var: " + ", ".join(tekrarlar))

    if mekan.get("giris") not in idler_kume:
        hatalar.append("Giriş noktasını seçin. Giriş QR'ı bu noktaya asılır.")
    if mekan.get("kasa") not in (None, "") and mekan.get("kasa") not in idler_kume:
        hatalar.append("Kasa olarak seçilen nokta listede yok.")

    for i, b in enumerate(baglantilar, 1):
        tur = b.get("tur") or "yuru"
        etiket = f"{i}. yol ({b.get('a', '?')} → {b.get('b', '?')})"
        if tur not in BAGLANTI_TURLERI:
            hatalar.append(f"{etiket}: yol türü geçersiz.")
        if b.get("a") not in idler_kume or b.get("b") not in idler_kume:
            hatalar.append(f"{etiket}: başlangıç ve bitiş noktası listede olmalı.")
        elif b.get("a") == b.get("b"):
            hatalar.append(f"{etiket}: başlangıç ve bitiş aynı nokta.")
        adim = b.get("adim")
        if not isinstance(adim, (int, float)) or adim <= 0:
            hatalar.append(f"{etiket}: adım sayısı 0'dan büyük olmalı.")
        if tur not in DIKEY_GECISLER:
            if not str(b.get("tarif") or "").strip():
                hatalar.append(f"{etiket}: gidiş tarifini yazın (ör. 'Danışmanın solundaki koridora girin').")
            if not b.get("tekYon") and not str(b.get("geriTarif") or "").strip():
                hatalar.append(f"{etiket}: dönüş tarifini yazın ya da yolu tek yönlü işaretleyin.")
        elif tur == "merdiven" and not b.get("basamak"):
            uyarilar.append(f"{etiket}: merdivenin basamak sayısını yazarsanız kullanıcıya söylenir.")
        if tur in DIKEY_GECISLER and b.get("a") in idler_kume and b.get("b") in idler_kume:
            katlar = {n["id"]: n.get("kat", 0) or 0 for n in noktalar}
            if katlar[b["a"]] == katlar[b["b"]]:
                uyarilar.append(f"{etiket}: merdiven/asansörün iki ucu aynı katta görünüyor; noktaların katını kontrol edin.")

    if not hedefler:
        hatalar.append("En az bir hedef ekleyin (danışma, tuvalet, bir oda…).")
    for h in hedefler:
        ad = str(h.get("ad", "")).strip()
        if not ad:
            hatalar.append("Adı boş bir hedef var.")
        if h.get("nokta") not in idler_kume:
            hatalar.append(f"'{ad or '?'}' hedefinin noktası listede yok.")
        if not isinstance(h.get("anahtarlar"), list):
            hatalar.append(f"'{ad or '?'}' hedefinin anahtar kelimeleri liste olmalı.")
        elif not h["anahtarlar"]:
            uyarilar.append(f"'{ad}' için anahtar kelime yok; kullanıcı yalnızca tam adını söyleyerek bulabilir.")
        if not str(h.get("tarif", "")).strip():
            uyarilar.append(f"'{ad}' için varınca söylenecek tarif boş (ör. 'Kapı solunuzda, oda 112').")
        if len(ad) > UZUN_AD and not str(h.get("kisaAd", "")).strip():
            uyarilar.append(f"'{ad}' adı uzun; girişteki listede böyle okunur. Kısa ad yazın "
                            "(ör. 'Kardiyoloji Polikliniği' → 'Kardiyoloji').")

    kisa_adlar: dict[str, set[str]] = {}
    for h in hedefler:
        if str(h.get("kisaAd", "")).strip():
            kisa_adlar.setdefault(kisalt(h["kisaAd"]), set()).add(str(h.get("ad", "")))
    for kisa, adlar in kisa_adlar.items():
        if len(adlar) > 1:
            uyarilar.append(f"Farklı yerler aynı kısa adı taşıyor ({', '.join(sorted(adlar))}); listede bir kez okunur.")

    if not hatalar:
        ulasilamayan = ulasilamayan_hedefler(mekan)
        if ulasilamayan:
            hatalar.append("Girişten yol olmayan hedefler var: " + ", ".join(ulasilamayan) +
                           ". Bu noktalara giden yolları ekleyin.")
        sahipsiz = [n["ad"] for n in noktalar if n["id"] != mekan["giris"]
                    and not any(n["id"] in (b.get("a"), b.get("b")) for b in baglantilar)]
        if sahipsiz:
            uyarilar.append("Hiçbir yola bağlı olmayan noktalar: " + ", ".join(sahipsiz))

    return hatalar, uyarilar


def ulasilamayan_hedefler(mekan: dict) -> list[str]:
    komsular: dict[str, set[str]] = {n["id"]: set() for n in mekan["noktalar"]}
    for b in mekan["baglantilar"]:
        komsular[b["a"]].add(b["b"])
        if not b.get("tekYon"):
            komsular[b["b"]].add(b["a"])
    gorulen = {mekan["giris"]}
    kuyruk = deque([mekan["giris"]])
    while kuyruk:
        for k in komsular[kuyruk.popleft()] - gorulen:
            gorulen.add(k)
            kuyruk.append(k)
    return [h["ad"] for h in mekan["hedefler"] if h["nokta"] not in gorulen]


def rota_onizleme(mekan: dict, hedef_ad: str) -> list[str]:
    """Girişten hedefe en kısa yolun, uygulamanın okuyacağına yakın kaba bir önizlemesi."""
    import heapq

    hedef = next(h for h in mekan["hedefler"] if h["ad"] == hedef_ad)
    kenarlar: dict[str, list[tuple[str, dict, bool]]] = {n["id"]: [] for n in mekan["noktalar"]}
    for b in mekan["baglantilar"]:
        kenarlar[b["a"]].append((b["b"], b, False))
        if not b.get("tekYon"):
            kenarlar[b["b"]].append((b["a"], b, True))
    adlar = {n["id"]: n["ad"] for n in mekan["noktalar"]}
    uzaklik = {mekan["giris"]: 0}
    onceki: dict[str, tuple[str, dict, bool]] = {}
    kuyruk = [(0, mekan["giris"])]
    while kuyruk:
        u, nokta = heapq.heappop(kuyruk)
        if u > uzaklik.get(nokta, float("inf")):
            continue
        for komsu, b, ters in kenarlar[nokta]:
            yeni = u + b["adim"]
            if yeni < uzaklik.get(komsu, float("inf")):
                uzaklik[komsu] = yeni
                onceki[komsu] = (nokta, b, ters)
                heapq.heappush(kuyruk, (yeni, komsu))
    if hedef["nokta"] not in uzaklik:
        return ["Girişten bu hedefe yol yok."]
    adimlar = []
    nokta = hedef["nokta"]
    while nokta in onceki:
        kaynak, b, ters = onceki[nokta]
        tur = b.get("tur", "yuru")
        tarif = (b.get("geriTarif") if ters else b.get("tarif")) or ""
        if tur in DIKEY_GECISLER:
            adimlar.append(f"{tur.replace('-', ' ').capitalize()} ile {adlar[nokta]} noktasına. {tarif}".strip())
        else:
            adimlar.append(f"{tarif}, yaklaşık {b['adim']} adım → {adlar[nokta]}")
        nokta = kaynak
    return [f"Giriş: {adlar[mekan['giris']]}", *reversed(adimlar), f"Varınca: {hedef['tarif']}"]


# ── Girişte okunacak yer listesi ──────────────────────────
# Uygulamadaki hedefListesi.ts ile aynı kurallar: aynı adlı yerler bir kez, katlara göre, onar onar.

def liste_adi(h: dict) -> str:
    return str(h.get("kisaAd") or "").strip() or h["ad"]


def kat_adi(kat: int) -> str:
    if kat == 0:
        return "zemin kat"
    if kat == -1:
        return "bodrum kat"
    return f"{kat}. kat" if kat > 0 else f"eksi {-kat}. kat"


def liste_sayfalari(mekan: dict) -> list[str]:
    katlar_sozlugu = {n["id"]: n.get("kat", 0) or 0 for n in mekan["noktalar"]}
    gorulen: set[str] = set()
    secenekler = []
    for i, h in enumerate(mekan["hedefler"]):
        anahtar = kisalt(liste_adi(h))
        if anahtar not in gorulen:
            gorulen.add(anahtar)
            secenekler.append((katlar_sozlugu.get(h["nokta"], 0), i, h))
    secenekler.sort(key=lambda x: (x[0], x[1]))
    tum_katlar = {k for k, _, _ in secenekler}
    sayfalar = []
    for bas in range(0, len(secenekler), SAYFA_BOYU):
        sayfa = secenekler[bas:bas + SAYFA_BOYU]
        numarali = [(k, f"{bas + j + 1}, {liste_adi(h)}") for j, (k, _, h) in enumerate(sayfa)]
        if len(tum_katlar) > 1:
            parcalar = []
            for kat in dict.fromkeys(k for k, _ in numarali):
                ad = kat_adi(kat)
                parcalar.append(f"{ad[0].upper() + ad[1:]}: " + "; ".join(m for k, m in numarali if k == kat) + ".")
            liste = " ".join(parcalar)
        else:
            liste = "; ".join(m for _, m in numarali) + "."
        kalan = len(secenekler) - bas - SAYFA_BOYU
        giris = (f"Burada {len(secenekler)} yer var." + (f" İlk {SAYFA_BOYU} tanesi:" if kalan > 0 else "")
                 if bas == 0 else f"{bas + 1}. yerden devam:")
        kisi_var = bas == 0 and any(h.get("kisiler") for h in mekan["hedefler"])
        sayfalar.append(f"{giris} {liste}" + (f" Diğer {kalan} yer için devam deyin." if kalan > 0 else "") +
                        (" Çalışanların adıyla da sorabilirsiniz, örneğin doktorun adını söyleyin." if kisi_var else ""))
    return sayfalar


def okuma_suresi(metin: str) -> int:
    """Telefonun normal hızda okuma süresi, saniye (uygulamadaki tahminiOkumaSuresi)."""
    return max(1, round(len(metin) * 0.07))


# Birden çok yerin adında tekrarlanan genel sözcükler kısa addan atılır:
# "Kardiyoloji Polikliniği", "Dahiliye Polikliniği" → "Kardiyoloji", "Dahiliye"
def kisa_ad_onerileri(hedefler: list[dict]) -> dict[int, str]:
    """Satır sırası → önerilen kısa ad (yalnızca kısa adı boş ve önerisi olan satırlar)."""
    kelimeler = [str(h.get("ad") or "").split() for h in hedefler]
    son_sayilari: dict[str, int] = {}
    for k in kelimeler:
        if len(k) >= 2:
            son_sayilari[kisalt(k[-1])] = son_sayilari.get(kisalt(k[-1]), 0) + 1
    oneriler = {}
    for i, (h, k) in enumerate(zip(hedefler, kelimeler)):
        if str(h.get("kisaAd") or "").strip() or len(k) < 2 or son_sayilari.get(kisalt(k[-1]), 0) < 2:
            continue
        oneri = " ".join(k[:-1])
        # "101 numaralı sınıf" gibi numara taşıyan adlar kısaltılmaz: listede "1, 101 numaralı" karışır
        if not re.search(r"\d", oneri):
            oneriler[i] = oneri
    return oneriler


# ── Tablolar ↔ düzen dosyası ──────────────────────────────

def _metin(deger) -> str:
    if deger is None:
        return ""
    if isinstance(deger, float) and deger != deger:  # NaN (boş hücre)
        return ""
    return str(deger).strip()


def _liste(deger) -> list[str]:
    return [p.strip() for p in _metin(deger).split(",") if p.strip()]


def satirlardan_mekan(bilgi: dict, noktalar: list[dict], yollar: list[dict], hedefler: list[dict]) -> dict:
    """Tablo satırlarını uygulamanın okuduğu düzen biçimine çevirir; boş alanlar yazılmaz."""
    nokta_listesi = []
    for n in noktalar:
        ad = _metin(n.get("ad"))
        if not ad and not _metin(n.get("id")):
            continue
        nokta = {"id": _metin(n.get("id")) or kisalt(ad), "ad": ad}
        kat = n.get("kat")
        if kat not in (None, "") and kat == kat and int(kat) != 0:
            nokta["kat"] = int(kat)
        nokta_listesi.append(nokta)

    yol_listesi = []
    for y in yollar:
        if not _metin(y.get("a")) and not _metin(y.get("b")):
            continue
        yol = {"a": _metin(y.get("a")), "b": _metin(y.get("b"))}
        adim = y.get("adim")
        yol["adim"] = int(adim) if adim not in (None, "") and adim == adim else 0
        tur = _metin(y.get("tur")) or "yuru"
        if tur != "yuru":
            yol["tur"] = tur
        for alan in ("tarif", "geriTarif"):
            if _metin(y.get(alan)):
                yol[alan] = _metin(y.get(alan))
        if y.get("tekYon") is True:
            yol["tekYon"] = True
        basamak = y.get("basamak")
        if basamak not in (None, "") and basamak == basamak and int(basamak) > 0:
            yol["basamak"] = int(basamak)
        yol_listesi.append(yol)

    hedef_listesi = []
    for h in hedefler:
        ad = _metin(h.get("ad"))
        if not ad and not _metin(h.get("nokta")):
            continue
        hedef = {"ad": ad, "nokta": _metin(h.get("nokta")), "tarif": _metin(h.get("tarif")),
                 "anahtarlar": _liste(h.get("anahtarlar"))}
        for alan in ("kisaAd", "oda", "no", "koridor", "raf"):
            if _metin(h.get(alan)):
                hedef[alan] = _metin(h.get(alan))
        if _liste(h.get("kisiler")):
            hedef["kisiler"] = _liste(h.get("kisiler"))
        hedef_listesi.append(hedef)

    mekan = {"id": bilgi["id"], "ad": _metin(bilgi.get("ad")), "tur": bilgi.get("tur"),
             "surum": int(bilgi.get("surum") or 1), "giris": _metin(bilgi.get("giris"))}
    if _metin(bilgi.get("kasa")):
        mekan["kasa"] = _metin(bilgi["kasa"])
    mekan.update(noktalar=nokta_listesi, baglantilar=yol_listesi, hedefler=hedef_listesi)
    return mekan


def mekandan_satirlar(mekan: dict) -> tuple[list[dict], list[dict], list[dict]]:
    noktalar = [{"id": n["id"], "ad": n["ad"], "kat": n.get("kat", 0)} for n in mekan["noktalar"]]
    yollar = [{"a": b["a"], "b": b["b"], "tur": b.get("tur", "yuru"), "adim": b["adim"],
               "tarif": b.get("tarif", ""), "geriTarif": b.get("geriTarif", ""),
               "tekYon": bool(b.get("tekYon")), "basamak": b.get("basamak")}
              for b in mekan["baglantilar"]]
    hedefler = [{"ad": h["ad"], "kisaAd": h.get("kisaAd", ""), "nokta": h["nokta"], "tarif": h.get("tarif", ""),
                 "anahtarlar": ", ".join(h.get("anahtarlar", [])), "kisiler": ", ".join(h.get("kisiler", [])),
                 "oda": h.get("oda", ""), "no": h.get("no", "")}
                for h in mekan["hedefler"]]
    return noktalar, yollar, hedefler


# ── Tablo düzenleyici ─────────────────────────────────────

NOKTA_SUTUNLARI = ["ad", "kat", "id"]
YOL_SUTUNLARI = ["a", "b", "tur", "adim", "tarif", "geriTarif", "tekYon", "basamak"]
HEDEF_SUTUNLARI = ["ad", "kisaAd", "nokta", "tarif", "anahtarlar", "kisiler", "oda", "no"]
SAYI_SUTUNLARI = {"kat", "adim", "basamak"}
MANTIKSAL_SUTUNLAR = {"tekYon"}
# Tablo yapısı değişince artırılır: önceki sürümden kalan tablo düzenlemeleri yeni sütunlara uygulanmasın
TABLO_SEMASI = 2


def tablo(veri, sutunlar: list[str]) -> pd.DataFrame:
    """Her sütunu tek türe zorlar. Karışık türlü sütun (ör. oda numarası bir satırda 112, diğerinde "B-3")
    tablo düzenleyicide hata verir; yazı sütunları yazıya, sayı sütunları sayıya çevrilir."""
    df = pd.DataFrame(veri, columns=sutunlar)
    for s in sutunlar:
        if s in SAYI_SUTUNLARI:
            df[s] = pd.to_numeric(df[s], errors="coerce").astype("float64")
        elif s in MANTIKSAL_SUTUNLAR:
            df[s] = df[s].fillna(False).astype(bool)
        else:
            df[s] = df[s].map(_metin).astype(object)
    return df.reset_index(drop=True)


# ── Şablonlar ─────────────────────────────────────────────

def sablonlar() -> dict[str, dict]:
    """Şablon adı → düzen. Dosya adındaki sıra numarası listede sırayı belirler."""
    sonuc = {}
    for dosya in sorted(SABLON_KLASORU.glob("*.json")):
        veri = json.loads(dosya.read_text(encoding="utf-8"))
        sonuc[veri.pop("sablonAdi")] = veri
    return sonuc


# ── Yazdırılabilir etiketler ──────────────────────────────

def _png_veri_adresi(metin: str) -> str:
    return "data:image/png;base64," + base64.b64encode(qr_png(metin, kutu=10)).decode()


def etiket_sayfasi(mekan: dict) -> str:
    """A4'e yazdırılacak HTML: önce büyük giriş etiketi, sonra her nokta için küçük etiket."""
    ad = html.escape(mekan["ad"])
    giris = _png_veri_adresi(qr_verisi(mekan))
    noktalar = "".join(
        f"""<div class="etiket"><img src="{_png_veri_adresi(nokta_qr_verisi(mekan['id'], n['id']))}" alt="">
        <b>{html.escape(n['ad'])}</b><small>BAK · {ad}</small></div>"""
        for n in mekan["noktalar"] if n["id"] != mekan["giris"])
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<title>BAK etiketleri – {ad}</title>
<style>
  @page {{ size: A4; margin: 12mm; }}
  body {{ font-family: Arial, sans-serif; color: #000; margin: 0; }}
  .giris {{ border: 6px solid #0d47a1; border-radius: 12px; padding: 10mm; text-align: center;
           page-break-after: always; }}
  .giris img {{ width: 150mm; height: 150mm; image-rendering: pixelated; }}
  .giris h1 {{ font-size: 30pt; margin: 0 0 4mm; }}
  .giris p {{ font-size: 16pt; margin: 2mm 0; }}
  .izgara {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 6mm; }}
  .etiket {{ border: 2px solid #000; border-radius: 8px; padding: 4mm; text-align: center;
            break-inside: avoid; display: flex; flex-direction: column; align-items: center; gap: 2mm; }}
  .etiket img {{ width: 50mm; height: 50mm; image-rendering: pixelated; }}
  .etiket b {{ font-size: 13pt; }}
  .etiket small {{ font-size: 9pt; color: #333; }}
  .not {{ font-size: 11pt; margin-bottom: 6mm; }}
</style></head><body>
<section class="giris">
  <h1>BAK · {ad}</h1>
  <img src="{giris}" alt="BAK giriş QR kodu">
  <p><b>Görme engelli ziyaretçilerimiz için sesli yönlendirme</b></p>
  <p>BAK uygulamasını açıp bu kodu telefonun kamerasıyla okutun.</p>
</section>
<p class="not">Her etiketi üzerinde yazan noktaya, yerden yaklaşık 120 cm yüksekliğe ve her zaman aynı tarafa
(ör. kapının sağına) yapıştırın. Altına kabartma bir işaret koymak, etiketin elle bulunmasını kolaylaştırır.</p>
<div class="izgara">{noktalar}</div>
</body></html>"""
