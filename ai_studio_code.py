import io, os
import pandas as pd
import streamlit as st
import manifest_core as mc

st.set_page_config(page_title="Export Manifest Auto-Coder", layout="wide")
CS_PATH = "coding_sheet.docx"  # commit your coding sheet to the repo under this name to auto-load it

def gate():
    try:
        pw = st.secrets["APP_PASSWORD"]
    except Exception:
        st.error("Set APP_PASSWORD under Settings > Secrets in Streamlit Cloud, then reload.")
        return False
    if st.session_state.get("ok"):
        return True
    st.subheader("🔒 Manifest Coding System")
    if st.text_input("Office access password", type="password") == pw:
        st.session_state["ok"] = True
        st.rerun()
    return False

if not gate():
    st.stop()

ss = st.session_state
ss.setdefault("rows", []); ss.setdefault("seen", set())
st.title("🚢 Export Manifest Auto-Coder")

with st.sidebar:
    cs = st.file_uploader("1. Coding sheet (.docx)", type=["docx"])
    tpl = st.file_uploader("2. Excel template (.xlsx), optional", type=["xlsx"])
    month = st.selectbox("Month", ["Auto (from departure date)"] + mc.MONTHS)
if cs is not None:
    open(CS_PATH, "wb").write(cs.getvalue())
if os.path.exists(CS_PATH) and not mc.SHEET["ports"]:
    mc.load_coding_sheet(CS_PATH)
if not mc.SHEET["ports"]:
    st.info("Upload the coding sheet in the sidebar to begin."); st.stop()
st.caption(f"Coding sheet: {len(mc.SHEET['ports'])} ports, {len(mc.SHEET['pairs'])} line/agent pairs, {len(mc.SHEET['codes'])} commodity codes")

files = st.file_uploader("3. Export manifests (PDF)", type=["pdf"], accept_multiple_files=True)
if files and st.button("🚀 Process manifests", type="primary"):
    for f in files:
        key = (f.name, f.size)
        if key in ss.seen:
            st.warning(f"{f.name}: already processed, skipped"); continue
        try:
            rows, n, msg = mc.process_pdf(f.name, f.getvalue(), None if month.startswith("Auto") else month)
        except Exception as e:
            st.error(f"{f.name}: {e}"); continue
        if msg: st.warning(msg)
        if rows:
            ss.seen.add(key); ss.rows += rows
            st.success(f"{f.name}: {len(rows)} records from {n} B/L numbers")

if ss.rows:
    df = pd.DataFrame([{**{k: r[k] for k in mc.FIELDS}, "FLAGS": "; ".join(mc.validate(r)),
                        "SOURCE": r["SOURCE"], "ORIGINAL": r["ORIGINAL"], "CARGO": r["CARGO"]} for r in ss.rows])
    df.insert(0, "APPROVE", df["FLAGS"] == "")
    st.subheader("Review (edit any cell, tick APPROVE to include)")
    ed = st.data_editor(df, width="stretch", hide_index=True, disabled=["FLAGS", "SOURCE", "ORIGINAL", "CARGO"],
        column_config={"CONTYPE": st.column_config.SelectboxColumn(options=sorted(mc.TYPES)),
                       "TONNAGES": st.column_config.NumberColumn(format="%.2f", step=0.01),
                       "CONTQTY": st.column_config.NumberColumn(step=1)})
    c1, c2, c3 = st.columns(3)
    c1.metric("Records", len(ed)); c2.metric("Need review", int((df["FLAGS"] != "").sum())); c3.metric("Approved", int(ed["APPROVE"].sum()))
    out, blocked = [], 0
    for r in ed[ed["APPROVE"]].to_dict("records"):
        r["FLAGS"] = []
        if mc.validate(r): blocked += 1; continue   # hard errors (blank field / bad CONTYPE) can never be exported
        r["TONNAGES"] = round(float(r["TONNAGES"]), 2); r["CONTQTY"] = int(r["CONTQTY"]); out.append(r)"""Drop-in fixes for the Ghana Export Manifest Auto-Coder.
Replaces: PORT_MAP/COUNTRY_MAP, resolve_port_info, classify_commodity, normalize_container,
parse_maersk, the carrier router, rotation handling and the Excel export.
Rules: coding sheet is the authority; nothing is invented; unknowns are left blank and flagged."""
import re, io
from decimal import Decimal, ROUND_HALF_UP
import fitz  # PyMuPDF
from docx import Document
from openpyxl import load_workbook

