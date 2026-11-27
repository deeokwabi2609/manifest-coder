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
    "RUSSIAN": ("RU", "CT"),

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
    "FREETOWN": ("OH", "SL", "AF"),
    "ANTWERP": ("AT", "BG", "CT"), "AMSTERDAM": ("AM", "NL", "CT"), "ROTTERDAM": ("RM", "NL", "CT"),
    "HAMBURG": ("HM", "GR", "CT"), "BREMERHAVEN": ("BM", "GR", "CT"), "LE HAVRE": ("LH", "FR", "CT"),
    "DUNKERQUE": ("DK", "FR", "CT"), "DUNKIRK": ("DK", "FR", "CT"), "PORT VENDRES": ("BD", "FR", "CT"),
    "FOS SUR MER": ("OH", "FR", "CT"), "MARSEILLE": ("MS", "FR", "CT"), "ROUEN": ("RN", "FR", "CT"),
    "GDYNIA": ("GA", "PL", "CT"), "GDANSK": ("GK", "PL", "CT"), "ZEEBRUGGE": ("ZB", "BG", "CT"),
    "TALLINN": ("OH", "ET", "CT"), "SAINT PETERSBURG": ("OH", "RU", "CT"),
    "TILBURY": ("TY", "UK", "UK"), "LIVERPOOL": ("LV", "UK", "UK"), "LONDON": ("LD", "UK", "UK"),
    "FELIXSTOWE": ("FX", "UK", "UK"), "DUBLIN": ("DU", "IR", "UK"), "BELFAST": ("BT", "IR", "UK"),
    "CORK": ("OH", "IR", "UK"),
    "BARCELONA": ("BC", "SP", "ME"), "VALENCIA": ("VL", "SP", "ME"), "ALGECIRAS": ("AR", "SP", "ME"),
    "GENOA": ("GE", "IT", "ME"), "LIVORNO": ("LO", "IT", "ME"), "NAPLES": ("NS", "IT", "ME"),
    "ISTANBUL": ("IL", "TU", "ME"), "IZMIT": ("OH", "TU", "ME"), "AMBARLI": ("OH", "TU", "ME"),
    "MARPORT": ("OH", "TU", "ME"), "GEBZE": ("OH", "TU", "ME"), "PIRAEUS": ("PI", "GC", "ME"),
    "ALEXANDRIA": ("OH", "EY", "AF"),
    "SHANGHAI": ("SH", "CH", "FE"), "NINGBO": ("OH", "CH", "FE"), "QINGDAO": ("OH", "CH", "FE"),
    "XIAMEN": ("OH", "CH", "FE"), "NANSHA": ("OH", "CH", "FE"), "SHEKOU": ("OH", "CH", "FE"),
    "HONGKONG": ("HK", "HK", "FE"), "HONG KONG": ("HK", "HK", "FE"),
    "BUSAN": ("BU", "SK", "FE"), "INCHEON": ("OH", "SK", "FE"),
    "SINGAPORE": ("SG", "SG", "FE"), "PORT KLANG": ("OH", "MY", "FE"), "PENANG": ("PM", "MY", "FE"),
    "HO CHI MINH": ("OH", "VT", "FE"), "MUMBAI": ("BY", "IN", "FE"), "NHAVA SHEVA": ("OH", "IN", "FE"),
    "MUNDRA": ("OH", "IN", "FE"), "CHENNAI": ("MD", "IN", "FE"), "TUTICORIN": ("OH", "IN", "FE"),
    "VISAKHAPATNAM": ("OH", "IN", "FE"), "YOKOHAMA": ("YK", "JP", "FE"), "TOKYO": ("TK", "JP", "FE"),
    "NEW YORK": ("NY", "US", "NA"), "SAVANNAH": ("SV", "US", "NA"), "HOUSTON": ("HO", "US", "NA"),
    "MONTREAL": ("OH", "CN", "NA"),
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
        # 1. Dairy / Beverage blends before Cocoa/Chocolate
        if hs_clean.startswith("0402"):
            return "LPE"

        # 2. Cocoa & Cocoa Products
        if any(k in text_to_check for k in ["COCOA BEAN", "RAW COCOA", "BEANS OF COCOA"]) or hs_clean.startswith("1801"):
            return "LCB"
        if any(k in text_to_check for k in ["COCOA BUTTER", "COCOA CAKE", "COCOA POWDER", "COCOA LIQUOR", "COCOA MASS", "COCOA PASTE", "CHOCOLATE", "COCOA NIB", "COCOA PRESS CAKE"]) or hs_clean.startswith(("1803", "1804", "1805", "1806")):
            return "LCP"

        # 3. Fresh Produce & Agricultural Commodities
        if ("BANANA" in text_to_check and "CONDOM" not in text_to_check) or hs_clean.startswith("0803"):
            return "LBN"
        if any(k in text_to_check for k in ["PINEAPPLE JUICE", "CANNED PINEAPPLE", "MANGO JUICE", "JUICE DRINK"]) or hs_clean.startswith(("2008", "2009")):
            return "LPE"
        if "PINEAPPLE" in text_to_check or hs_clean.startswith("080430"):
            return "LPN"
        if has_word(text_to_check, ["YAM", "YAMS"]) or hs_clean.startswith("0714"):
            return "LYM"
        if any(k in text_to_check for k in ["CASHEW", "ANACARDE"]) or hs_clean.startswith(("080131", "080132")):
            return "LCA"
        if any(k in text_to_check for k in ["SHEA NUT", "SHEANUT", "SHEA BUTTER", "SHEABUTTER", "SHEA STEARIN", "KARITE"]) or hs_clean.startswith("1515"):
            return "LSH"

        # Ethnic / mixed foodstuff containers before single-ingredient LNO/LFI/LCH/LRB triggers
        if any(k in text_to_check for k in ["ASSORTED FOOD", "FOOD ITEMS", "FOODSTUFF", "GARI", "CASSAVA DOUGH", "CASSAVA FLOUR", "CORN DOUGH", "PALM SOUP", "PALM BASE", "PALM OIL", "TOMBROWN", "TOM BROWN", "HAUSA KOKO", "TUOZAAFI", "INDOMIE", "NOODLES", "ALOMO BITTERS", "CLUB BEER", "PLANTAIN FUFU", "CERELAC"]):
            return "LPE"

        if any(k in text_to_check for k in ["TOBACCO", "GINGER", "CHILLI", "TURMERIC", "SESAME", "SEEDS", "COCONUT", "COIR", "COCOPEAT", "PEPPER", "CASHEW SHELL", "COCOA SHELL", "CHARCOAL", "TAMARIND"]) or hs_clean.startswith(("0813", "0904", "0910", "1207", "2401", "5305")):
            return "LNO"

        # 4. Fish & Meat (check Canned/Pouched Fish LFS before Frozen Fish/Meat LFI)
        if any(k in text_to_check for k in ["CANNED TUNA", "POUCHED TUNA", "CANNED FISH", "CANNED MACKEREL", "CANNED SARDINE"]) or hs_clean.startswith("1604"):
            return "LFS"
        if any(k in text_to_check for k in ["TUNA", "FROZEN FISH", "BLACK SEA BREAM", "SKIPJACK", "YELLOWFIN", "MACKEREL", "SARDINE", "MEAT", "POULTRY", "CHICKEN", "BUFFALO", "PRAWNS", "SEAFOOD"]) or hs_clean.startswith(("0201", "0202", "0207", "0303", "0306")):
            return "LFI"

        # 5. Timber, Lumber & Furniture
        if any(k in text_to_check for k in ["ROUND LOG", "TEAK POLE", "LOGS", "ROUGH SQUARE LOGS", "ROUGH SQUARES", "TEAK ROUGH"]) or (hs_clean.startswith("4403") and "SAWN" not in text_to_check):
            return "LLG"
        if any(k in text_to_check for k in ["LUMBER", "SAWN TIMBER", "TEAK SAWN", "TEAK IN CONTAINER", "TEAK WOOD", "TEAK TIMBER", "PLYWOOD", "CHIP BOARD", "CHIPBOARD", "MELAMINE BOARD", "FIBREBOARD", "FIBERBOARD"]) or hs_clean.startswith(("4407", "4411", "4412")):
            return "LST"
        if any(k in text_to_check for k in ["FURNITURE", "DOOR", "MOULDING", "WOODEN CHAIR", "SOFA", "WARDROBE"]) or hs_clean.startswith(("9401", "9403")):
            return "LFW"

        # 6. Metals, Scrap, Rubber & Aluminium
        if any(k in text_to_check for k in ["SCRAP", "COPPER SCRAP", "ALUMINIUM SCRAP", "STEEL SCRAP", "IRON SCRAP"]) or hs_clean.startswith(("7204", "7404", "7602")):
            return "LMS"
        if any(k in text_to_check for k in ["NATURAL RUBBER", "RAW RUBBER", "CRUMB RUBBER", "TIRE", "TYRE", "TYRES", "TIRES", "TUBES", "CONDOM"]) or (has_word(text_to_check, ["RUBBER"]) and "PLASTIC RUBBER" not in text_to_check) or hs_clean.startswith(("4011", "4014")):
            return "LRB"
        if any(k in text_to_check for k in ["ALUMINIUM INGOT", "ALUMINUM INGOT", "ALUMINIUM WIRE ROD", "ALUMINUM WIRE"]):
            return "LAL"

        # 7. Vehicles/Cars (LVE), Trucks (LTR) & Machinery/Equipment (LME)
        if allow_vehicle_match:
            if hs_clean.startswith("8704") or any(k in text_to_check for k in ["FORKLIFT", "TRACTOR", "REFRIGERATED TRUCK", "PICKUP TRUCK"]) or (has_word(text_to_check, ["TRUCK", "TRUCKS"]) and "TIRE" not in text_to_check and "TYRE" not in text_to_check):
                return "LTR"

            is_part_or_non_car = any(k in text_to_check for k in ["CAR BATTERY", "CAR FITTING", "SPARE PART", "ACCESSOR", "MOTORCYCLE", "TRICYCLE", "ENGINE", "FILTER", "BRAKE", "BICYCLE", "BABY WALKER"])
            has_vehicle_word = any(k in text_to_check for k in ["VEHICLE", "USED AUTO", "USED CAR", "USED CARS", "SECOND-HAND CAR", "SECOND-HAND CARS", "TOYOTA", "HYUNDAI", "MERCEDES", "MAZDA", "HONDA", "NISSAN", "LEXUS", "CHANGAN", "JETOUR", "AUTOS", "AUTORICKSHAW", "BAJAJ"]) or has_word(text_to_check, ["CARS"]) or hs_clean.startswith("8703")
            if has_vehicle_word and not is_part_or_non_car:
                return "LVE"

        if any(k in text_to_check for k in ["MACHINE", "ENGINE", "PUMP", "EQUIPMENT", "SPARE PARTS", "AUTO PARTS", "MOTORCYCLE", "TRICYCLE", "CAR BATTERY", "CAR FITTING", "WHEEL LOADER", "CRUSHER", "SOLAR PANEL", "SOLAR SYSTEM", "SOLAR MODULE", "BATTERY", "REFRIGERATOR", "FRIDGE", "CHEST FREEZER", "AIR CONDITION", "CEILING FAN", "STAND FAN", "WALL FAN", "FANS", "SPEAKER", "HOME APPLIANCE", "ELECTRONIC GOODS", "ALTERNATOR", "MOULDS", "LATHE", "INCENSE", "MATCHET", "AGRICULTURAL IMPLEMENT", "REFRIGERATING", "SHOVEL", "SPRAYER", "WRENCH", "HAND TOOLS"]) or hs_clean.startswith(("84", "85", "8201", "8204", "8205", "8708", "8711", "8714", "9018")):
            return "LME"

        # 8. Chemicals, Resins, Detergents & Lubricants
        if any(k in text_to_check for k in ["CHEMICAL", "ZINC OXIDE", "CALCIUM", "RESIN", "POLYETHYLENE", "HDPE", "LLDPE", "EVA MATERIAL", "POLYETHER POLYOL", "PET FLAKES", "GYPSUM", "CHLORIDE", "ETHYL ACETATE", "HEXANE", "SOLVENT", "ACETATE", "MANGANESE", "ENZYMES", "BOSTIK", "DETERGENT", "WASHING POWDER", "COCAMIDOPROPYL", "LUBRICANT", "LUBRICATING", "PIGMENT", "DYESTUFF", "ULTRAMARINE", "PHOSPHIDE", "BENZOATE", "TIRE SEALER", "KAOLINITE", "POWERFLOW"]) or has_word(text_to_check, ["SALT"]) or hs_clean.startswith(("2501", "2507", "2520", "2710", "28", "29", "3206", "3402", "3506", "3507", "38", "3901", "3907", "7202")):
            return "LCH"

        # 9. Foodstuffs, Beverages, Textiles, Footwear, Pharma & Personal Effects
        if any(k in text_to_check for k in ["SPAGHETTI", "MACARONI", "FOOD ITEM", "BISCUITS", "CONFECTIONERY", "SNACK PELLET", "SUGAR", "SOYABEAN OIL", "SOY SAUCE", "GHERKINS", "TOMATO PASTE", "BEVERAGE", "VODKA", "WHISKY", "COFFEE", "BLACK TEA", "GREEN TEA", "CEYLON BLACK TEA", "SOAP", "SODIUM PALMITATE", "DEODORANT", "COSMETIC", "TOOTHPASTE", "CREAM", "BEAUTY", "TEXTILE", "CLOTHING", "USED CLOTH", "SECOND HAND CLOTH", "CLOTHES", "GARMENTS", "SHIRT", "TSHIRT", "JEANS", "DRESS", "CAPS", "BED SHEET", "BEDSHEET", "CURTAIN", "SHOES", "SLIPPERS", "FOOTWEAR", "SUITCASE", "TROLLEY CASE", "BABY DIAPER", "ADULT DIAPER", "SANITARY NAPKIN", "SYNTHETIC FIBER", "SYNTHETIC MONO FILAMENT", "HUMAN HAIR", "SYNTHETIC HAIR", "PARBOILED RICE", "RICE PAPER", "MEDICINE", "PHARMACEUTICAL", "MEDICAL SUPPL", "MEDICAL PRODUCT", "GAUZE SWAB", "LATEX GLOVES", "TAILORING", "POPPADOM", "FILTERATION", "YARN", "FABRIC", "NONWOVENS", "PAPERBOARD", "PAPER CUP", "PHOTOCOPY PAPER", "TISSUE", "PRINTED BOOKS", "EDUCATIONAL BOOKS", "STATIONERY", "STATIONARY", "SPORTS MATERIAL", "CATERING", "HOUSEHOLDING GOODS", "HOUSEGOODS", "COWBELL", "YUMVITA", "ONGA"]) or has_word(text_to_check, ["OIL", "HAIR", "RICE", "TEA", "BAGS", "BAG", "SACS", "BEER", "WINE"]) or hs_clean.startswith(("0902", "1702", "1704", "1901", "1904", "1905", "2001", "2002", "2101", "2103", "2208", "3004", "3005", "3304", "3307", "3401", "4015", "4202", "4802", "4818", "4820", "4823", "4901", "52", "54", "55", "56", "58", "61", "62", "63", "64", "6505", "9619")):
            return "LPE"

        # 10. Building Materials / General Cargo
        if any(k in text_to_check for k in ["GRANITE", "TILES", "SANITARY WARE", "GLASS", "MANHOLE COVER", "LEAD INGOTS"]) or hs_clean.startswith(("6802", "6904", "6907", "6910", "6914", "7005", "7007", "7801")):
            return "LGC"

        return None

    result = match_rules(t, allow_vehicle_match=True)
    if result:
        return result

    if use_web_search and len(desc.strip()) > 3:
        noise_words = {"PACKAGES", "PACKAGE", "CARTONS", "CARTON", "BALES", "BALE", "PKGS", "CTNS", "PIECES", "SETS", "BOXES", "DRUMS", "ROLLS", "PALLETS", "BAGS", "SACKS", "CRATES", "UNITS", "UNIT", "GENERAL", "GOODS", "DIVERS", "VARIOUS", "ITEMS", "STUFF", "SAID", "CONTAIN", "TOTAL", "GROSS", "WEIGHT", "TRANSIT", "DAKAR", "MALI", "BAMAKO", "GAMBIA", "BANJUL", "CONAKRY", "GUINEA", "SENEGAL", "BISSAU", "CHINA", "INDIA", "PREPAID", "COLLECT", "INVOICE", "DATE", "SHIPPING", "BILL", "CODE", "NUMBER", "MARCHANDISES", "DIVERSES", "CARGO", "CONTAINER"}
        cleaned_words = [w for w in re.sub(r"[^A-Za-z]", " ", desc.upper()).split() if len(w) > 3 and w not in noise_words][:3]
        if cleaned_words:
            web_info = fast_web_lookup(" ".join(cleaned_words) + " product")
            if web_info:
                res = match_rules(web_info, allow_vehicle_match=False)
                if res:
                    return res

    return "LGC"

