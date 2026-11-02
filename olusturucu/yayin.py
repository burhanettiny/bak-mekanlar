"""Büyük binayı BAK deposunda yayınlama: tek QR'a sığmayan düzen dosyası kurumun sitesi yerine BAK'ın GitHub
Pages deposuna (bak-mekanlar, kurum/ klasörü) yazılır; giriş QR'ı yalnızca adresini taşır. Kurumun web sitesi
gerekmez, dosya koymayı bilmesi gerekmez.

Güvenlik: depoya yalnızca doğrulanmış BAK düzeni yazılır (boyut sınırı, kimlik biçimi). Nokta etiketlerinde
kurumun kimliği açıkça yazdığı için kimliği bilen herkes aynı dosyanın üzerine yazmaya kalkabilir: ilk yayında
rastgele bir yayın anahtarı üretilir, dosyaya yalnızca özeti (SHA-256) yazılır, anahtarın kendisi kurumun
kaydettiği düzen dosyasının planında durur. Güncelleme yalnızca aynı anahtarla yapılabilir.

GitHub erişimi Streamlit sırlarından gelir (.streamlit/secrets.toml ya da Streamlit Cloud → Settings → Secrets):
    [github]
    token = "github_pat_…"     # yalnızca bak-mekanlar deposunda "Contents: Read and write" izni
    depo = "burhanettiny/bak-mekanlar"   # isteğe bağlı
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import urllib.error
import urllib.request

import bak_mekan as bm

DEPO = "burhanettiny/bak-mekanlar"
KLASOR = "kurum"
EN_BUYUK_BAYT = 400_000
_KIMLIK = re.compile(r"^q-[a-z0-9-]{3,70}$")


class YayinHatasi(Exception):
    """Kullanıcıya olduğu gibi gösterilecek açıklama taşır."""


def ayarlar() -> dict | None:
    """GitHub ayarı (token, depo); yoksa None: bu durumda e-postayla gönderme yolu gösterilir."""
    try:
        import streamlit as st
        gh = st.secrets.get("github")
    except Exception:
        return None
    if not gh or not gh.get("token"):
        return None
    return {"token": gh["token"], "depo": gh.get("depo") or DEPO}


def yayin_adresi(mekan_id: str, depo: str = DEPO) -> str:
    sahip, ad = depo.split("/", 1)
    return f"https://{sahip}.github.io/{ad}/{KLASOR}/{mekan_id}.json"


def _ozet(anahtar: str) -> str:
    return hashlib.sha256(anahtar.encode()).hexdigest()


def _istek(yontem: str, url: str, token: str, govde: dict | None = None):
    istek = urllib.request.Request(url, method=yontem, data=json.dumps(govde).encode() if govde else None, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "User-Agent": "BAK-QR-olusturucu/1.0", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(istek, timeout=30) as yanit:
            return json.loads(yanit.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise YayinHatasi(f"BAK deposuna yazılamadı (GitHub {e.code}). Biraz sonra yeniden deneyin.") from e
    except OSError as e:
        raise YayinHatasi("BAK deposuna ulaşılamadı; internet bağlantısını kontrol edin.") from e


def yayinla(mekan: dict, plan: dict, ayar: dict, istek=None) -> str:
    """Düzeni depoya yazar ve dosyanın kalıcı adresini döner. plan["yayinAnahtari"] yoksa üretilir (çağıran planı
    oturuma kaydetmeli: kurum "Kaydet" ile indirdiği dosyada anahtarı saklar)."""
    istek = istek or _istek   # testlerde sahte GitHub
    if not _KIMLIK.match(mekan.get("id") or ""):
        raise YayinHatasi("Kurum kimliği geçersiz; Başla sayfasından yeni bir çalışma açın.")
    hatalar, _ = bm.dogrula(mekan)
    if hatalar:
        raise YayinHatasi("Düzende hata var; önce düzeltin: " + "; ".join(hatalar[:3]))
    anahtar = plan.get("yayinAnahtari") or secrets.token_urlsafe(18)
    icerik = {k: v for k, v in mekan.items() if k != "plan"}
    icerik["yayinOzeti"] = _ozet(anahtar)
    metin = json.dumps(icerik, ensure_ascii=False, separators=(",", ":"))
    if len(metin.encode()) > EN_BUYUK_BAYT:
        raise YayinHatasi("Düzen çok büyük; yerlerin bir kısmını çıkarın.")
    url = f"https://api.github.com/repos/{ayar['depo']}/contents/{KLASOR}/{mekan['id']}.json"
    mevcut = istek("GET", url, ayar["token"])
    govde = {"message": f"Kurum düzeni: {mekan.get('ad', mekan['id'])}",
             "content": base64.b64encode(metin.encode()).decode()}
    if mevcut:
        try:
            eski = json.loads(base64.b64decode(mevcut.get("content") or "").decode())
        except (ValueError, UnicodeDecodeError):
            eski = {}
        if eski.get("yayinOzeti") and eski["yayinOzeti"] != _ozet(anahtar):
            raise YayinHatasi("Bu kimlikle yayınlanmış bir düzen var ve size ait görünmüyor. Kendi kaydettiğiniz "
                              "dosyayı Başla sayfasından açıp yeniden deneyin.")
        govde["sha"] = mevcut.get("sha")
    istek("PUT", url, ayar["token"], govde)
    plan["yayinAnahtari"] = anahtar
    return yayin_adresi(mekan["id"], ayar["depo"])
