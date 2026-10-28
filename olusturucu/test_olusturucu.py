import json
import zlib

import pytest
from streamlit.testing.v1 import AppTest

import bak_mekan as bm


@pytest.fixture
def hastane():
    mekan = json.loads(json.dumps(bm.sablonlar()["Hastane / poliklinik (iki katlı, asansörlü)"]))
    mekan["id"] = "q-test-hastane"
    return mekan


def test_base45_rfc_ornekleri():
    assert bm.base45(b"AB") == "BB8"
    assert bm.base45(b"Hello!!") == "%69 VD92EX0"
    assert bm.base45(b"base-45") == "UJCLQE7W581"
    assert bm.base45_coz("UJCLQE7W581") == b"base-45"


def test_qr_verisi_geri_cozulur_ve_harf_rakam_kipinde(hastane):
    veri = bm.qr_verisi(hastane)
    assert veri.startswith("BAK:VERI:1:")
    assert set(veri) <= set(bm.BASE45)          # QR'ın sıkışık harf-rakam kipine uygun
    assert bm.qr_verisini_coz(veri) == hastane


def test_tum_sablonlar_gecerli_ve_qr_okunabilir_boyutta():
    buyukler = bm.buyuk_sablonlar()
    for ad, mekan in bm.sablonlar().items():
        mekan = {**mekan, "id": bm.kimlik_uret(mekan["ad"])}
        hatalar, _ = bm.dogrula(mekan)
        assert hatalar == [], ad
        # Büyük binalar QR'a sığmaz; onlar bina bilgisini kurumun sitesinde tutar
        assert bm.qr_sigar_mi(bm.qr_verisi(mekan)) != (ad in buyukler), ad


def test_hicbir_qra_sigmayan_bina_sayfayi_cokertmez():
    """146 mağazalı AVM en büyük QR'ı (sürüm 40) da aşar; QR sayfası çökmemeli, adres yolunu önermeli."""
    ad = next(iter(bm.buyuk_sablonlar()))
    at = sablon_ac(uygulama(), ad).switch_page("app_pages/yazdir.py").run()
    assert not at.exception
    assert bm.qr_surumu(bm.qr_verisi(bm.sablonlar()[ad])) is None
    assert at.segmented_control(key="qr_yontemi").value == "adres"
    at.segmented_control(key="qr_yontemi").set_value("icinde").run()   # kurum yine de "QR'ın içinde" seçerse
    assert not at.exception


def test_kimlik_q_ile_baslar_ve_turkce_harfleri_sadelestirir():
    kimlik = bm.kimlik_uret("Kadıköy Şişli Göz Hastanesi")
    assert kimlik.startswith("q-kadikoy-sisli-goz-hastanesi-")


@pytest.mark.parametrize("bozma, beklenen", [
    (lambda m: m.update(id="ornek-hastane"), "q-"),
    (lambda m: m.update(giris="yok"), "Giriş noktasını"),
    (lambda m: m["baglantilar"][0].pop("geriTarif"), "dönüş tarifini"),
    (lambda m: m["baglantilar"][0].update(adim=0), "adım sayısı"),
    (lambda m: m["hedefler"][0].update(nokta="yok"), "noktası listede yok"),
])
def test_hatalar_turkce_anlatilir(hastane, bozma, beklenen):
    bozma(hastane)
    hatalar, _ = bm.dogrula(hastane)
    assert any(beklenen in h for h in hatalar), hatalar


def test_girisinden_yol_olmayan_hedef_hata(hastane):
    hastane["noktalar"].append({"id": "ada", "ad": "Ulaşılamaz oda"})
    hastane["hedefler"].append({"ad": "Gizli oda", "nokta": "ada", "tarif": "", "anahtarlar": ["gizli"]})
    hatalar, _ = bm.dogrula(hastane)
    assert any("Gizli oda" in h for h in hatalar)


def test_tablolar_ile_duzen_arasinda_kayipsiz_donusum(hastane):
    noktalar, yollar, hedefler = bm.mekandan_satirlar(hastane)
    bilgi = {k: hastane.get(k) for k in ("id", "ad", "tur", "surum", "giris", "kasa")}
    # "kat: 0" (zemin) yazılmaz; uygulama kat yoksa zemin kabul eder
    beklenen = {**hastane, "noktalar": [{k: v for k, v in n.items() if not (k == "kat" and v == 0)}
                                        for n in hastane["noktalar"]]}
    assert bm.satirlardan_mekan(bilgi, noktalar, yollar, hedefler) == beklenen