def normalize_container(sz_text: str) -> str:
    sz = str(sz_text).upper()
    is_reefer = any(k in sz for k in ["REEF", "RH", "RA", "RC", "RF", "HR", "R2", "R5", "20R", "40R", "45R"])
    if is_reefer:
        if "20" in sz or "R2" in sz:
            return "20R"
        return "40R"
    if any(k in sz for k in ["40", "45", "42G", "D5"]):
        return "40D"
    if any(k in sz for k in ["20", "22G", "D2"]):
        return "20D"
    return "40D"

def is_empty_equipment(text: str) -> bool:
    t = text.upper()
    empty_equipment_patterns = [
        r"\bEMPTY\s+(?:CONTAINERS?|ISO\s*TANKS?|TANKS?|CNTRS?|REEFERS?|UNITS?|EQUIPMENT)\b",
        r"\b(?:CONTAINERS?|CNTRS?|TANKS?)\s+(?:STC\s+)?EMPTY\b",
        r"\bMT\s+CONTAINERS?\b",
        r"\bEMPTY\s+WITH\s+RESIDUE\b",
        r"\bRESIDUE\s*\(SOC\)\b",
        r"\bEMPTY\s+SOC\b"
    ]
    return any(re.search(pat, t) for pat in empty_equipment_patterns)

