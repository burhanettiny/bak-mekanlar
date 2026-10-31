"""OpenStreetMap'ten kampüs: kurum adı yazılır, alanı bulunur; adlı binalar ve yürünebilir yollar çekilir, girişten
her binaya giden yolların birleşimi BAK noktaları ve yollarına çevrilir. Sonuç çizim sayfasında haritanın üstünde
açılır; kurum noktaları sürükleyerek, ad ve tarifleri değiştirerek düzeltir. Mesafeler yol boyunca ölçülür.

Ağ işlemleri (ara, veri_cek) ile kurulum (kampus_kur) ayrıdır: kurulum kaydedilmiş Overpass verisiyle sınanır.
Harita verisi © OpenStreetMap katkıcıları (ODbL).
"""
from __future__ import annotations

import heapq
import json
import math
import re
import unicodedata
import urllib.parse
import urllib.request

import bak_mekan as bm
import cizim as cz

BIRIM_M = 8.0                     # çizimde bir birim kaç metre (kampüs ölçeğinde okunaklı)
EN_FAZLA_BINA = 20                # QR ve liste uzamasın: en büyük binalar
_YOL_DISI = {"motorway", "motorway_link", "trunk", "trunk_link", "track", "construction", "proposed", "raceway",
             "bus_guideway", "escape", "bridleway", "corridor", "elevator", "platform"}
_ONEM = {"primary": 6, "secondary": 5, "tertiary": 4, "unclassified": 3, "residential": 3, "service": 2,
         "living_street": 2, "pedestrian": 2, "footway": 1, "path": 1, "steps": 0, "cycleway": 1}
_AJAN = "BAK-QR-olusturucu/1.0 (https://bakmekan.streamlit.app; mailtoburhanettin@gmail.com)"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"]
_TR = str.maketrans("çğıöşüÇĞİÖŞÜâÂîÎûÛ", "cgiosuCGIOSUaAiIuU")


# Ziyaretçinin gideceği yer olmayan yapılar
_ATLA = re.compile(r"lojman|güvenlik kulübe|bekçi|trafo|jeneratör|kazan dairesi|pompa|depo\b|garaj|kulübe", re.I)
# Kısa ad ve kimlikte atılan genel sözcükler
_GENEL = {"fakultesi", "binasi", "mudurlugu", "yuksekokulu", "enstitusu", "baskanligi", "blok", "bina", "binalari"}


def kisalt(metin: str, uzunluk: int = 20) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", metin.translate(_TR)).encode("ascii", "ignore")
               .decode().lower()).strip("-")
    if len(s) > uzunluk:   # sözcük ortasında kesilmesin
        s = s[:uzunluk + 1].rsplit("-", 1)[0] if "-" in s[:uzunluk + 1] else s[:uzunluk]
    return s or "bina"


def kisa_ad(ad: str, kurum: str) -> str:
    """"Ardahan Üniversitesi Mühendislik Fakültesi" → "Mühendislik": kurumun adı ve genel sözcükler atılır."""
    sozler = ad.split()
    kurum_sozleri = kurum.split()
    while sozler and kurum_sozleri and sozler[0].casefold() == kurum_sozleri[0].casefold():
        sozler, kurum_sozleri = sozler[1:], kurum_sozleri[1:]
    while len(sozler) > 1 and kisalt(sozler[-1]) in _GENEL:
        sozler = sozler[:-1]
    return " ".join(sozler) or ad


# ── Ağ ────────────────────────────────────────────────────
def _getir(url: str, veri: bytes | None = None, zaman: int = 25):
    istek = urllib.request.Request(url, data=veri, headers={"User-Agent": _AJAN, "Accept-Language": "tr"})
    with urllib.request.urlopen(istek, timeout=zaman) as yanit:
        return json.loads(yanit.read().decode("utf-8"))


def ara(sorgu: str) -> list[dict]:
    """Kurum adı → OSM'de alan olan (yol ya da ilişki) adaylar: [{ad, aciklama, tur, kimlik}]."""
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": sorgu, "format": "jsonv2", "limit": 8, "accept-language": "tr"})
    sonuc = []
    for s in _getir(url):
        if s.get("osm_type") not in ("way", "relation"):
            continue
        ad = s.get("name") or s["display_name"].split(",")[0]
        sonuc.append({"ad": ad, "aciklama": s["display_name"], "tur": s["osm_type"], "kimlik": int(s["osm_id"])})
    return sonuc


