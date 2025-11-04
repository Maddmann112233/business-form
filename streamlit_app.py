import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ====== Google Sheets client (uses your TOML secrets) ======
def _gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=60)
def load_sheet(spreadsheet_id: str, worksheet_name: str) -> pd.DataFrame:
    gc = _gspread_client()
    ws = gc.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    data = ws.get_all_records()  # list of dicts
    return pd.DataFrame(data)

SPREADSHEET_ID = "1mtlFkp7yAMh8geFF1cfcyruYJhcafsetJktOhwTZz1Y"
WORKSHEET_NAME = "Sheet1"   # <-- غيّرها إذا كان اسم الورقة مختلفاً

st.header("البحث برقم الطلب (ID)")

# Load once
df = load_sheet(SPREADSHEET_ID, WORKSHEET_NAME)

if df.empty:
    st.info("الورقة لا تحتوي على بيانات بعد.")
else:
    # Normalize ID column name: try common variants
    possible_id_cols = ["id", "ID", "Id", "request_id", "ticket_id"]
    id_col = next((c for c in possible_id_cols if c in df.columns), None)

    if not id_col:
        st.error("لم يتم العثور على عمود للـ ID في الورقة. تأكد أن العمود اسمه 'id' (أو عدّل الكود ليطابق اسم العمود لديك).")
    else:
        # UI
        search_id = st.text_input("أدخل رقم الطلب (ID)")
        if st.button("بحث"):
            # String-compare: strip + case-insensitive
            series = df[id_col].astype(str).str.strip().str.lower()
            key = (search_id or "").strip().lower()
            result = df[series == key]

            if result.empty:
                st.warning(f"لا توجد نتيجة للمعرف: {search_id}")
            else:
                st.success(f"تم العثور على {len(result)} صف(وف).")
                # اختيار أعمدة (اختياري)
                with st.expander("تخصيص الأعمدة المعروضة (اختياري)"):
                    cols = st.multiselect("اختر الأعمدة", list(result.columns), default=list(result.columns))
                    st.dataframe(result[cols], use_container_width=True)
                # العرض الافتراضي
                if not cols:
                    st.dataframe(result, use_container_width=True)
