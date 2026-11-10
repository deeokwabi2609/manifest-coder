import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import re
import io
import requests
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
# 1. GHANA PORT AUTHORITY (GPHA) MASTER CODES
# ==========================================

# Strict conversion of ISO / raw country names to GPHA Statistical Codes
GPHA_COUNTRY_MAP = {
    # AFRICA (RANGE: AF)
    "NIGERIA": ("NG", "AF"), "NG": ("NG", "AF"),
    "TOGO": ("TG", "AF"), "TG": ("TG", "AF"),
    "BENIN": ("BN", "AF"), "BN": ("BN", "AF"), "BJ": ("BN", "AF"),
    "GHANA": ("GH", "AF"), "GH": ("GH", "AF"),
    "COTE D'IVOIRE": ("IV", "AF"), "IVORY COAST": ("IV", "AF"), "IV": ("IV", "AF"), "CI": ("IV", "AF"),
    "BURKINA FASO": ("BF", "AF"), "BF": ("BF", "AF"),
    "NIGER": ("NR", "AF"), "NR": ("NR", "AF"), "NE": ("NR", "AF"),
    "MALI": ("ML", "AF"), "ML": ("ML", "AF"),
    "SENEGAL": ("SN", "AF"), "SN": ("SN", "AF"),
    "SOUTH AFRICA": ("SA", "AF"), "SA": ("SA", "AF"), "ZA": ("SA", "AF"),
    "CAMEROON": ("CM", "AF"), "CM": ("CM", "AF"),
    "CONGO": ("CG", "AF"), "CG": ("CG", "AF"),
    "GABON": ("GA", "AF"), "GA": ("GA", "AF"),
    "GUINEA": ("GN", "AF"), "GN": ("GN", "AF"),
    "SIERRA LEONE": ("SL", "AF"), "SL": ("SL", "AF"),
    "LIBERIA": ("LB", "AF"), "LB": ("LB", "AF"),
    "MAURITANIA": ("MR", "AF"), "MR": ("MR", "AF"),
    "EGYPT": ("EY", "AF"), "EY": ("EY", "AF"), "EG": ("EY", "AF"),
    "MOROCCO": ("MC", "AF"), "MC": ("MC", "AF"), "MA": ("MC", "AF"),
    "ALGERIA": ("AG", "AF"), "AG": ("AG", "AF"), "DZ": ("AG", "AF"),
    "TUNISIA": ("TS", "AF"), "TS": ("TS", "AF"), "TN": ("TS", "AF"),
    "LIBYA": ("LY", "AF"), "LY": ("LY", "AF"),
    "TANZANIA": ("TZ", "AF"), "TZ": ("TZ", "AF"),
    "KENYA": ("KY", "AF"), "KY": ("KY", "AF"), "KE": ("KY", "AF"),
    "ANGOLA": ("OH", "AF"), "AO": ("OH", "AF"),
    "MOZAMBIQUE": ("MZ", "AF"), "MZ": ("MZ", "AF"),
    "NAMIBIA": ("OH", "AF"), "NA": ("OH", "AF"),

    # UNITED KINGDOM & IRELAND (RANGE: UK)
    "UNITED KINGDOM": ("UK", "UK"), "UK": ("UK", "UK"), "GB": ("UK", "UK"),
    "ENGLAND": ("UK", "UK"), "SCOTLAND": ("UK", "UK"),
    "IRELAND": ("IR", "UK"), "IR": ("IR", "UK"), "IE": ("IR", "UK"),

    # CONTINENT EUROPE (RANGE: CT)
    "NETHERLANDS": ("NL", "CT"), "HOLLAND": ("NL", "CT"), "NL": ("NL", "CT"),
    "BELGIUM": ("BG", "CT"), "BG": ("BG", "CT"), "BE": ("BG", "CT"),
    "GERMANY": ("GR", "CT"), "GR": ("GR", "CT"), "DE": ("GR", "CT"),
    "FRANCE": ("FR", "CT"), "FR": ("FR", "CT"),
    "POLAND": ("PL", "CT"), "PL": ("PL", "CT"),
    "DENMARK": ("DK", "CT"), "DK": ("DK", "CT"),
    "SWEDEN": ("SE", "CT"), "SE": ("SE", "CT"),
    "NORWAY": ("NW", "CT"), "NW": ("NW", "CT"), "NO": ("NW", "CT"),
    "FINLAND": ("FL", "CT"), "FL": ("FL", "CT"), "FI": ("FL", "CT"),
    "ESTONIA": ("ET", "CT"), "ET": ("ET", "CT"), "EE": ("ET", "CT"),
    "LATVIA": ("LV", "CT"), "LV": ("LV", "CT"),
    "LITHUANIA": ("LT", "CT"), "LT": ("LT", "CT"),
    "UKRAINE": ("UE", "CT"), "UE": ("UE", "CT"), "UA": ("UE", "CT"),
    "RUSSIA": ("RU", "CT"), "RU": ("RU", "CT"),

    # MEDITERRANEAN (RANGE: ME)
    "SPAIN": ("SP", "ME"), "SP": ("SP", "ME"), "ES": ("SP", "ME"),
    "ITALY": ("IT", "ME"), "IT": ("IT", "ME"),
    "GREECE": ("GC", "ME"), "GC": ("GC", "ME"),
    "PORTUGAL": ("PG", "ME"), "PG": ("PG", "ME"), "PT": ("PG", "ME"),
    "TURKEY": ("TU", "ME"), "TURKIYE": ("TU", "ME"), "TU": ("TU", "ME"), "TR": ("TU", "ME"),
    "CYPRUS": ("CY", "ME"), "CY": ("CY", "ME"),
    "ROMANIA": ("RM", "ME"), "RM": ("RM", "ME"), "RO": ("RM", "ME"),
    "BULGARIA": ("BU", "ME"), "BU": ("BU", "ME"),
    "CROATIA": ("CT", "OH"), "HR": ("CT", "OH"),
    "SLOVENIA": ("OH", "ME"), "SI": ("OH", "ME"),
    "CANARY ISLANDS": ("CI", "ME"),

    # FAR EAST & ASIA (RANGE: FE)
    "INDIA": ("IN", "FE"), "IN": ("IN", "FE"),
    "CHINA": ("CH", "FE"), "CH": ("CH", "FE"), "CN": ("CH", "FE"),
    "JAPAN": ("JP", "FE"), "JP": ("JP", "FE"),
    "SOUTH KOREA": ("SK", "FE"), "KOREA": ("SK", "FE"), "SK": ("SK", "FE"), "KR": ("SK", "FE"),
    "VIETNAM": ("VT", "FE"), "VT": ("VT", "FE"), "VN": ("VT", "FE"),
    "MALAYSIA": ("MY", "FE"), "MY": ("MY", "FE"),
    "INDONESIA": ("ID", "FE"), "ID": ("ID", "FE"),
    "THAILAND": ("TH", "FE"), "TH": ("TH", "FE"),
    "SINGAPORE": ("SG", "FE"), "SG": ("SG", "FE"),
    "TAIWAN": ("TW", "FE"), "TW": ("TW", "FE"),
    "HONG KONG": ("HK", "FE"), "HONGKONG": ("HK", "FE"), "HK": ("HK", "FE"),
    "PAKISTAN": ("PK", "FE"), "PK": ("PK", "FE"),
    "BANGLADESH": ("BD", "FE"), "BD": ("BD", "FE"),
    "SRI LANKA": ("SR", "FE"), "SR": ("SR", "FE"), "LK": ("SR", "FE"),
    "PHILIPPINES": ("PH", "FE"), "PH": ("PH", "FE"),

    # NORTH AMERICA (RANGE: NA)
    "UNITED STATES": ("US", "NA"), "USA": ("US", "NA"), "US": ("US", "NA"),
    "CANADA": ("CN", "NA"),

    # OTHER / OCEANIA / SOUTH AMERICA / MIDDLE EAST (RANGE: OH)
    "BRAZIL": ("BZ", "OH"), "BZ": ("BZ", "OH"), "BR": ("BZ", "OH"),
    "ARGENTINA": ("AR", "OH"), "AR": ("AR", "OH"),
    "AUSTRALIA": ("AU", "OH"), "AU": ("AU", "OH"),
    "NEW ZEALAND": ("NZ", "OH"), "NZ": ("NZ", "OH"),
    "UNITED ARAB EMIRATES": ("AE", "OH"), "UAE": ("AE", "OH"), "AE": ("AE", "OH"), "DUBAI": ("AE", "OH"),
    "SAUDI ARABIA": ("SB", "OH"), "SB": ("SB", "OH"),
    "JORDAN": ("JD", "OH"), "JD": ("JD", "OH"),
    "ISRAEL": ("IL", "OH"), "IL": ("IL", "OH"),
    "QATAR": ("OH", "OH"), "QA": ("OH", "OH")
}

