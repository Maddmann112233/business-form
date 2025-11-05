import json
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

def _gspread_client_from_secret():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds_info = json.loads(st.secrets["GOOGLE_CREDS_JSON"])
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=60)
def read_sheet_df(spreadsheet_id: str, worksheet_name: str) -> pd.DataFrame:
    gc = _gspread_client_from_secret()
    ws = gc.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    rows = ws.get_all_records()  # list[dict]
    return pd.DataFrame(rows)

def show_sheet():
    sid = st.secrets["sheets"]["spreadsheet_id"]
    wsn = st.secrets["sheets"]["worksheet_name"]
    try:
        df = read_sheet_df(sid, wsn)
        if df.empty:
            st.info("الورقة فارغة.")
        else:
            st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"تعذر تحميل بيانات Google Sheets: {e}")