def test_rota_onizleme_kat_degistirir(hastane):
    adimlar = bm.rota_onizleme(hastane, "Kardiyoloji Polikliniği")
    assert adimlar[0].startswith("Giriş")
    assert any("Asansor" in a or "Merdiven" in a for a in adimlar)
    assert adimlar[-1].startswith("Varınca: Kardiyoloji")


def test_etiket_sayfasi_her_nokta_icin_qr_icerir(hastane):
    sayfa = bm.etiket_sayfasi(hastane)
    assert sayfa.count("<img") == len(hastane["noktalar"])     # giriş + girişten başka her nokta
    assert "Örnek Devlet Hastanesi" in sayfa


def uygulama():
    return AppTest.from_file("streamlit_app.py", default_timeout=30).run()


def sablon_ac(at, ad="Hastane / poliklinik (iki katlı, asansörlü)"):
    at.selectbox[0].select(ad)
    next(b for b in at.button if b.label == "Şablonu aç").click().run()
    return at


def test_uygulama_sablonla_acilir_plan_ve_qr_uretir():
    at = sablon_ac(uygulama())
    assert not at.exception
    assert at.get("graphviz_chart")                  # şablon açılınca plan sayfasına geçilir
    at.switch_page("app_pages/yazdir.py").run()
    assert not at.exception
    assert any("15 nokta, 15 yol, 8 hedef" in str(s.value) for s in at.success)
    at.switch_page("app_pages/duzenle.py").run()
    assert not at.exception
    assert at.text_input[0].value == "Örnek Devlet Hastanesi"


def test_bos_sayfada_eksikler_soylenir():
    at = uygulama().switch_page("app_pages/yazdir.py").run()
    assert not at.exception
    assert any("Kurumun adını yazın" in str(e.value) for e in at.error)


def test_uretilen_qr_gercek_bir_okuyucuyla_okunur(hastane):
    """ZXing, Android'deki barkod okuyuculara yakın bir çözücüdür."""
    zxingcpp = pytest.importorskip("zxingcpp")
    import io

    from PIL import Image

    veri = bm.qr_verisi(hastane)
    for kutu in (3, 6):
        okunan = zxingcpp.read_barcodes(Image.open(io.BytesIO(bm.qr_png(veri, kutu=kutu))))
        assert okunan and okunan[0].text == veri


def test_liste_uygulamadakiyle_ayni_okunur(hastane):
    # Uygulama testindeki (__tests__/hedefSecimi.test.tsx) beklenen metinle aynı başlamalı
    assert bm.liste_sayfalari(hastane) == [
        "Burada 7 yer var. Zemin kat: 1, Danışma; 2, Vezne; 3, Laboratuvar; 4, Tuvalet. "
        "1. kat: 5, Kardiyoloji Polikliniği; 6, Dahiliye Polikliniği; 7, Göz Polikliniği. "
        "Çalışanların adıyla da sorabilirsiniz, örneğin doktorun adını söyleyin."]


def test_uzun_liste_onar_onar():
    mekan = {"noktalar": [{"id": "a", "ad": "A"}], "hedefler": [
        {"ad": f"Oda {i}", "nokta": "a"} for i in range(1, 24)]}
    sayfalar = bm.liste_sayfalari(mekan)
    assert len(sayfalar) == 3
    assert sayfalar[0].startswith("Burada 23 yer var. İlk 10 tanesi: 1, Oda 1;")
    assert sayfalar[0].endswith("Diğer 13 yer için devam deyin.")
    assert sayfalar[2] == "21. yerden devam: 21, Oda 21; 22, Oda 22; 23, Oda 23."


def test_kisa_ad_onerisi_tekrarlanan_sozcugu_atar():
    hedefler = [{"ad": "Kardiyoloji Polikliniği"}, {"ad": "Göz Polikliniği"}, {"ad": "Vezne"},
                {"ad": "101 numaralı sınıf"}, {"ad": "102 numaralı sınıf"},
                {"ad": "Dahiliye Polikliniği", "kisaAd": "Dahiliye"}]
    assert bm.kisa_ad_onerileri(hedefler) == {0: "Kardiyoloji", 1: "Göz"}


