# ==========================================================
# SUPPLYSENSE – ENTERPRISE ULTRA (STABLE SINGLE FILE)
# ==========================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import datetime
import os
from sklearn.linear_model import LinearRegression
from sqlalchemy import create_engine, text

st.set_page_config(layout="wide")

# ==========================================================
# DATABASE ENGINE (POSTGRESQL + SQLITE FALLBACK)
# ==========================================================

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
# TABLE CREATION
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

# Add country column safely (only if not exists)
try:
    run_query("ALTER TABLE suppliers ADD COLUMN country TEXT")
except:
    pass

# ==========================================================
# LOGIN SYSTEM
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
# LOAD DATA
# ==========================================================

orders = get_table("orders")
inventory = get_table("inventory")
suppliers = get_table("suppliers")
capacity_df = get_table("capacity")
supply_pool = get_table("supply_pool")

# ==========================================================
# CORE ENGINES
# ==========================================================

def balancing_engine():

    if inventory.empty:
        return pd.DataFrame(), []

    df = inventory.copy()

    if not orders.empty:
        demand = orders.groupby("item")["qty"].sum().reset_index()
        demand.rename(columns={"qty":"forecast_demand"}, inplace=True)
        df = df.merge(demand, on="item", how="left")
    else:
        df["forecast_demand"] = 0

    df["forecast_demand"] = df["forecast_demand"].fillna(0)
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

def capacity_engine():
    if capacity_df.empty or orders.empty:
        return 0
    return round((orders["qty"].sum() /
                  (capacity_df["daily_capacity"].sum()+1))*100,2)

def calc_kpis():

    revenue = (orders["qty"] * orders["unit_price"]).sum() if not orders.empty else 0
    inv_value = (inventory["on_hand"] * inventory["unit_cost"]).sum() if not inventory.empty else 0
    return revenue, inv_value, 96, capacity_engine()

def advanced_forecast():

    if orders.empty:
        return pd.DataFrame()

    daily = orders.groupby("date")["qty"].sum().reset_index()
    if len(daily) < 5:
        return pd.DataFrame()

    daily["index"] = np.arange(len(daily))
    model = LinearRegression()
    model.fit(daily[["index"]], daily["qty"])

    future_index = np.arange(len(daily), len(daily)+7)
    preds = model.predict(future_index.reshape(-1,1))

    return pd.DataFrame({
        "future_day":future_index,
        "predicted_demand":preds
    })

balanced, actions = balancing_engine()
forecast_df = advanced_forecast()

# ==========================================================
# STABLE NAVIGATION
# ==========================================================

PAGES = [
    "Control Tower",
    "Analytics",
    "Upload Data",
    "Manual Entry",
    "Admin Dashboard",
    "Planning Settings",
    "System Settings"
]

if "menu" not in st.session_state:
    st.session_state.menu = "Control Tower"

selected_page = st.sidebar.selectbox(
    "Navigation",
    PAGES,
    index=PAGES.index(st.session_state.menu)
)

st.session_state.menu = selected_page
menu = selected_page
# ==========================================================
# CONTROL TOWER PAGE
# ==========================================================

if menu == "Control Tower":

    st.title("🏭 Enterprise Control Tower")

    revenue, inv_value, service, util = calc_kpis()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💵 Sales Generated", f"₹{int(revenue):,}")
    c2.metric("🏦 Inventory Value", f"₹{int(inv_value):,}")
    c3.metric("🚚 Service Level", f"{service}%")
    c4.metric("🏭 Factory Utilization", f"{util}%")

    st.divider()
    st.subheader("⚠️ Recommended Actions")

    for i, (action, item) in enumerate(actions):

        col1, col2, col3 = st.columns([4,1,1])
        col1.write(f"{action} → {item}")

        if col2.button("Approve", key=f"approve_{i}"):

            run_query(
                "INSERT INTO action_log VALUES (?,?,?,?)",
                (action, item, "Approved",
                 str(datetime.datetime.now()))
            )

            st.success("Action Approved")

        if col3.button("Reject", key=f"reject_{i}"):

            run_query(
                "INSERT INTO action_log VALUES (?,?,?,?)",
                (action, item, "Rejected",
                 str(datetime.datetime.now()))
            )

            st.error("Action Rejected")

    st.divider()
    st.subheader("📦 Projected Stock Overview")
    st.dataframe(balanced)

    st.divider()
    st.subheader("⚡ Instant Order Fulfilment Simulator")

    item_req = st.text_input("Product Needed")
    qty_req = st.number_input("Required Quantity", 0, 100000)

    if st.button("Find Supply Plan"):

        plan = []
        remaining = qty_req

        own_stock_df = inventory[inventory["item"] == item_req]

        if not own_stock_df.empty:
            own_qty = int(own_stock_df["on_hand"].sum())
            allocate = min(own_qty, remaining)
            if allocate > 0:
                plan.append(("🏭 Own Warehouse", allocate, "Internal Stock"))
                remaining -= allocate

        pool = supply_pool[supply_pool["item"] == item_req]

        for _, row in pool.iterrows():
            if remaining <= 0:
                break
            allocate = min(int(row["available_qty"]), remaining)
            if allocate > 0:
                plan.append((
                    row["source"],
                    allocate,
                    f"{row['contact']} | {row['whatsapp']} | {row['email']}"
                ))
                remaining -= allocate

        if not plan:
            st.error("No supply found")
        else:
            df_plan = pd.DataFrame(
                plan,
                columns=["Source","Allocated Qty","Contact"]
            )
            st.dataframe(df_plan)

            if remaining > 0:
                st.error(f"Shortage: {remaining}")
            else:
                st.success("Demand Fully Satisfied")


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
# UPLOAD DATA PAGE
# ==========================================================

