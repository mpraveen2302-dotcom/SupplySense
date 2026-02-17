# ==========================================================
# SUPPLYSENSE – FINAL TANCAM VERSION (FULL SYSTEM)
# Real-time Supply–Demand Balancing for MSMEs
# ==========================================================

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px

# ---------- SAFE AI IMPORT ----------
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
# AUTO DEMO DATA (FOR LIVE ANALYTICS)
# ==========================================================
def seed_demo_data():
    conn=get_conn()
    cur=conn.cursor()
    if cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0] > 0:
        return

    items=["Milk","Bread","Eggs","Juice","Rice","Sugar","Biscuits","Oil"]
    cats=["Dairy","Bakery","Dairy","Beverage","Grocery","Grocery","Snacks","Grocery"]
    customers=["Retailer A","Hotel B","Online C","Supermarket D"]
    cities=["Chennai","Madurai","Coimbatore","Salem"]
    warehouses=["Chennai Hub","Madurai Hub","Coimbatore Hub"]
    suppliers_list=["ABC Foods","Fresh Farms","Dairy Best"]

    for i in range(120):
        idx=np.random.randint(0,len(items))
        cur.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)",
        (f"O{i}","2025-01-"+str(np.random.randint(1,28)),
         np.random.choice(customers),
         np.random.choice(cities),
         "Retail",items[idx],cats[idx],
         np.random.randint(20,150),
         np.random.randint(20,120),"Normal"))

    for w in warehouses:
        for i,item in enumerate(items):
            cur.execute("INSERT INTO inventory VALUES (?,?,?,?,?,?,?,?,?)",
            (item,w,cats[i],np.random.choice(suppliers_list),
             np.random.randint(200,600),np.random.randint(50,200),
             150,150,np.random.randint(10,40)))

    for s in suppliers_list:
        for item in items:
            cur.execute("INSERT INTO suppliers VALUES (?,?,?,?,?,?,?)",
            (s,item,"India",np.random.randint(2,10),
             np.random.randint(100,400),
             round(np.random.uniform(0.7,0.95),2),
             np.random.randint(10,40)))

    conn.commit()

seed_demo_data()

# ==========================================================
# LOAD DATA
# ==========================================================
def get_table(name):
    try: return pd.read_sql(f"SELECT * FROM {name}",get_conn())
    except: return pd.DataFrame()

orders=get_table("orders")
inventory=get_table("inventory")
suppliers=get_table("suppliers")

# ==========================================================
# REAL-TIME BALANCING ENGINE
# ==========================================================
def balancing_engine():
    df=inventory.copy()
    demand=orders.groupby("item")["qty"].sum().reset_index()
    df=df.merge(demand,on="item",how="left").fillna(0)
    df["available_stock"]=df["on_hand"]+df["wip"]
    df["projected_stock"]=df["available_stock"]-df["qty"]

    actions=[]
    for _,r in df.iterrows():
        if r["projected_stock"]<0:
            actions.append(f"🚨 STOCKOUT risk for {r['item']} → Expedite supplier")
        elif r["projected_stock"]<r["safety"]:
            actions.append(f"⚠️ Low stock {r['item']} → Increase production")
        elif r["projected_stock"]>r["safety"]*3:
            actions.append(f"📦 Overstock {r['item']} → Run promotion")

    return df,actions

balanced,actions=balancing_engine()

# ==========================================================
# PERSONAS (CHARACTERS FROM PROBLEM STATEMENT)
# ==========================================================
st.sidebar.title("👥 MSME Personas")
persona=st.sidebar.selectbox("Choose Persona",
["Owner Rajesh","Planner Kavitha","Warehouse Arun","Supplier ABC Foods"])

if persona=="Owner Rajesh":
    st.sidebar.info("Wants fewer stockouts & better cash flow")
elif persona=="Planner Kavitha":
    st.sidebar.info("Needs faster planning & fewer reschedules")
elif persona=="Warehouse Arun":
    st.sidebar.info("Needs to avoid overstock & space issues")
elif persona=="Supplier ABC Foods":
    st.sidebar.info("Needs predictable purchase orders")

# ==========================================================
# MENU
# ==========================================================
menu=st.sidebar.selectbox("Navigation",
["Control Tower","Analytics","AI Assistant","Upload Data","Manual Entry"])

# ==========================================================
# CONTROL TOWER
# ==========================================================
if menu=="Control Tower":
    st.title("🏭 SupplySense Control Tower")

    col1,col2,col3=st.columns(3)
    col1.metric("Orders",len(orders))
    col2.metric("Inventory Items",len(inventory))
    col3.metric("Alerts",len(actions))

    st.subheader("⚠️ AI Recommendations")
    for a in actions: st.warning(a)

    st.subheader("Projected Stock")
    st.dataframe(balanced)

# ==========================================================
# ANALYTICS
# ==========================================================
elif menu=="Analytics":
    st.title("📊 Demand & Inventory Insights")

    st.plotly_chart(px.bar(inventory,x="warehouse",y="on_hand",color="category"))
    st.plotly_chart(px.pie(orders,names="category",values="qty"))
    st.plotly_chart(px.bar(orders.groupby("customer")["qty"].sum().reset_index(),
                           x="customer",y="qty",title="Top Customers"))
    suppliers["risk"]=suppliers["lead_time"]*(1-suppliers["reliability"])
    st.plotly_chart(px.bar(suppliers,x="supplier",y="risk",title="Supplier Risk"))

# ==========================================================
# AI ASSISTANT (SAFE)
# ==========================================================
elif menu=="AI Assistant":
    st.title("🤖 Ask SupplySense")
    q=st.text_input("Ask planning question")

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
            st.write("Review stockouts & supplier lead times.")

# ==========================================================
# UPLOAD
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
    st.title("➕ Add Order")
    item=st.text_input("Item")
    qty=st.number_input("Quantity")
    if st.button("Add Order"):
        run_query("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("NEW","2025-01-01","Retailer","Chennai","Retail",
         item,"General",qty,40,"Normal"))
        st.success("Order Added!")
