import json
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ----------------- CONFIG -----------------
SPREADSHEET_ID = "1mtlFkp7yAMh8geFF1cfcyruYJhcafsetJktOhwTZz1Y"
WORKSHEET_NAME = "Sheet1"     # change if your tab name differs
ID_COLUMN_CANDIDATES = ["id", "ID", "Id", "request_id", "ticket_id"]
JSON_COLUMN_NAME = None       # e.g. "table" if you know it; leave None to auto-detect
# ------------------------------------------

st.set_page_config(page_title="", layout="wide")

# ----- Google Sheets client from st.secrets -----
def _gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=60)
def load_sheet_df(spreadsheet_id: str, worksheet_name: str) -> pd.DataFrame:
    gc = _gspread_client()
    ws = gc.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    rows = ws.get_all_records()  # list[dict]
    return pd.DataFrame(rows)

def _get_query_params():
    try:
        return st.query_params
    except Exception:
        return st.experimental_get_query_params()

def _pick_id_column(df: pd.DataFrame) -> str | None:
    for c in ID_COLUMN_CANDIDATES:
        if c in df.columns:
            return c
    return None

def _auto_detect_json_column(row: pd.Series) -> str | None:
    for col, val in row.items():
        if isinstance(val, str):
            s = val.strip()
            if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                return col
    return None

def _to_table(json_text: str) -> pd.DataFrame | None:
    try:
        data = json.loads(json_text)
    except Exception:
        return None
    # list of objects → table
    if isinstance(data, list):
        if len(data) == 0:
            return pd.DataFrame()
        if all(isinstance(x, dict) for x in data):
            return pd.json_normalize(data, max_level=1)
        # list of scalars
        return pd.DataFrame({"value": data})
    # single object → flatten
    if isinstance(data, dict):
        # try to expand nested quickly
        flat = pd.json_normalize(data, max_level=1)
        # if it ends up as a single wide row, show as key/value pairs for readability
        if flat.shape[0] == 1:
            kv = pd.DataFrame(list(flat.iloc[0].to_dict().items()), columns=["field", "value"])
            return kv
        return flat
    # anything else → show raw
    return pd.DataFrame({"value": [data]})

# ----- Load data -----
df = load_sheet_df(SPREADSHEET_ID, WORKSHEET_NAME)
if df.empty:
    st.stop()  # nothing to show

# ----- Get ID from URL (?id=...) -----
qp = _get_query_params()
raw_id = qp.get("id")
if isinstance(raw_id, list):
    raw_id = raw_id[0]
if not raw_id:
    st.stop()  # no ID supplied => render nothing

# ----- Find the row by ID (case/space-insensitive) -----
id_col = _pick_id_column(df)
if not id_col:
    st.stop()  # no ID column => render nothing

mask = df[id_col].astype(str).str.strip().str.lower() == str(raw_id).strip().lower()
match = df[mask]
if match.empty:
    st.stop()  # no matching row => render nothing

row = match.iloc[0]

# ----- Find JSON column -----
json_col = JSON_COLUMN_NAME or _auto_detect_json_column(row)
if not json_col:
    st.stop()  # no JSON-looking column => render nothing

json_text = str(row[json_col]).strip()
table = _to_table(json_text)
if table is None:
    st.stop()

# ----- Display ONLY the table -----
st.dataframe(table, use_container_width=True)
