import json
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# =============== CONFIG ===============
SPREADSHEET_ID = "1mtlFkp7yAMh8geFF1cfcyruYJhcafsetJktOhwTZz1Y"
WORKSHEET_NAME = "Sheet1"       # غيّرها إذا كان اسم التبويب مختلف
ID_COLUMN_CANDIDATES = ["id", "ID", "Id", "request_id", "ticket_id"]
JSON_COLUMN_NAME = None         # ضع اسم العمود الذي يحتوي JSON إن كنت تعرفه (مثلاً "table_json")
# =====================================

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

def detect_json_column(row: pd.Series):
    """Return the first column that looks like JSON in this row."""
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
        return pd.DataFrame({"value": data})

    if isinstance(data, dict):
        flat = pd.json_normalize(data, max_level=1)
        if flat.shape[0] == 1:
            # show as key/value pairs for readability
            return pd.DataFrame(flat.iloc[0]).reset_index(names=["field"]).rename(columns={0: "value"})
        return flat

    return pd.DataFrame({"value": [data]})

# --- UI: ID input + "بحث" button (no Enter needed) ---
st.markdown("### البحث برقم الطلب")
with st.form("search_form", clear_on_submit=False):
    search_id = st.text_input("أدخل رقم الطلب (ID):", value=st.session_state.get("last_search_id", ""))
    do_search = st.form_submit_button("بحث")

df = load_sheet(SPREADSHEET_ID, WORKSHEET_NAME)

# Validate ID column
id_col = next((c for c in ID_COLUMN_CANDIDATES if c in df.columns), None)
if not id_col:
    st.error("⚠️ لم يتم العثور على عمود للـ ID في الورقة. تأكد من وجود عمود باسم 'id' أو عدّل القائمة في الكود.")
    st.stop()

# When user clicks "بحث"
if do_search:
    st.session_state["last_search_id"] = search_id

# If we have an ID to search (from the current click or previous state)
effective_id = st.session_state.get("last_search_id", "").strip()
if effective_id:
    mask = df[id_col].astype(str).str.strip().str.lower() == effective_id.lower()
    match = df[mask]

    if match.empty:
        st.warning(f"❌ لا توجد نتيجة للمعرّف: {effective_id}")
    else:
        row = match.iloc[0]
        # Determine which column has JSON
        json_col = JSON_COLUMN_NAME or detect_json_column(row)
        if not json_col:
            st.error("⚠️ لم يتم العثور على عمود يحتوي على JSON في الصف المطابق.")
        else:
            table = parse_json_to_table(str(row[json_col]).strip())
            if table is None:
                st.error("⚠️ تعذر قراءة محتوى JSON.")
            else:
                # Show ONLY the table + decision controls
                st.dataframe(table, use_container_width=True)

                # Decision controls
                st.markdown("---")
                decision = st.radio("القرار", ["موافقة", "عدم موافقة"], horizontal=True, index=0)
                reason = ""
                if decision == "عدم موافقة":
                    reason = st.text_area("سبب الرفض (إلزامي عند عدم الموافقة):")

                if st.button("إرسال القرار"):
                    if decision == "عدم موافقة" and not reason.strip():
                        st.warning("يرجى كتابة سبب الرفض قبل الإرسال.")
                    else:
                        # Placeholder: here you can POST to n8n or update Google Sheet
                        payload = {
                            "id": effective_id,
                            "decision": decision,
                            "reason": reason.strip() if decision == "عدم موافقة" else "",
                        }
                        # Example (disabled): requests.post(WEBHOOK_URL, json=payload, timeout=10)
                        st.success("تم حفظ القرار.")
                        st.json(payload)
