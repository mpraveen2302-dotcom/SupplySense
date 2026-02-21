
# ==========================================================
# SUPPLYSENSE – FINAL MASTER BUILD (TANCAM READY)
# Real-Time Supply–Demand Balancing Control Tower for MSMEs
# MULTI-TENANT + AI + ANALYTICS + WHATSAPP + FORECASTING
# ==========================================================

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import datetime

st.set_page_config(layout="wide")
st.cache_data.clear()
st.cache_resource.clear()
# ⏱ refresh indicator
st.sidebar.write("⏱ Last updated:", datetime.datetime.now().strftime("%H:%M:%S"))

# ---------- SAFE OPENAI IMPORT ----------
AI_AVAILABLE = True
try:
    from openai import OpenAI
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except:
    AI_AVAILABLE = False

# ==========================================================
# DATABASE CONNECTION (STABLE VERSION)
# ==========================================================

def get_conn():
    return sqlite3.connect("supplysense.db", check_same_thread=False)

def run_query(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    conn.close()

def get_table(name):
    conn = get_conn()
    try:
        df = pd.read_sql(f"SELECT * FROM {name}", conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df


# ==========================================================
# CREATE BASE TABLES
# ==========================================================

# ==========================================================
# NEW TABLE → PLANNING PARAMETERS (PER PERSONA)
# ==========================================================
run_query("""
CREATE TABLE IF NOT EXISTS planning_params(
persona TEXT,
safety_stock INT,
lead_time INT,
moq INT
)
""")
run_query("""
CREATE TABLE IF NOT EXISTS action_log(
action TEXT,
item TEXT,
decision TEXT,
timestamp TEXT
)
""")
# ==========================================================
# 🆕 ENTERPRISE TABLES (ADD BELOW planning_params)
# ==========================================================

run_query("""
CREATE TABLE IF NOT EXISTS order_status(
order_id TEXT,
status TEXT,
last_update TEXT
)
""")

run_query("""
CREATE TABLE IF NOT EXISTS customers(
customer TEXT,
phone TEXT,
email TEXT,
last_followup TEXT
)
""")

run_query("""
CREATE TABLE IF NOT EXISTS invoices(
invoice_id TEXT,
customer TEXT,
amount FLOAT,
status TEXT
)
""")

run_query("""
CREATE TABLE IF NOT EXISTS tasks(
task TEXT,
assignee TEXT,
status TEXT
)
""")
run_query("""
CREATE TABLE IF NOT EXISTS supply_pool(
source TEXT,
item TEXT,
available_qty INT,
contact TEXT,
whatsapp TEXT,
email TEXT
)
""")


# ==========================================================
# 🔁 PRODUCT SUBSTITUTION MATRIX (NEW FEATURE)
# ==========================================================
SUBSTITUTIONS = {
    "Milk": ["Milk Powder","Almond Milk"],
    "Bread": ["Buns","Rusk"],
    "Eggs": ["Paneer","Tofu"],
    "Rice": ["Wheat","Millets"],
    "Sugar": ["Jaggery","Honey"],
    "Oil": ["Butter","Ghee"]
}


# ==========================================================
# PERSONA SELECTOR
# ==========================================================
st.sidebar.title("👥 MSME Personas")

persona = st.sidebar.selectbox(
    "Choose Workspace",
    ["Owner Rajesh","Planner Kavitha","Warehouse Arun","Supplier ABC Foods"]
)

persona_key = {
    "Owner Rajesh":"rajesh",
    "Planner Kavitha":"kavitha",
    "Warehouse Arun":"arun",
    "Supplier ABC Foods":"supplier"
}[persona]

PERSONA_CONTEXT = {
    "Owner Rajesh": {
        "concern": "Profit & cash flow risk",
        "why": "Missed deliveries reduce revenue. Overstock blocks working capital."
    },
    "Planner Kavitha": {
        "concern": "Demand vs Production mismatch",
        "why": "Sudden demand spikes force rescheduling and overtime."
    },
    "Warehouse Arun": {
        "concern": "Space & expiry risk",
        "why": "Excess stock increases storage cost and wastage risk."
    },
    "Supplier ABC Foods": {
        "concern": "Unpredictable purchase orders",
        "why": "Last-minute orders disrupt procurement planning."
    }
}

st.sidebar.info(
    f"🎯 Concern: {PERSONA_CONTEXT[persona]['concern']}\n\n"
    f"💡 Why: {PERSONA_CONTEXT[persona]['why']}"
)


# ==========================================================
# TABLE LOADER
# ==========================================================
def get_table(name):
    try:
        return pd.read_sql(f"SELECT * FROM {name}",get_conn())
    except:
        return pd.DataFrame()

orders     = get_table("orders")
inventory  = get_table("inventory")
suppliers  = get_table("suppliers")

def load_capacity():
    try:
        return pd.read_sql("SELECT * FROM capacity", get_conn())
    except:
        return pd.DataFrame(columns=[
            "warehouse","machine","daily_capacity","shift_hours","utilization"
        ])


# ==========================================================
# LOAD PLANNING PARAMETERS (PER PERSONA)
# ==========================================================
def load_params():
    try:
        df = pd.read_sql(
            f"SELECT * FROM planning_params WHERE persona='{persona_key}'",
            get_conn()
        )
        if len(df) > 0:
            return df.iloc[0]
    except:
        pass

    # Default values if nothing saved yet
    return {"safety_stock":150, "lead_time":5, "moq":200}


# ==========================================================
# 🧠 REAL-TIME SUPPLY–DEMAND BALANCING ENGINE (FIXED)
# ==========================================================
def balancing_engine():

    df = inventory.copy()
    ord_df = orders.copy()
    params = load_params()
    DEFAULT_SAFETY = params["safety_stock"]


    # Ensure required columns exist
    if "item" not in df.columns:
        df["item"] = ""
    if "on_hand" not in df.columns:
        df["on_hand"] = 0
    if "wip" not in df.columns:
        df["wip"] = 0
    if "safety" not in df.columns:
        df["safety"] = DEFAULT_SAFETY

    if "item" not in ord_df.columns:
        ord_df["item"] = ""
    if "qty" not in ord_df.columns:
        ord_df["qty"] = 0

    # Demand aggregation
    demand = ord_df.groupby("item")["qty"].sum().reset_index()
    demand.rename(columns={"qty": "forecast_demand"}, inplace=True)

    # Merge demand with inventory
    df = df.merge(demand, on="item", how="left")
    df["forecast_demand"] = df["forecast_demand"].fillna(0)

    # Stock projection
    df["available_stock"] = df["on_hand"] + df["wip"]
    df["projected_stock"] = df["available_stock"] - df["forecast_demand"]

    # Recommendation engine
    actions = []

    for _, r in df.iterrows():


        if r["projected_stock"] < 0:
            actions.append(("🚨 Expedite Supplier", r["item"]))
                        # 🔁 Suggest substitute products (NEW)
            if r["item"] in SUBSTITUTIONS:
                alt = ", ".join(SUBSTITUTIONS[r["item"]])
                actions.append((f"🔁 Offer Substitutes: {alt}", r["item"]))

                # 🔄 Production sequence change (NEW)
        elif r["forecast_demand"] > r["available_stock"] * 1.2:
            actions.append(("🔀 Change Production Sequence", r["item"]))


        elif r["projected_stock"] < r["safety"]:
            actions.append(("⚠️ Increase Production", r["item"]))
            actions.append(("📦 Pull Purchase Order Earlier", r["item"]))

        elif r["projected_stock"] > r["safety"] * 5:
            actions.append(("🛑 Reduce Batch Size", r["item"]))

        elif r["projected_stock"] > r["safety"] * 3:
            actions.append(("⏳ Push Purchase Order Later", r["item"]))
            actions.append(("📦 Run Promotion", r["item"]))

        elif r["projected_stock"] < r["safety"] * 0.5:
            actions.append(("🔄 Reallocate Inventory", r["item"]))

        else:
            actions.append(("✅ Balanced", r["item"]))

    return df, actions


# RUN ENGINE
balanced, actions = balancing_engine()
def fulfilment_engine(item, demand_qty):

    if len(inventory)==0:
        return [], demand_qty

    if "item" not in inventory.columns:
        return [], demand_qty

    if "on_hand" not in inventory.columns:
        return [], demand_qty

    inv = inventory[inventory["item"]==item]
    own_stock = int(inv["on_hand"].sum()) if len(inv)>0 else 0


    remaining = demand_qty - own_stock
    plan = []

    if own_stock > 0:
        plan.append(("🏭 Own Warehouse", own_stock, "Internal stock"))

    if remaining <= 0:
        return plan, 0

    pool = get_table("supply_pool")
    pool = pool[pool["item"]==item]

    for _,r in pool.iterrows():
        if remaining <= 0:
            break

        take = min(remaining, r["available_qty"])
        remaining -= take

        plan.append((
            r["source"],
            take,
            f"📞 {r['contact']} | 💬 {r['whatsapp']} | ✉ {r['email']}"
        ))

    return plan, remaining

def create_purchase_transaction(item, qty):

    # 1️⃣ reduce supplier pool
    run_query("""
        UPDATE supply_pool
        SET available_qty = available_qty - ?
        WHERE item = ?
    """,(qty,item))

    # 2️⃣ increase our inventory
    run_query("""
        UPDATE inventory
        SET on_hand = on_hand + ?
        WHERE item = ?
    """,(qty,item))

    # 3️⃣ log purchase
    run_query("""
        INSERT INTO tasks VALUES (?,?,?)
    """,(f"Purchased {qty} {item}","Procurement","Completed"))


# ==========================================================
# CAPACITY UTILIZATION ENGINE
# ==========================================================
def capacity_engine():

    cap = load_capacity()

    if len(cap) == 0 or len(orders) == 0:
        return cap, []

    demand_total = orders["qty"].sum()
    total_capacity = cap["daily_capacity"].sum()

    utilization = (demand_total/(total_capacity+1))*100
    cap["utilization"] = utilization

    cap_alerts = []
    if utilization > 95:
        cap_alerts.append("🔴 Factory overloaded → Add extra shift")
    elif utilization < 50:
        cap_alerts.append("🟡 Idle capacity → Increase production")
    else:
        cap_alerts.append("🟢 Capacity balanced")

    return cap, cap_alerts


capacity_df, capacity_alerts = capacity_engine()


# ==========================================================
# KPI ENGINE
# ==========================================================
# ==========================================================
# 💰 KPI ENGINE (SAFE VERSION)
# ==========================================================
def calc_kpis():

    # ---------- Revenue ----------
    if "qty" in orders.columns and "unit_price" in orders.columns and len(orders) > 0:

        qty = pd.to_numeric(orders["qty"], errors="coerce").fillna(0)
        price = pd.to_numeric(orders["unit_price"], errors="coerce").fillna(0)

        revenue = (qty * price).sum()

    else:
        revenue = 0

    # ---------- Inventory value ----------
    if "on_hand" in inventory.columns and "unit_cost" in inventory.columns and len(inventory) > 0:

        stock = pd.to_numeric(inventory["on_hand"], errors="coerce").fillna(0)
        cost = pd.to_numeric(inventory["unit_cost"], errors="coerce").fillna(0)

        inv_value = (stock * cost).sum()

    else:
        inv_value = 0

    # ---------- Service level (demo metric) ----------
    service_level = 96 if len(orders) > 0 else 0

    # ---------- Capacity utilization ----------
    if "utilization" in capacity_df.columns and len(capacity_df) > 0:

        util_series = pd.to_numeric(
            capacity_df["utilization"],
            errors="coerce"
        ).fillna(0)

        util = util_series.mean()

    else:
        util = 0

    return revenue, inv_value, service_level, util



# ==========================================================
# DEMAND FORECAST ENGINE
# ==========================================================
# ==========================================================
# 📈 DEMAND FORECASTING MODULE (SAFE VERSION)
# ==========================================================
def forecast_demand():

    # If no data → skip forecasting
    if len(orders) == 0:
        return pd.DataFrame()

    df = orders.copy()

    # Auto-create missing columns (prevents KeyError)
    if "date" not in df.columns:
        return pd.DataFrame()

    if "qty" not in df.columns:
        return pd.DataFrame()

    # Convert date safely
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    if len(df) < 7:
        return pd.DataFrame()

    # Daily demand aggregation
    forecast = df.groupby("date")["qty"].sum().reset_index()

    # Simple rolling forecast (demo AI)
    forecast["forecast"] = forecast["qty"].rolling(7).mean()

    return forecast
forecast_df = forecast_demand()

# ==========================================================
# SAFE CHART BUILDER
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

# ==========================================================
# NAVIGATION MENU
# ==========================================================
menu = st.sidebar.selectbox(
    "Navigation",
    [
        "Control Tower",
        "Analytics",
        "AI Assistant",
        "Voice Assistant",
        "Planning Settings",
        "Live Map",
        "Upload Data",
        "Manual Entry",

        # 🆕 ENTERPRISE MODULES
        "Order Tracking",
        "CRM & Customer Followup",
        "Finance & Invoicing",
        "Workflow Automation",
        "Admin Dashboard",
        "System Settings"
    ]
)


# ==========================================================
# CONTROL TOWER DASHBOARD
# ==========================================================
if menu=="Control Tower":

    st.title("🏭 SupplySense Control Tower")

    revenue,inv_value,service,util = calc_kpis()

    # KPI CARDS
    k1,k2,k3,k4 = st.columns(4)
    k1.metric("💵 Sales Generated", f"₹{int(revenue):,}")
    k2.metric("🏦 Working Capital Locked", f"₹{int(inv_value):,}")
    k3.metric("🚚 Order Fulfilment Rate", f"{service}%")
    k4.metric("🏭 Factory Load", f"{int(util)}%")

    # Capacity alerts
    for cap_alert in capacity_alerts:
        st.info(cap_alert)

    st.divider()
    st.subheader("⚠️ Recommended Actions")

    # ACTIONS LOOP
    for i,(action,item) in enumerate(actions):
        col1,col2,col3 = st.columns([4,1,1])
        col1.write(f"{action} → {item}")

        if col2.button("Approve", key=f"approve_{i}_{item}"):

            create_purchase_transaction(item, 100)

            run_query(
                "INSERT INTO action_log VALUES (?,?,?,?)",
                (action,item,"Approved",str(datetime.datetime.now()))
            )

            st.success("Purchase executed. All modules updated.")
            st.rerun()

        if col3.button("Reject", key=f"reject_{i}_{item}"):

            run_query(
                "INSERT INTO action_log VALUES (?,?,?,?)",
                (action,item,"Rejected",str(datetime.datetime.now()))
            )

            st.error("Action rejected and logged")

    st.subheader("Projected Stock Levels")
    st.dataframe(balanced)

st.divider()
st.subheader("⚡ Instant Order Fulfilment Simulator")

item_req = st.text_input("Product Needed")
qty_req  = st.number_input("Required Quantity",0,100000)

if st.button("Find Supply Plan"):

    plan, shortage = fulfilment_engine(item_req, qty_req)

    if len(plan)==0:
        st.error("No supply found for this item")
    else:
        df_plan = pd.DataFrame(plan,columns=["Source","Allocated Qty","Contact"])
        st.dataframe(df_plan)

        if shortage>0:
            st.error(f"⚠️ Still Short: {shortage} units")
        else:
            st.success("✅ Demand fully satisfied")


# ==========================================================
# ANALYTICS DASHBOARD
# ==========================================================
elif menu=="Analytics":

    st.title("📊 Demand & Inventory Insights")

    safe_bar_chart(inventory,"warehouse","on_hand","category","Inventory by Warehouse")

    try:
        fig=px.pie(orders,names="category",values="qty",title="Demand by Category")
        st.plotly_chart(fig,use_container_width=True)
    except:
        st.warning("Upload more order data.")

    try:
        cust=orders.groupby("customer")["qty"].sum().reset_index()
        safe_bar_chart(cust,"customer","qty",None,"Top Customers")
    except:
        pass

    if len(forecast_df)>0:
        st.subheader("🔮 Demand Forecast")
        st.plotly_chart(px.line(forecast_df,x="date",y=["qty","forecast"]))

# ==========================================================
# AI ASSISTANT
# ==========================================================
elif menu=="AI Assistant":

    st.title("🤖 Ask SupplySense")
    q = st.text_input("Ask a planning question")

    if q:

        if AI_AVAILABLE:
            try:
                context=f"{inventory.head()}\n{orders.head()}\n{suppliers.head()}"

                res = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[
                        {"role":"system","content":"You are a supply chain planner."},
                        {"role":"user","content":context+"\nQuestion:"+q}
                    ]
                )
                st.success(res.choices[0].message.content)

            except:
                st.warning("AI cloud unavailable → using offline planner")

        low = balanced[balanced["projected_stock"] < balanced["safety"]]
        for i in low["item"]:
            st.write(f"• Expedite purchase for **{i}**")

# ==========================================================
# VOICE ASSISTANT (Demo)
# ==========================================================
elif menu=="Voice Assistant":

    st.title("🎤 Voice Assistant")
    cmd = st.text_input("Type your voice command")

    if cmd:
        if "stock" in cmd.lower():
            st.write(actions)
        elif "supplier" in cmd.lower():
            st.write(suppliers.head())
        else:
            st.write("Command not recognised")

# ==========================================================
# WHATSAPP ALERT ENGINE
# ==========================================================
def send_whatsapp_alert(message):
    try:
        from twilio.rest import Client
        client_twilio = Client(st.secrets["TWILIO_SID"],st.secrets["TWILIO_TOKEN"])
        client_twilio.messages.create(
            from_='whatsapp:+14155238886',
            body=message,
            to='whatsapp:+91XXXXXXXXXX'
        )
    except:
        pass

for action,item in actions:
    if "🚨" in action:
        send_whatsapp_alert(f"URGENT: Stockout risk for {item}")

# ==========================================================
# STRIPE BILLING (UI)
# ==========================================================
st.sidebar.subheader("💳 Subscription")
plan = st.sidebar.selectbox("Plan",["Free","Pro ₹999/mo","Enterprise ₹2999/mo"])
# ==========================================================
# FEATURE ACCESS BASED ON PLAN
# ==========================================================
if plan == "Free":
    allowed_pages = ["Control Tower","Upload Data","Manual Entry"]

elif plan == "Pro ₹999/mo":
    allowed_pages = [
        "Control Tower",
        "Analytics",
        "AI Assistant",
        "Upload Data",
        "Manual Entry"
    ]

else:  # Enterprise
    allowed_pages = [
        "Control Tower",
        "Analytics",
        "AI Assistant",
        "Voice Assistant",
        "Planning Settings",
        "Live Map",
        "Upload Data",
        "Manual Entry"
    ]

if st.sidebar.button("Upgrade"):
    st.sidebar.success("Stripe checkout would open here")

# ==========================================================
# PLANNING SETTINGS PAGE (NOW REAL)
# ==========================================================
elif menu=="Planning Settings":

    st.title("⚙️ Planning Parameters")

    params = load_params()

    safety = st.slider("Safety Stock",50,500,int(params["safety_stock"]))
    lead   = st.slider("Lead Time (days)",1,15,int(params["lead_time"]))
    moq    = st.slider("Minimum Order Quantity",50,500,int(params["moq"]))

    if st.button("💾 Save Parameters"):

        run_query(
            "DELETE FROM planning_params WHERE persona=?",
            (persona_key,)
        )

        run_query(
            "INSERT INTO planning_params VALUES (?,?,?,?)",
            (persona_key,safety,lead,moq)
        )

        st.success("Parameters saved for this persona!")


# ==========================================================
# LIVE MAP
# ==========================================================
elif menu=="Live Map":
    st.title("🗺 Warehouse Network")
    map_df=pd.DataFrame({"lat":[13.08,9.92,11.01],"lon":[80.27,78.12,76.96]})
    st.map(map_df)

# ==========================================================
# DATA UPLOAD (Excel/CSV)
# ==========================================================
elif menu=="Upload Data":

    st.title("Upload Dataset")

    table = st.selectbox(
        "Table",
        ["orders","inventory","suppliers","capacity","supply_pool"]
    )

    file = st.file_uploader("Upload file")

    if file:

        # Read file
        if file.name.endswith(".xlsx"):
            df = pd.read_excel(file)
        else:
            df = pd.read_csv(file)

        # Standardize column names
        df.columns = df.columns.str.lower().str.replace(" ","_")

        # Auto rename common column variations
        rename_map = {
            "product":"item",
            "product_name":"item",
            "stock":"on_hand",
            "quantity":"on_hand",
            "qty":"qty"
        }
        df.rename(columns=rename_map, inplace=True)

        conn = get_conn()

        # --- AUTO SCHEMA UPDATE ---
        try:
            existing = pd.read_sql(f"SELECT * FROM {table} LIMIT 1", conn)
            existing_cols = set(existing.columns)
            new_cols = set(df.columns)

            for col in new_cols - existing_cols:
                run_query(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
        except:
            pass  # table doesn't exist yet

        # --- APPEND DATA ---
        df.to_sql(
            table,
            conn,
            if_exists="append",
            index=False
        )

        st.success(f"{table} dataset uploaded successfully!")


# ==========================================================
# MANUAL ENTRY
# ==========================================================
elif menu=="Manual Entry":

    st.title("Add New Order")

    item = st.text_input("Item")
    qty  = st.number_input("Quantity")

    if st.button("Add Order"):
        run_query(
            f"INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("NEW","2025-01-01","Retail","Chennai","Retail",
             item,"General",qty,40,"Normal")
        )
        st.success("Order Added!")
# ==========================================================
# 📦 ORDER TRACKING MODULE
# ==========================================================
elif menu=="Order Tracking":

    st.title("📦 Order Lifecycle Tracking")

    if len(orders)==0:
        st.warning("No orders found")
    else:
        order_ids = orders["order_id"].unique()
        selected = st.selectbox("Select Order", order_ids)

        status = st.selectbox(
            "Update Status",
            ["Pending","Processing","Shipped","Delivered"]
        )

        if st.button("Update Order Status"):
            run_query(
                "INSERT INTO order_status VALUES (?,?,?)",
                (selected,status,str(datetime.datetime.now()))
            )
            st.success("Order updated")

        st.subheader("Status History")
        st.dataframe(get_table("order_status"))
# ==========================================================
# 👥 CRM & CUSTOMER FOLLOWUP
# ==========================================================
elif menu=="CRM & Customer Followup":

    st.title("Customer Relationship Manager")

    name = st.text_input("Customer Name")
    phone = st.text_input("Phone")
    email = st.text_input("Email")

    if st.button("Save Customer"):
        run_query(
            "INSERT INTO customers VALUES (?,?,?,?)",
            (name,phone,email,str(datetime.date.today()))
        )
        st.success("Customer saved")

    st.dataframe(get_table("customers"))
# ==========================================================
# 💰 FINANCE & INVOICING
# ==========================================================
elif menu=="Finance & Invoicing":

    st.title("Invoice & Payment Tracking")

    inv_id = st.text_input("Invoice ID")
    cust = st.text_input("Customer")
    amt = st.number_input("Amount")

    if st.button("Create Invoice"):
        run_query(
            "INSERT INTO invoices VALUES (?,?,?,?)",
            (inv_id,cust,amt,"Pending")
        )
        st.success("Invoice created")

    st.dataframe(get_table("invoices"))
# ==========================================================
# ⚙️ WORKFLOW AUTOMATION
# ==========================================================
elif menu=="Workflow Automation":

    st.title("Task & Approval Workflow")

    task = st.text_input("New Task")
    assignee = st.text_input("Assign To")

    if st.button("Create Task"):
        run_query("INSERT INTO tasks VALUES (?,?,?)",(task,assignee,"Open"))
        st.success("Task assigned")

    st.dataframe(get_table("tasks"))
# ==========================================================
# 👑 ADMIN DASHBOARD
# ==========================================================
elif menu=="Admin Dashboard":

    st.title("Admin Control Panel")

    st.subheader("Orders")
    st.dataframe(orders)

    st.subheader("Inventory")
    st.dataframe(inventory)

    st.subheader("Suppliers")
    st.dataframe(suppliers)

    st.subheader("Invoices")
    st.dataframe(get_table("invoices"))

st.write("Tables in DB:")
tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", get_conn())
st.dataframe(tables)
# ==========================================================
# ⚙️ SYSTEM SETTINGS
# ==========================================================
elif menu=="System Settings":

    st.title("System Settings")

    lang = st.selectbox("Language",["English","Tamil"])
    if lang=="Tamil":
        st.success("தமிழ் ஆதரவு செயல்படுத்தப்பட்டது")

    if st.button("Backup Database"):
        st.success("Database backup simulated ✔")

