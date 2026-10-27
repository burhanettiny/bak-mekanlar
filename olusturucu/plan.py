"""Bina düzeninin 2D planı (Graphviz DOT).

Sihirbazla oluşturulan binalarda noktaların gerçek yerleşimi bilinir (adım birimiyle konum); plan ona göre
çizilir. Elle girilen düzenlerde konum yoktur; Graphviz katları kutulara ayırıp yerleşimi kendisi yapar.
"""

from __future__ import annotations

import html

ZEMIN = "#0B1F3A"
SARI = "#FFD400"
RENKLER = {"merdiven": "#E65100", "yuruyen-merdiven": "#E65100", "asansor": "#6A1B9A", "rampa": "#2E7D32"}
OLCEK = 0.3    # konum birimi → inç


def _kacis(metin: str) -> str:
    return html.escape(str(metin), quote=True)


def _kat_adi(kat: int) -> str:
    if kat == 0:
        return "Zemin kat"
    return "Bodrum kat" if kat == -1 else (f"Eksi {-kat}. kat" if kat < 0 else f"{kat}. kat")


def plan_dot(mekan: dict, plan: dict | None = None) -> str:
    plan = plan or {}
    konum: dict = plan.get("konum") or {}
    raflar: dict = plan.get("raflar") or {}
    katlar = {n["id"]: n.get("kat", 0) or 0 for n in mekan["noktalar"]}
    hedef_adlari: dict[str, list[str]] = {}
    for h in mekan["hedefler"]:
        hedef_adlari.setdefault(h["nokta"], []).append(h.get("kisaAd") or h["ad"])
    sabit = bool(konum) and all(n["id"] in konum for n in mekan["noktalar"])

    satirlar = [
        "digraph plan {",
        f'  graph [layout={"neato" if sabit else "dot"}, rankdir=LR, bgcolor="transparent", '
        'fontname="Helvetica", pad=0.3, splines=true, nodesep=0.35, ranksep=0.5, '
        f'overlap={"true" if sabit else "false"}];',
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, '
        'fillcolor="#FFFFFF", color="#90A4AE", penwidth=1.2, margin="0.12,0.06"];',
        '  edge [fontname="Helvetica", fontsize=9, color="#78909C", fontcolor="#455A64", arrowsize=0.6];',
    ]

    def dugum(n: dict) -> str:
        nid = n["id"]
        hedefler = hedef_adlari.get(nid, [])
        hedef_var = bool(hedefler)
        if nid in raflar and len(hedefler) > 1:
            hedefler = [f"{len(hedefler)} reyon"]
        # "Müdür odası kapısı" kutusunda "Müdür odası" ikinci kez yazılmaz
        hedefler = [h for h in hedefler if h.lower() not in n["ad"].lower()]
        alt = "<BR/>".join(f'<FONT POINT-SIZE="9" COLOR="#5D4037">{_kacis(h)}</FONT>' for h in hedefler[:4])
        if len(hedefler) > 4:
            alt += f'<BR/><FONT POINT-SIZE="9" COLOR="#5D4037">+{len(hedefler) - 4} yer</FONT>'
        etiket = f"<<B>{_kacis(n['ad'])}</B>{'<BR/>' + alt if alt else ''}>"
        if nid == mekan["giris"]:
            ozellik = f'fillcolor="{ZEMIN}", fontcolor="{SARI}", color="{ZEMIN}", penwidth=2'
            etiket = f"<<B>{_kacis(n['ad'])}</B><BR/><FONT POINT-SIZE='9'>GİRİŞ QR</FONT>>".replace("'", '"')
        elif hedef_var:
            ozellik = 'fillcolor="#FFF8D6", color="#C9A400"'
        else:
            ozellik = 'fillcolor="#FFFFFF"'
        konum_ozelligi = ""
        if sabit:
            x, y = konum[nid]
            konum_ozelligi = f', pos="{x * OLCEK:.2f},{y * OLCEK:.2f}!"'
        return f'  "{_kacis(nid)}" [label={etiket}, {ozellik}{konum_ozelligi}];'

    if sabit:
        for n in mekan["noktalar"]:
            satirlar.append(dugum(n))
        # Birden çok katta her katın soluna kat adı
        if len(set(katlar.values())) > 1:
            for kat in sorted(set(katlar.values())):
                kat_konumlari = [konum[i] for i, k in katlar.items() if k == kat]
                x = min(k[0] for k in kat_konumlari) - 7
                y = sum(k[1] for k in kat_konumlari) / len(kat_konumlari)
                satirlar.append(f'  "kat-etiketi-{kat}" [shape=plaintext, style="", label=<<B>{_kat_adi(kat)}</B>>, '
                                f'fontsize=14, fontcolor="{ZEMIN}", pos="{x * OLCEK:.2f},{y * OLCEK:.2f}!"];')
    else:
        # Konum yoksa her kat ayrı kutuda
        for kat in sorted(set(katlar.values())):
            satirlar.append(f'  subgraph "cluster_{kat}" {{ label="{_kat_adi(kat)}"; style="rounded,dashed"; '
                            'color="#B0BEC5"; fontcolor="#455A64";')
            satirlar += ["  " + dugum(n) for n in mekan["noktalar"] if katlar[n["id"]] == kat]
            satirlar.append("  }")

    # Market rafları: koridor başının üstünde iki taraflı raf kutusu
    for nid, raf in raflar.items():
        if nid not in katlar:
            continue
        sol, sag = _kacis(raf.get("sol") or "—"), _kacis(raf.get("sag") or "—")
        rid = f"raf-{nid}"
        konum_ozelligi = ""
        if sabit and nid in konum:
            x, y = konum[nid]
            boy = plan.get("koridorBoyu", 15)
            konum_ozelligi = f', pos="{x * OLCEK:.2f},{(y + boy / 2) * OLCEK:.2f}!"'
        satirlar.append(
            f'  "{rid}" [shape=plain, label=<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4" '
            f'COLOR="#90A4AE"><TR><TD BGCOLOR="#E3F2FD"><FONT POINT-SIZE="9"><B>Sol:</B> {sol}</FONT></TD></TR>'
            f'<TR><TD BGCOLOR="#ECEFF1"><FONT POINT-SIZE="8">▲ koridor ▲</FONT></TD></TR>'
            f'<TR><TD BGCOLOR="#E3F2FD"><FONT POINT-SIZE="9"><B>Sağ:</B> {sag}</FONT></TD></TR></TABLE>>{konum_ozelligi}];')
        satirlar.append(f'  "{_kacis(nid)}" -> "{rid}" [style=dotted, arrowhead=none];')

    for b in mekan["baglantilar"]:
        tur = b.get("tur", "yuru")
        renk = RENKLER.get(tur, "#78909C")
        etiket = {"merdiven": "merdiven", "yuruyen-merdiven": "yürüyen merdiven",
                  "asansor": "asansör"}.get(tur, f'{b["adim"]} adım')
        if tur == "merdiven" and b.get("basamak"):
            etiket = f'merdiven · {b["basamak"]} basamak'
        ok = "normal" if b.get("tekYon") else "none"
        cizgi = "dashed" if tur in ("merdiven", "yuruyen-merdiven", "asansor") else "solid"
        satirlar.append(f'  "{_kacis(b["a"])}" -> "{_kacis(b["b"])}" [label="{_kacis(etiket)}", color="{renk}", '
                        f'fontcolor="{renk}", style={cizgi}, arrowhead={ok}, penwidth={2 if tur != "yuru" else 1.3}];')
    satirlar.append("}")
    return "\n".join(satirlar)