# Major designated ports from code sheet
PORT_MAP = {
    # AFRICA
    "LOME": ("LM", "TG", "AF"), "COTONOU": ("CU", "BN", "AF"), "ABIDJAN": ("AJ", "IV", "AF"),
    "LAGOS": ("LG", "NG", "AF"), "TINCAN": ("LG", "NG", "AF"), "APAPA": ("OH", "NG", "AF"),
    "LEKKI": ("OH", "NG", "AF"), "ONNE": ("OH", "NG", "AF"), "PORT HARCOURT": ("OH", "NG", "AF"),
    "DAKAR": ("DA", "SN", "AF"), "POINTE NOIRE": ("OH", "CG", "AF"), "POINT NOIRE": ("OH", "CG", "AF"),
    "MATADI": ("MA", "CG", "AF"), "LIBREVILLE": ("LB", "GA", "AF"), "PORT GENTIL": ("PG", "GA", "AF"),
    "DOUALA": ("DL", "CM", "AF"), "DURBAN": ("DR", "SA", "AF"), "CAPETOWN": ("CN", "SA", "AF"),
    "CAPE TOWN": ("CN", "SA", "AF"), "PORT ELIZABETH": ("PE", "SA", "AF"), "TEMA": ("TM", "GH", "AF"),
    "TAKORADI": ("TD", "GH", "AF"), "DAR ES SALAAM": ("ES", "TZ", "AF"), "CONAKRY": ("CN", "GN", "AF"),

    # CONTINENT EUROPE
    "ANTWERP": ("AT", "BG", "CT"), "AMSTERDAM": ("AM", "NL", "CT"), "ROTTERDAM": ("RM", "NL", "CT"),
    "HAMBURG": ("HM", "GR", "CT"), "BREMERHAVEN": ("BM", "GR", "CT"), "LE HAVRE": ("LH", "FR", "CT"),
    "DUNKERQUE": ("DK", "FR", "CT"), "DUNKIRK": ("DK", "FR", "CT"), "PORT VENDRES": ("BD", "FR", "CT"),
    "FOS SUR MER": ("OH", "FR", "CT"), "MARSEILLE": ("MS", "FR", "CT"), "ROUEN": ("RN", "FR", "CT"),
    "GDYNIA": ("GA", "PL", "CT"), "GDANSK": ("GK", "PL", "CT"), "ZEEBRUGGE": ("ZB", "BG", "CT"),

    # UK
    "TILBURY": ("TY", "UK", "UK"), "LIVERPOOL": ("LV", "UK", "UK"), "LONDON": ("LD", "UK", "UK"),
    "FELIXSTOWE": ("FX", "UK", "UK"), "DUBLIN": ("DU", "IR", "UK"), "BELFAST": ("BT", "IR", "UK"),

    # MEDITERRANEAN
    "BARCELONA": ("BC", "SP", "ME"), "VALENCIA": ("VL", "SP", "ME"), "ALGECIRAS": ("AR", "SP", "ME"),
    "GENOA": ("GE", "IT", "ME"), "LIVORNO": ("LO", "IT", "ME"), "NAPLES": ("NS", "IT", "ME"),
    "ISTANBUL": ("IL", "TU", "ME"), "IZMIT": ("OH", "TU", "ME"), "AMBARLI": ("OH", "TU", "ME"),
    "MARPORT": ("OH", "TU", "ME"), "PIRAEUS": ("PI", "GC", "ME"), "ALEXANDRIA": ("OH", "EY", "AF"),

    # FAR EAST
    "SHANGHAI": ("SH", "CH", "FE"), "NINGBO": ("OH", "CH", "FE"), "QINGDAO": ("OH", "CH", "FE"),
    "XIAMEN": ("OH", "CH", "FE"), "NANSHA": ("OH", "CH", "FE"), "SHEKOU": ("OH", "CH", "FE"),
    "HONGKONG": ("HK", "HK", "FE"), "BUSAN": ("BU", "SK", "FE"), "INCHEON": ("OH", "SK", "FE"),
    "SINGAPORE": ("SG", "SG", "FE"), "PORT KLANG": ("OH", "MY", "FE"), "PENANG": ("PM", "MY", "FE"),
    "HO CHI MINH": ("OH", "VT", "FE"), "MUMBAI": ("BY", "IN", "FE"), "NHAVA SHEVA": ("OH", "IN", "FE"),
    "MUNDRA": ("OH", "IN", "FE"), "CHENNAI": ("MD", "IN", "FE"), "TUTICORIN": ("OH", "IN", "FE"),
    "VISAKHAPATNAM": ("OH", "IN", "FE"), "YOKOHAMA": ("YK", "JP", "FE"), "TOKYO": ("TK", "JP", "FE"),
    "COLOMBO": ("OH", "SR", "FE"),

    # NORTH AMERICA
    "NEW YORK": ("NY", "US", "NA"), "SAVANNAH": ("SV", "US", "NA"), "HOUSTON": ("HO", "US", "NA"),

    # OTHER
    "SANTOS": ("ST", "BZ", "OH"), "BUENOS AIRES": ("BO", "AR", "OH"), "JEDDAH": ("JD", "SB", "OH")
}

