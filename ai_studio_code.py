import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import re
import io
import requests
from datetime import datetime

st.set_page_config(page_title="Ghana Export Manifest Auto-Coder", layout="wide")

# ==========================================
# 0. SECURITY GATE
# ==========================================

def check_password():
    if st.session_state.get("password_correct"):
        return True

    st.subheader("🔒 Manifest Coding System - Restricted Access")
    with st.form("login_form"):
        pwd = st.text_input("Enter Office Access Password:", type="password")
        submitted = st.form_submit_button("Enter", type="primary")

    if submitted:
        if pwd == "GsaMeta@123":
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("❌ Incorrect password. Access denied.")
    return False

if not check_password():
    st.stop()

# ==========================================
# 1. MASTER KNOWLEDGE BASE & GEOGRAPHY MAP
# ==========================================

COUNTRY_MAP = {
    "NIGERIA": ("NG", "AF"), "TOGO": ("TG", "AF"), "BENIN": ("BN", "AF"),
    "GHANA": ("GH", "AF"), "COTE D'IVOIRE": ("IV", "AF"), "IVORY COAST": ("IV", "AF"),
    "BURKINA FASO": ("BF", "AF"), "NIGER": ("NR", "AF"), "MALI": ("ML", "AF"),
    "SENEGAL": ("SN", "AF"), "SOUTH AFRICA": ("SA", "AF"), "CAMEROON": ("CM", "AF"),
    "CONGO": ("CG", "AF"), "GABON": ("GA", "AF"), "GUINEA": ("GN", "AF"),
    "SIERRA LEONE": ("SL", "AF"), "LIBERIA": ("LB", "AF"), "MAURITANIA": ("MR", "AF"),
    "EGYPT": ("EY", "AF"), "MOROCCO": ("MC", "AF"), "ALGERIA": ("AG", "AF"),
    "TUNISIA": ("TS", "AF"), "LIBYA": ("LY", "AF"), "TANZANIA": ("TZ", "AF"),
    "KENYA": ("KY", "AF"), "ANGOLA": ("OH", "AF"), "MOZAMBIQUE": ("MZ", "AF"),
    "NAMIBIA": ("OH", "AF"), "MADAGASCAR": ("OH", "AF"), "GAMBIA": ("GM", "AF"),

    "UNITED KINGDOM": ("UK", "UK"), "UK": ("UK", "UK"), "ENGLAND": ("UK", "UK"),
    "SCOTLAND": ("UK", "UK"), "IRELAND": ("IR", "UK"),

    "NETHERLANDS": ("NL", "CT"), "HOLLAND": ("NL", "CT"), "BELGIUM": ("BG", "CT"),
    "GERMANY": ("GR", "CT"), "FRANCE": ("FR", "CT"), "POLAND": ("PL", "CT"),
    "DENMARK": ("DK", "CT"), "SWEDEN": ("SE", "CT"), "NORWAY": ("NW", "CT"),
    "FINLAND": ("FL", "CT"), "ESTONIA": ("ET", "CT"), "LATVIA": ("LV", "CT"),
    "LITHUANIA": ("LT", "CT"), "UKRAINE": ("UE", "CT"), "RUSSIA": ("RU", "CT"),

    "SPAIN": ("SP", "ME"), "ITALY": ("IT", "ME"), "GREECE": ("GC", "ME"),
    "PORTUGAL": ("PG", "ME"), "TURKEY": ("TU", "ME"), "TURKIYE": ("TU", "ME"),
    "CYPRUS": ("CY", "ME"), "ROMANIA": ("RM", "ME"), "BULGARIA": ("BU", "ME"),
    "CANARY ISLANDS": ("CI", "ME"),

    "INDIA": ("IN", "FE"), "CHINA": ("CH", "FE"), "JAPAN": ("JP", "FE"),
    "SOUTH KOREA": ("SK", "FE"), "KOREA": ("SK", "FE"), "VIETNAM": ("VT", "FE"),
    "MALAYSIA": ("MY", "FE"), "INDONESIA": ("ID", "FE"), "THAILAND": ("TH", "FE"),
    "SINGAPORE": ("SG", "FE"), "TAIWAN": ("TW", "FE"), "HONG KONG": ("HK", "FE"),
    "HONGKONG": ("HK", "FE"), "PAKISTAN": ("PK", "FE"), "BANGLADESH": ("BD", "FE"),
    "SRI LANKA": ("SR", "FE"), "PHILIPPINES": ("PH", "FE"),

    "UNITED STATES": ("US", "NA"), "USA": ("US", "NA"), "CANADA": ("CN", "NA"),

    "BRAZIL": ("BZ", "OH"), "ARGENTINA": ("AR", "OH"), "AUSTRALIA": ("AU", "OH"),
    "NEW ZEALAND": ("NZ", "OH"), "UNITED ARAB EMIRATES": ("AE", "OH"), "UAE": ("AE", "OH"),
    "DUBAI": ("AE", "OH"), "SAUDI ARABIA": ("SB", "OH"), "JORDAN": ("JD", "OH"),
    "ISRAEL": ("IL", "OH")
}

