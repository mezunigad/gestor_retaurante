from flask import Flask, render_template, request, redirect, url_for, g, current_app, jsonify, flash
import sqlite3, datetime, os, threading

# Optional escpos import; app works without it but printing will be disabled.
try:
    from escpos.printer import Usb
    ESC_POS_AVAILABLE = True
except Exception as e:
    ESC_POS_AVAILABLE = False
    
# Configuración de Flask
app = Flask(__name__)
app.secret_key = 'epicuro_secret_key_2024'  # Esto es importante    

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
        # Sándwiches existentes...
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
        
        # Completos
        ("COMPLETO ITALIANO", "COMPLETO", "—"),
        ("COMPLETO DINÁMICO", "COMPLETO", "—"),
        ("COMPLETO GRINGO", "COMPLETO", "—"),
        
        # Bebestibles organizados por categoría
        ("COCA COLA", "BEBIDA", "—"),
        ("FANTA", "BEBIDA", "—"),
        ("SPRITE", "BEBIDA", "—"),
        ("PEPSI", "BEBIDA", "—"),
        ("AGUA MINERAL", "BEBIDA", "—"),
        ("AGUA CON GAS", "BEBIDA", "—"),
        ("RED BULL", "ENERGÉTICA", "—"),
        ("MONSTER", "ENERGÉTICA", "—"),
        ("BURN", "ENERGÉTICA", "—"),
        ("JUGO NATURAL NARANJA", "JUGO", "—"),
        ("JUGO NATURAL FRUTILLA", "JUGO", "—"),
        ("JUGO NATURAL PIÑA", "JUGO", "—"),
        ("JUGO EN CAJA", "JUGO", "—"),
        
        # Productos de Cafetería (nueva categoría)
        ("CAFÉ EXPRESO", "CAFETERÍA", "—"),
        ("CAFÉ AMERICANO", "CAFETERÍA", "—"),
        ("CAPUCHINO", "CAFETERÍA", "—"),
        ("LATTE", "CAFETERÍA", "—"),
        ("MOCACCINO", "CAFETERÍA", "—"),
        ("TÉ NEGRO", "CAFETERÍA", "—"),
        ("TÉ VERDE", "CAFETERÍA", "—"),
        ("CHOCOLATE CALIENTE", "CAFETERÍA", "—")
    ]
    for name, cat, protein in defaults:
        cur.execute("SELECT id FROM products WHERE name = ?", (name,))
        if not cur.fetchone():
            # Asignar precios según categoría
            if cat == "SANDWICH":
                price = 10000
            elif cat == "COMPLETO":
                price = 8000  # Precio para completos
            elif cat == "ENERGÉTICA":
                price = 2000
            elif cat == "JUGO":
                price = 1500
            elif cat == "CAFETERÍA":  # Precio para productos de cafetería
                price = 2400
            else:  # BEBIDA
                price = 1200
                
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
            # Asignar precios por defecto según categoría
            if category == "SANDWICH":
                price = 10000
            elif category == "COMPLETO":
                price = 8000
            elif category == "ENERGÉTICA":
                price = 2000
            elif category == "JUGO":
                price = 1500
            elif category == "CAFETERÍA":
                price = 2500
            else:  # BEBIDA
                price = 1200
            cost = int(price * 0.3)
        
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
        
        # Validación en el servidor
        if not customer:
            flash("El nombre del cliente es obligatorio", "error")
            return redirect(url_for("orders"))
        
        # Verificar que hay al menos un producto con cantidad > 0
        has_products = False
        for key, val in request.form.items():
            if key.startswith("qty_"):
                try:
                    if int(val) > 0:
                        has_products = True
                        break
                except:
                    continue
        
        if not has_products:
            flash("Debes agregar al menos un producto a la comanda", "error")
            return redirect(url_for("orders"))
        
        # Si pasa las validaciones, crear la comanda
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
    
    # Obtener completos
    cur.execute("SELECT * FROM products WHERE category='COMPLETO' ORDER BY name")
    completos = cur.fetchall()
    
    # Obtener bebestibles por categoría
    cur.execute("SELECT * FROM products WHERE category='BEBIDA' ORDER BY name")
    bebidas = cur.fetchall()
    
    cur.execute("SELECT * FROM products WHERE category='ENERGÉTICA' ORDER BY name")
    energeticas = cur.fetchall()
    
    cur.execute("SELECT * FROM products WHERE category='JUGO' ORDER BY name")
    jugos = cur.fetchall()
    
    # Obtener productos de cafetería (nueva consulta)
    cur.execute("SELECT * FROM products WHERE category='CAFETERÍA' ORDER BY name")
    cafeteria = cur.fetchall()
    
    # Definir opciones de proteína y sandwiches que las requieren
    protein_options = ["Churrasco", "Lomito", "Pollo"]
    protein_sandwiches = ["A LO POBRE", "BARROS LUCO", "CHACARERO", "ITALIANO"]
    
    return render_template("orders.html", 
                         sandwiches=sandwiches, 
                         completos=completos,
                         bebidas=bebidas,
                         energeticas=energeticas,
                         jugos=jugos,
                         cafeteria=cafeteria,  # Nueva variable pasada al template
                         protein_options=protein_options,
                         protein_sandwiches=protein_sandwiches)
