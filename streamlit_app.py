import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

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
def read_sheet_df(spreadsheet_id: str, worksheet_name: str) -> pd.DataFrame:
    gc = _gspread_client()
    ws = gc.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    data = ws.get_all_records()  # list of dicts
    return pd.DataFrame(data)

def show_sheet():
    sid = st.secrets["sheets"]["spreadsheet_id"]
    wsn = st.secrets["sheets"]["worksheet_name"]
    with st.expander("عرض بيانات Google Sheets", expanded=True):
        try:
            df = read_sheet_df(sid, wsn)
            if df.empty:
                st.info("الورقة فارغة أو لا تحتوي على صفوف حتى الآن.")
            else:
                st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"تعذر تحميل بيانات Google Sheets: {e}")

# call this somewhere in your page:
show_sheet()
