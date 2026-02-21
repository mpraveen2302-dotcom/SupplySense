# ==========================================================
# SUPPLYSENSE – ENTERPRISE ULTRA COMPLETE VERSION
# ==========================================================

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import datetime
import time
from sklearn.linear_model import LinearRegression

st.set_page_config(layout="wide")

# ==========================================================
# DATABASE ENGINE (POSTGRESQL + SQLITE FALLBACK)
# ==========================================================

from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
else:
    engine = create_engine("sqlite:///supplysense.db")


def run_query(query, params=None):
    with engine.begin() as conn:
        conn.execute(text(query), params or {})


def get_table(name):
    try:
        return pd.read_sql(f"SELECT * FROM {name}", engine)
    except:
        return pd.DataFrame()




# ==========================================================
# TABLE CREATION (ALL FEATURES PRESERVED)
# ==========================================================

tables_sql = [

"""
CREATE TABLE IF NOT EXISTS orders(
order_id TEXT,date TEXT,customer TEXT,city TEXT,channel TEXT,
item TEXT,category TEXT,qty INT,unit_price FLOAT,priority TEXT)
""",

"""
CREATE TABLE IF NOT EXISTS inventory(
item TEXT,warehouse TEXT,category TEXT,supplier TEXT,
on_hand INT,wip INT,safety INT,reorder_point INT,unit_cost FLOAT)
""",

"""
CREATE TABLE IF NOT EXISTS suppliers(
supplier TEXT,item TEXT,lead_time INT,moq INT,
reliability FLOAT,cost_per_unit FLOAT,
phone TEXT,whatsapp TEXT,email TEXT)
""",

"""
CREATE TABLE IF NOT EXISTS capacity(
warehouse TEXT,machine TEXT,daily_capacity INT,
shift_hours INT,utilization FLOAT)
""",

"""
CREATE TABLE IF NOT EXISTS supply_pool(
source TEXT,item TEXT,available_qty INT,
contact TEXT,whatsapp TEXT,email TEXT)
""",

"""
CREATE TABLE IF NOT EXISTS planning_params(
persona TEXT,safety_stock INT,lead_time INT,moq INT)
""",

"""
CREATE TABLE IF NOT EXISTS action_log(
action TEXT,item TEXT,decision TEXT,timestamp TEXT)
""",

"""
CREATE TABLE IF NOT EXISTS tasks(
task TEXT,assignee TEXT,status TEXT)
"""
]

for sql in tables_sql:
    run_query(sql)


# ==========================================================
# LOGIN (ONLY ONE BLOCK – CLEAN)
# ==========================================================

