# ==========================================================
# SUPPLYSENSE – FINAL MASTER BUILD (TANCAM READY)
# Real-Time Supply–Demand Balancing Control Tower for MSMEs
# ==========================================================

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px

# ---------- SAFE OPENAI IMPORT ----------
AI_AVAILABLE = True
try:
    from openai import OpenAI
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except:
    AI_AVAILABLE = False

st.set_page_config(layout="wide")

# ==========================================================
# DATABASE CONNECTION (STREAMLIT SAFE SQLITE)
# ==========================================================
@st.cache_resource
def get_conn():
    return sqlite3.connect("/tmp/supplysense.db", check_same_thread=False)

def run_query(q,p=()):
    conn=get_conn()
    cur=conn.cursor()
    cur.execute(q,p)
    conn.commit()
# ==========================================================
# CREATE ENTERPRISE TABLES
# ==========================================================
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
# AUTO DEMO DATA → makes analytics dynamic instantly
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

    # ---- ORDERS ----
    for i in range(120):
        idx=np.random.randint(0,len(items))
        cur.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)",
        (f"O{i}","2025-01-"+str(np.random.randint(1,28)),
         np.random.choice(customers),
         np.random.choice(cities),
         "Retail",items[idx],cats[idx],
         np.random.randint(20,150),
         np.random.randint(20,120),"Normal"))

    # ---- INVENTORY ----
    for w in warehouses:
        for i,item in enumerate(items):
            cur.execute("INSERT INTO inventory VALUES (?,?,?,?,?,?,?,?,?)",
            (item,w,cats[i],np.random.choice(suppliers_list),
             np.random.randint(200,600),np.random.randint(50,200),
             150,150,np.random.randint(10,40)))

    # ---- SUPPLIERS ----
    for s in suppliers_list:
        for item in items:
            cur.execute("INSERT INTO suppliers VALUES (?,?,?,?,?,?,?)",
            (s,item,"India",
             np.random.randint(2,10),
             np.random.randint(100,400),
             round(np.random.uniform(0.7,0.95),2),
             np.random.randint(10,40)))

    conn.commit()

seed_demo_data()
def get_table(name):
    try:
        return pd.read_sql(f"SELECT * FROM {name}",get_conn())
    except:
        return pd.DataFrame()

orders = get_table(f"orders_{persona_key}")
inventory = get_table(f"inventory_{persona_key}")
suppliers = get_table(f"suppliers_{persona_key}")


# ==========================================================
# REAL-TIME SUPPLY DEMAND BALANCING ENGINE
# ==========================================================
# ==========================================================
# 🧠 SAFE SUPPLY–DEMAND BALANCING ENGINE
# ==========================================================
def balancing_engine():

    # copy tables safely
    inventory = get_table(f"inventory_{persona_key}")
    orders = get_table(f"orders_{persona_key}")
    df = inventory.copy()
    ord_df = orders.copy()

    # ------------------------------------------------------
    # 🔥 AUTO CREATE MISSING COLUMNS (PREVENTS ALL KeyErrors)
    # ------------------------------------------------------
    inv_required = {
        "item": "",
        "on_hand": 0,
        "wip": 0,
        "safety": 100
    }

    for col, default in inv_required.items():
        if col not in df.columns:
            df[col] = default

    if "item" not in ord_df.columns:
        ord_df["item"] = ""

    if "qty" not in ord_df.columns:
        ord_df["qty"] = 0

    # ------------------------------------------------------
    # DEMAND CALCULATION
    # ------------------------------------------------------
    demand = ord_df.groupby("item")["qty"].sum().reset_index()
    demand.rename(columns={"qty":"forecast_demand"}, inplace=True)

    df = df.merge(demand, on="item", how="left")
    df["forecast_demand"] = df["forecast_demand"].fillna(0)

    # ------------------------------------------------------
    # STOCK PROJECTION
    # ------------------------------------------------------
    df["available_stock"] = df["on_hand"] + df["wip"]
    df["projected_stock"] = df["available_stock"] - df["forecast_demand"]

    # ------------------------------------------------------
    # ACTION RECOMMENDATION ENGINE
    # ------------------------------------------------------
    actions = []

    for _, r in df.iterrows():

        if r["projected_stock"] < 0:
            actions.append(f"🚨 STOCKOUT risk for {r['item']} → Expedite supplier")

        elif r["projected_stock"] < r["safety"]:
            actions.append(f"⚠️ Low stock {r['item']} → Increase production")

        elif r["projected_stock"] > r["safety"] * 3:
            actions.append(f"📦 Overstock {r['item']} → Run promotion")

        else:
            actions.append(f"✅ {r['item']} Balanced")

    return df, actions


balanced, actions = balancing_engine()

# ==========================================================
# PERSONAS FROM PROBLEM STATEMENT
# ==========================================================
st.sidebar.title("👥 MSME Personas")

persona=st.sidebar.selectbox("Choose Persona",
["Owner Rajesh","Planner Kavitha","Warehouse Arun","Supplier ABC Foods"])
# persona database key
persona_key = {
    "Owner Rajesh":"rajesh",
    "Planner Kavitha":"kavitha",
    "Warehouse Arun":"arun",
    "Supplier ABC Foods":"supplier"
}[persona]


