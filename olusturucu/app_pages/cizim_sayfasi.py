import json
import math
import zlib

import streamlit as st

import bak_mekan as bm
import cizim as cz
import durum
import harita as hr

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
    # Taşınan, eklenen ya da silinen her şeyden sonra BAK'ın ürettiği tarifler (sağa/sola/düz) yeniden hesaplanır
    cz.tarifleri_guncelle(mekan, plan)
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
    elif tur == "ac":
        # Binanın içine gir: odaları ayrı çizimde
        plan = json.loads(json.dumps(st.session_state.get("plan") or {}))
        plan.setdefault("tur", {})[olay["id"]] = "bina"
        st.session_state.plan = plan
        st.session_state.cizim_gorunum, st.session_state.cizim_secili = olay["id"], None
        st.session_state.cizim_yol = None
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


def harita_olay() -> None:
    """Haritadan gelen olay: nokta seçme ya da seçili noktanın konumu (tıklama veya "Buradayım")."""
    olay = st.session_state["harita"].olay
    if not olay:
        return
    if olay.get("tur") == "sec":
        st.session_state.cizim_secili, st.session_state.cizim_yol = olay["id"], None
    elif olay.get("tur") == "konum" and olay.get("id"):
        plan = json.loads(json.dumps(st.session_state.get("plan") or {}))
        k = cz.gps_coz([olay["enlem"], olay["boylam"]])
        if k:
            plan.setdefault("gps", {})[olay["id"]] = list(k)
            plan["gpsTahmin"] = [i for i in plan.get("gpsTahmin") or [] if i != olay["id"]]
            st.session_state.plan = plan
            dogruluk = olay.get("dogruluk")
            if dogruluk and dogruluk > 25:
                st.toast(f"Telefonun konumu yaklaşık {round(dogruluk)} m hassas; açık havada tekrar deneyin ya da "
                         "haritada düzeltin.", icon=":material/gps_not_fixed:")


mekan, plan, olc = mekan_ve_plan()
adlar = {n["id"]: n["ad"] for n in mekan["noktalar"]}
gorunum = st.session_state.cizim_gorunum if st.session_state.cizim_gorunum in adlar else None
secili = st.session_state.cizim_secili if st.session_state.cizim_secili in adlar else None
ust = plan.get("ust") or {}

durum.adim_cubugu(2)
st.title("Kontrol et")
ornek = st.session_state.get("ornek_adi")
# Ad kutusu aşağıda; yazılan yeni ad bu çalıştırmada henüz bilgiye geçmemiş olabilir
ad_simdi = st.session_state.get(f"cizim-kurum-adi-{st.session_state.surum_anahtari}",
                                st.session_state.bilgi.get("ad"))
if ornek and (ad_simdi or "").strip() == ornek:
    st.info("**Bu bir örnek; size ait bir kopya olarak açıldı** (orijinal örnek değişmez). Kendi kurumunuz için "
            "kullanacaksanız aşağıdan adını, sonra yerleri ve mesafeleri kendi binanıza göre değiştirin.",
            icon=":material/content_copy:")
elif st.session_state.pop("yeni_olusturuldu", False):
    st.success("Düzeniniz hazır. Aşağıda kontrol edin: bir yere tıklayıp adını düzeltebilir, sürükleyip yerini "
               "değiştirebilir, yeni yer ekleyebilirsiniz. Her şey doğruysa **4. Yazdır** adımına geçin.",
               icon=":material/check_circle:")
else:
    st.caption("Bir kutuya tıklayınca altında ayarları açılır. Sürükleyince aradaki adım sayısı yeniden hesaplanır. "
               "Bir binanın içine girmek için kutusunun yanındaki **İçi ›** düğmesine basın.")

# Kampüs gibi sıfırdan çizilen düzende kurumun adı burada sorulur (sihirbaz kullanılmadı)
bilgi = st.session_state.bilgi
if not gorunum:
    yeni_ad = st.text_input("Kurumun adı", bilgi.get("ad") or "", placeholder="ör. Ardahan Üniversitesi Yenisey Kampüsü",
                            key=f"cizim-kurum-adi-{st.session_state.surum_anahtari}")
    if yeni_ad.strip() != (bilgi.get("ad") or ""):
        bilgi["ad"] = yeni_ad.strip()
        mekan["ad"] = bilgi["ad"]

