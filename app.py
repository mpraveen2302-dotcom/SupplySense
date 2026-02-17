# =====================================================
# SUPPLYSENSE – MASTER FINAL BUILD (TANCAM READY)
# =====================================================

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
from openai import OpenAI

# ---------- OPTIONAL VOICE ----------
try:
    import speech_recognition as sr
    VOICE_ENABLED=True
except:
    VOICE_ENABLED=False

st.set_page_config(layout="wide")

# ---------- OPENAI ----------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ---------- STRIPE LINKS ----------
PRO_LINK="https://buy.stripe.com/YOUR_PRO_LINK"
ENT_LINK="https://buy.stripe.com/YOUR_ENTERPRISE_LINK"

# ---------- SAFE SQLITE ----------
@st.cache_resource
def get_conn():
    return sqlite3.connect("/tmp/msme.db",check_same_thread=False)

def run_query(query, params=()):
    conn=get_conn()
    cur=conn.cursor()
    cur.execute(query, params)
    conn.commit()
    return cur

# ---------- CREATE TABLES ----------
run_query("CREATE TABLE IF NOT EXISTS users(username TEXT,password TEXT,role TEXT,plan TEXT)")
run_query("CREATE TABLE IF NOT EXISTS orders(date TEXT,item TEXT,qty INT)")
run_query("CREATE TABLE IF NOT EXISTS inventory(item TEXT,warehouse TEXT,on_hand INT,wip INT,safety INT)")
run_query("CREATE TABLE IF NOT EXISTS suppliers(item TEXT,lead INT,moq INT)")

# ---------- PASSWORD HASH ----------
def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()
def verify_password(p,h): return hash_password(p)==h

# ---------- DEFAULT USERS ----------
if run_query("SELECT COUNT(*) FROM users").fetchone()[0]==0:
    run_query("INSERT INTO users VALUES (?,?,?,?)",("admin",hash_password("admin123"),"Admin","Enterprise"))
    run_query("INSERT INTO users VALUES (?,?,?,?)",("planner",hash_password("plan123"),"Planner","Pro"))
    run_query("INSERT INTO users VALUES (?,?,?,?)",("viewer",hash_password("view123"),"Viewer","Free"))

# ---------- ALERTS ----------
def send_whatsapp(msg):
    try:
        Client(st.secrets["TWILIO_SID"],st.secrets["TWILIO_TOKEN"]).messages.create(
            body=msg,from_=st.secrets["TWILIO_FROM"],to=st.secrets["USER_WHATSAPP"])
    except: pass

def send_email(msg):
    try:
        smtp=smtplib.SMTP("smtp.gmail.com",587)
        smtp.starttls()
        smtp.login(st.secrets["EMAIL"],st.secrets["EMAIL_PASS"])
        email=MIMEText(msg)
        email["Subject"]="SupplySense Alert"
        email["From"]=st.secrets["EMAIL"]
        email["To"]=st.secrets["EMAIL"]
        smtp.sendmail(st.secrets["EMAIL"],st.secrets["EMAIL"],email.as_string())
        smtp.quit()
    except: pass

# ---------- PDF ----------
def generate_pdf(actions):
    doc=SimpleDocTemplate("/tmp/report.pdf")
    styles=getSampleStyleSheet()
    story=[Paragraph("SupplySense Daily Report",styles["Title"])]
    for a in actions: story.append(Paragraph(a,styles["Normal"]))
    doc.build(story)

# ---------- VOICE ----------
def voice_query():
    if not VOICE_ENABLED: return "Voice disabled on cloud"
    r=sr.Recognizer()
    with sr.Microphone() as source: audio=r.listen(source)
    try: return r.recognize_google(audio)
    except: return "Could not understand"

# ---------- AUTH ----------
if "logged" not in st.session_state: st.session_state.logged=False