if persona=="Owner Rajesh":
    st.sidebar.info("Concern: Cash flow & missed deliveries")
elif persona=="Planner Kavitha":
    st.sidebar.info("Concern: Rescheduling & firefighting")
elif persona=="Warehouse Arun":
    st.sidebar.info("Concern: Overstock & storage space")
elif persona=="Supplier ABC Foods":
    st.sidebar.info("Concern: Sudden urgent purchase orders")
# ==========================================================
# SAFE CHART BUILDER (no plotly crashes ever)
# ==========================================================
def safe_bar_chart(df,x,y,color=None,title="Chart"):
    try:
        if x not in df.columns: df[x]="Unknown"
        if y not in df.columns: df[y]=0
        if color and color not in df.columns: df[color]="General"
        fig=px.bar(df,x=x,y=y,color=color,title=title)
        st.plotly_chart(fig,use_container_width=True)
    except:
        st.warning("Not enough data to display this chart yet.")
menu=st.sidebar.selectbox("Navigation",
["Control Tower","Analytics","AI Assistant","Upload Data","Manual Entry"])

if menu=="Control Tower":
    st.title("🏭 SupplySense Control Tower")

    c1,c2,c3=st.columns(3)
    c1.metric("Orders",len(orders))
    c2.metric("Inventory Items",len(inventory))
    c3.metric("Alerts",len(actions))

    st.subheader("⚠️ Recommended Actions")
    for a in actions:
        st.warning(a)

    st.subheader("Projected Stock Levels")
    st.dataframe(balanced)
elif menu=="Analytics":
    st.title("📊 Demand & Inventory Insights")

    safe_bar_chart(inventory,"warehouse","on_hand","category","Inventory by Warehouse")

    try:
        fig=px.pie(orders,names="category",values="qty",title="Demand by Category")
        st.plotly_chart(fig,use_container_width=True)
    except:
        st.warning("Upload more order data for category insights.")

    try:
        cust=orders.groupby("customer")["qty"].sum().reset_index()
        safe_bar_chart(cust,"customer","qty",None,"Top Customers")
    except:
        pass

    try:
        suppliers["risk"]=suppliers["lead_time"]*(1-suppliers["reliability"])
        safe_bar_chart(suppliers,"supplier","risk",None,"Supplier Risk")
    except:
        pass
elif menu=="AI Assistant":
    st.title("🤖 Ask SupplySense")

    q = st.text_input("Ask planning question")

    if q:

        # -------- TRY REAL AI FIRST --------
        if AI_AVAILABLE:
            try:
                context = f"""
                Inventory:
                {inventory.head()}

                Orders:
                {orders.head()}

                Supplier lead times:
                {suppliers.head()}
                """

                res = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[
                        {"role":"system","content":"You are a supply chain planning assistant."},
                        {"role":"user","content":context + "\nQuestion: " + q}
                    ]
                )

                st.success(res.choices[0].message.content)

            except Exception:
                st.warning("AI cloud unavailable → switching to built-in planner")
                AI_AVAILABLE_LOCAL = False
        else:
            AI_AVAILABLE_LOCAL = False

        # -------- FALLBACK RULE ENGINE --------
        if not AI_AVAILABLE or 'AI_AVAILABLE_LOCAL' in locals():

            low_stock = balanced[balanced["projected_stock"] < balanced["safety"]]

            st.info("📊 Built-in SupplySense Planner")

            if len(low_stock) > 0:
                for item in low_stock["item"].tolist():
                    st.write(f"• Consider expediting purchase for **{item}**")

            st.write("• Review supplier lead times")
            st.write("• Consider adjusting batch sizes")
            st.write("• Monitor demand spikes weekly")

elif menu=="Upload Data":
    st.title("📤 Upload Excel / CSV")

    table = st.selectbox("Select table", ["orders","inventory","suppliers"])
    file = st.file_uploader("Upload dataset")

    if file:
        # read file
        df = pd.read_excel(file) if file.name.endswith(".xlsx") else pd.read_csv(file)

        # ==================================================
        # 🔥 AUTO COLUMN CLEANER (FINAL BUG FIX)
        # ==================================================
        df.columns = (
            df.columns
            .str.strip()          # remove spaces
            .str.lower()          # lowercase
            .str.replace(" ", "_")# spaces → underscore
            .str.replace("-", "_")
        )

        st.write("Detected columns:", df.columns.tolist())

        conn = get_conn()
        table_name = f"{table}_{persona_key}"
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        st.success(f"Dataset uploaded for {persona}")

        st.success("File uploaded and standardized successfully!")


elif menu=="Manual Entry":
    st.title("➕ Add New Order")
    item=st.text_input("Item")
    qty=st.number_input("Quantity")
    if st.button("Add Order"):
        run_query("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("NEW","2025-01-01","Retailer","Chennai","Retail",
         item,"General",qty,40,"Normal"))
        st.success("Order Added!")
