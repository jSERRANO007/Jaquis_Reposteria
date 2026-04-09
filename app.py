from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3, os, shutil, urllib.parse
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'jaquis.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title='JAQUIS Repostería Gourmet')
app.mount('/static', StaticFiles(directory=os.path.join(BASE_DIR, 'static')), name='static')
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, 'templates'))

PRODUCTS = [
    {'category':'Burbujas','name':'Burbuja surtida','price':1000,'image':'https://images.unsplash.com/photo-1486427944299-d1955d23e34d?q=80&w=1200&auto=format&fit=crop'},
    {'category':'Burbujas','name':'Burbuja salada','price':1000,'image':'https://images.unsplash.com/photo-1509440159596-0249088772ff?q=80&w=1200&auto=format&fit=crop'},
    {'category':'Burbujas','name':'Burbuja combinada','price':1000,'image':'https://images.unsplash.com/photo-1464306076886-da185f6a9d05?q=80&w=1200&auto=format&fit=crop'},
    {'category':'Trenzas','name':'Trenza de pollo','price':1000,'image':'https://images.unsplash.com/photo-1608198093002-ad4e005484ec?q=80&w=1200&auto=format&fit=crop'},
    {'category':'Trenzas','name':'Trenza dulce de leche','price':1000,'image':'https://images.unsplash.com/photo-1555507036-ab794f4ade2a?q=80&w=1200&auto=format&fit=crop'},
    {'category':'Queques','name':'Queque pequeño','price':12000,'image':'https://images.unsplash.com/photo-1578985545062-69928b1d9587?q=80&w=1200&auto=format&fit=crop'},
    {'category':'Queques','name':'Queque mediano','price':16000,'image':'https://images.unsplash.com/photo-1535254973040-607b474cb50d?q=80&w=1200&auto=format&fit=crop'},
    {'category':'Queques','name':'Queque grande','price':20000,'image':'https://images.unsplash.com/photo-1563729784474-d77dbb933a9e?q=80&w=1200&auto=format&fit=crop'},
]


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
    conn.commit()
    conn.close()

init_db()

@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse('index.html', {'request': request, 'products': PRODUCTS})

@app.get('/pedido', response_class=HTMLResponse)
def order_form(request: Request):
    return templates.TemplateResponse('order_form.html', {'request': request, 'products': PRODUCTS})

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
    conn = get_conn(); cur = conn.cursor()
    created_at = datetime.now().isoformat(timespec='seconds')
    cur.execute('''INSERT INTO orders
        (customer_name, phone, delivery_date, delivery_time, product_name, category, quantity, unit_price, total, deposit_required, deposit_amount, packaging, notes, proof_path, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (customer_name, phone, delivery_date, delivery_time, product_name, category, quantity, unit_price, total, deposit_required, deposit_amount, packaging, notes, proof_path, created_at)
    )
    order_id = cur.lastrowid
    cur.execute('INSERT INTO audit_log (order_id, action, detail, created_at) VALUES (?,?,?,?)',
                (order_id, 'CREATED', f'Pedido creado por {customer_name}', created_at))
    conn.commit(); conn.close()

    message = f"Hola, quiero confirmar el pedido #{order_id}%0ACliente: {customer_name}%0ATeléfono: {phone}%0AProducto: {product_name}%0ACantidad: {quantity}%0ATotal: ₡{int(total)}%0AFecha entrega: {delivery_date} {delivery_time}"
    wa_url = f"https://wa.me/50688140898?text={message}"
    return RedirectResponse(url=f'/pedido-exito/{order_id}?wa={urllib.parse.quote(wa_url, safe="")}', status_code=303)

@app.get('/pedido-exito/{order_id}', response_class=HTMLResponse)
def order_success(request: Request, order_id: int, wa: str = ''):
    return templates.TemplateResponse('success.html', {'request': request, 'order_id': order_id, 'wa_url': urllib.parse.unquote(wa)})

@app.get('/cocina', response_class=HTMLResponse)
def kitchen(request: Request):
    conn = get_conn(); orders = conn.execute('SELECT * FROM orders ORDER BY delivery_date, delivery_time, id DESC').fetchall(); conn.close()
    return templates.TemplateResponse('kitchen.html', {'request': request, 'orders': orders})

@app.post('/estado/{order_id}/{status}')
def change_status(order_id: int, status: str):
    conn = get_conn(); cur = conn.cursor()
    cur.execute('UPDATE orders SET status=? WHERE id=?', (status, order_id))
    cur.execute('INSERT INTO audit_log (order_id, action, detail, created_at) VALUES (?,?,?,?)',
                (order_id, 'STATUS', f'Estado cambiado a {status}', datetime.now().isoformat(timespec='seconds')))
    conn.commit(); conn.close()
    return RedirectResponse('/cocina', status_code=303)

@app.get('/reportes', response_class=HTMLResponse)
def reports(request: Request):
    conn = get_conn()
    summary = conn.execute('''SELECT category, product_name, SUM(quantity) as qty, SUM(total) as amount
                              FROM orders GROUP BY category, product_name ORDER BY category, qty DESC''').fetchall()
    daily = conn.execute('''SELECT delivery_date, COUNT(*) as orders_count, SUM(total) as total_amount
                            FROM orders GROUP BY delivery_date ORDER BY delivery_date DESC''').fetchall()
    conn.close()
    return templates.TemplateResponse('reports.html', {'request': request, 'summary': summary, 'daily': daily})