def veri_cek(tur: str, kimlik: int) -> list[dict]:
    """Alanın sınırı, içindeki yollar, adlı binalar ve sınırdaki kapılar (Overpass, "out geom")."""
    secici = "rel" if tur == "relation" else "way"
    alan_kimligi = (3600000000 if tur == "relation" else 2400000000) + kimlik
    sorgu = f"""[out:json][timeout:90];
{secici}({kimlik})->.sinir;
.sinir out geom;
area({alan_kimligi})->.alan;
(
  way["highway"](area.alan);
  way["building"]["name"](area.alan);
  relation["building"]["name"](area.alan);
  node["barrier"~"^(gate|lift_gate|entrance)$"](around.sinir:40);
);
out geom;"""
    hata = None
    for adres in OVERPASS:
        try:
            return _getir(adres, urllib.parse.urlencode({"data": sorgu}).encode(), zaman=90)["elements"]
        except Exception as e:   # bir ayna meşgulse sıradakine geçilir
            hata = e
    raise RuntimeError(f"OpenStreetMap verisi alınamadı: {hata}")


# ── Kurulum ───────────────────────────────────────────────
def _geometri(e: dict) -> list[dict]:
    return e.get("geometry") or [p for m in e.get("members", []) if m.get("role") != "inner"
                                 for p in (m.get("geometry") or [])]


def _icinde(p: tuple[float, float], cokgen: list[tuple[float, float]]) -> bool:
    x, y = p
    ic = False
    for (x1, y1), (x2, y2) in zip(cokgen, cokgen[1:] + cokgen[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 or 1e-12) + x1:
            ic = not ic
    return ic


def _alan_m2(cokgen: list[tuple[float, float]]) -> float:
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(cokgen, cokgen[1:] + cokgen[:1]))) / 2


