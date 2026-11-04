import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import re
import io
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

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
    "CAPE TOWN": ("CN", "SA", "AF"),
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

# ==========================================
# 2. HYPER-INTELLIGENCE WEB SEARCH
# ==========================================

def search_web_for_commodity(query_text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z\s]", " ", query_text)
    words = [w for w in cleaned.split() if len(w) > 3 and w.upper() not in ["CARTON", "BAGS", "PACKAGE", "CONTAINER", "WEIGHT", "GROSS", "NET"]][:4]
    search_term = " ".join(words)
    if not search_term.strip():
        return ""
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(search_term + ' product what is')}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            snippets = [s.get_text() for s in soup.find_all("a", class_="result__snippet")[:2]]
            return " ".join(snippets).upper()
    except Exception:
        pass
    return ""

def classify_commodity(desc: str, hs_code: str = "", use_web_search: bool = False) -> str:
    t = (desc + " " + hs_code).upper()

    def match_rules(text_to_check):
        if any(k in text_to_check for k in ["COCOA BEAN", "RAW COCOA", "BEANS OF COCOA"]) or hs_code.startswith("1801"):
            return "LCB"
        if any(k in text_to_check for k in ["COCOA BUTTER", "COCOA CAKE", "COCOA POWDER", "COCOA LIQUOR", "COCOA PASTE", "CHOCOLATE"]) or hs_code.startswith(("1803", "1804", "1805", "1806")):
            return "LCP"
        if "BANANA" in text_to_check or hs_code.startswith("0803"):
            return "LBN"
        if "PINEAPPLE" in text_to_check or hs_code.startswith("080430"):
            return "LPN"
        if "YAM" in text_to_check or hs_code.startswith("0714"):
            return "LYM"
        if any(k in text_to_check for k in ["CASHEW", "ANACARDE"]) or hs_code.startswith("080131"):
            return "LCA"
        if any(k in text_to_check for k in ["SHEA NUT", "SHEANUT", "KARITE"]):
            return "LSH"
        if any(k in text_to_check for k in ["TUNA", "FROZEN FISH", "SKIPJACK", "YELLOWFIN", "MACKEREL", "SARDINE", "MEAT", "POULTRY", "CHICKEN", "BUFFALO", "PRAWNS", "SEAFOOD"]) or hs_code.startswith(("0207", "0303", "0306", "0201", "0202")):
            return "LFI"
        if "CANNED TUNA" in text_to_check or "CANNED FISH" in text_to_check:
            return "LFS"
        if any(k in text_to_check for k in ["ROUND LOG", "TEAK POLE", "LOGS", "ROUGH SQUARE LOGS", "ROUGH SQUARES", "TEAK ROUGH"]):
            return "LLG"
        if any(k in text_to_check for k in ["LUMBER", "SAWN TIMBER", "TEAK SAWN", "TEAK IN CONTAINER"]) or hs_code.startswith("4407"):
            return "LST"
        if any(k in text_to_check for k in ["FURNITURE", "DOOR", "MOULDING"]):
            return "LFW"
        if any(k in text_to_check for k in ["SCRAP", "COPPER SCRAP", "ALUMINIUM SCRAP", "STEEL SCRAP", "IRON SCRAP"]) or hs_code.startswith(("7204", "7404", "7602")):
            return "LMS"
        if any(k in text_to_check for k in ["RUBBER", "TIRE", "TYRE", "TUBES"]):
            return "LRB"
        if any(k in text_to_check for k in ["ALUMINIUM INGOT", "ALUMINUM INGOT"]):
            return "LAL"
        if any(k in text_to_check for k in ["VEHICLE", "USED AUTO", "CARS", "TOYOTA", "HYUNDAI", "MERCEDES", "MAZDA", "HONDA", "AUTOS", "AUTORICKSHAW", "BAJAJ"]) or hs_code.startswith("8703"):
            return "LVE"
        if any(k in text_to_check for k in ["TRUCK", "FORKLIFT", "TRACTOR"]) or hs_code.startswith("8704"):
            return "LTR"
        if any(k in text_to_check for k in ["MACHINE", "ENGINE", "PUMP", "EQUIPMENT", "SPARE PARTS", "MOULDS", "LATHE"]) or hs_code.startswith(("84", "85")):
            return "LME"
        if any(k in text_to_check for k in ["CHEMICAL", "ZINC OXIDE", "CALCIUM", "RESIN", "POLYETHYLENE", "HDPE", "LLDPE", "GYPSUM", "CHLORIDE", "SALT", "ETHYL ACETATE", "HEXANE", "SOLVENT", "ACETATE"]) or hs_code.startswith(("2501", "2520", "28", "29", "38", "3901")):
            return "LCH"
        if any(k in text_to_check for k in ["SPAGHETTI", "MACARONI", "FOODSTUFF", "BISCUITS", "SUGAR", "OIL", "BEVERAGE", "VODKA", "SOAP", "TEXTILE", "CLOTHING", "USED CLOTH", "SHOES", "SYNTHETIC FIBER", "HAIR", "RICE", "PARBOILED RICE", "TOBACCO", "TEA", "MEDICINE", "PHARMACEUTICAL", "SESAME"]):
            return "LPE"
        return None

    result = match_rules(t)
    if result:
        return result

    if use_web_search and len(desc.strip()) > 3:
        web_info = search_web_for_commodity(desc)
        if web_info:
            searched_result = match_rules(web_info)
            if searched_result:
                return searched_result

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
    """Strictly checks for EMPTY CONTAINERS/TANKS, ignoring spare empty packing bags."""
    t = text.upper()
    empty_equipment_patterns = [
        r"\bEMPTY\s+(?:CONTAINER|ISO\s*TANK|TANK|CNTR|REEFER|UNIT|EQUIPMENT)\b",
        r"\b(?:CONTAINER|CNTR|TANK)\s+(?:STC\s+)?EMPTY\b",
        r"\bMT\s+CONTAINER\b",
        r"\bEMPTY\s+WITH\s+RESIDUE\b",
        r"\bRESIDUE\s*\(SOC\)\b",
        r"\bEMPTY\s+SOC\b"
    ]
    for pat in empty_equipment_patterns:
        if re.search(pat, t):
            return True
    return False

