from app.database import get_engine
from sqlalchemy import text

engine = get_engine()

def run_query(query, params=None):
    with engine.begin() as conn:
        conn.execute(text(query), params or {})

from app.auth import generate_token, verify_token

if "token" not in st.session_state:

    st.title("🔐 Login")

    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")

    if st.button("Login"):
        if user == "admin" and pwd == "admin123":
            st.session_state.token = generate_token(user)
            st.experimental_rerun()
        else:
            st.error("Invalid credentials")

    st.stop()

# ==========================================================
# SUPPLYSENSE – ENTERPRISE ULTRA CONTROL TOWER
# ==========================================================

import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import datetime

st.set_page_config(layout="wide")

# ==========================================================
# REAL-TIME AUTO REFRESH ENGINE
# ==========================================================

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

REFRESH_INTERVAL = 10  # seconds

if time.time() - st.session_state.last_refresh > REFRESH_INTERVAL:
    st.session_state.last_refresh = time.time()
    st.experimental_rerun()

# ==========================================================
# DATABASE (PERSISTENT)
# ==========================================================



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
# TABLE CREATION
# ==========================================================

run_query("""
CREATE TABLE IF NOT EXISTS orders(
order_id TEXT,date TEXT,customer TEXT,city TEXT,channel TEXT,
item TEXT,category TEXT,qty INT,unit_price FLOAT,priority TEXT)
""")

run_query("""
CREATE TABLE IF NOT EXISTS inventory(
item TEXT,warehouse TEXT,category TEXT,supplier TEXT,
on_hand INT,wip INT,safety INT,reorder_point INT,unit_cost FLOAT)
""")

run_query("""
CREATE TABLE IF NOT EXISTS suppliers(
supplier TEXT,item TEXT,country TEXT,lead_time INT,
moq INT,reliability FLOAT,cost_per_unit FLOAT,
phone TEXT,whatsapp TEXT,email TEXT)
""")

run_query("""
CREATE TABLE IF NOT EXISTS capacity(
warehouse TEXT,machine TEXT,daily_capacity INT,
shift_hours INT,utilization FLOAT)
""")

run_query("""
CREATE TABLE IF NOT EXISTS supply_pool(
source TEXT,item TEXT,available_qty INT,
contact TEXT,whatsapp TEXT,email TEXT)
""")

run_query("""
CREATE TABLE IF NOT EXISTS planning_params(
persona TEXT,safety_stock INT,lead_time INT,moq INT)
""")

run_query("""
CREATE TABLE IF NOT EXISTS action_log(
action TEXT,item TEXT,decision TEXT,timestamp TEXT)
""")

run_query("""
CREATE TABLE IF NOT EXISTS tasks(
task TEXT,assignee TEXT,status TEXT)
""")

# ==========================================================
# PERSONA ENGINE
# ==========================================================

st.sidebar.title("👥 MSME Personas")

persona = st.sidebar.selectbox(
    "Choose Workspace",
    ["Owner Rajesh",
     "Planner Kavitha",
     "Warehouse Arun",
     "Supplier ABC Foods"]
)

PERSONA_CONTEXT = {
    "Owner Rajesh": (
        "Cash Flow & Revenue Risk",
        "Stockouts reduce sales. Overstock blocks working capital."
    ),
    "Planner Kavitha": (
        "Demand–Production Imbalance",
        "Sudden spikes require rescheduling."
    ),
    "Warehouse Arun": (
        "Storage & Expiry Risk",
        "Excess inventory increases wastage."
    ),
    "Supplier ABC Foods": (
        "Unpredictable Orders",
        "Last-minute POs disrupt planning."
    )
}

st.sidebar.info(
    f"🎯 Concern: {PERSONA_CONTEXT[persona][0]}\n\n"
    f"💡 Why: {PERSONA_CONTEXT[persona][1]}"
)

# ==========================================================
# LOAD LIVE DATA
# ==========================================================

orders = get_table("orders")
inventory = get_table("inventory")
suppliers = get_table("suppliers")
capacity_df = get_table("capacity")
supply_pool = get_table("supply_pool")
# ==========================================================
# BALANCING ENGINE (REAL-TIME SUPPLY-DEMAND CONTROL)
# ==========================================================