# ── Hangi çizim: dış çizim ya da bir binanın içi; birden çok katta kat seçimi ──
with st.container(horizontal=True, vertical_alignment="center"):
    if gorunum:
        ust_gorunum = ust.get(gorunum)   # bina başka bir binanın içindeyse bir üst çizime dönülür
        if st.button(f"{adlar[ust_gorunum]} çizimine dön" if ust_gorunum else "Dış çizime dön",
                     icon=":material/arrow_back:"):
            st.session_state.cizim_gorunum, st.session_state.cizim_secili = ust_gorunum, gorunum
            st.rerun()
        st.subheader(f"{bm.liste_adi(next((h for h in mekan['hedefler'] if h['nokta'] == gorunum), {'ad': adlar[gorunum]}))} – içi")
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
    # Binanın girişi yalnızca kendi katında görünür; üst katlara merdiven/asansörle çıkılır
    gorunen = {i for i in gorunen if next((n.get("kat") or 0) == kat for n in mekan["noktalar"] if n["id"] == i)}
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
# Binanın içinde, binanın kendi kutusu dışarıyla bağlantı noktasıdır: "Bina girişi" olarak gösterilir
for d in dugumler:
    if d["id"] == gorunum:
        d.update(ad="Bina girişi", tur="kavsak", hedef=False, giris=True, icerik=0)
yollar = []
for b in mekan["baglantilar"]:
    tur = b.get("tur") or "yuru"
    if tur in bm.DIKEY_GECISLER:
        # Başka kata giden asansör/merdiven: bu katta görünen ucun yanına kısa bir işaret olarak çizilmez
        continue
    if b["a"] in gorunen and b["b"] in gorunen:
        yollar.append({"a": b["a"], "b": b["b"], "adim": b.get("adim"), "dikey": False,
                       "etiket": bm.mesafe_etiketi(b.get("adim"))})

# ── Boş binanın içini kat listesinden tek seferde kurma ──
if gorunum and not icerik.get(gorunum):
    with st.container(border=True):
        st.markdown("**Binanın içini hızlıca kurun.** Her kat için odaları yazın; koridor, sırayla sol ve sağ "
                    "kapılar, katlar arasında merdiven ve asansör kendiliğinden çizilir. Sonra sürükleyerek "
                    "düzeltir, tek tek oda eklersiniz.")
        with st.form("cizim-doldur", border=False):
            liste_metni = st.text_area(
                "Katlar ve odalar", height=130,
                placeholder="Zemin kat: Sekreterlik, Dekan odası, Toplantı salonu, WC\n"
                            "1. kat: 101, 102, 103, Öğretim üyesi odaları, WC")
            dikey_secim = st.segmented_control(
                "Katlar arası", ["ikisi", "merdiven", "asansor"], default="ikisi", required=True,
                format_func={"ikisi": "Merdiven ve asansör", "merdiven": "Yalnızca merdiven",
                             "asansor": "Yalnızca asansör"}.get)
            if st.form_submit_button("Odaları ekle", icon=":material/playlist_add:", type="primary"):
                eklenen = cz.binayi_doldur(mekan, plan, gorunum, liste_metni, dikey_secim)
                if eklenen:
                    kaydet(mekan, plan)
                    st.toast(f"{eklenen} oda eklendi. Adımları sahada sayıp düzeltin.", icon=":material/check:")
                    st.rerun()
                st.warning("Liste okunamadı. Her satıra bir kat yazın: \"Zemin kat: Sekreterlik, WC\".",
                           icon=":material/info:")

# ── Yer ekleme: çizim boşsa açık, değilse kapalı (önce kontrol, sonra ekleme) ──
with st.expander("Yer ekle", icon=":material/add_location_alt:", expanded=len(dugumler) <= 1):
    secenekler = [t for t in cz.MODULLER if not (gorunum and t == "bina")]
    with st.container(horizontal=True, vertical_alignment="bottom"):
        yeni_tur = st.segmented_control("Eklenecek modül", secenekler, required=True, default="oda" if gorunum else
                                        ("bina" if not mekan["noktalar"] else "oda"), key="cizim-yeni-tur",
                                        format_func=lambda t: cz.MODULLER[t][0])
    with st.form("cizim-ekle", clear_on_submit=True, border=False):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            yeni_ad = st.text_input("Adı (virgülle birden çok)",
                                    placeholder="ör. Mühendislik Fakültesi, Rektörlük" if yeni_tur == "bina"
                                    else "ör. Sekreterlik, Dekan odası, 101, 102, WC",
                                    help="Virgülle birden çok yer yazarsanız hepsi sırayla, koridor boyunca eklenir.")
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
        # "101, 102, 103": ilki seçili modülün yanına, sonrakiler aynı yönde birbirinin ardına (koridor boyunca)
        adlar_listesi = [a.strip() for a in yeni_ad.split(",") if a.strip()] or [""]
        onceki, kimlik = baglanacak if bagla_mi else None, None
        yon = (yer[0] - merkez[0], yer[1] - merkez[1])
        for i, ad in enumerate(adlar_listesi):
            if i:
                yer = [yer[0] + yon[0], yer[1] + yon[1]]
            kimlik = cz.modul_ekle(mekan, plan, yeni_tur, ad, yer=yer, ust=gorunum, baglanacak=onceki, olc=olc_g,
                                   kat=kat_yeni)
            onceki = kimlik   # sonraki yer bunun ardına bağlanır
        if len(adlar_listesi) > 1:
            st.toast(f"{len(adlar_listesi)} yer koridor boyunca sırayla eklendi.", icon=":material/check:")
        st.session_state.cizim_secili, st.session_state.cizim_yol = kimlik, None
        kaydet(mekan, plan)
        st.rerun()

