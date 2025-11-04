import json
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ================= CONFIG =================
SPREADSHEET_ID = "1mtlFkp7yAMh8geFF1cfcyruYJhcafsetJktOhwTZz1Y"
WORKSHEET_NAME = "Sheet1"
ID_COLUMN_CANDIDATES = ["id", "ID", "Id", "request_id", "ticket_id"]
JSON_COLUMN_NAME = None   # if you know the exact name, e.g. "table", set it here
# ==========================================

st.set_page_config(page_title="نتائج الطلب", layout="wide")

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

def detect_json_column(row):
    for col, val in row.items():
        if isinstance(val, str):
            s = val.strip()
            if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                return col
    return None

def parse_json_to_table(text):
    try:
        data = json.loads(text)
    except Exception:
        return None

    if isinstance(data, list):
        if all(isinstance(x, dict) for x in data):
            return pd.json_normalize(data)
        return pd.DataFrame({"value": data})

    if isinstance(data, dict):
        flat = pd.json_normalize(data, max_level=1)
        if flat.shape[0] == 1:
            return pd.DataFrame(flat.T).reset_index(names=["field"]).rename(columns={0: "value"})
        return flat

    return pd.DataFrame({"value": [data]})

# --- Load the sheet ---
df = load_sheet(SPREADSHEET_ID, WORKSHEET_NAME)

# --- Input ID manually ---
id_col = next((c for c in ID_COLUMN_CANDIDATES if c in df.columns), None)
if not id_col:
    st.error("⚠️ لم يتم العثور على عمود للـ ID في الجدول.")
    st.stop()

search_id = st.text_input("أدخل رقم الطلب (ID):")

if search_id:
    mask = df[id_col].astype(str).str.strip().str.lower() == search_id.strip().lower()
    match = df[mask]

    if match.empty:
        st.warning("❌ لم يتم العثور على أي صف بالـ ID المدخل.")
    else:
        row = match.iloc[0]
        json_col = JSON_COLUMN_NAME or detect_json_column(row)

        if not json_col:
            st.error("⚠️ لم يتم العثور على أي عمود يحتوي على JSON.")
        else:
            table = parse_json_to_table(row[json_col])
            if table is None:
                st.error("⚠️ لا يمكن قراءة محتوى JSON.")
            else:
                # Hide everything except the table
                st.markdown(
                    """
                    <style>
                    header, footer, [data-testid="stSidebar"], .stToolbar {visibility: hidden;}
                    </style>
                    """,
                    unsafe_allow_html=True,
                )
                st.dataframe(table, use_container_width=True)