TYPES = {"20D", "40D", "45D", "20R", "40R", "45R"}
FIELDS = ["MONTH", "SHIP", "SHIP LINE", "AGENT", "PORT", "CTRY", "RANGE", "CONTYPE", "CONTQTY", "COMMODITY", "TONNAGES"]
MONTHS = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
SHEET = {"ports": [], "pairs": [], "codes": set()}

# ---------- coding sheet (the single source of truth) ----------
def load_coding_sheet(src):
    d = Document(src if not isinstance(src, bytes) else io.BytesIO(src))
    ports, pairs = [], []
    for t in d.tables:
        for r in t.rows:
            c = [x.text.strip() for x in r.cells]
            if len(c) >= 5 and all(re.fullmatch(r"[A-Z]{2}", c[i]) for i in (1, 3, 4)):
                ports.append(dict(name=c[0], pc=c[1], country=c[2], cc=c[3], rng=c[4]))
            elif len(c) == 2 and c[0] and c[1] and not c[0].upper().startswith("SHIPPING"):
                pairs.append(dict(agent=c[0], line=c[1]))
    codes = set(re.findall(r"\d+\.\s*([A-Z]{3})\b", "\n".join(p.text for p in d.paragraphs)))
    SHEET.update(ports=ports, pairs=pairs, codes=codes)
    return SHEET

def _pn(s):
    return re.sub(r"\*+", "", s.upper()).strip()

def _names(n):
    return [x.strip() for x in re.split(r"/|\(I\.?\s?E\.?\s*|\)", _pn(n)) if x.strip()]

def resolve_port_info(pod_raw, full_chunk="", use_web_search=False):
    """Returns (PORT code, CTRY code, RANGE) from the coding sheet, or ('','','') if not found/ambiguous."""
    parts = [p.strip() for p in re.split(r",", pod_raw.upper()) if p.strip()]
    city, ctry = (parts[0] if parts else ""), (parts[-1] if len(parts) > 1 else "")
    hit = [p for p in SHEET["ports"] if city in _names(p["name"])]
    k = re.sub(r"[^A-Z]", "", ctry)
    narrowed = [p for p in hit if k and (k in re.sub(r"[^A-Z]", "", p["country"].upper()) or re.sub(r"[^A-Z]", "", p["country"].upper()) in k)]
    hit = narrowed or hit
    if len(hit) != 1:
        return ("", "", "")
    return (hit[0]["pc"], hit[0]["cc"], hit[0]["rng"])

def agent_for(line_key):
    for p in SHEET["pairs"]:
        if line_key.upper() in p["line"].upper():
            return p["line"], p["agent"]
    return "", ""

# ---------- containers, weights, commodities ----------
def normalize_container(text):
    t = str(text).upper()
    m = re.search(r"(?<!\d)(20|40|45)(?!\d)\s*(?:'|FT|FEET)?\s*([A-Z]*)", t)
    if not m:
        return ""
    size, rest = m.group(1), m.group(2) + " " + t[m.end():]
    if re.search(r"\b(OPEN|FLAT|TANK|OT|FR|BULK)", rest):
        return ""
    if re.search(r"REEF|\bRF\b|\bRE\b|\bRH\b|\bHR\b|^R[FHE]?\b", rest):
        return size + "R"
    if re.search(r"DRY|\bGP\b|\bHC\b|\bHQ\b|\bST\b|\bDV\b|\bDC\b|^(HC|HQ|GP|ST|DV)\b", rest):
        return size + "D"
    return ""

