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

# RTL styling and Arabic font
st.markdown(
    """
    <style>
    body, .stApp {
        direction: rtl;
        text-align: right;
        font-family: 'Tahoma', sans-serif;
    }
    .stButton>button {
        width: 150px;
        background-color: #0A66C2;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        height: 40px;
    }
    .stRadio label {
        font-size: 16px;
        font-weight: 600;
    }
    h1, h2, h3 {
        text-align: center;
        font-family: 'Tahoma', sans-serif;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Header ---
st.markdown("<h2>MOH Business Owner</h2>", unsafe_allow_html=True)
st.markdown("<h4>نظام مراجعة طلبات مشاركة البيانات</h4>", unsafe_allow_html=True)

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
            return pd.DataFrame(flat.iloc[0]).reset_index(names=["الحقل"]).rename(columns={0: "القيمة"})
        return flat

    return pd.DataFrame({"القيمة": [data]})

# --- UI Layout ---
df = load_sheet(SPREADSHEET_ID, WORKSHEET_NAME)

id_col = next((c for c in ID_COLUMN_CANDIDATES if c in df.columns), None)
if not id_col:
    st.error("⚠️ لم يتم العثور على عمود للـ ID في الورقة.")
    st.stop()

st.markdown("### 🔍 البحث برقم الطلب")

col1, col2 = st.columns([3, 1])
with col1:
    search_id = st.text_input("أدخل رقم الطلب (ID):", key="search_id", label_visibility="collapsed")
with col2:
    do_search = st.button("بحث")

if do_search and not search_id.strip():
    st.warning("يرجى إدخال رقم الطلب أولاً.")

if do_search and search_id.strip():
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
                st.markdown("### 📋 تفاصيل الطلب")
                st.dataframe(table, use_container_width=True)

                st.markdown("---")
                st.markdown("### 💬 القرار")

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
                            "id": search_id,
                            "decision": decision,
                            "reason": reason.strip(),
                        }

                        # Placeholder for webhook integration:
                        # import requests
                        # WEBHOOK_URL = "https://tofyz.app.n8n.cloud/webhook-test/moh-form"
                        # requests.post(WEBHOOK_URL, json=payload, timeout=10)

                        st.success("✅ تم إرسال القرار بنجاح.")
                        st.json(payload)