def balancing_engine():

    if inventory.empty:
        return pd.DataFrame(), []

    df = inventory.copy()
    ord_df = orders.copy()

    # Ensure numeric safety
    if "qty" not in ord_df.columns:
        ord_df["qty"] = 0

    ord_df["qty"] = pd.to_numeric(ord_df["qty"], errors="coerce").fillna(0)

    # Aggregate demand
    demand = ord_df.groupby("item")["qty"].sum().reset_index()
    demand.rename(columns={"qty": "forecast_demand"}, inplace=True)

    df = df.merge(demand, on="item", how="left")
    df["forecast_demand"] = df["forecast_demand"].fillna(0)

    # Stock projection
    df["available_stock"] = df["on_hand"] + df["wip"]
    df["projected_stock"] = df["available_stock"] - df["forecast_demand"]

    actions = []

    for _, r in df.iterrows():

        if r["projected_stock"] < 0:
            actions.append(("🚨 Expedite Supplier", r["item"]))

        elif r["projected_stock"] < r["safety"]:
            actions.append(("⚠️ Increase Production", r["item"]))

        elif r["projected_stock"] > r["safety"] * 3:
            actions.append(("🛑 Reduce Batch Size", r["item"]))

        else:
            actions.append(("✅ Balanced", r["item"]))

    return df, actions


balanced, actions = balancing_engine()


# ==========================================================
# SMART FULFILMENT ENGINE (MULTI-SUPPLIER ALLOCATION)
# ==========================================================

def fulfilment_engine(item, required_qty):

    plan = []
    remaining = required_qty

    # 1️⃣ Own inventory first
    own_stock_df = inventory[inventory["item"] == item]

    if not own_stock_df.empty:
        own_qty = int(own_stock_df["on_hand"].sum())
        allocate = min(own_qty, remaining)

        if allocate > 0:
            plan.append(("🏭 Own Warehouse", allocate, "Internal Stock"))
            remaining -= allocate

    # 2️⃣ External supply pool
    pool = supply_pool[supply_pool["item"] == item]

    for _, row in pool.iterrows():

        if remaining <= 0:
            break

        available = int(row["available_qty"])
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
# PURCHASE TRANSACTION ENGINE (LIVE UPDATE)
# ==========================================================

def create_purchase_transaction(item, qty):

    # Deduct from supply pool proportionally
    pool = get_table("supply_pool")
    pool = pool[pool["item"] == item]

    remaining = qty

    for _, row in pool.iterrows():

        if remaining <= 0:
            break

        available = int(row["available_qty"])
        deduct = min(available, remaining)

        run_query("""
        UPDATE supply_pool
        SET available_qty = available_qty - ?
        WHERE source = ? AND item = ?
        """, (deduct, row["source"], item))

        remaining -= deduct

    # Add to inventory
    run_query("""
    UPDATE inventory
    SET on_hand = on_hand + ?
    WHERE item = ?
    """, (qty, item))

    # Log action
    run_query("""
    INSERT INTO tasks VALUES (?,?,?)
    """, (f"Purchased {qty} of {item}", "Procurement", "Completed"))


# ==========================================================
# CAPACITY ENGINE (LOAD CALCULATION)
# ==========================================================

def capacity_engine():

    if capacity_df.empty or orders.empty:
        return 0

    total_capacity = capacity_df["daily_capacity"].sum()
    total_demand = pd.to_numeric(orders["qty"], errors="coerce").fillna(0).sum()

    utilization = (total_demand / (total_capacity + 1)) * 100

    return round(utilization, 2)


# ==========================================================
# KPI ENGINE (ENTERPRISE METRICS)
# ==========================================================

def calc_kpis():

    revenue = 0
    inv_value = 0
    service = 0
    util = capacity_engine()

    if not orders.empty:
        revenue = (
            pd.to_numeric(orders["qty"], errors="coerce").fillna(0) *
            pd.to_numeric(orders["unit_price"], errors="coerce").fillna(0)
        ).sum()

        service = 96

    if not inventory.empty:
        inv_value = (
            pd.to_numeric(inventory["on_hand"], errors="coerce").fillna(0) *
            pd.to_numeric(inventory["unit_cost"], errors="coerce").fillna(0)
        ).sum()

    return revenue, inv_value, service, util


# ==========================================================
# ADVANCED ML FORECAST ENGINE
# ==========================================================

