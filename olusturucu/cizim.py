"""2B çizim düzenleyici: kurum, binasını modül modül (bina, oda, kavşak, asansör…) çizer.

Modüller sürüklenince aradaki yolların adım sayısı çizimdeki mesafeden yeniden hesaplanır. Bir binanın içi ayrı bir
çizimdir: binaya tıklayıp "İçini aç" denince odaları eklenir. Hepsi BAK'ın düz nokta–yol–hedef biçimine yazılır; çizime
özgü bilgiler (konum, ölçek, modül türü, hangi odanın hangi binada olduğu) plan içinde durur ve QR'a girmez.

plan anahtarları:
  konum  {nokta: [x, y]}  çizimdeki yer (birim: olcek kadar adım)
  olcek  bir birimin kaç adım olduğu
  tur    {nokta: modül türü}
  ust    {nokta: bina noktası}  bina içindeki odalar; konumları binanın kendi çizimindedir
  icKonum {bina: [x, y]}  bina girişinin, binanın iç çizimindeki yeri
  icOlcek {bina: adım}    iç çizimde bir birimin kaç adım olduğu (varsayılan 1)
  sabitAdim [[a, b]]      sahada sayılıp elle yazılmış adımlar: sürükleyince değişmez
  harita {enlem, boylam}  dış çizim haritaya oturtulduysa çizimin (0, 0) noktasının konumu. O zaman dış çizim gerçek
                          ölçekte ve kuzey yukarıdadır (bir birim = olcek × 0,7 m); noktaların harita konumu
                          çizimdeki yerinden hesaplanır, arka planda harita görünür
  gps    {nokta: [enlem, boylam]}  çizim henüz haritaya oturtulmadıysa elle yerleştirilen noktalar (en az ikisi
                          girilince çizim haritaya oturtulur, bkz. harita.py)
"""

from __future__ import annotations

import heapq
import json
import math
import re
import statistics
from collections import deque
from collections.abc import Callable

import streamlit as st

import bak_mekan as bm

MODULLER = {
    "bina": ("Bina", ":material/apartment:"),
    "oda": ("Oda / birim", ":material/meeting_room:"),
    "kavsak": ("Nokta (koridor başı, kavşak)", ":material/fork_right:"),   # ör. yalnızca etiket asılacak yer
    "danisma": ("Danışma", ":material/support_agent:"),
    "wc": ("Tuvalet", ":material/wc:"),
    "asansor": ("Asansör", ":material/elevator:"),
    "merdiven": ("Merdiven", ":material/stairs:"),
}
# Bu modüller ziyaretçinin sorabileceği yerlerdir: eklenince hedef de olur
HEDEF_MODULLERI = {"bina", "oda", "danisma", "wc", "asansor", "merdiven"}
ANAHTAR_EKLERI = {"wc": ["tuvalet", "wc", "lavabo"], "danisma": ["danışma", "bilgi"],
                  "asansor": ["asansör"], "merdiven": ["merdiven"]}
YENI_MESAFE = 10   # yeni modül seçili modülden bu kadar adım uzağa konur


# ── Yerleşim ve ölçek ─────────────────────────────────────