# Aqui termina @app.route("/orders", methods=["GET", "POST"])

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

'''@app.route("/orders/list")
def orders_list():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 50")
    orders = cur.fetchall()
    return render_template("orders_list.html", orders=orders)'''
    
@app.route("/orders/list")
def orders_list():
    db = get_db()
    cur = db.cursor()
    
    # Consulta actualizada para asegurar que total_venta nunca sea NULL
    cur.execute("""
        SELECT o.*, 
               COALESCE(SUM(p.price * oi.qty), 0) as total_venta,
               COUNT(oi.id) as total_items
        FROM orders o
        LEFT JOIN order_items oi ON o.id = oi.order_id
        LEFT JOIN products p ON oi.product_id = p.id
        GROUP BY o.id
        ORDER BY o.id DESC 
        LIMIT 50
    """)
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
        
@app.route("/products/<int:pid>/delete", methods=["POST"])
def delete_product(pid):
    db = get_db()
    cur = db.cursor()
    
    # Verificar si el producto existe
    cur.execute("SELECT * FROM products WHERE id = ?", (pid,))
    product = cur.fetchone()
    
    if not product:
        return "Producto no encontrado", 404
    
    # Verificar si el producto está siendo usado en alguna orden
    cur.execute("SELECT COUNT(*) as count FROM order_items WHERE product_id = ?", (pid,))
    usage = cur.fetchone()
    
    if usage["count"] > 0:
        return "No se puede eliminar: este producto tiene órdenes asociadas", 400
    
    # Eliminar el producto
    cur.execute("DELETE FROM products WHERE id = ?", (pid,))
    db.commit()
    
    return redirect(url_for("products"))

# --- API Endpoints para Reportería ---
@app.route("/reports")
def reports():
    """Página principal de reportes"""
    return render_template("reports.html")

@app.route("/api/ventas")
def api_ventas():
    """Endpoint para obtener datos de ventas con filtros opcionales"""
    try:
        # Obtener parámetros de filtro si existen
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        categoria = request.args.get('categoria')
        
        db = get_db()
        cur = db.cursor()
        
        # Construir consulta base
        query = """
            SELECT 
                o.id as idPedido, 
                o.created_at as fecha, 
                o.customer_name as cliente,
                p.name as producto, 
                p.category as categoria, 
                oi.qty as cantidad, 
                p.price as precio, 
                (p.price * oi.qty) as total,
                (p.cost * oi.qty) as costo
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            WHERE 1=1
        """
        params = []
        
        # Aplicar filtros si se proporcionan
        if fecha_inicio:
            query += " AND DATE(o.created_at) >= ?"
            params.append(fecha_inicio)
        if fecha_fin:
            query += " AND DATE(o.created_at) <= ?"
            params.append(fecha_fin)
        if categoria:
            query += " AND p.category = ?"
            params.append(categoria)
            
        query += " ORDER BY o.created_at DESC"
        
        cur.execute(query, params)
        ventas = cur.fetchall()
        
        # Convertir a lista de diccionarios
        resultados = []
        for v in ventas:
            resultados.append({
                'idPedido': v['idPedido'],
                'fecha': v['fecha'],
                'cliente': v['cliente'] or 'Cliente no especificado',
                'producto': v['producto'],
                'categoria': v['categoria'],
                'cantidad': v['cantidad'],
                'precio': v['precio'],
                'total': v['total'],
                'costo': v['costo']
            })
        
        return jsonify(resultados)
        
    except Exception as e:
        print(f"Error en API ventas: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/api/metricas")
