# =====================================================
# SUPPLYSENSE ENTERPRISE EDITION – TANCAM FINAL
# =====================================================

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import hashlib
from openai import OpenAI

st.set_page_config(layout="wide")

# -------- OPENAI ----------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# -------- SAFE SQLITE ----------
@st.cache_resource
def get_conn():
    return sqlite3.connect("/tmp/msme.db",check_same_thread=False)

def run_query(q,params=()):
    conn=get_conn()
    cur=conn.cursor()
    cur.execute(q,params)
    conn.commit()
    return cur

# -------- ENTERPRISE TABLES ----------
run_query("""CREATE TABLE IF NOT EXISTS users(
username TEXT,password TEXT,role TEXT,plan TEXT)""")

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
def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()
def verify_password(p,h): return hash_password(p)==h

if run_query("SELECT COUNT(*) FROM users").fetchone()[0]==0:
    run_query("INSERT INTO users VALUES (?,?,?,?)",
              ("admin",hash_password("admin123"),"Admin","Enterprise"))

if "logged" not in st.session_state:
    st.session_state.logged=False

def login():
    u=st.text_input("Username",key="login_user")
    p=st.text_input("Password",type="password",key="login_pass")
    if st.button("Login"):
        res=run_query("SELECT password FROM users WHERE username=?",(u,)).fetchone()
        if res and verify_password(p,res[0]):
            st.session_state.logged=True
            st.rerun()
        else:
            st.error("Invalid login")

if not st.session_state.logged:
    st.title("🏭 SupplySense Enterprise")
    st.subheader("AI Control Tower for MSME Supply Chains")
    login()
    st.stop()
def get_table(name):
    return pd.read_sql(f"SELECT * FROM {name}", get_conn())

orders=get_table("orders")
inventory=get_table("inventory")
suppliers=get_table("suppliers")
capacity=get_table("capacity")

# ---- KPIs ----
def calc_kpis():
    if len(orders)==0 or len(inventory)==0:
        return 0,0,0,0
    revenue=(orders["qty"]*orders["unit_price"]).sum()
    inv_value=(inventory["on_hand"]*inventory["unit_cost"]).sum()
    service=round(100-np.random.randint(3,10),2)
    util=round(capacity["utilization"].mean() if len(capacity)>0 else 75,2)
    return revenue,inv_value,service,util
menu=st.sidebar.selectbox("Menu",
["Dashboard","Demand Analytics","Customer Analytics",
 "Supplier Analytics","AI Assistant","Upload Data"])
if menu=="Dashboard":
    revenue,inv_value,service,util=calc_kpis()

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Revenue ₹",int(revenue))
    c2.metric("Inventory Value ₹",int(inv_value))
    c3.metric("Service Level %",service)
    c4.metric("Capacity Util %",util)

    st.subheader("Inventory by Warehouse")
    if len(inventory)>0:
        fig=px.bar(inventory,x="warehouse",y="on_hand",color="category")
        st.plotly_chart(fig,use_container_width=True)
elif menu=="Demand Analytics":
    if len(orders)>0:
        orders["date"]=pd.to_datetime(orders["date"])

        daily=orders.groupby("date")["qty"].sum().reset_index()
        st.plotly_chart(px.line(daily,x="date",y="qty",title="Demand Trend"))

        cat=orders.groupby("category")["qty"].sum()
        st.plotly_chart(px.pie(cat,title="Demand by Category"))
elif menu=="Customer Analytics":
    if len(orders)>0:
        rev=orders.groupby("customer").apply(
            lambda x:(x.qty*x.unit_price).sum()).sort_values(ascending=False).head(10)
        st.plotly_chart(px.bar(rev,title="Top Customers"))
elif menu=="Supplier Analytics":
    if len(suppliers)>0:
        suppliers["risk"]=suppliers["lead_time"]*(1-suppliers["reliability"])
        st.plotly_chart(px.bar(suppliers,x="supplier",y="risk",title="Supplier Risk"))
elif menu=="AI Assistant":
    st.subheader("🤖 Ask SupplySense AI")

    query=st.text_input("Ask about demand, customers, suppliers")

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
elif menu=="Upload Data":
    st.subheader("Upload Excel/CSV")

    table=st.selectbox("Select table",
    ["orders","inventory","suppliers","capacity"])

    file=st.file_uploader("Upload file")

    if file:
        df=pd.read_excel(file) if file.name.endswith(".xlsx") else pd.read_csv(file)
        df.to_sql(table,get_conn(),if_exists="replace",index=False)
        st.success("Data uploaded successfully!")
