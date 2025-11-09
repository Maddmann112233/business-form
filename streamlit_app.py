import json
import pandas as pd
import streamlit as st
import gspread
import requests
import base64
from urllib.parse import urlparse
from google.oauth2.service_account import Credentials

# ================= الإعدادات =================
SPREADSHEET_ID = "1mtlFkp7yAMh8geFF1cfcyruYJhcafsetJktOhwTZz1Y"
WORKSHEET_NAME = "Sheet1"
ID_COLUMN_CANDIDATES = ["id", "ID", "Id", "request_id", "ticket_id"]
STATE_COLUMN = "State"
REQUIRED_STATE = "Waiting For Business"
WEBHOOK_COLUMN = "Business Authorize"
JSON_COLUMN_NAME = None
# ===========================================

st.set_page_config(page_title="MOH Business Owner", layout="wide")

# ====== الخلفية + الثيم المتوافق مع الصورة الجديدة ======
def set_background(png_file):
    with open(png_file, "rb") as f:
        data = f.read()
    encoded = base64.b64encode(data).decode()
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/png;base64,{encoded}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            background-repeat: no-repeat;
            color: #E9F5FF;
        }}
        .stApp::before {{
            content: "";
            position: fixed;
            inset: 0;
            background:
              radial-gradient(60% 80% at 75% 25%, rgba(33, 0, 95, .35) 0%, rgba(10, 12, 26, .65) 60%),
              linear-gradient(180deg, rgba(0, 0, 0, .15), rgba(0, 0, 0, .35));
            pointer-events: none;
            z-index: 0;
        }}

        :root {{
            --electric: #00E5FF;
            --violet:  #7C4DFF;
            --indigo:  #1A1F3B;
            --glass:   rgba(13, 16, 34, 0.42);
            --glass-2: rgba(13, 16, 34, 0.55);
            --border:  rgba(124, 77, 255, 0.35);
            --text:    #E9F5FF;
        }}

        body, .stApp {{ direction: rtl; text-align: right; font-family: Tahoma, Arial, sans-serif; }}
        .block-container {{ padding-top: 24px; position: relative; z-index: 1; }}
        .block-container > :not(style) {{ backdrop-filter: blur(6px); }}

        h1, h2, h3, h4 {{
            color: var(--electric) !important;
            text-shadow: 0 1px 12px rgba(0,0,0,.35);
            text-align: center;
        }}

        .stButton>button {{
            background: linear-gradient(135deg, var(--violet), var(--electric));
            color: #0B1020;
            font-weight: 800;
            border: 0;
            border-radius: 14px;
            height: 44px;
            padding: 0 22px;
            box-shadow: 0 12px 30px rgba(0, 229, 255, .22), inset 0 0 0 1px rgba(255,255,255,.12);
            transition: transform .06s ease, box-shadow .2s ease, filter .2s ease;
        }}
        .stButton>button:hover {{ filter: brightness(1.06); box-shadow: 0 16px 36px rgba(124, 77, 255, .28); }}
        .stButton>button:active {{ transform: translateY(1px) scale(.99); }}

        .stTextInput>div>div>input,
        .stTextArea textarea {{
            background: var(--glass);
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 12px;
            text-align: center;
        }}
        .stTextInput>div>div>input:focus,
        .stTextArea textarea:focus {{
            outline: none;
            border-color: var(--electric);
            box-shadow: 0 0 0 3px rgba(0, 229, 255, .25);
        }}

        .segmented .stRadio > div {{ display:flex; gap:10px; justify-content:center; flex-wrap: wrap; }}
        .segmented .stRadio label {{
            padding:10px 18px;
            border:1px solid var(--border);
            border-radius:999px;
            cursor:pointer; font-weight:700; user-select:none;
            background: var(--glass-2);
            color: var(--text);
        }}
        .segmented .stRadio input {{ display:none; }}
        .segmented .stRadio [aria-checked="true"] + span {{
            background: linear-gradient(135deg, var(--violet), var(--electric));
            color:#0B1020; border-color: transparent;
            box-shadow: 0 8px 20px rgba(124, 77, 255, .32);
        }}
        .segmented .stRadio label:hover {{ border-color: var(--electric); }}

        .stAlert>div {{ background: var(--glass-2); color: var(--text); border: 1px solid var(--border); border-radius: 12px; }}
        </style>
        """,
        unsafe_allow_html=True
    )

set_background("Gemini_Generated_Image_ls8zmgls8zmgls8z.png")

st.markdown('<h2>MOH Business Owner</h2><h4>نظام مراجعة طلبات مشاركة البيانات</h4>', unsafe_allow_html=True)

# ====== Google Sheets ======
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
    for col, val in row.items():
        if isinstance(val, str):
            s = val.strip()
            if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                return col
    return None

def is_valid_url(s: str) -> bool:
    s = (s or "").strip()
    try:
        u = urlparse(s)
        return bool(u.scheme and u.netloc)
    except Exception:
        return False

# ====== تحميل البيانات ======
df = load_sheet(SPREADSHEET_ID, WORKSHEET_NAME)
id_col = next((c for c in ID_COLUMN_CANDIDATES if c in df.columns), None)
if not id_col:
    st.error("لم يتم العثور على عمود يحتوي على المعرف (ID).")
    st.stop()

# ====== البحث برقم الطلب ======
st.markdown("### البحث برقم الطلب")
center = st.columns([1, 3, 1])[1]
with center:
    sid = st.text_input("أدخل رقم الطلب:", key="search_id_input")
    search_btn = st.button("بحث", use_container_width=True)

if search_btn:
    st.session_state.selected_id = (sid or "").strip()

selected_id = (st.session_state.get("selected_id") or "").strip()

selected_row = None
if selected_id:
    mask = df[id_col].astype(str).str.strip().str.lower() == selected_id.lower()
    match = df[mask]
    if not match.empty:
        selected_row = match.iloc[0]

if search_btn and not selected_id:
    st.warning("يرجى إدخال رقم الطلب أولاً.")

if selected_id and selected_row is None:
    st.warning("لا توجد نتائج مطابقة لهذا الرقم.")
    st.stop()

# ====== التحقق من الحالة ======
if selected_row is not None:
    if STATE_COLUMN not in selected_row.index:
        st.error(f"لم يتم العثور على عمود الحالة '{STATE_COLUMN}'.")
        st.stop()

    current_state = str(selected_row[STATE_COLUMN]).strip()
    if current_state != REQUIRED_STATE:
        st.error(f"لا يمكن متابعة المعالجة. الحالة الحالية هي: {current_state}")
        st.stop()

    # ====== قراءة رابط الويب هوك ======
    webhook_url = str(selected_row.get(WEBHOOK_COLUMN, "")).strip()
    if not is_valid_url(webhook_url):
        st.warning(f"تعذر العثور على رابط ويب هوك صالح في العمود '{WEBHOOK_COLUMN}'. لن يتم إرسال القرار.")

    # ====== واجهة القرار ======
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("### القرار")

    if "decision" not in st.session_state:
        st.session_state.decision = "موافقة"
    if "reason" not in st.session_state:
        st.session_state.reason = ""

    with st.container():
        st.markdown('<div class="segmented">', unsafe_allow_html=True)
        st.session_state.decision = st.radio(
            "اختر القرار:",
            ["موافقة", "غير موافق"],
            horizontal=True,
            key="decision_radio_ar",
            index=0 if st.session_state.decision == "موافقة" else 1,
            label_visibility="collapsed",
        )
        st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.decision == "غير موافق":
        st.session_state.reason = st.text_area("سبب الرفض (إلزامي):", value=st.session_state.reason, key="reason_ar")
    else:
        st.session_state.reason = ""

    submit = st.button("إرسال القرار")

    if submit:
        if st.session_state.decision == "غير موافق" and not st.session_state.reason.strip():
            st.warning("يرجى كتابة سبب الرفض قبل الإرسال.")
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
                    st.success("تم إرسال القرار بنجاح.")
                except Exception as e:
                    st.error(f"تعذر إرسال القرار عبر الويب هوك: {e}")
            else:
                st.info("لم يتم إرسال القرار لعدم توفر رابط ويب هوك صالح.")
