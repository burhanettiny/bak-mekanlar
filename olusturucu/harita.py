"""Açık alandaki noktaların harita konumu (isteğe bağlı) ve çizimin haritaya oturtulması.

Kampüs gibi açık alanlarda noktaların gerçek konumu bilinirse ziyaretçi QR okutmadan "neredeyim" diyebilir:
telefon GPS'le en yakın noktayı söyler. Harita ayrı bir bileşen değildir: çizimin arka planıdır (cizim.py). Kurum
çizimin üstündeki kutuda kurumunu arar, çizim bulunan yere konur (cizimi_yere_koy) ve noktaları sürükleyerek
gerçek yerlerine taşır; ya da iki noktanın konumunu yazar, çizimin tamamı döndürülüp ölçeklenerek oturtulur. Bundan sonra
çizim gerçek ölçekte, kuzey yukarıdadır, arkasında harita görünür ve her noktanın harita konumu çizimdeki yerinden
hesaplanır (bkz. cizim.dis_gps): haritada taşınan nokta çizimde de taşınmış olur.
OpenStreetMap'ten kurulan kampüsler (osm_kampus.py) baştan haritaya oturtulmuş gelir.
"""
import math

import streamlit as st

import bak_mekan as bm
import cizim as cz


def haritaya_oturt(mekan: dict, plan: dict) -> float:
    """Elle yerleştirilmiş (plan["gps"], en az iki) dış noktalara göre dış çizimi haritaya oturtur: döndürme +
    ölçek + kaydırma (en küçük kareler). Yerleştirilen noktalar tam haritadaki yerlerine konur, diğerleri çizimdeki
    düzenleriyle taşınır; yürüme yollarının adımı gerçek mesafeden yeniden hesaplanır (sahada sayılıp elle yazılanlar
    korunur). Döner: yerleştirilen noktalarda çizimin haritaya en kötü uyumu (metre); kötüyse çizim ölçekli
    değildir ve kurum diğer noktaları da haritada düzeltmelidir. İkiden az nokta varsa bir şey yapmaz (-1)."""
    konum = cz.gorunum_konumlari(plan, None)
    gps = {i: k for i, k in cz.dis_gps({**plan, "harita": None}).items() if i in konum}
    if len(gps) < 2:
        return -1.0
    olc = cz.olcek(mekan, plan)
    plan["olcek"] = olc
    enlem0 = sum(k[0] for k in gps.values()) / len(gps)
    boylam0 = sum(k[1] for k in gps.values()) / len(gps)
    kx = cz._kx(enlem0)
    # Çizimde x doğu, y kuzey (bkz. cizim.pusula_yonu); haritada da doğu/kuzey metre. Karmaşık sayılarla
    # benzerlik dönüşümü: w = a·z + b (a döndürme ve ölçek, b kaydırma)
    z = {i: complex(*konum[i]) for i in gps}
    w = {i: complex((k[1] - boylam0) * kx, (k[0] - enlem0) * cz._KY) for i, k in gps.items()}
    zm, wm = sum(z.values()) / len(z), sum(w.values()) / len(w)
    payda = sum(abs(z[i] - zm) ** 2 for i in gps)
    if payda < 1e-9:   # yerleştirilen noktalar çizimde üst üste: döndürme bulunamaz
        return -1.0
    a = sum((w[i] - wm) * (z[i] - zm).conjugate() for i in gps) / payda
    b = wm - a * zm
    uyum = max(abs(a * z[i] + b - w[i]) for i in gps)
    m = cz.harita_birimi(plan)
    for i, p in konum.items():
        t = w[i] if i in gps else a * complex(*p) + b
        plan.setdefault("konum", {})[i] = [round(t.real / m, 2), round(t.imag / m, 2)]
    plan["harita"] = {"enlem": round(enlem0, 6), "boylam": round(boylam0, 6)}
    plan.pop("gps", None)
    adimlari_yenile(mekan, plan)
    return uyum