PORT_MAP = {
    "LOME": ("LM", "TG", "AF"), "COTONOU": ("CU", "BN", "AF"), "ABIDJAN": ("AJ", "IV", "AF"),
    "LAGOS": ("LG", "NG", "AF"), "TINCAN": ("LG", "NG", "AF"), "APAPA": ("OH", "NG", "AF"),
    "LEKKI": ("OH", "NG", "AF"), "ONNE": ("OH", "NG", "AF"), "PORT HARCOURT": ("OH", "NG", "AF"),
    "DAKAR": ("DA", "SN", "AF"), "POINTE NOIRE": ("OH", "CG", "AF"), "POINT NOIRE": ("OH", "CG", "AF"),
    "MATADI": ("MA", "CG", "AF"), "LIBREVILLE": ("LB", "GA", "AF"), "PORT GENTIL": ("PG", "GA", "AF"),
    "DOUALA": ("DL", "CM", "AF"), "DURBAN": ("DR", "SA", "AF"), "CAPETOWN": ("CN", "SA", "AF"),
    "CAPE TOWN": ("CN", "SA", "AF"), "PORT ELIZABETH": ("PE", "SA", "AF"), "TEMA": ("TM", "GH", "AF"),
    "TAKORADI": ("TD", "GH", "AF"), "DAR ES SALAAM": ("ES", "TZ", "AF"), "CONAKRY": ("CN", "GN", "AF"),
    "ANTWERP": ("AT", "BG", "CT"), "AMSTERDAM": ("AM", "NL", "CT"), "ROTTERDAM": ("RM", "NL", "CT"),
    "HAMBURG": ("HM", "GR", "CT"), "BREMERHAVEN": ("BM", "GR", "CT"), "LE HAVRE": ("LH", "FR", "CT"),
    "DUNKERQUE": ("DK", "FR", "CT"), "DUNKIRK": ("DK", "FR", "CT"), "PORT VENDRES": ("BD", "FR", "CT"),
    "FOS SUR MER": ("OH", "FR", "CT"), "MARSEILLE": ("MS", "FR", "CT"), "ROUEN": ("RN", "FR", "CT"),
    "GDYNIA": ("GA", "PL", "CT"), "GDANSK": ("GK", "PL", "CT"), "ZEEBRUGGE": ("ZB", "BG", "CT"),
    "TILBURY": ("TY", "UK", "UK"), "LIVERPOOL": ("LV", "UK", "UK"), "LONDON": ("LD", "UK", "UK"),
    "FELIXSTOWE": ("FX", "UK", "UK"), "DUBLIN": ("DU", "IR", "UK"), "BELFAST": ("BT", "IR", "UK"),
    "CORK": ("OH", "IR", "UK"),
    "BARCELONA": ("BC", "SP", "ME"), "VALENCIA": ("VL", "SP", "ME"), "ALGECIRAS": ("AR", "SP", "ME"),
    "GENOA": ("GE", "IT", "ME"), "LIVORNO": ("LO", "IT", "ME"), "NAPLES": ("NS", "IT", "ME"),
    "ISTANBUL": ("IL", "TU", "ME"), "IZMIT": ("OH", "TU", "ME"), "AMBARLI": ("OH", "TU", "ME"),
    "MARPORT": ("OH", "TU", "ME"), "PIRAEUS": ("PI", "GC", "ME"), "ALEXANDRIA": ("OH", "EY", "AF"),
    "SHANGHAI": ("SH", "CH", "FE"), "NINGBO": ("OH", "CH", "FE"), "QINGDAO": ("OH", "CH", "FE"),
    "XIAMEN": ("OH", "CH", "FE"), "NANSHA": ("OH", "CH", "FE"), "SHEKOU": ("OH", "CH", "FE"),
    "HONGKONG": ("HK", "HK", "FE"), "HONG KONG": ("HK", "HK", "FE"),
    "BUSAN": ("BU", "SK", "FE"), "INCHEON": ("OH", "SK", "FE"),
    "SINGAPORE": ("SG", "SG", "FE"), "PORT KLANG": ("OH", "MY", "FE"), "PENANG": ("PM", "MY", "FE"),
    "HO CHI MINH": ("OH", "VT", "FE"), "MUMBAI": ("BY", "IN", "FE"), "NHAVA SHEVA": ("OH", "IN", "FE"),
    "MUNDRA": ("OH", "IN", "FE"), "CHENNAI": ("MD", "IN", "FE"), "TUTICORIN": ("OH", "IN", "FE"),
    "VISAKHAPATNAM": ("OH", "IN", "FE"), "YOKOHAMA": ("YK", "JP", "FE"), "TOKYO": ("TK", "JP", "FE"),
    "NEW YORK": ("NY", "US", "NA"), "SAVANNAH": ("SV", "US", "NA"), "HOUSTON": ("HO", "US", "NA"),
    "COLOMBO": ("OH", "SR", "FE")
}