def parse_num(val_str: str) -> float:
    try:
        clean = re.sub(r"\s+", "", str(val_str))
        if not clean:
            return 0.0
        if "," in clean and "." in clean:
            if clean.rfind(",") > clean.rfind("."):
                clean = clean.replace(".", "").replace(",", ".")
            else:
                clean = clean.replace(",", "")
        elif "," in clean:
            if re.search(r",\d{1,2}$", clean):
                clean = clean.replace(",", ".")
            else:
                clean = clean.replace(",", "")
        return float(clean)
    except Exception:
        return 0.0

def to_tonnes(val: float, unit_str: str = "") -> float:
    u = unit_str.upper().strip()
    if u.startswith("KG"):
        return round(val / 1000.0, 2)
    if u.startswith("MT"):
        return round(val, 2)
    return round(val if (0.0 < val < 500.0) else val / 1000.0, 2)

# ==========================================
# 3. SPECIALIZED CARRIER PARSERS
# ==========================================

def parse_one(pdf_text: str, use_web_search: bool = True):
    """Universal parser for all ONE (Ocean Network Express) manifest variants."""
    rows = []

    ship_m = re.search(r"(?:1\.Name of ship|Vessel Name|Vessel)[^\n]*\n[ \t]*([A-Z0-9 ]+?)(?:CSYD|\b\d{4}[A-Z]?\b|IMO|\n)", pdf_text, re.IGNORECASE)
    ship = ship_m.group(1).strip().upper() if ship_m else "UNKNOWN VESSEL"

    bl_numbers = list(dict.fromkeys(re.findall(r"\b(ONEY[A-Z0-9]{8,15})\b", pdf_text)))
    if not bl_numbers:
        bl_numbers = list(dict.fromkeys(re.findall(r"\b([A-Z]{4}\d{8,12})\b", pdf_text)))

    for i, bl_no in enumerate(bl_numbers):
        next_bl_lookahead = rf"\n\s*{re.escape(bl_numbers[i + 1])}\b|" if i + 1 < len(bl_numbers) else ""
        pattern = rf"(?:^|\n)\s*{re.escape(bl_no)}\b[\s\S]*?(?=(?:{next_bl_lookahead}\n\s*ONEY[A-Z0-9]+\b|\n\s*OUTWARD|\Z))"
        matches = re.findall(pattern, pdf_text)
        chunk = "\n".join(matches) if matches else ""

        if not chunk or is_empty_equipment(chunk):
            continue

        dest_m = re.search(r"(?:Final destination|5b\.Port of discharge|Port of discharge)[^\n]*(?:\n[^\n]*?)?[ \t:]+([A-Za-z0-9 -]+?)(?:[ \t]{2,}|\n|$)", chunk, re.IGNORECASE)
        pod_raw = dest_m.group(1).strip().upper() if dest_m else ""
        if not pod_raw:
            page_dest = re.search(r"5b\.Port of discharge[ \t:]*([^\n]+)", pdf_text, re.IGNORECASE)
            pod_raw = page_dest.group(1).strip().upper() if page_dest else "DURBAN"

        port_info = resolve_port_info(pod_raw, chunk, use_web_search)

        wgt_m = re.search(r"(?:TOTAL GROSS WEIGHT\s*:\s*|GROSS WEIGHT\s*[：:]\s*|1\)\s*)([\d \t\.,]+?)\s*(MTS|MT|KGS|KG)(?:\s|\(|\n|$)", chunk, re.IGNORECASE)
        if wgt_m:
            tonnage = to_tonnes(parse_num(wgt_m.group(1)), wgt_m.group(2))
        else:
            wgt_fallback = re.search(r"(?:TOTAL GROSS WEIGHT\s*:\s*|GROSS WEIGHT\s*[：:]\s*)([\d \t\.,]+)", chunk, re.IGNORECASE)
            tonnage = to_tonnes(parse_num(wgt_fallback.group(1))) if wgt_fallback else 0.0

        if tonnage <= 0.0:
            continue

        container_groups = re.findall(r"(\d+)\s*X\s*(\d{2}[A-Za-z0-9]+)", chunk, re.IGNORECASE)

        desc_m = re.search(r"(?:SAID TO CONTAIN:\s*(?:STC\s+)?|\d+\s+PKGS\s+)([A-Za-z0-9 \t\(\),.-]+?)(?:CN>|HS CODE|FORM M|\n\s*\d+\)|\n)", chunk, re.IGNORECASE)
        desc = desc_m.group(1).strip() if desc_m else "GENERAL CARGO"
        comm = classify_commodity(desc, use_web_search=use_web_search)

        if container_groups:
            total_containers = sum(int(q) for q, _ in container_groups if int(q) > 0)
            for q_str, sz_str in container_groups:
                q_val = int(q_str)
                if q_val <= 0:
                    continue
                c_tonnage = round(tonnage * (q_val / total_containers), 2) if total_containers > 0 else tonnage
                rows.append({
                    "SHIP": ship, "SHIP LINE": "OCEAN NETWORK EXPRESS", "AGENT": "ONE GH. LTD",
                    "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
                    "CONTYPE": normalize_container(sz_str), "CONTQTY": q_val, "COMMODITY": comm, "TONNAGES": c_tonnage
                })
        else:
            cont_tags = re.findall(r"\(CN\)\s+([A-Z0-9]+)", chunk)
            cont_qty = len(cont_tags) if cont_tags else 1
            cont_type = "40D" if "40" in chunk else "20D"
            rows.append({
                "SHIP": ship, "SHIP LINE": "OCEAN NETWORK EXPRESS", "AGENT": "ONE GH. LTD",
                "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
                "CONTYPE": cont_type, "CONTQTY": cont_qty, "COMMODITY": comm, "TONNAGES": tonnage
            })
    return rows