# ==========================================
# 2. STRICT DISCHARGE PORT & COUNTRY RESOLVER
# ==========================================

SEARCH_CACHE = {}

def fast_web_lookup(term: str) -> str:
    clean_term = term.strip().upper()
    if clean_term in SEARCH_CACHE:
        return SEARCH_CACHE[clean_term]
    try:
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote_plus(clean_term)}&utf8=&format=json"
        headers = {"User-Agent": "GhanaManifestBot/1.0"}
        resp = requests.get(url, headers=headers, timeout=1.5)
        if resp.status_code == 200:
            data = resp.json()
            snippets = [item.get("snippet", "") for item in data.get("query", {}).get("search", [])[:2]]
            res_text = re.sub(r"<[^>]+>", " ", " ".join(snippets)).upper()
            SEARCH_CACHE[clean_term] = res_text
            return res_text
    except Exception:
        pass
    SEARCH_CACHE[clean_term] = ""
    return ""

def resolve_port_info(pod_text: str, use_web_search: bool = True) -> tuple:
    """Strictly parses the Port of Discharge text to extract PORT, CTRY, and RANGE accurately."""
    clean = pod_text.upper().strip()
    # Remove leading noise
    clean = re.sub(r"^(?:FINAL DISCH|VESSEL DISCH|PORT OF DISCHARGE|PLACE OF DELIVERY|FINAL DESTINATION|DEL|TO)\s*[:\.]?\s*", "", clean)

    # 1. Check for exact port name in PORT_MAP first
    for p_name, p_val in PORT_MAP.items():
        # Match whole port word or pattern
        if re.search(rf"\b{re.escape(p_name)}\b", clean):
            return p_val

    # 2. Check for ISO Prefix pattern like "CN-NANSHA" or "ZA-DURBAN" or "IN-MUNDRA"
    iso_prefix_m = re.search(r"\b([A-Z]{2})-([A-Z\s]+)\b", clean)
    if iso_prefix_m:
        iso_code = iso_prefix_m.group(1)
        port_part = iso_prefix_m.group(2).strip()
        # Look up port part in PORT_MAP
        for p_name, p_val in PORT_MAP.items():
            if p_name in port_part:
                return p_val
        # If port unlisted, map ISO code to GPHA country code
        if iso_code in GPHA_COUNTRY_MAP:
            c_code, r_code = GPHA_COUNTRY_MAP[iso_code]
            return ("OH", c_code, r_code)

    # 3. Check for Country name in the Discharge text (e.g., "Izmit, Turkey" or "San Pedro, Ivory Coast")
    for c_name, (c_code, r_code) in GPHA_COUNTRY_MAP.items():
        if re.search(rf"\b{re.escape(c_name)}\b", clean):
            return ("OH", c_code, r_code)

    # 4. Web Search fallback for unlisted foreign port
    if use_web_search and len(clean) > 2:
        res = fast_web_lookup(f"{clean} seaport city country")
        if res:
            for c_name, (c_code, r_code) in GPHA_COUNTRY_MAP.items():
                if re.search(rf"\b{re.escape(c_name)}\b", res):
                    return ("OH", c_code, r_code)

    return ("OH", "OH", "AF")

# ==========================================
# 3. SHIP NAME EXTRACTOR (ZERO HARDCODING)
# ==========================================

HEADER_NOISE_PHRASES = [
    "PORT WHERE REPORT", "REPORT IS MODE", "REPORT IS MADE", "NAME OF MASTER",
    "NATIONALITY OF SHIP", "PORT OF LOADING", "PORT OF DISCHARGE", "FINAL DESTINATION",
    "SAILING DATE", "VESSEL IMO", "PAGE NO", "OUTWARD", "INBOUND", "CARGO MANIFEST",
    "FOREIGN CARGO", "VOYAGE NO", "SERVICE CODE", "PLACE OF ACCEPTANCE", "PLACE OF DELIVERY"
]

def is_header_noise(text: str) -> bool:
    t = text.upper().strip()
    return any(noise in t for noise in HEADER_NOISE_PHRASES)

