import json
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# =============== CONFIG ===============
SPREADSHEET_ID = "1mtlFkp7yAMh8geFF1cfcyruYJhcafsetJktOhwTZz1Y"
WORKSHEET_NAME = "Sheet1"
ID_COLUMN_CANDIDATES = ["id", "ID", "Id", "request_id", "ticket_id"]
JSON_COLUMN_NAME = None
# =====================================

st.set_page_config(page_title="MOH Business Owner", layout="wide")

# --- Custom Styling (Arabic + Center Alignment) ---
st.markdown(
    """
    <style>
    body, .stApp {
        direction: rtl;
        text-align: right;
        font-family: 'Tahoma', sans-serif;
        background-color: #0e1117;
        color: #ffffff;
    }
    h1, h2, h3, h4 {
        text-align: center;
        font-family: 'Tahoma', sans-serif;
    }
    .header-container {
        text-align: center;
        margin-bottom: 10px;
    }
    .search-container {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 15px;
        margin-top: 20px;
    }
    .stButton>button {
        background-color: #0A66C2;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        width: 120px;
        height: 42px;
        font-size: 16px;
    }
    .stTextInput>div>div>input {
        text-align: center;
        direction: rtl;
        font-size: 16px;
    }
    .stRadio label {
        font-size: 16px;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Header ---
st.markdown(
    """
    <div class="header-container">
        <h2>MOH Business Owner</h2>
        <h4>نظام مراجعة طلبات مشاركة البيانات</h4>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Google Sheets Connection ---
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
            return pd.DataFrame(flat.iloc[0]).reset_index(names=["الحقل"]).rename(columns={0: "القيمة"})
        return flat

    return pd.DataFrame({"القيمة": [data]})

# --- Load Data ---
df = load_sheet(SPREADSHEET_ID, WORKSHEET_NAME)
id_col = next((c for c in ID_COLUMN_CANDIDATES if c in df.columns), None)
if not id_col:
    st.error("⚠️ لم يتم العثور على عمود للـ ID في الورقة.")
    st.stop()

# --- Centered Search Box ---
st.markdown("<h3>🔍 البحث برقم الطلب</h3>", unsafe_allow_html=True)

# Center search input and button using columns
col_center = st.columns([1, 3, 1])
with col_center[1]:
    search_id = st.text_input("أدخل رقم الطلب:", key="search_id", label_visibility="collapsed")
    search_btn = st.button("بحث", use_container_width=True)

# --- Search Logic ---
if search_btn and not search_id.strip():
    st.warning("يرجى إدخال رقم الطلب أولاً.")

if search_btn and search_id.strip():
    mask = df[id_col].astype(str).str.strip().str.lower() == search_id.strip().lower()
    match = df[mask]

    if match.empty:
        st.warning("❌ لا توجد نتيجة للمعرّف المدخل.")
    else:
        row = match.iloc[0]
        json_col = JSON_COLUMN_NAME or detect_json_column(row)

        if not json_col:
            st.error("⚠️ لم يتم العثور على عمود يحتوي على بيانات JSON في الصف.")
        else:
            table = parse_json_to_table(str(row[json_col]).strip())
            if table is None:
                st.error("⚠️ تعذر قراءة بيانات JSON.")
            else:
                st.markdown("<h3>📋 تفاصيل الطلب</h3>", unsafe_allow_html=True)
                st.dataframe(table, use_container_width=True)

                st.markdown("<hr>", unsafe_allow_html=True)
                st.markdown("<h3>💬 القرار</h3>", unsafe_allow_html=True)

                decision = st.radio("يرجى اختيار القرار:", ["موافقة", "عدم موافقة"], horizontal=True, index=0)
                reason = ""
                if decision == "عدم موافقة":
                    reason = st.text_area("سبب الرفض (إلزامي):")

                send = st.button("إرسال القرار", use_container_width=False)

                if send:
                    if decision == "عدم موافقة" and not reason.strip():
                        st.warning("يرجى كتابة سبب الرفض قبل الإرسال.")
                    else:
                        payload = {
                            "id": search_id,
                            "decision": decision,
                            "reason": reason.strip(),
                        }

                        # Example: send to n8n webhook
                        # import requests
                        # WEBHOOK_URL = "https://tofyz.app.n8n.cloud/webhook-test/moh-form"
                        # requests.post(WEBHOOK_URL, json=payload, timeout=10)

                        st.success("✅ تم إرسال القرار بنجاح.")
                        st.json(payload)
