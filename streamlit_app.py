import json
import pandas as pd
import streamlit as st
import gspread
import requests
from urllib.parse import urlparse
from google.oauth2.service_account import Credentials

# ================= CONFIG =================
SPREADSHEET_ID = "1mtlFkp7yAMh8geFF1cfcyruYJhcafsetJktOhwTZz1Y"
WORKSHEET_NAME = "Sheet1"
ID_COLUMN_CANDIDATES = ["id", "ID", "Id", "request_id", "ticket_id"]
STATE_COLUMN = "State"
REQUIRED_STATE = "Waiting For Business"
WEBHOOK_COLUMN = "Business Authorize"      # <— read webhook from this column
JSON_COLUMN_NAME = None                    # set explicit JSON column name if you know it; otherwise auto-detect
# ==========================================

st.set_page_config(page_title="MOH Business Owner", layout="wide")

# ---------- Styling (English / LTR) ----------
st.markdown(
    """
    <style>
    body, .stApp { direction: ltr; text-align: left; font-family: Tahoma, Arial, sans-serif; }
    h1, h2, h3, h4 { text-align: center; }
    .header { text-align:center; margin-bottom: 10px; }
    .stButton>button {
        background-color: #0A66C2; color: white; font-weight: 600;
        border-radius: 8px; width: 140px; height: 42px; font-size: 16px;
    }
    .stTextInput>div>div>input { text-align: left; font-size: 16px; }
    .stRadio label { font-size: 16px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown('<div class="header"><h2>MOH Business Owner</h2><h4>Data Sharing Request Review</h4></div>', unsafe_allow_html=True)

# ---------- Google Sheets helpers ----------
def _gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=60)
def load_sheet(spreadsheet_id, worksheet_name) -> pd.DataFrame:
    gc = _gspread_client()
    ws = gc.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    data = ws.get_all_records()
    return pd.DataFrame(data)

def detect_json_column(row: pd.Series):
    """Find first column in this row that looks like JSON."""
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
        if not data:
            return pd.DataFrame()
        if all(isinstance(x, dict) for x in data):
            return pd.json_normalize(data, max_level=1)
        return pd.DataFrame({"value": data})

    if isinstance(data, dict):
        flat = pd.json_normalize(data, max_level=1)
        if flat.shape[0] == 1:
            return pd.DataFrame(flat.iloc[0]).reset_index(names=["field"]).rename(columns={0: "value"})
        return flat

    return pd.DataFrame({"value": [data]})

def is_valid_url(s: str) -> bool:
    s = (s or "").strip()
    try:
        u = urlparse(s)
        return bool(u.scheme and u.netloc)
    except Exception:
        return False

# ---------- Load data ----------
df = load_sheet(SPREADSHEET_ID, WORKSHEET_NAME)
id_col = next((c for c in ID_COLUMN_CANDIDATES if c in df.columns), None)
if not id_col:
    st.error("ID column not found. Ensure the sheet has an 'id' column or update the candidates in code.")
    st.stop()

# ---------- Search UI (stores state) ----------
st.markdown("### Search by ID")
mid = st.columns([1, 3, 1])[1]
with mid:
    search_id_input = st.text_input("Enter Request ID:", key="search_id_input")
    search_btn = st.button("Search", use_container_width=True, key="search_btn")

# Persist selected ID and row in session_state so later widget changes (like radio) don't clear it
if search_btn:
    st.session_state.selected_id = search_id_input.strip()

# If we already have a selected ID, keep using it on rerun
selected_id = st.session_state.get("selected_id", "").strip()

selected_row = None
if selected_id:
    mask = df[id_col].astype(str).str.strip().str.lower() == selected_id.lower()
    match = df[mask]
    if not match.empty:
        selected_row = match.iloc[0]

if search_btn and not selected_id:
    st.warning("Enter an ID first.")

if selected_id and selected_row is None:
    st.warning("No rows found for this ID.")
    st.stop()

# ---------- Gate by State ----------
if selected_row is not None:
    if STATE_COLUMN not in selected_row.index:
        st.error(f"State column '{STATE_COLUMN}' not found in the sheet.")
        st.stop()

    current_state = str(selected_row[STATE_COLUMN]).strip()
    if current_state != REQUIRED_STATE:
        st.error(f"Cannot proceed. Current State is: {current_state}")
        st.stop()

    # ---------- JSON → table ----------
    json_col = JSON_COLUMN_NAME or detect_json_column(selected_row)
    if not json_col:
        st.error("No JSON-looking column found in this row.")
        st.stop()

    table = parse_json_to_table(str(selected_row[json_col]).strip())
    if table is None:
        st.error("JSON content could not be parsed.")
        st.stop()

    st.markdown("### Request Details")
    st.dataframe(table, use_container_width=True)

    # ---------- Webhook from 'Business Authorize' ----------
    webhook_url = str(selected_row.get(WEBHOOK_COLUMN, "")).strip()
    if not is_valid_url(webhook_url):
        st.warning(f"No valid webhook in column '{WEBHOOK_COLUMN}'. The decision will not be sent.")

    # ---------- Decision controls (persisted) ----------
    st.markdown("---")
    st.markdown("### Decision")

    # Persist decision widgets to avoid “reset” feel
    if "decision" not in st.session_state:
        st.session_state.decision = "Approve"
    if "reason" not in st.session_state:
        st.session_state.reason = ""

    st.session_state.decision = st.radio("Choose:", ["Approve", "Reject"], horizontal=True, index=0 if st.session_state.decision=="Approve" else 1, key="decision_radio")
    if st.session_state.decision == "Reject":
        st.session_state.reason = st.text_area("Rejection reason (required for Reject):", value=st.session_state.reason, key="reason_area")
    else:
        st.session_state.reason = ""

    submit = st.button("Submit decision", key="submit_decision")

    if submit:
        if st.session_state.decision == "Reject" and not st.session_state.reason.strip():
            st.warning("Please provide a rejection reason.")
        else:
            payload = {
                "id": selected_id,
                "decision": st.session_state.decision,
                "reason": st.session_state.reason.strip(),
                "state_checked": REQUIRED_STATE,
            }
            if is_valid_url(webhook_url):
                try:
                    r = requests.post(webhook_url, json=payload, timeout=15)
                    r.raise_for_status()
                    st.success("Decision sent successfully.")
                except Exception as e:
                    st.error(f"Failed to POST to webhook: {e}")
            else:
                st.info("Decision not sent because no valid webhook was found.")