def parse_pil(pdf_text: str, use_web_search: bool = True):
    rows = []
    ship_m = re.search(r"Name of ship[^\n]*\n[ \t]*([A-Z0-9 ]+?)(?:CSYD|\b\d{4}|\n)", pdf_text, re.IGNORECASE)
    ship = ship_m.group(1).strip().upper() if ship_m else "UNKNOWN VESSEL"

    sections = re.split(r"(?:\n|^)(?=OUTWARD)", pdf_text)
    for sec in sections:
        pod_m = re.search(r"5b\.Port of discharge[ \t:]*([^\n]+)", sec, re.IGNORECASE)
        pod_raw = pod_m.group(1).strip().upper() if pod_m else "NANSHA"
        port_info = resolve_port_info(pod_raw, sec, use_web_search)

        bl_chunks = re.split(r"(?:\n|^)(?=N/A\s+[A-Z0-9]{8,15})", sec)
        for chunk in bl_chunks:
            if is_empty_equipment(chunk):
                continue

            wgt_m = re.search(r"1\)\s*([\d \t\.,]+)\s*(KGS|KG|MTS|MT)", chunk, re.IGNORECASE)
            raw_w = parse_num(wgt_m.group(1)) if wgt_m else 0.0
            if raw_w <= 0.0:
                continue
            tonnage = to_tonnes(raw_w, wgt_m.group(2))

            cont_types = re.findall(r"\((?:CY/CY|FCL/FCL)\)\s*-\s*([A-Z0-9]+)", chunk)
            if cont_types:
                cont_type = normalize_container(cont_types[0])
                cont_qty = len(cont_types)
            else:
                qty_m = re.search(r"(\d+)\s*X\s*(\d{2}[A-Z]*)", chunk)
                cont_qty = int(qty_m.group(1)) if qty_m else 1
                cont_type = normalize_container(qty_m.group(2)) if qty_m else "20D"

            desc_m = re.search(r"(?:SAID TO CONTAIN:|CONTAINER\(S\)\s+SAID\s+TO\s+CONTAIN:)[ \t]*([^\n]+)", chunk, re.IGNORECASE)
            desc = desc_m.group(1).strip() if desc_m else "GENERAL CARGO"
            comm = classify_commodity(desc, use_web_search=use_web_search)

            rows.append({
                "SHIP": ship, "SHIP LINE": "PACIFIC INTERNATIONAL LINES", "AGENT": "PIL GH. LTD",
                "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
                "CONTYPE": cont_type, "CONTQTY": cont_qty, "COMMODITY": comm, "TONNAGES": tonnage
            })
    return rows

