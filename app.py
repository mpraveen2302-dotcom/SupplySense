# =========================================================
# SUPPLYSENSE – MSME SUPPLY DEMAND CONTROL TOWER (FINAL)
# =========================================================

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import random
from twilio.rest import Client

st.set_page_config(layout="wide")

# ================= MOBILE RESPONSIVE =================
st.markdown("""
<style>
.block-container {padding-top:1rem;}
h1,h2,h3 {text-align:center;}
.stMetric {text-align:center;}
@media (max-width:768px){.stColumns{flex-direction:column;}}
</style>
""", unsafe_allow_html=True)

# ================= DATABASE (CLOUD SAFE) =================
DB_PATH="/tmp/msme.db"
conn=sqlite3.connect(DB_PATH,check_same_thread=False)
c=conn.cursor()

def safe_commit():
    try: conn.commit()
    except: pass

def init_db():
    c.execute("CREATE TABLE IF NOT EXISTS users (username TEXT,password TEXT,role TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS orders (date TEXT,item TEXT,qty INT)")
    c.execute("CREATE TABLE IF NOT EXISTS inventory (item TEXT,on_hand INT,wip INT,safety INT)")
    c.execute("CREATE TABLE IF NOT EXISTS suppliers (item TEXT,lead INT,moq INT)")
    c.execute("CREATE TABLE IF NOT EXISTS capacity (date TEXT,max_units INT)")
    safe_commit()
init_db()

# default users
c.execute("SELECT COUNT(*) FROM users")
if c.fetchone()[0]==0:
    c.execute("INSERT INTO users VALUES ('admin','admin123','Admin')")
    c.execute("INSERT INTO users VALUES ('planner','plan123','Planner')")
    c.execute("INSERT INTO users VALUES ('viewer','view123','Viewer')")
    safe_commit()

# ================= WHATSAPP ALERTS =================
TWILIO_SID="PUT_SID"
TWILIO_TOKEN="PUT_TOKEN"
TWILIO_WHATSAPP="whatsapp:+14155238886"
USER_WHATSAPP="whatsapp:+91XXXXXXXXXX"

def send_alert(msg):
    try:
        Client(TWILIO_SID,TWILIO_TOKEN).messages.create(body=msg,from_=TWILIO_WHATSAPP,to=USER_WHATSAPP)
    except: pass

# ================= LOGIN =================
def login():
    st.title("🔐 SupplySense Login")
    u=st.text_input("Username")
    p=st.text_input("Password",type="password")
    if st.button("Login"):
        res=c.execute("SELECT role FROM users WHERE username=? AND password=?",(u,p)).fetchone()
        if res:
            st.session_state.logged=True
            st.session_state.role=res[0]
            st.rerun()
        else: st.error("Invalid login")

if "logged" not in st.session_state: st.session_state.logged=False
if not st.session_state.logged:
    login(); st.stop()

role=st.session_state.role

# ================= HELPERS =================
def get_table(name): return pd.read_sql(f"SELECT * FROM {name}",conn)

def forecast_demand(df):
    fc={}
    for item in df.item.unique():
        avg=df[df.item==item].qty.mean()
        fc[item]=sum([avg+random.randint(-5,5) for _ in range(14)])
    return fc

def inventory_sim(inv,fc):
    rows=[]
    for _,r in inv.iterrows():
        stock=r.on_hand+r.wip
        demand=fc.get(r.item,0)
        rows.append([r.item,stock,demand,stock-demand,r.safety])
    return pd.DataFrame(rows,columns=["Item","StartStock","ForecastDemand","EndStock","Safety"])

def capacity_util(cap,fc): return round((sum(fc.values())/cap.max_units.sum())*100,2)

def supplier_risk(df):
    return pd.DataFrame([[r.item,"HIGH" if random.random()>0.7 else "MEDIUM" if random.random()>0.4 else "LOW"]
        for _,r in df.iterrows()],columns=["Item","Risk"])

def actions(inv,risks):
    acts=[]
    for _,r in inv.iterrows():
        if r.EndStock<0: msg=f"🚨 STOCKOUT {r.Item}"; acts.append(msg); send_alert(msg)
        elif r.EndStock<r.Safety: acts.append(f"⚠️ Reorder {r.Item}")
        elif r.EndStock>r.Safety*3: acts.append(f"📉 Overstock {r.Item}")
    for _,r in risks.iterrows():
        if r.Risk=="HIGH": acts.append(f"⛔ Supplier risk {r.Item}")
    return acts

