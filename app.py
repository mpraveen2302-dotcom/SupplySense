# =========================================================
# SUPPLYSENSE – ULTIMATE FINAL VERSION
# =========================================================

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import random
import hashlib
import smtplib
import speech_recognition as sr
from email.mime.text import MIMEText
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from twilio.rest import Client

st.set_page_config(layout="wide")

# ---------- STRIPE LINKS ----------
PRO_LINK="https://buy.stripe.com/YOUR_PRO_LINK"
ENT_LINK="https://buy.stripe.com/YOUR_ENTERPRISE_LINK"

# ---------- TWILIO ----------
TWILIO_SID="PUT_SID"
TWILIO_TOKEN="PUT_TOKEN"
TWILIO_WHATSAPP="whatsapp:+14155238886"
USER_WHATSAPP="whatsapp:+91XXXXXXXXXX"

# ---------- EMAIL ----------
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

def init_db():
    c.execute("""CREATE TABLE IF NOT EXISTS users
        (username TEXT,password TEXT,role TEXT,plan TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS orders
        (date TEXT,item TEXT,qty INT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS inventory
        (item TEXT,warehouse TEXT,on_hand INT,wip INT,safety INT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS suppliers
        (item TEXT,lead INT,moq INT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS capacity
        (date TEXT,max_units INT)""")

    safe_commit()

init_db()
# ---------- PASSWORD HASH ----------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password)==hashed

# default users
c.execute("SELECT COUNT(*) FROM users")
if c.fetchone()[0]==0:
    c.execute("INSERT INTO users VALUES (?,?,?,?)",
              ("admin",hash_password("admin123"),"Admin","Enterprise"))
    c.execute("INSERT INTO users VALUES (?,?,?,?)",
              ("planner",hash_password("plan123"),"Planner","Pro"))
    c.execute("INSERT INTO users VALUES (?,?,?,?)",
              ("viewer",hash_password("view123"),"Viewer","Free"))
    safe_commit()

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
    st.title("🏭 SupplySense")
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

    with tab2:
        signup()

if "logged" not in st.session_state:
    st.session_state.logged=False

# ---------- PUBLIC LANDING PAGE ----------
if not st.session_state.logged:
    st.title("🏭 SupplySense")
    st.subheader("AI Control Tower for Small Business Supply Chains")

    st.markdown("### Stop firefighting. Start forecasting.")
    col1,col2,col3=st.columns(3)
    col1.subheader("FREE")
    col2.subheader("PRO ₹499")
    col3.subheader("ENTERPRISE ₹1999")
    col2.link_button("Buy PRO",PRO_LINK)
    col3.link_button("Buy Enterprise",ENT_LINK)

    st.divider()
    login()
    st.stop()
# ---------- ALERTS ----------
def send_alert(msg):
    try:
        Client(TWILIO_SID,TWILIO_TOKEN).messages.create(
            body=msg,from_=TWILIO_WHATSAPP,to=USER_WHATSAPP)
    except: pass

def send_email_alert(msg):
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

def generate_pdf(inv,recs):
    doc=SimpleDocTemplate("/tmp/report.pdf")
    styles=getSampleStyleSheet()
    story=[Paragraph("SupplySense Daily Report",styles["Title"])]
    for r in recs:
        story.append(Paragraph(r,styles["Normal"]))
    doc.build(story)

def voice_query():
    r=sr.Recognizer()
    with sr.Microphone() as source:
        audio=r.listen(source)
    try:
        return r.recognize_google(audio)
    except:
        return "Could not understand"
def get_table(name):
    return pd.read_sql(f"SELECT * FROM {name}",conn)

def forecast_demand(df):
    fc={}
    for item in df["item"].unique():
        avg=df[df["item"]==item]["qty"].mean()
        fc[item]=sum([avg+random.randint(-5,5) for _ in range(14)])
    return fc

def inventory_sim(inv,fc):
    rows=[]
    for _,r in inv.iterrows():
        stock=r["on_hand"]+r["wip"]
        demand=fc.get(r["item"],0)
        rows.append([r["warehouse"],r["item"],stock,demand,stock-demand,r["safety"]])
    return pd.DataFrame(rows,columns=["Warehouse","Item","StartStock","ForecastDemand","EndStock","Safety"])

def supplier_risk(df):
    risks=[]
    for _,r in df.iterrows():
        risk=random.choice(["LOW","MEDIUM","HIGH"])
        risks.append([r["item"],risk])
    return pd.DataFrame(risks,columns=["Item","Risk"])

def actions(inv,risks):
    acts=[]
    for _,r in inv.iterrows():
        if r["EndStock"]<0:
            msg=f"🚨 STOCKOUT {r['Item']}"
            acts.append(msg)
            send_alert(msg)
            send_email_alert(msg)
        elif r["EndStock"]<r["Safety"]:
            qty=int(r["Safety"]*2-r["EndStock"])
            acts.append(f"⚠️ Reorder {qty} units of {r['Item']}")
        elif r["EndStock"]>r["Safety"]*3:
            acts.append(f"📉 Overstock {r['Item']} → Run Discount Campaign")
    return acts
orders=get_table("orders")
inventory=get_table("inventory")
suppliers=get_table("suppliers")
capacity=get_table("capacity")

st.sidebar.success(f"Plan: {st.session_state.plan}")
dark=st.sidebar.toggle("🌙 Dark Mode")

menu=st.sidebar.selectbox("Menu",
["Dashboard","Forecast","Simulator","Supplier Risk",
 "Analytics","Warehouse Map","AI Assistant","Data Entry"])

# DASHBOARD
if menu=="Dashboard":
    if len(orders)>0 and len(inventory)>0:
        fc=forecast_demand(orders)
        inv=inventory_sim(inventory,fc)
        risks=supplier_risk(suppliers)
        recs=actions(inv,risks)

        util=75
        service=round((1-sum(inv["EndStock"]<0)/len(inv))*100,2)
        value=int(inv["StartStock"].sum()*100)

        c1,c2,c3,c4=st.columns(4)
        c1.metric("Capacity %",util)
        c2.metric("Stockouts",sum(inv["EndStock"]<0))
        c3.metric("Inventory Value ₹",value)
        c4.metric("Service Level %",service)

        st.dataframe(inv)
        st.subheader("AI Actions")
        for r in recs: st.write(r)

        generate_pdf(inv,recs)
        with open("/tmp/report.pdf","rb") as f:
            st.download_button("Download Report",f,"report.pdf")

# ANALYTICS
elif menu=="Analytics":
    orders["date"]=pd.to_datetime(orders["date"])
    daily=orders.groupby("date")["qty"].sum().reset_index()
    st.plotly_chart(px.line(daily,x="date",y="qty"))

# MAP
elif menu=="Warehouse Map":
    map_df=pd.DataFrame({
        "lat":[13.08,12.97,19.07,28.70],
        "lon":[80.27,77.59,72.87,77.10]
    })
    st.map(map_df.rename(columns={"lat":"latitude","lon":"longitude"}))

# AI ASSISTANT
elif menu=="AI Assistant":
    query=st.text_input("Ask SupplySense")
    if st.button("Voice Input"):
        query=voice_query()
        st.write(query)
    if query:
        st.success("Check dashboard for insights!")

# DATA ENTRY (UPLOAD)
elif menu=="Data Entry":
    file=st.file_uploader("Upload dataset",type=["csv","xlsx"])
    if file:
        df=pd.read_excel(file) if file.name.endswith(".xlsx") else pd.read_csv(file)
        st.dataframe(df)
