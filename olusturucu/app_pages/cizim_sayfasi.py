import json
import math

import streamlit as st

import bak_mekan as bm
import cizim as cz
import durum

st.session_state.setdefault("cizim_gorunum", None)   # None: dış çizim; bir bina kimliği: o binanın içi
st.session_state.setdefault("cizim_secili", None)
st.session_state.setdefault("cizim_yol", None)
st.session_state.setdefault("cizim_kat", None)


def mekan_ve_plan() -> tuple[dict, dict, float]:
    mekan = durum.guncel_mekan()
    plan = json.loads(json.dumps(st.session_state.get("plan") or {}))
    olc = cz.olcek(mekan, plan)
    plan["olcek"] = olc
    plan["konum"] = cz.yerlesim(mekan, plan, olc)   # otomatik yerleşenler de sabitlenir, çizim kaymasın
    return mekan, plan, olc


def kaydet(mekan: dict, plan: dict) -> None:
    st.session_state.plan = plan
    durum.mekani_tablolara_yaz(mekan)


def olay_geldi() -> None:
    """Çizimden gelen olay (taşıma, seçme, bağlama); betik gövdesinden önce çalışır."""
    olay = st.session_state["cizim"].olay
    if not olay:
        return
    tur = olay.get("tur")
    if tur == "sec":
        st.session_state.cizim_secili, st.session_state.cizim_yol = olay["id"], None
    elif tur == "secyol":
        st.session_state.cizim_secili, st.session_state.cizim_yol = None, [olay["a"], olay["b"]]
    elif tur == "bos":
        st.session_state.cizim_secili = st.session_state.cizim_yol = None
    elif tur in ("tasi", "bagla"):
        mekan, plan, olc = mekan_ve_plan()
        if tur == "tasi":
            # Planda y kuzeye (yukarı) doğru artar, ekranda aşağı doğru: çizime giderken ve dönerken çevrilir
            gor = st.session_state.cizim_gorunum
            degisen = cz.tasi(mekan, plan, olay["id"], float(olay["x"]), -float(olay["y"]),
                              cz.gorunum_olcegi(plan, gor, olc), gor)
            adlar = {n["id"]: n["ad"] for n in mekan["noktalar"]}
            if degisen:
                st.toast("Adımlar çizimden yeniden hesaplandı: " + "; ".join(
                    f"{adlar[a]} – {adlar[b]}: {adim} adım" for a, b, adim in degisen[:4]), icon=":material/straighten:")
        elif cz.bagla(mekan, plan, olay["a"], olay["b"],
                      cz.gorunum_olcegi(plan, st.session_state.cizim_gorunum, olc), st.session_state.cizim_gorunum):
            st.session_state.cizim_secili, st.session_state.cizim_yol = None, [olay["a"], olay["b"]]
        kaydet(mekan, plan)


mekan, plan, olc = mekan_ve_plan()
adlar = {n["id"]: n["ad"] for n in mekan["noktalar"]}
gorunum = st.session_state.cizim_gorunum if st.session_state.cizim_gorunum in adlar else None
secili = st.session_state.cizim_secili if st.session_state.cizim_secili in adlar else None
ust = plan.get("ust") or {}

st.title("Çizim")
st.caption("Binanızı modül modül çizin: bina, oda, kavşak, danışma, tuvalet… Modülleri sürükleyerek yerleştirin; "
           "aradaki yolların adım sayısı çizimdeki mesafeden hesaplanır. Bir binaya tıklayıp **İçini aç** deyince "
           "odalarını eklersiniz. Yaptıklarınız Düzenle, Plan ve QR sayfalarına yansır.")