def clean_vessel_name(raw_name: str) -> str:
    name = raw_name.strip()
    name = re.sub(r"^(?:1\.\s*)?(?:NAME\s+OF\s+(?:VESSEL|SHIP)|VESSEL\s+NAME|SHIP\s+NAME|VESSEL|SHIP)\s*[:\.]?\s*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\([A-Z0-9]+\)", "", name)
    name = re.sub(r"\b\d{7}\b.*", "", name)
    name = re.sub(r"\b[A-Z0-9]{2,10}(?:/[EWNS])?\b\s*(?:\d+)?$", "", name)
    for noise in ["VOYAGE", "VOY", "IMO", "FLAG", "PAGE", "OUTWARD", "INBOUND", "NATIONALITY"]:
        name = re.sub(rf"\b{noise}\b.*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[\r\n\t]+", " ", name)
    name = re.sub(r"\s{2,}", " ", name).strip().upper()
    return name

def extract_vessel_name(pdf_text: str) -> str:
    lines = [line.strip() for line in pdf_text.splitlines() if line.strip()]

    for i, line in enumerate(lines[:60]):
        m_inline = re.search(r"\b(?:NAME\s+OF\s+(?:VESSEL|SHIP)|VESSEL\s+NAME|SHIP\s+NAME|VESSEL)\s*[:]\s*([A-Za-z0-9\s\.\-/'\"]+)", line, re.IGNORECASE)
        if m_inline:
            cand = clean_vessel_name(m_inline.group(1))
            if cand and not is_header_noise(cand) and len(cand) > 2:
                return cand

        if re.search(r"\b(?:1\.\s*)?(?:NAME\s+OF\s+(?:VESSEL|SHIP)|VESSEL\s+NAME|SHIP\s+NAME|VESSEL|SHIP)\b", line, re.IGNORECASE):
            for next_line in lines[i+1 : i+5]:
                if is_header_noise(next_line):
                    continue
                cand = clean_vessel_name(next_line)
                if cand and not is_header_noise(cand) and len(cand) > 2:
                    return cand

    for line in lines[:25]:
        m = re.search(r"^\s*([A-Za-z\s]{3,25})\s+\d{3,4}/[EWNS]", line)
        if m:
            cand = clean_vessel_name(m.group(1))
            if cand and not is_header_noise(cand):
                return cand

    return "UNKNOWN VESSEL"

# ==========================================
# 4. COMMODITY & CONTAINER CLASSIFIER
# ==========================================

def classify_commodity(desc: str, hs_code: str = "", use_web_search: bool = False) -> str:
    t = (desc + " " + hs_code).upper()

    def match_rules(text_to_check):
        if any(k in text_to_check for k in ["COCOA BEAN", "RAW COCOA", "BEANS OF COCOA"]) or hs_code.startswith("1801"):
            return "LCB"
        if any(k in text_to_check for k in ["COCOA BUTTER", "COCOA CAKE", "COCOA POWDER", "COCOA LIQUOR", "COCOA MASS", "COCOA PASTE", "CHOCOLATE", "COCOA NIB"]) or hs_code.startswith(("1803", "1804", "1805", "1806")):
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
        if any(k in text_to_check for k in ["TOBACCO", "GINGER", "CHILLI", "TURMERIC", "SESAME", "SEEDS", "COCONUT", "COIR", "COCOPEAT", "PEPPER", "CASHEW SHELL", "COCOA SHELL", "CHARCOAL"]) or hs_code.startswith(("0904", "0910", "1207", "2401", "5305")):
            return "LNO"
        if any(k in text_to_check for k in ["TUNA", "FROZEN FISH", "SKIPJACK", "YELLOWFIN", "MACKEREL", "SARDINE", "MEAT", "POULTRY", "CHICKEN", "BUFFALO", "PRAWNS", "SEAFOOD"]) or hs_code.startswith(("0207", "0303", "0306", "0201", "0202")):
            return "LFI"
        if "CANNED TUNA" in text_to_check or "CANNED FISH" in text_to_check:
            return "LFS"
        if any(k in text_to_check for k in ["ROUND LOG", "TEAK POLE", "LOGS", "ROUGH SQUARE LOGS", "ROUGH SQUARES", "TEAK ROUGH"]) or (hs_code.startswith("4403") and "SAWN" not in text_to_check):
            return "LLG"
        if any(k in text_to_check for k in ["LUMBER", "SAWN TIMBER", "TEAK SAWN", "TEAK IN CONTAINER"]) or hs_code.startswith("4407"):
            return "LST"
        if any(k in text_to_check for k in ["FURNITURE", "DOOR", "MOULDING"]):
            return "LFW"
        if any(k in text_to_check for k in ["SCRAP", "COPPER SCRAP", "ALUMINIUM SCRAP", "STEEL SCRAP", "IRON SCRAP"]) or hs_code.startswith(("7204", "7404", "7602")):
            return "LMS"
        if any(k in text_to_check for k in ["RUBBER", "TIRE", "TYRE", "TUBES"]):
            return "LRB"
        if any(k in text_to_check for k in ["ALUMINIUM INGOT", "ALUMINUM INGOT", "ALUMINIUM WIRE ROD", "ALUMINUM WIRE"]):
            return "LAL"
        if any(k in text_to_check for k in ["VEHICLE", "USED AUTO", "CARS", "TOYOTA", "HYUNDAI", "MERCEDES", "MAZDA", "HONDA", "AUTOS", "AUTORICKSHAW", "BAJAJ"]) or hs_code.startswith("8703"):
            return "LVE"
        if any(k in text_to_check for k in ["TRUCK", "FORKLIFT", "TRACTOR"]) or hs_code.startswith("8704"):
            return "LTR"
        if any(k in text_to_check for k in ["MACHINE", "ENGINE", "PUMP", "EQUIPMENT", "SPARE PARTS", "MOULDS", "LATHE", "INCENSE", "MATCHET", "AGRICULTURAL IMPLEMENT", "REFRIGERATING"]) or hs_code.startswith(("84", "85", "3307", "8201")):
            return "LME"
        if any(k in text_to_check for k in ["CHEMICAL", "ZINC OXIDE", "CALCIUM", "RESIN", "POLYETHYLENE", "HDPE", "LLDPE", "GYPSUM", "CHLORIDE", "SALT", "ETHYL ACETATE", "HEXANE", "SOLVENT", "ACETATE", "MANGANESE", "ENZYMES", "BOSTIK"]) or hs_code.startswith(("2501", "2520", "28", "29", "3507", "38", "3901", "7202")):
            return "LCH"
        if any(k in text_to_check for k in ["SPAGHETTI", "MACARONI", "FOODSTUFF", "BISCUITS", "SUGAR", "OIL", "SOYABEAN OIL", "BEVERAGE", "VODKA", "SOAP", "BEAUTY", "BEAUTY PREPARATION", "COSMETIC", "TEXTILE", "CLOTHING", "USED CLOTH", "SHOES", "SYNTHETIC FIBER", "HAIR", "RICE", "PARBOILED RICE", "TEA", "MEDICINE", "PHARMACEUTICAL", "TAILORING", "POPPADOM", "FILTERATION", "YARN", "FABRIC", "PAPERBOARD", "FOOTWEAR", "SPORTS MATERIAL", "CATERING"]):
            return "LPE"
        if "GRANITE" in text_to_check or "TILES" in text_to_check or hs_code.startswith("6907"):
            return "LGC"
        return None

    result = match_rules(t)
    if result:
        return result

    if use_web_search and len(desc.strip()) > 3:
        cleaned_words = [w for w in re.sub(r"[^A-Za-z]", " ", desc).split() if len(w) > 3][:3]
        if cleaned_words:
            web_info = fast_web_lookup(" ".join(cleaned_words) + " product")
            if web_info:
                res = match_rules(web_info)
                if res:
                    return res

    return "LGC"

