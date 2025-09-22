import os
import time # <-- Make sure time is imported
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
from psycopg2.extras import RealDictCursor
import psycopg2
import threading
from urllib.parse import quote_plus
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# Use price_fetcher from your workspace (has fallback to requests/BS4)
from price_fetcher import update_all_prices, fetch_price

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "a-secure-default-secret-key-for-dev")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:admin@localhost/postgres")

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()

    # Users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            user_name VARCHAR(100) NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            mobile_number VARCHAR(20),
            address TEXT,
            password_hash TEXT
        );
    """)

    # Vendors table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vendors (
            vendor_id SERIAL PRIMARY KEY,
            vendor_name VARCHAR(100) NOT NULL,
            website_url TEXT
        );
    """)

    # Products table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id SERIAL PRIMARY KEY,
            product_name VARCHAR(120) NOT NULL,
            category VARCHAR(100)
        );
    """)

    # Product Prices table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_prices (
            price_id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(product_id),
            vendor_id INTEGER REFERENCES vendors(vendor_id),
            product_price FLOAT NOT NULL
        );
    """)

    # Alerts table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            alert_id SERIAL PRIMARY KEY,
            user_id_reference INTEGER REFERENCES users(user_id),
            product_id_reference INTEGER REFERENCES products(product_id),
            price_alert FLOAT NOT NULL
        );
    """)

    # Deals table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            deal_id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(product_id),
            vendor_id INTEGER REFERENCES vendors(vendor_id),
            deal_price FLOAT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL
        );
    """)

    conn.commit()
    cur.close()
    conn.close()

# Run table creation once
create_tables()

# --- LOGIN REQUIRED DECORATOR ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# --- LOGIN/LOGOUT ROUTES ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id, password_hash FROM users WHERE user_name=%s OR email=%s", (username, username))
        row = cur.fetchone()
        cur.close(); conn.close()
        if row and row[1] and check_password_hash(row[1], password):
            session["user"] = username
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- REGISTER ROUTE ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        if not username or not email or not password:
            flash("All fields required", "danger")
            return render_template("register.html")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE user_name=%s OR email=%s", (username, email))
        if cur.fetchone():
            flash("Username or email already exists", "danger")
            cur.close(); conn.close()
            return render_template("register.html")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;")
        cur.execute(
            "INSERT INTO users (user_name, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, generate_password_hash(password))
        )
        conn.commit()
        cur.close(); conn.close()
        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

# --- MAIN PAGE ROUTES (all require login) ---
@app.route("/")
@login_required
def index():
    return render_template("dashboard.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/add-user")
@login_required
def add_user_page():
    return render_template("add_user.html")

@app.route("/add-vendor")
@login_required
def add_vendor_page():
    return render_template("add_vendor.html")

@app.route("/add-product")
@login_required
def add_product_page():
    return render_template("add_product.html")

@app.route("/set-alert")
@login_required
def set_alert_page():
    return render_template("set_alert.html")

@app.route("/get-deals")
@login_required
def get_deals_page():
    return render_template("get_deals.html")

@app.route("/view-products")
@login_required
def view_products_page():
    return render_template("view_products.html")

@app.route("/view-vendors")
@login_required
def view_vendors_page():
    return render_template("view_vendors.html")

@app.route("/track-products")
@login_required
def track_products_page():
    return render_template("track_products.html")

@app.route("/edit-vendor")
@login_required
def edit_vendor_page():
    return render_template("edit_vendor.html")

@app.route('/my-deals-page')
@login_required
def my_deals_page():
    return render_template('my_deals.html')

@app.route('/add-deal-page')
@login_required
def add_deal_page():
    return render_template('add_deal.html')