# ── Hangi çizim: dış çizim ya da bir binanın içi; birden çok katta kat seçimi ──
with st.container(horizontal=True, vertical_alignment="center"):
    if gorunum:
        if st.button("Dış çizime dön", icon=":material/arrow_back:"):
            st.session_state.cizim_gorunum, st.session_state.cizim_secili = None, gorunum
            st.rerun()
        st.subheader(f"{bm.liste_adi(next((h for h in mekan['hedefler'] if h['nokta'] == gorunum), {'ad': adlar[gorunum]}))} – içi")
    elif mekan.get("ad"):
        st.subheader(mekan["ad"])
    gorunen_katlar = sorted({n.get("kat") or 0 for n in mekan["noktalar"]
                             if (ust.get(n["id"]) == gorunum if gorunum else n["id"] not in ust)})
    kat = None
    if len(gorunen_katlar) > 1:
        varsayilan = st.session_state.cizim_kat if st.session_state.cizim_kat in gorunen_katlar else next(
            (n.get("kat") or 0 for n in mekan["noktalar"] if n["id"] == (gorunum or mekan.get("giris"))), 0)
        kat = st.segmented_control("Kat", gorunen_katlar, format_func=bm.kat_adi, required=True,
                                   default=varsayilan if varsayilan in gorunen_katlar else gorunen_katlar[0],
                                   key=f"cizim-kat-{gorunum}")
        st.session_state.cizim_kat = kat

gorunen = cz.gorunum_noktalari(mekan, plan, gorunum, kat)
if gorunum and kat is not None:
    gorunen = {i for i in gorunen if i == gorunum or next(
        (n.get("kat") or 0) == kat for n in mekan["noktalar"] if n["id"] == i)}
hedef_noktalari = {h["nokta"] for h in mekan["hedefler"]}
konum_g = cz.gorunum_konumlari(plan, gorunum)
olc_g = cz.gorunum_olcegi(plan, gorunum, olc)
icerik = {}
for i, u in ust.items():
    icerik[u] = icerik.get(u, 0) + 1
dugumler = [{"id": n["id"], "ad": n["ad"], "x": konum_g[n["id"]][0], "y": -konum_g[n["id"]][1],
             "tur": cz.modul_turu(mekan, plan, n["id"]), "hedef": n["id"] in hedef_noktalari,
             "giris": n["id"] == mekan.get("giris"), "icerik": icerik.get(n["id"], 0)}
            for n in mekan["noktalar"] if n["id"] in gorunen and n["id"] in konum_g]
yollar = []
for b in mekan["baglantilar"]:
    tur = b.get("tur") or "yuru"
    if tur in bm.DIKEY_GECISLER:
        # Başka kata giden asansör/merdiven: bu katta görünen ucun yanına kısa bir işaret olarak çizilmez
        continue
    if b["a"] in gorunen and b["b"] in gorunen:
        yollar.append({"a": b["a"], "b": b["b"], "adim": b.get("adim"), "dikey": False})

# ── Modül ekleme ──────────────────────────────────────────
with st.container(border=True):
    secenekler = [t for t in cz.MODULLER if not (gorunum and t == "bina")]
    with st.container(horizontal=True, vertical_alignment="bottom"):
        yeni_tur = st.segmented_control("Eklenecek modül", secenekler, required=True, default="oda" if gorunum else
                                        ("bina" if not mekan["noktalar"] else "oda"), key="cizim-yeni-tur",
                                        format_func=lambda t: cz.MODULLER[t][0])
    with st.form("cizim-ekle", clear_on_submit=True, border=False):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            yeni_ad = st.text_input("Adı", placeholder="ör. Mühendislik Fakültesi" if yeni_tur == "bina"
                                    else "ör. Kardiyoloji, Dekanlık, 112 nolu sınıf")
            # Seçili modül yoksa binanın girişine (bina içinde) ya da kurumun girişine bağlanır
            baglanacak = secili if secili in gorunen else gorunum or (
                mekan.get("giris") if mekan.get("giris") in gorunen else None)
            bagla_mi = st.checkbox(f"{adlar[baglanacak]} modülüne bağla" if baglanacak else "Bağlanacak modül yok",
                                   value=bool(baglanacak), disabled=not baglanacak)
            ekle = st.form_submit_button("Ekle", icon=":material/add:", type="primary")
    if ekle:
        if not mekan.get("ad"):
            st.toast("Önce Düzenle sayfasında kurumun adını yazın; modül yine eklendi.", icon=":material/info:")
        merkez = konum_g.get(baglanacak) if baglanacak else None
        if merkez is None:
            pts = [konum_g[i] for i in gorunen if i in konum_g]
            merkez = [sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)] if pts else [0, 0]
        uzak = cz.YENI_MESAFE / olc_g
        yer = None
        for aci in (0, 60, -60, 120, -120, 180, 30, -30, 90, -90, 150, -150):
            aday = [merkez[0] + uzak * math.cos(math.radians(aci)), merkez[1] + uzak * math.sin(math.radians(aci))]
            if all(math.dist(aday, konum_g[i]) > uzak * 0.6 for i in gorunen if i in konum_g):
                yer = aday
                break
        yer = yer or [merkez[0] + uzak, merkez[1] + uzak]
        kat_yeni = kat if kat is not None else next((n.get("kat") or 0 for n in mekan["noktalar"]
                                                     if n["id"] == (gorunum or baglanacak)), 0)
        kimlik = cz.modul_ekle(mekan, plan, yeni_tur, yeni_ad, yer=yer, ust=gorunum,
                               baglanacak=baglanacak if bagla_mi else None, olc=olc_g, kat=kat_yeni)
        st.session_state.cizim_secili, st.session_state.cizim_yol = kimlik, None
        kaydet(mekan, plan)
        st.rerun()

