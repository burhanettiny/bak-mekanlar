import math
import json
from pathlib import Path

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
    assert any("tek bir QR'a sığmayacak" in str(i.value) for i in at.info)   # adres yolu kendiliğinden
    assert at.text_input(key="duzen_adresi")


def test_kimlik_q_ile_baslar_ve_turkce_harfleri_sadelestirir():
    kimlik = bm.kimlik_uret("Kadıköy Şişli Göz Hastanesi")
    assert kimlik.startswith("q-kadikoy-sisli-goz-hastanesi-")


@pytest.mark.parametrize("bozma, beklenen", [
    (lambda m: m.update(id="ornek-hastane"), "q-"),
    (lambda m: m.update(giris="yok"), "Giriş noktasını"),
    (lambda m: m["baglantilar"][0].pop("geriTarif"), "dönüş tarifini"),
    (lambda m: m["baglantilar"][0].update(adim=0), "adım sayısı"),
    (lambda m: m["hedefler"][0].update(nokta="yok"), "Noktalar listesinde yok"),
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
    """Başla sayfasında örnekler türünün kartındadır: birden çok örnek "Örnekle dene" açılır kutusunda adıyla,
    tek örnek doğrudan "Örnekle dene" düğmesiyle (adı ipucunda) açılır."""
    dugme = next((b for b in at.button if b.label == ad), None) or next(
        b for b in at.button if b.label == "Örnekle dene" and b.help == ad)
    dugme.click().run()
    return at


def test_uygulama_sablonla_acilir_plan_ve_qr_uretir():
    at = sablon_ac(uygulama())
    assert not at.exception
    assert any(t.label == "Kurumun adı" for t in at.text_input)   # örnek açılınca kontrol ve çizime geçilir
    at.switch_page("app_pages/yazdir.py").run()
    assert not at.exception
    assert any("Ziyaretçiye 8 yer okunacak. 15 etiket" in str(s.value) for s in at.success)
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
    at = uygulama()
    at.session_state["sihirbaz_turu"] = "Market"
    at.switch_page("app_pages/sihirbaz.py").run()
    assert not at.exception
    at.text_input[0].input("Çarşı Market").run()
    next(b for b in at.button if b.label == "Market düzenini oluştur").click().run()
    assert not at.exception
    assert at.session_state["bilgi"]["ad"] == "Çarşı Market"
    assert at.session_state["plan"]["raflar"]
    assert any(t.label == "Kurumun adı" for t in at.text_input)   # kontrol ve çizim sayfasına geçildi


def test_bina_sihirbazi_sayfasi_calisir():
    at = uygulama()
    at.session_state["sihirbaz_turu"] = "Koridorlu bina"
    at.session_state["sihirbaz_Koridorlu bina_yontem"] = "tablo"
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
    at.session_state["sihirbaz_AVM_yontem"] = "tablo"
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
    at.session_state["sihirbaz_Koridorlu bina_yontem"] = "tablo"
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


def test_kimligi_degisen_noktanin_yollari_ve_hedefleri_onerilir_ve_duzeltilir(hastane):
    m = json.loads(json.dumps(hastane))
    eski = m["hedefler"][0]["nokta"]
    yeni = f"{eski}-kapi"
    next(n for n in m["noktalar"] if n["id"] == eski)["id"] = yeni
    hatalar, _ = bm.dogrula(m)
    assert any(f"'{eski}'" in h and "Noktalar listesinde yok" in h for h in hatalar)
    assert bm.kopuk_kimlikler(m) == [eski]
    assert bm.kimlik_onerileri(m) == {eski: yeni}
    assert bm.dogrula(bm.kimlikleri_degistir(m, {eski: yeni}))[0] == []


def test_qr_sayfasi_kopuk_baglantilari_tek_tikla_duzeltir():
    at = sablon_ac(uygulama())
    noktalar = at.session_state["kaynak"]["noktalar"].copy()
    hedefler = at.session_state["kaynak"]["hedefler"]
    eski = hedefler.loc[0, "nokta"]
    yeni = f"{eski}-kapi"
    noktalar.loc[noktalar["id"] == eski, "id"] = yeni
    at.session_state["kaynak"] = {**at.session_state["kaynak"], "noktalar": noktalar}
    at.switch_page("app_pages/yazdir.py").run()
    assert at.error
    next(b for b in at.button if b.label == "Bağlantıları düzelt").click().run()
    assert not at.exception and not at.error


def test_cizim_modul_ekleme_tasima_ve_bina_ici():
    import cizim as cz
    m = json.loads(json.dumps(bm.sablonlar()["Ardahan Üniversitesi Yenisey Kampüsü (OpenStreetMap yol ağından – sahada doğrulayın)"]))
    plan = m.pop("plan")
    olc = cz.olcek(m, plan)
    assert 10 < olc < 15                                  # haritadan: bir birim ~ 8 m ~ 11 adım
    plan["konum"] = cz.yerlesim(m, plan, olc)

    # Bina içine oda: binanın iç çiziminde, ölçek 1 kare = 1 adım
    oda = cz.modul_ekle(m, plan, "oda", "Dekanlık", yer=[12, 0], ust="muhendislik", baglanacak="muhendislik",
                        olc=cz.gorunum_olcegi(plan, "muhendislik", olc))
    assert plan["ust"][oda] == "muhendislik"
    yol = next(b for b in m["baglantilar"] if b["b"] == oda)
    assert yol["adim"] == 12 and yol["tarif"] and yol["geriTarif"]
    assert any(h["nokta"] == oda and "dekanlık" in h["anahtarlar"] for h in m["hedefler"])
    assert cz.gorunum_noktalari(m, plan, "muhendislik", None) == {"muhendislik", oda}
    assert oda not in cz.gorunum_noktalari(m, plan, None, None)

    # Odayı taşımak yalnızca iç çizimdeki mesafeyi değiştirir
    assert cz.tasi(m, plan, oda, 20, 0, 1.0, "muhendislik") == [("muhendislik", oda, 20)]
    # Elle yazılan (sahada sayılan) adım sürüklenince değişmez
    plan["sabitAdim"] = [["muhendislik", oda]]
    assert cz.tasi(m, plan, oda, 40, 0, 1.0, "muhendislik") == [] and yol["adim"] == 20

    # Dış çizimde binayı taşımak kampüs ölçeğiyle yolu yeniden hesaplar
    x, y = plan["konum"]["rektorluk"]
    eski = next(b["adim"] for b in m["baglantilar"] if b["b"] == "rektorluk")
    assert cz.tasi(m, plan, "rektorluk", x / 2, y / 2, olc)
    assert next(b["adim"] for b in m["baglantilar"] if b["b"] == "rektorluk") != eski

    assert bm.dogrula(m)[0] == []
    # Bina silinince odaları da gider
    cz.nokta_sil(m, plan, "muhendislik")
    assert oda not in {n["id"] for n in m["noktalar"]} and oda not in plan["ust"]


def test_cizim_sayfasi_bos_ve_sablonla_acilir_modul_eklenir():
    at = uygulama().switch_page("app_pages/cizim_sayfasi.py").run()
    assert not at.exception
    at = sablon_ac(uygulama())
    at.switch_page("app_pages/cizim_sayfasi.py").run()
    assert not at.exception
    next(t for t in at.text_input if t.label.startswith("Adı")).input("Kütüphane")
    next(b for b in at.button if b.label == "Ekle").click().run()
    assert not at.exception
    assert at.session_state["cizim_secili"] == "kutuphane"
    at.switch_page("app_pages/yazdir.py").run()
    assert not at.error                                   # girişe bağlandı: QR üretilebilir


def test_cizim_bina_ici_kat_listesinden_kurulur():
    import cizim as cz
    m = json.loads(json.dumps(bm.sablonlar()["Ardahan Üniversitesi Yenisey Kampüsü (OpenStreetMap yol ağından – sahada doğrulayın)"]))
    plan = m.pop("plan")
    plan["konum"] = cz.yerlesim(m, plan, cz.olcek(m, plan))
    n = cz.binayi_doldur(m, plan, "rektorluk", "Zemin kat: Sekreterlik, Rektör odası, WC\n1. kat: 101, 102, WC")
    assert n == 6
    ic = cz.gorunum_noktalari(m, plan, "rektorluk", None)
    assert "rektorluk" in ic and len(ic) > 6
    assert all(i.startswith("rektorluk-") for i in ic - {"rektorluk"})
    # Girişten bina içindeki odaya yol var; aynı adlı ikinci WC bina adıyla ayrılır
    assert bm.dogrula(m)[0] == []
    adlar = [h["ad"] for h in m["hedefler"]]
    assert "WC" in adlar and "WC (Rektörlük)" in adlar
    cz.binayi_doldur(m, plan, "konukevi", "Zemin kat: WC\n1. kat: WC")
    assert {"WC (Konukevi)", "WC (Konukevi, 1. kat)"} <= {h["ad"] for h in m["hedefler"]}
    assert any("1. kat" in s or "kat" in s.lower() for s in bm.rota_onizleme(m, "101"))
    # İkinci binada aynı kimlikler çakışmaz
    cz.binayi_doldur(m, plan, "iibf", "Zemin kat: Dekanlık, WC")
    assert bm.dogrula(m)[0] == []
    assert len({n["id"] for n in m["noktalar"]}) == len(m["noktalar"])


def test_cizim_yildiz_bicimindeki_odalar_koridora_dizilir():
    import cizim as cz
    m = {"id": "q-x", "ad": "Okul", "tur": "kurum", "surum": 1, "giris": "giris",
         "noktalar": [{"id": i, "ad": a} for i, a in [("giris", "Giriş"), ("hol", "Hol"), ("mudur", "Müdür odası"),
                                                       ("ogretmen", "Öğretmenler odası"), ("merdiven", "Merdiven")]],
         "baglantilar": [{"a": "giris", "b": "hol", "adim": 6, "tarif": "x", "geriTarif": "y"}] +
                        [{"a": "hol", "b": v, "adim": 9, "tarif": "x", "geriTarif": "y"}
                         for v in ("mudur", "ogretmen", "merdiven")],
         "hedefler": [{"ad": "Müdür odası", "nokta": "mudur", "tarif": "t", "anahtarlar": ["müdür"]},
                      {"ad": "Öğretmenler odası", "nokta": "ogretmen", "tarif": "t", "anahtarlar": ["öğretmen"]}]}
    # Hol solda; müdür 4 adım ileride sağda, öğretmenler 10 adım ileride solda; merdiven arkada
    plan = {"konum": {"giris": [-6, 0], "hol": [0, 0], "mudur": [4, -1], "ogretmen": [10, 1], "merdiven": [-2, 5]}}
    assert set(cz.sirala_adaylari(m, plan, "hol")) == {"mudur", "ogretmen"}
    assert cz.koridora_diz(m, plan, "hol", 1.0) == 2
    yollar = {(b["a"], b["b"]): b for b in m["baglantilar"]}
    assert ("hol", "mudur") in yollar and ("mudur", "ogretmen") in yollar and ("hol", "ogretmen") not in yollar
    assert "sağınızda" in yollar[("hol", "mudur")]["tarif"] and "solunuzda" in yollar[("mudur", "ogretmen")]["tarif"]
    assert yollar[("mudur", "ogretmen")]["adim"] == 6
    assert ("hol", "merdiven") in yollar                     # arkadaki merdiven olduğu gibi kalır
    assert bm.dogrula(m)[0] == []


def test_bina_listesi_tek_kutuyla_duzene_donusur():
    """Varsayılan yol: ad + "Zemin kat: …" listesi → Düzeni oluştur → kontrol ve çizim."""
    at = uygulama()
    at.session_state["sihirbaz_turu"] = "Koridorlu bina"
    at.switch_page("app_pages/sihirbaz.py").run()
    assert not at.exception
    at.text_input[0].input("Atatürk İlkokulu").run()
    at.text_area(key="sihirbaz_Koridorlu bina_liste").input(
        "Zemin kat: Müdür odası, Öğretmenler odası, WC" + chr(10) + "1. kat: 101, 102, Kütüphane").run()
    assert any("Zemin kat: 3 yer" in str(x.value) for x in at.success)
    next(b for b in at.button if b.label == "Düzeni oluştur").click().run()
    assert not at.exception
    hedefler = list(at.session_state["kaynak"]["hedefler"]["ad"])
    assert {"Müdür odası", "Kütüphane", "101"} <= set(hedefler)
    assert any("Düzeniniz hazır" in str(x.value) for x in at.success)
    at.switch_page("app_pages/yazdir.py").run()
    assert not at.error


def test_mesafe_metre_olarak_girilir_standart_adima_cevrilir():
    assert bm.metreden_adim(7) == 10 and bm.metreden_adim(0.2) == 1
    assert bm.mesafe_etiketi(10) == "7 m" and bm.mesafe_etiketi(20) == "14 m"
    at = sablon_ac(uygulama(), "Okul (iki katlı, merdivenli ve rampalı)")
    at.session_state["cizim_yol"] = ["hol", "mudur"]
    at.run()
    assert not at.exception
    next(n for n in at.number_input if n.label == "Mesafe (metre)").set_value(14.0).run()
    assert any("≈ 20 standart adım" in str(c.value) for c in at.caption)
    next(b for b in at.button if b.label == "Kaydet").click().run()
    assert not at.exception
    yollar = at.session_state["kaynak"]["yollar"]
    assert int(yollar[(yollar["a"] == "hol") & (yollar["b"] == "mudur")]["adim"].iloc[0]) == 20
    assert ["hol", "mudur"] in at.session_state["plan"]["sabitAdim"]     # sürüklenince değişmez


def test_yarim_is_uyarisiz_silinmez():
    at = sablon_ac(uygulama())                                   # hastane örneği açık
    at.switch_page("app_pages/basla.py").run()
    assert any("Yarım kalan" in str(m.value) for m in at.markdown)
    next(b for b in at.button if b.label == "Boş başla").click().run()
    assert not at.exception
    assert at.session_state["bilgi"]["ad"] == "Örnek Devlet Hastanesi"   # onay verilmeden silinmedi
    assert any(b.label == "Yeni başla" for b in at.button)
    next(b for b in at.button if b.label == "Yeni başla").click().run()
    assert not at.exception
    assert at.session_state["bilgi"]["ad"] == ""


def test_cizimde_virgulle_birden_cok_yer_koridor_boyunca_eklenir():
    at = sablon_ac(uygulama(), "Okul (iki katlı, merdivenli ve rampalı)")
    at.session_state["cizim_secili"] = "hol"
    at.run()
    next(t for t in at.text_input if t.label.startswith("Adı")).input("101, 102, WC")
    next(b for b in at.button if b.label == "Ekle").click().run()
    assert not at.exception
    yollar = at.session_state["kaynak"]["yollar"]
    zincir = {(a, b) for a, b in zip(yollar["a"], yollar["b"], strict=True)}
    assert {("hol", "101"), ("101", "102"), ("102", "wc")} <= zincir
    hedefler = set(at.session_state["kaynak"]["hedefler"]["ad"])
    assert {"101", "102", "WC"} <= hedefler
    wc = at.session_state["kaynak"]["hedefler"].set_index("ad").loc["WC", "anahtarlar"]
    assert "tuvalet" in wc                                     # adından tuvalet olduğu anlaşıldı


def test_ornek_kopya_olarak_acilir_adi_degismeden_yazdirilirsa_uyarilir():
    at = sablon_ac(uygulama(), "Okul (iki katlı, merdivenli ve rampalı)")
    assert any("Bu bir örnek" in str(i.value) for i in at.info)
    at.switch_page("app_pages/yazdir.py").run()
    assert any("hâlâ örnekteki gibi" in str(w.value) for w in at.warning)
    at.switch_page("app_pages/cizim_sayfasi.py").run()
    next(t for t in at.text_input if t.label == "Kurumun adı").input("Cumhuriyet İlkokulu").run()
    assert not any("Bu bir örnek" in str(i.value) for i in at.info)
    at.switch_page("app_pages/yazdir.py").run()
    assert not any("hâlâ örnekteki gibi" in str(w.value) for w in at.warning)
    # Orijinal örnek değişmedi
    assert bm.sablonlar()["Okul (iki katlı, merdivenli ve rampalı)"]["ad"] == "Örnek İlkokulu"


def test_cizimden_yon_tarifi_saga_sola_duz():
    import cizim as cz
    assert cz.donus_metni((0, 1), (0, 1)) == "Düz ilerleyin"
    assert cz.donus_metni((0, 1), (-1, 0)) == "Sola dönün"         # kuzeye giderken batı: sol
    assert cz.donus_metni((0, 1), (1, 0)) == "Sağa dönün"
    assert cz.donus_metni((0, 1), (1, 1)) == "Hafif sağa yönelin"
    assert cz.donus_metni((0, 1), (0, -1)) == "Geri dönün"
    m = {"id": "q-x", "ad": "X", "tur": "kurum", "surum": 1, "giris": "giris",
         "noktalar": [{"id": i, "ad": a} for i, a in [("giris", "Giriş"), ("hol", "Hol"), ("sol", "Sekreterlik"),
                                                       ("sag", "WC"), ("ileri", "Kantin"), ("ust", "Arşiv")]],
         "baglantilar": [], "hedefler": [{"ad": "WC", "nokta": "sag", "tarif": "t", "anahtarlar": ["wc"]}]}
    plan = {"konum": {"giris": [0, 0], "hol": [0, 10], "sol": [-10, 10], "sag": [10, 10], "ileri": [0, 20],
                      "ust": [0, 30]}}
    for a, b in [("giris", "hol"), ("hol", "sol"), ("sag", "hol"), ("hol", "ileri"), ("ileri", "ust")]:
        cz.bagla(m, plan, a, b, 1.0)
    # Elle yazılmış tarif korunur
    m["baglantilar"].append({"a": "giris", "b": "x", "adim": 1, "tarif": "Rampadan çıkın", "geriTarif": "İnin"})
    cz.tarifleri_guncelle(m, plan)
    y = {(b["a"], b["b"]): b for b in m["baglantilar"]}
    assert y[("hol", "sol")]["tarif"] == "Sola dönün"
    assert y[("hol", "sol")]["geriTarif"] == "Geri dönün"       # odadan çıkış
    assert y[("sag", "hol")]["geriTarif"] == "Sağa dönün"        # ters yönde kaydedilmiş yol
    assert y[("hol", "ileri")]["tarif"].startswith("Düz ilerleyin")
    assert y[("ileri", "ust")]["geriTarif"] == "Geri dönün"
    assert y[("ileri", "ust")]["tarif"].startswith("Düz ilerleyin")
    # Arşivden kantine dönüp (tek çocuk) hole doğru: düz
    assert y[("hol", "ileri")]["geriTarif"] == "Düz ilerleyin"
    assert y[("giris", "x")]["tarif"] == "Rampadan çıkın"
    # Kantin bir hedefse ziyaretçi oraya holden gelmiştir: dönüşte geri döner
    m["hedefler"].append({"ad": "Kantin", "nokta": "ileri", "tarif": "t", "anahtarlar": ["kantin"]})
    cz.tarifleri_guncelle(m, plan)
    assert y[("hol", "ileri")]["geriTarif"] == "Geri dönün"


def test_otomatik_tarif_elle_degistirilince_korunur_ve_qrda_oto_isaretlenmez():
    import cizim as cz
    m = {"id": "q-x", "ad": "X", "tur": "kurum", "surum": 1, "giris": "giris",
         "noktalar": [{"id": i, "ad": i} for i in ("giris", "hol", "oda")], "baglantilar": [], "hedefler": []}
    plan = {"konum": {"giris": [0, 0], "hol": [0, 10], "oda": [-10, 10]}}
    cz.bagla(m, plan, "giris", "hol", 1.0)
    cz.bagla(m, plan, "hol", "oda", 1.0)
    cz.tarifleri_guncelle(m, plan)
    q = cz.yonleri_ekle(m, plan)
    assert q["baglantilar"][1]["oto"] is True and q["baglantilar"][1]["yon"] == 270
    m["baglantilar"][1]["tarif"] = "Panoyu geçince soldaki kapı"          # Tablolar sayfasında elle
    cz.tarifleri_guncelle(m, plan)
    assert m["baglantilar"][1]["tarif"] == "Panoyu geçince soldaki kapı"
    assert "oto" not in cz.yonleri_ekle(m, plan)["baglantilar"][1]


def test_nokta_etiketi_kapatilir_ve_tek_etiket_basilir():
    m = bm.sablonlar()["Okul (iki katlı, merdivenli ve rampalı)"]
    tumu = bm.etiket_sayfasi(m)
    assert tumu.count('class="etiket"') == len(m["noktalar"]) - 1         # giriş dışındaki her nokta
    assert bm.etiket_sayfasi(m, haric={"hol"}).count('class="etiket"') == len(m["noktalar"]) - 2
    tek = bm.etiket_sayfasi(m, yalniz="hol")
    assert tek.count('class="etiket"') == 1 and 'class="giris"' not in tek and "Giriş holü" in tek
    at = sablon_ac(uygulama(), "Okul (iki katlı, merdivenli ve rampalı)")
    at.session_state["plan"] = {**at.session_state["plan"], "etiketsiz": ["hol"]}
    at.switch_page("app_pages/yazdir.py").run()
    assert any("1 noktaya etiket asılmayacak" in str(s.value) for s in at.success)


ARDAHAN = "Ardahan Üniversitesi Yenisey Kampüsü (OpenStreetMap yol ağından – sahada doğrulayın)"


def _ardahan():
    return json.loads((Path(__file__).parent / "sablonlar" / "9-ardahan-universitesi.json").read_text(encoding="utf-8"))


def test_haritali_cizimde_konum_cizimden_hesaplanir_qrya_girer_ve_kimlikle_tasinir():
    import cizim as cz
    assert cz.gps_coz("41.130848, 42.786478") == (41.130848, 42.786478)
    assert cz.gps_coz("41.13 42.78") == (41.13, 42.78)
    for bozuk in ("", "abc", "95, 10", "0, 0", None, "41.1"):
        assert cz.gps_coz(bozuk) is None
    sablon = _ardahan()
    plan = sablon.pop("plan")
    gps = cz.dis_gps(plan)
    assert set(gps) == {n["id"] for n in sablon["noktalar"]}
    # Çizim ↔ harita gidiş-dönüş aynı yere varır
    x, y = cz.gpsden_konum(plan, *gps["cami"])
    assert math.dist((x, y), plan["konum"]["cami"]) < 0.05
    qr = cz.yonleri_ekle(sablon, plan)
    giris = next(n for n in qr["noktalar"] if n["id"] == "giris")
    assert (giris["enlem"], giris["boylam"]) == gps["giris"]
    cz.plan_kimlikleri_degistir(plan, {"giris": "ana-kapi"})
    assert "ana-kapi" in cz.dis_gps(plan)


def test_elle_cizim_iki_noktayla_haritaya_oturtulur():
    import cizim as cz
    import harita as hr
    sablon = _ardahan()
    plan = sablon.pop("plan")
    gercek = cz.dis_gps(plan)
    # Kurum kampüsü elle, yamuk ve yarı ölçekte çizmiş olsun: 40° döndürülmüş, 0,5 kat
    aci, k = math.radians(40), 0.5
    elle = {**plan, "konum": {i: [k * (x * math.cos(aci) - y * math.sin(aci)), k * (x * math.sin(aci) + y * math.cos(aci))]
                              for i, (x, y) in plan["konum"].items()}}
    elle.pop("harita")
    elle["gps"] = {i: list(gercek[i]) for i in ("giris", "cami")}
    uyum = hr.haritaya_oturt(sablon, elle)
    assert 0 <= uyum < 1 and "harita" in elle and "gps" not in elle
    for i, (enlem, boylam) in cz.dis_gps(elle).items():
        assert math.dist(((enlem - gercek[i][0]) * 110540, (boylam - gercek[i][1]) * 83800), (0, 0)) < 3, i
    assert hr.haritaya_oturt(sablon, {**plan, "harita": None, "gps": {"giris": [41.1, 42.7]}}) == -1


def test_osmden_kampus_kurulur():
    import osm_kampus as ok
    import cizim as cz
    elemanlar = json.loads((Path(__file__).parent / "test_veri" / "ardahan-osm.json").read_text(encoding="utf-8"))["elements"]
    m = ok.kampus_kur(elemanlar, 662891327, "Ardahan Üniversitesi Yenisey Kampüsü")
    plan = m.pop("plan")
    hatalar, _ = bm.dogrula(m)
    assert hatalar == []
    adlar = {h["ad"] for h in m["hedefler"]}
    assert {"Rektörlük", "Mühendislik Fakültesi", "Konukevi"} <= adlar
    assert not any("Lojman" in a for a in adlar)                       # ziyaret yeri olmayan yapılar atlanır
    assert next(h for h in m["hedefler"] if h["ad"] == "Mühendislik Fakültesi")["kisaAd"] == "Mühendislik"
    # Elle hazırlanan şablonla aynı yol ağı: toplam yürüme mesafesi aynı (kıvrımlara dönemeç eklenince parçalanır)
    sablon = _ardahan()
    assert abs(sum(b["adim"] for b in m["baglantilar"]) - sum(b["adim"] for b in sablon["baglantilar"])) <= len(m["baglantilar"])
    donemecler = [n["id"] for n in m["noktalar"] if n["id"].startswith("donemec-")]
    assert donemecler and set(donemecler) <= set(plan["etiketsiz"])
    assert any(b["tarif"] in ("Sağa dönün", "Sola dönün") for b in m["baglantilar"])
    assert cz.dis_gps(plan)["giris"] == pytest.approx(cz.dis_gps(sablon["plan"])["giris"], abs=1e-4)
    assert all(b["tarif"] for b in m["baglantilar"])
    assert ok.kisa_ad("Ardahan Üniversitesi Rektörlük Binası", "Ardahan Üniversitesi") == "Rektörlük"


def test_cizim_sayfasinda_konum_yazilinca_cizim_haritaya_oturur_ve_tasinir():
    at = sablon_ac(uygulama())   # hastane örneği: haritasız
    at.switch_page("app_pages/cizim_sayfasi.py").run()
    ilk = bm.sablonlar()["Hastane / poliklinik (iki katlı, asansörlü)"]["giris"]

    def konum_yaz(kimlik, metin):
        at.session_state["cizim_secili"] = kimlik
        at.run()
        next(t for t in at.text_input if t.label == "Harita konumu (isteğe bağlı)").set_value(metin)
        next(b for b in at.button if b.label == "Kaydet").click().run()

    konum_yaz(ilk, "41.0000, 29.0000")
    assert "harita" not in at.session_state["plan"]
    import cizim as cz
    dis = cz.gorunum_konumlari(at.session_state["plan"], None)
    noktalar = [ilk, max(dis, key=lambda i: math.dist(dis[i], dis[ilk]))]
    konum_yaz(noktalar[1], "41.0003, 29.0004")
    plan = at.session_state["plan"]
    assert plan.get("harita") and not plan.get("gps")
    assert any(b.label == "Haritadan ayır" for b in at.button)
    assert cz.dis_gps(plan)[noktalar[1]] == pytest.approx((41.0003, 29.0004), abs=2e-5)
    # Haritalı çizimde konum yazmak noktayı taşır
    konum_yaz(noktalar[1], "41.0006, 29.0004")
    assert cz.dis_gps(at.session_state["plan"])[noktalar[1]] == pytest.approx((41.0006, 29.0004), abs=2e-5)


def test_yola_kavsak_eklenir_ve_kosesine_surukleninca_tarif_doner():
    import cizim as cz
    sablon = _ardahan()
    plan = sablon.pop("plan")
    yol = next(y for y in sablon["baglantilar"] if y["b"] == "kultur-merkezi")
    a, b, toplam = yol["a"], yol["b"], yol["adim"]
    yeni = cz.yolu_bol(sablon, plan, a, b)
    assert yeni and yeni in plan["konum"] and yeni in plan["etiketsiz"]
    parcalar = [y for y in sablon["baglantilar"] if yeni in (y["a"], y["b"])]
    assert len(parcalar) == 2 and sum(y["adim"] for y in parcalar) == toplam
    assert not any({y["a"], y["b"]} == {a, b} for y in sablon["baglantilar"])
    assert bm.dogrula(sablon)[0] == []
    # Köşeye sürükle: a'dan önce güneye, sonra batıya gidilen bir L
    ka, kb = plan["konum"][a], plan["konum"][b]
    cz.tasi(sablon, plan, yeni, ka[0], kb[1], cz.olcek(sablon, plan))
    cz.tarifleri_guncelle(sablon, plan)
    ikinci = next(y for y in sablon["baglantilar"] if y["a"] == yeni)
    assert ikinci["tarif"] in ("Sağa dönün", "Sola dönün")
    # Düşey geçiş (merdiven, asansör) bölünmez
    sablon["baglantilar"].append({"a": a, "b": b, "adim": 5, "tur": "merdiven", "tarif": "", "geriTarif": ""})
    sablon["baglantilar"] = [y for y in sablon["baglantilar"] if {y["a"], y["b"]} != {a, b} or y.get("tur")]
    assert cz.yolu_bol(sablon, plan, a, b) is None


def test_bos_cizimde_harita_bolumu_ve_haritadan_kur_formu_gorunur():
    at = uygulama()
    next(b for b in at.button if b.label == "Boş başla" and b.key == "bos-kampus").click().run()
    assert not at.exception
    assert any("Haritadan kurun" in m.value for m in at.markdown)
    assert at.text_input(key="osm-sorgu-cizim").label == "Kurumun adı"
    assert not any(b.label == "Haritadan ayır" for b in at.button)


def test_bos_cizim_aranan_yere_konur():
    import cizim as cz
    import harita as hr
    mekan = {"noktalar": [{"id": "giris", "ad": "Giriş"}], "baglantilar": [], "hedefler": [], "giris": "giris"}
    plan = {"konum": {"giris": [3.0, -2.0]}, "olcek": 1.0}
    hr.cizimi_yere_koy(mekan, plan, 41.13, 42.78)
    assert plan["olcek"] == pytest.approx(8 / bm.STANDART_ADIM_M, abs=1e-3)
    assert cz.dis_gps(plan)["giris"] == pytest.approx((41.13, 42.78), abs=1e-6)
    # Dolu (elle çizilmiş) çizimde ölçek korunur, çizimin ortası aranan yere gelir
    okul = json.loads(json.dumps(bm.sablonlar()["Okul (iki katlı, merdivenli ve rampalı)"]))
    oplan = {"konum": {"a": [0.0, 0.0], "b": [10.0, 0.0]}, "olcek": 2.0}
    hr.cizimi_yere_koy({**okul, "baglantilar": [{"a": "a", "b": "b", "adim": 20}]}, oplan, 40.0, 30.0)
    g = cz.dis_gps(oplan)
    assert oplan["olcek"] == 2.0
    assert (g["a"][0] + g["b"][0]) / 2 == pytest.approx(40.0, abs=1e-5)
    assert math.dist(((g["b"][1] - g["a"][1]) * 85300, 0), (0, 0)) == pytest.approx(10 * 2.0 * 0.7, rel=0.02)


def test_buyuk_kampuste_tek_nokta_etiketi_basilir():
    import osm_kampus as ok
    elemanlar = json.loads((Path(__file__).parent / "test_veri" / "ardahan-osm.json").read_text(encoding="utf-8"))["elements"]
    m = ok.kampus_kur(elemanlar, 662891327, "Ardahan Üniversitesi Yenisey Kampüsü")
    m.pop("plan")
    m["id"] = "q-ardahan"
    # Çok binalı büyük alan: giriş QR'ı 40. sürüme bile sığmaz (yazdırmada adres yöntemi kullanılır)
    for i in range(400):
        m["hedefler"].append({"ad": f"Birim {i} Uzun Adlı Daire Başkanlığı", "nokta": "rektorluk", "tarif": "Burada.",
                              "anahtarlar": [f"birim {i}"]})
    with pytest.raises(ValueError):
        bm.qr_png(bm.qr_verisi(m))
    tek = bm.etiket_sayfasi(m, yalniz="rektorluk")
    assert tek.count('class="etiket"') == 1