def kampus_kur(elemanlar: list[dict], sinir_kimligi: int, ad: str) -> dict:
    """Overpass elemanlarından BAK düzeni (çizim planıyla birlikte, haritaya oturtulmuş). Hata: ValueError."""
    sinir = next((e for e in elemanlar if e.get("id") == sinir_kimligi and e["type"] in ("way", "relation")
                  and _geometri(e)), None)
    if not sinir:
        raise ValueError("Alanın sınırı bulunamadı.")
    sinir_geo = _geometri(sinir)
    enlem0 = sum(p["lat"] for p in sinir_geo) / len(sinir_geo)
    boylam0 = sum(p["lon"] for p in sinir_geo) / len(sinir_geo)
    kx = cz._kx(enlem0)

    def xy(lat, lon):
        return ((lon - boylam0) * kx, (lat - enlem0) * cz._KY)

    cokgen = [xy(p["lat"], p["lon"]) for p in sinir_geo]
    xs, ys = [p[0] for p in cokgen], [p[1] for p in cokgen]
    kutu = (min(xs) - 60, min(ys) - 60, max(xs) + 60, max(ys) + 60)
    kutuda = lambda p: kutu[0] <= p[0] <= kutu[2] and kutu[1] <= p[1] <= kutu[3]   # noqa: E731

    # Yol ağı (alanın biraz dışına taşan parçalar dahil; uzaktakiler atılır)
    konum: dict = {}
    komsu: dict = {}
    yol_turu: dict = {}
    for e in elemanlar:
        t = e.get("tags", {})
        if e["type"] != "way" or "highway" not in t or t["highway"] in _YOL_DISI or t.get("access") == "private" \
                or not e.get("geometry"):
            continue
        for nid, g in zip(e["nodes"], e["geometry"]):
            konum.setdefault(nid, xy(g["lat"], g["lon"]))
        for a, b in zip(e["nodes"], e["nodes"][1:]):
            if not (kutuda(konum[a]) or kutuda(konum[b])):
                continue
            komsu.setdefault(a, set()).add(b)
            komsu.setdefault(b, set()).add(a)
            yol_turu[frozenset((a, b))] = t["highway"]
    if not komsu:
        raise ValueError("Bu alanda haritada yürüme yolu yok.")

    sanal = [0]

    def yola_bagla(p):
        """Noktayı en yakın yol parçasına bağlar (parça bölünür). Döner: düğüm ve uzaklık (m)."""
        en = None
        for a in komsu:
            for b in komsu[a]:
                if a > b:
                    continue
                (ax, ay), (bx, by) = konum[a], konum[b]
                dx, dy = bx - ax, by - ay
                u = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy or 1)))
                q = (ax + u * dx, ay + u * dy)
                d = math.dist(p, q)
                if en is None or d < en[0]:
                    en = (d, a, b, u, q)
        d, a, b, u, q = en
        if u < 0.05 or math.dist(q, konum[a]) < 3:
            return a, d
        if u > 0.95 or math.dist(q, konum[b]) < 3:
            return b, d
        sanal[0] -= 1
        n = sanal[0]
        konum[n] = q
        tur = yol_turu[frozenset((a, b))]
        komsu[a].discard(b)
        komsu[b].discard(a)
        komsu[n] = {a, b}
        komsu[a].add(n)
        komsu[b].add(n)
        yol_turu[frozenset((a, n))] = yol_turu[frozenset((n, b))] = tur
        return n, d

    # Binalar: alanın içindeki adlı binalar, büyükten küçüğe en fazla EN_FAZLA_BINA
    binalar = []
    for e in elemanlar:
        t = e.get("tags", {})
        if "building" not in t or not t.get("name") or not _geometri(e) or _ATLA.search(t["name"]):
            continue
        noktalar = [xy(p["lat"], p["lon"]) for p in _geometri(e)]
        merkez = (sum(p[0] for p in noktalar) / len(noktalar), sum(p[1] for p in noktalar) / len(noktalar))
        if _icinde(merkez, cokgen) and not any(b[0] == t["name"] for b in binalar):
            binalar.append((t["name"], merkez, _alan_m2(noktalar)))
    binalar = sorted(binalar, key=lambda b: -b[2])[:EN_FAZLA_BINA]
    if not binalar:   # hastane gibi tek yapılı alan: alanın kendisi tek hedef
        binalar = [(ad, (sum(xs) / len(xs), sum(ys) / len(ys)), _alan_m2(cokgen))]

    # Giriş: sınırdaki kapı; yoksa alan sınırını kesen en önemli yol
    kapilar = [e for e in elemanlar if e["type"] == "node" and e.get("tags", {}).get("barrier") in
               ("gate", "lift_gate", "entrance") and e["id"] in komsu]
    if kapilar:
        onem = lambda n: max((_ONEM.get(yol_turu[frozenset((n, m))], 1) for m in komsu[n]), default=0)   # noqa: E731
        giris = max(kapilar, key=lambda e: onem(e["id"]))["id"]
    else:
        sinirda = [(a, b) for a in komsu for b in komsu[a]
                   if _icinde(konum[a], cokgen) and not _icinde(konum[b], cokgen)]
        if sinirda:
            a, _ = max(sinirda, key=lambda ab: (_ONEM.get(yol_turu[frozenset(ab)], 1), -math.dist(konum[ab[0]], (0, 0))))
            giris = a
        else:
            giris = min(komsu, key=lambda n: min(math.dist(konum[n], p) for p in cokgen))

    bina_dugum = {}
    for bad, p, _ in binalar:
        n, d = yola_bagla(p)
        bina_dugum[bad] = (n, d)

    # Girişten en kısa yollar (Dijkstra) ve hepsinin birleşimi olan ağaç
    uz, once = {giris: 0.0}, {}
    kuyruk = [(0.0, giris)]
    while kuyruk:
        d, u = heapq.heappop(kuyruk)
        if d > uz[u]:
            continue
        for v in komsu[u]:
            nd = d + math.dist(konum[u], konum[v])
            if nd < uz.get(v, 1e18):
                uz[v], once[v] = nd, u
                heapq.heappush(kuyruk, (nd, v))
    bina_dugum = {b: v for b, v in bina_dugum.items() if v[0] in uz}
    if not bina_dugum:
        raise ValueError("Girişten binalara giden yol bulunamadı.")
    cocuk: dict = {}
    for n, _ in bina_dugum.values():
        v = n
        while v != giris:
            cocuk.setdefault(once[v], set()).add(v)
            v = once[v]
    hedef_dugum = {}
    for bad, (n, _) in sorted(bina_dugum.items(), key=lambda kv: uz[kv[1][0]]):
        hedef_dugum.setdefault(n, []).append(bad)
    anahtar = {giris} | set(hedef_dugum) | {u for u, c in cocuk.items() if len(c) >= 2}

    # Noktalar ve yollar: ağaçta anahtar düğümden sonrakine
    kimlik, ad_ = {giris: "giris"}, {giris: "Giriş kapısı" if kapilar else "Giriş"}
    kullanilan = {"giris"}
    for n, adlar in hedef_dugum.items():
        if n == giris:
            continue
        k = kisalt(kisa_ad(adlar[0], ad))
        while k in kullanilan:
            k += "-2"
        kullanilan.add(k)
        kimlik[n], ad_[n] = k, f"{adlar[0]} önü"
    kavsak = 0
    baglantilar, sabit = [], []
    sira = [giris]
    while sira:
        u = sira.pop(0)
        for v in sorted(cocuk.get(u, ()), key=lambda v: uz[v]):
            yol = [u, v]
            while yol[-1] not in anahtar:
                yol.append(next(iter(cocuk[yol[-1]])))
            son = yol[-1]
            if son not in kimlik:
                kavsak += 1
                kimlik[son], ad_[son] = f"kavsak-{kavsak}", f"{kavsak}. kavşak"
            metre = sum(math.dist(konum[a], konum[b]) for a, b in zip(yol, yol[1:]))
            baglantilar.append({"a": kimlik[u], "b": kimlik[son], "adim": bm.metreden_adim(metre),
                                "tarif": f"{ad_[son]} yönüne ilerleyin", "geriTarif": f"{ad_[u]} yönüne ilerleyin"})
            # Kıvrımlı yolda çizimdeki düz çizgi gerçek yürüyüşten kısadır: yol boyu ölçüsü korunur
            if metre > 1.15 * math.dist(konum[u], konum[son]):
                sabit.append([kimlik[u], kimlik[son]])
            sira.append(son)

    hedefler = []
    for n, adlar in hedef_dugum.items():
        for bad in adlar:
            d = bina_dugum[bad][1]
            hedefler.append({"ad": bad, "nokta": kimlik[n],
                             "tarif": f"{bad} yakınındasınız" + ("." if d < 25 else f", bina yaklaşık {round(d / 10) * 10} "
                                                                  "metre içeride.") + " Bina kapısının yerini sorabilirsiniz.",
                             "anahtarlar": list(dict.fromkeys(
                                 s.replace("I", "ı").replace("İ", "i").lower() for s in (bad, kisa_ad(bad, ad))))})
            if kisa_ad(bad, ad) != bad:
                hedefler[-1]["kisaAd"] = kisa_ad(bad, ad)
    olcek = round(BIRIM_M / bm.STANDART_ADIM_M, 4)
    plan = {"olcek": olcek, "harita": {"enlem": round(enlem0, 6), "boylam": round(boylam0, 6)},
            "konum": {kimlik[n]: [round(konum[n][0] / BIRIM_M, 2), round(konum[n][1] / BIRIM_M, 2)] for n in kimlik},
            "tur": {kimlik[n]: ("bina" if n in hedef_dugum and n != giris else "kavsak") for n in kimlik},
            "otoTarif": [[b["a"], b["b"]] for b in baglantilar], "sabitAdim": sabit}
    mekan = {"id": "q-" + kisalt(ad, 30), "ad": ad, "tur": "kurum", "surum": 1, "giris": "giris",
             "noktalar": [{"id": kimlik[n], "ad": ad_[n]} for n in kimlik],
             "baglantilar": baglantilar, "hedefler": hedefler}
    cz.tarifleri_guncelle(mekan, plan)   # sağa / sola / düz, çizimdeki açılardan
    return {**mekan, "plan": plan}
