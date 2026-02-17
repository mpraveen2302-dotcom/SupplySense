# ==========================================================
# SUPPLYSENSE – FINAL TANCAM BUILD
# Real-time Supply–Demand Balancing for MSMEs
# ==========================================================

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px

# ---------- OPTIONAL AI ----------
AI_AVAILABLE = True
try:
    from openai import OpenAI
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except:
    AI_AVAILABLE = False

st.set_page_config(layout="wide")

# ==========================================================
# DATABASE
# ==========================================================
@st.cache_resource
def get_conn():
    return sqlite3.connect("/tmp/supplysense.db",check_same_thread=False)

def run_query(q,p=()):
    conn=get_conn()
    cur=conn.cursor()
    cur.execute(q,p)
    conn.commit()

# ---------- TABLES ----------
run_query("""CREATE TABLE IF NOT EXISTS orders(
order_id TEXT,date TEXT,customer TEXT,city TEXT,channel TEXT,
item TEXT,category TEXT,qty INT,unit_price FLOAT,priority TEXT)""")

run_query("""CREATE TABLE IF NOT EXISTS inventory(
item TEXT,warehouse TEXT,category TEXT,supplier TEXT,
on_hand INT,wip INT,safety INT,reorder_point INT,unit_cost FLOAT)""")

run_query("""CREATE TABLE IF NOT EXISTS suppliers(
supplier TEXT,item TEXT,country TEXT,lead_time INT,
moq INT,reliability FLOAT,cost_per_unit FLOAT)""")

# ==========================================================
# LOAD + NORMALIZE DATA (NEVER CRASH)
# ==========================================================
def get_table(name):
    try: return pd.read_sql(f"SELECT * FROM {name}",get_conn())
    except: return pd.DataFrame()

def normalize(df, defaults):
    if df is None or len(df)==0:
        return pd.DataFrame(defaults,index=[0]).drop(index=0)
    for c,v in defaults.items():
        if c not in df.columns: df[c]=v
    return df

orders = normalize(get_table("orders"),
{"order_id":"ORD001","date":"2025-01-01","customer":"Retailer",
 "city":"Chennai","channel":"Retail","item":"Milk",
 "category":"Dairy","qty":0,"unit_price":40,"priority":"Normal"})

inventory = normalize(get_table("inventory"),
{"item":"Milk","warehouse":"Main","category":"Dairy",
 "supplier":"ABC Foods","on_hand":100,"wip":50,"safety":80,
 "reorder_point":80,"unit_cost":25})

suppliers = normalize(get_table("suppliers"),
{"supplier":"ABC Foods","item":"Milk","country":"India",
 "lead_time":5,"moq":100,"reliability":0.9,"cost_per_unit":25})

# ==========================================================
# REAL-TIME SUPPLY DEMAND BALANCING ENGINE
# ==========================================================
def balancing_engine():
    df = inventory.copy()
    demand = orders.groupby("item")["qty"].sum().reset_index()
    df = df.merge(demand, on="item", how="left").fillna(0)

    df["available_stock"] = df["on_hand"] + df["wip"]
    df["projected_stock"] = df["available_stock"] - df["qty"]

    actions=[]
    for _,r in df.iterrows():
        if r["projected_stock"] < 0:
            actions.append(f"🚨 STOCKOUT risk for {r['item']} → Expedite supplier order")
        elif r["projected_stock"] < r["safety"]:
            actions.append(f"⚠️ Low stock {r['item']} → Increase production batch")
        elif r["projected_stock"] > r["safety"]*3:
            actions.append(f"📦 Overstock {r['item']} → Run discount promotion")

    return df, actions

balanced, actions = balancing_engine()

# ==========================================================
# PERSONAS (PROBLEM STATEMENT CHARACTERS)
# ==========================================================
st.sidebar.title("👥 MSME Personas")

persona = st.sidebar.selectbox("Choose Persona",
["Owner – Rajesh","Planner – Kavitha","Warehouse – Arun","Supplier – ABC Foods"])

if persona=="Owner – Rajesh":
    st.sidebar.info("Concern: Cash tied in stock & missed deliveries")

if persona=="Planner – Kavitha":
    st.sidebar.info("Concern: Constant rescheduling & firefighting")

if persona=="Warehouse – Arun":
    st.sidebar.info("Concern: Overstock & storage space")

if persona=="Supplier – ABC Foods":
    st.sidebar.info("Concern: Sudden urgent purchase orders")

# ==========================================================
# MENU
# ==========================================================
menu = st.sidebar.selectbox("Navigation",
["Control Tower","Analytics","AI Assistant","Upload Data","Manual Entry"])

# ==========================================================
# CONTROL TOWER DASHBOARD
# ==========================================================
if menu=="Control Tower":
    st.title("🏭 SupplySense Control Tower")

    col1,col2,col3 = st.columns(3)
    col1.metric("Items at Risk", len(actions))
    col2.metric("Orders", len(orders))
    col3.metric("Inventory Items", len(inventory))

    st.subheader("⚠️ Recommended Actions")
    for a in actions: st.warning(a)

    st.subheader("Projected Stock Levels")
    st.dataframe(balanced)

# ==========================================================
# ANALYTICS
# ==========================================================
elif menu=="Analytics":
    st.title("📊 Demand & Inventory Insights")

    try:
        st.plotly_chart(px.bar(inventory,x="warehouse",y="on_hand",color="category"))
        st.plotly_chart(px.pie(orders,names="category",values="qty"))
    except:
        st.warning("Upload more diverse data to unlock full analytics")

# ==========================================================
# AI ASSISTANT (SAFE FALLBACK)
# ==========================================================
elif menu=="AI Assistant":
    st.title("🤖 Ask SupplySense")

    q = st.text_input("Ask a planning question")

    if q:
        if AI_AVAILABLE:
            context=f"Inventory:\n{inventory.head()}\nOrders:\n{orders.head()}"
            res=client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role":"user","content":context+"\n"+q}]
            )
            st.success(res.choices[0].message.content)
        else:
            st.info("AI offline → Showing rule-based insight")
            st.write("Based on current data, review low stock & supplier lead times.")

# ==========================================================
# UPLOAD CSV / EXCEL
# ==========================================================
elif menu=="Upload Data":
    table=st.selectbox("Table",["orders","inventory","suppliers"])
    file=st.file_uploader("Upload CSV/Excel",type=["csv","xlsx"])
    if file:
        df=pd.read_excel(file) if file.name.endswith(".xlsx") else pd.read_csv(file)
        df.to_sql(table,get_conn(),if_exists="replace",index=False)
        st.success("Uploaded!")

# ==========================================================
# MANUAL ENTRY
# ==========================================================
elif menu=="Manual Entry":
    st.title("➕ Add New Order")
    item=st.text_input("Item")
    qty=st.number_input("Quantity")
    if st.button("Add Order"):
        run_query("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("ORDNEW","2025-01-01","Retailer","Chennai","Retail",
         item,"General",qty,40,"Normal"))
        st.success("Order Added!")