# ── Çizim ─────────────────────────────────────────────────
cz.cizim({"dugumler": dugumler, "yollar": yollar, "secili": secili, "seciliYol": st.session_state.cizim_yol,
          "olcek": round(olc_g, 2), "gorunum": f"{gorunum}-{kat}"}, key="cizim", on_olay=olay_geldi)
if not dugumler:
    st.info("Çizim boş. Yukarıdan ilk modülü ekleyin: kampüs için **Bina**, tek bina için önce bir **Kavşak / "
            "koridor** (giriş) ekleyip odaları ona bağlayın.", icon=":material/draw:")

# ── Seçili modül ya da yol ────────────────────────────────
if secili:
    hedef = next((h for h in mekan["hedefler"] if h["nokta"] == secili), None)
    nokta = next(n for n in mekan["noktalar"] if n["id"] == secili)
    tur = cz.modul_turu(mekan, plan, secili)
    with st.container(border=True):
        st.markdown(f"**{nokta['ad']}** · {cz.MODULLER.get(tur, ('Nokta',))[0]}"
                    + (" · giriş noktası" if secili == mekan.get("giris") else ""))
        with st.form(f"cizim-modul-{secili}", border=False):
            with st.container(horizontal=True):
                nokta_ad = st.text_input("Nokta adı (etikette ve yol tarifinde)", nokta["ad"])
                yeni_tur_sec = st.selectbox("Tür", list(cz.MODULLER), index=list(cz.MODULLER).index(tur)
                                            if tur in cz.MODULLER else 0, format_func=lambda t: cz.MODULLER[t][0])
            if hedef:
                with st.container(horizontal=True):
                    h_ad = st.text_input("Hedef adı", hedef["ad"])
                    h_kisa = st.text_input("Kısa ad", hedef.get("kisaAd", ""), help="Girişteki listede okunur")
                h_tarif = st.text_input("Varınca söylenecek", hedef.get("tarif", ""))
                h_anahtar = st.text_input("Anahtar kelimeler", ", ".join(hedef.get("anahtarlar", [])))
            else:
                hedef_yap = st.checkbox("Ziyaretçi burayı sorabilsin (hedef yap)")
            if st.form_submit_button("Kaydet", icon=":material/save:"):
                nokta["ad"] = nokta_ad.strip() or nokta["ad"]
                plan.setdefault("tur", {})[secili] = yeni_tur_sec
                if hedef:
                    hedef.update(ad=h_ad.strip() or hedef["ad"], tarif=h_tarif.strip(),
                                 anahtarlar=[a.strip() for a in h_anahtar.split(",") if a.strip()])
                    if h_kisa.strip():
                        hedef["kisaAd"] = h_kisa.strip()
                    else:
                        hedef.pop("kisaAd", None)
                elif hedef_yap:
                    mekan["hedefler"].append({"ad": nokta["ad"], "nokta": secili, "tarif": f"{nokta['ad']} burada.",
                                              "anahtarlar": [nokta["ad"].replace("I", "ı").replace("İ", "i").lower()]})
                kaydet(mekan, plan)
                st.rerun()
        with st.container(horizontal=True):
            if tur == "bina" and not gorunum:
                if st.button("İçini aç", icon=":material/door_open:", type="primary",
                             help="Bu binanın odalarını ayrı bir çizimde ekleyin"):
                    plan.setdefault("tur", {})[secili] = "bina"
                    st.session_state.plan = plan
                    st.session_state.cizim_gorunum, st.session_state.cizim_secili = secili, secili
                    st.rerun()
            if secili != mekan.get("giris") and st.button("Giriş noktası yap", icon=":material/login:",
                                                          help="Büyük giriş QR'ı bu noktaya asılır"):
                mekan["giris"] = secili
                kaydet(mekan, plan)
                st.rerun()
            sil_yazi = "Binayı ve odalarını sil" if icerik.get(secili) else "Sil"
            if st.button(sil_yazi, icon=":material/delete:"):
                cz.nokta_sil(mekan, plan, secili)
                st.session_state.cizim_secili = None
                if st.session_state.cizim_gorunum == secili:
                    st.session_state.cizim_gorunum = None
                kaydet(mekan, plan)
                st.rerun()