# --- API ENDPOINTS ---
@app.route('/users', methods=['POST'])
def add_user():
    data = request.get_json() or request.form
    name = data.get('user_name')
    email = data.get('email')
    mobile = data.get('mobile_number')
    address = data.get('address')
    if not name or not email:
        return jsonify({"message": "user_name and email required"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_name, email, mobile_number, address)
        VALUES (%s, %s, %s, %s) RETURNING user_id
    """, (name, email, mobile, address))
    user_id = cur.fetchone()[0]
    conn.commit()
    cur.close(); conn.close()
    return jsonify({"message":"User added", "user_id": user_id})

@app.route('/vendors', methods=['POST'])
def add_vendor():
    data = request.get_json() or request.form
    name = data.get('vendor_name')
    url = data.get('website_url')
    if not name:
        return jsonify({"message":"vendor_name required"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO vendors (vendor_name, website_url) VALUES (%s,%s) RETURNING vendor_id", (name, url))
    vendor_id = cur.fetchone()[0]
    conn.commit()
    cur.close(); conn.close()
    return jsonify({"message":"Vendor added", "vendor_id": vendor_id})

@app.route('/products', methods=['POST'])
def add_product():
    data = request.get_json() or request.form
    pname = data.get('product_name')
    category = data.get('category')
    vendors = data.get('vendors') or []
    if not pname:
        return jsonify({"message":"product_name required"}), 400
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("INSERT INTO products (product_name, category) VALUES (%s,%s) RETURNING product_id", (pname, category))
    product_id = cur.fetchone()['product_id']
    for v in vendors:
        vname = v.get('vendor_name')
        vurl = v.get('vendor_website') or v.get('website') or v.get('vendor_url')
        price = v.get('price')
        if not vname:
            continue
        cur.execute("SELECT vendor_id FROM vendors WHERE vendor_name = %s", (vname,))
        row = cur.fetchone()
        if row:
            vendor_id = row['vendor_id']
            if vurl:
                cur.execute("UPDATE vendors SET website_url = %s WHERE vendor_id = %s", (vurl, vendor_id))
        else:
            cur.execute("INSERT INTO vendors (vendor_name, website_url) VALUES (%s,%s) RETURNING vendor_id", (vname, vurl))
            vendor_id = cur.fetchone()['vendor_id']
        if price is not None:
            cur.execute("INSERT INTO product_prices (product_id, vendor_id, product_price) VALUES (%s,%s,%s)", (product_id, vendor_id, price))
    conn.commit()
    cur.close(); conn.close()
    return jsonify({"message":"Product added", "product_id": product_id})

@app.route('/alerts', methods=['POST'])
@login_required
def add_alert():
    data = request.get_json()
    product_id = data.get("product_id")
    price_alert = data.get("price_alert")
    user_name = session["user"]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_name = %s", (user_name,))
    user_row = cur.fetchone()
    if not user_row:
        cur.close(); conn.close()
        return jsonify({"message": "User not found"}), 400
    user_id = user_row[0]
    cur.execute(
        "INSERT INTO alerts (user_id_reference, product_id_reference, price_alert) VALUES (%s, %s, %s)",
        (user_id, product_id, price_alert)
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Alert set successfully!"})

@app.route('/deals/<int:user_id>', methods=['GET'])
def get_user_deals(user_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT a.alert_id, a.price_alert, p.product_id, p.product_name,
               v.vendor_id, v.vendor_name, v.website_url, pp.product_price as current_price
        FROM alerts a
        JOIN products p ON a.product_id_reference = p.product_id
        LEFT JOIN product_prices pp ON pp.product_id = p.product_id
        LEFT JOIN vendors v ON pp.vendor_id = v.vendor_id
        WHERE a.user_id_reference = %s
    """, (user_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    results = []
    by_product = {}
    for r in rows:
        pid = r['product_id']
        if pid not in by_product:
            by_product[pid] = {
                "product_id": pid,
                "product_name": r['product_name'],
                "alert_price": r['price_alert'],
                "vendors": []
            }
        by_product[pid]['vendors'].append({
            "vendor_id": r['vendor_id'],
            "vendor_name": r['vendor_name'],
            "vendor_website": r['website_url'],
            "current_price": r['current_price']
        })
    results = list(by_product.values())
    return jsonify({"user_id": user_id, "deals": results})

@app.route('/products', methods=['GET'])
def list_products():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM products ORDER BY product_name")
    prods = cur.fetchall()
    for p in prods:
        cur.execute("""
            SELECT v.vendor_id, v.vendor_name, v.website_url, pp.product_price
            FROM product_prices pp JOIN vendors v ON pp.vendor_id = v.vendor_id
            WHERE pp.product_id = %s
        """, (p['product_id'],))
        p['vendors'] = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(prods)

@app.route('/vendors', methods=['GET'])
def list_vendors():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM vendors ORDER BY vendor_name")
    vendors = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(vendors)

@app.route('/users', methods=['GET'])
def list_users():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT user_id, user_name, email, mobile_number, address FROM users ORDER BY user_name")
    users = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(users)

@app.route('/vendors/<int:vendor_id>', methods=['GET', 'PUT', 'DELETE'])
def vendor_detail(vendor_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'GET':
        cur.execute("SELECT * FROM vendors WHERE vendor_id = %s", (vendor_id,))
        vendor = cur.fetchone()
        cur.close(); conn.close()
        if not vendor:
            return jsonify({"message": "Vendor not found"}), 404
        return jsonify(vendor)
    if request.method == 'PUT':
        data = request.get_json()
        cur.execute("UPDATE vendors SET vendor_name=%s, website_url=%s WHERE vendor_id=%s",
                    (data.get('vendor_name'), data.get('website_url'), vendor_id))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"message": "Vendor updated successfully"})
    if request.method == 'DELETE':
        cur.execute("DELETE FROM product_prices WHERE vendor_id = %s", (vendor_id,))
        cur.execute("DELETE FROM vendors WHERE vendor_id = %s", (vendor_id,))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"message": "Vendor deleted"})