def olcek(mekan: dict, plan: dict) -> float:
    """Bir çizim biriminin kaç adım olduğu: kayıtlıysa o, değilse var olan yolların adım/mesafe oranı."""
    if plan.get("olcek"):
        return float(plan["olcek"])
    konum = gorunum_konumlari(plan, None)
    oranlar = []
    for b in mekan.get("baglantilar") or []:
        if (b.get("tur") or "yuru") in bm.DIKEY_GECISLER or b["a"] not in konum or b["b"] not in konum:
            continue
        d = math.dist(konum[b["a"]], konum[b["b"]])
        if d > 0.01 and b.get("adim"):
            oranlar.append(b["adim"] / d)
    if oranlar:
        return round(statistics.median(oranlar), 3)
    # Hiç konum yok (tablodan ya da eski şablondan): kısa yollar da etiketler çakışmadan çizilsin diye
    # bir birim birkaç adımın altında tutulur (kısa yollar en az ~8 birim olur)
    adimlar = sorted(b["adim"] for b in mekan.get("baglantilar") or []
                     if (b.get("tur") or "yuru") not in bm.DIKEY_GECISLER and b.get("adim"))
    return round(min(1.0, max(0.1, adimlar[len(adimlar) // 4] / 8)), 3) if adimlar else 1.0


def gorunum_konumlari(plan: dict, gorunum: str | None) -> dict[str, list[float]]:
    """Bir çizimin koordinatları: dış çizimde binalara ait olmayan noktalar; bina çiziminde odalar ve binanın
    girişi (iç çizimdeki yeriyle)."""
    konum = plan.get("konum") or {}
    ust = plan.get("ust") or {}
    if not gorunum:
        return {i: p for i, p in konum.items() if i not in ust}
    ic = {i: konum[i] for i, u in ust.items() if u == gorunum and i in konum}
    ic[gorunum] = (plan.get("icKonum") or {}).get(gorunum, [0.0, 0.0])
    return ic


def gorunum_olcegi(plan: dict, gorunum: str | None, dis_olcek: float) -> float:
    return float((plan.get("icOlcek") or {}).get(gorunum, 1.0)) if gorunum else dis_olcek


def yerlesim(mekan: dict, plan: dict, olc: float) -> dict[str, list[float]]:
    """Kayıtlı konumlar korunur; konumu olmayan noktalar girişten başlayarak komşusunun yanına, yolun adım
    sayısı kadar uzağa yerleştirilir (kardeşler yelpaze gibi açılır)."""
    konum = {k: list(v) for k, v in (plan.get("konum") or {}).items()}
    idler = [n["id"] for n in mekan.get("noktalar") or []]
    komsu: dict[str, list[tuple[str, float]]] = {i: [] for i in idler}
    for b in mekan.get("baglantilar") or []:
        if b["a"] in komsu and b["b"] in komsu:
            adim = b.get("adim") or YENI_MESAFE
            if (b.get("tur") or "yuru") in bm.DIKEY_GECISLER:
                adim = 4   # başka kattaki uç: çizimde hemen yanına
            komsu[b["a"]].append((b["b"], adim))
            komsu[b["b"]].append((b["a"], adim))
    gezilen: set[str] = set()
    for kok in [mekan.get("giris"), *idler]:
        if kok not in komsu or kok in gezilen:
            continue
        if kok not in konum:
            alt = max((v[1] for v in konum.values()), default=-8.0) + 8
            konum[kok] = [0.0, alt]
        gezilen.add(kok)
        kuyruk = deque([(kok, None)])
        while kuyruk:
            u, ebeveyn = kuyruk.popleft()
            ux, uy = konum[u]
            # Yollar girişten yukarı doğru açılır: etiketler yatay olduğu için dikey zincirler çakışmaz
            temel = math.atan2(uy - konum[ebeveyn][1], ux - konum[ebeveyn][0]) if ebeveyn else math.pi / 2
            yerlesecek = [(v, a) for v, a in komsu[u] if v not in konum]
            for i, (v, adim) in enumerate(yerlesecek):
                sira = (i + 1) // 2 * (1 if i % 2 else -1)
                aci = temel + sira * math.radians(60)
                konum[v] = [round(ux + math.cos(aci) * adim / olc, 1), round(uy + math.sin(aci) * adim / olc, 1)]
            for v, _ in komsu[u]:
                if v not in gezilen:
                    gezilen.add(v)
                    kuyruk.append((v, u))
    return {i: konum[i] for i in idler if i in konum}


def gorunum_noktalari(mekan: dict, plan: dict, gorunum: str | None, kat: int | None) -> set[str]:
    """Bir çizimde görünen noktalar: dış çizimde binalara bağlı olmayanlar (seçili kat), bina çiziminde o
    binanın odaları ve binanın kendisi (girişi)."""
    ust = plan.get("ust") or {}
    if gorunum:
        return {gorunum} | {i for i, u in ust.items() if u == gorunum}
    return {n["id"] for n in mekan.get("noktalar") or []
            if n["id"] not in ust and (kat is None or (n.get("kat") or 0) == kat)}


# ── Değişiklikler (mekan ve plan yerinde değiştirilir) ────

def _yeni_kimlik(mekan: dict, ad: str) -> str:
    govde = bm.kisalt(ad) or "nokta"
    var = {n["id"] for n in mekan["noktalar"]}
    kimlik, i = govde, 2
    while kimlik in var:
        kimlik, i = f"{govde}-{i}", i + 1
    return kimlik


def _adim(konum: dict, a: str, b: str, olc: float) -> int:
    return max(1, round(math.dist(konum[a], konum[b]) * olc))


def bagla(mekan: dict, plan: dict, a: str, b: str, olc: float, gorunum: str | None = None) -> bool:
    """İki modül arasına yürüme yolu ekler; adım çizimdeki mesafeden. Yol zaten varsa bir şey yapmaz."""
    if a == b or any({y["a"], y["b"]} == {a, b} for y in mekan["baglantilar"]):
        return False
    konum = gorunum_konumlari(plan, gorunum)
    adlar = {n["id"]: n["ad"] for n in mekan["noktalar"]}
    mekan["baglantilar"].append({
        "a": a, "b": b, "adim": _adim(konum, a, b, olc) if a in konum and b in konum else YENI_MESAFE,
        "tarif": f"{adlar[b]} yönüne ilerleyin", "geriTarif": f"{adlar[a]} yönüne ilerleyin"})
    # Yön (sağa/sola/düz) kaydedilirken çizimden hesaplanır (tarifleri_guncelle)
    plan.setdefault("otoTarif", []).append([a, b])
    return True


# ── Çizimden yön tarifi ───────────────────────────────────
# Görme engelli ziyaretçiye "tuvalet yönüne ilerleyin" bir şey söylemez; sağa mı, sola mı, düz mü gideceğini bilmeli.
# Ziyaretçinin bir noktaya hangi yönden geldiği, girişten oraya giden en kısa yoldan bulunur; çıkış yönüyle arasındaki
# açı tarife çevrilir. Dönüşte (geri tarif) aynı yolun tersi kullanılır. Elle yazılan ve örneklerden gelen tarifler
# korunur: yalnızca BAK'ın ürettiği tarifler (plan["otoTarif"]) ve eski genel cümleler yeniden hesaplanır.
_GENEL_TARIF = re.compile(r"^.+ yönüne ilerleyin\.?$")
# BAK'ın ürettiği tarif kalıpları. "Otomatik" işaretli bir yolun tarifi bunlardan biri değilse kurum onu (ör.
# Tablolar sayfasında) elle değiştirmiştir: korunur, telefondaki uygulama da onu okur.
_OTO_TARIF = re.compile(r"^(Düz ilerleyin|Hafif (sağa|sola) yönelin|(Sağa|Sola) dönün|Geri dönün|.+ yönüne ilerleyin)$")


def _oto_mu(b: dict) -> bool:
    return bool(_OTO_TARIF.match(b.get("tarif") or "") and _OTO_TARIF.match(b.get("geriTarif") or ""))


def donus_metni(gelis: tuple[float, float], gidis: tuple[float, float]) -> str:
    """İki yön arasındaki açı → "Düz ilerleyin", "Hafif sağa yönelin", "Sola dönün", "Geri dönün". Planda y yukarı."""
    aci = math.degrees(math.atan2(gelis[0] * gidis[1] - gelis[1] * gidis[0], gelis[0] * gidis[0] + gelis[1] * gidis[1]))
    if abs(aci) < 30:
        return "Düz ilerleyin"
    taraf = "sola" if aci > 0 else "sağa"   # saat yönünün tersi (artı açı) sol
    if abs(aci) < 60:
        return f"Hafif {taraf} yönelin"
    if abs(aci) < 150:
        return f"{taraf.capitalize()} dönün"
    return "Geri dönün"


def _yon(konum: dict, a: str, b: str) -> tuple[float, float]:
    return konum[b][0] - konum[a][0], konum[b][1] - konum[a][1]


def tarifleri_guncelle(mekan: dict, plan: dict) -> int:
    """Her çizimde (dış çizim ve her binanın içi) BAK'ın ürettiği yürüme tariflerini açılardan yeniden yazar.
    Değişen yol sayısı döner."""
    oto = {tuple(y) for y in plan.get("otoTarif") or []}
    hedef_noktalari = {h["nokta"] for h in mekan["hedefler"]}
    adlar = {h["nokta"]: bm.liste_adi(h) for h in mekan["hedefler"]}
    adlar = {n["id"]: adlar.get(n["id"], n["ad"]) for n in mekan["noktalar"]}
    degisen = 0
    gorunumler = [None, *dict.fromkeys((plan.get("ust") or {}).values())]
    for gorunum in gorunumler:
        konum = gorunum_konumlari(plan, gorunum)
        yollar = [b for b in mekan["baglantilar"] if b["a"] in konum and b["b"] in konum
                  and (b.get("tur") or "yuru") not in bm.DIKEY_GECISLER and b["a"] != b["b"]]
        if not yollar:
            continue
        komsu: dict[str, list[str]] = {}
        for b in yollar:
            komsu.setdefault(b["a"], []).append(b["b"])
            komsu.setdefault(b["b"], []).append(b["a"])
        # Kök: kurumun girişi (dış çizimde) ya da binanın girişi (iç çizimde); yoksa ilk nokta
        kok = gorunum or (mekan.get("giris") if mekan.get("giris") in komsu else next(iter(komsu)))
        if kok not in komsu:
            continue
        # Girişten en kısa yollar ağacı (Dijkstra, mesafe çizimden)
        uz, ebeveyn, kuyruk = {kok: 0.0}, {kok: None}, [(0.0, kok)]
        while kuyruk:
            d, u = heapq.heappop(kuyruk)
            if d > uz[u]:
                continue
            for v in komsu[u]:
                nd = d + math.dist(konum[u], konum[v])
                if nd < uz.get(v, math.inf):
                    uz[v], ebeveyn[v] = nd, u
                    heapq.heappush(kuyruk, (nd, v))
        cocuklar: dict[str, list[str]] = {}
        for v, u in ebeveyn.items():
            if u:
                cocuklar.setdefault(u, []).append(v)
        # Girişte ziyaretçi binanın içine (çizimin ortasına) bakar
        ox = sum(p[0] for p in konum.values()) / len(konum)
        oy = sum(p[1] for p in konum.values()) / len(konum)
        giris_bakisi = (ox - konum[kok][0], oy - konum[kok][1])

        def gidis(u: str, v: str) -> str:
            """u'dan v'ye: girişten u'ya gelinen yöne göre dönüş."""
            p = ebeveyn.get(u)
            gelis = _yon(konum, p, u) if p else giris_bakisi
            if not p and math.hypot(*gelis) < 0.01:
                return f"{adlar[v]} yönüne ilerleyin"
            # Yalnızca dönüş: uygulama "…, yaklaşık 8 adım. WC noktasına ulaşacaksınız." diye tamamlar (yer iki kez
            # söylenmesin); art arda "Düz ilerleyin" bölümleri de uygulamada tek düz yürüyüş olarak birleşir
            return donus_metni(gelis, _yon(konum, u, v))

        def donus(u: str, v: str) -> str:
            """u'dan girişe doğru v'ye. u bir oda/hedef ya da uç ise ziyaretçi oraya girişten gelmiştir: geri döner.
            Bir koridor noktasıysa içeriden (tek çocuğundan) geldiği varsayılır."""
            alt = cocuklar.get(u, [])
            if not alt or u in hedef_noktalari:
                return "Geri dönün"
            if len(alt) == 1:
                return donus_metni(_yon(konum, alt[0], u), _yon(konum, u, v))
            return f"{adlar[v]} yönüne ilerleyin"

        for b in yollar:
            anahtar = (b["a"], b["b"])
            if anahtar in oto and not _oto_mu(b):
                oto.discard(anahtar)   # otomatikti ama kurum elle değiştirdi
            if anahtar not in oto and not (_GENEL_TARIF.match(b.get("tarif") or "")
                                           and _GENEL_TARIF.match(b.get("geriTarif") or "")):
                continue   # elle yazılmış ya da örnekten gelen tarif
            a, c = b["a"], b["b"]
            if ebeveyn.get(c) == a:          # a girişe daha yakın: gidiş a → c
                yeni = gidis(a, c), donus(c, a)
            elif ebeveyn.get(a) == c:        # c girişe daha yakın: a → c girişe doğru
                yeni = donus(a, c), gidis(c, a)
            else:                            # ağaç dışı (döngü) yolu: iki uç da kendi geliş yönüne göre
                yeni = gidis(a, c), gidis(c, a)
            if (b.get("tarif"), b.get("geriTarif")) != yeni:
                b["tarif"], b["geriTarif"] = yeni
                degisen += 1
            oto.add(anahtar)
    plan["otoTarif"] = sorted(map(list, oto))
    return degisen


def pusula_yonu(konum: dict, a: str, b: str) -> int:
    """a'dan b'ye çizimdeki yön: kuzey (çizimin üstü) 0, doğu 90 (saat yönünde derece)."""
    dx, dy = _yon(konum, a, b)
    return round(math.degrees(math.atan2(dx, dy))) % 360


def yonleri_ekle(mekan: dict, plan: dict) -> dict:
    """QR'a girecek düzene her yürüme yolunun çizimdeki yönünü ("yon") ve BAK'ın ürettiği tarif işaretini ("oto")
    ekler (kopya döner). Telefondaki uygulama, gerçekte izlenen rotada önceki yolun yönüyle karşılaştırıp her köşede
    dönüşü kendisi söyler: WC'den müdür odasına giderken holde "düz", girişten gelirken "sola" der. Bina içi çizim
    ayrı bir koordinat sistemi olduğu için bina girişine değen iç yollara yön yazılmaz (orada kayıtlı tarif okunur)."""
    yeni = json.loads(json.dumps(mekan))
    oto = {tuple(y) for y in plan.get("otoTarif") or []}
    for gorunum in [None, *dict.fromkeys((plan.get("ust") or {}).values())]:
        konum = gorunum_konumlari(plan, gorunum)
        for b in yeni["baglantilar"]:
            if (b.get("tur") or "yuru") in bm.DIKEY_GECISLER or b["a"] not in konum or b["b"] not in konum \
                    or (gorunum and gorunum in (b["a"], b["b"])) or b["a"] == b["b"]:
                continue
            if math.dist(konum[b["a"]], konum[b["b"]]) < 0.01:
                continue
            b["yon"] = pusula_yonu(konum, b["a"], b["b"])
            if (b["a"], b["b"]) in oto and _oto_mu(b):
                b["oto"] = True
    # Açık alandaki noktaların harita koordinatı: uygulama "neredeyim"de GPS'ten en yakın noktayı söyler
    gps = dis_gps(plan)
    for n in yeni["noktalar"]:
        if n["id"] in gps:
            n["enlem"], n["boylam"] = gps[n["id"]]
    return yeni


# ── Çizim ↔ harita ────────────────────────────────────────
# Haritaya oturtulmuş dış çizimde x doğu, y kuzey yönünde metredir (bir birim = olcek × standart adım). Kampüs
# ölçeğinde (birkaç km) dünyanın eğriliği önemsizdir: enlem/boylam farkı metreye doğrusal çevrilir.
_KY = 110540.0   # 1 derece enlem, metre


def _kx(enlem: float) -> float:
    return 111320.0 * math.cos(math.radians(enlem))


def harita_birimi(plan: dict) -> float:
    """Haritaya oturtulmuş çizimde bir birimin kaç metre olduğu."""
    return float(plan.get("olcek") or 1.0) * bm.STANDART_ADIM_M


def konumdan_gps(plan: dict, p) -> tuple[float, float]:
    h, m = plan["harita"], harita_birimi(plan)
    return (round(h["enlem"] + p[1] * m / _KY, 6), round(h["boylam"] + p[0] * m / _kx(h["enlem"]), 6))


def gpsden_konum(plan: dict, enlem: float, boylam: float) -> list[float]:
    h, m = plan["harita"], harita_birimi(plan)
    return [round((boylam - h["boylam"]) * _kx(h["enlem"]) / m, 2), round((enlem - h["enlem"]) * _KY / m, 2)]


def dis_gps(plan: dict) -> dict[str, tuple[float, float]]:
    """Dış çizimdeki noktaların harita konumu: çizim haritaya oturtulduysa hepsi çizimden; değilse yalnızca elle
    yerleştirilenler."""
    dis = gorunum_konumlari(plan, None)
    if plan.get("harita"):
        return {i: konumdan_gps(plan, p) for i, p in dis.items()}
    gps = {i: gps_coz(v) for i, v in (plan.get("gps") or {}).items() if i in dis}
    return {i: k for i, k in gps.items() if k}


def gps_coz(deger) -> tuple[float, float] | None:
    """[enlem, boylam] ya da Google Haritalar'dan kopyalanan "41.1308, 42.7864" metni → (enlem, boylam)."""
    if isinstance(deger, str):
        parcalar = [p for p in deger.replace(";", ",").replace(" ", ",").split(",") if p]
        if len(parcalar) != 2:
            return None
        deger = parcalar
    try:
        enlem, boylam = float(deger[0]), float(deger[1])
    except (TypeError, ValueError, IndexError):
        return None
    if not (-90 <= enlem <= 90 and -180 <= boylam <= 180) or (enlem == 0 and boylam == 0):
        return None
    return round(enlem, 6), round(boylam, 6)


def modul_ekle(mekan: dict, plan: dict, tur: str, ad: str, *, yer: list[float], ust: str | None,
               baglanacak: str | None, olc: float, kat: int = 0) -> str:
    """Yeni modül: nokta (+ hedef türlerinde hedef), çizimdeki yeri ve isteğe bağlı olarak seçili modüle yol."""
    ad = ad.strip() or MODULLER[tur][0]
    # "Yer ekle"de hepsi "Oda" seçiliyken "WC", "Danışma" yazılırsa doğru tür (ve "tuvalet" gibi söyleyişler) gelsin
    if tur == "oda":
        kucuk_ad = ad.replace("I", "ı").replace("İ", "i").lower()
        for t, sozler in (("wc", ("wc", "tuvalet", "lavabo")), ("danisma", ("danışma", "bilgi masası")),
                          ("asansor", ("asansör",)), ("merdiven", ("merdiven",))):
            if any(soz in kucuk_ad for soz in sozler):
                tur = t
                break
    nokta_adi = f"{ad} girişi" if tur == "bina" else f"{ad} kapısı" if tur == "oda" else ad
    kimlik = _yeni_kimlik(mekan, ad)
    nokta = {"id": kimlik, "ad": nokta_adi}
    if kat:
        nokta["kat"] = kat
    mekan["noktalar"].append(nokta)
    plan.setdefault("konum", {})[kimlik] = [round(yer[0], 1), round(yer[1], 1)]
    plan.setdefault("tur", {})[kimlik] = tur
    if ust:
        plan.setdefault("ust", {})[kimlik] = ust
    if tur in HEDEF_MODULLERI:
        kucuk = ad.replace("I", "ı").replace("İ", "i").lower()
        sozcukler = [w for w in kucuk.split() if len(w) >= 3]
        mekan["hedefler"].append({"ad": ad, "nokta": kimlik, "tarif": f"{nokta_adi} burada.",
                                  "anahtarlar": list(dict.fromkeys([kucuk, *sozcukler,
                                                                    *ANAHTAR_EKLERI.get(tur, [])]))})
    if not mekan.get("giris"):
        mekan["giris"] = kimlik
    if baglanacak:
        bagla(mekan, plan, baglanacak, kimlik, olc, ust)
    return kimlik


def tasi(mekan: dict, plan: dict, kimlik: str, x: float, y: float, olc: float,
         gorunum: str | None = None) -> list[tuple[str, str, int]]:
    """Modülü taşır; ona bağlı yürüme yollarının adımı yeni mesafeden hesaplanır. Değişen yollar döner."""
    if gorunum and kimlik == gorunum:
        plan.setdefault("icKonum", {})[kimlik] = [round(x, 1), round(y, 1)]
    else:
        plan.setdefault("konum", {})[kimlik] = [round(x, 1), round(y, 1)]
    konum = gorunum_konumlari(plan, gorunum)
    sabit = {tuple(y) for y in plan.get("sabitAdim") or []}   # sahada sayılıp elle yazılan adımlar
    degisen = []
    for b in mekan["baglantilar"]:
        if (b["a"], b["b"]) in sabit:
            continue
        if kimlik in (b["a"], b["b"]) and (b.get("tur") or "yuru") not in bm.DIKEY_GECISLER \
                and b["a"] in konum and b["b"] in konum:
            yeni = _adim(konum, b["a"], b["b"], olc)
            if yeni != b.get("adim"):
                b["adim"] = yeni
                degisen.append((b["a"], b["b"], yeni))
    return degisen


def plan_kimlikleri_degistir(plan: dict, harita: dict[str, str]) -> None:
    """Nokta kimliği değişince çizimdeki yeri, türü, harita konumu vb. de yeni kimliğe taşınır."""
    for alan in ("konum", "icKonum", "tur", "ust", "gps", "icOlcek"):
        sozluk = plan.get(alan)
        if isinstance(sozluk, dict):
            plan[alan] = {harita.get(k, k): (harita.get(v, v) if alan == "ust" else v) for k, v in sozluk.items()}
    for alan in ("sabitAdim", "otoTarif"):
        if plan.get(alan):
            plan[alan] = [[harita.get(a, a), harita.get(b, b)] for a, b in plan[alan]]
    if plan.get("etiketsiz"):
        plan["etiketsiz"] = sorted(harita.get(i, i) for i in plan["etiketsiz"])


def nokta_sil(mekan: dict, plan: dict, kimlik: str) -> None:
    """Modülü, ona bağlı yolları ve hedefleri siler; bina silinince içindeki odalar da silinir."""
    ust = plan.get("ust") or {}
    silinecek = {kimlik} | {i for i, u in ust.items() if u == kimlik}
    mekan["noktalar"] = [n for n in mekan["noktalar"] if n["id"] not in silinecek]
    mekan["baglantilar"] = [b for b in mekan["baglantilar"] if b["a"] not in silinecek and b["b"] not in silinecek]
    mekan["hedefler"] = [h for h in mekan["hedefler"] if h["nokta"] not in silinecek]
    for alan in ("konum", "tur", "ust", "gps", "icKonum"):
        for i in silinecek:
            (plan.get(alan) or {}).pop(i, None)
    if mekan.get("giris") in silinecek:
        mekan["giris"] = mekan["noktalar"][0]["id"] if mekan["noktalar"] else ""
    if mekan.get("kasa") in silinecek:
        mekan["kasa"] = None


def binayi_doldur(mekan: dict, plan: dict, bina: str, metin: str, dikey: str = "ikisi") -> int:
    """Binanın içini kat listesinden kurar: her katta koridor, sırayla sol/sağ kapılar, katlar arasında
    merdiven/asansör ("Zemin kat: Sekreterlik, Dekan odası, WC / 1. kat: 101, 102"). Koridorlu bina sihirbazının
    ürettiği düzen bu binanın iç çizimine modüller olarak eklenir; binanın girişi koridora bağlanır.
    Eklenen hedef sayısı döner."""
    import sihirbaz   # döngüsel içe aktarmayı önlemek için burada

    liste = sihirbaz.kat_listesi_coz(metin)
    if not liste:
        return 0
    ilk, son = min(liste), max(liste)
    katlar = [[{"ad": ad, "taraf": "sol" if i % 2 == 0 else "sag", "adim": 5} for i, ad in enumerate(liste.get(k, []))]
              for k in range(ilk, son + 1)]
    bina_adi = next((h["ad"] for h in mekan["hedefler"] if h["nokta"] == bina),
                    next(n["ad"] for n in mekan["noktalar"] if n["id"] == bina))
    alt, alt_plan = sihirbaz.bina_olustur(bina_adi, mekan.get("tur") or "kurum", katlar, giris_adim=6, dikey=dikey,
                                          ilk_kat=ilk)

    # Kimlikler bina adıyla öneklenir (iki binada da "koridor-0" olabilir); sihirbazın girişi bu binanın kendisidir
    var = {n["id"] for n in mekan["noktalar"]}
    harita = {"giris": bina}
    for n in alt["noktalar"]:
        if n["id"] != "giris":
            kimlik, i = f"{bina}-{n['id']}", 2
            while kimlik in var:
                kimlik, i = f"{bina}-{n['id']}-{i}", i + 1
            harita[n["id"]] = kimlik
            var.add(kimlik)
    ust = plan.setdefault("ust", {})
    konum = plan.setdefault("konum", {})
    for n in alt["noktalar"]:
        if n["id"] == "giris":
            continue
        mekan["noktalar"].append({**n, "id": harita[n["id"]]})
        ust[harita[n["id"]]] = bina
        konum[harita[n["id"]]] = list(alt_plan["konum"][n["id"]])
    gx, gy = alt_plan["konum"]["giris"]
    plan.setdefault("icKonum", {})[bina] = [gx, gy]
    for b in alt["baglantilar"]:
        mekan["baglantilar"].append({**b, "a": harita[b["a"]], "b": harita[b["b"]]})
    adlar = {h["ad"] for h in mekan["hedefler"]}
    for h in alt["hedefler"]:
        # Başka binada ya da başka katta da "WC" olabilir: listede ayırt edilsin diye bina adı, gerekirse kat eklenir
        kat = next((n.get("kat") or 0) for n in alt["noktalar"] if n["id"] == h["nokta"])
        ad = next((a for a in (h["ad"], f"{h['ad']} ({bina_adi})",
                               f"{h['ad']} ({bina_adi}, {sihirbaz.kat_adi(kat)})") if a not in adlar), None)
        adlar.add(ad)
        mekan["hedefler"].append({**h, "ad": ad, "nokta": harita[h["nokta"]]})
    # İç çizimin ölçeği sihirbazın verdiği adımlardan: sürükleyince adımlar tutarlı değişsin
    ic = gorunum_konumlari(plan, bina)
    oranlar = [b["adim"] / math.dist(ic[b["a"]], ic[b["b"]]) for b in mekan["baglantilar"]
               if (b.get("tur") or "yuru") not in bm.DIKEY_GECISLER and b["a"] in ic and b["b"] in ic
               and math.dist(ic[b["a"]], ic[b["b"]]) > 0.01]
    if oranlar:
        plan.setdefault("icOlcek", {})[bina] = round(statistics.median(oranlar), 3)
    plan.setdefault("tur", {})[bina] = "bina"
    return len(alt["hedefler"])


def sirala_adaylari(mekan: dict, plan: dict, merkez: str, gorunum: str | None = None) -> list[str]:
    """Merkeze tek tek bağlı, başka hiçbir yere bağlı olmayan ve aynı yönde duran odalar (yıldız biçimi).
    Yön, en uzaktaki odanın yönüdür; ondan 50°'den fazla sapanlar (ör. arkadaki merdiven) katılmaz."""
    konum = gorunum_konumlari(plan, gorunum)
    if merkez not in konum:
        return []
    derece: dict[str, int] = {}
    for b in mekan["baglantilar"]:
        for u in (b["a"], b["b"]):
            derece[u] = derece.get(u, 0) + 1
    yapraklar = [v for b in mekan["baglantilar"] if merkez in (b["a"], b["b"])
                 and (b.get("tur") or "yuru") not in bm.DIKEY_GECISLER
                 for v in [b["b"] if b["a"] == merkez else b["a"]]
                 if derece.get(v) == 1 and v in konum and v != mekan.get("giris")]
    if len(yapraklar) < 2:
        return []
    mx, my = konum[merkez]
    uzak = max(yapraklar, key=lambda v: math.dist(konum[v], konum[merkez]))
    yon = math.atan2(konum[uzak][1] - my, konum[uzak][0] - mx)

    def sapma(v):
        return abs((math.atan2(konum[v][1] - my, konum[v][0] - mx) - yon + math.pi) % (2 * math.pi) - math.pi)

    secilen = [v for v in yapraklar if sapma(v) <= math.radians(50)]
    return secilen if len(secilen) >= 2 else []


def koridora_diz(mekan: dict, plan: dict, merkez: str, olc: float, gorunum: str | None = None) -> int:
    """Merkeze ayrı ayrı bağlı odaları koridor gibi sıraya dizer: merkez → en yakın oda → sonraki → …
    Odanın koridorun solunda mı sağında mı olduğu çizimden bulunur ve tarife yazılır. Dizilen oda sayısı döner."""
    secilen = sirala_adaylari(mekan, plan, merkez, gorunum)
    if not secilen:
        return 0
    konum = gorunum_konumlari(plan, gorunum)
    mx, my = konum[merkez]
    # Koridorun ekseni: merkezden odaların ortasına (kapılar eksenin iki yanına dağılır)
    ux = sum(konum[v][0] for v in secilen) / len(secilen) - mx
    uy = sum(konum[v][1] for v in secilen) / len(secilen) - my
    boy = math.hypot(ux, uy) or 1
    ux, uy = ux / boy, uy / boy
    secilen.sort(key=lambda v: (konum[v][0] - mx) * ux + (konum[v][1] - my) * uy)
    adlar = {h["nokta"]: bm.liste_adi(h) for h in mekan["hedefler"]}
    adlar = {n["id"]: adlar.get(n["id"], n["ad"]) for n in mekan["noktalar"]}
    mekan["baglantilar"] = [b for b in mekan["baglantilar"]
                            if not ({b["a"], b["b"]} & set(secilen) and merkez in (b["a"], b["b"]))]
    onceki = merkez
    for i, v in enumerate(secilen):
        # Planda y yukarı doğru artar: koridor yönüne göre çapraz çarpım artıysa oda solda
        capraz = ux * (konum[v][1] - my) - uy * (konum[v][0] - mx)
        taraf = "solunuzda" if capraz > 0 else "sağınızda"
        mekan["baglantilar"].append({
            "a": onceki, "b": v, "adim": _adim(konum, onceki, v, olc),
            "tarif": f"Koridora girin, {adlar[v]} {taraf}" if i == 0
            else f"Koridorda düz devam edin, {adlar[v]} {taraf}",
            "geriTarif": f"Koridorda {adlar[merkez]} yönüne ilerleyin"})
        onceki = v
    return len(secilen)


def yolu_bol(mekan: dict, plan: dict, a: str, b: str, yer: tuple[float, float] | None = None,
             gorunum: str | None = None) -> str | None:
    """a–b yolunun üstüne yeni bir kavşak (ya da köşe) noktası koyar; yol ikiye bölünür. Yol gerçekte dönerek
    gidiyorsa nokta köşeye sürüklenir ve tarif "…sonra sola dönün" diye doğru söylenir. yer verilirse (çizimde
    çift tıklanan yer) yolun en yakın yerine, verilmezse ortasına konur. Toplam adım korunur; elle yazılmış
    (sahada sayılmış) mesafe iki parçaya oranla bölünür ve elle sayılmış kalır. Yeni noktanın kimliği döner."""
    yol = next((y for y in mekan["baglantilar"] if {y["a"], y["b"]} == {a, b}), None)
    konum = gorunum_konumlari(plan, gorunum)
    if not yol or (yol.get("tur") or "yuru") in bm.DIKEY_GECISLER or yol["a"] not in konum or yol["b"] not in konum:
        return None
    (ax, ay), (bx, by) = konum[yol["a"]], konum[yol["b"]]
    dx, dy = bx - ax, by - ay
    u = 0.5
    if yer and (dx or dy):
        u = ((yer[0] - ax) * dx + (yer[1] - ay) * dy) / (dx * dx + dy * dy)
    u = min(0.9, max(0.1, u))
    numaralar = [int(m.group(1)) for n in mekan["noktalar"] if (m := re.match(r"^(\d+)\. kavşak$", n["ad"]))]
    no = max(numaralar, default=0) + 1
    kimlik = f"kavsak-{no}"
    mevcut = {n["id"] for n in mekan["noktalar"]}
    while kimlik in mevcut:
        no += 1
        kimlik = f"kavsak-{no}"
    nokta = {"id": kimlik, "ad": f"{no}. kavşak"}
    kat = next((n.get("kat") for n in mekan["noktalar"] if n["id"] == yol["a"]), None)
    if kat:
        nokta["kat"] = kat
    mekan["noktalar"].append(nokta)
    plan.setdefault("konum", {})[kimlik] = [round(ax + u * dx, 2), round(ay + u * dy, 2)]
    plan.setdefault("tur", {})[kimlik] = "kavsak"
    if gorunum:
        plan.setdefault("ust", {})[kimlik] = gorunum
    # Köşe noktasına QR etiketi gerekmez; isteyen panelden açar
    plan["etiketsiz"] = sorted(set(plan.get("etiketsiz") or []) | {kimlik})
    toplam = int(yol.get("adim") or 1)
    ilk = min(max(1, round(toplam * u)), max(1, toplam - 1))
    adlar = {n["id"]: n["ad"] for n in mekan["noktalar"]}
    parcalar = []
    for p, q, adim in ((yol["a"], kimlik, ilk), (kimlik, yol["b"], max(1, toplam - ilk))):
        parca = {k: v for k, v in yol.items() if k not in ("a", "b", "adim", "tarif", "geriTarif")}
        parca.update(a=p, b=q, adim=adim, tarif=f"{adlar[q]} yönüne ilerleyin", geriTarif=f"{adlar[p]} yönüne ilerleyin")
        parcalar.append(parca)
    i = mekan["baglantilar"].index(yol)
    mekan["baglantilar"][i:i + 1] = parcalar
    eski = {(yol["a"], yol["b"]), (yol["b"], yol["a"])}
    sabit = [s for s in plan.get("sabitAdim") or [] if tuple(s) not in eski]
    if len(sabit) != len(plan.get("sabitAdim") or []):
        sabit += [[p["a"], p["b"]] for p in parcalar]
    plan["sabitAdim"] = sabit
    plan["otoTarif"] = [o for o in plan.get("otoTarif") or [] if tuple(o) not in eski] + [[p["a"], p["b"]] for p in parcalar]
    return kimlik


def yol_sil(mekan: dict, a: str, b: str) -> None:
    mekan["baglantilar"] = [y for y in mekan["baglantilar"] if {y["a"], y["b"]} != {a, b}]


def modul_turu(mekan: dict, plan: dict, kimlik: str) -> str:
    """Kayıtlı tür; yoksa adından ya da hedef olup olmamasından tahmin."""
    tur = (plan.get("tur") or {}).get(kimlik)
    if tur:
        return tur
    if kimlik in (plan.get("ust") or {}).values():
        return "bina"
    ad = next((n["ad"] for n in mekan["noktalar"] if n["id"] == kimlik), "").lower()
    for anahtar, sozler in (("asansor", ("asansör",)), ("merdiven", ("merdiven",)), ("wc", ("tuvalet", "wc")),
                            ("danisma", ("danışma",)), ("kavsak", ("kavşak", "koridor", "giriş"))):
        if any(s in ad for s in sozler):
            return anahtar
    return "oda" if any(h["nokta"] == kimlik for h in mekan["hedefler"]) else "kavsak"


# ── Çizim bileşeni (Streamlit özel bileşeni, CCv2) ────────

_HTML = """
<div class="cizim">
  <div class="arac">
    <button type="button" class="bagla" aria-pressed="false" title="İki modüle sırayla tıklayın">Bağla</button>
    <button type="button" class="yakin" title="Yakınlaştır" aria-label="Yakınlaştır">+</button>
    <button type="button" class="uzak" title="Uzaklaştır" aria-label="Uzaklaştır">−</button>
    <button type="button" class="sigdir" title="Tüm çizimi ekrana sığdır">Sığdır</button>
    <button type="button" class="zemin-sec" title="Arka plan: harita, uydu ya da boş" hidden>Zemin: Harita</button>
    <button type="button" class="ekle" aria-pressed="false"
      title="Açıkken çizimde boş bir yere tıklayınca oraya yeni yer eklenir ve seçili yere yolla bağlanır">➕ Tıklayarak ekle</button>
    <button type="button" class="buradayim" hidden
      title="Sahadaysanız: telefonunuzun konumunu seçili noktaya yazar">📍 Buradayım</button>
    <input class="ara" type="search" placeholder="Haritada ara: kurum, adres" aria-label="Haritada ara" hidden>
  </div>
  <div class="ipucu" aria-live="polite"></div>
  <div class="tuval">
    <svg role="application" aria-label="Bina çizimi" tabindex="-1"></svg>
    <span class="atif" hidden></span>
  </div>
</div>
"""

_CSS = """
.cizim { font-family: var(--st-font); color: var(--st-text-color); }
.arac { display: flex; gap: .5rem; align-items: center; margin-bottom: .5rem; flex-wrap: wrap; }
.arac button { font: inherit; padding: .3rem .8rem; border-radius: var(--st-button-radius, .5rem);
  border: 1px solid var(--st-border-color); background: var(--st-background-color); color: inherit;
  cursor: pointer; }
.arac button[aria-pressed="true"] { background: var(--st-primary-color); color: #fff;
  border-color: var(--st-primary-color); }
.ipucu { font-size: .875rem; opacity: .75; margin-bottom: .4rem; min-height: 1.2em; }
.arac input { font: inherit; padding: .3rem .6rem; flex: 1 1 12rem; min-width: 10rem;
  border-radius: var(--st-button-radius, .5rem); border: 1px solid var(--st-border-color);
  background: var(--st-background-color); color: inherit; }
svg.ekleniyor { cursor: crosshair; }
.tuval { position: relative; }
.atif { position: absolute; right: 4px; bottom: 3px; font-size: 11px; padding: 0 4px; border-radius: 3px;
  background: rgba(255, 255, 255, .8); color: #333; pointer-events: none; }
svg { width: 100%; height: 540px; display: block; touch-action: pan-y; user-select: none;
  background-color: var(--st-secondary-background-color); border-radius: var(--st-base-radius, .5rem);
  border: 1px solid var(--st-border-color); cursor: grab; }
svg.suruk { cursor: grabbing; }
.yol { stroke: var(--st-text-color); opacity: .45; }
.yol.dikey { stroke-dasharray: 4 4; }
.yol.secili { stroke: var(--st-primary-color); opacity: 1; }
.yolvurus { stroke: transparent; cursor: pointer; }
.adim { fill: var(--st-primary-color); font-weight: 600; paint-order: stroke; cursor: pointer;
  stroke: var(--st-secondary-background-color); text-anchor: middle; dominant-baseline: central; }
.adim:hover { text-decoration: underline; }
.modul { cursor: pointer; touch-action: none; }
.ic-ac { cursor: pointer; }
.modul rect { fill: var(--st-background-color); stroke: var(--st-border-color); }
.modul.hedef rect { stroke: var(--st-text-color); }
.modul.bina rect { fill: var(--st-primary-color); fill-opacity: .14; stroke: var(--st-primary-color); }
.modul.giris rect { stroke: var(--st-green-color, #21c354); }
.modul.secili rect, .modul:focus rect { stroke: var(--st-primary-color); }
.modul.kaynak rect { stroke: var(--st-primary-color); stroke-dasharray: 3 2; }
.modul:focus { outline: none; }
.modul text { fill: var(--st-text-color); dominant-baseline: central; }
/* Harita zemininde: kutu yerine haritadaki gibi nokta ve hâlesi olan ad; renkler temadan bağımsız */
svg.haritali .modul circle { fill: #fff; stroke: #1c3d6e; }
svg.haritali .modul.bina circle { fill: #1c62b9; stroke: #fff; }
svg.haritali .modul.giris circle { fill: #21c354; stroke: #fff; }
svg.haritali .modul.secili circle, svg.haritali .modul:focus circle { stroke: #ff4b4b; }
svg.haritali .modul text { fill: #111; paint-order: stroke; stroke: rgba(255, 255, 255, .9); stroke-linejoin: round; }
svg.haritali .ic-ac text { stroke: none; fill: #fff; }
svg.haritali .yol { stroke: #1c3d6e; opacity: .8; }
svg.haritali .yol.secili { stroke: #ff4b4b; }
svg.haritali .adim { fill: #1c3d6e; stroke: rgba(255, 255, 255, .9); }
"""

_JS = """
const durumlar = new WeakMap()
const NS = "http://www.w3.org/2000/svg"
const SIMGE = {bina: "▣", oda: "□", kavsak: "◇", danisma: "ⓘ", wc: "◫", asansor: "⇅", merdiven: "≡"}

function el(ad, ozellik, ust) {
  const e = document.createElementNS(NS, ad)
  for (const [k, v] of Object.entries(ozellik)) e.setAttribute(k, v)
  if (ust) ust.appendChild(e)
  return e
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const svg = parentElement.querySelector("svg")
  const baglaBtn = parentElement.querySelector(".bagla")
  const sigdirBtn = parentElement.querySelector(".sigdir")
  const ipucu = parentElement.querySelector(".ipucu")
  if (!svg) return

  let d = durumlar.get(parentElement)
  if (!d) {
    d = { vb: null, gorunum: null, bagla: false, kaynak: null, zemin: null, karolar: new Map(), zeminTuru: 0, ekle: false }
    durumlar.set(parentElement, d)
  }
  const dugumler = (data.dugumler || []).map(n => ({ ...n }))
  const yollar = data.yollar || []
  const bul = id => dugumler.find(n => n.id === id)

  function sigdir() {
    if (!dugumler.length) { d.vb = { x: -20, y: -15, w: 40, h: 30 }; return }
    const xs = dugumler.map(n => n.x), ys = dugumler.map(n => n.y)
    const kenar = 8
    let x0 = Math.min(...xs) - kenar, x1 = Math.max(...xs) + kenar
    let y0 = Math.min(...ys) - kenar, y1 = Math.max(...ys) + kenar
    const oran = (svg.clientWidth || 800) / (svg.clientHeight || 540)
    let w = x1 - x0, h = y1 - y0
    if (w / h < oran) { const yw = h * oran; x0 -= (yw - w) / 2; w = yw } else { const yh = w / oran; y0 -= (yh - h) / 2; h = yh }
    d.vb = { x: x0, y: y0, w, h }
  }
  // Başka çizime geçilince ya da görüş alanı dışına yeni modül eklenince çizim yeniden sığdırılır
  const idler = dugumler.map(n => n.id).join("|")
  if (d.gorunum !== data.gorunum) { d.gorunum = data.gorunum; d.vb = null }
  else if (d.vb && d.idler !== idler && dugumler.some(n => n.x < d.vb.x || n.x > d.vb.x + d.vb.w ||
                                                           n.y < d.vb.y || n.y > d.vb.y + d.vb.h)) d.vb = null
  d.idler = idler

  // ── Harita zemini: çizim haritaya oturtulduysa (data.harita) OpenStreetMap ya da uydu karoları çizimin
  // birimlerine çevrilip arkaya döşenir. Kampüs ölçeğinde Mercator karosu ile düz metre ızgarası örtüşür.
  const ZEMINLER = [
    { ad: "Harita", url: (z, x, y) => `https://tile.openstreetmap.org/${z}/${x}/${y}.png`, atif: "© OpenStreetMap katkıcıları" },
    { ad: "Uydu", url: (z, x, y) => `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${y}/${x}`,
      atif: "Uydu: Esri, Maxar, Earthstar Geographics" },
    { ad: "Yok" },
  ]
  const zeminBtn = parentElement.querySelector(".zemin-sec")
  const atif = parentElement.querySelector(".atif")
  const H = data.harita
  zeminBtn.hidden = !H
  if (!d.zemin) d.zemin = document.createElementNS(NS, "g")

  function zeminCiz() {
    const tur = ZEMINLER[d.zeminTuru]
    zeminBtn.textContent = "Zemin: " + tur.ad
    atif.hidden = !H || !tur.url
    if (!H || !tur.url) { d.zemin.replaceChildren(); d.karolar.clear(); return }
    atif.textContent = tur.atif
    const { x, y, w, h } = d.vb
    const m = H.m, kx = 111320 * Math.cos(H.enlem * Math.PI / 180), ky = 110540
    const metrePiksel = w * m / (svg.clientWidth || 800)
    const z = Math.max(3, Math.min(19, Math.round(Math.log2(156543.03 * Math.cos(H.enlem * Math.PI / 180) / metrePiksel))))
    const n2 = 2 ** z
    const boylam = X => H.boylam + X * m / kx, enlem = Y => H.enlem - Y * m / ky
    const kX = lon => Math.floor((lon + 180) / 360 * n2)
    const kY = lat => { const r = lat * Math.PI / 180; return Math.floor((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * n2) }
    const karoBoylam = i => i / n2 * 360 - 180
    const karoEnlem = j => 180 / Math.PI * Math.atan(Math.sinh(Math.PI - 2 * Math.PI * j / n2))
    const X = lon => (lon - H.boylam) * kx / m, Y = lat => -(lat - H.enlem) * ky / m
    const x0 = kX(boylam(x)), x1 = kX(boylam(x + w)), y0 = kY(enlem(y)), y1 = kY(enlem(y + h))
    if ((x1 - x0 + 1) * (y1 - y0 + 1) > 120) return
    const istenen = new Set()
    for (let i = x0; i <= x1; i++) for (let j = y0; j <= y1; j++) {
      const anahtar = `${d.zeminTuru}/${z}/${i}/${j}`
      istenen.add(anahtar)
      if (d.karolar.has(anahtar)) continue
      const sx = X(karoBoylam(i)), sy = Y(karoEnlem(j))
      d.karolar.set(anahtar, el("image", { href: tur.url(z, i, j), x: sx, y: sy, width: X(karoBoylam(i + 1)) - sx,
        height: Y(karoEnlem(j + 1)) - sy, preserveAspectRatio: "none" }, d.zemin))
    }
    for (const [anahtar, resim] of d.karolar) if (!istenen.has(anahtar)) { resim.remove(); d.karolar.delete(anahtar) }
  }
  zeminBtn.onclick = () => { d.zeminTuru = (d.zeminTuru + 1) % ZEMINLER.length; ciz() }

  // ── Haritada ara ve Buradayım (yalnızca dış çizimde) ──
  const araKutu = parentElement.querySelector(".ara")
  const buradaBtn = parentElement.querySelector(".buradayim")
  const ekleBtn = parentElement.querySelector(".ekle")
  const disCizim = !data.ankraj
  araKutu.hidden = buradaBtn.hidden = !disCizim
  araKutu.onkeydown = e => {
    if (e.key !== "Enter" || !araKutu.value.trim()) return
    e.preventDefault()
    ipucu.textContent = "Aranıyor…"
    fetch("https://nominatim.openstreetmap.org/search?format=json&limit=1&accept-language=tr&q=" +
          encodeURIComponent(araKutu.value.trim()))
      .then(r => r.json())
      .then(s => {
        if (!s.length) { ipucu.textContent = "Bulunamadı; il ya da ilçe adını ekleyerek deneyin."; return }
        const enlem = +s[0].lat, boylam = +s[0].lon
        if (H) {
          // Çizim haritadaysa görünüm oraya kayar (yaklaşık 500 m genişlik)
          const kx = 111320 * Math.cos(H.enlem * Math.PI / 180)
          const X = (boylam - H.boylam) * kx / H.m, Y = -(enlem - H.enlem) * 110540 / H.m
          const w = 500 / H.m, h = w * (svg.clientHeight || 540) / (svg.clientWidth || 800)
          d.vb = { x: X - w / 2, y: Y - h / 2, w, h }
          ciz()
          ipucu.textContent = s[0].display_name.split(",").slice(0, 2).join(",")
        } else {
          // Çizim henüz haritada değil: bulunan yere konur, arkasında harita görünür
          setTriggerValue("olay", { tur: "merkez", enlem, boylam })
        }
      })
      .catch(() => { ipucu.textContent = "Arama yapılamadı (internet bağlantısını kontrol edin)." })
  }
  buradaBtn.onclick = () => {
    if (!data.secili) { ipucu.textContent = "Önce yanında durduğunuz noktayı seçin."; return }
    if (!navigator.geolocation) { ipucu.textContent = "Bu tarayıcı konum vermiyor."; return }
    ipucu.textContent = "Konum alınıyor…"
    navigator.geolocation.getCurrentPosition(
      p => setTriggerValue("olay", { tur: "buradayim", id: data.secili, enlem: p.coords.latitude,
                                     boylam: p.coords.longitude, dogruluk: p.coords.accuracy }),
      h => { ipucu.textContent = "Konum alınamadı: " + (h.code === 1 ? "izin verilmedi." : h.message) },
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 })
  }
  ekleBtn.onclick = () => { d.ekle = !d.ekle; if (d.ekle) { d.bagla = false; d.kaynak = null } ciz() }

  function ciz() {
    if (!d.vb) sigdir()
    const { x, y, w, h } = d.vb
    svg.setAttribute("viewBox", `${x} ${y} ${w} ${h}`)
    const k = (svg.clientWidth || 800) / w       // piksel / birim
    const px = p => p / k
    svg.classList.toggle("haritali", !!H && !!ZEMINLER[d.zeminTuru].url)
    svg.replaceChildren(d.zemin)
    zeminCiz()
    const katman = el("g", {}, svg)
    for (const yol of yollar) {
      const a = bul(yol.a), b = bul(yol.b)
      if (!a || !b) continue
      const secili = data.seciliYol && data.seciliYol[0] === yol.a && data.seciliYol[1] === yol.b
      el("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: "yol" + (yol.dikey ? " dikey" : "") + (secili ? " secili" : ""),
        "stroke-width": px(secili ? 3 : 2) }, katman)
      const vurus = el("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: "yolvurus", "stroke-width": px(14) }, katman)
      // Yolun kendisi ve üstündeki mesafe yazısı tıklanınca yol seçilir (mesafe girilir). Basış arka plana
      // geçmesin: yoksa kaydırma işleyicisi tıklamayı "boşluğa tıklandı" sayıp seçimi kaldırıyordu.
      const yoluSec = e => { e.stopPropagation(); setTriggerValue("olay", { tur: "secyol", a: yol.a, b: yol.b }) }
      vurus.onpointerdown = e => e.stopPropagation()
      vurus.onclick = yoluSec
      // Haritada kısa yolların mesafe yazısı üst üste biner: seçili değilse gösterilmez (yola tıklayınca görünür)
      if (svg.classList.contains("haritali") && !secili && Math.hypot(b.x - a.x, b.y - a.y) * k < 55) continue

      const t = el("text", { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, class: "adim", "font-size": px(13),
        "stroke-width": px(5), role: "button", tabindex: 0,
        "aria-label": `${yol.etiket}. Mesafeyi değiştirmek için seçin` }, katman)
      t.textContent = yol.etiket
      t.onpointerdown = e => e.stopPropagation()
      t.onclick = yoluSec
      t.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); yoluSec(e) } }
    }
    for (const n of dugumler) {
      const sinif = ["modul", n.tur, n.hedef ? "hedef" : "", n.giris ? "giris" : "",
        n.id === data.secili ? "secili" : "", n.id === d.kaynak ? "kaynak" : ""].join(" ")
      const g = el("g", { class: sinif, transform: `translate(${n.x} ${n.y})`, tabindex: 0, role: "button",
        "aria-label": `${n.ad}${n.icerik ? `, içinde ${n.icerik} oda` : ""}`, "data-id": n.id }, katman)
      const haritali = svg.classList.contains("haritali")
      const yazi = haritali ? n.ad + (n.icerik ? ` (${n.icerik})` : "")
        : (SIMGE[n.tur] || "") + " " + n.ad + (n.icerik ? ` (${n.icerik})` : "")
      let gen = px(Math.max(70, yazi.length * 7.2 + 20))
      if (haritali) {
        // Haritada kutu yolu ve binayı örter: noktanın kendisi küçük bir daire, adı yanında
        const r = px(n.tur === "bina" ? 8 : 6)
        el("circle", { r, "stroke-width": px(n.id === data.secili ? 3.5 : 2) }, g)
        // Haritada yalnızca ziyaretçinin gideceği yerlerin, girişin ve seçili noktanın adı yazılır; kavşak ve
        // dönemeçlerin adı üstüne gelince görünür (kalabalık olmasın)
        if (!(n.hedef || n.giris || n.tur === "bina" || n.id === data.secili)) {
          el("title", {}, g).textContent = yazi
          g.onpointerdown = e => surukBasla(e, n)
          g.onkeydown = e => tus(e, n)
          continue
        }
        const t = el("text", { x: r + px(4), y: 0, "font-size": px(12.5), "text-anchor": "start",
          "font-weight": n.tur === "bina" ? 600 : 500, "stroke-width": px(3.5) }, g)
        t.textContent = yazi
        // "İçi ›" adın hemen sağında dursun: yazının gerçek genişliği (çizim biriminde) ölçülür
        let yaziGen = px(yazi.length * 6.8)
        try { yaziGen = t.getComputedTextLength() || yaziGen } catch (e) {}
        gen = 2 * (r + px(4) + yaziGen)
      } else {
        const yuk = px(n.tur === "bina" ? 40 : 28)
        el("rect", { x: -gen / 2, y: -yuk / 2, width: gen, height: yuk, rx: px(n.tur === "bina" ? 6 : 14),
          "stroke-width": px(n.id === data.secili ? 3 : 1.5) }, g)
        const t = el("text", { x: 0, y: 0, "font-size": px(13), "text-anchor": "middle",
          "font-weight": n.tur === "bina" ? 600 : 400 }, g)
        t.textContent = yazi
      }
      // Binanın içine girmek için kutunun sağında görünür bir düğme (çift tıklama keşfedilmiyor ve yeniden
      // çizimde kayboluyor)
      if (n.tur === "bina" && n.id !== data.ankraj) {
        const dg = px(44), dy = px(24)
        const ac = el("g", { class: "ic-ac", transform: `translate(${gen / 2 + px(6)} ${-dy / 2})`, role: "button",
          tabindex: 0, "aria-label": `${n.ad} içini aç` }, g)
        // Satır içi stil: bina kutusunun kuralları (yarı saydam dolgu, çerçeve) düğmeye geçmesin
        el("rect", { x: 0, y: 0, width: dg, height: dy, rx: px(12),
          style: "fill: var(--st-primary-color); fill-opacity: 1; stroke: none" }, ac)
        const at = el("text", { x: dg / 2, y: dy / 2, "font-size": px(12), "text-anchor": "middle",
          style: "fill: #fff; font-weight: 600" }, ac)
        at.textContent = "İçi ›"
        ac.onpointerdown = e => e.stopPropagation()
        ac.onclick = e => { e.stopPropagation(); setTriggerValue("olay", { tur: "ac", id: n.id }) }
        ac.onkeydown = e => {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setTriggerValue("olay", { tur: "ac", id: n.id }) }
        }
      }
      g.onpointerdown = e => surukBasla(e, n)
      g.onkeydown = e => tus(e, n)
    }
    baglaBtn.setAttribute("aria-pressed", String(d.bagla))
    ekleBtn.setAttribute("aria-pressed", String(d.ekle))
    svg.classList.toggle("ekleniyor", d.ekle)
    const seciliAd = data.secili && bul(data.secili)?.ad
    ipucu.textContent = d.ekle
      ? `Boş bir yere tıklayın: yeni yer oraya eklenir${seciliAd ? ` ve ${seciliAd} ile yolla bağlanır` : ""}. Bitince düğmeyi kapatın.`
      : d.bagla
      ? (d.kaynak ? `${bul(d.kaynak)?.ad ?? ""} seçildi; bağlanacak ikinci modüle tıklayın.` : "Bağlanacak ilk modüle tıklayın.")
      : "Kutuya tıklayın: ayarları açılır. Mesafe yazısına (ör. 12 m) tıklayın: mesafeyi girin. Yola çift tıklayın: " +
        "oraya kavşak / köşe eklenir. İçi › : binanın içi."
  }

  function svgNokta(e) {
    const p = svg.createSVGPoint()
    p.x = e.clientX; p.y = e.clientY
    return p.matrixTransform(svg.getScreenCTM().inverse())
  }

  function surukBasla(e, n) {
    e.stopPropagation()
    const bas = svgNokta(e), ilk = { x: n.x, y: n.y }
    let oynadi = false
    svg.setPointerCapture(e.pointerId)
    svg.classList.add("suruk")
    svg.onpointermove = m => {
      const p = svgNokta(m)
      const dx = p.x - bas.x, dy = p.y - bas.y
      if (!oynadi && Math.hypot(dx, dy) * ((svg.clientWidth || 800) / d.vb.w) < 4) return
      oynadi = true
      n.x = Math.round((ilk.x + dx) * 2) / 2
      n.y = Math.round((ilk.y + dy) * 2) / 2
      ciz()
    }
    svg.onpointerup = () => {
      svg.onpointermove = null; svg.onpointerup = null
      svg.classList.remove("suruk")
      if (oynadi) { setTriggerValue("olay", { tur: "tasi", id: n.id, x: n.x, y: n.y }); return }
      tikla(n)
    }
  }

  function tikla(n) {
    if (d.bagla) {
      if (!d.kaynak) { d.kaynak = n.id; ciz(); return }
      const a = d.kaynak
      d.kaynak = null
      if (a !== n.id) setTriggerValue("olay", { tur: "bagla", a, b: n.id })
      ciz()
      return
    }
    setTriggerValue("olay", { tur: "sec", id: n.id })
  }

  // Klavye: oklar modülü 1 kare (Shift ile 5) taşır, Enter seçer
  let tusZaman = null
  function tus(e, n) {
    const adim = e.shiftKey ? 5 : 1
    const yon = { ArrowLeft: [-adim, 0], ArrowRight: [adim, 0], ArrowUp: [0, -adim], ArrowDown: [0, adim] }[e.key]
    if (yon) {
      e.preventDefault()
      n.x += yon[0]; n.y += yon[1]
      ciz()
      svg.querySelector(`[data-id="${CSS.escape(n.id)}"]`)?.focus({ preventScroll: true })
      clearTimeout(tusZaman)
      tusZaman = setTimeout(() => setTriggerValue("olay", { tur: "tasi", id: n.id, x: n.x, y: n.y }), 500)
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault()
      tikla(n)
    }
  }

  svg.onpointerdown = e => {
    if (e.target !== svg && e.target.closest(".modul")) return
    const bas = { x: e.clientX, y: e.clientY }, vb0 = { ...d.vb }, yer = svgNokta(e)
    let oynadi = false
    svg.setPointerCapture(e.pointerId)
    svg.onpointermove = m => {
      const k = (svg.clientWidth || 800) / d.vb.w
      const dx = (m.clientX - bas.x) / k, dy = (m.clientY - bas.y) / k
      if (Math.hypot(dx, dy) * k > 3) oynadi = true
      d.vb = { ...vb0, x: vb0.x - dx, y: vb0.y - dy }
      ciz()
    }
    svg.onpointerup = () => {
      svg.onpointermove = null; svg.onpointerup = null
      if (oynadi) return
      if (d.ekle) setTriggerValue("olay", { tur: "ekle", x: yer.x, y: yer.y })
      else if (data.secili || data.seciliYol) setTriggerValue("olay", { tur: "bos" })
    }
  }
  // Yola çift tıklama: tıklanan yere en yakın yolun o yerine kavşak / köşe noktası (sonra köşeye sürüklenir).
  // Çizim alanında yakalanır: ilk tıklamalar yolu seçip çizimi yeniden kurunca hedef öğe değişebiliyor
  svg.ondblclick = e => {
    if (e.target.closest && e.target.closest(".modul")) return
    const p = svgNokta(e), esik = 12 * d.vb.w / (svg.clientWidth || 800)
    let en = null
    for (const yol of yollar) {
      const a = bul(yol.a), b = bul(yol.b)
      if (!a || !b || yol.dikey) continue
      const dx = b.x - a.x, dy = b.y - a.y
      const u = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy || 1)))
      const uz = Math.hypot(a.x + u * dx - p.x, a.y + u * dy - p.y)
      if (uz < esik && (!en || uz < en.uz)) en = { uz, yol }
    }
    if (en) setTriggerValue("olay", { tur: "bol", a: en.yol.a, b: en.yol.b, x: p.x, y: p.y })
  }
  // Tekerlek sayfayı kaydırır (çizim üstünde kalınca sayfa takılmasın); yakınlaştırma Ctrl + tekerlek ya da
  // + / − düğmeleriyle
  function yakinlas(f, merkez) {
    const p = merkez || { x: d.vb.x + d.vb.w / 2, y: d.vb.y + d.vb.h / 2 }
    d.vb = { x: p.x - (p.x - d.vb.x) * f, y: p.y - (p.y - d.vb.y) * f, w: d.vb.w * f, h: d.vb.h * f }
    ciz()
  }
  svg.onwheel = e => {
    if (!e.ctrlKey && !e.metaKey) return
    e.preventDefault()
    yakinlas(e.deltaY > 0 ? 1.15 : 1 / 1.15, svgNokta(e))
  }
  parentElement.querySelector(".yakin").onclick = () => yakinlas(1 / 1.3)
  parentElement.querySelector(".uzak").onclick = () => yakinlas(1.3)
  baglaBtn.onclick = () => { d.bagla = !d.bagla; d.kaynak = null; if (d.bagla) d.ekle = false; ciz() }
  sigdirBtn.onclick = () => { d.vb = null; ciz() }

  ciz()
}
"""

_CIZIM = st.components.v2.component("bak_cizim", html=_HTML, css=_CSS, js=_JS)


def cizim(veri: dict, *, key: str, on_olay: Callable[[], None]):
    """Çizim bileşeni. veri: dugumler, yollar, secili, seciliYol, olcek, gorunum; haritaya oturtulmuş dış çizimde
    harita {enlem, boylam, m} (m: bir birimin metresi). Olaylar on_olay ile gelir."""
    return _CIZIM(data=veri, key=key, on_olay_change=on_olay)
