from fastapi import FastAPI, Form, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3, os, shutil, urllib.parse, secrets
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'jaquis.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

EMPRESA_USER = os.environ.get("EMPRESA_USER", "jaquis")
EMPRESA_PASS = os.environ.get("EMPRESA_PASS", "reposteria2026")

app = FastAPI(title='JAQUIS Repostería Gourmet')
app.mount('/static', StaticFiles(directory=os.path.join(BASE_DIR, 'static')), name='static')
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, 'templates'))

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        delivery_date TEXT NOT NULL,
        delivery_time TEXT NOT NULL,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        total REAL NOT NULL,
        deposit_required INTEGER NOT NULL DEFAULT 0,
        deposit_amount REAL NOT NULL DEFAULT 0,
        packaging TEXT,
        notes TEXT,
        proof_path TEXT,
        status TEXT NOT NULL DEFAULT 'Recibido',
        created_at TEXT NOT NULL
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        action TEXT NOT NULL,
        detail TEXT NOT NULL,
        created_at TEXT NOT NULL
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        image TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1
    )''')
    count = cur.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    if count == 0:
        base_products = [
            ('Burbujas','Burbuja surtida',1000,'https://images.unsplash.com/photo-1486427944299-d1955d23e34d?q=80&w=1200&auto=format&fit=crop'),
            ('Burbujas','Burbuja salada',1000,'https://images.unsplash.com/photo-1509440159596-0249088772ff?q=80&w=1200&auto=format&fit=crop'),
            ('Burbujas','Burbuja combinada',1000,'https://images.unsplash.com/photo-1464306076886-da185f6a9d05?q=80&w=1200&auto=format&fit=crop'),
            ('Trenzas','Trenza de pollo',1000,'https://images.unsplash.com/photo-1608198093002-ad4e005484ec?q=80&w=1200&auto=format&fit=crop'),
            ('Trenzas','Trenza dulce de leche',1000,'https://images.unsplash.com/photo-1555507036-ab794f4ade2a?q=80&w=1200&auto=format&fit=crop'),
            ('Queques','Queque pequeño',12000,'https://images.unsplash.com/photo-1578985545062-69928b1d9587?q=80&w=1200&auto=format&fit=crop'),
            ('Queques','Queque mediano',16000,'https://images.unsplash.com/photo-1535254973040-607b474cb50d?q=80&w=1200&auto=format&fit=crop'),
            ('Queques','Queque grande',20000,'https://images.unsplash.com/photo-1563729784474-d77dbb933a9e?q=80&w=1200&auto=format&fit=crop'),
        ]
        cur.executemany('INSERT INTO products (category, name, price, image) VALUES (?,?,?,?)', base_products)
    conn.commit()
    conn.close()

init_db()

def check_auth(request: Request):
    return request.cookies.get("jaquis_auth") == "ok"

# ── Rutas públicas ────────────────────────────────────────────────────────────────

@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    conn = get_conn()
    products = conn.execute('SELECT * FROM products WHERE active=1 ORDER BY category, name').fetchall()
    conn.close()
    return templates.TemplateResponse('index.html', {'request': request, 'products': products})

@app.get('/pedido', response_class=HTMLResponse)
def order_form(request: Request):
    conn = get_conn()
    products = conn.execute('SELECT * FROM products WHERE active=1 ORDER BY category, name').fetchall()
    conn.close()
    return templates.TemplateResponse('order_form.html', {'request': request, 'products': products})

@app.post('/pedido')
async def create_order(
    customer_name: str = Form(...),
    phone: str = Form(...),
    delivery_date: str = Form(...),
    delivery_time: str = Form(...),
    product_name: str = Form(...),
    category: str = Form(...),
    quantity: int = Form(...),
    unit_price: float = Form(...),
    packaging: str = Form('Burbuja'),
    notes: str = Form(''),
    proof_file: UploadFile | None = File(None)
):
    total = quantity * unit_price
    deposit_required = 1 if quantity >= 10 else 0
    deposit_amount = round(total * 0.5, 2) if deposit_required else 0
    proof_path = ''
    if proof_file and proof_file.filename:
        safe_name = f"{int(datetime.now().timestamp())}_{proof_file.filename.replace(' ', '_')}"
        file_path = os.path.join(UPLOAD_DIR, safe_name)
        with open(file_path, 'wb') as buffer:
            shutil.copyfileobj(proof_file.file, buffer)
        proof_path = f'/static/uploads/{safe_name}'
    conn = get_conn()
    cur = conn.cursor()
    created_at = datetime.now().isoformat(timespec='seconds')
    cur.execute('''INSERT INTO orders
        (customer_name, phone, delivery_date, delivery_time, product_name, category, quantity, unit_price, total, deposit_required, deposit_amount, packaging, notes, proof_path, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (customer_name, phone, delivery_date, delivery_time, product_name, category, quantity, unit_price, total, deposit_required, deposit_amount, packaging, notes, proof_path, created_at)
    )
    order_id = cur.lastrowid
    cur.execute('INSERT INTO audit_log (order_id, action, detail, created_at) VALUES (?,?,?,?)',
                (order_id, 'CREATED', f'Pedido creado por {customer_name}', created_at))
    conn.commit()
    conn.close()

    deposito_linea = f"%0A%F0%9F%92%B5 Dep%C3%B3sito requerido (50%25): %E2%82%A1{int(deposit_amount)}" if deposit_required else ""
    notas_linea = f"%0A%F0%9F%93%9D Notas: {urllib.parse.quote(notes)}" if notes.strip() else ""
    empaque_linea = f"%0A%F0%9F%93%A6 Empaque: {urllib.parse.quote(packaging)}" if packaging else ""

    wa_text = (
        f"🍰 *JAQUIS Repostería Gourmet*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 *Pedido #{order_id}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Cliente: {customer_name}\n"
        f"📱 Teléfono: {phone}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛍️ Producto: {product_name}\n"
        f"📂 Categoría: {category}\n"
        f"🔢 Cantidad: {quantity}\n"
        f"💰 Precio unitario: ₡{int(unit_price)}\n"
        f"💳 *Total: ₡{int(total)}*\n"
        f"{'💵 Depósito requerido (50%): ₡' + str(int(deposit_amount)) + chr(10) if deposit_required else ''}"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Fecha de entrega: {delivery_date}\n"
        f"⏰ Hora de entrega: {delivery_time}\n"
        f"{'📦 Empaque: ' + packaging + chr(10) if packaging else ''}"
        f"{'📝 Notas: ' + notes + chr(10) if notes.strip() else ''}"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Estado: Recibido\n"
        f"🕐 Registrado: {created_at}"
    )

    wa_encoded = urllib.parse.quote(wa_text)
    wa_url = f"https://wa.me/50688140898?text={wa_encoded}"
    return RedirectResponse(
        url=f'/pedido-exito/{order_id}?wa={urllib.parse.quote(wa_url, safe="")}',
        status_code=303
    )

