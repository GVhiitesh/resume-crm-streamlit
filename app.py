import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from io import BytesIO
import hashlib

# ================= CONFIG =================
st.set_page_config(page_title="Resume CRM", layout="wide")

# ================= SECURITY ===============
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

# ================= SESSION ================
for k in ["logged_in", "username", "role"]:
    if k not in st.session_state:
        st.session_state[k] = None

# ================= DATABASE ===============
def get_db():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        role TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS resumes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telecall_date TEXT,
        candidate_date TEXT,
        mobile TEXT,
        email TEXT,
        location TEXT,
        source TEXT,
        position_interested TEXT,
        qualification TEXT,
        skills TEXT,
        requirement_type TEXT,
        offer_status TEXT,
        joining_status TEXT,
        registration_fee TEXT,
        amount REAL,
        payment_mode TEXT,
        remarks TEXT,
        next_followup_date TEXT,
        action_notes TEXT,
        created_year INTEGER
    )
    """)

    admin = conn.execute("SELECT * FROM users WHERE username='admin'").fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO users (username,password_hash,role) VALUES (?,?,?)",
            ("admin", hash_password("Admin@123"), "admin")
        )

    conn.commit()
    conn.close()

init_db()

# ================= LOGIN ===================
def login_page():
    st.title("🔐 Resume CRM Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?", (u,)
        ).fetchone()
        conn.close()

        if user and hash_password(p) == user["password_hash"]:
            st.session_state.logged_in = True
            st.session_state.username = user["username"]
            st.session_state.role = user["role"]
            st.rerun()
        else:
            st.error("Invalid credentials")

if not st.session_state.logged_in:
    login_page()
    st.stop()

# ================= SIDEBAR =================
with st.sidebar:
    st.success(f"{st.session_state.username} ({st.session_state.role})")
    if st.button("Logout"):
        for k in ["logged_in", "username", "role"]:
            st.session_state[k] = None
        st.rerun()

# ================= LOAD DATA ===============
conn = get_db()
df = pd.read_sql("SELECT * FROM resumes ORDER BY id DESC", conn)
conn.close()
filtered_df = df.copy()

# ================= DASHBOARD ===============
st.title("📄 Resume Management CRM")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Resumes", len(df))
c2.metric("This Year", df[df["created_year"] == datetime.now().year].shape[0])
c3.metric("Joined", df[df["joining_status"] == "Joined"].shape[0])
c4.metric("Pending", df[df["joining_status"] == "Pending"].shape[0])

# ================= TABS ====================
tabs = ["➕ Add Resume", "📋 View & Export", "✏️ Edit Resume"]
if st.session_state.role == "admin":
    tabs.append("👤 Manage Users")

tab_add, tab_view, tab_edit, *tab_users = st.tabs(tabs)

# ================= ADD RESUME ==============
with tab_add:
    with st.form("add_resume"):
        tc = st.date_input("TeleCall Date")
        cd = st.date_input("Candidate Date")
        mobile = st.text_input("Mobile Number")
        email = st.text_input("Email")
        location = st.text_input("Location")
        source = st.text_input("Source")
        position = st.text_input("Position Interested")
        qualification = st.text_input("Qualification")
        skills = st.text_input("Skills")
        req = st.selectbox("Requirement Type", ["Permanent","Contract","Intern"])
        offer = st.selectbox("Offer Status", ["Pending","Offered","Rejected"])
        join = st.selectbox("Joining Status", ["Pending","Joined","Not Joined"])
        reg = st.selectbox("Registration Fee Collected", ["Yes","No"])
        amount = st.number_input("Amount", min_value=0.0)
        pay = st.text_input("Payment Mode (UPI-9944943240)")
        remarks = st.text_area("Remarks")
        follow = st.date_input("Next Follow-up Date")
        notes = st.text_area("Action Required / Notes")

        save = st.form_submit_button("Save Resume")

    if save:
        conn = get_db()
        conn.execute("""
        INSERT INTO resumes (
            telecall_date,candidate_date,mobile,email,location,source,
            position_interested,qualification,skills,requirement_type,
            offer_status,joining_status,registration_fee,amount,
            payment_mode,remarks,next_followup_date,action_notes,created_year
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            str(tc), str(cd), mobile, email, location, source,
            position, qualification, skills, req,
            offer, join, reg, amount, pay,
            remarks, str(follow), notes, datetime.now().year
        ))
        conn.commit()
        conn.close()
        st.success("Resume added successfully")
        st.rerun()