def normalize_container(sz_text: str):
    sz = str(sz_text).upper()
    if any(k in sz for k in ["REEF", "40RH", "40RA", "40RC", "45R", "40R", "40HR", "R5"]):
        return "40R"
    if any(k in sz for k in ["20R", "20RF", "R2"]):
        return "20R"
    if any(k in sz for k in ["40", "40D", "40HC", "40HQ", "40ST", "42G", "45G", "40 OPEN", "D5"]):
        return "40D"
    if any(k in sz for k in ["20", "20D", "20ST", "20GP", "22G", "DV20", "D2", "20 BO"]):
        return "20D"
    return "40D"

def is_empty_equipment(text: str) -> bool:
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

# ==========================================
# 5. CARRIER PARSERS (STRICT SEQUENTIAL ORDER)
# ==========================================

def parse_one(pdf_text: str, ship_name: str, use_web_search: bool = True):
    rows = []
    ship = ship_name

    # Preserve EXACT appearance order in document (no set())
    bl_matches = []
    for m in re.finditer(r"\b(ONEY[A-Z0-9]{8,15}|[A-Z]{4}\d{8,12})\b", pdf_text):
        b = m.group(1)
        if b not in bl_matches:
            bl_matches.append(b)

    for bl_no in bl_matches:
        pattern = rf"(?:^|\n)\s*{re.escape(bl_no)}\b[\s\S]*?(?=(?:\n\s*ONEY[A-Z0-9]+\b|\n\s*OUTWARD|\Z))"
        matches = re.findall(pattern, pdf_text)
        chunk = "\n".join(matches) if matches else ""

        if not chunk or is_empty_equipment(chunk):
            continue

        # Extract strictly from destination / discharge line
        dest_m = re.search(r"(?:Final destination|5b\.Port of discharge|Port of discharge)[^\n]*\n[^\n]*?\s*([A-Za-z0-9\s-]+?)(?:\s{2,}|\n|$)", chunk, re.IGNORECASE)
        pod_raw = dest_m.group(1).strip().upper() if dest_m else ""
        if not pod_raw:
            page_dest = re.search(r"5b\.Port of discharge\s*([^\n]+)", pdf_text, re.IGNORECASE)
            pod_raw = page_dest.group(1).strip().upper() if page_dest else "DURBAN"

        port_info = resolve_port_info(pod_raw, use_web_search)

        wgt_m = re.search(r"(?:TOTAL GROSS WEIGHT\s*:\s*|GROSS WEIGHT\s*[：:]\s*|1\)\s*)([\d\s\.,]+)(?:\s*MTS|\s*KG|\s*\(|\n)", chunk, re.IGNORECASE)
        val = parse_num(wgt_m.group(1)) if wgt_m else 0.0
        tonnage = round(val if (0.0 < val < 500.0) else val / 1000.0, 2)
        if tonnage <= 0.0:
            continue

        container_groups = re.findall(r"(\d+)\s*X\s*(\d{2}[A-Za-z0-9]+)", chunk, re.IGNORECASE)
        desc_m = re.search(r"(?:SAID TO CONTAIN:\s*(?:STC\s+)?|\d+\s+PKGS\s+)([A-Za-z\s\(\)]+?)(?:CN>|HS CODE|FORM M|\n\s*\d+\))", chunk, re.IGNORECASE)
        desc = desc_m.group(1).strip() if desc_m else "GENERAL CARGO"
        comm = classify_commodity(desc, use_web_search=use_web_search)

        if container_groups:
            total_containers = sum(int(q) for q, _ in container_groups)
            for q_str, sz_str in container_groups:
                q_val = int(q_str)
                c_tonnage = round(tonnage * (q_val / total_containers), 2) if total_containers > 0 else tonnage
                rows.append({
                    "SHIP": ship, "SHIP LINE": "OCEAN NETWORK EXPRESS", "AGENT": "ONE GH. LTD",
                    "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
                    "CONTYPE": normalize_container(sz_str), "CONTQTY": q_val, "COMMODITY": comm, "TONNAGES": f"{c_tonnage:.2f}"
                })
        else:
            cont_tags = re.findall(r"\(CN\)\s+([A-Z0-9]+)", chunk)
            cont_qty = len(cont_tags) if cont_tags else 1
            cont_type = "40D" if "40" in chunk else "20D"
            rows.append({
                "SHIP": ship, "SHIP LINE": "OCEAN NETWORK EXPRESS", "AGENT": "ONE GH. LTD",
                "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
                "CONTYPE": cont_type, "CONTQTY": cont_qty, "COMMODITY": comm, "TONNAGES": f"{tonnage:.2f}"
            })
    return rows

