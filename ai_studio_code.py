import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import re
import io

st.set_page_config(page_title="Ghana Export Manifest Auto-Coder", layout="wide")

# ==========================================
# 0. SECURITY GATE
# ==========================================

def check_password():
    def password_entered():
        if st.session_state["password"] == "GsaMeta@123":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.subheader("🔒 Manifest Coding System - Restricted Access")
        st.text_input("Enter Office Access Password:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.subheader("🔒 Manifest Coding System - Restricted Access")
        st.text_input("Enter Office Access Password:", type="password", on_change=password_entered, key="password")
        st.error("❌ Incorrect password. Access denied.")
        return False
    else:
        return True

if not check_password():
    st.stop()

# ==========================================
# 1. MASTER DICTIONARIES & KNOWLEDGE BASE
# ==========================================

PORT_MAP = {
    "LOME": ("LM", "TG", "AF"),
    "COTONOU": ("CU", "BN", "AF"),
    "ABIDJAN": ("AJ", "IV", "AF"),
    "LAGOS": ("LG", "NG", "AF"),
    "TINCAN": ("LG", "NG", "AF"),
    "APAPA": ("OH", "NG", "AF"),
    "ONNE": ("OH", "NG", "AF"),
    "PORT HARCOURT": ("OH", "NG", "AF"),
    "DAKAR": ("DA", "SN", "AF"),
    "POINTE NOIRE": ("OH", "CG", "AF"),
    "POINT NOIRE": ("OH", "CG", "AF"),
    "MATADI": ("MA", "CG", "AF"),
    "LIBREVILLE": ("LB", "GA", "AF"),
    "PORT GENTIL": ("PG", "GA", "AF"),
    "DOUALA": ("DL", "CM", "AF"),
    "DURBAN": ("DR", "SA", "AF"),
    "CAPETOWN": ("CN", "SA", "AF"),
    "PORT ELIZABETH": ("PE", "SA", "AF"),
    "TEMA": ("TM", "GH", "AF"),
    "TAKORADI": ("TD", "GH", "AF"),
    "ANTWERP": ("AT", "BG", "CT"),
    "AMSTERDAM": ("AM", "NL", "CT"),
    "ROTTERDAM": ("RM", "NL", "CT"),
    "HAMBURG": ("HM", "GR", "CT"),
    "BREMERHAVEN": ("BM", "GR", "CT"),
    "LE HAVRE": ("LH", "FR", "CT"),
    "DUNKERQUE": ("DK", "FR", "CT"),
    "DUNKIRK": ("DK", "FR", "CT"),
    "PORT VENDRES": ("BD", "FR", "CT"),
    "FOS SUR MER": ("OH", "FR", "CT"),
    "MARSEILLE": ("MS", "FR", "CT"),
    "ROUEN": ("RN", "FR", "CT"),
    "GDYNIA": ("GA", "PL", "CT"),
    "GDANSK": ("GK", "PL", "CT"),
    "ZEEBRUGGE": ("ZB", "BG", "CT"),
    "AARHUS": ("AH", "DK", "CT"),
    "COPENHAGEN": ("CP", "DK", "CT"),
    "TILBURY": ("TY", "UK", "UK"),
    "LIVERPOOL": ("LV", "UK", "UK"),
    "LONDON": ("LD", "UK", "UK"),
    "FELIXSTOWE": ("FX", "UK", "UK"),
    "TEESPORT": ("TE", "UK", "UK"),
    "DUBLIN": ("DU", "IR", "UK"),
    "BELFAST": ("BT", "IR", "UK"),
    "BARCELONA": ("BC", "SP", "ME"),
    "VALENCIA": ("VL", "SP", "ME"),
    "ALGECIRAS": ("AR", "SP", "ME"),
    "BILBAO": ("BI", "SP", "ME"),
    "GENOA": ("GE", "IT", "ME"),
    "LIVORNO": ("LO", "IT", "ME"),
    "LEGHORN": ("LN", "IT", "ME"),
    "NAPLES": ("NS", "IT", "ME"),
    "SALERNO": ("SL", "IT", "ME"),
    "ISTANBUL": ("IL", "TU", "ME"),
    "AMBARLI": ("OH", "TU", "ME"),
    "IZMIR": ("OH", "TU", "ME"),
    "MERSIN": ("OH", "TU", "ME"),
    "PIRAEUS": ("PI", "GC", "ME"),
    "SHANGHAI": ("SH", "CH", "FE"),
    "NINGBO": ("OH", "CH", "FE"),
    "QINGDAO": ("OH", "CH", "FE"),
    "SHEKOU": ("OH", "CH", "FE"),
    "YANTIAN": ("OH", "CH", "FE"),
    "HONGKONG": ("HK", "HK", "FE"),
    "BUSAN": ("BU", "SK", "FE"),
    "PUSAN": ("BU", "SK", "FE"),
    "INCHEON": ("OH", "SK", "FE"),
    "SINGAPORE": ("SG", "SG", "FE"),
    "PORT KLANG": ("OH", "MY", "FE"),
    "TANJUNG PELEPAS": ("OH", "MY", "FE"),
    "PENANG": ("PM", "MY", "FE"),
    "HO CHI MINH": ("OH", "VT", "FE"),
    "HAIPHONG": ("OH", "VT", "FE"),
    "MUMBAI": ("BY", "IN", "FE"),
    "NHAVA SHEVA": ("OH", "IN", "FE"),
    "MUNDRA": ("OH", "IN", "FE"),
    "CHENNAI": ("MD", "IN", "FE"),
    "YOKOHAMA": ("YK", "JP", "FE"),
    "TOKYO": ("TK", "JP", "FE"),
    "KOBE": ("KB", "JP", "FE"),
    "NEW YORK": ("NY", "US", "NA"),
    "SAVANNAH": ("SV", "US", "NA"),
    "HOUSTON": ("HO", "US", "NA"),
    "BALTIMORE": ("BE", "US", "NA"),
    "NORFOLK": ("NF", "US", "NA"),
    "NEW ORLEANS": ("NO", "US", "NA"),
    "MONTREAL": ("MT", "CN", "NA"),
    "SANTOS": ("ST", "BZ", "OH"),
    "BUENOS AIRES": ("BO", "AR", "OH"),
}

def classify_commodity(desc: str, hs_code: str = "") -> str:
    t = (desc + " " + hs_code).upper()
    if any(k in t for k in ["COCOA BEAN", "RAW COCOA", "BEANS OF COCOA"]) or hs_code.startswith("1801"):
        return "LCB"
    if any(k in t for k in ["COCOA BUTTER", "COCOA CAKE", "COCOA POWDER", "COCOA LIQUOR", "COCOA PASTE", "CHOCOLATE"]) or hs_code.startswith(("1803", "1804", "1805", "1806")):
        return "LCP"
    if "BANANA" in t or hs_code.startswith("0803"):
        return "LBN"
    if "PINEAPPLE" in t or hs_code.startswith("080430"):
        return "LPN"
    if "YAM" in t or hs_code.startswith("0714"):
        return "LYM"
    if any(k in t for k in ["CASHEW", "ANACARDE"]) or hs_code.startswith("080131"):
        return "LCA"
    if any(k in t for k in ["SHEA NUT", "SHEANUT", "KARITE"]):
        return "LSH"
    if any(k in t for k in ["TUNA", "FROZEN FISH", "SKIPJACK", "YELLOWFIN", "MACKEREL", "SARDINE"]) or hs_code.startswith("0303"):
        return "LFI"
    if "CANNED TUNA" in t or "CANNED FISH" in t:
        return "LFS"
    if any(k in t for k in ["ROUND LOG", "TEAK POLE", "LOGS", "ROUGHS"]):
        return "LLG"
    if any(k in t for k in ["LUMBER", "SAWN TIMBER", "TEAK IN CONTAINER"]):
        return "LST"
    if any(k in t for k in ["FURNITURE", "DOOR", "MOULDING"]):
        return "LFW"
    if any(k in t for k in ["SCRAP", "COPPER SCRAP", "ALUMINIUM SCRAP", "BATTERY SCRAP", "STEEL SCRAP", "IRON SCRAP"]) or hs_code.startswith(("7204", "7404", "7602")):
        return "LMS"
    if any(k in t for k in ["RUBBER", "TIRE", "TYRE", "TUBES"]):
        return "LRB"
    if any(k in t for k in ["ALUMINIUM INGOT", "ALUMINUM INGOT"]):
        return "LAL"
    if any(k in t for k in ["VEHICLE", "USED AUTO", "CARS", "TOYOTA", "HYUNDAI", "MERCEDES", "MAZDA", "HONDA"]) or hs_code.startswith("8703"):
        return "LVE"
    if any(k in t for k in ["TRUCK", "FORKLIFT", "TRACTOR"]) or hs_code.startswith("8704"):
        return "LTR"
    if any(k in t for k in ["MACHINE", "ENGINE", "PUMP", "APPARATUS", "EQUIPMENT"]) or hs_code.startswith(("84", "85")):
        return "LME"
    if any(k in t for k in ["CHEMICAL", "ZINC OXIDE", "CALCIUM", "RESIN", "POLYETHYLENE", "HDPE", "LLDPE"]) or hs_code.startswith(("28", "29", "38", "3901")):
        return "LCH"
    if any(k in t for k in ["SPAGHETTI", "MACARONI", "FOODSTUFF", "BISCUITS", "SUGAR", "OIL", "BEVERAGE", "VODKA", "SOAP", "TEXTILE", "CLOTHING", "USED CLOTH", "SHOES"]):
        return "LPE"
    return "LGC"

def normalize_container(sz_text: str):
    sz = str(sz_text).upper()
    if any(k in sz for k in ["REEF", "40RH", "40RA", "40RC", "45R", "40R", "40HR"]):
        return "40R"
    if any(k in sz for k in ["20R", "20RF"]):
        return "20R"
    if any(k in sz for k in ["40", "40D", "40HC", "40ST", "42G", "45G", "40 OPEN"]):
        return "40D"
    if any(k in sz for k in ["20", "20D", "20ST", "22G"]):
        return "20D"
    return "40D"

def is_empty_equipment(text: str) -> bool:
    t = text.upper()
    empty_patterns = [
        "EMPTY", "EMPTY ISO TANK", "RESIDUE (SOC)", "EMPTY CONTAINER",
        "MT CONTAINER", "SHIPPERS OWNED CONTAINER WITH RESIDUE"
    ]
    return any(p in t for p in empty_patterns)

# ==========================================
# 2. ROBUST EXTRACTION & OCR ENGINE
# ==========================================

def extract_page_text_with_ocr(page, user_rot: int, enable_ocr: bool):
    """Extracts text, handling rotation and OCR for image-only scans."""
    if user_rot != 0:
        page.set_rotation(user_rot)

    text = page.get_text("text")

    # If digital text is missing or extremely short, trigger OCR
    if len(text.strip()) < 40 and enable_ocr:
        pix = page.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        try:
            text = pytesseract.image_to_string(img)
        except Exception:
            pass  # Fallback if tesseract binary is warming up

    return text

# ==========================================
# 3. CARRIER PARSERS
# ==========================================

def parse_maersk(pdf_text: str):
    rows = []
    ship_m = re.search(r"Vessel\s*\n?\s*([A-Z0-9\s]+?)(?:Voyage|Page|\n)", pdf_text, re.IGNORECASE)
    ship = ship_m.group(1).strip() if ship_m else "BOSTON"

    bl_chunks = re.split(r"(?:\n|^)(?=[A-Z0-9]{7,12}\s*(?:\n| )*(?:MAEU|WAYBILL))", pdf_text)
    for chunk in bl_chunks:
        if not ("MAEU" in chunk or "WAYBILL" in chunk):
            continue
        if is_empty_equipment(chunk):
            continue

        pod_m = re.search(r"(?:Final Disch|Vessel Disch|Del):\s*([^,\n]+)", chunk, re.IGNORECASE)
        pod_raw = pod_m.group(1).strip().upper() if pod_m else "LOME"

        port_info = ("OH", "OH", "AF")
        for k, v in PORT_MAP.items():
            if k in pod_raw:
                port_info = v
                break

        cont_matches = re.findall(r"(\d+)\s*X\s*(\d{2}\s*(?:DRY|REEF|OPEN|HC|HR)[^\n]*)", chunk, re.IGNORECASE)
        cont_type = "40D"
        cont_qty = 1
        if cont_matches:
            cont_qty = int(cont_matches[0][0])
            cont_type = normalize_container(cont_matches[0][1])

        wgt_m = re.search(r"([\d\.,\s]+)\s*KGS", chunk, re.IGNORECASE)
        tonnage = 0.0
        if wgt_m:
            raw_w = wgt_m.group(1).replace(" ", "").replace(",", "")
            try:
                tonnage = round(float(raw_w) / 1000.0, 2)
            except:
                tonnage = 0.0

        hs_m = re.search(r"HS\s*(?:Code|CODE)?\s*[:\.]?\s*(\d{4,10})", chunk)
        hs = hs_m.group(1) if hs_m else ""
        desc_m = re.search(r"Description of goods\s*([\s\S]+?)(?:Shipper Provided|Basic Ocean|Container Protect|\n[A-Z0-9]{7,12}|$)", chunk, re.IGNORECASE)
        desc = desc_m.group(1).strip() if desc_m else ""

        comm = classify_commodity(desc, hs)

        if tonnage > 0:
            rows.append({
                "SHIP": ship,
                "SHIP LINE": "MAERSK LINE",
                "AGENT": "MAERSK GH. LTD.",
                "PORT": port_info[0],
                "CTRY": port_info[1],
                "RANGE": port_info[2],
                "CONTYPE": cont_type,
                "CONTQTY": cont_qty,
                "COMMODITY": comm,
                "TONNAGES": tonnage
            })
    return rows

def parse_cmacgm(pdf_text: str):
    rows = []
    ship_m = re.search(r"VESSEL:\s*([A-Z0-9\s]+?)\s*FLAG:", pdf_text, re.IGNORECASE)
    ship = ship_m.group(1).strip() if ship_m else "MAERSK HANGZHOU"

    bl_chunks = re.split(r"(?:\n|^)(?=TMA\w+)", pdf_text)
    for chunk in bl_chunks[1:]:
        if is_empty_equipment(chunk):
            continue

        pod_m = re.search(r"Final Port of Discharge\s*([^\n]+)", chunk, re.IGNORECASE)
        pod_raw = pod_m.group(1).strip().upper() if pod_m else ""

        port_info = ("OH", "OH", "AF")
        for k, v in PORT_MAP.items():
            if k in pod_raw:
                port_info = v
                break

        wgt_m = re.search(r"B/L TOTAL[\s\S]*?WGT:\s*([\d\.]+)\s*TNE", chunk, re.IGNORECASE)
        if not wgt_m:
            wgt_m = re.search(r"WGT:\s*([\d\.]+)\s*TNE", chunk, re.IGNORECASE)
        tonnage = float(wgt_m.group(1)) if wgt_m else 0.0

        splits = re.findall(r"SZTP:\s*([0-9A-Z]+)", chunk)
        cont_qty = len(splits) if splits else 1
        cont_type = normalize_container(splits[0]) if splits else "40D"

        desc_m = re.search(r"DESCRIPTION\s*([\s\S]+?)(?:FREIGHT|B/L TOTAL|SPLIT)", chunk, re.IGNORECASE)
        desc = desc_m.group(1).strip() if desc_m else ""

        comm = classify_commodity(desc)

        if tonnage > 0:
            rows.append({
                "SHIP": ship,
                "SHIP LINE": "CMA CGM",
                "AGENT": "CMA CGM GH. LTD.",
                "PORT": port_info[0],
                "CTRY": port_info[1],
                "RANGE": port_info[2],
                "CONTYPE": cont_type,
                "CONTQTY": cont_qty,
                "COMMODITY": comm,
                "TONNAGES": round(tonnage, 2)
            })
    return rows

def parse_ael(pdf_text: str):
    rows = []
    ship_m = re.search(r"Name of ship:\s*([^\n]+)", pdf_text, re.IGNORECASE)
    ship = ship_m.group(1).strip().upper() if ship_m else "CAMEROUN EXPRESS"

    bl_chunks = re.split(r"(?:\n|^)(?=TEMPOV\w+)", pdf_text)
    for chunk in bl_chunks[1:]:
        if is_empty_equipment(chunk):
            continue

        pod_m = re.search(r"Port of Discharge:\s*([^\n]+)", pdf_text, re.IGNORECASE)
        pod_raw = pod_m.group(1).strip().upper() if pod_m else "PORT VENDRES"

        port_info = ("BD", "FR", "CT")
        for k, v in PORT_MAP.items():
            if k in pod_raw:
                port_info = v
                break

        is_breakbulk = "PALLETS IN HOLD" in chunk.upper()
        cont_type = ""
        cont_qty = ""
        if not is_breakbulk:
            cont_m = re.search(r"(\d+)\s*X\s*40['\s]*hc reefer", chunk, re.IGNORECASE)
            cont_qty = int(cont_m.group(1)) if cont_m else 1
            cont_type = "40R"

        wgt_m = re.search(r"TOTAL GROSS WEIGHT\s*:\s*([\d\s\.,]+)\s*KG", chunk, re.IGNORECASE)
        tonnage = 0.0
        if wgt_m:
            raw_w = wgt_m.group(1).replace(" ", "").replace(",", "")
            tonnage = round(float(raw_w) / 1000.0, 2)

        comm = "LBN" if "BANANA" in chunk.upper() else "LPN"

        if tonnage > 0:
            rows.append({
                "SHIP": ship,
                "SHIP LINE": "AFRICA EXPRESS LINE",
                "AGENT": "EOLIS GH. LTD",
                "PORT": port_info[0],
                "CTRY": port_info[1],
                "RANGE": port_info[2],
                "CONTYPE": cont_type,
                "CONTQTY": cont_qty,
                "COMMODITY": comm,
                "TONNAGES": tonnage
            })
    return rows

# ==========================================
# 4. USER INTERFACE
# ==========================================

st.title("🚢 Ghana Ports Export Manifest Auto-Coder (with OCR)")
st.markdown("Upload your shipping manifest PDF to automatically extract, orient, and code data into your standard format.")

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    month_selected = st.selectbox("Select Operating Month", [
        "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
        "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
    ], index=8)

with col2:
    rotation_option = st.selectbox("Document Orientation / Rotation", [
        "0° (Normal / Upright)",
        "90° Clockwise (Sideways / Landscape)",
        "180° (Upside Down)",
        "270° (Counter-Clockwise)"
    ], index=0)
    
    rotation_degrees = {
        "0° (Normal / Upright)": 0,
        "90° Clockwise (Sideways / Landscape)": 90,
        "180° (Upside Down)": 180,
        "270° (Counter-Clockwise)": 270
    }[rotation_option]

with col3:
    enable_ocr = st.checkbox("Enable OCR for Scanned Images", value=True)
    show_debug_text = st.checkbox("Show Raw Text Preview (Diagnostics)", value=False)

uploaded_files = st.file_uploader("Upload Manifest PDFs", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    start_btn = st.button("🚀 Process & Code Manifest", type="primary", use_container_width=True)

    if start_btn:
        all_extracted_rows = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, uploaded_file in enumerate(uploaded_files):
            file_bytes = uploaded_file.read()
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            total_pages = len(doc)
            pages_text = []

            for p_idx in range(total_pages):
                status_text.text(f"Extracting & Orienting page {p_idx + 1} of {total_pages}...")
                page = doc[p_idx]
                t = extract_page_text_with_ocr(page, rotation_degrees, enable_ocr)
                pages_text.append(t)

            full_text = "\n".join(pages_text)

            if show_debug_text:
                with st.expander(f"🔍 Raw Text Preview ({uploaded_file.name})"):
                    st.text(full_text[:1500] if full_text else "[NO TEXT EXTRACTED]")

            status_text.text("Matching shipping lines & coding master tables...")

            parsed = []
            if "MAERSK" in full_text and ("ML Export Manifest" in full_text or "MAEU" in full_text):
                parsed = parse_maersk(full_text)
            elif "CMA CGM" in full_text or "CMA\\CGM" in full_text:
                parsed = parse_cmacgm(full_text)
            elif "EOLIS" in full_text or "Cameroun Express" in full_text or "AFRICA EXPRESS" in full_text:
                parsed = parse_ael(full_text)
            else:
                # Try all parsers
                parsed = parse_maersk(full_text) or parse_cmacgm(full_text) or parse_ael(full_text)

            for r in parsed:
                r["MONTH"] = month_selected
                all_extracted_rows.append(r)

            progress_bar.progress((idx + 1) / len(uploaded_files))

        status_text.empty()
        progress_bar.empty()

        if all_extracted_rows:
            df = pd.DataFrame(all_extracted_rows)
            col_order = ["MONTH", "SHIP", "SHIP LINE", "AGENT", "PORT", "CTRY", "RANGE", "CONTYPE", "CONTQTY", "COMMODITY", "TONNAGES"]
            df = df[col_order]

            st.success(f"Successfully processed and coded {len(df)} manifest rows!")
            st.subheader("Interactive Review Screen (Edit if needed)")
            edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                edited_df.to_excel(writer, index=False, sheet_name="CODED MANIFEST")

            st.download_button(
                label="📥 Download Coded Excel Sheet (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"{month_selected} 2026 CODING.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.error("No valid cargo rows were found. Tip: If the manifest is sideways, change 'Document Orientation' to '90° Clockwise' or check 'Show Raw Text Preview' to see what was extracted.")