# ================= VIEW & EXPORT ===========
with tab_view:
    if df.empty:
        st.info("No records found")
    else:
        year = st.selectbox("Filter by Year", ["All"] + sorted(df["created_year"].unique()))
        if year != "All":
            filtered_df = filtered_df[filtered_df["created_year"] == year]

        search = st.text_input("Search (Mobile / Skills / Position)")
        if search:
            filtered_df = filtered_df[
                filtered_df["mobile"].str.contains(search, case=False, na=False) |
                filtered_df["skills"].str.contains(search, case=False, na=False) |
                filtered_df["position_interested"].str.contains(search, case=False, na=False)
            ]

        st.dataframe(filtered_df, use_container_width=True)

        if not filtered_df.empty:
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                filtered_df.to_excel(writer, index=False)
            buf.seek(0)

            st.download_button(
                "⬇️ Export to Excel",
                buf,
                "resumes.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# ================= EDIT RESUME ==============
with tab_edit:
    if df.empty:
        st.info("No records to edit")
    else:
        rid = st.selectbox("Select Resume ID", df["id"].tolist())
        r = df[df["id"] == rid].iloc[0]

        with st.form("edit_form"):
            tc = st.text_input("TeleCall Date", r["telecall_date"])
            cd = st.text_input("Candidate Date", r["candidate_date"])
            mobile = st.text_input("Mobile", r["mobile"])
            email = st.text_input("Email", r["email"])
            location = st.text_input("Location", r["location"])
            source = st.text_input("Source", r["source"])
            position = st.text_input("Position Interested", r["position_interested"])
            qualification = st.text_input("Qualification", r["qualification"])
            skills = st.text_input("Skills", r["skills"])
            req = st.text_input("Requirement Type", r["requirement_type"])
            offer = st.text_input("Offer Status", r["offer_status"])
            join = st.text_input("Joining Status", r["joining_status"])
            reg = st.text_input("Registration Fee", r["registration_fee"])
            amount = st.number_input("Amount", value=float(r["amount"] or 0))
            pay = st.text_input("Payment Mode", r["payment_mode"])
            remarks = st.text_area("Remarks", r["remarks"])
            follow = st.text_input("Next Follow-up Date", r["next_followup_date"])
            notes = st.text_area("Action Required / Notes", r["action_notes"])

            upd = st.form_submit_button("Update Resume")

        if upd:
            conn = get_db()
            conn.execute("""
            UPDATE resumes SET
                telecall_date=?, candidate_date=?, mobile=?, email=?,
                location=?, source=?, position_interested=?, qualification=?,
                skills=?, requirement_type=?, offer_status=?, joining_status=?,
                registration_fee=?, amount=?, payment_mode=?, remarks=?,
                next_followup_date=?, action_notes=?
            WHERE id=?
            """, (
                tc, cd, mobile, email, location, source,
                position, qualification, skills, req,
                offer, join, reg, amount, pay,
                remarks, follow, notes, rid
            ))
            conn.commit()
            conn.close()
            st.success("Resume updated successfully")
            st.rerun()

        if st.session_state.role == "admin":
            if st.button("❌ Delete Resume"):
                conn = get_db()
                conn.execute("DELETE FROM resumes WHERE id=?", (rid,))
                conn.commit()
                conn.close()
                st.warning("Resume deleted")
                st.rerun()

# ================= USERS ===================
if st.session_state.role == "admin":
    with tab_users[0]:
        with st.form("add_user"):
            u = st.text_input("New Username")
            p = st.text_input("Password", type="password")
            r = st.selectbox("Role", ["staff","admin"])
            c = st.form_submit_button("Create User")

        if c:
            conn = get_db()
            try:
                conn.execute(
                    "INSERT INTO users (username,password_hash,role) VALUES (?,?,?)",
                    (u, hash_password(p), r)
                )
                conn.commit()
                st.success("User created")
            except:
                st.error("Username already exists")
            conn.close()