# ── Çizim ─────────────────────────────────────────────────
cz.cizim({"dugumler": dugumler, "yollar": yollar, "secili": secili, "seciliYol": st.session_state.cizim_yol,
          "olcek": round(olc_g, 2), "ankraj": gorunum, "gorunum": f"{gorunum}-{kat}"}, key="cizim", on_olay=olay_geldi)
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
            # Açık alandaki noktalar (bina önü, kavşak) için: telefon "neredeyim"de GPS'ten en yakın noktayı söyler
            gps_eski = (plan.get("gps") or {}).get(secili)
            gps_metin = st.text_input(
                "Harita konumu (isteğe bağlı)", ", ".join(map(str, gps_eski)) if gps_eski else "",
                placeholder="ör. 41.130848, 42.786478",
                help="Yalnızca açık alandaki noktalar için. En kolayı aşağıdaki Harita konumu bölümünde haritaya tıklamak. "
                     "Ya da Google Haritalar'da noktaya sağ tıklayıp ilk satırdaki "
                     "sayıları kopyalayın. Ziyaretçi \"neredeyim\" deyince telefon GPS'le en yakın noktayı söyler.",
            ) if not gorunum else ""
            if st.form_submit_button("Kaydet", icon=":material/save:"):
                nokta["ad"] = nokta_ad.strip() or nokta["ad"]
                if not gorunum:
                    gps_k = cz.gps_coz(gps_metin)
                    if gps_metin.strip() and not gps_k:
                        st.warning("Harita konumu anlaşılamadı; \"enlem, boylam\" biçiminde yazın.")
                    elif gps_k:
                        plan.setdefault("gps", {})[secili] = list(gps_k)
                    else:
                        (plan.get("gps") or {}).pop(secili, None)
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
        # Nokta etiketi: ziyaretçi okutunca "neredeyim" ve yol tarifi buradan sürer. Her nokta için basılır;
        # gerekmeyen yerde (ör. yol ortasında) kapatılır. Yırtılan tek etiket buradan yeniden basılır.
        if secili != mekan.get("giris"):
            etiketsiz = set(plan.get("etiketsiz") or [])
            with st.container(horizontal=True, vertical_alignment="center"):
                asilacak = st.toggle("Buraya QR etiketi asılacak", value=secili not in etiketsiz,
                                     key=f"cizim-etiket-{secili}",
                                     help="Ziyaretçi bu etiketi okutunca nerede olduğunu duyar; yol tarifi buradan sürer. "
                                          "Koridor başı, asansör önü, merdiven başı ve oda kapıları için önerilir.")
                if asilacak == (secili in etiketsiz):
                    plan["etiketsiz"] = sorted(etiketsiz - {secili} if asilacak else etiketsiz | {secili})
                    st.session_state.plan = plan
                if asilacak and mekan.get("ad"):
                    st.download_button("Bu noktanın etiketini indir", bm.etiket_sayfasi(mekan, yalniz=secili),
                                       file_name=f"{mekan['id']}-{secili}-etiket.html", mime="text/html",
                                       icon=":material/qr_code_2:", key=f"cizim-tek-etiket-{secili}")
        with st.container(horizontal=True):
            if tur == "bina" and secili != gorunum:
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
            # Odalar bu noktaya ayrı ayrı bağlıysa (yıldız biçimi) gerçekteki gibi koridor boyunca sıraya dizilir
            dizilecek = cz.sirala_adaylari(mekan, plan, secili, gorunum)
            if dizilecek and st.button(
                    f"Bağlı {len(dizilecek)} odayı koridor gibi sırala", icon=":material/linear_scale:",
                    help="Odalara tek tek buradan gidiliyormuş gibi bağlı. Gerçekte koridor boyunca sırayla "
                         "varılır: en yakın oda, sonraki, … Sağ/sol çizimden bulunur."):
                n = cz.koridora_diz(mekan, plan, secili, olc_g, gorunum)
                kaydet(mekan, plan)
                st.toast(f"{n} oda koridor boyunca sıraya dizildi.", icon=":material/linear_scale:")
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
            with st.container():   # form değil: birim ve "≈ adım" önizlemesi yazarken güncellensin
                # Kurum mesafeyi metre olarak girer (adım kişiden kişiye değişir); isteyen adım sayısı da girebilir.
                # Düzende standart adım (70 cm) saklanır; uygulama ziyaretçinin kendi adımına çevirir.
                with st.container(horizontal=True, vertical_alignment="bottom"):
                    birim = st.segmented_control("Birim", ["m", "adim"], default="m", required=True,
                                                 key=f"cizim-birim-{a}-{b}",
                                                 format_func={"m": "Metre", "adim": "Adım"}.get)
                    deger = st.number_input(
                        "Mesafe (metre)" if birim == "m" else "Adım (normal yürüyüşle sayılan)",
                        min_value=0.5 if birim == "m" else 1.0, step=0.5 if birim == "m" else 1.0,
                        format="%.1f" if birim == "m" else "%d",
                        value=float(bm.adimdan_metre(yol.get("adim") or 1) if birim == "m" else yol.get("adim") or 1),
                        key=f"cizim-mesafe-{a}-{b}-{birim}-{yol.get('adim')}",
                        help="Şerit metreyle, lazer metreyle ya da kat planından ölçün. Bir kez girince modülü "
                             "sürükleseniz de değişmez.")
                    tek_yon = st.checkbox("Tek yön", bool(yol.get("tekYon")), key=f"cizim-tekyon-{a}-{b}")
                yeni_adim = bm.metreden_adim(deger) if birim == "m" else int(round(deger))
                st.caption(f"≈ {yeni_adim} standart adım ({bm.adimdan_metre(yeni_adim):g} m). Telefondaki uygulama "
                           "bunu her ziyaretçinin kendi adım uzunluğuna göre söyler.")
                tarif = st.text_input(f"Gidiş tarifi ({adlar[yol['a']]} → {adlar[yol['b']]})", yol.get("tarif", ""),
                                      key=f"cizim-tarif-{a}-{b}-{zlib.crc32(yol.get('tarif', '').encode())}")
                geri = st.text_input(f"Dönüş tarifi ({adlar[yol['b']]} → {adlar[yol['a']]})", yol.get("geriTarif", ""),
                                     key=f"cizim-geri-{a}-{b}-{zlib.crc32(yol.get('geriTarif', '').encode())}")
                if st.button("Kaydet", icon=":material/save:", type="primary", key=f"cizim-yol-kaydet-{a}-{b}"):
                    if yeni_adim != yol.get("adim"):
                        sabit.add((yol["a"], yol["b"]))
                        plan["sabitAdim"] = sorted(map(list, sabit))
                    if (tarif.strip(), geri.strip()) != (yol.get("tarif"), yol.get("geriTarif")):
                        # Elle yazılan tarif bundan sonra çizimden yeniden hesaplanmaz
                        plan["otoTarif"] = [y for y in plan.get("otoTarif") or [] if y != [yol["a"], yol["b"]]]
                    yol.update(adim=yeni_adim, tarif=tarif.strip(), geriTarif=geri.strip())
                    if tek_yon:
                        yol["tekYon"] = True
                    else:
                        yol.pop("tekYon", None)
                    kaydet(mekan, plan)
                    st.rerun()
            if [yol["a"], yol["b"]] not in (plan.get("otoTarif") or []) and st.button(
                    "Yön tarifini çizimden üret", icon=":material/turn_right:",
                    help="Elle yazılmış tarifin yerine, çizimdeki açılardan sağa / sola / düz tarifi yazılır."):
                plan.setdefault("otoTarif", []).append([yol["a"], yol["b"]])
                kaydet(mekan, plan)
                st.rerun()
            if st.button("Yolu sil", icon=":material/delete:"):
                cz.yol_sil(mekan, a, b)
                st.session_state.cizim_yol = None
                kaydet(mekan, plan)
                st.rerun()