def parse_goldstar(pdf_text: str, use_web_search: bool = True):
    rows = []
    ship_m = re.search(r"([A-Z0-9 ]+?)\s+\d{3}/[EW]", pdf_text)
    ship = ship_m.group(1).strip().upper() if ship_m else "UNKNOWN VESSEL"

    global_to_m = re.search(r"To\s*:\s*([^\n]+)", pdf_text, re.IGNORECASE)
    default_pod = global_to_m.group(1).strip().upper() if global_to_m else "ABIDJAN"

    bl_chunks = re.split(r"(?:\n|^)(?=Bill type:)", pdf_text)
    for chunk in bl_chunks[1:]:
        if is_empty_equipment(chunk):
            continue

        to_m = re.search(r"To\s*:\s*([^\n]+)", chunk, re.IGNORECASE)
        pod_raw = to_m.group(1).strip().upper() if to_m else default_pod
        port_info = resolve_port_info(pod_raw, chunk, use_web_search)

        qty_m = re.search(r"(\d+)\s*cont\s*([A-Z0-9]+)\s+([\d \t\.,]+)", chunk, re.IGNORECASE)
        if qty_m:
            cont_qty = int(qty_m.group(1))
            cont_type = normalize_container(qty_m.group(2))
            tonnage = to_tonnes(parse_num(qty_m.group(3)), "KG")
        else:
            continue

        if tonnage <= 0.0:
            continue

        desc_m = re.search(r"CONTAINERS S\.L\.A\.C\.\s*\n[ \t]*([A-Za-z0-9 \t\.,-]+)", chunk)
        desc = desc_m.group(1).strip() if desc_m else "GENERAL CARGO"
        comm = classify_commodity(desc, use_web_search=use_web_search)

        rows.append({
            "SHIP": ship, "SHIP LINE": "GOLD STAR LINE", "AGENT": "ISAG GH. LTD",
            "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
            "CONTYPE": cont_type, "CONTQTY": cont_qty, "COMMODITY": comm, "TONNAGES": tonnage
        })
    return rows

def parse_arkas(pdf_text: str, use_web_search: bool = True):
    rows = []
    ship_m = re.search(r"Vessel\s*\n?[ \t]*([A-Z0-9 ]+?)\s+MAS\w+", pdf_text, re.IGNORECASE)
    ship = ship_m.group(1).strip().upper() if ship_m else "UNKNOWN VESSEL"

    bl_chunks = re.split(r"(?:\n|^)(?=B/L#:)", pdf_text)
    for chunk in bl_chunks[1:]:
        if is_empty_equipment(chunk):
            continue

        pod_m = re.search(r"Port Of Discharge\s*\n?[ \t]*([A-Z ,.-]+?)(?:Terminal|\n|$)", chunk, re.IGNORECASE)
        pod_raw = pod_m.group(1).strip().upper() if pod_m else "GENOA"
        port_info = resolve_port_info(pod_raw, chunk, use_web_search)

        wgt_m = re.search(r"BL GROSS WEIGHT\s*:\s*([\d \t\.,]+)\s*(MTS|MT|KGS|KG)?", chunk, re.IGNORECASE)
        tonnage = to_tonnes(parse_num(wgt_m.group(1)), wgt_m.group(2) or "KG") if wgt_m else 0.0
        if tonnage <= 0.0:
            continue

        c_match = re.search(r"BL TOTAL CONTAINERS:\s*(\d+)\s*\n\s*\d+\*(\d{2}[ \t]*[A-Z]+)", chunk)
        if c_match:
            cont_qty = int(c_match.group(1))
            cont_type = normalize_container(c_match.group(2))
        else:
            cont_qty = 1
            cont_type = "40D"

        desc_m = re.search(r"\d+\s+(?:CARTONS|BAGS|PACKAGES)\s*\n[ \t]*([A-Za-z \t]+?)(?:NET WEIGHT|HS CODE|\n)", chunk, re.IGNORECASE)
        desc = desc_m.group(1).strip() if desc_m else "COCOA PRODUCTS"
        comm = classify_commodity(desc, use_web_search=use_web_search)

        rows.append({
            "SHIP": ship, "SHIP LINE": "ARKAS LINES", "AGENT": "ARKAS GH. LTD",
            "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
            "CONTYPE": cont_type, "CONTQTY": cont_qty, "COMMODITY": comm, "TONNAGES": tonnage
        })
    return rows

def parse_cosco(pdf_text: str, use_web_search: bool = True):
    rows = []
    ship_m = re.search(r"VESSEL\s*:\s*(?:\([A-Z]+\))?[ \t]*([A-Z0-9 ]+?)(?:SHIP FLAG|Voy|\n)", pdf_text, re.IGNORECASE)
    ship = ship_m.group(1).strip().upper() if ship_m else "UNKNOWN VESSEL"

    if "B/LNUMBER:" in pdf_text:
        bl_chunks = re.split(r"(?:\n|^)(?=B/LNUMBER:)", pdf_text)
        for chunk in bl_chunks[1:]:
            if is_empty_equipment(chunk):
                continue

            pod_m = re.search(r"(?:PORT OF DISCHARGE|PLACE OF DELIVERY)\s*:[ \t]*([A-Z ,.-]+)", chunk, re.IGNORECASE)
            pod_raw = pod_m.group(1).strip().upper() if pod_m else "APAPA"
            port_info = resolve_port_info(pod_raw, chunk, use_web_search)

            wgt_m = re.search(r"GROSS WEIGHT\s*[：:]\s*([\d \t\.,]+)\s*(KGS|KG|MTS|MT)", chunk, re.IGNORECASE)
            tonnage = to_tonnes(parse_num(wgt_m.group(1)), wgt_m.group(2)) if wgt_m else 0.0
            if tonnage <= 0.0:
                continue

            cont_lines = re.findall(r"\b([0-9]{2}[A-Z]{2})\b[^\n]*\bFCL/FCL\b", chunk)
            cont_qty = len(cont_lines) if cont_lines else 1
            cont_type = normalize_container(cont_lines[0]) if cont_lines else "20D"

            desc_m = re.search(r"DESCRIPTION OF GOODS\s*\n\s*([A-Z0-9 \t\(\)\.,-]+?)(?:GROSS WEIGHT|FORM M|HS CODE|\n\n)", chunk, re.IGNORECASE)
            desc = desc_m.group(1).strip() if desc_m else "GENERAL CARGO"
            comm = classify_commodity(desc, use_web_search=use_web_search)

            rows.append({
                "SHIP": ship, "SHIP LINE": "COSCO SHIPPING LINE", "AGENT": "COSCO GH. LTD",
                "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
                "CONTYPE": cont_type, "CONTQTY": cont_qty, "COMMODITY": comm, "TONNAGES": tonnage
            })
    else:
        bl_chunks = re.split(r"(?:\n|^)(?=Item No\.)", pdf_text)
        for chunk in bl_chunks[1:]:
            if is_empty_equipment(chunk):
                continue

            pod_m = re.search(r"B/L Port of Discharge\s*\n?[ \t]*([A-Z ,.-]+?)\s*B/L Place", chunk, re.IGNORECASE)
            pod_raw = pod_m.group(1).strip().upper() if pod_m else "XIAMEN"
            port_info = resolve_port_info(pod_raw, chunk, use_web_search)

            wgt_m = re.search(r"([\d,\.]+\d)\s*(KGS|KG|MTS|MT)", chunk, re.IGNORECASE)
            tonnage = to_tonnes(parse_num(wgt_m.group(1)), wgt_m.group(2)) if wgt_m else 0.0
            if tonnage <= 0.0:
                continue

            c_match = re.search(r"(\d+)\s*CONTAINER\(S\)", chunk, re.IGNORECASE)
            cont_qty = int(c_match.group(1)) if c_match else 1
            sz_match = re.search(r"\b(20|40|45)\s*(?:FT|'|HC|HQ|GP|DC|RF|RH)\b", chunk, re.IGNORECASE)
            cont_type = normalize_container(sz_match.group(0)) if sz_match else "40D"

            desc_m = re.search(r"Number and Kinds of Package/Description of Goods\s*\n[\s\S]*?\d+\s+BAGS\s*\n[\s\S]*?\n[ \t]*([A-Za-z \t]+?)\n", chunk)
            desc = desc_m.group(1).strip() if desc_m else "COCOA POWDER"
            comm = classify_commodity(desc, use_web_search=use_web_search)

            rows.append({
                "SHIP": ship, "SHIP LINE": "COSCO SHIPPING LINE", "AGENT": "COSCO GH. LTD",
                "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
                "CONTYPE": cont_type, "CONTQTY": cont_qty, "COMMODITY": comm, "TONNAGES": tonnage
            })
    return rows