@app.route('/products/<int:product_id>', methods=['GET', 'PUT', 'DELETE'])
def product_detail(product_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'GET':
        cur.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
        product = cur.fetchone()
        if not product:
            cur.close(); conn.close()
            return jsonify({"message": "Product not found"}), 404
        cur.execute("""
            SELECT v.vendor_id, v.vendor_name, v.website_url, pp.product_price
            FROM product_prices pp JOIN vendors v ON pp.vendor_id = v.vendor_id
            WHERE pp.product_id = %s
        """, (product_id,))
        product['vendors'] = cur.fetchall()
        cur.close(); conn.close()
        return jsonify(product)

    if request.method == 'PUT':
        data = request.get_json()
        cur.execute("UPDATE products SET product_name=%s, category=%s WHERE product_id=%s",
                    (data.get('product_name'), data.get('category'), product_id))
        for v in data.get('vendors', []):
            vendor_id = v.get('vendor_id')
            if not vendor_id:
                cur.execute("SELECT vendor_id FROM vendors WHERE vendor_name = %s", (v.get('vendor_name'),))
                row = cur.fetchone()
                if row:
                    vendor_id = row['vendor_id']
                else:
                    cur.execute("INSERT INTO vendors (vendor_name, website_url) VALUES (%s, %s) RETURNING vendor_id",
                                (v.get('vendor_name'), v.get('vendor_website')))
                    vendor_id = cur.fetchone()['vendor_id']
            cur.execute("SELECT price_id FROM product_prices WHERE product_id=%s AND vendor_id=%s", (product_id, vendor_id))
            pr = cur.fetchone()
            if pr:
                cur.execute("UPDATE product_prices SET product_price=%s WHERE price_id=%s", (v.get('price'), pr['price_id']))
            else:
                cur.execute("INSERT INTO product_prices (product_id, vendor_id, product_price) VALUES (%s, %s, %s)",
                            (product_id, vendor_id, v.get('price')))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"message": "Product updated"})

    if request.method == 'DELETE':
        cur.execute("DELETE FROM product_prices WHERE product_id = %s", (product_id,))
        cur.execute("DELETE FROM alerts WHERE product_id_reference = %s", (product_id,))
        cur.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"message": "Product deleted"})