# ── Harita konumu (kampüs gibi açık alanlar için, isteğe bağlı) ──
if not gorunum and dugumler:
    dis = cz.gorunum_konumlari(plan, None)
    gps = {i: cz.gps_coz(v) for i, v in (plan.get("gps") or {}).items() if i in dis}
    gps = {i: k for i, k in gps.items() if k}
    tahmin = set(plan.get("gpsTahmin") or []) & set(gps)
    with st.expander(f"Harita konumu (açık alan) · {len(gps)}/{len(dis)} nokta", icon=":material/map:",
                     expanded=bool(gps)):
        st.caption("Kampüs gibi açık alanlarda ziyaretçi QR okutmadan **neredeyim** diyebilsin diye. Bir nokta seçin, "
                   "haritada yerine tıklayın; sahadaysanız noktanın yanında durup **Buradayım**'a basın. İki noktayı "
                   "yerleştirince diğerlerini çizimden hesaplayabilirsiniz. Bina içi için gerekmez.")
        hr.harita({"noktalar": [{"id": i, "ad": adlar[i], "enlem": gps[i][0] if i in gps else None,
                                 "boylam": gps[i][1] if i in gps else None, "tahmin": i in tahmin}
                                for i in dis if i in adlar],
                   "secili": secili if secili in dis else None,
                   "anahtar": ",".join(sorted(gps)), "sigdir": False}, key="harita", on_olay=harita_olay)
        if tahmin:
            st.caption(f":orange[●] Sarı noktalar çizimden hesaplandı ({len(tahmin)}); yerinde değilse tıklayıp düzeltin.")
        eksik = [i for i in dis if i not in gps]
        with st.container(horizontal=True):
            if len(gps) - len(tahmin) >= 2 and eksik and st.button(
                    f"Kalan {len(eksik)} noktayı çizimden hesapla", icon=":material/auto_fix_high:",
                    help="Elle yerleştirdiğiniz noktalara göre çizim haritaya oturtulur"):
                elle = {**plan, "gps": {i: k for i, k in plan.get("gps", {}).items() if i not in tahmin}}
                hesap, uyum = hr.cizimden_hesapla(elle)
                plan.setdefault("gps", {}).update(hesap)
                plan["gpsTahmin"] = sorted(set(plan.get("gpsTahmin") or []) | set(hesap))
                st.session_state.plan = plan
                if uyum > 15:
                    st.session_state["harita_uyari"] = (
                        f"Çizim haritaya tam oturmadı (elle yerleştirdiğiniz noktalarda {round(uyum)} m sapma). "
                        "Hesaplanan sarı noktaları haritada kontrol edin.")
                st.rerun()
            if gps and st.button("Harita konumlarını sil", icon=":material/delete:", type="tertiary"):
                plan.pop("gps", None)
                plan.pop("gpsTahmin", None)
                st.session_state.plan = plan
                st.rerun()
        if st.session_state.get("harita_uyari"):
            st.warning(st.session_state.pop("harita_uyari"), icon=":material/warning:")