elif st.session_state.cizim_yol:
    a, b = st.session_state.cizim_yol
    yol = next((y for y in mekan["baglantilar"] if {y["a"], y["b"]} == {a, b}), None)
    if yol:
        sabit = set(map(tuple, plan.get("sabitAdim") or []))
        with st.container(border=True):
            st.markdown(f"**{adlar[yol['a']]} → {adlar[yol['b']]}**")
            with st.form(f"cizim-yol-{a}-{b}", border=False):
                with st.container(horizontal=True, vertical_alignment="bottom"):
                    adim = st.number_input("Adım", min_value=1, step=1, value=int(yol.get("adim") or 1),
                                           help="Çizimdeki mesafeden hesaplandı. Sahada sayınca yazın; o zaman "
                                                "modülü sürükleseniz de değişmez.")
                    tek_yon = st.checkbox("Tek yön", bool(yol.get("tekYon")))
                tarif = st.text_input(f"Gidiş tarifi ({adlar[yol['a']]} → {adlar[yol['b']]})", yol.get("tarif", ""))
                geri = st.text_input(f"Dönüş tarifi ({adlar[yol['b']]} → {adlar[yol['a']]})", yol.get("geriTarif", ""))
                if st.form_submit_button("Kaydet", icon=":material/save:"):
                    if adim != yol.get("adim"):
                        sabit.add((yol["a"], yol["b"]))
                        plan["sabitAdim"] = sorted(map(list, sabit))
                    yol.update(adim=int(adim), tarif=tarif.strip(), geriTarif=geri.strip())
                    if tek_yon:
                        yol["tekYon"] = True
                    else:
                        yol.pop("tekYon", None)
                    kaydet(mekan, plan)
                    st.rerun()
            if st.button("Yolu sil", icon=":material/delete:"):
                cz.yol_sil(mekan, a, b)
                st.session_state.cizim_yol = None
                kaydet(mekan, plan)
                st.rerun()

hatalar, _ = bm.dogrula(mekan)
with st.container(horizontal=True, vertical_alignment="center"):
    st.caption(f":material/error: {len(hatalar)} eksik var; ayrıntılar QR sayfasında." if hatalar
               else ":material/check_circle: Düzen geçerli.")
    st.page_link("app_pages/duzenle.py", label="Tablolarda düzenle", icon=":material/edit_note:")
    st.page_link("app_pages/yazdir.py", label="QR ve etiketler", icon=":material/qr_code_2:")