@app.route('/search', methods=['GET'])
def search_products():
    q = request.args.get('q')
    if not q:
        return jsonify({"message": "Query required"}), 400
    q_enc = quote_plus(q)
    results = []
    platform_urls = [
        ("Amazon", f"https://www.amazon.in/s?k={q_enc}"),
        ("Flipkart", f"https://www.flipkart.com/search?q={q_enc}"),
        ("Apple", f"https://www.apple.com/search/?q={q_enc}")
    ]
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT vendor_name, website_url FROM vendors WHERE website_url IS NOT NULL")
    vendor_rows = cur.fetchall()
    cur.close(); conn.close()
    for v in vendor_rows:
        if v['website_url']:
            platform_urls.append((v['vendor_name'], v['website_url']))
    for platform_name, url in platform_urls:
        try:
            price = fetch_price(url)
        except Exception:
            price = None
        results.append({
            "platform": platform_name,
            "url": url,
            "price": float(price) if price is not None else None
        })
    return jsonify({"query": q, "results": results})

def price_updater_loop(interval_seconds=300):
    """Background loop: refresh all vendor prices every interval_seconds."""
    # <-- CHANGE: Add a delay before the first run to allow the web server to start.
    print("Background worker started. Waiting 15 seconds before first price update.")
    time.sleep(15)
    
    while True:
        try:
            print("Starting background price update...")
            update_all_prices()
            print("Background price update finished.")
        except Exception as e:
            print(f"Price updater error: {e}")
        time.sleep(interval_seconds)

# Start background updater (daemon)
updater_thread = threading.Thread(target=price_updater_loop, args=(300,), daemon=True)
updater_thread.start()

@app.route("/api/track-products", methods=["GET"])
def api_track_products():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
            p.product_id, p.product_name, p.category,
            v.vendor_name, v.website_url, pp.product_price
        FROM product_prices pp
        JOIN products p ON pp.product_id = p.product_id
        JOIN vendors v ON pp.vendor_id = v.vendor_id
        ORDER BY p.product_id
    """)
    data = cur.fetchall()
    cur.close(); conn.close()
    product_map = {}
    for row in data:
        pid = row['product_id']
        if pid not in product_map:
            product_map[pid] = {
                "product_id": pid,
                "product_name": row['product_name'],
                "category": row['category'],
                "vendors": []
            }
        product_map[pid]["vendors"].append({
            "vendor_name": row['vendor_name'],
            "vendor_website": row['website_url'],
            "price": float(row['product_price']) if row['product_price'] is not None else None
        })
    results = list(product_map.values())
    return jsonify(results)

@app.route('/deals', methods=['GET'])
def get_deals():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT d.deal_id, d.product_id, d.vendor_id, d.deal_price, d.start_date, d.end_date,
               p.product_name, v.vendor_name
        FROM deals d
        JOIN products p ON d.product_id = p.product_id
        JOIN vendors v ON d.vendor_id = v.vendor_id
        WHERE d.end_date >= CURRENT_DATE
        ORDER BY d.start_date DESC
        LIMIT 10
    """)
    deals = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(deals)

@app.route('/my-deals', methods=['GET'])
@login_required
def my_deals():
    user = session["user"]
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT a.alert_id, a.product_id_reference AS product_id, a.price_alert, p.product_name, p.category
        FROM alerts a
        JOIN products p ON a.product_id_reference = p.product_id
        JOIN users u ON a.user_id_reference = u.user_id
        WHERE u.user_name = %s
        ORDER BY a.alert_id DESC
        LIMIT 20
    """, (user,))
    alerts = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(alerts)

@app.route('/add-deal', methods=['POST'])
@login_required
def add_deal():
    data = request.get_json()
    product_id = data.get("product_id")
    vendor_id = data.get("vendor_id")
    deal_price = data.get("deal_price")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    if not all([product_id, vendor_id, deal_price, start_date, end_date]):
        return jsonify({"message": "Missing fields"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO deals (product_id, vendor_id, deal_price, start_date, end_date) VALUES (%s, %s, %s, %s, %s)",
        (product_id, vendor_id, deal_price, start_date, end_date)
    )
    conn.commit()
    cur.close(); conn.close()
    return jsonify({"message": "Deal added successfully!"})


if __name__ == '__main__':
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() in ("true", "1", "t")
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=debug_mode)