def signup():
    st.subheader("Create Account")
    u=st.text_input("Username",key="su_user")
    p=st.text_input("Password",type="password",key="su_pass")
    role=st.selectbox("Role",["Viewer","Planner"],key="su_role")
    plan=st.selectbox("Plan",["Free","Pro","Enterprise"],key="su_plan")
    if st.button("Sign Up",key="su_btn"):
        run_query("INSERT INTO users VALUES (?,?,?,?)",(u,hash_password(p),role,plan))
        st.success("Account created")

def login():
    tab1,tab2=st.tabs(["Login","Sign Up"])
    with tab1:
        u=st.text_input("Username",key="li_user")
        p=st.text_input("Password",type="password",key="li_pass")
        if st.button("Login",key="li_btn"):
            res=run_query("SELECT password,role,plan FROM users WHERE username=?",(u,)).fetchone()
            if res and verify_password(p,res[0]):
                st.session_state.logged=True
                st.session_state.role=res[1]
                st.session_state.plan=res[2]
                st.rerun()
            else: st.error("Invalid login")
    with tab2: signup()

# ---------- LANDING ----------
if not st.session_state.logged:
    st.title("🏭 SupplySense")
    st.subheader("AI Control Tower for MSME Supply Chains")
    st.link_button("Buy PRO",PRO_LINK)
    st.link_button("Buy Enterprise",ENT_LINK)
    login()
    st.stop()

# ---------- LOAD TABLES ----------
def get_table(name):
    return pd.read_sql(f"SELECT * FROM {name}", get_conn())

orders=get_table("orders")
inventory=get_table("inventory")

# ---------- AI ENGINE ----------
def forecast(df):
    fc={}
    for item in df["item"].unique():
        fc[item]=df[df["item"]==item]["qty"].mean()*14
    return fc

def simulate(inv,fc):
    rows=[]
    for _,r in inv.iterrows():
        stock=r["on_hand"]+r["wip"]
        demand=fc.get(r["item"],0)
        rows.append([r["warehouse"],r["item"],stock,demand,stock-demand,r["safety"]])
    return pd.DataFrame(rows,columns=["Warehouse","Item","StartStock","Demand","EndStock","Safety"])

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

# ---------- MENU ----------
menu=st.sidebar.selectbox("Menu",["Dashboard","Analytics","Warehouse Map","AI Assistant","Data Entry"])

# ---------- DASHBOARD ----------
if menu=="Dashboard" and len(orders)>0 and len(inventory)>0:
    fc=forecast(orders)
    inv=simulate(inventory,fc)
    recs=actions(inv)
    st.dataframe(inv)
    for r in recs: st.write(r)
    generate_pdf(recs)
    with open("/tmp/report.pdf","rb") as f:
        st.download_button("Download Report",f,"report.pdf")

# ---------- ANALYTICS ----------
elif menu=="Analytics" and len(orders)>0:
    orders["date"]=pd.to_datetime(orders["date"])
    daily=orders.groupby("date")["qty"].sum().reset_index()
    st.plotly_chart(px.line(daily,x="date",y="qty"))

# ---------- MAP ----------
elif menu=="Warehouse Map":
    st.map(pd.DataFrame({"lat":[13.08,12.97,19.07],"lon":[80.27,77.59,72.87]}).rename(columns={"lat":"latitude","lon":"longitude"}))

# ---------- REAL CHATGPT ----------
elif menu=="AI Assistant":
    st.subheader("Ask SupplySense AI")
    query=st.text_input("Ask about inventory or demand")

    if VOICE_ENABLED and st.button("Voice"):
        query=voice_query()
        st.write(query)

    if query:
        context=f"""
        Inventory:
        {inventory.head().to_string()}

        Orders:
        {orders.head().to_string()}
        """

        response=client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role":"system","content":"You are a supply chain AI assistant."},
                {"role":"user","content":context+"\nUser question:"+query}
            ]
        )
        st.success(response.choices[0].message.content)

# ---------- DATA UPLOAD ----------
elif menu=="Data Entry":
    file=st.file_uploader("Upload CSV/Excel",type=["csv","xlsx"])
    if file:
        df=pd.read_excel(file) if file.name.endswith(".xlsx") else pd.read_csv(file)
        st.dataframe(df)