@app.get('/pedido-exito/{order_id}', response_class=HTMLResponse)
def order_success(request: Request, order_id: int, wa: str = ''):
    return templates.TemplateResponse('success.html', {
        'request': request, 'order_id': order_id, 'wa_url': urllib.parse.unquote(wa)
    })

# ── Login / Logout ────────────────────────────────────────────────────────────────

@app.get('/login', response_class=HTMLResponse)
def login_page(request: Request, error: str = ''):
    if check_auth(request):
        return RedirectResponse(url='/cocina', status_code=302)
    return templates.TemplateResponse('login.html', {'request': request, 'error': error})

@app.post('/login')
def login_post(username: str = Form(...), password: str = Form(...)):
    if secrets.compare_digest(username, EMPRESA_USER) and secrets.compare_digest(password, EMPRESA_PASS):
        response = RedirectResponse(url='/cocina', status_code=303)
        response.set_cookie(key="jaquis_auth", value="ok", httponly=True, samesite="lax")
        return response
    return RedirectResponse(url='/login?error=1', status_code=303)

@app.get('/logout')
def logout():
    response = RedirectResponse(url='/login', status_code=303)
    response.delete_cookie("jaquis_auth")
    return response

# ── Rutas protegidas ──────────────────────────────────────────────────────────────