def parse_num(val_str: str) -> float:
    try:
        clean = val_str.replace(" ", "").replace(",", "")
        return float(clean)
    except Exception:
        return 0.0

def determine_carrier_agent(vessel_name: str, full_doc_text: str):
    """Detects shipping line and agent accurately based on vessel and document headers."""
    v = vessel_name.upper()
    if "CMA CGM" in v:
        return "CMA CGM", "CMA CGM GH. LTD."
    if "GRIMALDI" in v or "GRANDE" in v:
        return "GRIMALDI LINES", "GRIMALDI GH. LTD"
    if "MSC" in v:
        return "MEDITERRANEAN SHIPPING. CO", "MSC GH. LTD"
    if "CAMEROUN EXPRESS" in v or "CARIBBEAN STAR" in v or "EOLIS" in full_doc_text:
        return "AFRICA EXPRESS LINE", "EOLIS GH. LTD"
    if "HAPAG" in v:
        return "HAPAG-LLOYD", "HAPAG-LLOYD GH. LTD"
    return "MAERSK LINE", "MAERSK GH. LTD."

# ==========================================
# 3. EXTRACTION ENGINES
# ==========================================

def extract_maersk_gross_weight(chunk: str, cont_qty: int) -> float:
    """Extracts actual Cargo Gross Weight in MT, properly summing multiple containers."""
    cleaned = re.sub(r"Tare\s*:\s*[\d\.,\s]+(?:KGS|KG)", "", chunk, flags=re.IGNORECASE)

    # 1. Search for explicit overall B/L Gross Weight
    explicit_totals = re.findall(
        r"(?:TOTAL\s+GROSS\s+WEIGHT|TOTAL\s+GR\.?\s*WT\.?|TOTAL\s+G\.?W\.?|TOTAL\s+CARGO\s+GROSS\s+WEIGHT)\s*[:\.]?\s*([\d\s\.,]+)\s*(?:KGS|KG|MT|MTS)",
        cleaned,
        re.IGNORECASE
    )
    if explicit_totals:
        val = parse_num(explicit_totals[0])
        if val > 500:
            return round(val / 1000.0, 2)
        elif val > 0:
            return round(val, 2)

    # 2. Look for the standalone Gross Weight Column value
    col_totals = re.findall(
        r"(?:^|\n)\s*([\d\.,]+)\s*KGS\s*\n\s*(?:Basic Ocean|Container Protect|Inland Haulage|Additional Import|Storage Export|Inspection Fee|Demurrage|Detention|Electronic Cargo|Terminal Handling|Port Additionals|Import Service|Documentation fee|Verified Gross Mass|Rollable Compensation|3rd Party)",
        cleaned,
        re.IGNORECASE
    )
    if col_totals:
        val = parse_num(col_totals[0])
        if val > 500:
            return round(val / 1000.0, 2)
        elif val > 0:
            return round(val, 2)

    # 3. Collect individual container weights and SUM them if multiple exist
    item_matches = re.findall(
        r"(?:BALES|BAGS|PACKAGES|CARTONS|UNITS|PIECES|COLIS|PKGS|PACKAGE|SACKS|CARTON|BALE|PLTS|PALLET|PALLETS|CTNS|BOXES)\s+([\d\s\.,]+)\s*KGS",
        cleaned,
        re.IGNORECASE
    )
    
    if item_matches:
        container_weights = [parse_num(w) for w in item_matches if parse_num(w) > 500]
        if container_weights:
            if cont_qty > 1 and len(container_weights) > 1:
                max_w = max(container_weights)
                others = [w for w in container_weights if w != max_w]
                if others and abs(max_w - sum(others)) < 100.0:
                    return round(max_w / 1000.0, 2)
                return round(sum(container_weights) / 1000.0, 2)
            else:
                return round(max(container_weights) / 1000.0, 2)

    # 4. Fallback: all numbers with KGS
    fallbacks = re.findall(r"([\d\.,]+)\s*KGS", cleaned, re.IGNORECASE)
    valid_nums = [parse_num(w) for w in fallbacks if parse_num(w) > 500]
    if valid_nums:
        if cont_qty > 1 and len(valid_nums) == cont_qty:
            return round(sum(valid_nums) / 1000.0, 2)
        return round(max(valid_nums) / 1000.0, 2)

    return 0.0