def advanced_forecast():

    if orders.empty or "date" not in orders.columns:
        return pd.DataFrame()

    df = orders.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    if len(df) < 5:
        return pd.DataFrame()

    daily = df.groupby("date")["qty"].sum().reset_index()

    daily["day_index"] = np.arange(len(daily))

    model = LinearRegression()
    model.fit(daily[["day_index"]], daily["qty"])

    future_days = 7
    future_index = np.arange(len(daily), len(daily)+future_days)

    predictions = model.predict(future_index.reshape(-1,1))

    forecast_df = pd.DataFrame({
        "future_day_index": future_index,
        "predicted_demand": predictions
    })

    return forecast_df
# ==========================================================
# WHATSAPP ALERT ENGINE (SAFE WRAPPER)
# ==========================================================

def send_whatsapp_alert(message):
    try:
        from twilio.rest import Client
        client = Client(st.secrets["TWILIO_SID"], st.secrets["TWILIO_TOKEN"])
        client.messages.create(
            from_='whatsapp:+14155238886',
            body=message,
            to='whatsapp:+91XXXXXXXXXX'
        )
    except:
        pass


# Auto-trigger alerts for critical shortages
for action, item in actions:
    if "🚨" in action:
        send_whatsapp_alert(f"URGENT: Stockout risk for {item}")
        # ==========================================================
# NAVIGATION
# ==========================================================

from app.rbac import get_allowed_pages

role = "admin"  # replace later with real role lookup
allowed = get_allowed_pages(role)

ALL_PAGES = [
    "Control Tower",
    "Analytics",
    "Upload Data",
    "Admin Dashboard",
    "Planning Settings"
]

visible_pages = ALL_PAGES if "ALL" in allowed else allowed

menu = st.sidebar.selectbox("Navigation", visible_pages)

# ==========================================================
# CONTROL TOWER
# ==========================================================

if menu == "Control Tower":

    st.title("🏭 Enterprise Control Tower")

    revenue, inv_value, service, util = calc_kpis()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💵 Sales Generated", f"₹{int(revenue):,}")
    k2.metric("🏦 Working Capital Locked", f"₹{int(inv_value):,}")
    k3.metric("🚚 Order Fulfilment Rate", f"{service}%")
    k4.metric("🏭 Factory Load", f"{util}%")

    st.divider()
    st.subheader("⚠️ Recommended Actions")

    for i, (action, item) in enumerate(actions):

        col1, col2, col3 = st.columns([4,1,1])
        col1.write(f"{action} → {item}")

        if col2.button("Approve", key=f"approve_{i}"):

            create_purchase_transaction(item, 100)
            from app.kafka_engine import send_event
send_event("PURCHASE_APPROVED", {"item": item})

            run_query("""
            INSERT INTO action_log VALUES (?,?,?,?)
            """,(action,item,"Approved",str(datetime.datetime.now())))

            st.success("Transaction executed & system updated.")
            st.rerun()

        if col3.button("Reject", key=f"reject_{i}"):

            run_query("""
            INSERT INTO action_log VALUES (?,?,?,?)
            """,(action,item,"Rejected",str(datetime.datetime.now())))

            st.error("Action rejected.")

    st.divider()
    st.subheader("📦 Projected Stock Overview")
    st.dataframe(balanced)

    st.divider()
    st.subheader("⚡ Instant Order Fulfilment Simulator")

    item_req = st.text_input("Product Needed")
    qty_req = st.number_input("Required Quantity",0,100000)

    if st.button("Find Supply Plan"):

        plan, shortage = fulfilment_engine(item_req, qty_req)

        if not plan:
            st.error("No supply found.")
        else:
            df_plan = pd.DataFrame(plan,
                                   columns=["Source","Allocated Qty","Contact"])
            st.dataframe(df_plan)

            if shortage > 0:
                st.error(f"Still Short: {shortage}")
            else:
                st.success("Demand fully satisfied.")

# ==========================================================
# ANALYTICS
# ==========================================================

elif menu == "Analytics":

    st.title("📊 Analytics Dashboard")

    if not inventory.empty:
        fig = px.bar(inventory, x="warehouse", y="on_hand",
                     color="category", title="Inventory by Warehouse")
        st.plotly_chart(fig, use_container_width=True)

    if not orders.empty:
        fig2 = px.pie(orders, names="category",
                      values="qty", title="Demand by Category")
        st.plotly_chart(fig2, use_container_width=True)

    if not forecast_df.empty:
        fig3 = px.line(forecast_df, x="date",
                       y=["qty","forecast"],
                       title="7-Day Rolling Forecast")
        st.plotly_chart(fig3, use_container_width=True)