def test_kisa_ad_listede_okunur_ve_dosyaya_yazilir(hastane):
    hastane["hedefler"][5]["kisaAd"] = "Kardiyoloji"
    assert "5, Kardiyoloji; 6" in bm.liste_sayfalari(hastane)[0]
    noktalar, yollar, hedefler = bm.mekandan_satirlar(hastane)
    bilgi = {k: hastane.get(k) for k in ("id", "ad", "tur", "surum", "giris", "kasa")}
    assert bm.satirlardan_mekan(bilgi, noktalar, yollar, hedefler)["hedefler"][5]["kisaAd"] == "Kardiyoloji"


def test_uzun_ada_kisa_ad_uyarisi(hastane):
    _, uyarilar = bm.dogrula(hastane)
    assert any("Kardiyoloji Polikliniği" in u and "Kısa ad" in u for u in uyarilar)


def test_kisa_ad_oner_dugmesi_tabloyu_doldurur():
    at = sablon_ac(uygulama()).switch_page("app_pages/duzenle.py").run()
    oner = next(b for b in at.button if b.label == "Kısa adları öner")
    oner.click().run()
    assert not at.exception
    assert "Kardiyoloji" in list(at.session_state["kaynak"]["hedefler"]["kisaAd"])


def test_karisik_turlu_sutunlar_tek_ture_cevrilir():
    """Kurumun elle düzenlediği dosyada oda numarası sayı olabilir; tablo düzenleyici karışık türde hata veriyordu."""
    mekan = json.loads(json.dumps(bm.sablonlar()["Hastane / poliklinik (iki katlı, asansörlü)"]))
    mekan["hedefler"][5]["oda"] = 112
    mekan["noktalar"][3]["kat"] = "0"
    noktalar, _, hedefler = bm.mekandan_satirlar(mekan)
    assert set(map(type, bm.tablo(hedefler, bm.HEDEF_SUTUNLARI)["oda"])) == {str}
    assert bm.tablo(noktalar, bm.NOKTA_SUTUNLARI)["kat"].dtype == "float64"


def test_eski_oturumdaki_tablolar_yeni_yapiya_cevrilir():
    """Sayfa açıkken uygulama güncellenince eski oturumda 'kisaAd' sütunu yoktu."""
    at = AppTest.from_file("streamlit_app.py", default_timeout=30).run()
    eski = at.session_state["kaynak"]
    eski["hedefler"] = eski["hedefler"].drop(columns=["kisaAd"])
    at.session_state["kaynak"] = eski
    at.session_state["tablo_semasi"] = 1
    at.run()
    assert not at.exception
    assert "kisaAd" in at.session_state["kaynak"]["hedefler"].columns


# ── Sihirbazlar ve plan ──────────────────────────────────

import plan  # noqa: E402
import sihirbaz  # noqa: E402


def test_market_sihirbazi_sag_sol_reyonlari_tarif_eder():
    mekan, p = sihirbaz.market_olustur("Deneme Market", [
        {"sol": "Meyve, Sebze", "sag": "Ekmek"},
        {"sol": "Süt, Peynir, Yoğurt", "sag": "Deterjan"}])
    mekan["id"] = "q-deneme-market"
    assert bm.dogrula(mekan) == ([], [])
    tarifler = {h["ad"]: h["tarif"] for h in mekan["hedefler"]}
    assert tarifler["Ekmek"] == "1. koridora girin. Ekmek sağınızda."
    assert tarifler["Süt"] == "2. koridora girin. Süt koridorun başında, solunuzda."
    assert tarifler["Yoğurt"] == "2. koridora girin. Yoğurt koridorun sonunda, solunuzda."
    assert "süt" in next(h for h in mekan["hedefler"] if h["ad"] == "Süt")["anahtarlar"]
    assert p["raflar"]["k2"]["sol"] == "Süt, Peynir, Yoğurt"
    assert set(p["konum"]) == {n["id"] for n in mekan["noktalar"]}
    # Plan QR'a girmez
    assert "plan" not in bm.qr_verisini_coz(bm.qr_verisi({**mekan, "plan": p}))