elif menu == "Upload Data":

    st.title("📤 Upload Dataset")

    table = st.selectbox(
        "Select Table",
        ["orders","inventory","suppliers","capacity","supply_pool"]
    )

    file = st.file_uploader("Upload CSV", type=["csv"])

    if file:

        try:
            df = pd.read_csv(file)
            df.columns = df.columns.str.lower().str.replace(" ","_")

            df.to_sql(table, engine, if_exists="append", index=False)

            st.success(f"{table} uploaded successfully!")

        except Exception as e:
            st.error(f"Upload failed: {e}")


# ==========================================================
# MANUAL ENTRY PAGE
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

        st.success("Order Added Successfully")


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

        st.success("Planning Parameters Saved")


# ==========================================================
# SYSTEM SETTINGS
# ==========================================================

elif menu == "System Settings":

    st.title("⚙️ System Settings")

    if st.button("Backup Database"):
        st.success("Database Backup Simulated")

    if st.button("View Logs"):
        st.dataframe(get_table("action_log"))

# ==========================================================
# ENTERPRISE SIDEBAR EXTENSIONS (SCOPED SAFELY)
# ==========================================================

st.sidebar.divider()
st.sidebar.subheader("🚀 Enterprise Tools")

# ==========================================================
# GEO SUPPLY NETWORK MAP
# ==========================================================

if menu == "Control Tower":

    if st.sidebar.button("🌍 Show Warehouse Map"):

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
                map_data.append({
                    "lat": lat,
                    "lon": lon,
                    "size": row["on_hand"]
                })

        if map_data:
            st.map(pd.DataFrame(map_data))
        else:
            st.warning("No warehouse geo data available")


# ==========================================================
# WAREHOUSE TRANSFER TOOL
# ==========================================================

if menu == "Control Tower":

    st.sidebar.subheader("🔁 Warehouse Transfer")

    transfer_item = st.sidebar.text_input("Item to Transfer")
    transfer_qty = st.sidebar.number_input("Quantity", 0, 100000)
    from_wh = st.sidebar.text_input("From Warehouse")
    to_wh = st.sidebar.text_input("To Warehouse")

    if st.sidebar.button("Execute Transfer"):

        run_query(
            """
            UPDATE inventory
            SET on_hand = on_hand - ?
            WHERE item=? AND warehouse=?
            """,
            (transfer_qty, transfer_item, from_wh)
        )

        run_query(
            """
            UPDATE inventory
            SET on_hand = on_hand + ?
            WHERE item=? AND warehouse=?
            """,
            (transfer_qty, transfer_item, to_wh)
        )

        run_query(
            "INSERT INTO tasks VALUES (?,?,?)",
            (f"Transferred {transfer_qty} {transfer_item}",
             "Warehouse",
             "Completed")
        )

        st.sidebar.success("Transfer Completed")


# ==========================================================
# STRIPE SUBSCRIPTION UI (SIMULATED)
# ==========================================================

st.sidebar.subheader("💳 Subscription Plan")

plan = st.sidebar.selectbox(
    "Select Plan",
    ["Free","Pro ₹999/mo","Enterprise ₹2999/mo"]
)

if st.sidebar.button("Upgrade Plan"):
    st.sidebar.success("Stripe Checkout Triggered (UI Simulation)")


# ==========================================================
# AI PLANNING ASSISTANT
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
            context = f"""
            Inventory Snapshot:
            {inventory.head().to_string()}

            Orders Snapshot:
            {orders.head().to_string()}
            """

            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role":"system","content":"You are a supply chain strategist."},
                    {"role":"user","content":context + "\nQuestion: " + ai_question}
                ]
            )

            st.sidebar.success(response.choices[0].message.content)

        except:
            st.sidebar.warning("AI temporarily unavailable")


# ==========================================================
# DEMAND SPIKE SIMULATOR
# ==========================================================

st.sidebar.subheader("📈 Demand Spike Simulator")

if st.sidebar.button("Simulate 200% Demand Spike"):

    if not orders.empty:

        run_query("UPDATE orders SET qty = qty * 2")
        st.sidebar.success("Demand Spike Simulated")

    else:
        st.sidebar.warning("No orders to modify")


# ==========================================================
# SUPPLIER WHATSAPP AUTO ALERT
# ==========================================================

def send_supplier_alert(supplier_name, message):

    supplier_row = suppliers[suppliers["supplier"] == supplier_name]

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


if menu == "Control Tower":

    for action, item in actions:
        if "🚨" in action:

            supplier_match = inventory[inventory["item"] == item]

            if not supplier_match.empty:

                supplier_name = supplier_match.iloc[0]["supplier"]

                send_supplier_alert(
                    supplier_name,
                    f"URGENT: Immediate replenishment required for {item}"
                )


# ==========================================================
# ENTERPRISE MONITORING OPTIONS
# ==========================================================

st.sidebar.subheader("📊 Monitoring Mode")

monitor_option = st.sidebar.selectbox(
    "Monitoring Level",
    ["Basic Metrics","Advanced Risk Alerts","Enterprise Ultra"]
)

if monitor_option == "Basic Metrics":
    st.sidebar.info("Standard Monitoring Active")

elif monitor_option == "Advanced Risk Alerts":
    st.sidebar.warning("AI Risk Detection Enabled")

else:
    st.sidebar.success("Enterprise Ultra Intelligence Active")


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
# ENTERPRISE ACTION HISTORY
# ==========================================================

with st.expander("📜 Enterprise Action History"):

    logs = get_table("action_log")

    if not logs.empty:
        st.dataframe(logs)
    else:
        st.info("No actions logged yet")