# ==========================================================
# MULTI-TENANT LOGIN
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

    st.title("🔐 SupplySense Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        if username in USERS and USERS[username] == password:
            st.session_state.logged_in = True
            st.session_state.user_role = username
            st.success("Login successful.")
            st.experimental_rerun()
        else:
            st.error("Invalid credentials.")

    st.stop()


# ==========================================================
# ERP UI STYLE
# ==========================================================

st.markdown("""
<style>
.big-font {font-size:20px !important;}
.metric-card {
    background-color:#f0f2f6;
    padding:15px;
    border-radius:10px;
    text-align:center;
}
</style>
""", unsafe_allow_html=True)
# ==========================================================
# GEO SUPPLY NETWORK MAP
# ==========================================================

def geo_network_map():

    if inventory.empty:
        st.warning("No inventory data.")
        return

    # Dummy geo coordinates per warehouse (customize later)
    geo_map = {
        "Chennai WH": (13.08,80.27),
        "Cold Storage": (13.10,80.25),
        "Grain Warehouse": (11.01,76.96),
        "Grocery WH": (9.92,78.12)
    }

    map_data = []

    for _,row in inventory.iterrows():
        wh = row["warehouse"]
        if wh in geo_map:
            lat,lon = geo_map[wh]
            map_data.append({
                "lat":lat,
                "lon":lon,
                "size":row["on_hand"]
            })

    map_df = pd.DataFrame(map_data)

    if not map_df.empty:
        st.map(map_df)

# ==========================================================
# UPLOAD ENGINE
# ==========================================================

elif menu == "Upload Data":

    st.title("📤 Upload Dataset")

    table = st.selectbox("Select Table",
                         ["orders","inventory",
                          "suppliers","capacity","supply_pool"])

    file = st.file_uploader("Upload CSV")

    if file:

        df = pd.read_csv(file)
        df.columns = df.columns.str.lower().str.replace(" ","_")

        df.to_sql(table, get_conn(), if_exists="append", index=False)

        st.success("Upload successful.")
        st.rerun()

# ==========================================================
# MANUAL ENTRY
# ==========================================================

elif menu == "Manual Entry":

    st.title("➕ Add Manual Order")

    item = st.text_input("Item")
    qty = st.number_input("Quantity")

    if st.button("Add Order"):

        run_query("""
        INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)
        """,(
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
        ))

        st.success("Order Added.")
        st.rerun()

# ==========================================================
# ADMIN DASHBOARD
# ==========================================================

elif menu == "Admin Dashboard":

    st.title("👑 Admin Control Panel")

    st.subheader("Orders")
    st.dataframe(orders)

    st.subheader("Inventory")
    st.dataframe(inventory)

    st.subheader("Suppliers")
    st.dataframe(suppliers)

    st.subheader("Supply Pool")
    st.dataframe(supply_pool)

    st.subheader("System Tables")
    tables = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table';",
        get_conn()
    )
    st.dataframe(tables)

# ==========================================================
# PLANNING SETTINGS
# ==========================================================

elif menu == "Planning Settings":

    st.title("⚙️ Planning Parameters")

    safety = st.slider("Safety Stock",50,500,150)
    lead = st.slider("Lead Time (Days)",1,15,5)
    moq = st.slider("Minimum Order Quantity",50,500,200)

    if st.button("Save Settings"):

        run_query("DELETE FROM planning_params WHERE persona=?",
                  (persona,))

        run_query("""
        INSERT INTO planning_params VALUES (?,?,?,?)
        """,(persona,safety,lead,moq))

        st.success("Planning parameters saved.")

# ==========================================================
# SYSTEM SETTINGS
# ==========================================================

elif menu == "System Settings":

    st.title("⚙️ System Settings")

    if st.button("Backup Database"):
        st.success("Database backup simulated.")

    if st.button("View Action Logs"):
        logs = get_table("action_log")
        st.dataframe(logs)

from app.billing import create_checkout

if st.button("Upgrade to Pro"):
    url = create_checkout("price_xxxxx")
    st.write("Proceed to payment:", url)
        # ==========================================================