def test_market_koridorlar_sola_sirali_olabilir():
    mekan, _ = sihirbaz.market_olustur("M", [{"sol": "A"}, {"sag": "B"}], siralama="sol")
    yol = next(b for b in mekan["baglantilar"] if b["a"] == "k1" and b["b"] == "k2")
    assert yol["tarif"] == "Ön koridorda sola doğru ilerleyin"
    assert yol["geriTarif"] == "Ön koridorda sağa doğru ilerleyin"


def test_bina_sihirbazi_katlari_merdiven_ve_asansorle_baglar():
    mekan, p = sihirbaz.bina_olustur("Okul", "kurum", [
        [{"ad": "Müdür odası", "taraf": "sag", "adim": 4}],
        [{"ad": "101 numaralı sınıf", "taraf": "sol", "adim": 5, "oda": "101", "kisiler": "Ayşe Öğretmen"}],
        [{"ad": "Kütüphane", "taraf": "sag", "adim": 7}]], basamak=20)
    mekan["id"] = "q-okul"
    assert bm.dogrula(mekan) == ([], [])
    turler = [b.get("tur") for b in mekan["baglantilar"] if b.get("tur")]
    assert turler.count("merdiven") == 2 and turler.count("asansor") == 2
    assert all(b.get("basamak") == 20 for b in mekan["baglantilar"] if b.get("tur") == "merdiven")
    sinif = next(h for h in mekan["hedefler"] if h["ad"] == "101 numaralı sınıf")
    assert sinif["tarif"] == "101 numaralı sınıf kapısı solunuzda, oda 101."
    assert sinif["kisiler"] == ["Ayşe Öğretmen"]
    yol = bm.rota_onizleme(mekan, "Kütüphane")
    assert any("Merdiven" in a or "Asansor" in a for a in yol) and yol[-1] == "Varınca: Kütüphane kapısı sağınızda."


def test_tek_katli_binada_merdiven_asansor_yok():
    mekan, _ = sihirbaz.bina_olustur("Ofis", "kurum", [[{"ad": "Vezne", "taraf": "sol", "adim": 5}]])
    assert not any(b.get("tur") for b in mekan["baglantilar"])


def test_plan_sihirbaz_konumlariyla_sabit_cizilir_elle_girilende_katlara_ayrilir(hastane):
    mekan, p = sihirbaz.market_olustur("M", [{"sol": "Süt", "sag": "Ekmek"}])
    dot = plan.plan_dot(mekan, p)
    assert "layout=neato" in dot and 'pos="' in dot and "raf-k1" in dot
    dot2 = plan.plan_dot(hastane)
    assert "layout=dot" in dot2 and 'cluster_0' in dot2 and 'cluster_1' in dot2
    assert "24 basamak" in dot2 and "asansör" in dot2


def test_sihirbaz_sayfasindan_market_olusturulur():
    at = uygulama().switch_page("app_pages/sihirbaz.py").run()
    assert not at.exception
    at.text_input[0].input("Çarşı Market").run()
    next(b for b in at.button if b.label == "Market düzenini oluştur").click().run()
    assert not at.exception
    assert at.session_state["bilgi"]["ad"] == "Çarşı Market"
    assert at.session_state["plan"]["raflar"]
    assert at.get("graphviz_chart")


def test_bina_sihirbazi_sayfasi_calisir():
    at = uygulama()
    at.session_state["sihirbaz_turu"] = "Koridorlu bina"
    at.switch_page("app_pages/sihirbaz.py").run()
    assert not at.exception
    at.text_input[0].input("Deneme Hastanesi").run()
    next(b for b in at.button if b.label == "Bina düzenini oluştur").click().run()
    assert not at.exception
    assert at.session_state["bilgi"]["tur"] == "hastane"


def test_duzen_dosyasi_plani_saklar_ve_geri_yukler(hastane):
    mekan, p = sihirbaz.market_olustur("M", [{"sol": "Süt"}])
    mekan["id"] = "q-m-0001"
    at = uygulama()
    import durum  # noqa: F401
    dosya = json.dumps({**mekan, "plan": p}, ensure_ascii=False)
    at.session_state["yuklenecek"] = dosya
    # Dosya yükleme bileşeni AppTest'te doğrudan beslenemediği için yükleme işlevi ayrıca sınanır
    from streamlit.testing.v1 import AppTest as _A
    yukleme = _A.from_string("""
import json, streamlit as st, durum
durum.baslat()
durum.mekani_yukle(json.loads(st.session_state.yuklenecek), yeni_kimlik=False)
st.write(durum.dosya_icerigi(durum.guncel_mekan()))
""", default_timeout=30)
    yukleme.session_state["yuklenecek"] = dosya
    yukleme.run()
    assert not yukleme.exception
    yazilan = json.loads(yukleme.markdown[0].value)
    assert yazilan["surum"] == 2 and yazilan["plan"]["raflar"]["k1"]["sol"] == "Süt"


