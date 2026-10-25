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
    for ad, mekan in bm.sablonlar().items():
        mekan = {**mekan, "id": bm.kimlik_uret(mekan["ad"])}
        hatalar, _ = bm.dogrula(mekan)
        assert hatalar == [], ad
        assert bm.qr_olustur(bm.qr_verisi(mekan)).version <= bm.ONERILEN_EN_BUYUK_QR_SURUMU, ad


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


def test_uygulama_sablonla_acilir_ve_qr_uretir():
    at = AppTest.from_file("streamlit_app.py", default_timeout=30).run()
    assert not at.exception
    at.selectbox[0].select("Hastane / poliklinik (iki katlı, asansörlü)")
    at.button[0].click().run()
    assert not at.exception
    assert any("Düzen geçerli" in str(s.value) or "QR hazır" in str(s.value) for s in at.success)
    assert at.text_input[0].value == "Örnek Devlet Hastanesi"


def test_bos_sayfada_eksikler_soylenir():
    at = AppTest.from_file("streamlit_app.py", default_timeout=30).run()
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
