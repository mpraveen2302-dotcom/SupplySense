# ======================================================
# SUPPLYSENSE – FINAL CLOUD VERSION
# ======================================================

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import random
import hashlib
import smtplib
from email.mime.text import MIMEText
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from twilio.rest import Client

# ---------- SAFE VOICE IMPORT ----------
try:
    import speech_recognition as sr
    VOICE_ENABLED = True
except:
    VOICE_ENABLED = False

st.set_page_config(layout="wide")

# ---------- STRIPE LINKS ----------
PRO_LINK="https://buy.stripe.com/YOUR_PRO_LINK"
ENT_LINK="https://buy.stripe.com/YOUR_ENTERPRISE_LINK"

# ---------- TWILIO (optional) ----------
TWILIO_SID="PUT_SID"
TWILIO_TOKEN="PUT_TOKEN"
TWILIO_WHATSAPP="whatsapp:+14155238886"
USER_WHATSAPP="whatsapp:+91XXXXXXXXXX"

# ---------- EMAIL (optional) ----------
EMAIL_SENDER="yourgmail@gmail.com"
EMAIL_PASSWORD="your_app_password"
EMAIL_RECEIVER="yourgmail@gmail.com"

# ---------- DATABASE ----------
DB_PATH="/tmp/msme.db"
conn=sqlite3.connect(DB_PATH,check_same_thread=False)
c=conn.cursor()

def safe_commit():
    try: conn.commit()
    except: pass

# ---------- DB INIT ----------
c.execute("""CREATE TABLE IF NOT EXISTS users
(username TEXT,password TEXT,role TEXT,plan TEXT)""")

c.execute("""CREATE TABLE IF NOT EXISTS orders
(date TEXT,item TEXT,qty INT)""")

c.execute("""CREATE TABLE IF NOT EXISTS inventory
(item TEXT,warehouse TEXT,on_hand INT,wip INT,safety INT)""")

c.execute("""CREATE TABLE IF NOT EXISTS suppliers
(item TEXT,lead INT,moq INT)""")

safe_commit()

# ---------- DEFAULT USERS ----------
def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()
def verify_password(p,h): return hash_password(p)==h

if c.execute("SELECT COUNT(*) FROM users").fetchone()[0]==0:
    c.execute("INSERT INTO users VALUES (?,?,?,?)",
              ("admin",hash_password("admin123"),"Admin","Enterprise"))
    c.execute("INSERT INTO users VALUES (?,?,?,?)",
              ("planner",hash_password("plan123"),"Planner","Pro"))
    c.execute("INSERT INTO users VALUES (?,?,?,?)",
              ("viewer",hash_password("view123"),"Viewer","Free"))
    safe_commit()

# ---------- ALERT FUNCTIONS ----------
def send_whatsapp(msg):
    try:
        Client(TWILIO_SID,TWILIO_TOKEN).messages.create(
            body=msg,from_=TWILIO_WHATSAPP,to=USER_WHATSAPP)
    except: pass

def send_email(msg):
    try:
        smtp=smtplib.SMTP("smtp.gmail.com",587)
        smtp.starttls()
        smtp.login(EMAIL_SENDER,EMAIL_PASSWORD)
        email=MIMEText(msg)
        email["Subject"]="SupplySense Alert"
        email["From"]=EMAIL_SENDER
        email["To"]=EMAIL_RECEIVER
        smtp.sendmail(EMAIL_SENDER,EMAIL_RECEIVER,email.as_string())
        smtp.quit()
    except: pass

# ---------- PDF REPORT ----------
def generate_pdf(actions):
    doc=SimpleDocTemplate("/tmp/report.pdf")
    styles=getSampleStyleSheet()
    story=[Paragraph("SupplySense Daily Report",styles["Title"])]
    for a in actions:
        story.append(Paragraph(a,styles["Normal"]))
    doc.build(story)

# ---------- VOICE ----------
def voice_query():
    if not VOICE_ENABLED:
        return "Voice disabled on cloud"
    r=sr.Recognizer()
    with sr.Microphone() as source:
        audio=r.listen(source)
    try: return r.recognize_google(audio)
    except: return "Could not understand"

# ---------- LOGIN ----------
if "logged" not in st.session_state:
    st.session_state.logged=False