def parse_pil(pdf_text: str, ship_name: str, use_web_search: bool = True):
    rows = []
    ship = ship_name

    sections = re.split(r"(?:\n|^)(?=OUTWARD)", pdf_text)
    for sec in sections:
        pod_m = re.search(r"5b\.Port of discharge\s*([^\n]+)", sec, re.IGNORECASE)
        pod_raw = pod_m.group(1).strip().upper() if pod_m else "NANSHA"
        port_info = resolve_port_info(pod_raw, use_web_search)

        bl_chunks = re.split(r"(?:\n|^)(?=N/A\s+[A-Z0-9]{8,15})", sec)
        for chunk in bl_chunks:
            if is_empty_equipment(chunk):
                continue
            
            wgt_m = re.search(r"1\)\s*([\d\s\.,]+)\s*KGS", chunk, re.IGNORECASE)
            raw_w = parse_num(wgt_m.group(1)) if wgt_m else 0.0
            if raw_w <= 0.0:
                continue
            tonnage = round(raw_w / 1000.0, 2)

            cont_types = re.findall(r"\((?:CY/CY|FCL/FCL)\)\s*-\s*([A-Z0-9]+)", chunk)
            if cont_types:
                cont_type = normalize_container(cont_types[0])
                cont_qty = len(cont_types)
            else:
                qty_m = re.search(r"(\d+)\s*X\s*(\d{2}[A-Z]*)", chunk)
                cont_qty = int(qty_m.group(1)) if qty_m else 1
                cont_type = normalize_container(qty_m.group(2)) if qty_m else "20D"

            desc_m = re.search(r"(?:SAID TO CONTAIN:|CONTAINER\(S\)\s+SAID\s+TO\s+CONTAIN:)\s*([^\n]+)", chunk, re.IGNORECASE)
            desc = desc_m.group(1).strip() if desc_m else "GENERAL CARGO"
            comm = classify_commodity(desc, use_web_search=use_web_search)

            rows.append({
                "SHIP": ship, "SHIP LINE": "PACIFIC INTERNATIONAL LINES", "AGENT": "PIL GH. LTD",
                "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
                "CONTYPE": cont_type, "CONTQTY": cont_qty, "COMMODITY": comm, "TONNAGES": f"{tonnage:.2f}"
            })
    return rows

def parse_goldstar(pdf_text: str, ship_name: str, use_web_search: bool = True):
    rows = []
    ship = ship_name

    bl_chunks = re.split(r"(?:\n|^)(?=Bill type:)", pdf_text)
    for chunk in bl_chunks[1:]:
        if is_empty_equipment(chunk):
            continue

        to_m = re.search(r"To\s*:\s*([^\n]+)", chunk if "To :" in chunk else pdf_text)
        pod_raw = to_m.group(1).strip().upper() if to_m else "ABIDJAN"
        port_info = resolve_port_info(pod_raw, use_web_search)

        qty_m = re.search(r"(\d+)\s*cont\s*([A-Z0-9]+)\s+([\d\s\.,]+)", chunk)
        if qty_m:
            cont_qty = int(qty_m.group(1))
            cont_type = normalize_container(qty_m.group(2))
            tonnage = round(parse_num(qty_m.group(3)) / 1000.0, 2)
        else:
            continue

        desc_m = re.search(r"CONTAINERS S\.L\.A\.C\.\s*\n\s*([A-Z\s\.]+)", chunk)
        desc = desc_m.group(1).strip() if desc_m else "GENERAL CARGO"
        comm = classify_commodity(desc, use_web_search=use_web_search)

        rows.append({
            "SHIP": ship, "SHIP LINE": "GOLD STAR LINE", "AGENT": "ISAG GH. LTD",
            "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
            "CONTYPE": cont_type, "CONTQTY": cont_qty, "COMMODITY": comm, "TONNAGES": f"{tonnage:.2f}"
        })
    return rows

def parse_arkas(pdf_text: str, ship_name: str, use_web_search: bool = True):
    rows = []
    ship = ship_name

    bl_chunks = re.split(r"(?:\n|^)(?=B/L#:)", pdf_text)
    for chunk in bl_chunks[1:]:
        if is_empty_equipment(chunk):
            continue

        pod_m = re.search(r"Port Of Discharge\s*\n?\s*([A-Z\s]+?)(?:Terminal|\n)", chunk, re.IGNORECASE)
        pod_raw = pod_m.group(1).strip().upper() if pod_m else "GENOA"
        port_info = resolve_port_info(pod_raw, use_web_search)

        wgt_m = re.search(r"BL GROSS WEIGHT\s*:\s*([\d\s\.,]+)", chunk, re.IGNORECASE)
        tonnage = round(parse_num(wgt_m.group(1)) / 1000.0, 2) if wgt_m else 0.0
        if tonnage <= 0.0:
            continue

        c_match = re.search(r"BL TOTAL CONTAINERS:\s*(\d+)\s*\n\s*\d+\*(\d{2}\s*[A-Z]+)", chunk)
        if c_match:
            cont_qty = int(c_match.group(1))
            cont_type = normalize_container(c_match.group(2))
        else:
            cont_qty = 1
            cont_type = "40D"

        desc_m = re.search(r"\d+\s+(?:CARTONS|BAGS|PACKAGES)\s*\n\s*([A-Z\s]+?)(?:NET WEIGHT|HS CODE|\n)", chunk, re.IGNORECASE)
        desc = desc_m.group(1).strip() if desc_m else "COCOA PRODUCTS"
        comm = classify_commodity(desc, use_web_search=use_web_search)

        rows.append({
            "SHIP": ship, "SHIP LINE": "ARKAS LINES", "AGENT": "ARKAS GH. LTD",
            "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
            "CONTYPE": cont_type, "CONTQTY": cont_qty, "COMMODITY": comm, "TONNAGES": f"{tonnage:.2f}"
        })
    return rows

