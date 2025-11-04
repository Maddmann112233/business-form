import json
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Diag", layout="centered")
st.title("Streamlit – Google Sheets Diagnostics")

# 0) Show something unconditionally
st.success("App is running ✅")

# 1) Check secrets presence
has_json = "GOOGLE_CREDS_JSON" in st.secrets
has_sheets = "sheets" in st.secrets
st.write("Secrets present:", {"GOOGLE_CREDS_JSON": has_json, "sheets": has_sheets})

if not has_json or not has_sheets:
    st.error("Missing required secrets. Add GOOGLE_CREDS_JSON and [sheets] in Secrets, then Restart the app.")
    st.stop()

# 2) Parse creds JSON
try:
    creds_info = json.loads(st.secrets["GOOGLE_CREDS_JSON"])
    st.write("Creds keys:", sorted(list(creds_info.keys())))
except Exception as e:
    st.exception(e)
    st.stop()

# 3) Read sheet settings
SPREADSHEET_ID = st.secrets["sheets"].get("spreadsheet_id")
WORKSHEET_NAME = st.secrets["sheets"].get("worksheet_name")
st.write("Sheet config:", {"spreadsheet_id": SPREADSHEET_ID, "worksheet_name": WORKSHEET_NAME})
if not SPREADSHEET_ID or not WORKSHEET_NAME:
    st.error("Missing spreadsheet_id or worksheet_name in [sheets] secret.")
    st.stop()

# 4) Try to auth and load
try:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    rows = ws.get_all_records()  # list[dict]
    df = pd.DataFrame(rows)
    st.write("Rows loaded:", len(df))
    if df.empty:
        st.info("Sheet is empty (no data rows under the header).")
    else:
        st.dataframe(df, use_container_width=True)
except Exception as e:
    st.error("Failed to load Google Sheet:")
    st.exception(e)