def parse_maersk(pdf_text: str, use_web_search: bool = False):
    rows = []
    ship_m = re.search(r"Vessel\s*\n?\s*([A-Z0-9\s]+?)(?:Voyage|Page|\n)", pdf_text, re.IGNORECASE)
    ship = ship_m.group(1).strip() if ship_m else "VESSEL"

    carrier, agent = determine_carrier_agent(ship, pdf_text)

    # Regex splits across multi-line or alphanumeric B/Ls cleanly
    bl_chunks = re.split(r"(?:\n|^)\s*(?=[A-Z0-9]{7,12}(?:\s*\n\s*[0-9]{1,4})?\s*\n\s*(?:MAEU|WAYBILL))", pdf_text)
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

        tonnage = extract_maersk_gross_weight(chunk, cont_qty)

        hs_m = re.search(r"HS\s*(?:Code|CODE)?\s*[:\.]?\s*(\d{4,10})", chunk)
        hs = hs_m.group(1) if hs_m else ""
        desc_m = re.search(r"Description of goods\s*([\s\S]+?)(?:Shipper Provided|Basic Ocean|Container Protect|\n[A-Z0-9]{7,12}|$)", chunk, re.IGNORECASE)
        desc = desc_m.group(1).strip() if desc_m else ""

        comm = classify_commodity(desc, hs, use_web_search)

        if tonnage > 0:
            rows.append({
                "SHIP": ship,
                "SHIP LINE": carrier,
                "AGENT": agent,
                "PORT": port_info[0],
                "CTRY": port_info[1],
                "RANGE": port_info[2],
                "CONTYPE": cont_type,
                "CONTQTY": cont_qty,
                "COMMODITY": comm,
                "TONNAGES": f"{tonnage:.2f}"
            })
    return rows