@app.get('/cocina', response_class=HTMLResponse)
def kitchen(request: Request):
    if not check_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    conn = get_conn()
    orders = conn.execute('SELECT * FROM orders ORDER BY delivery_date, delivery_time, id DESC').fetchall()
    conn.close()
    return templates.TemplateResponse('kitchen.html', {'request': request, 'orders': orders})

@app.post('/estado/{order_id}/{new_status}')
def change_status(order_id: int, new_status: str, request: Request):
    if not check_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('UPDATE orders SET status=? WHERE id=?', (new_status, order_id))
    cur.execute('INSERT INTO audit_log (order_id, action, detail, created_at) VALUES (?,?,?,?)',
                (order_id, 'STATUS', f'Estado cambiado a {new_status}', datetime.now().isoformat(timespec='seconds')))
    conn.commit()
    conn.close()
    return RedirectResponse('/cocina', status_code=303)

@app.get('/reportes', response_class=HTMLResponse)
def reports(request: Request):
    if not check_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    conn = get_conn()
    summary = conn.execute('''SELECT category, product_name, SUM(quantity) as qty, SUM(total) as amount
                              FROM orders GROUP BY category, product_name ORDER BY category, qty DESC''').fetchall()
    daily = conn.execute('''SELECT delivery_date, COUNT(*) as orders_count, SUM(total) as total_amount
                            FROM orders GROUP BY delivery_date ORDER BY delivery_date DESC''').fetchall()
    conn.close()
    return templates.TemplateResponse('reports.html', {'request': request, 'summary': summary, 'daily': daily})

# ── Catálogo CRUD ─────────────────────────────────────────────────────────────────

@app.get('/catalogo', response_class=HTMLResponse)
def catalogo(request: Request):
    if not check_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    conn = get_conn()
    products = conn.execute('SELECT * FROM products ORDER BY category, name').fetchall()
    conn.close()
    return templates.TemplateResponse('catalogo.html', {'request': request, 'products': products})

@app.get('/catalogo/nuevo', response_class=HTMLResponse)
def catalogo_nuevo(request: Request):
    if not check_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    return templates.TemplateResponse('catalogo_form.html', {
        'request': request, 'product': None, 'action': '/catalogo/crear'
    })

@app.post('/catalogo/crear')
def catalogo_crear(
    request: Request,
    category: str = Form(...),
    name: str = Form(...),
    price: float = Form(...),
    image: str = Form(...)
):
    if not check_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    conn = get_conn()
    conn.execute('INSERT INTO products (category, name, price, image) VALUES (?,?,?,?)', (category, name, price, image))
    conn.commit()
    conn.close()
    return RedirectResponse('/catalogo', status_code=303)

@app.get('/catalogo/editar/{product_id}', response_class=HTMLResponse)
def catalogo_editar(request: Request, product_id: int):
    if not check_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    conn = get_conn()
    product = conn.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
    conn.close()
    if not product:
        return RedirectResponse('/catalogo', status_code=302)
    return templates.TemplateResponse('catalogo_form.html', {
        'request': request, 'product': product, 'action': f'/catalogo/actualizar/{product_id}'
    })

@app.post('/catalogo/actualizar/{product_id}')
def catalogo_actualizar(
    request: Request,
    product_id: int,
    category: str = Form(...),
    name: str = Form(...),
    price: float = Form(...),
    image: str = Form(...),
    active: int = Form(1)
):
    if not check_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    conn = get_conn()
    conn.execute('UPDATE products SET category=?, name=?, price=?, image=?, active=? WHERE id=?',
                 (category, name, price, image, active, product_id))
    conn.commit()
    conn.close()
    return RedirectResponse('/catalogo', status_code=303)

@app.post('/catalogo/eliminar/{product_id}')
def catalogo_eliminar(request: Request, product_id: int):
    if not check_auth(request):
        return RedirectResponse(url='/login', status_code=302)
    conn = get_conn()
    conn.execute('UPDATE products SET active=0 WHERE id=?', (product_id,))
    conn.commit()
    conn.close()
    return RedirectResponse('/catalogo', status_code=303)
Listo