def parse_cosco(pdf_text: str, ship_name: str, use_web_search: bool = True):
    rows = []
    ship = ship_name

    if "B/LNUMBER:" in pdf_text:
        bl_chunks = re.split(r"(?:\n|^)(?=B/LNUMBER:)", pdf_text)
        for chunk in bl_chunks[1:]:
            if is_empty_equipment(chunk):
                continue

            # Look strictly at PORT OF DISCHARGE / PLACE OF DELIVERY
            pod_m = re.search(r"(?:PORT OF DISCHARGE|PLACE OF DELIVERY)\s*:\s*([A-Z\s]+)", chunk, re.IGNORECASE)
            pod_raw = pod_m.group(1).strip().upper() if pod_m else "APAPA"
            port_info = resolve_port_info(pod_raw, use_web_search)

            wgt_m = re.search(r"GROSS WEIGHT\s*[：:]\s*([\d\s\.,]+)\s*KG", chunk, re.IGNORECASE)
            tonnage = round(parse_num(wgt_m.group(1)) / 1000.0, 2) if wgt_m else 0.0
            if tonnage <= 0.0:
                continue

            cont_lines = re.findall(r"\b([0-9]{2}[A-Z]{2})\b[^\n]*\bFCL/FCL\b", chunk)
            cont_qty = len(cont_lines) if cont_lines else 1
            cont_type = normalize_container(cont_lines[0]) if cont_lines else "20D"

            desc_m = re.search(r"DESCRIPTION OF GOODS\s*\n\s*([A-Z0-9\s\(\)\.,-]+?)(?:GROSS WEIGHT|FORM M|HS CODE|\n\n)", chunk, re.IGNORECASE)
            desc = desc_m.group(1).strip() if desc_m else "GENERAL CARGO"
            comm = classify_commodity(desc, use_web_search=use_web_search)

            rows.append({
                "SHIP": ship, "SHIP LINE": "COSCO SHIPPING LINE", "AGENT": "COSCO GH. LTD",
                "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
                "CONTYPE": cont_type, "CONTQTY": cont_qty, "COMMODITY": comm, "TONNAGES": f"{tonnage:.2f}"
            })
    else:
        bl_chunks = re.split(r"(?:\n|^)(?=Item No\.)", pdf_text)
        for chunk in bl_chunks[1:]:
            pod_m = re.search(r"B/L Port of Discharge\s*\n?\s*([A-Z\s]+?)\s*B/L Place", chunk, re.IGNORECASE)
            pod_raw = pod_m.group(1).strip().upper() if pod_m else "XIAMEN"
            port_info = resolve_port_info(pod_raw, use_web_search)

            wgt_m = re.search(r"(\d+\.\d{2})\s*KG", chunk)
            tonnage = round(parse_num(wgt_m.group(1)) / 1000.0, 2) if wgt_m else 0.0
            if tonnage <= 0.0:
                continue

            c_match = re.search(r"(\d+)\s*CONTAINER\(S\)", chunk)
            cont_qty = int(c_match.group(1)) if c_match else 1
            cont_type = "40D"

            desc_m = re.search(r"Number and Kinds of Package/Description of Goods\s*\n[\s\S]*?\d+\s+BAGS\s*\n[\s\S]*?\n\s*([A-Z\s]+?)\n", chunk)
            desc = desc_m.group(1).strip() if desc_m else "COCOA POWDER"
            comm = classify_commodity(desc, use_web_search=use_web_search)

            rows.append({
                "SHIP": ship, "SHIP LINE": "COSCO SHIPPING LINE", "AGENT": "COSCO GH. LTD",
                "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
                "CONTYPE": cont_type, "CONTQTY": cont_qty, "COMMODITY": comm, "TONNAGES": f"{tonnage:.2f}"
            })
    return rows

def parse_maersk(pdf_text: str, ship_name: str, use_web_search: bool = True):
    rows = []
    ship = ship_name
    carrier, agent = ("CMA CGM", "CMA CGM GH. LTD.") if "CMA CGM" in ship else ("MAERSK LINE", "MAERSK GH. LTD.")

    # Strictly preserve document order
    bl_chunks = re.split(r"(?:\n|^)\s*(?=[A-Z0-9]{7,12}(?:\s*\n\s*[0-9]{1,4})?\s*\n\s*(?:MAEU|WAYBILL))", pdf_text)
    for chunk in bl_chunks:
        if not ("MAEU" in chunk or "WAYBILL" in chunk):
            continue
        if is_empty_equipment(chunk):
            continue

        # Strictly isolate Port of Discharge field (ignore Shipper and POL)
        pod_m = re.search(r"(?:Final Disch|Vessel Disch|Del)\s*:\s*([^\n]+)", chunk, re.IGNORECASE)
        pod_raw = pod_m.group(1).strip().upper() if pod_m else "LOME"
        port_info = resolve_port_info(pod_raw, use_web_search)

        cont_matches = re.findall(r"(\d+)\s*X\s*(\d{2}\s*(?:DRY|REEF|OPEN|HC|HR)[^\n]*)", chunk, re.IGNORECASE)
        cont_type = "40D"
        cont_qty = 1
        if cont_matches:
            cont_qty = int(cont_matches[0][0])
            cont_type = normalize_container(cont_matches[0][1])

        cleaned = re.sub(r"Tare\s*:\s*[\d\.,\s]+(?:KGS|KG)", "", chunk, flags=re.IGNORECASE)
        explicit_totals = re.findall(r"(?:TOTAL\s+GROSS\s+WEIGHT|TOTAL\s+GR\.?\s*WT\.?|TOTAL\s+G\.?W\.?|TOTAL\s+CARGO\s+GROSS\s+WEIGHT)\s*[:\.]?\s*([\d\s\.,]+)\s*(?:KGS|KG|MT|MTS)", cleaned, re.IGNORECASE)
        if explicit_totals:
            val = parse_num(explicit_totals[0])
            tonnage = round(val / 1000.0 if val > 500 else val, 2)
        else:
            col_totals = re.findall(r"(?:^|\n)\s*([\d\.,]+)\s*KGS\s*\n\s*(?:Basic Ocean|Container Protect|Inland Haulage|Additional Import|Storage Export|Inspection Fee|Demurrage|Detention|Electronic Cargo|Terminal Handling|Port Additionals|Import Service|Documentation fee|Verified Gross Mass|Rollable Compensation|3rd Party)", cleaned, re.IGNORECASE)
            if col_totals:
                val = parse_num(col_totals[0])
                tonnage = round(val / 1000.0 if val > 500 else val, 2)
            else:
                item_matches = re.findall(r"(?:BALES|BAGS|PACKAGES|CARTONS|UNITS|PIECES|COLIS|PKGS|PACKAGE|SACKS|CARTON|BALE|PLTS|PALLET|PALLETS|CTNS|BOXES|ROLLS)\s+([\d\s\.,]+)\s*KGS", cleaned, re.IGNORECASE)
                valid_nums = [parse_num(w) for w in item_matches if parse_num(w) > 500]
                if valid_nums:
                    tonnage = round(sum(valid_nums) / 1000.0 if cont_qty > 1 and len(valid_nums) > 1 else max(valid_nums) / 1000.0, 2)
                else:
                    tonnage = 0.0

        hs_m = re.search(r"HS\s*(?:Code|CODE)?\s*[:\.]?\s*(\d{4,10})", chunk)
        hs = hs_m.group(1) if hs_m else ""
        desc_m = re.search(r"Description of goods\s*([\s\S]+?)(?:Shipper Provided|Basic Ocean|Container Protect|\n[A-Z0-9]{7,12}|$)", chunk, re.IGNORECASE)
        desc = desc_m.group(1).strip() if desc_m else ""

        comm = classify_commodity(desc, hs, use_web_search)

        if tonnage > 0:
            rows.append({
                "SHIP": ship, "SHIP LINE": carrier, "AGENT": agent,
                "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
                "CONTYPE": cont_type, "CONTQTY": cont_qty, "COMMODITY": comm, "TONNAGES": f"{tonnage:.2f}"
            })
    return rows