def test_avm_sihirbazi_bodrum_yuruyen_merdiven_ve_kategoriler():
    kat = lambda *s: [{"taraf": t, "ad": a, "adim": 5, "anahtarlar": k} for t, a, k in s]  # noqa: E731
    mekan, _ = sihirbaz.bina_olustur("AVM", "diger", [
        kat(("sol", "Otopark", "araba")),
        kat(("sag", "Danışma", "bilgi"), ("sol", "A Giyim", "giyim")),
        kat(("sol", "B Giyim", "giyim, kot"))], dikey="yuruyen", ilk_kat=-1)
    mekan["id"] = "q-avm"
    assert bm.dogrula(mekan) == ([], [])
    giris_yolu = next(b for b in mekan["baglantilar"] if b["a"] == "giris")
    assert next(n for n in mekan["noktalar"] if n["id"] == giris_yolu["b"]).get("kat", 0) == 0   # giriş zemin katta
    assert {n.get("kat", 0) for n in mekan["noktalar"]} == {-1, 0, 1}
    assert any(b.get("tur") == "yuruyen-merdiven" for b in mekan["baglantilar"])
    # Yürüyen merdiven asansörden önce tercih edilir; not inerken de okunur
    assert ("Yürüyen merdiven ile 1 kat aşağı → Yürüyen merdiven başı. Binmeden önce yan tutamağı bulun; "
            "inişte bant bitince adımınızı uzatın.") in bm.rota_onizleme(mekan, "Otopark")
    # "giyim" iki mağazada: uygulama seçenek sunar
    assert sum("giyim" in h["anahtarlar"] for h in mekan["hedefler"]) == 2


def test_adres_qr_ve_etiketler():
    assert bm.adres_gecerli("https://avm.com.tr/bak/duzen.json")
    assert not bm.adres_gecerli("http://avm.com.tr/duzen.json")
    assert not bm.adres_gecerli("https://avm.com.tr/a b.json")
    veri = bm.adres_qr_verisi("https://avm.com.tr/bak/duzen.json")
    assert veri == "BAK:URL:https://avm.com.tr/bak/duzen.json"
    mekan, _ = sihirbaz.market_olustur("M", [{"sol": "Süt"}])
    mekan["id"] = "q-m"
    assert bm.etiket_sayfasi(mekan, veri) != bm.etiket_sayfasi(mekan)


def test_buyuk_binada_adres_secenegi_kendiliginden_secilir():
    at = uygulama()
    at.session_state["sihirbaz_turu"] = "AVM"
    at.switch_page("app_pages/sihirbaz.py").run()
    assert not at.exception
    at.text_input[0].input("Büyük AVM").run()
    next(b for b in at.button if b.label == "AVM düzenini oluştur").click().run()
    assert not at.exception
    # Bina büyütülür: 40 mağaza ekle
    kaynak = at.session_state["kaynak"]
    noktalar = kaynak["noktalar"].to_dict("records")
    yollar = kaynak["yollar"].to_dict("records")
    hedefler = kaynak["hedefler"].to_dict("records")
    for i in range(40):
        noktalar.append({"ad": f"Mağaza {i} kapısı", "kat": 0, "id": f"m{i}"})
        yollar.append({"a": "koridor-1", "b": f"m{i}", "tur": "yuru", "adim": 5 + i,
                       "tarif": "Koridorda düz ilerleyin", "geriTarif": "Koridorda geri dönün", "tekYon": False})
        hedefler.append({"ad": f"Mağaza {i}", "nokta": f"m{i}", "tarif": f"Mağaza {i} sağınızda.",
                         "anahtarlar": "giyim"})
    at.session_state["kaynak"] = {"noktalar": bm.tablo(noktalar, bm.NOKTA_SUTUNLARI),
                                  "yollar": bm.tablo(yollar, bm.YOL_SUTUNLARI),
                                  "hedefler": bm.tablo(hedefler, bm.HEDEF_SUTUNLARI)}
    at.switch_page("app_pages/yazdir.py").run()
    assert not at.exception
    assert at.segmented_control(key="qr_yontemi").value == "adres"
    at.text_input(key="duzen_adresi").input("https://buyuk-avm.com.tr/bak.json").run()
    assert not at.exception
    assert any(b.label.startswith("Etiketleri indir") for b in at.get("download_button"))