def signup():
    st.subheader("Create Account")
    u=st.text_input("Username")
    p=st.text_input("Password",type="password")
    role=st.selectbox("Role",["Viewer","Planner"])
    plan=st.selectbox("Plan",["Free","Pro","Enterprise"])
    if st.button("Sign Up"):
        c.execute("INSERT INTO users VALUES (?,?,?,?)",
                  (u,hash_password(p),role,plan))
        safe_commit()
        st.success("Account created")

def login():
    tab1,tab2=st.tabs(["Login","Sign Up"])
    with tab1:
        u=st.text_input("Username")
        p=st.text_input("Password",type="password")
        if st.button("Login"):
            res=c.execute("SELECT password,role,plan FROM users WHERE username=?",(u,)).fetchone()
            if res and verify_password(p,res[0]):
                st.session_state.logged=True
                st.session_state.role=res[1]
                st.session_state.plan=res[2]
                st.rerun()
            else:
                st.error("Invalid login")
    with tab2: signup()

# ---------- LANDING PAGE ----------
if not st.session_state.logged:
    st.title("🏭 SupplySense")
    st.subheader("AI Control Tower for MSME Supply Chains")
    col1,col2,col3=st.columns(3)
    col2.link_button("Buy PRO",PRO_LINK)
    col3.link_button("Buy Enterprise",ENT_LINK)
    login()
    st.stop()

# ---------- LOAD DATA ----------
def get_table(name):
    return pd.read_sql(f"SELECT * FROM {name}",conn)

orders=get_table("orders")
inventory=get_table("inventory")
suppliers=get_table("suppliers")

# ---------- AI ENGINE ----------
def forecast(df):
    fc={}
    for item in df["item"].unique():
        avg=df[df["item"]==item]["qty"].mean()
        fc[item]=avg*14
    return fc

def simulate(inv,fc):
    rows=[]
    for _,r in inv.iterrows():
        stock=r["on_hand"]+r["wip"]
        demand=fc.get(r["item"],0)
        rows.append([r["warehouse"],r["item"],stock,demand,stock-demand,r["safety"]])
    return pd.DataFrame(rows,
        columns=["Warehouse","Item","StartStock","Demand","EndStock","Safety"])

def actions(inv):
    acts=[]
    for _,r in inv.iterrows():
        if r["EndStock"]<0:
            msg=f"🚨 STOCKOUT {r['Item']}"
            acts.append(msg); send_whatsapp(msg); send_email(msg)
        elif r["EndStock"]<r["Safety"]:
            qty=int(r["Safety"]*2-r["EndStock"])
            acts.append(f"⚠️ Reorder {qty} units of {r['Item']}")
        elif r["EndStock"]>r["Safety"]*3:
            acts.append(f"📉 Overstock {r['Item']} → Discount")
    return acts

# ---------- SIDEBAR ----------
st.sidebar.success(f"Plan: {st.session_state.plan}")
menu=st.sidebar.selectbox("Menu",
["Dashboard","Analytics","Warehouse Map","AI Assistant","Data Entry"])

# ---------- DASHBOARD ----------
if menu=="Dashboard":
    if len(orders)>0 and len(inventory)>0:
        fc=forecast(orders)
        inv=simulate(inventory,fc)
        recs=actions(inv)

        st.dataframe(inv)
        st.subheader("AI Recommendations")
        for r in recs: st.write(r)

        generate_pdf(recs)
        with open("/tmp/report.pdf","rb") as f:
            st.download_button("Download Report",f,"report.pdf")

# ---------- ANALYTICS ----------
elif menu=="Analytics":
    orders["date"]=pd.to_datetime(orders["date"])
    daily=orders.groupby("date")["qty"].sum().reset_index()
    st.plotly_chart(px.line(daily,x="date",y="qty"))

# ---------- MAP ----------
elif menu=="Warehouse Map":
    st.map(pd.DataFrame({"lat":[13.08,12.97,19.07],"lon":[80.27,77.59,72.87]})
           .rename(columns={"lat":"latitude","lon":"longitude"}))

# ---------- AI ASSISTANT ----------
elif menu=="AI Assistant":
    q=st.text_input("Ask SupplySense")
    if VOICE_ENABLED and st.button("Voice"):
        q=voice_query()
        st.write(q)
    if q: st.success("Check dashboard insights!")

# ---------- DATA UPLOAD ----------
elif menu=="Data Entry":
    file=st.file_uploader("Upload CSV/Excel",type=["csv","xlsx"])
    if file:
        df=pd.read_excel(file) if file.name.endswith(".xlsx") else pd.read_csv(file)
        st.dataframe(df)