def parse_ael(pdf_text: str, ship_name: str, use_web_search: bool = True):
    rows = []
    ship = ship_name

    # Preserve exact order
    bl_chunks = re.split(r"(?:\n|^)(?=TEMPOV\w+|TEMDKR\w+)", pdf_text)
    for chunk in bl_chunks[1:]:
        if is_empty_equipment(chunk):
            continue

        pod_m = re.search(r"Port of Discharge:\s*([^\n]+)", chunk if "Port of Discharge:" in chunk else pdf_text, re.IGNORECASE)
        pod_raw = pod_m.group(1).strip().upper() if pod_m else "PORT VENDRES"
        port_info = resolve_port_info(pod_raw, use_web_search)

        is_breakbulk = "PALLETS IN HOLD" in chunk.upper()
        cont_type = ""
        cont_qty = ""
        if not is_breakbulk:
            cont_m = re.search(r"(\d+)\s*X\s*40['\s]*hc reefer", chunk, re.IGNORECASE)
            cont_qty = int(cont_m.group(1)) if cont_m else 1
            cont_type = "40R"

        wgt_m = re.search(r"TOTAL GROSS WEIGHT\s*:\s*([\d\s\.,]+)\s*KG", chunk, re.IGNORECASE)
        tonnage = round(parse_num(wgt_m.group(1)) / 1000.0, 2) if wgt_m else 0.0

        if "YAM" in chunk.upper():
            comm = "LYM"
        elif "BANANA" in chunk.upper():
            comm = "LBN"
        else:
            comm = "LPN"

        if tonnage > 0:
            rows.append({
                "SHIP": ship, "SHIP LINE": "AFRICA EXPRESS LINE", "AGENT": "EOLIS GH. LTD",
                "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
                "CONTYPE": cont_type, "CONTQTY": cont_qty, "COMMODITY": comm, "TONNAGES": f"{tonnage:.2f}"
            })
    return rows

# ==========================================
# 6. USER INTERFACE & DISPATCHER
# ==========================================

st.title("🚢 Ghana Ports Export Manifest Auto-Coder")
st.markdown("Universal Multi-Carrier Manifest Coding Engine.")

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
    enable_web_search = st.checkbox("🌐 Enable Web Search (Ports & Commodities)", value=True)
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

            has_digital_text = any(len(p.get_text("text").strip()) > 50 for p in doc[:3])

            for p_idx in range(total_pages):
                status_text.text(f"Reading page {p_idx + 1} of {total_pages} ({uploaded_file.name})...")
                page = doc[p_idx]
                if rotation_degrees != 0:
                    page.set_rotation(rotation_degrees)
                
                txt = page.get_text("text")
                if not has_digital_text and len(txt.strip()) < 30:
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

            detected_ship = extract_vessel_name(full_text)
            status_text.text(f"Detected Vessel: '{detected_ship}' — Processing cargo rows...")

            parsed = []
            if "OCEAN NETWORK EXPRESS" in full_text or "ONEY" in full_text or re.search(r"\bONE\b", full_text):
                parsed = parse_one(full_text, detected_ship, enable_web_search)
            elif "PIL" in full_text or "PACIFIC INTERNATIONAL" in full_text or "KOTA" in full_text:
                parsed = parse_pil(full_text, detected_ship, enable_web_search)
            elif "GOSUTEM" in full_text or "GOLD STAR" in full_text or "CONDOR 630" in full_text:
                parsed = parse_goldstar(full_text, detected_ship, enable_web_search)
            elif "ARKU" in full_text or "APM Terminals Barcelona" in full_text or "MICHEL A" in full_text:
                parsed = parse_arkas(full_text, detected_ship, enable_web_search)
            elif "COSCO SHIPPING" in full_text or "COSU" in full_text or "EXPORT REPORT MANIFEST" in full_text:
                parsed = parse_cosco(full_text, detected_ship, enable_web_search)
            elif "EOLIS" in full_text or "AFRICA EXPRESS" in full_text or "TEMPOV" in full_text:
                parsed = parse_ael(full_text, detected_ship, enable_web_search)
            else:
                parsed = parse_maersk(full_text, detected_ship, enable_web_search)

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

            st.success(f" Successfully processed and coded {len(df)} manifest rows in chronological order!")
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