def parse_maersk(pdf_text: str, use_web_search: bool = True):
    rows = []

    ship_m = re.search(r"(?:^|\n)[ \t]*Vessel[ \t]*\n[ \t]*([A-Z0-9 \-]+?)(?:[ \t]+Page|\n|$)", pdf_text, re.IGNORECASE)
    ship = ship_m.group(1).strip().upper() if ship_m else "UNKNOWN VESSEL"

    carrier, agent = ("CMA CGM", "CMA CGM GH. LTD.") if "CMA CGM" in ship else ("MAERSK LINE", "MAERSK GH. LTD.")

    clean_text = re.sub(
        r"(?:ML Export Manifest\s*\n)?Voyage No\b[\s\S]*?Rate\s+Currency\s+Prepaid\s+Collect\s*\n",
        "\n",
        pdf_text,
        flags=re.IGNORECASE
    )
    clean_text = re.sub(r"\n[ \t]*ML Export Manifest[ \t]*(?=\n|$)", "\n", clean_text, flags=re.IGNORECASE)

    bl_chunks = re.split(
        r"(?:^|\n)[ \t]*(?=(?:[A-Z0-9]{7,12}(?:\s*\n\s*[0-9]{1,4})?\s*\n\s*(?:MAEU|WAYBILL)\b|\d{8,12}\s+\d+\s*X\s*\d{2}\s*(?:DRY|REEF|OPEN|HC|HR)\b))",
        clean_text
    )

    for chunk in bl_chunks:
        if not ("MAEU" in chunk or "WAYBILL" in chunk):
            continue
        if is_empty_equipment(chunk):
            continue

        pod_m = re.search(r"(?:Final Disch|Vessel Disch|Del):\s*([^,\n]+(?:,[^,\n]+)?)", chunk, re.IGNORECASE)
        pod_raw = pod_m.group(1).strip().upper() if pod_m else "LOME"
        port_info = resolve_port_info(pod_raw, chunk, use_web_search)

        cont_summary_m = re.search(
            r"(?:^|\n)[ \t]*([^\n]*\d+\s*X\s*\d{2}\s*(?:DRY|REEF|OPEN|HC|HR)[^\n]*)\n[ \t]*(?:CY|SD|FCL)/(?:CY|SD|FCL)\b",
            chunk,
            re.IGNORECASE
        )
        if cont_summary_m:
            cont_matches = re.findall(r"(\d+)\s*X\s*(\d{2}\s*(?:DRY|REEF|OPEN|HC|HR)[^\n,]*)", cont_summary_m.group(1), re.IGNORECASE)
        else:
            first_line_m = re.search(r"([^\n]*\d+\s*X\s*\d{2}\s*(?:DRY|REEF|OPEN|HC|HR)[^\n]*)", chunk, re.IGNORECASE)
            cont_matches = re.findall(r"(\d+)\s*X\s*(\d{2}\s*(?:DRY|REEF|OPEN|HC|HR)[^\n,]*)", first_line_m.group(1), re.IGNORECASE) if first_line_m else []

        if not cont_matches:
            cont_matches = [("1", "40 DRY")]

        total_cont_qty = sum(int(q) for q, _ in cont_matches if int(q) > 0) or 1

        cleaned_wgt = re.sub(r"Tare(?:\s*Weight)?\s*:\s*[\d\.,\s]+(?:KGS|KG)", "", chunk, flags=re.IGNORECASE)
        tonnage = 0.0

        explicit_totals = re.findall(
            r"(?:TOTAL\s+GROSS\s+WEIGHT|TOTAL\s+GROSS\s+WT|TOTAL\s+GR\.?\s*WT\.?|TOTAL\s+GRS\.?\s*WT\.?|TOTAL\s+G\.?W\.?|TOTAL\s+CARGO\s+GROSS\s+WEIGHT)\s*[:\.\-]*\s*([\d \t\.,]+)\s*(KGS|KG|MTS|MT)",
            cleaned_wgt,
            re.IGNORECASE
        )
        if explicit_totals:
            val_str, unit_str = explicit_totals[0]
            tonnage = to_tonnes(parse_num(val_str), unit_str)
        else:
            col_totals = re.findall(
                r"(?:^|\n)[ \t]*([\d\.,]+)\s*KGS\s*\n\s*(?:Basic Ocean|Additional Import|Additional Export|Container Protect|Inland Haulage|Additional|Storage Export|Inspection Fee|Demurrage|Detention|Electronic Cargo|Terminal Handling|Port Additionals|Import Service|Documentation fee|Document Stamp|Verified Gross Mass|Rollable Compensation|Late Payment|Transport Document|DMR Free|Change of Destination|Consignee FT|Spot Booking|3rd Party)",
                cleaned_wgt,
                re.IGNORECASE
            )
            if col_totals:
                tonnage = to_tonnes(parse_num(col_totals[0]), "KG")
            else:
                standalone_kgs = re.findall(r"(?:^|\n)[ \t]*([\d\.,]+)\s*KGS(?:[ \t]+[\d\.,]+[ \t]*CBM)?[ \t]*(?:\n|$)", cleaned_wgt, re.IGNORECASE)
                valid_standalone = [parse_num(w) for w in standalone_kgs if parse_num(w) > 0]
                if valid_standalone:
                    tonnage = to_tonnes(max(valid_standalone), "KG")
                else:
                    item_matches = re.findall(
                        r"(?:BALES|BAGS|PACKAGES|CARTONS|UNITS|PIECES|COLIS|PKGS|PACKAGE|SACKS|CARTON|BALE|PLTS|PALLET|PALLETS|CTNS|BOXES|ROLLS|DRUMS|DRUM|CRATES|SETS|IBCS)\s+([\d \t\.,]+)\s*KGS",
                        cleaned_wgt,
                        re.IGNORECASE
                    )
                    valid_nums = [parse_num(w) for w in item_matches if parse_num(w) > 0]
                    if valid_nums:
                        raw_kg = sum(valid_nums) if (total_cont_qty > 1 and len(valid_nums) > 1) else max(valid_nums)
                        tonnage = to_tonnes(raw_kg, "KG")

        if tonnage <= 0:
            continue

        hs_m = re.search(r"Shipper Provided HS Code\s*[:\-\.]*\s*(\d{4,10})", chunk, re.IGNORECASE)
        if not hs_m:
            hs_m = re.search(r"\bH\.?S\.?N?(?:\s*CODE)?(?:\s*NO\.?)?\s*[:\-\.]+\s*(\d{4,10})", chunk, re.IGNORECASE)
        hs = hs_m.group(1) if hs_m else ""

        desc_parts = []
        d1 = re.search(
            r"(?:CY|SD|FCL)/(?:CY|SD|FCL)\s*\n([\s\S]+?)(?=\n(?:Basic Ocean Freight|Additional Import Service|Additional Export Service|Documentation fee|Document Stamp Tax|Late Payment Fee|Electronic Cargo Release|Rollable Compensation|Transport Document|Detention Fee|Demurrage Fee|DMR Free|Change of Destination|Consignee FT|Final Disch:|Shipper:|Consignee:|$))",
            chunk,
            re.IGNORECASE
        )
        if d1:
            desc_parts.append(d1.group(1))

        for d2 in re.finditer(
            r"\nML-[A-Z0-9]+\s*\n(?:(?:Customs Seal|Shipper Seal)\s*\n\s*[A-Z0-9]+\s*\n)?(?!(?:27|26|28)\d{7}\b)([\s\S]+?)(?=\n(?:Basic Ocean Freight|Additional Import Service|Additional Export Service|Documentation fee|Document Stamp Tax|Late Payment Fee|Electronic Cargo Release|Rollable Compensation|Transport Document|Detention Fee|Demurrage Fee|Export Service|3rd Party Fine|Operational Cost|Terminal Handling|Port Additionals|Recovery for Handling|Value Protect|$))",
            chunk,
            re.IGNORECASE
        ):
            block_txt = d2.group(1).strip()
            if block_txt and not re.match(r"^(?:CY|SD|FCL)/(?:CY|SD|FCL)\b", block_txt, re.IGNORECASE):
                desc_parts.append(block_txt)

        raw_desc = "\n".join(desc_parts)
        raw_desc = re.sub(r"(?:Shipper Provided HS Code|Notify|Second Notify|Third Notify|Fourth Notify|Fifth Notify|2nd Notify|3rd Notify|4th Notify|5th Notify|ALSO NOTIFY|DESTINATION AGENT ADDRESS|Tare:)[^\n]*", "", raw_desc, flags=re.IGNORECASE)
        desc = raw_desc.strip()

        comm = classify_commodity(desc, hs, use_web_search)

        for q_str, sz_str in cont_matches:
            q_val = int(q_str)
            if q_val <= 0:
                continue
            c_tonnage = round(tonnage * (q_val / total_cont_qty), 2) if len(cont_matches) > 1 else tonnage
            rows.append({
                "SHIP": ship, "SHIP LINE": carrier, "AGENT": agent,
                "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
                "CONTYPE": normalize_container(sz_str), "CONTQTY": q_val, "COMMODITY": comm, "TONNAGES": c_tonnage
            })
    return rows