def api_metricas():
    """Endpoint para obtener métricas resumidas de ventas"""
    try:
        # Obtener parámetros de filtro si existen
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        categoria = request.args.get('categoria')
        
        db = get_db()
        cur = db.cursor()
        
        # Construir consulta base
        query = """
            SELECT 
                COUNT(DISTINCT o.id) as total_pedidos,
                SUM(p.price * oi.qty) as ventas_totales,
                SUM(p.cost * oi.qty) as costos_totales,
                COUNT(DISTINCT o.customer_name) as clientes_unicos
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            WHERE 1=1
        """
        params = []
        
        # Aplicar filtros si se proporcionan
        if fecha_inicio:
            query += " AND DATE(o.created_at) >= ?"
            params.append(fecha_inicio)
        if fecha_fin:
            query += " AND DATE(o.created_at) <= ?"
            params.append(fecha_fin)
        if categoria:
            query += " AND p.category = ?"
            params.append(categoria)
        
        cur.execute(query, params)
        metricas = cur.fetchone()
        
        # Calcular métricas adicionales
        ventas_totales = metricas['ventas_totales'] or 0
        costos_totales = metricas['costos_totales'] or 0
        total_pedidos = metricas['total_pedidos'] or 0
        clientes_unicos = metricas['clientes_unicos'] or 0
        
        ticket_promedio = ventas_totales / total_pedidos if total_pedidos > 0 else 0
        margen_beneficio = ((ventas_totales - costos_totales) / ventas_totales * 100) if ventas_totales > 0 else 0
        
        return jsonify({
            'ventas_totales': ventas_totales,
            'costos_totales': costos_totales,
            'total_pedidos': total_pedidos,
            'clientes_unicos': clientes_unicos,
            'ticket_promedio': ticket_promedio,
            'margen_beneficio': margen_beneficio
        })
        
    except Exception as e:
        print(f"Error en API métricas: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/api/ventas-por-categoria")
def api_ventas_por_categoria():
    """Endpoint para obtener ventas agrupadas por categoría"""
    try:
        # Obtener parámetros de filtro si existen
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        db = get_db()
        cur = db.cursor()
        
        query = """
            SELECT 
                p.category as categoria,
                SUM(p.price * oi.qty) as ventas_totales,
                SUM(p.cost * oi.qty) as costos_totales,
                SUM(oi.qty) as cantidad_vendida
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            WHERE 1=1
        """
        params = []
        
        # Aplicar filtros si se proporcionan
        if fecha_inicio:
            query += " AND DATE(o.created_at) >= ?"
            params.append(fecha_inicio)
        if fecha_fin:
            query += " AND DATE(o.created_at) <= ?"
            params.append(fecha_fin)
            
        query += " GROUP BY p.category ORDER BY ventas_totales DESC"
        
        cur.execute(query, params)
        categorias = cur.fetchall()
        
        resultados = []
        for c in categorias:
            resultados.append({
                'categoria': c['categoria'],
                'ventas_totales': c['ventas_totales'],
                'costos_totales': c['costos_totales'],
                'cantidad_vendida': c['cantidad_vendida']
            })
        
        return jsonify(resultados)
        
    except Exception as e:
        print(f"Error en API ventas por categoría: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/api/top-productos")
def api_top_productos():
    """Endpoint para obtener los productos más vendidos"""
    try:
        # Obtener parámetros de filtro si existen
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        limite = request.args.get('limite', 5)
        
        db = get_db()
        cur = db.cursor()
        
        query = """
            SELECT 
                p.name as producto,
                p.category as categoria,
                SUM(oi.qty) as cantidad_vendida,
                SUM(p.price * oi.qty) as ventas_totales
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            WHERE 1=1
        """
        params = []
        
        # Aplicar filtros si se proporcionan
        if fecha_inicio:
            query += " AND DATE(o.created_at) >= ?"
            params.append(fecha_inicio)
        if fecha_fin:
            query += " AND DATE(o.created_at) <= ?"
            params.append(fecha_fin)
            
        query += " GROUP BY p.id ORDER BY ventas_totales DESC LIMIT ?"
        params.append(limite)
        
        cur.execute(query, params)
        productos = cur.fetchall()
        
        resultados = []
        for p in productos:
            resultados.append({
                'producto': p['producto'],
                'categoria': p['categoria'],
                'cantidad_vendida': p['cantidad_vendida'],
                'ventas_totales': p['ventas_totales']
            })
        
        return jsonify(resultados)
        
    except Exception as e:
        print(f"Error en API top productos: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/api/ventas-por-dia")