# ── Tarifi deneyin: ziyaretçinin duyacağı tarif ──
if mekan["hedefler"] and mekan.get("giris") in adlar:
    with st.container(border=True):
        st.markdown("**:material/hearing: Ziyaretçi ne duyacak?** Bir yer seçin; girişten oraya giden sesli tarif "
                    "görünür.")
        hedef_adi = st.selectbox("Gidilecek yer", [h["ad"] for h in mekan["hedefler"]], key="cizim-onizleme",
                                 label_visibility="collapsed")
        st.markdown("\n".join(f"1. {adim}" for adim in bm.rota_onizleme(mekan, hedef_adi)))

hatalar, _ = bm.dogrula(mekan)
# Eksik olsa da ilerlenir: Yazdır adımı eksikleri ayrıntılı gösterir ve bazılarını tek tıkla düzeltir
durum.ileri("app_pages/yazdir.py", "İleri: Yazdır",
            neden=f":material/error: {len(hatalar)} eksik var: {hatalar[0]}" if hatalar
            else ":material/check_circle: Düzen hazır.")

with st.expander("Gelişmiş", icon=":material/tune:"):
    st.caption("Her şeyi tek tek değiştirmek isteyenler için.")
    with st.container(horizontal=True):
        st.page_link("app_pages/duzenle.py", label="Tablolarda düzenle", icon=":material/table_view:")
        st.page_link("app_pages/plan_sayfasi.py", label="Teknik plan", icon=":material/map:")
