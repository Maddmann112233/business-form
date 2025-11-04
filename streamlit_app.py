from google.oauth2.service_account import Credentials
import gspread
import streamlit as st
import pandas as pd

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly"
]

creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
gc = gspread.authorize(creds)

sheet = gc.open_by_key("1mtlFkp7yAMh8geFF1cfcyruYJhcafsetJktOhwTZz1Y").worksheet("Sheet1")
df = pd.DataFrame(sheet.get_all_records())
st.dataframe(df)
