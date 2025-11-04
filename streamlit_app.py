import json
import pandas as pd
import streamlit as st
import gspread
import requests
from google.oauth2.service_account import Credentials
from urllib.parse import urlparse

# =============== CONFIG ===============
SPREADSHEET_ID = "1mtlFkp7yAMh8geFF1cfcyruYJhcafsetJktOhwTZz1Y"
WORKSHEET_NAME = "Sheet1"
ID_COLUMN_CANDIDATES = ["id", "ID", "Id", "request_id", "ticket_id"]
JSON_COLUMN_NAME = None  # set to explicit column if you know it, else auto-detect
STATE_COLUMN = "State"
REQUIRED_STATE = "Waiting For Business"
WEBHOOK_COLUMN = "Business Authorize"
# =====================================

st.set_page_config(page_title="MOH Business Owner", layout="wide")

# --- Styling: Arabic RTL + centered header ---
st.markdown(
    """
    <style>
    body, .stApp { direction: rtl; text-align: right; font-family: Tahoma, sans-serif; }
    h1, h2, h3, h4 { text-align: center; }
    .header-container { text-align:center; margin-bottom: 10px; }
    .stButton>button {
        background-color: #0A66C2; color: white; font-weight: bold;
        border-radius: 8px; width: 120px; height: 42px; font-size: 16px;
    }
    .stTextInput>div>div>input { text-align: center; direction: rtl; font-size: 16px; }
    .stRadio label { font-size: 16px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="header-container">
        <h2>MOH Business Owner</h2>
        <h4>نظام مراجعة طلبات مشاركة البيانات</h4>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Google Sheets connection ---
def _gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    return gspread.authorize(creds)

@st.cache_data(ttl=60)
def load_sheet(spreadsheet_id, worksheet_name):
    gc = _gspread_client()
    ws = gc.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    data = ws.get_all_records()
    return pd.DataFrame(data)

def detect_json_column(row: pd.Series):
    for col, val in row.items():
        if isinstance(val, str):
            s = val.strip()
            if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                return col
    return None

def parse_json_to_table(text: str) -> pd.DataFrame | None:
    try:
        data = json.loads(text)
    except Exception:
        return None

    if isinstance(data, list):
        if len(data) == 0:
            return pd.DataFrame()
        if all(isinstance(x, dict) for x in data):
            return pd.json_normalize(data)
        return pd.DataFrame({"القيمة": data})

    if isinstance(data, dict):
        flat = pd.json_normalize(data, max_level=1)
        if flat.shape[0] == 1:
            return (
                pd.DataFrame(flat.iloc[0])
                .reset_index(names=["الحقل"])
                .rename(columns={0: "القيمة"})
            )
        return flat

    return pd.DataFrame({"القيمة": [data]})

def looks_like_url(s: str) -> bool:
    try:
        u = urlparse(s)
        return bool(u.scheme and u.netloc)
    except Exception:
        return False

# --- Load data ---
df = load_sheet(SPREADSHEET_ID, WORKSHEET_NAME)
id_col = next((c for c in ID_COLUMN_CANDIDATES if c in df.columns), None)
if not id_col:
    st.error("لم يتم العثور على عمود للـ ID في الورقة.")
    st.stop()

# --- Centered search box ---
st.markdown("<h3>البحث برقم الطلب</h3>", unsafe_allow_html=True)
col_center = st.columns([1, 3, 1])
with col_center[1]:
    search_id = st.text_input("أدخل رقم الطلب:", key="search_id", label_visibility="collapsed")
    search_btn = st.button("بحث", use_container_width=True)

# --- Search logic ---
if search_btn and not search_id.strip():
    st.warning("يرجى إدخال رقم الطلب أولاً.")

if search_btn and search_id.strip():
    mask = df[id_col].astype(str).str.strip().str.lower() == search_id.strip().lower()
    match = df[mask]

    if match.empty:
        st.warning("لا توجد نتيجة للمعرّف المدخل.")
        st.stop()

    row = match.iloc[0]

    # 1) enforce state
    if STATE_COLUMN not in row.index:
        st.error(f"لم يتم العثور على عمود الحالة '{STATE_COLUMN}'.")
        st.stop()

    current_state = str(row[STATE_COLUMN]).strip()
    if current_state != REQUIRED_STATE:
        st.error(f"لا يمكن المعالجة. الحالة الحالية: {current_state}")
        st.stop()

    # 2) find JSON column and render table
    json_col = JSON_COLUMN_NAME or detect_json_column(row)
    if not json_col:
        st.error("لم يتم العثور على عمود يحتوي على بيانات JSON في الصف.")
        st.stop()

    table = parse_json_to_table(str(row[json_col]).strip())
    if table is None:
        st.error("تعذر قراءة بيانات JSON.")
        st.stop()

    st.markdown("<h3>تفاصيل الطلب</h3>", unsafe_allow_html=True)
    st.dataframe(table, use_container_width=True)

    # 3) read webhook from "Authorize" column
    webhook_url = str(row.get(WEBHOOK_COLUMN, "")).strip()
    if not webhook_url or not looks_like_url(webhook_url):
        st.warning("تعذر العثور على رابط التفويض في عمود Authorize أو أن الرابط غير صالح. لن يتم إرسال القرار.")
        webhook_url = ""

    # 4) decision controls
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<h3>القرار</h3>", unsafe_allow_html=True)

    decision = st.radio("يرجى اختيار القرار:", ["موافقة", "عدم موافقة"], horizontal=True, index=0)
    reason = ""
    if decision == "عدم موافقة":
        reason = st.text_area("سبب الرفض (إلزامي):")

    send = st.button("إرسال القرار")

    if send:
        if decision == "عدم موافقة" and not reason.strip():
            st.warning("يرجى كتابة سبب الرفض قبل الإرسال.")
        else:
            payload = {
                "id": search_id.strip(),
                "decision": decision,
                "reason": reason.strip() if decision == "عدم موافقة" else "",
                "state_checked": REQUIRED_STATE,
            }

            if webhook_url:
                try:
                    r = requests.post(webhook_url, json=payload, timeout=15)
                    r.raise_for_status()
                    st.success("تم إرسال القرار بنجاح.")
                except Exception as e:
                    st.error(f"تعذر إرسال القرار عبر الويب هوك: {e}")
            else:
                st.info("لم يتم إرسال القرار لأن رابط التفويض غير متوفر.")