def test_elle_eklenen_nokta_plani_bozmaz():
    mekan, p = sihirbaz.market_olustur("M", [{"sol": "Süt"}, {"sag": "Ekmek"}])
    mekan["noktalar"].append({"id": "yeni", "ad": "Yeni nokta"})
    mekan["baglantilar"].append({"a": "k2", "b": "yeni", "adim": 4, "tarif": "x", "geriTarif": "y"})
    dot = plan.plan_dot(mekan, p)
    assert "layout=neato" in dot                                   # düzenli yerleşim korunur
    assert 'pos="' in dot.split('"k1"')[1].split("\n")[0]          # bilinen nokta sabit
    assert 'pos="' not in dot.split('"yeni" [')[1].split("\n")[0]  # yeni nokta serbest


def test_raf_kutusu_guncel_reyonlari_gosterir():
    mekan, p = sihirbaz.market_olustur("M", [{"sol": "Süt, Peynir", "sag": "Ekmek"}])
    mekan["hedefler"] = [h for h in mekan["hedefler"] if h["ad"] != "Peynir"]       # Düzenle'de silindi
    mekan["hedefler"].append({"ad": "Yumurta", "nokta": "k1", "tarif": "1. koridora girin. Yumurta sağınızda.",
                              "anahtarlar": ["yumurta"]})
    dot = plan.plan_dot(mekan, p)
    raf = dot.split('"raf-k1"')[1].split("\n")[0]
    assert "Süt" in raf and "Peynir" not in raf and "Ekmek, Yumurta" in raf


HASTANE_SITESI = """A BLOK
4. KAT
Hematoloji Polikliniği
Onkoloji Polikliniği
Zemin Kat
Danışma ve Vezne
Kan Alma Ünitesi
-1. Kat
Radyoloji Birimi
MR (Emar)
-2. Kat
Otopark"""


@pytest.mark.parametrize("metin, beklenen", [
    (HASTANE_SITESI, {-2: ["Otopark"], -1: ["Radyoloji Birimi", "MR (Emar)"],
                      0: ["Danışma ve Vezne", "Kan Alma Ünitesi"], 4: ["Hematoloji Polikliniği", "Onkoloji Polikliniği"]}),
    ("Zemin Kat: Psikiyatri, Nöroloji\n1. Kat: Genel Cerrahi; Üroloji\nBodrum Kat - Arşiv",
     {-1: ["Arşiv"], 0: ["Psikiyatri", "Nöroloji"], 1: ["Genel Cerrahi", "Üroloji"]}),
    ("• 2. Bodrum Kat: Otopark\n- 3. kat – Yoğun bakım", {-2: ["Otopark"], 3: ["Yoğun bakım"]}),
    ("Bu metinde kat yok", {}),
])
def test_kat_listesi_cozulur(metin, beklenen):
    assert sihirbaz.kat_listesi_coz(metin) == beklenen


def test_yapistirilan_kat_listesi_sihirbazi_doldurur():
    at = uygulama()
    at.session_state["sihirbaz_turu"] = "Koridorlu bina"
    at.switch_page("app_pages/sihirbaz.py").run()
    at.text_area(key="sihirbaz_Koridorlu bina_yapistir").input(HASTANE_SITESI).run()
    next(b for b in at.button if b.label == "Katları doldur").click().run()
    assert not at.exception
    assert at.number_input(key="sihirbaz_Koridorlu bina_ilkkat").value == -2
    assert at.number_input(key="sihirbaz_Koridorlu bina_katsayisi").value == 7      # -2 … 4
    assert any("Binada yürüyerek her katı düzeltin" in w.value for w in at.warning)
    at.text_input[0].input("Deneme Devlet Hastanesi").run()
    next(b for b in at.button if b.label == "Bina düzenini oluştur").click().run()
    assert not at.exception
    hedefler = list(at.session_state["kaynak"]["hedefler"]["ad"])
    assert "Radyoloji Birimi" in hedefler and "Onkoloji Polikliniği" in hedefler