SORTED_PORTS = sorted(PORT_MAP.items(), key=lambda x: len(x[0]), reverse=True)
SORTED_COUNTRIES = sorted(COUNTRY_MAP.items(), key=lambda x: len(x[0]), reverse=True)

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================

@st.cache_data(ttl=3600, show_spinner=False)
def fast_web_lookup(term: str) -> str:
    clean_term = term.strip().upper()
    if not clean_term:
        return ""
    try:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": clean_term,
            "utf8": "",
            "format": "json"
        }
        headers = {"User-Agent": "GhanaManifestBot/1.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=1.5)
        if resp.status_code == 200:
            data = resp.json()
            snippets = [item.get("snippet", "") for item in data.get("query", {}).get("search", [])[:2]]
            return re.sub(r"<[^>]+>", " ", " ".join(snippets)).upper()
    except Exception:
        pass
    return ""

def resolve_port_info(pod_raw: str, full_chunk: str = "", use_web_search: bool = True) -> tuple:
    clean_pod = pod_raw.upper().strip()
    clean_pod = re.sub(
        r"\b(?:CN|IN|NG|SG|GH|ZA|LK|FR|SP|ES|IT|DE|NL|BE|GB|UK|US|CA|MY|VN|TH|JP|KR|BR|AE|SA|TG|BJ|CI|SN|CM|CG|GA|TZ|KE|EG|MA|TR|PT|GR|PL|IE|AU|NZ|PH|ID|PK|BD|TW|HK|MX|AR)\s*-\s*",
        "",
        clean_pod
    )
    clean_pod = re.sub(r"\bGH\b", "", clean_pod).strip()

    for k, v in SORTED_PORTS:
        if re.search(rf"\b{re.escape(k)}\b", clean_pod):
            return v

    for c_name, (c_code, r_code) in SORTED_COUNTRIES:
        if re.search(rf"\b{re.escape(c_name)}\b", clean_pod):
            return ("OH", c_code, r_code)

    if re.search(r",\s*IR\b", clean_pod):
        return ("OH", "IR", "UK")

    if full_chunk:
        upper_chunk = full_chunk.upper()
        for c_name, (c_code, r_code) in SORTED_COUNTRIES:
            if re.search(rf"(?:,|\n)\s*{re.escape(c_name)}\b", upper_chunk):
                return ("OH", c_code, r_code)

    if use_web_search and len(clean_pod) > 2:
        res = fast_web_lookup(f"{clean_pod} seaport port city country")
        if res:
            for c_name, (c_code, r_code) in SORTED_COUNTRIES:
                if re.search(rf"\b{re.escape(c_name)}\b", res):
                    return ("OH", c_code, r_code)
            if "AFRICA" in res:
                return ("OH", "OH", "AF")
            if "EUROPE" in res:
                return ("OH", "OH", "CT")
            if "ASIA" in res:
                return ("OH", "OH", "FE")

    return ("OH", "OH", "AF")

def classify_commodity(desc: str, hs_code: str = "", use_web_search: bool = False) -> str:
    hs_clean = re.sub(r"[^0-9]", "", str(hs_code))
    t = f"{desc} {hs_clean}".upper()

    def has_word(text_to_check, words):
        return any(re.search(rf"\b{re.escape(w)}\b", text_to_check) for w in words)

    def match_rules(text_to_check, allow_vehicle_match: bool = True):
        # 1. Cocoa & Cocoa Products
        if any(k in
