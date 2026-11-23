import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from PIL import Image, ImageOps
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
        # Prefer Streamlit secrets. For local testing only, you can add
        # APP_PASSWORD to .streamlit/secrets.toml.
        expected_password = st.secrets.get("APP_PASSWORD", "CHANGE_THIS_PASSWORD")

        if st.session_state["password"] == expected_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.subheader("🔒 Manifest Coding System - Restricted Access")
        st.text_input(
            "Enter Office Access Password:",
            type="password",
            on_change=password_entered,
            key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        st.subheader("🔒 Manifest Coding System - Restricted Access")
        st.text_input(
            "Enter Office Access Password:",
            type="password",
            on_change=password_entered,
            key="password"
        )
        st.error("❌ Incorrect password. Access denied.")
        return False
    else:
        return True


if not check_password():
    st.stop()


# ==========================================
# PDF ORIENTATION / OCR HELPERS
# ==========================================

def render_page_for_ocr(page, rotation_degrees=0, dpi=220):
    """Render a PDF page as a grayscale image and apply requested rotation."""
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    # Pillow rotates counter-clockwise. expand=True avoids cropping.
    if rotation_degrees:
        image = image.rotate(rotation_degrees, expand=True)

    return ImageOps.grayscale(image)


def get_ocr_text(image):
    """Try two Tesseract page segmentation modes and return the better result."""
    best_text = ""

    for config in ("--psm 6", "--psm 11"):
        try:
            text = pytesseract.image_to_string(image, config=config)
            if len(text.strip()) > len(best_text.strip()):
                best_text = text
        except Exception:
            continue

    return best_text


def extract_page_text(page, manual_rotation=0, auto_rotate=True):
    """
    Extract native PDF text when possible. For scanned or sparse-text pages,
    OCR several orientations and choose the result with the strongest text
    and manifest-related terms.
    """
    native_text = page.get_text("text").strip()

    # Native PDF text is generally preferable to OCR.
    if len(native_text) >= 80:
        return native_text

    base_image = render_page_for_ocr(
        page,
        rotation_degrees=manual_rotation,
        dpi=220
    )

    extra_rotations = [0, 90, 180, 270] if auto_rotate else [0]
    candidates = []

    manifest_terms = (
        "PORT",
        "DISCHARGE",
        "GROSS WEIGHT",
        "CONTAINER",
        "BILL",
        "VESSEL",
        "CARGO",
        "DESCRIPTION",
        "SHIPPER",
        "CONSIGNEE"
    )

    for extra_rotation in extra_rotations:
        image = (
            base_image.rotate(extra_rotation, expand=True)
            if extra_rotation
            else base_image
        )

        text = get_ocr_text(image)
        upper_text = text.upper()

        score = sum(upper_text.count(term) * 20 for term in manifest_terms)
        score += sum(character.isalnum() for character in text)

        candidates.append((score, text))

    if candidates:
        return max(candidates, key=lambda item: item[0])[1]

    return native_text


# ==========================================
# 1. COMPLETE GPHA STATISTICAL PORT MASTER LIST
# ==========================================

FULL_PORT_MAP = {
    # AFRICA (RANGE: AF)
    "APAPA": ("OH", "NG", "AF"), "LAGOS": ("LG", "NG", "AF"), "TINCAN": ("LG", "NG", "AF"),
    "ONNE": ("OH", "NG", "AF"), "PORT HARCOURT": ("OH", "NG", "AF"), "LEKKI": ("OH", "NG", "AF"),
    "ABIDJAN": ("AJ", "IV", "AF"), "SAN PEDRO": ("OH", "IV", "AF"),
    "LOME": ("LM", "TG", "AF"), "COTONOU": ("CU", "BN", "AF"),
    "DAKAR": ("DA", "SN", "AF"), "BANJUL": ("BJ", "GM", "AF"),
    "CONAKRY": ("CN", "GN", "AF"), "FREETOWN": ("FT", "SL", "AF"),
    "MONROVIA": ("OH", "LB", "AF"), "NOUAKCHOTT": ("OH", "MR", "AF"),
    "NOUADHIBOU": ("OH", "MR", "AF"), "BATA": ("OH", "OH", "AF"), "MALABO": ("OH", "OH", "AF"),
    "DOUALA": ("DL", "CM", "AF"), "LIBREVILLE": ("LB", "GA", "AF"), "PORT GENTIL": ("PG", "GA", "AF"),
    "POINTE NOIRE": ("OH", "CG", "AF"), "POINT NOIRE": ("OH", "CG", "AF"),
    "MATADI": ("MA", "CG", "AF"), "KINSHASA": ("OH", "ZR", "AF"),
    "LUANDA": ("OH", "OH", "AF"), "LOBITO": ("OH", "OH", "AF"),
    "WALVIS BAY": ("OH", "OH", "AF"),
    "CAPETOWN": ("CN", "SA", "AF"), "CAPE TOWN": ("CN", "SA", "AF"),
    "DURBAN": ("DR", "SA", "AF"), "PORT ELIZABETH": ("PE", "SA", "AF"),
    "JOHANNESBURG": ("OH", "SA", "AF"), "EAST LONDON": ("OH", "SA", "AF"),
    "MAPUTO": ("MP", "MZ", "AF"), "BEIRA": ("OH", "MZ", "AF"),
    "DAR ES SALAAM": ("ES", "TZ", "AF"), "MOMBASA": ("OH", "KY", "AF"),
    "TEMA": ("TM", "GH", "AF"), "TAKORADI": ("TD", "GH", "AF"),
    "ALEXANDRIA": ("OH", "EY", "AF"), "DAMIETTA": ("OH", "EY", "AF"), "PORT SAID": ("OH", "EY", "AF"),
    "CASABLANCA": ("CB", "MC", "AF"), "CASSABLANCA": ("CB", "MC", "AF"),
    "AGADIR": ("AG", "MC", "AF"), "AGABIR": ("AG", "MC", "AF"), "TANGER": ("OH", "MC", "AF"),
    "ALGIERS": ("AL", "AG", "AF"), "ALGHERS": ("AL", "AG", "AF"),
    "TUNIS": ("OH", "TS", "AF"), "SFAX": ("OH", "TS", "AF"), "SOUSSE": ("OH", "TS", "AF"),
    "TRIPOLI": ("TL", "LY", "AF"), "BENGHAZI": ("BZ", "LY", "CT"),
    "DJIBOUTI": ("OH", "DJ", "AF"), "EHOALA": ("OH", "OH", "AF"),

    # UNITED KINGDOM & IRELAND (RANGE: UK)
    "TILBURY": ("TY", "UK", "UK"), "LIVERPOOL": ("LV", "UK", "UK"), "LONDON": ("LD", "UK", "UK"),
    "FELIXSTOWE": ("FX", "UK", "UK"), "SOUTHAMPTON": ("OH", "UK", "UK"), "TEESPORT": ("TE", "UK", "UK"),
    "CHIRK": ("TE", "UK", "UK"), "AVONMOUTH": ("AV", "UK", "UK"), "AMOIMOUTH": ("AV", "UK", "UK"),
    "BIRMINGHAM": ("BH", "UK", "UK"), "IMMINGHAM": ("IM", "UK", "UK"), "HULL": ("HU", "UK", "UK"),
    "HULI": ("HU", "UK", "UK"), "GOOLE": ("GO", "UK", "UK"), "GRANGEMOUTH": ("OH", "UK", "UK"),
    "DOVER": ("OH", "UK", "UK"), "HARWICH": ("HW", "UK", "UK"), "IPSWICH": ("IP", "UK", "UK"),
    "THAMES PORT": ("OH", "UK", "UK"), "NEW PORT": ("OH", "UK", "UK"),
    "DUBLIN": ("DU", "IR", "UK"), "BELFAST": ("BT", "IR", "UK"), "CORK": ("CK", "IR", "UK"),

    # CONTINENT EUROPE (RANGE: CT)
    "ANTWERP": ("AT", "BG", "CT"), "BRUGES": ("ZB", "BG", "CT"), "ZEEBRUGGE": ("ZB", "BG", "CT"),
    "ROTTERDAM": ("RM", "NL", "CT"), "AMSTERDAM": ("AM", "NL", "CT"), "FLUSHING": ("FS", "NL", "CT"),
    "DORDRECHT": ("RM", "NL", "CT"), "DELFZIJL": ("DZ", "NL", "CT"), "BARENDRECHT": ("OH", "NL", "CT"),
    "HAMBURG": ("HM", "GR", "CT"), "BREMERHAVEN": ("BM", "GR", "CT"), "BREMENHAVEN": ("BM", "GR", "CT"),
    "ROSTOCK": ("RK", "GR", "CT"), "NORDENHAM": ("NM", "GR", "CT"),
    "LE HAVRE": ("LH", "FR", "CT"), "DUNKERQUE": ("DK", "FR", "CT"), "DUNKIRK": ("DK", "FR", "CT"),
    "MARSEILLE": ("MS", "FR", "CT"), "MARSEILE": ("MS", "FR", "CT"), "ROUEN": ("RN", "FR", "CT"),
    "PORT VENDRES": ("BD", "FR", "CT"), "BORDEAUX": ("BD", "FR", "CT"), "FOS SUR MER": ("OH", "FR", "CT"),
    "NANTES": ("OH", "FR", "CT"), "CALAIS": ("OH", "FR", "CT"), "BREST": ("OH", "FR", "CT"),
    "SETE": ("SE", "FR", "CT"), "BOULOGNE": ("OH", "FR", "CT"),
    "GDYNIA": ("GA", "PL", "CT"), "GDANSK": ("GK", "PL", "CT"), "SZCZECIN": ("SZ", "PL", "CT"),
    "AARHUS": ("AH", "DK", "CT"), "COPENHAGEN": ("CP", "DK", "CT"),
    "GOTHENBURG": ("GB", "SE", "CT"), "GOTHENBORG": ("GB", "SE", "CT"), "STOCKHOLM": ("SM", "SE", "CT"),
    "HELSINGBORG": ("OH", "SE", "CT"), "NORRKOPING": ("OH", "SE", "CT"), "MALMOE": ("OH", "SE", "CT"),
    "OSLO": ("OS", "NW", "CT"), "BERGEN": ("OH", "NW", "CT"), "STAVANGER": ("OH", "NW", "CT"),
    "HELSINKI": ("OH", "FL", "CT"), "KOTKA": ("KK", "FL", "CT"),
    "KLAIPEDA": ("KE", "LT", "CT"), "RIGA": ("RG", "LV", "CT"), "LIEPAJA": ("LJ", "LV", "CT"),
    "TALLINN": ("OH", "ET", "CT"), "KUNDA": ("OH", "ET", "CT"),
    "ODESSA": ("OD", "UE", "CT"), "ODESSIA": ("OD", "UE", "CT"),
    "NOVOROSSIYSK": ("NV", "RU", "CT"), "ST. PETERSBURG": ("OH", "RU", "CT"),

    # MEDITERRANEAN (RANGE: ME)
    "BARCELONA": ("BC", "SP", "ME"), "VALENCIA": ("VL", "SP", "ME"),
    "ALGECIRAS": ("AR", "SP", "ME"), "ALGEDIRA": ("AR", "SP", "ME"),
    "BILBAO": ("BI", "SP", "ME"), "VIGO": ("VO", "SP", "ME"), "SANTANDER": ("SD", "SP", "ME"),
    "TARRAGONA": ("OH", "SP", "ME"), "CASTELLON": ("OH", "SP", "ME"), "ALICANTE": ("OH", "SP", "ME"),
    "CADIZ": ("OH", "SP", "ME"), "GIJON": ("OH", "SP", "ME"), "HUELVA": ("OH", "SP", "ME"),
    "GENOA": ("GE", "IT", "ME"), "GENOVA": ("GE", "IT", "ME"), "LIVORNO": ("LO", "IT", "ME"),
    "LEGHORN": ("LN", "IT", "ME"), "NAPLES": ("NS", "IT", "ME"), "NAPOLI": ("NS", "IT", "ME"),
    "SALERNO": ("SL", "IT", "ME"), "TRIESTE": ("TS", "IT", "ME"), "RAVENNA": ("RV", "IT", "ME"),
    "ANCONA": ("AC", "IT", "ME"), "VENICE": ("VI", "IT", "ME"), "CIVITAVECCHIA": ("OH", "IT", "ME"),
    "GIOIA TAURO": ("OH", "IT", "ME"), "LA SPEZIA": ("OH", "IT", "ME"),
    "LISBON": ("LS", "PG", "ME"), "LEIXOES": ("LX", "PG", "ME"),
    "PIRAEUS": ("PI", "GC", "ME"), "PIREAUS": ("PI", "GC", "ME"), "THESSALONIKI": ("OH", "GC", "ME"),
    "ISTANBUL": ("IL", "TU", "ME"), "IZMIT": ("OH", "TU", "ME"), "AMBARLI": ("OH", "TU", "ME"),
    "MARPORT": ("OH", "TU", "ME"), "IZMIR": ("OH", "TU", "ME"), "IZMAR": ("OH", "TU", "ME"),
    "MERSIN": ("OH", "TU", "ME"), "GEBZE": ("OH", "TU", "ME"), "GEMLIK": ("OH", "TU", "ME"),
    "LIMASSOL": ("LL", "CY", "ME"), "CONSTANTA": ("CA", "RM", "ME"), "VARNA": ("VN", "BG", "CT"),
    "TENERIFE": ("TF", "CI", "ME"), "LAS PALMAS": ("LP", "CI", "ME"),

    # FAR EAST & ASIA (RANGE: FE)
    "SHANGHAI": ("SH", "CH", "FE"), "NINGBO": ("OH", "CH", "FE"), "QINGDAO": ("OH", "CH", "FE"),
    "XIAMEN": ("OH", "CH", "FE"), "XIAMENG": ("OH", "CH", "FE"), "NANSHA": ("OH", "CH", "FE"),
    "SHEKOU": ("OH", "CH", "FE"), "YANTIAN": ("OH", "CH", "FE"), "GUANGZHOU": ("OH", "CH", "FE"),
    "DALIAN": ("OH", "CH", "FE"), "TIANJIN": ("OH", "CH", "FE"), "XINGANG": ("OH", "CH", "FE"),
    "HONGKONG": ("HK", "HK", "FE"), "HONG KONG": ("HK", "HK", "FE"),
    "BUSAN": ("BU", "SK", "FE"), "PUSAN": ("BU", "SK", "FE"), "INCHEON": ("OH", "SK", "FE"),
    "TOKYO": ("TK", "JP", "FE"), "YOKOHAMA": ("YK", "JP", "FE"), "KOBE": ("KB", "JP", "FE"),
    "OSAKA": ("OK", "JP", "FE"), "NAGOYA": ("NA", "JP", "FE"),
    "SINGAPORE": ("SG", "SG", "FE"),
    "PORT KLANG": ("OH", "MY", "FE"), "PORT KELANG": ("OH", "MY", "FE"),
    "TANJUNG PELEPAS": ("OH", "MY", "FE"), "PENANG": ("PM", "MY", "FE"), "PASIR GUDANG": ("OH", "MY", "FE"),
    "HO CHI MINH": ("OH", "VT", "FE"), "HAIPHONG": ("OH", "VT", "FE"),
    "BANGKOK": ("BK", "TH", "FE"), "LAEM CHABANG": ("OH", "TH", "FE"),
    "JAKARTA": ("JK", "ID", "FE"), "SURABAYA": ("SB", "ID", "FE"), "BELAWAN": ("OH", "ID", "FE"),
    "MUMBAI": ("BY", "IN", "FE"), "BOMBAY": ("BY", "IN", "FE"),
    "NHAVA SHEVA": ("OH", "IN", "FE"), "NEVA SHEVA": ("OH", "IN", "FE"),
    "MUNDRA": ("OH", "IN", "FE"), "CHENNAI": ("MD", "IN", "FE"), "MADRAS": ("MD", "IN", "FE"),
    "TUTICORIN": ("OH", "IN", "FE"), "VISAKHAPATNAM": ("OH", "IN", "FE"), "COCHIN": ("OH", "IN", "FE"),
    "KOLKATA": ("OH", "IN", "FE"), "CALCUTTA": ("OH", "IN", "FE"), "ENNORE": ("OH", "IN", "FE"),
    "KARACHI": ("KR", "PK", "FE"), "PORT QASIM": ("OH", "PK", "FE"),
    "CHITTAGONG": ("CG", "BD", "FE"), "CHITAGONG": ("CG", "BD", "FE"),
    "COLOMBO": ("OH", "SR", "FE"), "KAOHSIUNG": ("KA", "TW", "FE"), "KEELUNG": ("KL", "TW", "FE"),
    "MANILA": ("ML", "PH", "FE"),

    # NORTH AMERICA (RANGE: NA)
    "NEW YORK": ("NY", "US", "NA"), "SAVANNAH": ("SV", "US", "NA"), "HOUSTON": ("HO", "US", "NA"),
    "BALTIMORE": ("BE", "US", "NA"), "NORFOLK": ("NF", "US", "NA"), "NEW ORLEANS": ("NO", "US", "NA"),
    "CHARLESTON": ("CT", "US", "NA"), "LOS ANGELES": ("LA", "US", "NA"), "LONG BEACH": ("LO", "US", "NA"),
    "OAKLAND": ("OH", "US", "NA"), "SEATTLE": ("OH", "US", "NA"), "PHILADELPHIA": ("PH", "US", "NA"),
    "MONTREAL": ("MT", "CN", "NA"), "TORONTO": ("TR", "CN", "NA"), "VANCOUVER": ("VC", "CN", "NA"),
    "HALIFAX": ("HX", "US", "NA"),

    # OTHER / SOUTH AMERICA / OCEANIA / MIDDLE EAST (RANGE: OH)
    "SANTOS": ("ST", "BZ", "OH"), "RIO DE JANEIRO": ("RO", "BZ", "OH"), "PARANAGUA": ("OH", "BZ", "OH"),
    "BUENOS AIRES": ("BO", "AR", "OH"), "CALLAO": ("OH", "PU", "OH"),
    "SYDNEY": ("SY", "AU", "OH"), "MELBOURNE": ("MB", "AU", "OH"), "BRISBANE": ("BB", "AU", "OH"),
    "FREMANTLE": ("FM", "AU", "OH"), "AUCKLAND": ("AD", "NZ", "OH"),
    "DUBAI": ("DB", "AE", "OH"), "JEBEL ALI": ("JB", "AE", "OH"), "JABEL ALI": ("JB", "AE", "OH"),
    "JEDDAH": ("JD", "SB", "OH"), "DAMMAM": ("DM", "SB", "OH"),
    "AQABA": ("AQ", "JD", "OH"), "ASHDOD": ("AS", "IL", "OH"), "HAIFA": ("HF", "IL", "OH"),
    "BEIRUT": ("BR", "LN", "OH"), "KUWAIT": ("OH", "KU", "OH"), "DOHA": ("OH", "OH", "OH"),
    "MESAIEED": ("OH", "AE", "OH"), "QAPCO": ("OH", "AE", "OH")
}


# Country fallback list mapping country names to GPHA Country Code & Range
GPHA_COUNTRY_MAP = {
    # AFRICA
    "NIGERIA": ("NG", "AF"), "TOGO": ("TG", "AF"), "BENIN": ("BN", "AF"),
    "GHANA": ("GH", "AF"), "COTE D'IVOIRE": ("IV", "AF"), "IVORY COAST": ("IV", "AF"),
    "BURKINA FASO": ("BF", "AF"), "NIGER": ("NR", "AF"), "MALI": ("ML", "AF"),
    "SENEGAL": ("SN", "AF"), "SOUTH AFRICA": ("SA", "AF"), "CAMEROON": ("CM", "AF"),
    "CONGO": ("CG", "AF"), "GABON": ("GA", "AF"), "GUINEA": ("GN", "AF"),
    "SIERRA LEONE": ("SL", "AF"), "LIBERIA": ("LB", "AF"), "MAURITANIA": ("MR", "AF"),
    "EGYPT": ("EY", "AF"), "MOROCCO": ("MC", "AF"), "ALGERIA": ("AG", "AF"),
    "TUNISIA": ("TS", "AF"), "LIBYA": ("LY", "AF"), "TANZANIA": ("TZ", "AF"),
    "KENYA": ("KY", "AF"), "ANGOLA": ("OH", "AF"), "MOZAMBIQUE": ("MZ", "AF"),
    "NAMIBIA": ("OH", "AF"), "GAMBIA": ("GM", "AF"),

    # UNITED KINGDOM & IRELAND
    "UNITED KINGDOM": ("UK", "UK"), "IRELAND": ("IR", "UK"),

    # CONTINENT EUROPE
    "NETHERLANDS": ("NL", "CT"), "HOLLAND": ("NL", "CT"), "BELGIUM": ("BG", "CT"),
    "GERMANY": ("GR", "CT"), "FRANCE": ("FR", "CT"), "POLAND": ("PL", "CT"),
    "DENMARK": ("DK", "CT"), "SWEDEN": ("SE", "CT"), "NORWAY": ("NW", "CT"),
    "FINLAND": ("FL", "CT"), "ESTONIA": ("ET", "CT"), "LATVIA": ("LV", "CT"),
    "LITHUANIA": ("LT", "CT"), "UKRAINE": ("UE", "CT"), "RUSSIA": ("RU", "CT"),

    # MEDITERRANEAN
    "SPAIN": ("SP", "ME"), "ITALY": ("IT", "ME"), "GREECE": ("GC", "ME"),
    "PORTUGAL": ("PG", "ME"), "TURKEY": ("TU", "ME"), "TURKIYE": ("TU", "ME"),
    "CYPRUS": ("CY", "ME"), "ROMANIA": ("RM", "ME"), "BULGARIA": ("BU", "ME"),
    "CANARY ISLANDS": ("CI", "ME"), "SLOVENIA": ("OH", "ME"),

    # FAR EAST & ASIA
    "INDIA": ("IN", "FE"), "CHINA": ("CH", "FE"), "JAPAN": ("JP", "FE"),
    "SOUTH KOREA": ("SK", "FE"), "KOREA": ("SK", "FE"), "VIETNAM": ("VT", "FE"),
    "MALAYSIA": ("MY", "FE"), "INDONESIA": ("ID", "FE"), "THAILAND": ("TH", "FE"),
    "SINGAPORE": ("SG", "FE"), "TAIWAN": ("TW", "FE"), "HONG KONG": ("HK", "FE"),
    "HONGKONG": ("HK", "FE"), "PAKISTAN": ("PK", "FE"), "BANGLADESH": ("BD", "FE"),
    "SRI LANKA": ("SR", "FE"), "PHILIPPINES": ("PH", "FE"),

    # NORTH AMERICA
    "UNITED STATES": ("US", "NA"), "USA": ("US", "NA"), "CANADA": ("CN", "NA"),

    # OTHER / SOUTH AMERICA / MIDDLE EAST / OCEANIA
    "BRAZIL": ("BZ", "OH"), "ARGENTINA": ("AR", "OH"), "CHILE": ("CL", "OH"),
    "PERU": ("PU", "OH"), "AUSTRALIA": ("AU", "OH"), "NEW ZEALAND": ("NZ", "OH"),
    "UNITED ARAB EMIRATES": ("AE", "OH"), "UAE": ("AE", "OH"), "DUBAI": ("AE", "OH"),
    "SAUDI ARABIA": ("SB", "OH"), "JORDAN": ("JD", "OH"), "ISRAEL": ("IL", "OH")
}


# ISO prefix translator to Ghana GPHA country codes
ISO_PREFIX_MAP = {
    "NG": ("NG", "AF"), "TG": ("TG", "AF"), "BN": ("BN", "AF"), "BJ": ("BN", "AF"),
    "IV": ("IV", "AF"), "CI": ("IV", "AF"), "SN": ("SN", "AF"), "ZA": ("SA", "AF"),
    "SA": ("SA", "AF"), "GH": ("GH", "AF"), "CM": ("CM", "AF"), "MR": ("MR", "AF"),
    "EY": ("EY", "AF"), "EG": ("EY", "AF"), "MC": ("MC", "AF"), "MA": ("MC", "AF"),
    "UK": ("UK", "UK"), "GB": ("UK", "UK"), "IR": ("IR", "UK"), "IE": ("IR", "UK"),
    "NL": ("NL", "CT"), "BG": ("BG", "CT"), "BE": ("BG", "CT"), "GR": ("GR", "CT"),
    "DE": ("GR", "CT"), "FR": ("FR", "CT"), "PL": ("PL", "CT"), "DK": ("DK", "CT"),
    "SE": ("SE", "CT"), "NW": ("NW", "CT"), "NO": ("NW", "CT"), "FL": ("FL", "CT"),
    "SP": ("SP", "ME"), "ES": ("SP", "ME"), "IT": ("IT", "ME"), "GC": ("GC", "ME"),
    "PG": ("PG", "ME"), "PT": ("PG", "ME"), "TU": ("TU", "ME"), "TR": ("TU", "ME"),
    "CH": ("CH", "FE"), "CN": ("CH", "FE"), "IN": ("IN", "FE"), "JP": ("JP", "FE"),
    "SK": ("SK", "FE"), "KR": ("SK", "FE"), "VT": ("VT", "FE"), "VN": ("VT", "FE"),
    "MY": ("MY", "FE"), "SG": ("SG", "FE"), "SR": ("SR", "FE"), "LK": ("SR", "FE"),
    "US": ("US", "NA"), "BZ": ("BZ", "OH"), "BR": ("BZ", "OH"), "AE": ("AE", "OH")
}

SORTED_PORT_MAP = sorted(
    FULL_PORT_MAP.items(),
    key=lambda item: len(item[0]),
    reverse=True
)


# ==========================================
# 2. RESOLVER ENGINE
# ==========================================

SEARCH_CACHE = {}


def fast_web_lookup(term: str) -> str:
    clean_term = term.strip().upper()

    if clean_term in SEARCH_CACHE:
        return SEARCH_CACHE[clean_term]

    try:
        url = (
            "https://en.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={quote_plus(clean_term)}&utf8=&format=json"
        )
        headers = {"User-Agent": "GhanaManifestBot/1.0"}
        response = requests.get(url, headers=headers, timeout=1.5)

        if response.status_code == 200:
            data = response.json()
            snippets = [
                item.get("snippet", "")
                for item in data.get("query", {}).get("search", [])[:2]
            ]
            result_text = re.sub(
                r"<[^>]+>",
                " ",
                " ".join(snippets)
            ).upper()
            SEARCH_CACHE[clean_term] = result_text
            return result_text
    except Exception:
        pass

    SEARCH_CACHE[clean_term] = ""
    return ""


def resolve_port_info(pod_text: str, use_web_search: bool = True) -> tuple:
    clean = pod_text.upper().strip()
    clean = re.sub(
        r"^(?:FINAL DISCH|VESSEL DISCH|PORT OF DISCHARGE|PLACE OF DELIVERY|"
        r"FINAL DESTINATION|DEL|TO)\s*[:\.]?\s*",
        "",
        clean
    )

    for port_name, port_value in SORTED_PORT_MAP:
        if re.search(rf"\b{re.escape(port_name)}\b", clean):
            return port_value

    iso_match = re.search(r"\b([A-Z]{2})-([A-Z0-9\s]+)\b", clean)
    if iso_match:
        iso_code = iso_match.group(1)
        port_part = iso_match.group(2).strip()

        for port_name, port_value in SORTED_PORT_MAP:
            if re.search(rf"\b{re.escape(port_name)}\b", port_part):
                return port_value

        if iso_code in ISO_PREFIX_MAP:
            country_code, range_code = ISO_PREFIX_MAP[iso_code]
            return ("OH", country_code, range_code)

    for country_name, (country_code, range_code) in GPHA_COUNTRY_MAP.items():
        if re.search(rf"\b{re.escape(country_name)}\b", clean):
            return ("OH", country_code, range_code)

    if use_web_search and len(clean) > 2:
        result = fast_web_lookup(f"{clean} seaport city country")
        if result:
            for country_name, (country_code, range_code) in GPHA_COUNTRY_MAP.items():
                if re.search(rf"\b{re.escape(country_name)}\b", result):
                    return ("OH", country_code, range_code)

    return ("OH", "OH", "AF")


# ==========================================
# 3. SHIP NAME EXTRACTOR
# ==========================================

HEADER_NOISE_PHRASES = [
    "PORT WHERE REPORT", "REPORT IS MODE", "REPORT IS MADE", "NAME OF MASTER",
    "NATIONALITY OF SHIP", "PORT OF LOADING", "PORT OF DISCHARGE", "FINAL DESTINATION",
    "SAILING DATE", "VESSEL IMO", "PAGE NO", "OUTWARD", "INBOUND", "CARGO MANIFEST",
    "FOREIGN CARGO", "VOYAGE NO", "SERVICE CODE", "PLACE OF ACCEPTANCE", "PLACE OF DELIVERY"
]


def is_header_noise(text: str) -> bool:
    text_upper = text.upper().strip()
    return any(noise in text_upper for noise in HEADER_NOISE_PHRASES)


def clean_vessel_name(raw_name: str) -> str:
    name = raw_name.strip()
    name = re.sub(
        r"^(?:1\.\s*)?(?:NAME\s+OF\s+(?:VESSEL|SHIP)|VESSEL\s+NAME|SHIP\s+NAME|VESSEL|SHIP)\s*[:\.]?\s*",
        "",
        name,
        flags=re.IGNORECASE
    )
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

    for index, line in enumerate(lines[:60]):
        inline_match = re.search(
            r"\b(?:NAME\s+OF\s+(?:VESSEL|SHIP)|VESSEL\s+NAME|SHIP\s+NAME|VESSEL)\s*:\s*([A-Za-z0-9\s\.\-/'\"]+)",
            line,
            re.IGNORECASE
        )
        if inline_match:
            candidate = clean_vessel_name(inline_match.group(1))
            if candidate and not is_header_noise(candidate) and len(candidate) > 2:
                return candidate

        if re.search(
            r"\b(?:1\.\s*)?(?:NAME\s+OF\s+(?:VESSEL|SHIP)|VESSEL\s+NAME|SHIP\s+NAME|VESSEL|SHIP)\b",
            line,
            re.IGNORECASE
        ):
            for next_line in lines[index + 1:index + 5]:
                if is_header_noise(next_line):
                    continue

                candidate = clean_vessel_name(next_line)
                if candidate and not is_header_noise(candidate) and len(candidate) > 2:
                    return candidate

    for line in lines[:25]:
        match = re.search(r"^\s*([A-Za-z\s]{3,25})\s+\d{3,4}/[EWNS]", line)
        if match:
            candidate = clean_vessel_name(match.group(1))
            if candidate and not is_header_noise(candidate):
                return candidate

    return "UNKNOWN VESSEL"


# ==========================================
# 4. COMMODITY & CONTAINER CLASSIFIER
# ==========================================

def classify_commodity(desc: str, hs_code: str = "", use_web_search: bool = False) -> str:
    text = (desc + " " + hs_code).upper()

    def match_rules(text_to_check):
        if any(key in text_to_check for key in ["COCOA BEAN", "RAW COCOA", "BEANS OF COCOA"]) or hs_code.startswith("1801"):
            return "LCB"
        if any(key in text_to_check for key in ["COCOA BUTTER", "COCOA CAKE", "COCOA POWDER", "COCOA LIQUOR", "COCOA MASS", "COCOA PASTE", "CHOCOLATE", "COCOA NIB"]) or hs_code.startswith(("1803", "1804", "1805", "1806")):
            return "LCP"
        if "BANANA" in text_to_check or hs_code.startswith("0803"):
            return "LBN"
        if "PINEAPPLE" in text_to_check or hs_code.startswith("080430"):
            return "LPN"
        if "YAM" in text_to_check or hs_code.startswith("0714"):
            return "LYM"
        if any(key in text_to_check for key in ["CASHEW", "ANACARDE"]) or hs_code.startswith("080131"):
            return "LCA"
        if any(key in text_to_check for key in ["SHEA NUT", "SHEANUT", "KARITE"]):
            return "LSH"
        if any(key in text_to_check for key in ["TOBACCO", "GINGER", "CHILLI", "TURMERIC", "SESAME", "SEEDS", "COCONUT", "COIR", "COCOPEAT", "PEPPER", "CASHEW SHELL", "COCOA SHELL", "CHARCOAL"]) or hs_code.startswith(("0904", "0910", "1207", "2401", "5305")):
            return "LNO"
        if any(key in text_to_check for key in ["TUNA", "FROZEN FISH", "SKIPJACK", "YELLOWFIN", "MACKEREL", "SARDINE", "MEAT", "POULTRY", "CHICKEN", "BUFFALO", "PRAWNS", "SEAFOOD"]) or hs_code.startswith(("0207", "0303", "0306", "0201", "0202")):
            return "LFI"
        if "CANNED TUNA" in text_to_check or "CANNED FISH" in text_to_check:
            return "LFS"
        if any(key in text_to_check for key in ["ROUND LOG", "TEAK POLE", "LOGS", "ROUGH SQUARE LOGS", "ROUGH SQUARES", "TEAK ROUGH"]) or (hs_code.startswith("4403") and "SAWN" not in text_to_check):
            return "LLG"
        if any(key in text_to_check for key in ["LUMBER", "SAWN TIMBER", "TEAK SAWN", "TEAK IN CONTAINER"]) or hs_code.startswith("4407"):
            return "LST"
        if any(key in text_to_check for key in ["FURNITURE", "DOOR", "MOULDING"]):
            return "LFW"
        if any(key in text_to_check for key in ["SCRAP", "COPPER SCRAP", "ALUMINIUM SCRAP", "STEEL SCRAP", "IRON SCRAP"]) or hs_code.startswith(("7204", "7404", "7602")):
            return "LMS"
        if any(key in text_to_check for key in ["RUBBER", "TIRE", "TYRE", "TUBES"]):
            return "LRB"
        if any(key in text_to_check for key in ["ALUMINIUM INGOT", "ALUMINUM INGOT", "ALUMINIUM WIRE ROD", "ALUMINUM WIRE"]):
            return "LAL"
        if any(key in text_to_check for key in ["VEHICLE", "USED AUTO", "CARS", "TOYOTA", "HYUNDAI", "MERCEDES", "MAZDA", "HONDA", "AUTOS", "AUTORICKSHAW", "BAJAJ"]) or hs_code.startswith("8703"):
            return "LVE"
        if any(key in text_to_check for key in ["TRUCK", "FORKLIFT", "TRACTOR"]) or hs_code.startswith("8704"):
            return "LTR"
        if any(key in text_to_check for key in ["MACHINE", "ENGINE", "PUMP", "EQUIPMENT", "SPARE PARTS", "MOULDS", "LATHE", "INCENSE", "MATCHET", "AGRICULTURAL IMPLEMENT", "REFRIGERATING"]) or hs_code.startswith(("84", "85", "3307", "8201")):
            return "LME"
        if any(key in text_to_check for key in ["CHEMICAL", "ZINC OXIDE", "CALCIUM", "RESIN", "POLYETHYLENE", "HDPE", "LLDPE", "GYPSUM", "CHLORIDE", "SALT", "ETHYL ACETATE", "HEXANE", "SOLVENT", "ACETATE", "MANGANESE", "ENZYMES", "BOSTIK"]) or hs_code.startswith(("2501", "2520", "28", "29", "3507", "38", "3901", "7202")):
            return "LCH"
        if any(key in text_to_check for key in ["SPAGHETTI", "MACARONI", "FOODSTUFF", "BISCUITS", "SUGAR", "OIL", "SOYABEAN OIL", "BEVERAGE", "VODKA", "SOAP", "BEAUTY", "BEAUTY PREPARATION", "COSMETIC", "TEXTILE", "CLOTHING", "USED CLOTH", "SHOES", "SYNTHETIC FIBER", "HAIR", "RICE", "PARBOILED RICE", "TEA", "MEDICINE", "PHARMACEUTICAL", "TAILORING", "POPPADOM", "FILTERATION", "YARN", "FABRIC", "PAPERBOARD", "FOOTWEAR", "SPORTS MATERIAL", "CATERING"]):
            return "LPE"
        if "GRANITE" in text_to_check or "TILES" in text_to_check or hs_code.startswith("6907"):
            return "LGC"
        return None

    result = match_rules(text)
    if result:
        return result

    if use_web_search and len(desc.strip()) > 3:
        cleaned_words = [
            word
            for word in re.sub(r"[^A-Za-z]", " ", desc).split()
            if len(word) > 3
        ][:3]

        if cleaned_words:
            web_info = fast_web_lookup(" ".join(cleaned_words) + " product")
            if web_info:
                result = match_rules(web_info)
                if result:
                    return result

    return "LGC"


def normalize_container(sz_text: str):
    size_text = str(sz_text).upper()

    if any(key in size_text for key in ["REEF", "40RH", "40RA", "40RC", "45R", "40R", "40HR", "R5"]):
        return "40R"
    if any(key in size_text for key in ["20R", "20RF", "R2"]):
        return "20R"
    if any(key in size_text for key in ["40", "40D", "40HC", "40HQ", "40ST", "42G", "45G", "40 OPEN", "D5"]):
        return "40D"
    if any(key in size_text for key in ["20", "20D", "20ST", "20GP", "22G", "DV20", "D2", "20 BO"]):
        return "20D"

    return "40D"


def is_empty_equipment(text: str) -> bool:
    text_upper = text.upper()

    empty_equipment_patterns = [
        r"\bEMPTY\s+(?:CONTAINER|ISO\s*TANK|TANK|CNTR|REEFER|UNIT|EQUIPMENT)\b",
        r"\b(?:CONTAINER|CNTR|TANK)\s+(?:STC\s+)?EMPTY\b",
        r"\bMT\s+CONTAINER\b",
        r"\bEMPTY\s+WITH\s+RESIDUE\b",
        r"\bRESIDUE\s*\(SOC\)\b",
        r"\bEMPTY\s+SOC\b"
    ]

    return any(re.search(pattern, text_upper) for pattern in empty_equipment_patterns)


def parse_num(val_str: str) -> float:
    try:
        return float(val_str.replace(" ", "").replace(",", ""))
    except Exception:
        return 0.0


# ==========================================
# 5. CARRIER PARSERS
# ==========================================

def parse_one(pdf_text: str, ship_name: str, use_web_search: bool = True):
    rows = []
    ship = ship_name

    bl_matches = []
    for match in re.finditer(r"\b(ONEY[A-Z0-9]{8,15}|[A-Z]{4}\d{8,12})\b", pdf_text):
        bl_number = match.group(1)
        if bl_number not in bl_matches:
            bl_matches.append(bl_number)

    for bl_number in bl_matches:
        pattern = (
            rf"(?:^|\n)\s*{re.escape(bl_number)}\b[\s\S]*?"
            rf"(?=(?:\n\s*ONEY[A-Z0-9]+\b|\n\s*OUTWARD|\Z))"
        )
        matches = re.findall(pattern, pdf_text)
        chunk = "\n".join(matches) if matches else ""

        if not chunk or is_empty_equipment(chunk):
            continue

        destination_match = re.search(
            r"(?:Final destination|5b\.Port of discharge|Port of discharge)"
            r"[^\n]*\n[^\n]*?\s*([A-Za-z0-9\s-]+?)(?:\s{2,}|\n|$)",
            chunk,
            re.IGNORECASE
        )
        pod_raw = destination_match.group(1).strip().upper() if destination_match else ""

        if not pod_raw:
            page_destination = re.search(
                r"5b\.Port of discharge\s*([^\n]+)",
                pdf_text,
                re.IGNORECASE
            )
            pod_raw = page_destination.group(1).strip().upper() if page_destination else "DURBAN"

        port_info = resolve_port_info(pod_raw, use_web_search)

        weight_match = re.search(
            r"(?:TOTAL GROSS WEIGHT\s*:\s*|GROSS WEIGHT\s*[：:]\s*|1\)\s*)"
            r"([\d\s\.,]+)(?:\s*MTS|\s*KG|\s*\(|\n)",
            chunk,
            re.IGNORECASE
        )
        value = parse_num(weight_match.group(1)) if weight_match else 0.0
        tonnage = round(value if 0.0 < value < 500.0 else value / 1000.0, 2)

        container_groups = re.findall(
            r"(\d+)\s*X\s*(\d{2}[A-Za-z0-9]+)",
            chunk,
            re.IGNORECASE
        )

        desc_match = re.search(
            r"(?:SAID TO CONTAIN:\s*(?:STC\s+)?|\d+\s+PKGS\s+)"
            r"([A-Za-z\s\(\)]+?)(?:CN>|HS CODE|FORM M|\n\s*\d+\))",
            chunk,
            re.IGNORECASE
        )
        description = desc_match.group(1).strip() if desc_match else "GENERAL CARGO"
        commodity = classify_commodity(description, use_web_search=use_web_search)

        if container_groups:
            total_containers = sum(int(quantity) for quantity, _ in container_groups)

            for quantity_text, size_text in container_groups:
                quantity = int(quantity_text)
                container_tonnage = (
                    round(tonnage * (quantity / total_containers), 2)
                    if total_containers > 0
                    else tonnage
                )

                rows.append({
                    "SHIP": ship,
                    "SHIP LINE": "OCEAN NETWORK EXPRESS",
                    "AGENT": "ONE GH. LTD",
                    "PORT": port_info[0],
                    "CTRY": port_info[1],
                    "RANGE": port_info[2],
                    "CONTYPE": normalize_container(size_text),
                    "CONTQTY": quantity,
                    "COMMODITY": commodity,
                    "TONNAGES": f"{container_tonnage:.2f}"
                })
        else:
            container_tags = re.findall(r"\(CN\)\s+([A-Z0-9]+)", chunk)
            container_quantity = len(container_tags) if container_tags else 1
            container_type = "40D" if "40" in chunk else "20D"

            rows.append({
                "SHIP": ship,
                "SHIP LINE": "OCEAN NETWORK EXPRESS",
                "AGENT": "ONE GH. LTD",
                "PORT": port_info[0],
                "CTRY": port_info[1],
                "RANGE": port_info[2],
                "CONTYPE": container_type,
                "CONTQTY": container_quantity,
                "COMMODITY": commodity,
                "TONNAGES": f"{tonnage:.2f}"
            })

    return rows


def parse_pil(pdf_text: str, ship_name: str, use_web_search: bool = True):
    rows = []
    ship = ship_name

    sections = re.split(r"(?:\n|^)(?=OUTWARD)", pdf_text)

    for section in sections:
        pod_match = re.search(r"5b\.Port of discharge\s*([^\n]+)", section, re.IGNORECASE)
        pod_raw = pod_match.group(1).strip().upper() if pod_match else "NANSHA"
        port_info = resolve_port_info(pod_raw, use_web_search)

        bl_chunks = re.split(r"(?:\n|^)(?=N/A\s+[A-Z0-9]{8,15})", section)

        for chunk in bl_chunks:
            if is_empty_equipment(chunk):
                continue

            weight_match = re.search(r"1\)\s*([\d\s\.,]+)\s*KGS", chunk, re.IGNORECASE)
            raw_weight = parse_num(weight_match.group(1)) if weight_match else 0.0
            tonnage = round(raw_weight / 1000.0, 2)

            container_types = re.findall(
                r"\((?:CY/CY|FCL/FCL)\)\s*-\s*([A-Z0-9]+)",
                chunk
            )

            if container_types:
                container_type = normalize_container(container_types[0])
                container_quantity = len(container_types)
            else:
                quantity_match = re.search(r"(\d+)\s*X\s*(\d{2}[A-Z]*)", chunk)
                container_quantity = int(quantity_match.group(1)) if quantity_match else 1
                container_type = normalize_container(quantity_match.group(2)) if quantity_match else "20D"

            description_match = re.search(
                r"(?:SAID TO CONTAIN:|CONTAINER\(S\)\s+SAID\s+TO\s+CONTAIN:)\s*([^\n]+)",
                chunk,
                re.IGNORECASE
            )
            description = description_match.group(1).strip() if description_match else "GENERAL CARGO"
            commodity = classify_commodity(description, use_web_search=use_web_search)

            rows.append({
                "SHIP": ship,
                "SHIP LINE": "PACIFIC INTERNATIONAL LINES",
                "AGENT": "PIL GH. LTD",
                "PORT": port_info[0],
                "CTRY": port_info[1],
                "RANGE": port_info[2],
                "CONTYPE": container_type,
                "CONTQTY": container_quantity,
                "COMMODITY": commodity,
                "TONNAGES": f"{tonnage:.2f}"
            })

    return rows


def parse_goldstar(pdf_text: str, ship_name: str, use_web_search: bool = True):
    rows = []
    ship = ship_name

    bl_chunks = re.split(r"(?:\n|^)(?=Bill type:)", pdf_text)

    for chunk in bl_chunks[1:]:
        if is_empty_equipment(chunk):
            continue

        search_text = chunk if "To :" in chunk else pdf_text
        destination_match = re.search(r"To\s*:\s*([^\n]+)", search_text)
        pod_raw = destination_match.group(1).strip().upper() if destination_match else "ABIDJAN"
        port_info = resolve_port_info(pod_raw, use_web_search)

        quantity_match = re.search(r"(\d+)\s*cont\s*([A-Z0-9]+)\s+([\d\s\.,]+)", chunk)

        if quantity_match:
            container_quantity = int(quantity_match.group(1))
            container_type = normalize_container(quantity_match.group(2))
            tonnage = round(parse_num(quantity_match.group(3)) / 1000.0, 2)
        else:
            container_quantity = 1
            container_type = "20D"
            tonnage = 0.0

        description_match = re.search(
            r"CONTAINERS S\.L\.A\.C\.\s*\n\s*([A-Z\s\.]+)",
            chunk
        )
        description = description_match.group(1).strip() if description_match else "GENERAL CARGO"
        commodity = classify_commodity(description, use_web_search=use_web_search)

        rows.append({
            "SHIP": ship,
            "SHIP LINE": "GOLD STAR LINE",
            "AGENT": "ISAG GH. LTD",
            "PORT": port_info[0],
            "CTRY": port_info[1],
            "RANGE": port_info[2],
            "CONTYPE": container_type,
            "CONTQTY": container_quantity,
            "COMMODITY": commodity,
            "TONNAGES": f"{tonnage:.2f}"
        })

    return rows


def parse_arkas(pdf_text: str, ship_name: str, use_web_search: bool = True):
    rows = []
    ship = ship_name

    bl_chunks = re.split(r"(?:\n|^)(?=B/L#:)", pdf_text)

    for chunk in bl_chunks[1:]:
        if is_empty_equipment(chunk):
            continue

        pod_match = re.search(
            r"Port Of Discharge\s*\n?\s*([A-Z\s]+?)(?:Terminal|\n)",
            chunk,
            re.IGNORECASE
        )
        pod_raw = pod_match.group(1).strip().upper() if pod_match else "GENOA"
        port_info = resolve_port_info(pod_raw, use_web_search)

        weight_match = re.search(r"BL GROSS WEIGHT\s*:\s*([\d\s\.,]+)", chunk, re.IGNORECASE)
        tonnage = round(parse_num(weight_match.group(1)) / 1000.0, 2) if weight_match else 0.0

        container_match = re.search(
            r"BL TOTAL CONTAINERS:\s*(\d+)\s*\n\s*\d+\*(\d{2}\s*[A-Z]+)",
            chunk
        )

        if container_match:
            container_quantity = int(container_match.group(1))
            container_type = normalize_container(container_match.group(2))
        else:
            container_quantity = 1
            container_type = "40D"

        description_match = re.search(
            r"\d+\s+(?:CARTONS|BAGS|PACKAGES)\s*\n\s*([A-Z\s]+?)(?:NET WEIGHT|HS CODE|\n)",
            chunk,
            re.IGNORECASE
        )
        description = description_match.group(1).strip() if description_match else "COCOA PRODUCTS"
        commodity = classify_commodity(description, use_web_search=use_web_search)

        rows.append({
            "SHIP": ship,
            "SHIP LINE": "ARKAS LINES",
            "AGENT": "ARKAS GH. LTD",
            "PORT": port_info[0],
            "CTRY": port_info[1],
            "RANGE": port_info[2],
            "CONTYPE": container_type,
            "CONTQTY": container_quantity,
            "COMMODITY": commodity,
            "TONNAGES": f"{tonnage:.2f}"
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

            pod_match = re.search(
                r"(?:PORT OF DISCHARGE|PLACE OF DELIVERY)\s*:\s*([A-Z\s]+)",
                chunk,
                re.IGNORECASE
            )
            pod_raw = pod_match.group(1).strip().upper() if pod_match else "APAPA"
            port_info = resolve_port_info(pod_raw, use_web_search)

            weight_match = re.search(
                r"GROSS WEIGHT\s*[：:]\s*([\d\s\.,]+)\s*KG",
                chunk,
                re.IGNORECASE
            )
            tonnage = round(parse_num(weight_match.group(1)) / 1000.0, 2) if weight_match else 0.0

            container_lines = re.findall(
                r"\b([0-9]{2}[A-Z]{2})\b[^\n]*\bFCL/FCL\b",
                chunk
            )
            container_quantity = len(container_lines) if container_lines else 1
            container_type = normalize_container(container_lines[0]) if container_lines else "20D"

            description_match = re.search(
                r"DESCRIPTION OF GOODS\s*\n\s*([A-Z0-9\s\(\)\.,-]+?)"
                r"(?:GROSS WEIGHT|FORM M|HS CODE|\n\n)",
                chunk,
                re.IGNORECASE
            )
            description = description_match.group(1).strip() if description_match else "GENERAL CARGO"
            commodity = classify_commodity(description, use_web_search=use_web_search)

            rows.append({
                "SHIP": ship,
                "SHIP LINE": "COSCO SHIPPING LINE",
                "AGENT": "COSCO GH. LTD",
                "PORT": port_info[0],
                "CTRY": port_info[1],
                "RANGE": port_info[2],
                "CONTYPE": container_type,
                "CONTQTY": container_quantity,
                "COMMODITY": commodity,
                "TONNAGES": f"{tonnage:.2f}"
            })

    else:
        bl_chunks = re.split(r"(?:\n|^)(?=Item No\.)", pdf_text)

        for chunk in bl_chunks[1:]:
            pod_match = re.search(
                r"B/L Port of Discharge\s*\n?\s*([A-Z\s]+?)\s*B/L Place",
                chunk,
                re.IGNORECASE
            )
            pod_raw = pod_match.group(1).strip().upper() if pod_match else "XIAMEN"
            port_info = resolve_port_info(pod_raw, use_web_search)

            weight_match = re.search(r"(\d+\.\d{2})\s*KG", chunk)
            tonnage = round(parse_num(weight_match.group(1)) / 1000.0, 2) if weight_match else 0.0

            quantity_match = re.search(r"(\d+)\s*CONTAINER\(S\)", chunk)
            container_quantity = int(quantity_match.group(1)) if quantity_match else 1
            container_type = "40D"

            description_match = re.search(
                r"Number and Kinds of Package/Description of Goods\s*\n[\s\S]*?"
                r"\d+\s+BAGS\s*\n[\s\S]*?\n\s*([A-Z\s]+?)\n",
                chunk
            )
            description = description_match.group(1).strip() if description_match else "COCOA POWDER"
            commodity = classify_commodity(description, use_web_search=use_web_search)

            rows.append({
                "SHIP": ship,
                "SHIP LINE": "COSCO SHIPPING LINE",
                "AGENT": "COSCO GH. LTD",
                "PORT": port_info[0],
                "CTRY": port_info[1],
                "RANGE": port_info[2],
                "CONTYPE": container_type,
                "CONTQTY": container_quantity,
                "COMMODITY": commodity,
                "TONNAGES": f"{tonnage:.2f}"
            })

    return rows


def parse_maersk(pdf_text: str, ship_name: str, use_web_search: bool = True):
    rows = []
    ship = ship_name

    if "CMA CGM" in ship:
        carrier, agent = ("CMA CGM", "CMA CGM GH. LTD.")
    else:
        carrier, agent = ("MAERSK LINE", "MAERSK GH. LTD.")

    bl_chunks = re.split(
        r"(?:\n|^)\s*(?=[A-Z0-9]{7,12}(?:\s*\n\s*[0-9]{1,4})?\s*\n\s*(?:MAEU|WAYBILL))",
        pdf_text
    )

    for chunk in bl_chunks:
        if "MAEU" not in chunk and "WAYBILL" not in chunk:
            continue
        if is_empty_equipment(chunk):
            continue

        pod_match = re.search(
            r"(?:Final Disch|Vessel Disch|Del)\s*:\s*([^\n]+)",
            chunk,
            re.IGNORECASE
        )
        pod_raw = pod_match.group(1).strip().upper() if pod_match else "LOME"
        port_info = resolve_port_info(pod_raw, use_web_search)

        container_matches = re.findall(
            r"(\d+)\s*X\s*(\d{2}\s*(?:DRY|REEF|OPEN|HC|HR)[^\n]*)",
            chunk,
            re.IGNORECASE
        )

        container_type = "40D"
        container_quantity = 1

        if container_matches:
            container_quantity = int(container_matches[0][0])
            container_type = normalize_container(container_matches[0][1])

        cleaned = re.sub(
            r"Tare\s*:\s*[\d\.,\s]+(?:KGS|KG)",
            "",
            chunk,
            flags=re.IGNORECASE
        )

        explicit_totals = re.findall(
            r"(?:TOTAL\s+GROSS\s+WEIGHT|TOTAL\s+GR\.?\s*WT\.?|TOTAL\s+G\.?W\.?"
            r"|TOTAL\s+CARGO\s+GROSS\s+WEIGHT)\s*[:\.]?\s*"
            r"([\d\s\.,]+)\s*(?:KGS|KG|MT|MTS)",
            cleaned,
            re.IGNORECASE
        )

        if explicit_totals:
            value = parse_num(explicit_totals[0])
            tonnage = round(value / 1000.0 if value > 500 else value, 2)
        else:
            column_totals = re.findall(
                r"(?:^|\n)\s*([\d\.,]+)\s*KGS\s*\n\s*"
                r"(?:Basic Ocean|Container Protect|Inland Haulage|Additional Import|"
                r"Storage Export|Inspection Fee|Demurrage|Detention|Electronic Cargo|"
                r"Terminal Handling|Port Additionals|Import Service|Documentation fee|"
                r"Verified Gross Mass|Rollable Compensation|3rd Party)",
                cleaned,
                re.IGNORECASE
            )

            if column_totals:
                value = parse_num(column_totals[0])
                tonnage = round(value / 1000.0 if value > 500 else value, 2)
            else:
                item_weights = re.findall(
                    r"(?:BALES|BAGS|PACKAGES|CARTONS|UNITS|PIECES|COLIS|PKGS|PACKAGE|"
                    r"SACKS|CARTON|BALE|PLTS|PALLET|PALLETS|CTNS|BOXES|ROLLS)\s+"
                    r"([\d\s\.,]+)\s*KGS",
                    cleaned,
                    re.IGNORECASE
                )

                valid_numbers = [
                    parse_num(weight)
                    for weight in item_weights
                    if parse_num(weight) > 500
                ]

                if valid_numbers:
                    if container_quantity > 1 and len(valid_numbers) > 1:
                        tonnage = round(sum(valid_numbers) / 1000.0, 2)
                    else:
                        tonnage = round(max(valid_numbers) / 1000.0, 2)
                else:
                    tonnage = 0.0

        hs_match = re.search(r"HS\s*(?:Code|CODE)?\s*[:\.]?\s*(\d{4,10})", chunk)
        hs_code = hs_match.group(1) if hs_match else ""

        description_match = re.search(
            r"Description of goods\s*([\s\S]+?)"
            r"(?:Shipper Provided|Basic Ocean|Container Protect|\n[A-Z0-9]{7,12}|$)",
            chunk,
            re.IGNORECASE
        )
        description = description_match.group(1).strip() if description_match else ""

        commodity = classify_commodity(description, hs_code, use_web_search)

        rows.append({
            "SHIP": ship,
            "SHIP LINE": carrier,
            "AGENT": agent,
            "PORT": port_info[0],
            "CTRY": port_info[1],
            "RANGE": port_info[2],
            "CONTYPE": container_type,
            "CONTQTY": container_quantity,
            "COMMODITY": commodity,
            "TONNAGES": f"{tonnage:.2f}"
        })

    return rows


def parse_ael(pdf_text: str, ship_name: str, use_web_search: bool = True):
    rows = []
    ship = ship_name

    bl_chunks = re.split(r"(?:\n|^)(?=TEMPOV\w+|TEMDKR\w+)", pdf_text)

    for chunk in bl_chunks[1:]:
        if is_empty_equipment(chunk):
            continue

        search_text = chunk if "Port of Discharge:" in chunk else pdf_text
        pod_match = re.search(
            r"Port of Discharge:\s*([^\n]+)",
            search_text,
            re.IGNORECASE
        )
        pod_raw = pod_match.group(1).strip().upper() if pod_match else "PORT VENDRES"
        port_info = resolve_port_info(pod_raw, use_web_search)

        is_breakbulk = "PALLETS IN HOLD" in chunk.upper()
        container_type = ""
        container_quantity = ""

        if not is_breakbulk:
            container_match = re.search(
                r"(\d+)\s*X\s*40['\s]*hc reefer",
                chunk,
                re.IGNORECASE
            )
            container_quantity = int(container_match.group(1)) if container_match else 1
            container_type = "40R"

        weight_match = re.search(
            r"TOTAL GROSS WEIGHT\s*:\s*([\d\s\.,]+)\s*KG",
            chunk,
            re.IGNORECASE
        )
        tonnage = round(parse_num(weight_match.group(1)) / 1000.0, 2) if weight_match else 0.0

        if "YAM" in chunk.upper():
            commodity = "LYM"
        elif "BANANA" in chunk.upper():
            commodity = "LBN"
        else:
            commodity = "LPN"

        rows.append({
            "SHIP": ship,
            "SHIP LINE": "AFRICA EXPRESS LINE",
            "AGENT": "EOLIS GH. LTD",
            "PORT": port_info[0],
            "CTRY": port_info[1],
            "RANGE": port_info[2],
            "CONTYPE": container_type,
            "CONTQTY": container_quantity,
            "COMMODITY": commodity,
            "TONNAGES": f"{tonnage:.2f}"
        })

    return rows


# ==========================================
# 6. USER INTERFACE & DISPATCHER
# ==========================================

st.title("🚢 Ghana Ports Export Manifest Auto-Coder")
st.markdown("Universal Multi-Carrier Manifest Coding Engine.")

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    month_selected = st.selectbox(
        "Select Operating Month",
        [
            "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
            "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
        ],
        index=8
    )

with col2:
    rotation_option = st.selectbox(
        "Manual document rotation override",
        [
            "0° (Normal / Upright)",
            "90° Clockwise",
            "180° (Upside Down)",
            "270° Counter-Clockwise"
        ],
        index=0
    )

    rotation_degrees = {
        "0° (Normal / Upright)": 0,
        "90° Clockwise": 90,
        "180° (Upside Down)": 180,
        "270° Counter-Clockwise": 270
    }[rotation_option]

with col3:
    enable_web_search = st.checkbox(
        "🌐 Enable Web Search (Ports & Commodities)",
        value=True
    )
    show_debug_text = st.checkbox(
        "Show Raw Text Preview (Diagnostics)",
        value=False
    )
    auto_rotate_pages = st.checkbox(
        "🔄 Automatically detect sideways scanned pages",
        value=True
    )

uploaded_files = st.file_uploader(
    "Upload Manifest PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    start_button = st.button(
        "🚀 Process & Code Manifest",
        type="primary",
        use_container_width=True
    )

    if start_button:
        all_extracted_rows = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for file_index, uploaded_file in enumerate(uploaded_files):
            file_bytes = uploaded_file.read()

            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
            except Exception as error:
                st.error(f"Could not open {uploaded_file.name}: {error}")
                continue

            total_pages = len(doc)
            pages_text = []

            for page_index in range(total_pages):
                status_text.text(
                    f"Reading page {page_index + 1} of {total_pages} "
                    f"({uploaded_file.name})..."
                )

                page = doc[page_index]

                try:
                    page_text = extract_page_text(
                        page,
                        manual_rotation=rotation_degrees,
                        auto_rotate=auto_rotate_pages
                    )
                except Exception as error:
                    st.warning(
                        f"Could not read page {page_index + 1} "
                        f"of {uploaded_file.name}: {error}"
                    )
                    page_text = ""

                pages_text.append(page_text)

            full_text = "\n".join(pages_text)

            if show_debug_text:
                with st.expander(f"🔍 Raw Text Preview ({uploaded_file.name})"):
                    st.text(
                        full_text[:5000]
                        if full_text
                        else "[NO TEXT EXTRACTED]"
                    )

            detected_ship = extract_vessel_name(full_text)
            status_text.text(
                f"Detected Vessel: '{detected_ship}' — Processing cargo rows..."
            )

            if (
                "OCEAN NETWORK EXPRESS" in full_text
                or "ONEY" in full_text
                or re.search(r"\bONE\b", full_text)
            ):
                parsed = parse_one(full_text, detected_ship, enable_web_search)
            elif (
                "PIL" in full_text
                or "PACIFIC INTERNATIONAL" in full_text
                or "KOTA" in full_text
            ):
                parsed = parse_pil(full_text, detected_ship, enable_web_search)
            elif (
                "GOSUTEM" in full_text
                or "GOLD STAR" in full_text
                or "CONDOR 630" in full_text
            ):
                parsed = parse_goldstar(full_text, detected_ship, enable_web_search)
            elif (
                "ARKU" in full_text
                or "APM Terminals Barcelona" in full_text
                or "MICHEL A" in full_text
            ):
                parsed = parse_arkas(full_text, detected_ship, enable_web_search)
            elif (
                "COSCO SHIPPING" in full_text
                or "COSU" in full_text
                or "EXPORT REPORT MANIFEST" in full_text
            ):
                parsed = parse_cosco(full_text, detected_ship, enable_web_search)
            elif (
                "EOLIS" in full_text
                or "AFRICA EXPRESS" in full_text
                or "TEMPOV" in full_text
            ):
                parsed = parse_ael(full_text, detected_ship, enable_web_search)
            else:
                parsed = parse_maersk(full_text, detected_ship, enable_web_search)

            for row in parsed:
                row["MONTH"] = month_selected
                all_extracted_rows.append(row)

            progress_bar.progress((file_index + 1) / len(uploaded_files))
            doc.close()

        status_text.empty()
        progress_bar.empty()

        if all_extracted_rows:
            dataframe = pd.DataFrame(all_extracted_rows)

            column_order = [
                "MONTH", "SHIP", "SHIP LINE", "AGENT", "PORT",
                "CTRY", "RANGE", "CONTYPE", "CONTQTY",
                "COMMODITY", "TONNAGES"
            ]
            dataframe = dataframe[column_order]

            st.success(
                f"Successfully processed {len(dataframe)} manifest rows."
            )
            st.subheader("Interactive Review Screen (Edit if needed)")

            edited_dataframe = st.data_editor(
                dataframe,
                use_container_width=True,
                num_rows="dynamic"
            )

            buffer = io.BytesIO()

            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                edited_dataframe.to_excel(
                    writer,
                    index=False,
                    sheet_name="CODED MANIFEST"
                )

                worksheet = writer.sheets["CODED MANIFEST"]
                tonnages_column_index = column_order.index("TONNAGES") + 1

                for row_index in range(2, len(edited_dataframe) + 2):
                    cell = worksheet.cell(
                        row=row_index,
                        column=tonnages_column_index
                    )
                    try:
                        cell.value = float(cell.value)
                        cell.number_format = "0.00"
                    except (TypeError, ValueError):
                        pass

            st.download_button(
                label="📥 Download Coded Excel Sheet (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"{month_selected} 2026 CODING.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.error(
                "No valid cargo rows were found. Check the raw text preview, "
                "try the manual rotation override, and confirm that Tesseract "
                "OCR is installed."
