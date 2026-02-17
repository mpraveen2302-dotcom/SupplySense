# =====================================================
# SUPPLYSENSE – FINAL TANCAM VERSION
# =====================================================

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import hashlib
from openai import OpenAI

st.set_page_config(layout="wide")

# ---------------- OPENAI ----------------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ---------------- DATABASE ----------------
@st.cache_resource
def get_conn():
    return sqlite3.connect("/tmp/msme.db",check_same_thread=False)

def run_query(q,p=()):
    conn=get_conn()
    cur=conn.cursor()
    cur.execute(q,p)
    conn.commit()
    return cur

# ---------------- TABLES ----------------
run_query("""CREATE TABLE IF NOT EXISTS orders(
order_id TEXT,date TEXT,customer TEXT,city TEXT,channel TEXT,
item TEXT,category TEXT,qty INT,unit_price FLOAT,priority TEXT)""")

run_query("""CREATE TABLE IF NOT EXISTS inventory(
item TEXT,warehouse TEXT,category TEXT,supplier TEXT,
on_hand INT,wip INT,safety INT,reorder_point INT,unit_cost FLOAT)""")

run_query("""CREATE TABLE IF NOT EXISTS suppliers(
supplier TEXT,item TEXT,country TEXT,lead_time INT,
moq INT,reliability FLOAT,cost_per_unit FLOAT)""")

run_query("""CREATE TABLE IF NOT EXISTS capacity(
date TEXT,plant TEXT,shift_hours INT,max_units INT,utilization FLOAT)""")

# ---------------- NORMALIZE OLD DATA ----------------
def normalize_orders(df):
    defaults={"order_id":"ORD001","customer":"Retailer","city":"Chennai",
              "channel":"Retail","category":"General","unit_price":100.0,
              "priority":"Normal"}
    for c,v in defaults.items():
        if c not in df.columns: df[c]=v
    return df

def normalize_inventory(df):
    defaults={"category":"General","supplier":"Default",
              "reorder_point":50,"unit_cost":50.0}
    for c,v in defaults.items():
        if c not in df.columns: df[c]=v
    return df

def get_table(name):
    return pd.read_sql(f"SELECT * FROM {name}",get_conn())

orders=normalize_orders(get_table("orders"))
inventory=normalize_inventory(get_table("inventory"))
suppliers=get_table("suppliers")
capacity=get_table("capacity")

# ---------------- KPIs ----------------
def calc_kpis():
    if len(orders)==0 or len(inventory)==0: return 0,0,0,0
    revenue=(orders["qty"]*orders["unit_price"]).sum()
    inv_value=(inventory["on_hand"]*inventory["unit_cost"]).sum()
    service=round(100-np.random.randint(3,10),2)
    util=round(capacity["utilization"].mean() if len(capacity)>0 else 75,2)
    return revenue,inv_value,service,util

# ---------------- MENU ----------------
menu=st.sidebar.selectbox("Menu",
["Dashboard","Demand Analytics","Customer Analytics",
 "Supplier Analytics","AI Assistant","Upload Data","Manual Entry"])

# ====================================================
# DASHBOARD
# ====================================================
if menu=="Dashboard":
    revenue,inv_value,service,util=calc_kpis()
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Revenue ₹",int(revenue))
    c2.metric("Inventory Value ₹",int(inv_value))
    c3.metric("Service Level %",service)
    c4.metric("Capacity Util %",util)

    if len(inventory)>0:
        st.plotly_chart(px.bar(inventory,x="warehouse",y="on_hand",color="category"))

# ====================================================
# DEMAND ANALYTICS
# ====================================================
elif menu=="Demand Analytics":
    if len(orders)>0:
        orders["date"]=pd.to_datetime(orders["date"])
        daily=orders.groupby("date")["qty"].sum().reset_index()
        st.plotly_chart(px.line(daily,x="date",y="qty"))
        st.plotly_chart(px.pie(orders.groupby("category")["qty"].sum()))

# ====================================================
# CUSTOMER ANALYTICS
# ====================================================
elif menu=="Customer Analytics":
    if len(orders)>0:
        rev=orders.groupby("customer").apply(
            lambda x:(x.qty*x.unit_price).sum()).sort_values(ascending=False).head(10)
        st.plotly_chart(px.bar(rev,title="Top Customers"))

# ====================================================
# SUPPLIER ANALYTICS
# ====================================================
elif menu=="Supplier Analytics":
    if len(suppliers)>0:
        suppliers["risk"]=suppliers["lead_time"]*(1-suppliers["reliability"])
        st.plotly_chart(px.bar(suppliers,x="supplier",y="risk"))

# ====================================================
# REAL AI ASSISTANT
# ====================================================
elif menu=="AI Assistant":
    st.subheader("🤖 Ask SupplySense AI")
    query=st.text_input("Ask supply chain question")
    if query:
        context=f"""
        Orders:
        {orders.head().to_string()}
        Inventory:
        {inventory.head().to_string()}
        Suppliers:
        {suppliers.head().to_string()}
        """
        res=client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role":"system","content":"You are a supply chain AI assistant."},
                {"role":"user","content":context+"\nQuestion:"+query}
            ])
        st.success(res.choices[0].message.content)

# ====================================================
# FILE UPLOAD (CSV / EXCEL)
# ====================================================
elif menu=="Upload Data":
    table=st.selectbox("Table",["orders","inventory","suppliers","capacity"])
    file=st.file_uploader("Upload CSV or Excel",type=["csv","xlsx"])
    if file:
        df=pd.read_excel(file) if file.name.endswith(".xlsx") else pd.read_csv(file)
        df.to_sql(table,get_conn(),if_exists="replace",index=False)
        st.success("Uploaded successfully!")

# ====================================================
# MANUAL DATA ENTRY
# ====================================================
elif menu=="Manual Entry":
    st.subheader("Add Order Manually")
    item=st.text_input("Item")
    qty=st.number_input("Quantity")
    price=st.number_input("Unit Price")
    if st.button("Add Order"):
        run_query("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)",
                  ("ORDNEW","2025-01-01","Retailer","Chennai",
                   "Retail",item,"General",qty,price,"Normal"))
        st.success("Order added!")