def parse_msc(pages_text: list, use_web_search: bool = True):
    """Parser for Mediterranean Shipping Company (MSC) Cargo Manifests."""
    rows = []
    full_text = "\n".join(pages_text)

    ship_m = re.search(r"Vessel\s*:\s*([A-Z0-9 \-]+?)(?:\s*\(\d+\)|\n|$)", full_text, re.IGNORECASE)
    if not ship_m:
        ship_m = re.search(r"\b(MSC\s+[A-Z0-9 \-]+?)\s*\(\d{4,6}\)", full_text, re.IGNORECASE)
    if not ship_m:
        ship_m = re.search(r"\b([A-Z0-9 \-]+?)\s*\(\d{4,6}\)\s+[A-Z0-9]{4,8}\b", full_text)
    ship = ship_m.group(1).strip().upper() if ship_m else "UNKNOWN VESSEL"

    shipments = []
    current_bl = None

    for page_txt in pages_text:
        if not page_txt.strip():
            continue
        upper_pg = page_txt.upper()
        if "SUMMARY" in upper_pg and ("EQUIPMENT TYPE" in upper_pg or "GRAND TOTAL" in upper_pg):
            continue

        # Extract 5b. PORT OF DISCHARGE from page header (excluding Transshipment port)
        pod_raw = ""
        hdr_slice_m = re.search(
            r"(?:BILL ISSUANCE|5b\.\s*PORT OF DISCHARGE)([\s\S]+?)(?=SHIPPER\s*\(SH\)|B/L NR\.|MEDU[A-Z]{1,3}\d|MSCU[A-Z]{1,3}\d|$)",
            page_txt,
            re.IGNORECASE
        )
        if hdr_slice_m:
            hdr_clean = hdr_slice_m.group(1)
            hdr_clean = re.sub(r"Transshipment:[^\n]*", "", hdr_clean, flags=re.IGNORECASE)
            hdr_clean = re.sub(r"\b(?:MSC\s+TEMA|TEMA|Panama|PLACE OF RECEIPT|FINAL DESTINATION|5a\.\s*PORT OF LOADING|5b\.\s*PORT OF DISCHARGE|3\.-\s*NATIONALITY OF SHIP|\(not required in U\.S\.\)|BILL ISSUANCE)\b", "", hdr_clean, flags=re.IGNORECASE)
            pod_raw = re.sub(r"\s+", " ", hdr_clean).strip().upper()

        if not pod_raw:
            pod_raw = "ANTWERP"

        # Strip static header block down to cargo rows if clearly bounded; never drop B/L numbers
        body = page_txt
        tbl_hdr_m = re.search(r"(?:Service Contract|9\s*-\s*MEASURMENT|DESCRIPTION OF GOODS)[^\n]*\n", page_txt, re.IGNORECASE)
        if tbl_hdr_m:
            after_hdr = page_txt[tbl_hdr_m.end():]
            # Only use stripped body if it didn't accidentally skip a B/L number above it
            if re.search(r"\b(?:MEDU|MSCU)[A-Z]{1,3}\d{5,9}\b", after_hdr) or not re.search(r"\b(?:MEDU|MSCU)[A-Z]{1,3}\d{5,9}\b", page_txt):
                body = after_hdr

        # Match MSC B/L numbers (e.g. MEDUTM455506) — ignores container numbers (e.g. CN: MEDU4571063)
        bl_matches = list(re.finditer(r"(?<!CN:\s)\b((?:MEDU|MSCU)[A-Z]{1,3}\d{5,9})\b", body))
        if bl_matches:
            pre_text = body[:bl_matches[0].start()].strip()
            if pre_text and current_bl is not None:
                current_bl["chunks"].append(pre_text)

            for idx, m in enumerate(bl_matches):
                if current_bl is not None:
                    shipments.append(current_bl)
                end_pos = bl_matches[idx + 1].start() if idx + 1 < len(bl_matches) else len(body)
                current_bl = {
                    "bl": m.group(1),
                    "pod": pod_raw,
                    "chunks": [body[m.start():end_pos]]
                }
        else:
            if current_bl is not None:
                current_bl["chunks"].append(body)

    if current_bl is not None:
        shipments.append(current_bl)

    for s in shipments:
        chunk = "\n".join(s["chunks"])
        if is_empty_equipment(chunk):
            continue

        port_info = resolve_port_info(s["pod"], chunk, use_web_search)

        # Container types and quantities from "Total No. of containers: ..."
        cont_counts = {}
        tot_cont_m = re.search(r"Total No\. of containers:\s*([^\n]+)", chunk, re.IGNORECASE)
        if tot_cont_m:
            for q_str, sz_str in re.findall(r"(\d+)\s*x\s*((?:20|40|45)['\s]*[^\n,]+)", tot_cont_m.group(1), re.IGNORECASE):
                q_val = int(q_str)
                if q_val > 0:
                    ctype = normalize_container(sz_str)
                    cont_counts[ctype] = cont_counts.get(ctype, 0) + q_val

        if not cont_counts:
            cn_list = re.findall(r"\bCN:\s*[A-Z]{4}\d{7}\b", chunk)
            qty_fb = len(cn_list) if cn_list else 1
            sz_fb = "40R" if "REEF" in chunk.upper() and "40" in chunk else ("40D" if "40'" in chunk or "40 HIGH" in chunk.upper() else "20D")
            cont_counts = {sz_fb: qty_fb}

        total_cont_qty = sum(cont_counts.values()) or 1

        # Gross Weight: check "Total on this bill of lading:" first (ignoring cu. m.), then sum container weights
        total_kg = 0.0
        tot_line_m = re.search(r"Total on this bill of lading:([^\n]+)", chunk, re.IGNORECASE)
        if tot_line_m:
            tot_line_clean = re.sub(r"[\d,\.]+\s*cu\.\s*m\.?", "", tot_line_m.group(1), flags=re.IGNORECASE)
            tot_nums = re.findall(r"\b(\d[\d,]*\.\d{2})\b", tot_line_clean)
            if tot_nums:
                total_kg = parse_num(tot_nums[-1])

        body_no_tot = re.split(r"Total No\. of containers:", chunk, flags=re.IGNORECASE)[0]
        body_no_net = re.sub(r"(?:NET\s*WEIGHT|Tare\s*Weight)[^\n]*", "", body_no_tot, flags=re.IGNORECASE)
        if total_kg <= 0.0:
            wgt_matches = re.findall(r"\b(\d[\d,]*\.\d{2})\s*kgs\.", body_no_net, re.IGNORECASE)
            total_kg = sum(parse_num(w) for w in wgt_matches)

        tonnage = round(total_kg / 1000.0, 2)
        if tonnage <= 0.0:
            continue

        hs_m = re.search(r"(?:HS\s*CODE|Harmonized\s*Code)\s*[:\.]*\s*([\d\.\s]{4,14})", chunk, re.IGNORECASE)
        hs = re.sub(r"[^0-9]", "", hs_m.group(1))[:10] if hs_m else ""

        desc_clean = re.sub(r"(?:^|\n)\s*(?:SH|CO|NF|CN|SN|MN|Tare Weight|Service Contract|EXPRESS RELEASE|Total No\. of containers|Total on this bill)[^\n]*", "", body_no_net, flags=re.IGNORECASE)
        desc_clean = re.sub(r"\b\d[\d,]*\.\d{2}(?:kgs|lbs|cu\.\s*m|cu\.ft)\.?", "", desc_clean, flags=re.IGNORECASE)
        comm = classify_commodity(desc_clean, hs, use_web_search)

        for ctype, q_val in cont_counts.items():
            c_tonnage = round(tonnage * (q_val / total_cont_qty), 2) if len(cont_counts) > 1 else tonnage
            rows.append({
                "SHIP": ship, "SHIP LINE": "MEDITERRANEAN SHIPPING COMPANY", "AGENT": "MSC GH. LTD",
                "PORT": port_info[0], "CTRY": port_info[1], "RANGE": port_info[2],
                "CONTYPE": ctype, "CONTQTY": q_val, "COMMODITY": comm, "TONNAGES": c_tonnage
            })

    return rows