# ================= MENU BY ROLE =================
if role=="Admin":
    menu=st.sidebar.selectbox("Menu",["Dashboard","Forecast","Simulator","Supplier Risk","Data Entry"])
elif role=="Planner":
    menu=st.sidebar.selectbox("Menu",["Dashboard","Forecast","Simulator","Data Entry"])
else:
    menu=st.sidebar.selectbox("Menu",["Dashboard","Forecast"])

orders=get_table("orders")
inventory=get_table("inventory")
suppliers=get_table("suppliers")
capacity=get_table("capacity")

st.title("🏭 SupplySense Control Tower")

# ================= DASHBOARD =================
if menu=="Dashboard":
    if len(orders)>0 and len(inventory)>0 and len(capacity)>0:
        fc=forecast_demand(orders)
        inv=inventory_sim(inventory,fc)
        util=capacity_util(capacity,fc)
        risks=supplier_risk(suppliers)
        recs=actions(inv,risks)

        c1,c2,c3=st.columns(3)
        c1.metric("Capacity Util %",util)
        c2.metric("Stockout Items",sum(inv.EndStock<0))
        c3.metric("Recommendations",len(recs))

        st.dataframe(inv,use_container_width=True)
        st.subheader("AI Actions")
        for r in recs: st.write(r)

# ================= FORECAST =================
elif menu=="Forecast":
    fc=forecast_demand(orders)
    df=pd.DataFrame(fc.items(),columns=["Item","Forecast"])
    st.plotly_chart(px.bar(df,x="Item",y="Forecast"),use_container_width=True)

# ================= SIMULATOR =================
elif menu=="Simulator":
    spike=st.slider("Demand Spike %",0,200,30)
    if st.button("Run Simulation"):
        fc=forecast_demand(orders)
        fc={k:v*(1+spike/100) for k,v in fc.items()}
        st.dataframe(inventory_sim(inventory,fc))

# ================= SUPPLIER RISK =================
elif menu=="Supplier Risk":
    risks=supplier_risk(suppliers)
    for _,r in risks.iterrows():
        st.error(r.Item) if r.Risk=="HIGH" else st.warning(r.Item) if r.Risk=="MEDIUM" else st.success(r.Item)

# ================= DATA ENTRY (UPLOAD + MANUAL) =================
elif menu=="Data Entry":
    st.header("📥 Data Entry & Bulk Upload")

    upload_tab,manual_tab=st.tabs(["Upload CSV/Excel","Manual Entry"])

    with upload_tab:
        dtype=st.selectbox("Dataset",["Orders","Inventory","Suppliers","Capacity"])
        file=st.file_uploader("Upload CSV/Excel",type=["csv","xlsx"])
        if file:
            df=pd.read_excel(file) if file.name.endswith(".xlsx") else pd.read_csv(file)
            st.dataframe(df)
            if st.button("Upload to DB"):
                df.to_sql(dtype.lower(),conn,if_exists="append",index=False)
                safe_commit()
                st.success("Uploaded successfully")

    with manual_tab:
        tab1,tab2,tab3,tab4=st.tabs(["Orders","Inventory","Suppliers","Capacity"])
        with tab1:
            d=st.date_input("Date");item=st.text_input("Item");qty=st.number_input("Qty",0)
            if st.button("Add Order"):
                c.execute("INSERT INTO orders VALUES (?,?,?)",(d,item,qty));safe_commit();st.success("Added")
        with tab2:
            item=st.text_input("Item ");on=st.number_input("On hand");wip=st.number_input("WIP");ss=st.number_input("Safety")
            if st.button("Add Inventory"):
                c.execute("INSERT INTO inventory VALUES (?,?,?,?)",(item,on,wip,ss));safe_commit();st.success("Added")
        with tab3:
            item=st.text_input("Supplier Item");lead=st.number_input("Lead");moq=st.number_input("MOQ")
            if st.button("Add Supplier"):
                c.execute("INSERT INTO suppliers VALUES (?,?,?)",(item,lead,moq));safe_commit();st.success("Added")
        with tab4:
            d=st.date_input("Capacity Date");cap=st.number_input("Max Units")
            if st.button("Add Capacity"):
                c.execute("INSERT INTO capacity VALUES (?,?)",(d,cap));safe_commit();st.success("Added")