def to_mt(value, unit):
    """Exact conversion. Unit must be stated: KG(S) -> /1000, MT(S)/TON(NE)(S) -> unchanged. Never guessed from size."""
    v = Decimal(str(value).replace(",", "").strip())
    u = unit.upper().strip()
    if u in ("KG", "KGS", "KILOS", "KILOGRAMS"):
        v = v / 1000
    elif u not in ("MT", "MTS", "TON", "TONS", "TONNE", "TONNES"):
        return None
    return float(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

RULES = [  # (regex with word boundaries, code); first match wins, most specific first
    (r"\bCOCOA BEANS?\b|\bRAW COCOA\b", "LCB"), (r"\bCOCOA (BUTTER|CAKE|POWDER|LIQUOR|MASS|PASTE|NIBS?|WASTE)\b|\bCHOCOLATE\b", "LCP"),
    (r"\bBANANAS?\b", "LBN"), (r"\bPINEAPPLES?\b", "LPN"), (r"\bYAMS?\b", "LYM"), (r"\bCASHEW", "LCA"), (r"\bSHEA ?NUTS?\b|\bKARITE\b", "LSH"),
    (r"\bCANNED (TUNA|FISH)\b", "LFS"), (r"\bTUNA\b|\bFROZEN FISH\b|\bSKIPJACK\b|\bYELLOWFIN\b", "LFI"),
    (r"\bROUND LOGS?\b|\bTEAK POLES?\b|\bROUGH SQUARES?\b", "LLG"), (r"\bSAWN\b|\bLUMBER\b|\bTEAK (SAWN|IN CONTAINERS?)\b", "LST"),
    (r"\bFURNITURE\b|\bMOULDING\b|\bDOORS?\b", "LFW"), (r"\bSCRAP\b", "LMS"), (r"\bRUBBER\b", "LRB"),
    (r"\bALUMINI?UM INGOTS?\b", "LAL"), (r"\bCOFFEE\b", "LCF"), (r"\bCOLA NUTS?\b", "LCN"),
    (r"\bVEHICLES?\b|\bUSED CARS?\b|\bAUTOS?\b", "LVE"), (r"\bTRUCKS?\b|\bFORKLIFTS?\b|\bTRACTORS?\b", "LTR"),
    (r"\bMACHINE(S|RY)?\b|\bEQUIPMENT\b|\bSPARE PARTS\b|\bPUMPS?\b|\bENGINES?\b", "LME"),
    (r"\bCHEMICALS?\b|\bRESIN\b|\bZINC OXIDE\b|\bPOLYETHYLENE\b", "LCH"),
    (r"\bTEXTILES?\b|\bGARMENTS?\b|\bCOSMETICS?\b|\bSOAPS?\b|\bJUICE\b|\bBEVERAGES?\b|\bSUGAR\b|\bBISCUITS?\b|\bFOOTWEAR\b|\bFABRICS?\b", "LPE"),
    (r"\bSEEDS\b|\bGINGER\b|\bTOBACCO\b|\bSESAME\b|\bCHARCOAL\b|\bPALM KERNELS?\b", "LNO"),
]

def classify_with_flag(desc, hs=""):
    t = f"{desc} {hs}".upper()
    for rx, code in RULES:
        if re.search(rx, t) and (not SHEET["codes"] or code in SHEET["codes"]):
            return code, ""
    return "LGC", "Commodity not recognised; LGC (general cargo) used. Review"

def classify_commodity(desc, hs_code="", use_web_search=False):
    return classify_with_flag(desc, hs_code)[0]

# ---------- orientation ----------
def is_maersk_text(txt):
    return bool(re.search(r"\bMAEU\b|ML Export Manifest|\bMAERSK\b", txt, re.I))

def corrected_rotation(page, maersk):
    """Maersk: known sideways layout, add 90 deg clockwise. Others: use Tesseract OSD (only for image-only pages)."""
    if maersk:
        return (page.rotation + 90) % 360
    if not page.get_text("text").strip():
        try:
            import pytesseract
            from PIL import Image
            pix = page.get_pixmap(dpi=100)
            osd = pytesseract.image_to_osd(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
            return (page.rotation + int(re.search(r"Rotate: (\d+)", osd).group(1))) % 360
        except Exception:
            pass
    return page.rotation

def page_text(page, maersk=False):
    """Works on an in-memory copy; the uploaded file is never modified."""
    page.set_rotation(corrected_rotation(page, maersk))
    txt = page.get_text("text")
    if txt.strip():
        return txt
    try:
        import pytesseract
        from PIL import Image
        pix = page.get_pixmap(dpi=200)
        return pytesseract.image_to_string(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
    except Exception:
        return ""

# ---------- carrier router (no more "ONE"/"PIL" substring accidents; unknown = flagged, never defaulted to Maersk) ----------
def detect_carrier(txt):
    if is_maersk_text(txt): return "MAERSK"
    if re.search(r"OCEAN NETWORK EXPRESS|\bONEY[A-Z0-9]{6,}", txt): return "ONE"
    if re.search(r"PACIFIC INTERNATIONAL LINES?|\bPIL\b[^\n]{0,20}(MANIFEST|LINES)|KOTA SYDNEY", txt): return "PIL"
    if re.search(r"GOLD STAR LINE|GOSUTEM", txt): return "GOLDSTAR"
    if re.search(r"ARKAS|MICHEL A\b", txt): return "ARKAS"
    if re.search(r"COSCO SHIPPING|\bCOSU\d", txt): return "COSCO"
    if re.search(r"EOLIS|AFRICA EXPRESS LINE|TEMPOV", txt): return "AEL"
    return None

# ---------- Maersk parser (word coordinates; tested on the Boston manifest) ----------
def _lines(ws):
    out = []
    for w in sorted(ws, key=lambda w: (round(w[1]), w[0])):
        if out and abs(out[-1][0] - w[1]) < 2.5: out[-1][1].append(w)
        else: out.append([w[1], [w]])
    return [" ".join(x[4] for x in sorted(l, key=lambda x: x[0])) for _, l in out]

def parse_maersk_pdf(doc, fname="", month_override=None):
    rows, P = [], []
    for pn, pg in enumerate(doc, 1):
        # PyMuPDF returns word boxes in the unrotated page space, which for Maersk IS the upright reading layout
        W = pg.get_text("words")
        hdr = next((w for w in W if w[4] == "Parties"), None)
        y0 = hdr[1] + 3 if hdr else 0
        g = lambda t: next((w for w in W if w[4] == t), None)
        mk, ds, gr, me = g("Marks"), g("Description"), g("Gross"), g("Meassurement")
        body = [w for w in W if w[1] > y0 and w[4] != "Manifest"]
        mx = (mk[0] if mk else 150) - 3
        dx, mex = (ds[0] - 3 if ds else 0), (me[0] - 3 if me else 9999)
        rowtxt = lambda w: " ".join(m[4] for m in sorted([m for m in body if abs(m[1] - w[1]) < 3 and dx <= m[0] < mex], key=lambda m: m[0]))
        # a real B/L number sits in the left column and has the "N X 40 DRY" container line on its row
        bls = sorted([w for w in body if re.fullmatch(r"\d{9}", w[4]) and w[0] < mx - 20 and re.match(r"\d+ X \d{2}", rowtxt(w))], key=lambda w: w[1])
        P.append(dict(p=pn, W=W, body=body, bls=bls, mx=mx, dx=dx, mex=mex, ds=ds[0] - 3 if ds else 0, gr=gr[0] - 3 if gr else 9999))
    ship = date = ""
    for q in P:
        v = next((w for w in q["W"] if w[4] == "Vessel"), None)
        vy = next((w for w in q["W"] if w[4] == "Voyage"), None)
        if v and vy:
            ship = " ".join(w[4] for w in sorted(q["W"], key=lambda w: w[0]) if abs(w[1] - v[1] - 6) < 2.5 and v[0] - 3 <= w[0] < vy[0] - 3)
            date = next((w[4] for w in q["W"] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", w[4]) and abs(w[1] - vy[1] - 6) < 2.5), "")
            break
    month = month_override or (MONTHS[int(date[5:7]) - 1] if date else "")
    line, agent = agent_for("MAERSK")
    for i, q in enumerate(P):
        for k, bl in enumerate(q["bls"]):
            nx = q["bls"][k + 1] if k + 1 < len(q["bls"]) else None
            B = [w for w in q["body"] if w[1] >= bl[1] - 2 and (not nx or w[1] < nx[1] - 2)]
            if not nx and i + 1 < len(P):
                f2 = P[i + 1]["bls"][0] if P[i + 1]["bls"] else None
                B += [w for w in P[i + 1]["body"] if not f2 or w[1] < f2[1] - 2]
            r = dict(MONTH=month, SHIP=ship, **{"SHIP LINE": line, "AGENT": agent}, PORT="", CTRY="", RANGE="", CONTYPE="", CONTQTY="",
                     COMMODITY="", TONNAGES="", SOURCE=f"{fname} p.{q['p']} B/L {bl[4]}", CARGO="", ORIGINAL="", FLAGS=[])
            row = " ".join(w[4] for w in sorted([w for w in B if abs(w[1] - bl[1]) < 3 and q["dx"] <= w[0] < q["mex"]], key=lambda w: w[0]))
            m = re.match(r"(\d+)\s*X\s*(\d{2})\s*([A-Z]+)\b.*?([\d,]*\.?\d+)\s*(KGS?|MTS?)\b", row)
            leftcol = _lines([w for w in B if w[0] < q["mx"]])
            vd = next((re.search(r"Vessel Disch:\s*(.+)", l) for l in leftcol if "Vessel Disch:" in l), None)
            if vd: r["PORT"], r["CTRY"], r["RANGE"] = resolve_port_info(vd.group(1))
            if not vd: r["FLAGS"].append("Port of discharge (Vessel Disch) not found")
            elif not r["PORT"]: r["FLAGS"].append(f"Port '{vd.group(1)}' not found/ambiguous in coding sheet")
            if not m:
                r["FLAGS"].append("Container line / gross weight not readable")
            else:
                r["ORIGINAL"] = f"{m.group(1)} X {m.group(2)} {m.group(3)} | gross {m.group(4)} {m.group(5)}"
                r["CONTQTY"] = int(m.group(1)); r["CONTYPE"] = normalize_container(m.group(2) + m.group(3))
                if not r["CONTYPE"]: r["FLAGS"].append(f"Unsupported container '{m.group(2)} {m.group(3)}'")
                r["TONNAGES"] = to_mt(m.group(4), m.group(5)) or ""
                dl = _lines([w for w in B if q["ds"] <= w[0] < q["gr"]])
                s = sum(float(x.replace(",", "")) for l in dl for x in re.findall(r"([\d,]+\.?\d*)\s*KGS\s+[\d.]+\s*CBM", l))
                if s and abs(s - float(m.group(4).replace(",", ""))) > 1: r["FLAGS"].append(f"Per-container weights total {s:.3f} KGS vs header {m.group(4)}")
                nc = len({w[4] for w in B if re.fullmatch(r"[A-Z]{4}\d{7}", w[4])})
                if nc and nc != r["CONTQTY"]: r["FLAGS"].append(f"{nc} container numbers listed vs quantity {r['CONTQTY']}")
                cg = [l for l in dl[1:] if not re.fullmatch(r"[A-Z]{4}\d{7}", l) and not re.search(r"KGS|CBM", l)
                      and not re.match(r"\d+\s*(CARTONS?|PACKAGES|PKGS|BAGS|PALLETS|DRUMS)\b", l, re.I)]
                r["CARGO"] = " | ".join(cg[:3])
                r["COMMODITY"], fl = classify_with_flag(" ".join(cg))
                if fl: r["FLAGS"].append(fl)
            if not month: r["FLAGS"].append("Month not found")
            if not ship: r["FLAGS"].append("Vessel not found")
            if not line: r["FLAGS"].append("Maersk line/agent not in coding sheet")
            rows.append(r)
    return rows, sum(len(q["bls"]) for q in P)

# ---------- validation + export ----------
def validate(r):
    f = list(r.get("FLAGS", []))
    for k in FIELDS:
        if r.get(k) in ("", None): f.append(f"{k} missing")
    if r.get("CONTYPE") not in TYPES: f.append("CONTYPE must be one of 20D/40D/45D/20R/40R/45R")
    return sorted(set(f), key=f.index)

def export_to_template(rows, template_bytes=None):
    """Appends rows to the user's template (columns found by heading, formats kept); TONNAGES = number, 0.00."""
    if template_bytes:
        wb = load_workbook(io.BytesIO(template_bytes)); ws = wb.worksheets[0]
        hr = next((c.row for c in ws["A"] if str(c.value or "").strip().upper() == "MONTH"), 1)
        col = {str(c.value).strip().upper(): c.column for c in ws[hr] if c.value}
        last = max([c.row for c in ws["A"] if c.value not in (None, "")] + [hr])
        known = {}
        for (c,) in ws.iter_rows(min_row=hr + 1, min_col=col["AGENT"], max_col=col["AGENT"]):  # reuse the template's own agent spelling
            if c.value: known[re.sub(r"[^A-Z]", "", str(c.value).upper())] = c.value
    else:
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.append(FIELDS)
        hr, col, last, known = 1, {h: i + 1 for i, h in enumerate(FIELDS)}, 1, {}
    for i, r in enumerate(rows, 1):
        for h in FIELDS:
            v = r[h]
            if h == "AGENT": v = known.get(re.sub(r"[^A-Z]", "", str(v).upper()), v)
            c = ws.cell(row=last + i, column=col[h], value=v)
            if h == "TONNAGES": c.value = float(v); c.number_format = "0.00"
    out = io.BytesIO(); wb.save(out); return out.getvalue()


# ---------- one call per uploaded PDF (UI-free, so it can be tested) ----------
def process_pdf(name, data, month=None):
    """Returns (rows, expected_count, message). Unknown carriers are reported, never guessed."""
    doc = fitz.open(stream=data, filetype="pdf")
    head = "\n".join(p.get_text("text") for p in doc[:3]) or "\n".join(page_text(p) for p in list(doc)[:3])
    car = detect_carrier(head)
    if not head.strip():
        return [], 0, f"{name}: no readable text (scan) and OCR returned nothing"
    if car == "MAERSK":
        rows, n = parse_maersk_pdf(doc, name, month)
        return rows, n, "" if len(rows) == n else f"{name}: found {n} B/L numbers but built {len(rows)} rows"
    return [], 0, f"{name}: carrier {car or 'not recognised'}. No tested parser yet; send a sample so it can be added"

    if blocked: st.error(f"{blocked} approved row(s) still have blank fields or an invalid CONTYPE and were left out.")
    if out:
        st.download_button("📥 Download Excel", mc.export_to_template(out, tpl.getvalue() if tpl else None),
            file_name="EXPORT_MANIFEST_CODING.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