# PART 4 – ENTERPRISE INTELLIGENCE EXTENSION
# ==========================================================

# ==========================================================
# 1️⃣ AI PLANNING ASSISTANT (Context-Aware)
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
    ai_question = st.sidebar.text_input("Ask SupplySense AI")

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
                    {"role":"system","content":"You are an enterprise supply chain planner."},
                    {"role":"user","content":context_data + "\n\nQuestion: " + ai_question}
                ]
            )

            st.sidebar.success(response.choices[0].message.content)

        except:
            st.sidebar.warning("AI temporarily unavailable.")


# ==========================================================
# 2️⃣ DEMAND SPIKE SIMULATOR
# ==========================================================

st.sidebar.subheader("📈 Demand Spike Simulator")

if st.sidebar.button("Simulate 200% Demand Spike"):

    if not orders.empty:

        run_query("""
        UPDATE orders
        SET qty = qty * 2
        """)

        st.sidebar.success("Demand spike simulated.")
        st.rerun()


# ==========================================================
# 3️⃣ MULTI-WAREHOUSE TRANSFER ENGINE
# ==========================================================

def transfer_inventory(item, qty, from_wh, to_wh):

    run_query("""
    UPDATE inventory
    SET on_hand = on_hand - ?
    WHERE item=? AND warehouse=?
    """,(qty,item,from_wh))

    run_query("""
    UPDATE inventory
    SET on_hand = on_hand + ?
    WHERE item=? AND warehouse=?
    """,(qty,item,to_wh))

    run_query("""
    INSERT INTO tasks VALUES (?,?,?)
    """,(f"Transferred {qty} {item} from {from_wh} to {to_wh}",
         "Warehouse","Completed"))


st.sidebar.subheader("🌍 Warehouse Transfer")

transfer_item = st.sidebar.text_input("Transfer Item")
transfer_qty = st.sidebar.number_input("Transfer Qty",0,100000)
from_wh = st.sidebar.text_input("From Warehouse")
to_wh = st.sidebar.text_input("To Warehouse")

if st.sidebar.button("Execute Transfer"):
    transfer_inventory(transfer_item,transfer_qty,from_wh,to_wh)
    st.sidebar.success("Transfer completed.")
    st.rerun()


# ==========================================================
# 4️⃣ STRIPE BILLING ARCHITECTURE (SAFE STRUCTURE)
# ==========================================================

st.sidebar.subheader("💳 Subscription Billing")

subscription_plan = st.sidebar.selectbox(
    "Select Plan",
    ["Free","Pro ₹999/mo","Enterprise ₹2999/mo"]
)

if subscription_plan == "Free":
    st.sidebar.info("Limited Features Enabled")

elif subscription_plan == "Pro ₹999/mo":
    st.sidebar.success("Pro Features Enabled")

else:
    st.sidebar.success("Enterprise Ultra Enabled")


# (Stripe backend hook placeholder – ready for integration)
def stripe_checkout():
    # Placeholder for Stripe integration
    return "Stripe checkout initiated"


if st.sidebar.button("Upgrade Plan"):
    st.sidebar.success(stripe_checkout())


# ==========================================================
# 5️⃣ SUPPLIER-SPECIFIC WHATSAPP AUTO ALERT
# ==========================================================

def send_supplier_alert(supplier_name, message):

    supplier_row = suppliers[suppliers["supplier"]==supplier_name]

    if supplier_row.empty:
        return

    try:
        from twilio.rest import Client
        client = Client(st.secrets["TWILIO_SID"], st.secrets["TWILIO_TOKEN"])

        whatsapp_number = supplier_row.iloc[0]["whatsapp"]

        client.messages.create(
            from_='whatsapp:+14155238886',
            body=message,
            to=f'whatsapp:{whatsapp_number}'
        )

    except:
        pass


# Auto-trigger supplier alerts for stockouts
for action, item in actions:
    if "🚨" in action:

        supplier_match = inventory[inventory["item"]==item]

        if not supplier_match.empty:
            supplier_name = supplier_match.iloc[0]["supplier"]
            send_supplier_alert(
                supplier_name,
                f"URGENT: Immediate replenishment required for {item}"
            )


# ==========================================================
# END OF ENTERPRISE ULTRA+
# ==========================================================