def adimlari_yenile(mekan: dict, plan: dict) -> None:
    """Dış çizimdeki yürüme yollarının adımı çizimdeki (artık gerçek) mesafeden; elle yazılanlar korunur."""
    konum = cz.gorunum_konumlari(plan, None)
    sabit = {tuple(y) for y in plan.get("sabitAdim") or []}
    olc = cz.olcek(mekan, plan)
    for y in mekan["baglantilar"]:
        if (y["a"], y["b"]) in sabit or (y.get("tur") or "yuru") in bm.DIKEY_GECISLER:
            continue
        if y["a"] in konum and y["b"] in konum and math.dist(konum[y["a"]], konum[y["b"]]) > 0.01:
            y["adim"] = max(1, round(math.dist(konum[y["a"]], konum[y["b"]]) * olc))


def cizimi_yere_koy(mekan: dict, plan: dict, enlem: float, boylam: float) -> None:
    """Haritada aranan yer: henüz haritada olmayan çizimin ortası oraya konur, ölçeği korunur (bir birim olcek ×
    0,7 m), kuzey yukarı kabul edilir. Arkasında harita görünür; kurum noktaları sürükleyerek gerçek yerlerine
    taşır. Boş çizimde ölçek kampüse uygun seçilir (bir birim 8 m)."""
    dis = cz.gorunum_konumlari(plan, None)
    dis_yol = any(y["a"] in dis and y["b"] in dis for y in mekan["baglantilar"])
    if len(dis) <= 1 and not dis_yol:
        plan["olcek"] = round(8 / bm.STANDART_ADIM_M, 4)
    else:
        plan["olcek"] = cz.olcek(mekan, plan)
    m = cz.harita_birimi(plan)
    cx = sum(p[0] for p in dis.values()) / len(dis) if dis else 0.0
    cy = sum(p[1] for p in dis.values()) / len(dis) if dis else 0.0
    plan["harita"] = {"enlem": round(enlem - cy * m / cz._KY, 6), "boylam": round(boylam - cx * m / cz._kx(enlem), 6)}
    plan.pop("gps", None)


def haritadan_kur_formu(anahtar: str, *, uyari: str | None = None) -> dict | None:
    """Kurum adıyla OpenStreetMap'te arama ve seçilen alanın kurulumu (Başla ve çizim sayfasında ortak). Kurulan
    düzen döner (kullanıcı "Bu alanı kur"a bastıysa ve kurulum başarılıysa); yoksa None."""
    import osm_kampus as ok
    with st.form(f"osm-ara-{anahtar}", border=False):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            sorgu = st.text_input("Kurumun adı", placeholder="ör. Ardahan Üniversitesi Yenisey Kampüsü",
                                  key=f"osm-sorgu-{anahtar}")
            aranacak = st.form_submit_button("Haritada ara", icon=":material/search:")
    aday_anahtari = f"osm_adaylar_{anahtar}"
    if aranacak and sorgu.strip():
        try:
            st.session_state[aday_anahtari] = ok.ara_onbellek(sorgu.strip())
        except Exception:
            st.session_state.pop(aday_anahtari, None)
            st.error("Haritada arama yapılamadı; internet bağlantısını kontrol edip biraz sonra yeniden deneyin.")
    adaylar = st.session_state.get(aday_anahtari)
    if adaylar == []:
        st.info("Bu adla haritada bir alan bulunamadı. İl ya da ilçe adını ekleyerek deneyin; bulunmazsa yerleri "
                "haritaya tıklayarak kendiniz ekleyin.", icon=":material/search_off:")
        return None
    if not adaylar:
        return None
    secim = st.radio("Hangisi?", range(len(adaylar)), format_func=lambda i: adaylar[i]["aciklama"],
                     key=f"osm-secim-{anahtar}")
    if uyari:
        st.caption(uyari)
    if not st.button("Bu alanı kur", type="primary", icon=":material/construction:", key=f"osm-kur-{anahtar}"):
        return None
    aday = adaylar[secim]
    with st.spinner("Binalar ve yollar haritadan alınıyor; bir dakika kadar sürebilir…"):
        try:
            kurulan = ok.kampus_kur(ok.veri_onbellek(aday["tur"], aday["kimlik"]), aday["kimlik"], aday["ad"])
        except ValueError as hata:
            st.error(f"{hata} Haritada bu alanda yeterli bilgi yok; yerleri haritaya tıklayarak kendiniz ekleyin.")
            return None
        except Exception:
            st.error("OpenStreetMap'e ulaşılamadı; biraz sonra yeniden deneyin.")
            return None
    st.session_state.pop(aday_anahtari, None)
    return kurulan