def parse_cmacgm(pdf_text: str, use_web_search: bool = False):
    rows = []
    ship_m = re.search(r"VESSEL:\s*([A-Z0-9\s]+?)\s*FLAG:", pdf_text, re.IGNORECASE)
    ship = ship_m.group(1).strip() if ship_m else "MAERSK HANGZHOU"

    carrier, agent = determine_carrier_agent(ship, pdf_text)

    bl_matches = re.findall(r"\b(TMA[0-9A-Z]+)\b", pdf_text)
    unique_bls = []
    for b in bl_matches:
        if b not in unique_bls:
            unique_bls.append(b)

    for bl_no in unique_bls:
        bl_pattern = rf"(?:\n|^)\s*{bl_no}\b[\s\S]*?(?=(?:\n\s*TMA[0-9A-Z]+\b|\Z))"
        bl_full_text_list = re.findall(bl_pattern, pdf_text)
        bl_chunk = "\n".join(bl_full_text_list)

        if is_empty_equipment(bl_chunk):
            continue

        pod_m = re.search(r"Final Port of Discharge\s*([^\n]+)", bl_chunk, re.IGNORECASE)
        pod_raw = pod_m.group(1).strip().upper() if pod_m else ""

        port_info = ("OH", "OH", "AF")
        for k, v in PORT_MAP.items():
            if k in pod_raw:
                port_info = v
                break

        total_m = re.findall(r"B/L TOTAL[\s\S]*?WGT:\s*([\d\.]+)\s*TNE", bl_chunk, re.IGNORECASE)
        if total_m:
            tonnage = float(total_m[-1])
        else:
            split_weights = re.findall(r"SPLIT\s*:\s*\d+[\s\S]*?WGT:\s*([\d\.]+)\s*TNE", bl_chunk, re.IGNORECASE)
            if split_weights:
                tonnage = sum([float(w) for w in split_weights])
            else:
                any_w = re.findall(r"WGT:\s*([\d\.]+)\s*TNE", bl_chunk, re.IGNORECASE)
                tonnage = float(any_w[0]) if any_w else 0.0

        splits = re.findall(r"SZTP:\s*([0-9A-Z]+)", bl_chunk)
        cont_qty = len(splits) if splits else 1
        cont_type = normalize_container(splits[0]) if splits else "40D"

        desc_m = re.search(r"DESCRIPTION\s*([\s\S]+?)(?:FREIGHT|B/L TOTAL|SPLIT)", bl_chunk, re.IGNORECASE)
        desc = desc_m.group(1).strip() if desc_m else ""

        comm = classify_commodity(desc, use_web_search=use_web_search)

        if tonnage > 0:
            rows.append({
                "SHIP": ship,
                "SHIP LINE": carrier,
                "AGENT": agent,
                "PORT": port_info[0],
                "CTRY": port_info[1],
                "RANGE": port_info[2],
                "CONTYPE": cont_type,
                "CONTQTY": cont_qty,
                "COMMODITY": comm,
                "TONNAGES": f"{tonnage:.2f}"
            })
    return rows

def parse_ael(pdf_text: str, use_web_search: bool = False):
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
                "TONNAGES": f"{tonnage:.2f}"
            })
    return rows

# ==========================================
# 4. USER INTERFACE
# ==========================================

st.title("🚢 Ghana Ports Export Manifest Auto-Coder")
st.markdown("Automated coding engine with OCR, Multi-Container Gross Weight Aggregation, and Web Search Hyper-Intelligence.")

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
    enable_web_search = st.checkbox("🌐 Enable Web Search Hyper-Intelligence", value=True)
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
                status_text.text(f"Reading & Orienting page {p_idx + 1} of {total_pages}...")
                page = doc[p_idx]
                if rotation_degrees != 0:
                    page.set_rotation(rotation_degrees)
                
                txt = page.get_text("text")
                if len(txt.strip()) < 40:
                    pix = page.get_pixmap(dpi=150)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    try:
                        txt = pytesseract.image_to_string(img)
                    except Exception:
                        pass
                pages_text.append(txt)

            full_text = "\n".join(pages_text)

            if show_debug_text:
                with st.expander(f"🔍 Raw Text Preview ({uploaded_file.name})"):
                    st.text(full_text[:1500] if full_text else "[NO TEXT EXTRACTED]")

            status_text.text("Processing B/L records and formatting Gross Weights...")

            parsed = []
            if "ML Export Manifest" in full_text or "MAEU" in full_text:
                parsed = parse_maersk(full_text, enable_web_search)
            elif "CMA CGM" in full_text or "CMA\\CGM" in full_text:
                parsed = parse_cmacgm(full_text, enable_web_search)
            elif "EOLIS" in full_text or "Cameroun Express" in full_text or "AFRICA EXPRESS" in full_text:
                parsed = parse_ael(full_text, enable_web_search)
            else:
                parsed = (parse_maersk(full_text, enable_web_search) or 
                          parse_cmacgm(full_text, enable_web_search) or 
                          parse_ael(full_text, enable_web_search))

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

            st.success(f" Successfully processed {len(df)} B/L records with formatted Gross Weights!")
            st.subheader("Interactive Review Screen (Edit if needed)")
            edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                edited_df.to_excel(writer, index=False, sheet_name="CODED MANIFEST")
                ws = writer.sheets["CODED MANIFEST"]
                tonnages_col_idx = col_order.index("TONNAGES") + 1
                for r_idx in range(2, len(edited_df) + 2):
                    cell = ws.cell(row=r_idx, column=tonnages_col_idx)
                    try:
                        cell.value = float(cell.value)
                        cell.number_format = "0.00"
                    except:
                        pass

            st.download_button(
                label="📥 Download Coded Excel Sheet (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"{month_selected} 2026 CODING.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.error("No valid cargo rows were found. Tip: Check 'Show Raw Text Preview' to inspect the extracted text.")