def parse_grimaldi(pdf_text: str, use_web_search: bool = True):
    """Parser for Grimaldi Deep Sea S.p.A. / Grimaldi Lines Cargo Manifests."""
    rows = []

    ship_m = re.search(r"Name Of Ship And Voyage No\.[^\n]*\n[ \t]*\|?[ \t]*([A-Z0-9 \-]+?)[ \t]*:", pdf_text, re.IGNORECASE)
    ship = ship_m.group(1).strip().upper() if ship_m else "UNKNOWN VESSEL"

    pages = re.split(r"Page\s+\d+\s+of\s+\d+", pdf_text, flags=re.IGNORECASE)
    shipments = []
    current_bl = None

    for page_txt in pages:
        if not page_txt.strip():
            continue
        if any(skip in page_txt for skip in ["Parameter Information:", "Header Page", "Totals For :", "Grand Totals :", "Summary Totals :"]):
            continue
        if "B/L No." not in page_txt:
            continue

        pod_val = ""
        del_val = ""
        hdr_m = re.search(r"\|[^\n]*Port Of Discharge[^\n]*\n(\|[^\n]+)", page_txt, re.IGNORECASE)
        if hdr_m:
            cols = [c.strip() for c in hdr_m.group(1).split("|")]
            if len(cols) >= 7:
                pod_val = cols[5].upper()
                del_val = cols[6].upper()
            elif len(cols) >= 6:
                pod_val = cols[-2].upper()
        if not pod_val:
            pod_fb = re.search(r"Port Of Discharge\s*\n[ \t]*\|?[ \t]*([A-Z0-9 \-,]+)", page_txt, re.IGNORECASE)
            pod_val = pod_fb.group(1).strip().upper() if pod_fb else "ANTWERP"

        page_dest = del_val if del_val else pod_val

        body_m = re.search(r"\|B/L No\.[^\n]*\n\|[-]+\|[ \t]*\n([\s\S]*)", page_txt, re.IGNORECASE)
        body = body_m.group(1) if body_m else page_txt

        for line in body.splitlines():
            if re.match(r"^\s*\|?[-]{5,}\|?\s*$", line):
                continue
            bl_m = re.match(r"^\s*\|?\s*(\[?[A-Z]\d{8,12}(?:\[[A-