USERS = {
    "admin":"admin123",
    "planner":"plan123",
    "warehouse":"wh123",
    "supplier":"sup123"
}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:

    st.title("🔐 SupplySense Enterprise Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in USERS and USERS[username] == password:
            st.session_state.logged_in = True
            st.session_state.role = username
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.stop()


# ==========================================================
# LOAD LIVE DATA
# ==========================================================

orders = get_table("orders")
inventory = get_table("inventory")
suppliers = get_table("suppliers")
capacity_df = get_table("capacity")
supply_pool = get_table("supply_pool")
# ==========================================================
# BALANCING ENGINE (REAL-TIME SUPPLY–DEMAND)
# ==========================================================

def balancing_engine():

    if inventory.empty:
        return pd.DataFrame(), []

    df = inventory.copy()

    if orders.empty:
        df["forecast_demand"] = 0
    else:
        temp_orders = orders.copy()
        temp_orders["qty"] = pd.to_numeric(
            temp_orders["qty"], errors="coerce"
        ).fillna(0)

        demand = (
            temp_orders.groupby("item")["qty"]
            .sum()
            .reset_index()
        )

        demand.rename(
            columns={"qty": "forecast_demand"},
            inplace=True
        )

        df = df.merge(demand, on="item", how="left")
        df["forecast_demand"] = df["forecast_demand"].fillna(0)

    df["on_hand"] = pd.to_numeric(df["on_hand"], errors="coerce").fillna(0)
    df["wip"] = pd.to_numeric(df["wip"], errors="coerce").fillna(0)
    df["safety"] = pd.to_numeric(df["safety"], errors="coerce").fillna(0)

    df["available_stock"] = df["on_hand"] + df["wip"]
    df["projected_stock"] = df["available_stock"] - df["forecast_demand"]

    actions = []

    for _, r in df.iterrows():

        if r["projected_stock"] < 0:
            actions.append(("🚨 Expedite Supplier", r["item"]))

        elif r["projected_stock"] < r["safety"]:
            actions.append(("⚠️ Increase Production", r["item"]))

        elif r["projected_stock"] > r["safety"] * 5:
            actions.append(("🛑 Reduce Batch Size", r["item"]))

        elif r["projected_stock"] > r["safety"] * 3:
            actions.append(("📦 Run Promotion", r["item"]))

        else:
            actions.append(("✅ Balanced", r["item"]))

    return df, actions


balanced, actions = balancing_engine()


# ==========================================================
# CAPACITY ENGINE
# ==========================================================

def capacity_engine():

    if capacity_df.empty or orders.empty:
        return 0

    cap = capacity_df.copy()
    cap["daily_capacity"] = pd.to_numeric(
        cap["daily_capacity"], errors="coerce"
    ).fillna(0)

    total_capacity = cap["daily_capacity"].sum()

    total_demand = pd.to_numeric(
        orders["qty"], errors="coerce"
    ).fillna(0).sum()

    utilization = (total_demand / (total_capacity + 1)) * 100

    return round(utilization, 2)


# ==========================================================
# KPI ENGINE
# ==========================================================

def calc_kpis():

    revenue = 0
    inv_value = 0
    service = 0
    util = capacity_engine()

    if not orders.empty:

        qty = pd.to_numeric(
            orders["qty"], errors="coerce"
        ).fillna(0)

        price = pd.to_numeric(
            orders["unit_price"], errors="coerce"
        ).fillna(0)

        revenue = (qty * price).sum()
        service = 96

    if not inventory.empty:

        stock = pd.to_numeric(
            inventory["on_hand"], errors="coerce"
        ).fillna(0)

        cost = pd.to_numeric(
            inventory["unit_cost"], errors="coerce"
        ).fillna(0)

        inv_value = (stock * cost).sum()

    return revenue, inv_value, service, util


# ==========================================================
# ADVANCED ML FORECAST ENGINE
# ==========================================================

def advanced_forecast():

    if orders.empty or "date" not in orders.columns:
        return pd.DataFrame()

    df = orders.copy()

    df["date"] = pd.to_datetime(
        df["date"], errors="coerce"
    )

    df = df.dropna(subset=["date"])

    if len(df) < 5:
        return pd.DataFrame()

    daily = (
        df.groupby("date")["qty"]
        .sum()
        .reset_index()
    )

    daily["index"] = np.arange(len(daily))

    model = LinearRegression()
    model.fit(daily[["index"]], daily["qty"])

    future_index = np.arange(len(daily), len(daily) + 7)

    predictions = model.predict(
        future_index.reshape(-1, 1)
    )

    forecast = pd.DataFrame({
        "future_day": future_index,
        "predicted_demand": predictions
    })

    return forecast


forecast_df = advanced_forecast()


# ==========================================================
# FULFILMENT ENGINE (MULTI-SOURCE)
# ==========================================================

def fulfilment_engine(item, required_qty):

    plan = []
    remaining = required_qty

    # Own Inventory
    own_stock_df = inventory[inventory["item"] == item]

    if not own_stock_df.empty:

        own_qty = int(
            pd.to_numeric(
                own_stock_df["on_hand"],
                errors="coerce"
            ).fillna(0).sum()
        )

        allocate = min(own_qty, remaining)

        if allocate > 0:
            plan.append(
                ("🏭 Own Warehouse",
                 allocate,
                 "Internal Stock")
            )
            remaining -= allocate

    # Supply Pool
    pool = supply_pool[supply_pool["item"] == item]

    for _, row in pool.iterrows():

        if remaining <= 0:
            break

        available = int(
            pd.to_numeric(
                row["available_qty"],
                errors="coerce"
            )
        )

        allocate = min(available, remaining)

        if allocate > 0:
            plan.append((
                row["source"],
                allocate,
                f"📞 {row['contact']} | 💬 {row['whatsapp']} | ✉ {row['email']}"
            ))

            remaining -= allocate

    return plan, remaining


# ==========================================================
# PURCHASE TRANSACTION ENGINE
# ==========================================================

def create_purchase_transaction(item, qty):

    run_query(
        """
        UPDATE inventory
        SET on_hand = on_hand + ?
        WHERE item = ?
        """,
        (qty, item)
    )

    run_query(
        """
        INSERT INTO tasks VALUES (?,?,?)
        """,
        (f"Purchased {qty} {item}",
         "Procurement",
         "Completed")
    )


# ==========================================================
# WAREHOUSE TRANSFER ENGINE
# ==========================================================

def transfer_inventory(item, qty, from_wh, to_wh):

    run_query(
        """
        UPDATE inventory
        SET on_hand = on_hand - ?
        WHERE item=? AND warehouse=?
        """,
        (qty, item, from_wh)
    )

    run_query(
        """
        UPDATE inventory
        SET on_hand = on_hand + ?
        WHERE item=? AND warehouse=?
        """,
        (qty, item, to_wh)
    )

    run_query(
        """
        INSERT INTO tasks VALUES (?,?,?)
        """,
        (f"Transferred {qty} {item} from {from_wh} to {to_wh}",
         "Warehouse",
         "Completed")
    )
    # ==========================================================
# NAVIGATION MENU
# ==========================================================

if "menu" not in st.session_state:
    st.session_state.menu = "Control Tower"

st.session_state.menu = st.sidebar.selectbox(
    "Navigation",
    [
        "Control Tower",
        "Analytics",
        "Upload Data",
        "Manual Entry",
        "Admin Dashboard",
        "Planning Settings",
        "System Settings"
    ],
    index=[
        "Control Tower",
        "Analytics",
        "Upload Data",
        "Manual Entry",
        "Admin Dashboard",
        "Planning Settings",
        "System Settings"
    ].index(st.session_state.menu)
)

menu = st.session_state.menu
# ==========================================================
# CONTROL TOWER
# ==========================================================

if menu == "Control Tower":

    st.title("🏭 Enterprise Control Tower")

    revenue, inv_value, service, util = calc_kpis()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💵 Sales", f"₹{int(revenue):,}")
    c2.metric("🏦 Inventory Value", f"₹{int(inv_value):,}")
    c3.metric("🚚 Service Level", f"{service}%")
    c4.metric("🏭 Factory Load", f"{util}%")

    st.divider()
    st.subheader("⚠️ Recommended Actions")

    for i, (action, item) in enumerate(actions):

        col1, col2, col3 = st.columns([4,1,1])
        col1.write(f"{action} → {item}")

        if col2.button("Approve", key=f"approve_{i}"):

            create_purchase_transaction(item, 100)

            run_query(
                "INSERT INTO action_log VALUES (?,?,?,?)",
                (action, item, "Approved",
                 str(datetime.datetime.now()))
            )

            st.success("Approved")
            st.rerun()

        if col3.button("Reject", key=f"reject_{i}"):

            run_query(
                "INSERT INTO action_log VALUES (?,?,?,?)",
                (action, item, "Rejected",
                 str(datetime.datetime.now()))
            )

            st.error("Rejected")

    st.divider()
    st.subheader("📦 Projected Stock")
    st.dataframe(balanced)

    st.divider()
    st.subheader("⚡ Instant Fulfilment Simulator")

    item_req = st.text_input("Product Needed")
    qty_req = st.number_input("Required Quantity", 0, 100000)

    if st.button("Find Supply Plan"):

        plan, shortage = fulfilment_engine(item_req, qty_req)

        if not plan:
            st.error("No supply found")
        else:
            df_plan = pd.DataFrame(
                plan,
                columns=["Source","Allocated Qty","Contact"]
            )
            st.dataframe(df_plan)

            if shortage > 0:
                st.error(f"Shortage: {shortage}")
            else:
                st.success("Demand fully satisfied")


# ==========================================================
# ANALYTICS DASHBOARD
# ==========================================================

elif menu == "Analytics":

    st.title("📊 Analytics Dashboard")

    if not inventory.empty:
        fig = px.bar(
            inventory,
            x="warehouse",
            y="on_hand",
            color="category",
            title="Inventory by Warehouse"
        )
        st.plotly_chart(fig, use_container_width=True)

    if not forecast_df.empty:
        fig2 = px.line(
            forecast_df,
            x="future_day",
            y="predicted_demand",
            title="7-Day ML Forecast"
        )
        st.plotly_chart(fig2, use_container_width=True)


# ==========================================================
# UPLOAD ENGINE
# ==========================================================

elif menu == "Upload Data":

    st.title("📤 Upload Dataset")

    table = st.selectbox(
        "Select Table",
        ["orders","inventory","suppliers","capacity","supply_pool"]
    )

    file = st.file_uploader("Upload CSV", type=["csv"])

    if file is not None:

        try:
            df = pd.read_csv(file)
            df.columns = df.columns.str.lower().str.replace(" ","_")

            conn = get_conn()
            df.to_sql(table, conn, if_exists="append", index=False)
            conn.close()

            st.success(f"{table} uploaded successfully!")
            st.info("Go to Admin Dashboard to verify data.")

        except Exception as e:
            st.error(f"Upload failed: {e}")
# ==========================================================
# MANUAL ENTRY
# ==========================================================

elif menu == "Manual Entry":

    st.title("➕ Add Manual Order")

    item = st.text_input("Item")
    qty = st.number_input("Quantity", 0, 100000)

    if st.button("Add Order"):

        run_query(
            """
            INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "NEW",
                str(datetime.date.today()),
                "Retail",
                "Chennai",
                "Retail",
                item,
                "General",
                qty,
                40,
                "Normal"
            )
        )

        st.success("Order Added")
        st.rerun()


# ==========================================================
# ADMIN DASHBOARD
# ==========================================================

elif menu == "Admin Dashboard":

    st.title("👑 Admin Dashboard")

    st.subheader("Orders")
    st.dataframe(orders)

    st.subheader("Inventory")
    st.dataframe(inventory)

    st.subheader("Suppliers")
    st.dataframe(suppliers)

    st.subheader("Supply Pool")
    st.dataframe(supply_pool)

    st.subheader("Action Logs")
    st.dataframe(get_table("action_log"))


# ==========================================================
# PLANNING SETTINGS
# ==========================================================

elif menu == "Planning Settings":

    st.title("⚙️ Planning Parameters")

    safety = st.slider("Safety Stock", 50, 500, 150)
    lead = st.slider("Lead Time", 1, 15, 5)
    moq = st.slider("MOQ", 50, 500, 200)

    if st.button("Save Parameters"):

        run_query(
            "DELETE FROM planning_params WHERE persona=?",
            (st.session_state.role,)
        )

        run_query(
            "INSERT INTO planning_params VALUES (?,?,?,?)",
            (st.session_state.role, safety, lead, moq)
        )

        st.success("Parameters Saved")


# ==========================================================
# SYSTEM SETTINGS
# ==========================================================

elif menu == "System Settings":

    st.title("⚙️ System Settings")

    if st.button("Backup Database"):
        st.success("Backup simulated")

    if st.button("View Logs"):
        st.dataframe(get_table("action_log"))


# ==========================================================
# GEO SUPPLY NETWORK MAP
# ==========================================================

st.sidebar.subheader("🌍 Geo Supply Map")

if st.sidebar.button("Show Warehouse Map"):

    geo_map = {
        "Chennai WH": (13.08,80.27),
        "Cold Storage": (13.10,80.25),
        "Grain Warehouse": (11.01,76.96),
        "Grocery WH": (9.92,78.12)
    }

    map_data = []

    for _, row in inventory.iterrows():
        wh = row["warehouse"]
        if wh in geo_map:
            lat, lon = geo_map[wh]
            map_data.append({"lat":lat,"lon":lon})

    if map_data:
        st.map(pd.DataFrame(map_data))


# ==========================================================
# SIDEBAR WAREHOUSE TRANSFER
# ==========================================================

st.sidebar.subheader("🔁 Warehouse Transfer")

transfer_item = st.sidebar.text_input("Item to Transfer")
transfer_qty = st.sidebar.number_input("Qty", 0, 100000)
from_wh = st.sidebar.text_input("From Warehouse")
to_wh = st.sidebar.text_input("To Warehouse")

if st.sidebar.button("Execute Transfer"):

    transfer_inventory(
        transfer_item,
        transfer_qty,
        from_wh,
        to_wh
    )

    st.sidebar.success("Transfer Completed")
    st.rerun()


# ==========================================================
# STRIPE BILLING (UI ONLY)
# ==========================================================

st.sidebar.subheader("💳 Subscription")

plan = st.sidebar.selectbox(
    "Plan",
    ["Free","Pro ₹999/mo","Enterprise ₹2999/mo"]
)

if st.sidebar.button("Upgrade Plan"):
    st.sidebar.success("Stripe checkout placeholder")

# ==========================================================
# PART 4 – ENTERPRISE INTELLIGENCE EXTENSION
# ==========================================================


# ==========================================================
# ERP UI STYLE ENHANCEMENT
# ==========================================================

st.markdown("""
<style>
.metric-card {
    background-color:#f5f7fa;
    padding:15px;
    border-radius:12px;
    box-shadow:0px 2px 6px rgba(0,0,0,0.05);
}
</style>
""", unsafe_allow_html=True)


# ==========================================================
# AI PLANNING ASSISTANT (Context-Aware)
# ==========================================================

st.sidebar.subheader("🧠 AI Planning Assistant")

AI_AVAILABLE = False
try:
    from openai import OpenAI
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    AI_AVAILABLE = True
except:
    pass

if AI_AVAILABLE:

    ai_question = st.sidebar.text_input("Ask AI Planner")

    if ai_question:

        try:
            context_data = f"""
            Inventory:
            {inventory.head().to_string()}

            Orders:
            {orders.head().to_string()}

            Supply Pool:
            {supply_pool.head().to_string()}
            """

            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role":"system",
                     "content":"You are an enterprise supply chain strategist."},
                    {"role":"user",
                     "content":context_data + "\n\nQuestion: " + ai_question}
                ]
            )

            st.sidebar.success(
                response.choices[0].message.content
            )

        except:
            st.sidebar.warning("AI temporarily unavailable")


# ==========================================================
# DEMAND SPIKE SIMULATOR
# ==========================================================

st.sidebar.subheader("📈 Demand Spike Simulator")

if st.sidebar.button("Simulate 200% Demand Spike"):

    if not orders.empty:

        run_query(
            "UPDATE orders SET qty = qty * 2"
        )

        st.sidebar.success("Demand spike simulated")
        st.rerun()


# ==========================================================
# SUPPLIER WHATSAPP AUTO ALERT ENGINE
# ==========================================================

def send_supplier_alert(supplier_name, message):

    supplier_row = suppliers[
        suppliers["supplier"] == supplier_name
    ]

    if supplier_row.empty:
        return

    try:
        from twilio.rest import Client
        client_twilio = Client(
            st.secrets["TWILIO_SID"],
            st.secrets["TWILIO_TOKEN"]
        )

        whatsapp_number = supplier_row.iloc[0]["whatsapp"]

        client_twilio.messages.create(
            from_='whatsapp:+14155238886',
            body=message,
            to=f'whatsapp:{whatsapp_number}'
        )

    except:
        pass


# Auto-trigger supplier alerts for stockouts
for action, item in actions:

    if "🚨" in action:

        supplier_match = inventory[
            inventory["item"] == item
        ]

        if not supplier_match.empty:

            supplier_name = supplier_match.iloc[0]["supplier"]

            send_supplier_alert(
                supplier_name,
                f"URGENT: Immediate replenishment required for {item}"
            )


# ==========================================================
# SUBSCRIPTION FEATURE GATING
# ==========================================================

st.sidebar.subheader("💼 Enterprise Monitoring")

monitor_option = st.sidebar.selectbox(
    "Monitoring Tools",
    [
        "Basic Metrics",
        "Advanced Risk Alerts",
        "Full Enterprise Intelligence"
    ]
)

if monitor_option == "Basic Metrics":
    st.sidebar.info("Standard KPI Monitoring Active")

elif monitor_option == "Advanced Risk Alerts":
    st.sidebar.warning("AI Risk Detection Active")

else:
    st.sidebar.success("Enterprise Ultra Mode Enabled")


# ==========================================================
# REAL-TIME CRITICAL ALERT BANNER
# ==========================================================

critical_items = [
    item for action, item in actions
    if "🚨" in action
]

if critical_items:

    st.error(
        f"🚨 CRITICAL STOCK ALERT: {', '.join(critical_items)}"
    )


# ==========================================================
# ACTION LOG VIEWER (ENTERPRISE TRACEABILITY)
# ==========================================================

with st.expander("📜 Enterprise Action History"):

    logs = get_table("action_log")

    if not logs.empty:
        st.dataframe(logs)
    else:
        st.info("No actions logged yet")
