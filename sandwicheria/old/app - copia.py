from flask import Flask, render_template, request, redirect, url_for, g, current_app
import sqlite3, datetime, os, threading

# Optional escpos import; app works without it but printing will be disabled.
try:
    from escpos.printer import Usb
    ESC_POS_AVAILABLE = True
except Exception as e:
    ESC_POS_AVAILABLE = False

# --- Config: ajusta esto según tu impresora ---
# Para detectar ids en Linux: `lsusb` -> Bus 002 Device 003: ID 04b8:0202 EPSON
VENDOR_ID = 0x04b8   # ejemplo: Epson 0x04b8
PRODUCT_ID = 0x0202  # ejemplo: modelo
USB_INTERFACE = 0     # interfaz USB; a veces 0 o 1
ENABLE_PRINTER = False  # cambiar a True si quieres intentar imprimir automáticamente

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "sandwich.db")

app = Flask(__name__)

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    cur = db.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        category TEXT,
        base_protein TEXT,
        price INTEGER,
        cost INTEGER
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        customer_name TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        product_id INTEGER,
        qty INTEGER,
        note TEXT,
        FOREIGN KEY(order_id) REFERENCES orders(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    )""")
    db.commit()

def seed_defaults():
    db = get_db()
    cur = db.cursor()
    defaults = [
        ("BARROS LUCO", "SANDWICH", "Churrasco"),
        ("ITALIANO", "SANDWICH", "Lomito"),
        ("CHACARERO", "SANDWICH", "Churrasco"),
        ("A LO POBRE", "SANDWICH", "Churrasco"),
        ("LUCO DELUXE", "SANDWICH", "Lomito"),
        ("EPICURO", "SANDWICH", "Lomito"),
        ("PICARO", "SANDWICH", "Pollo"),
        ("COLCHAGUINO", "SANDWICH", "Arrollado"),
        ("VEGGIE", "SANDWICH", "Seitán"),
        ("DE NIÑO", "SANDWICH", "Churrasco"),
        ("COMPLETO JUNAEB", "SANDWICH", "Churrasco"),
        # Example bebestibles
        ("BEBIDA LATA", "BEBESTIBLE", "—"),
        ("AGUA MINERAL", "BEBESTIBLE", "—"),
        ("JUGO NATURAL", "BEBESTIBLE", "—")
    ]
    for name, cat, protein in defaults:
        cur.execute("SELECT id FROM products WHERE name = ?", (name,))
        if not cur.fetchone():
            price = 10000 if cat=="SANDWICH" else (1200 if name=="BEBIDA LATA" else 1000)
            cost = int(price * 0.3)
            cur.execute("INSERT INTO products (name, category, base_protein, price, cost) VALUES (?, ?, ?, ?, ?)",
                        (name, cat, protein, price, cost))
    db.commit()

def setup_database():
    """Inicializa la base de datos y carga los datos por defecto"""
    with app.app_context():
        init_db()
        seed_defaults()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

@app.route("/")
def index():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM products ORDER BY category, name")
    products = cur.fetchall()
    return render_template("index.html", products=products)

@app.route("/products", methods=["GET", "POST"])
def products():
    db = get_db()
    cur = db.cursor()
    if request.method == "POST":
        name = request.form["name"].strip().upper()
        category = request.form["category"].strip().upper()
        base_protein = request.form["base_protein"].strip().title()
        try:
            price = int(request.form["price"])
            cost = int(request.form["cost"])
        except:
            price = 10000 if category=="SANDWICH" else 1000
            cost = int(price*0.3)
        # INSERT OR IGNORE, but update if exists
        cur.execute("SELECT id FROM products WHERE name = ?", (name,))
        existing = cur.fetchone()
        if existing:
            cur.execute("UPDATE products SET category=?, base_protein=?, price=?, cost=? WHERE name=?",
                        (category, base_protein, price, cost, name))
        else:
            cur.execute("INSERT INTO products (name, category, base_protein, price, cost) VALUES (?, ?, ?, ?, ?)",
                        (name, category, base_protein, price, cost))
        db.commit()
        return redirect(url_for("products"))
    cur.execute("SELECT * FROM products ORDER BY category, name")
    products = cur.fetchall()
    return render_template("products.html", products=products)

@app.route("/products/<int:pid>/edit", methods=["GET", "POST"])
def edit_product(pid):
    db = get_db()
    cur = db.cursor()
    if request.method == "POST":
        name = request.form["name"].strip().upper()
        category = request.form["category"].strip().upper()
        base_protein = request.form["base_protein"].strip().title()
        price = int(request.form["price"])
        cost = int(request.form["cost"])
        cur.execute("UPDATE products SET name=?, category=?, base_protein=?, price=?, cost=? WHERE id=?",
                    (name, category, base_protein, price, cost, pid))
        db.commit()
        return redirect(url_for("products"))
    cur.execute("SELECT * FROM products WHERE id = ?", (pid,))
    prod = cur.fetchone()
    if not prod:
        return "Producto no encontrado", 404
    return render_template("edit_product.html", p=prod)

@app.route("/orders", methods=["GET", "POST"])
def orders():
    db = get_db()
    cur = db.cursor()
    if request.method == "POST":
        customer = request.form.get("customer_name", "").strip()
        created_at = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
        cur.execute("INSERT INTO orders (created_at, customer_name) VALUES (?, ?)", (created_at, customer))
        order_id = cur.lastrowid
        
        # Lista de sandwiches que requieren selección de proteína
        protein_sandwiches = ["A LO POBRE", "BARROS LUCO", "CHACARERO", "ITALIANO"]
        
        for key, val in request.form.items():
            if key.startswith("qty_"):
                pid = int(key.split("_",1)[1])
                try:
                    qty = int(val)
                except:
                    qty = 0
                
                # Obtener el nombre del producto para verificar si requiere proteína
                cur.execute("SELECT name FROM products WHERE id = ?", (pid,))
                product = cur.fetchone()
                product_name = product["name"] if product else ""
                
                note = request.form.get(f"note_{pid}", "").strip()
                
                # Si es un sandwich que requiere proteína, agregar la proteína seleccionada al inicio de la nota
                if qty > 0 and product_name in protein_sandwiches:
                    selected_protein = request.form.get(f"protein_{pid}", "").strip()
                    if selected_protein:
                        # Combinar proteína seleccionada con nota adicional
                        if note:
                            note = f"{selected_protein} - {note}"
                        else:
                            note = selected_protein
                
                if qty > 0:
                    cur.execute("INSERT INTO order_items (order_id, product_id, qty, note) VALUES (?, ?, ?, ?)",
                                (order_id, pid, qty, note))
        db.commit()
        # Launch printing in background to avoid blocking the request (if enabled)
        if ENABLE_PRINTER:
            threading.Thread(target=print_to_thermal, args=(order_id,)).start()
        return redirect(url_for("comanda", order_id=order_id))
    
    # GET
    cur.execute("SELECT * FROM products WHERE category='SANDWICH' ORDER BY name")
    sandwiches = cur.fetchall()
    cur.execute("SELECT * FROM products WHERE category='BEBESTIBLE' ORDER BY name")
    drinks = cur.fetchall()
    
    # Definir opciones de proteína y sandwiches que las requieren
    protein_options = ["Churrasco", "Lomito", "Pollo"]
    protein_sandwiches = ["A LO POBRE", "BARROS LUCO", "CHACARERO", "ITALIANO"]
    
    return render_template("orders.html", 
                         sandwiches=sandwiches, 
                         drinks=drinks,
                         protein_options=protein_options,
                         protein_sandwiches=protein_sandwiches)

@app.route("/comanda/<int:order_id>")
def comanda(order_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cur.fetchone()
    if not order:
        return "Orden no encontrada", 404
    cur.execute("""SELECT oi.*, p.name as product_name, p.base_protein, p.price, p.cost, p.category
                   FROM order_items oi JOIN products p ON oi.product_id = p.id
                   WHERE oi.order_id = ?""", (order_id,))
    items = cur.fetchall()
    subtotal = sum(item["price"] * item["qty"] for item in items)
    total_cost = sum(item["cost"] * item["qty"] for item in items)
    return render_template("comanda.html", order=order, items=items, subtotal=subtotal, total_cost=total_cost)

@app.route("/orders/list")
def orders_list():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 50")
    orders = cur.fetchall()
    return render_template("orders_list.html", orders=orders)

# --- Thermal printing function ---
def print_to_thermal(order_id):
    if not ESC_POS_AVAILABLE:
        current_app.logger.warning("python-escpos no disponible; impresión omitida")
        return
    try:
        db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        cur = db.cursor()
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cur.fetchone()
        cur.execute("""SELECT oi.*, p.name as product_name, p.base_protein, p.price
                       FROM order_items oi JOIN products p ON oi.product_id = p.id
                       WHERE oi.order_id = ?""", (order_id,))
        items = cur.fetchall()
        # connect to printer
        p = Usb(VENDOR_ID, PRODUCT_ID, USB_INTERFACE, timeout=0, profile=None)
        # Header compacto
        p.text("SANDWICHERÍA - COMANDA\n")
        p.text(f"#{order_id} - {order['created_at'][:16]}\n")
        if order['customer_name']:
            p.text(f"Cliente: {order['customer_name']}\n")
        p.text("---------------\n")
        for it in items:
            line = f"{it['qty']} x {it['product_name']}\n"
            p.text(line)
            
            # Note retrieval from DB
            cur2 = db.cursor()
            cur2.execute("SELECT note FROM order_items WHERE order_id=? AND product_id=? LIMIT 1", (order_id, it['product_id']))
            row = cur2.fetchone()
            
            # Mostrar proteína seleccionada o proteína base
            protein_shown = False
            if row and row['note']:
                # Si la nota contiene una proteína (Churrasco, Lomito, Pollo), mostrarla
                note_parts = row['note'].split(' - ')
                if note_parts[0] in ['Churrasco', 'Lomito', 'Pollo']:
                    p.text(f"  {note_parts[0]}\n")
                    protein_shown = True
                    # Si hay más información en la nota después del guión
                    if len(note_parts) > 1:
                        p.text(f"  Nota: {' - '.join(note_parts[1:])}\n")
                else:
                    # Si no es una proteína, mostrar la nota completa
                    p.text(f"  Nota: {row['note']}\n")
            
            # Si no se mostró proteína personalizada, mostrar la proteína base del producto
            if not protein_shown and it['base_protein'] and it['base_protein'] != "—":
                p.text(f"  {it['base_protein']}\n")
        p.text("¡Gracias!\n")
        p.cut()
        db.close()
    except Exception as e:
        current_app.logger.error(f"Error imprimiendo en térmica: {e}")

if __name__ == '__main__':
    # Inicializar la base de datos antes de ejecutar la aplicación
    setup_database()
    # Si no quieres impresión automática, deja ENABLE_PRINTER=False.
    app.run(debug=True)