def api_ventas_por_dia():
    """Endpoint para obtener ventas agrupadas por día"""
    try:
        # Obtener parámetros de filtro si existen
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        db = get_db()
        cur = db.cursor()
        
        query = """
            SELECT 
                DATE(o.created_at) as fecha,
                COUNT(DISTINCT o.id) as total_pedidos,
                SUM(p.price * oi.qty) as ventas_totales,
                SUM(oi.qty) as cantidad_vendida
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            WHERE 1=1
        """
        params = []
        
        # Aplicar filtros si se proporcionan
        if fecha_inicio:
            query += " AND DATE(o.created_at) >= ?"
            params.append(fecha_inicio)
        if fecha_fin:
            query += " AND DATE(o.created_at) <= ?"
            params.append(fecha_fin)
            
        query += " GROUP BY DATE(o.created_at) ORDER BY fecha"
        
        cur.execute(query, params)
        dias = cur.fetchall()
        
        resultados = []
        for d in dias:
            resultados.append({
                'fecha': d['fecha'],
                'total_pedidos': d['total_pedidos'],
                'ventas_totales': d['ventas_totales'],
                'cantidad_vendida': d['cantidad_vendida']
            })
        
        return jsonify(resultados)
        
    except Exception as e:
        print(f"Error en API ventas por día: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/api/ventas-por-dia-semana")
def api_ventas_por_dia_semana():
    """Endpoint para obtener ventas agrupadas por día de la semana"""
    try:
        # Obtener parámetros de filtro si existen
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        db = get_db()
        cur = db.cursor()
        
        query = """
            SELECT 
                CASE CAST(strftime('%w', o.created_at) AS INTEGER)
                    WHEN 0 THEN 'Domingo'
                    WHEN 1 THEN 'Lunes'
                    WHEN 2 THEN 'Martes'
                    WHEN 3 THEN 'Miércoles'
                    WHEN 4 THEN 'Jueves'
                    WHEN 5 THEN 'Viernes'
                    ELSE 'Sábado'
                END as dia_semana,
                SUM(p.price * oi.qty) as ventas_totales,
                COUNT(DISTINCT o.id) as total_pedidos
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            WHERE 1=1
        """
        params = []
        
        # Aplicar filtros si se proporcionan
        if fecha_inicio:
            query += " AND DATE(o.created_at) >= ?"
            params.append(fecha_inicio)
        if fecha_fin:
            query += " AND DATE(o.created_at) <= ?"
            params.append(fecha_fin)
            
        query += " GROUP BY dia_semana ORDER BY ventas_totales DESC"
        
        cur.execute(query, params)
        dias = cur.fetchall()
        
        # Ordenar por días de la semana (no por monto)
        dias_semana_orden = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        resultados_ordenados = []
        
        for dia in dias_semana_orden:
            encontrado = next((d for d in dias if d['dia_semana'] == dia), None)
            if encontrado:
                resultados_ordenados.append({
                    'dia_semana': encontrado['dia_semana'],
                    'ventas_totales': encontrado['ventas_totales'],
                    'total_pedidos': encontrado['total_pedidos']
                })
            else:
                resultados_ordenados.append({
                    'dia_semana': dia,
                    'ventas_totales': 0,
                    'total_pedidos': 0
                })
        
        return jsonify(resultados_ordenados)
        
    except Exception as e:
        print(f"Error en API ventas por día de semana: {e}")
        return jsonify({'error': str(e)}), 500
        
@app.route("/orders/<int:order_id>/delete", methods=["POST"])
def delete_order(order_id):
    db = get_db()
    cur = db.cursor()
    
    try:
        # Primero eliminar los items de la orden
        cur.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
        
        # Luego eliminar la orden
        cur.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        
        db.commit()
        return redirect(url_for("orders_list"))
    except Exception as e:
        db.rollback()
        return f"Error eliminando la orden: {str(e)}", 500

@app.route("/orders/<int:order_id>/edit", methods=["GET", "POST"])
def edit_order(order_id):
    db = get_db()
    cur = db.cursor()
    
    if request.method == "POST":
        nuevo_nombre = request.form["customer_name"].strip()
        
        try:
            cur.execute("UPDATE orders SET customer_name = ? WHERE id = ?", 
                       (nuevo_nombre, order_id))
            db.commit()
            return redirect(url_for("orders_list"))
        except Exception as e:
            db.rollback()
            return f"Error actualizando la orden: {str(e)}", 500
    
    # GET - Mostrar formulario de edición
    cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cur.fetchone()
    
    if not order:
        return "Orden no encontrada", 404
        
    return render_template("edit_order.html", order=order)

# Agregar filtro personalizado para formato de números
@app.template_filter('format')
def format_number(value, format_type=','):
    """Filtro para formatear números con separadores de miles"""
    if value is None:
        return "0"
    try:
        if format_type == ',':
            return "{:,.0f}".format(float(value)).replace(",", ".")
        return str(value)
    except (ValueError, TypeError):
        return str(value)

        
    
if __name__ == '__main__':
    # Inicializar la base de datos antes de ejecutar la aplicación
    setup_database()
    # Si no quieres impresión automática, deja ENABLE_PRINTER=False.
    app.run(debug=True)