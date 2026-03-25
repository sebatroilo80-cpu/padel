from flask import Flask, request, redirect, render_template_string, session
import sqlite3
from datetime import datetime
import urllib.parse
import os
import json
import requests
from markupsafe import escape
from functools import wraps

app = Flask(__name__)
@app.route("/test")
def home():
    return "Padel app funcionando 🚀"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "padel.db")
app.secret_key = "padel37_secret_key_cambiar_si_queres"

# =========================================================
# LOGIN
# =========================================================

ADMIN_USER = "admin"
ADMIN_PASS = "padel37"

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logueado"):
            return redirect("/login")
        return fn(*args, **kwargs)
    return wrapper


# =========================================================
# MERCADO PAGO
# =========================================================
# REEMPLAZAR ESTO CON TUS CREDENCIALES NUEVAS
MP_ACCESS_TOKEN = "APP_USR-3703014412541433-032419-8324ea40fcfa6d67ecdd36fcf03fd66f-1099436820"
MP_PUBLIC_KEY = "APP_USR-363b213c-9926-4f7b-9cd1-3008a5b01e3a"

# URL pública real cuando subas la app (ej: https://padel37.onrender.com)
PUBLIC_BASE_URL = "https://padel-9bk4.onrender.com"

BASE_URL_MP = "https://api.mercadopago.com"


# =========================================================
# HELPERS SEGUROS
# =========================================================

def e(valor):
    return escape("" if valor is None else str(valor))


def js_str(valor):
    return json.dumps("" if valor is None else str(valor), ensure_ascii=False)


def to_int(valor, default=0):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return default


def to_float(valor, default=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return default


# =========================================================
# DB
# =========================================================

def get_db():
    return sqlite3.connect(DB)


def ensure_config_table(c):
    c.execute("""
        CREATE TABLE IF NOT EXISTS config (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)

    cols = [col[1] for col in c.execute("PRAGMA table_info(config)").fetchall()]
    if "clave" not in cols or "valor" not in cols:
        c.execute("DROP TABLE IF EXISTS config")
        c.execute("""
            CREATE TABLE config (
                clave TEXT PRIMARY KEY,
                valor TEXT
            )
        """)

    defaults = {
        "precio_1h_dia": "25000",
        "precio_1h_noche": "30000",
        "precio_90m_dia": "32000",
        "precio_90m_noche": "40000",
        "senia_porcentaje": "0.30",
        "hora_apertura": "08:00",
        "hora_cierre": "23:30"
    }

    for clave, valor in defaults.items():
        existe = c.execute(
            "SELECT clave FROM config WHERE clave=?",
            (clave,)
        ).fetchone()
        if not existe:
            c.execute(
                "INSERT INTO config (clave, valor) VALUES (?, ?)",
                (clave, valor)
            )


def init_db():
    conn = get_db()
    c = conn.cursor()

    ensure_config_table(c)

    c.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            telefono TEXT
        )
    """)

    cols_clientes = [col[1] for col in c.execute("PRAGMA table_info(clientes)").fetchall()]
    if "nombre" not in cols_clientes:
        c.execute("ALTER TABLE clientes ADD COLUMN nombre TEXT")
    if "telefono" not in cols_clientes:
        c.execute("ALTER TABLE clientes ADD COLUMN telefono TEXT")

    c.execute("""
        CREATE TABLE IF NOT EXISTS reservas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            telefono TEXT,
            cancha INTEGER,
            fecha TEXT,
            hora TEXT,
            duracion INTEGER DEFAULT 90,
            metodo_pago TEXT,
            color TEXT,
            precio INTEGER,
            estado TEXT,
            monto_pagado INTEGER DEFAULT 0,
            monto_reembolso INTEGER DEFAULT 0,
            precio_total INTEGER DEFAULT 0,
            mp_tipo_pago TEXT,
            mp_preference_id TEXT,
            mp_payment_id TEXT,
            mp_status TEXT,
            mp_checkout_url TEXT
        )
    """)

    cols = [col[1] for col in c.execute("PRAGMA table_info(reservas)").fetchall()]

    if "telefono" not in cols:
        c.execute("ALTER TABLE reservas ADD COLUMN telefono TEXT")
    if "duracion" not in cols:
        c.execute("ALTER TABLE reservas ADD COLUMN duracion INTEGER DEFAULT 90")
    if "metodo_pago" not in cols:
        c.execute("ALTER TABLE reservas ADD COLUMN metodo_pago TEXT")
    if "color" not in cols:
        c.execute("ALTER TABLE reservas ADD COLUMN color TEXT")
    if "precio" not in cols:
        c.execute("ALTER TABLE reservas ADD COLUMN precio INTEGER DEFAULT 0")
    if "estado" not in cols:
        c.execute("ALTER TABLE reservas ADD COLUMN estado TEXT DEFAULT 'Confirmado'")
    if "monto_pagado" not in cols:
        c.execute("ALTER TABLE reservas ADD COLUMN monto_pagado INTEGER DEFAULT 0")
    if "monto_reembolso" not in cols:
        c.execute("ALTER TABLE reservas ADD COLUMN monto_reembolso INTEGER DEFAULT 0")
    if "precio_total" not in cols:
        c.execute("ALTER TABLE reservas ADD COLUMN precio_total INTEGER DEFAULT 0")
    if "mp_tipo_pago" not in cols:
        c.execute("ALTER TABLE reservas ADD COLUMN mp_tipo_pago TEXT")
    if "mp_preference_id" not in cols:
        c.execute("ALTER TABLE reservas ADD COLUMN mp_preference_id TEXT")
    if "mp_payment_id" not in cols:
        c.execute("ALTER TABLE reservas ADD COLUMN mp_payment_id TEXT")
    if "mp_status" not in cols:
        c.execute("ALTER TABLE reservas ADD COLUMN mp_status TEXT")
    if "mp_checkout_url" not in cols:
        c.execute("ALTER TABLE reservas ADD COLUMN mp_checkout_url TEXT")

    c.execute("""
        UPDATE reservas
        SET duracion = 90
        WHERE duracion IS NULL OR duracion = 0
    """)

    c.execute("""
        UPDATE reservas
        SET precio_total = COALESCE(precio, 0)
        WHERE COALESCE(precio_total, 0) = 0
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS egresos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            concepto TEXT,
            monto INTEGER
        )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================================================
# CONFIG
# =========================================================

def get_config():
    conn = get_db()
    c = conn.cursor()
    ensure_config_table(c)
    rows = c.execute("SELECT clave, valor FROM config").fetchall()
    conn.commit()
    conn.close()

    data = {r[0]: r[1] for r in rows}

    return {
        "precio_1h_dia": to_int(data.get("precio_1h_dia"), 25000),
        "precio_1h_noche": to_int(data.get("precio_1h_noche"), 30000),
        "precio_90m_dia": to_int(data.get("precio_90m_dia"), 32000),
        "precio_90m_noche": to_int(data.get("precio_90m_noche"), 40000),
        "senia_porcentaje": to_float(data.get("senia_porcentaje"), 0.30),
        "hora_apertura": data.get("hora_apertura", "08:00"),
        "hora_cierre": data.get("hora_cierre", "23:30"),
    }


def set_config_valores(precio_1h_dia, precio_1h_noche, precio_90m_dia, precio_90m_noche, senia_porcentaje, hora_apertura, hora_cierre):
    conn = get_db()
    c = conn.cursor()
    ensure_config_table(c)

    valores = {
        "precio_1h_dia": str(precio_1h_dia),
        "precio_1h_noche": str(precio_1h_noche),
        "precio_90m_dia": str(precio_90m_dia),
        "precio_90m_noche": str(precio_90m_noche),
        "senia_porcentaje": str(senia_porcentaje),
        "hora_apertura": str(hora_apertura),
        "hora_cierre": str(hora_cierre),
    }

    for clave, valor in valores.items():
        c.execute("""
            INSERT INTO config (clave, valor)
            VALUES (?, ?)
            ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor
        """, (clave, valor))

    conn.commit()
    conn.close()


# =========================================================
# HELPERS APP
# =========================================================

def render_page(title, content):
    links_admin = ""
    if session.get("admin_logueado"):
        links_admin = """
        <a href="/">Inicio</a>
        <a href="/clientes">Clientes</a>
        <a href="/reservas">Reservas</a>
        <a href="/caja">Caja</a>
        <a href="/precios">Precios</a>
        <a href="/logout">Salir</a>
        """

    return render_template_string(f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{e(title)}</title>
      <script src="https://sdk.mercadopago.com/js/v2"></script>
      <style>
        * {{
          box-sizing: border-box;
        }}
        body {{
          font-family: Arial, sans-serif;
          background: #111111;
          color: #f6e7a8;
          margin: 0;
          padding: 0;
        }}
        .topbar {{
          background: linear-gradient(90deg, #111111, #1a1a1a);
          color: #d4af37;
          padding: 18px 24px;
          border-bottom: 2px solid #d4af37;
        }}
        .topbar h1 {{
          margin: 0;
          font-size: 30px;
        }}
        .nav {{
          background: #181818;
          border-bottom: 1px solid #3b3312;
          padding: 12px 20px;
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
        }}
        .nav a {{
          text-decoration: none;
          background: #252525;
          color: #f6e7a8;
          padding: 9px 14px;
          border-radius: 8px;
          font-weight: bold;
          border: 1px solid #4a3d11;
          font-size: 14px;
        }}
        .nav a:hover {{
          background: #2d2d2d;
        }}
        .container {{
          padding: 20px;
        }}
        .card {{
          background: #1a1a1a;
          border: 1px solid #3d320e;
          border-radius: 14px;
          padding: 18px;
          margin-bottom: 18px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.25);
        }}
        .card h2, .card h3 {{
          margin-top: 0;
          color: #d4af37;
        }}
        .row {{
          display: flex;
          gap: 14px;
          flex-wrap: wrap;
        }}
        .row > div {{
          min-width: 180px;
          flex: 1;
        }}
        label {{
          display: block;
          font-weight: bold;
          margin-bottom: 6px;
          color: #f6e7a8;
          font-size: 14px;
        }}
        input, select {{
          width: 100%;
          padding: 10px 12px;
          border-radius: 8px;
          border: 1px solid #5a4b17;
          background: #111111;
          color: #f8f1c7;
          margin-bottom: 12px;
        }}
        button, .btn {{
          display: inline-block;
          border: none;
          text-decoration: none;
          cursor: pointer;
          padding: 10px 14px;
          border-radius: 8px;
          font-weight: bold;
          font-size: 14px;
        }}
        .btn-primary {{
          background: #d4af37;
          color: #111111;
        }}
        .btn-danger {{
          background: #dc2626;
          color: white;
        }}
        .btn-secondary {{
          background: #374151;
          color: white;
        }}
        .btn-success {{
          background: #16a34a;
          color: white;
        }}
        .btn-small {{
          padding: 6px 10px;
          font-size: 12px;
        }}
        .table-wrap {{
          overflow-x: auto;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          background: #161616;
        }}
        th {{
          background: #26210f;
          color: #d4af37;
          text-align: center;
          padding: 12px;
          border-bottom: 1px solid #4b3d10;
          font-size: 14px;
        }}
        td {{
          padding: 12px;
          border-bottom: 1px solid #2e2e2e;
          font-size: 14px;
          vertical-align: top;
          color: #f6e7a8;
          text-align: center;
        }}
        .err {{
          background: #991b1b;
          color: white;
          padding: 10px;
          border-radius: 8px;
          margin-bottom: 12px;
          font-weight: bold;
        }}
        .ok {{
          background: #166534;
          color: white;
          padding: 10px;
          border-radius: 8px;
          margin-bottom: 12px;
          font-weight: bold;
        }}
        .muted {{
          color: #c7b978;
          font-size: 13px;
        }}
        .summary-grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 12px;
        }}
        .summary-box {{
          background: #202020;
          border: 1px solid #4d3f11;
          border-radius: 12px;
          padding: 15px;
        }}
        .summary-box h4 {{
          margin: 0 0 8px 0;
          color: #d4af37;
        }}
        .summary-box p {{
          margin: 0;
          font-size: 28px;
          font-weight: bold;
        }}
        .color-confirmado {{
          background: #16a34a;
          color: white;
        }}
        .color-pendiente {{
          background: #f59e0b;
          color: #111111;
        }}
        .color-cancelado {{
          background: #dc2626;
          color: white;
        }}
      </style>
    </head>
    <body>
      <div class="topbar">
        <h1>Pádel 37</h1>
      </div>

      <div class="nav">
        {links_admin}
        <a href="/reservar">Reservar online</a>
      </div>

      <div class="container">
        {content}
      </div>
    </body>
    </html>
    """)


def hora_a_minutos(hora_str):
    h, m = hora_str.split(":")
    return int(h) * 60 + int(m)


def minutos_a_hora(mins):
    return f"{mins//60:02d}:{mins%60:02d}"


def generar_slots(inicio="08:00", fin="23:30", paso=30):
    inicio_m = hora_a_minutos(inicio)
    fin_m = hora_a_minutos(fin)
    slots = []
    actual = inicio_m
    while actual <= fin_m:
        slots.append(minutos_a_hora(actual))
        actual += paso
    return slots


def bloques_que_ocupa(hora_inicio, duracion=90, paso=30):
    inicio_m = hora_a_minutos(hora_inicio)
    fin = inicio_m + duracion
    bloques = []
    actual = inicio_m
    while actual < fin:
        bloques.append(minutos_a_hora(actual))
        actual += paso
    return bloques


def fecha_es_hoy(fecha_str):
    return fecha_str == datetime.now().strftime("%Y-%m-%d")


def hora_minima_reservable(fecha_str, margen_minutos=60):
    ahora = datetime.now()
    cfg = get_config()
    hora_apertura = cfg["hora_apertura"]
    hora_cierre = cfg["hora_cierre"]
    fecha_hoy_str = ahora.strftime("%Y-%m-%d")

    if fecha_str < fecha_hoy_str:
        return None

    if fecha_str > fecha_hoy_str:
        return hora_apertura

    minutos_actuales = ahora.hour * 60 + ahora.minute + margen_minutos
    resto = minutos_actuales % 30
    if resto != 0:
        minutos_actuales += (30 - resto)

    if minutos_actuales < hora_a_minutos(hora_apertura):
        minutos_actuales = hora_a_minutos(hora_apertura)

    if minutos_actuales > hora_a_minutos(hora_cierre):
        return None

    return minutos_a_hora(minutos_actuales)


def horario_habilitado_para_reservar(fecha_str, hora_str, margen_minutos=60):
    hora_minima = hora_minima_reservable(fecha_str, margen_minutos)
    if hora_minima is None:
        return False
    return hora_a_minutos(hora_str) >= hora_a_minutos(hora_minima)


def get_estado_y_color(estado):
    estado = (estado or "").strip().lower()
    if estado == "pendiente":
        return "Pendiente", "orange"
    if estado == "cancelado":
        return "Cancelado", "red"
    return "Confirmado", "lightgreen"


def get_estado_class(estado):
    estado = (estado or "").strip().lower()
    if estado == "pendiente":
        return "color-pendiente"
    if estado == "cancelado":
        return "color-cancelado"
    return "color-confirmado"


def precio_confirmado_por_turno(hora, duracion, config=None):
    if config is None:
        config = get_config()

    minutos = hora_a_minutos(hora)
    es_noche = minutos >= hora_a_minutos("18:00")

    if duracion == 60:
        return config["precio_1h_noche"] if es_noche else config["precio_1h_dia"]

    return config["precio_90m_noche"] if es_noche else config["precio_90m_dia"]


def precio_total_por_turno(hora, duracion, config=None):
    return precio_confirmado_por_turno(hora, duracion, config)


def precio_por_estado_y_turno(estado, hora, duracion, config=None):
    if config is None:
        config = get_config()

    confirmado = precio_confirmado_por_turno(hora, duracion, config)

    if estado == "Confirmado":
        return confirmado
    if estado == "Pendiente":
        return int(confirmado * config["senia_porcentaje"])
    if estado == "Cancelado":
        return 0
    return confirmado


def monto_pagado_inicial_por_estado(estado, hora, duracion, config=None):
    if config is None:
        config = get_config()

    total = precio_total_por_turno(hora, duracion, config)
    estado = (estado or "").strip()

    if estado == "Confirmado":
        return total
    if estado == "Pendiente":
        return int(total * config["senia_porcentaje"])
    if estado == "Cancelado":
        return 0
    return total


def monto_reembolso_por_cancelacion(estado_original, precio_total, monto_pagado, fecha_reserva, hora_reserva):
    estado_original = (estado_original or "").strip()

    ahora = datetime.now()
    fecha_hora_turno = datetime.strptime(f"{fecha_reserva} {hora_reserva}", "%Y-%m-%d %H:%M")
    horas_anticipacion = (fecha_hora_turno - ahora).total_seconds() / 3600

    if horas_anticipacion >= 24:
        return monto_pagado

    if estado_original == "Pendiente":
        return 0

    if estado_original == "Confirmado":
        return int(precio_total * 0.70)

    return 0


def deuda_reserva(precio_total, monto_pagado, estado):
    if estado == "Cancelado":
        return 0
    return max(0, to_int(precio_total) - to_int(monto_pagado))


def guardar_o_actualizar_cliente(nombre, telefono):
    nombre = (nombre or "").strip()
    telefono = (telefono or "").strip()

    if not nombre and not telefono:
        return

    conn = get_db()
    c = conn.cursor()

    if telefono:
        existente = c.execute(
            "SELECT id FROM clientes WHERE telefono=?",
            (telefono,)
        ).fetchone()

        if existente:
            c.execute(
                "UPDATE clientes SET nombre=? WHERE id=?",
                (nombre, existente[0])
            )
        else:
            c.execute(
                "INSERT INTO clientes (nombre, telefono) VALUES (?, ?)",
                (nombre, telefono)
            )
    else:
        existente = c.execute(
            "SELECT id FROM clientes WHERE lower(nombre)=lower(?)",
            (nombre,)
        ).fetchone()

        if existente:
            c.execute(
                "UPDATE clientes SET telefono=? WHERE id=?",
                (telefono, existente[0])
            )
        else:
            c.execute(
                "INSERT INTO clientes (nombre, telefono) VALUES (?, ?)",
                (nombre, telefono)
            )

    conn.commit()
    conn.close()


def reserva_se_superpone(cancha, fecha, hora, duracion, excluir_id=None):
    conn = get_db()
    c = conn.cursor()

    nuevos_bloques = set(bloques_que_ocupa(hora, duracion))

    if excluir_id is None:
        rows = c.execute("""
            SELECT id, hora, duracion
            FROM reservas
            WHERE cancha=? AND fecha=? AND lower(trim(estado))!='cancelado'
        """, (cancha, fecha)).fetchall()
    else:
        rows = c.execute("""
            SELECT id, hora, duracion
            FROM reservas
            WHERE cancha=? AND fecha=? AND id!=? AND lower(trim(estado))!='cancelado'
        """, (cancha, fecha, excluir_id)).fetchall()

    conn.close()

    for r in rows:
        bloques_existentes = set(bloques_que_ocupa(r[1], to_int(r[2], 90)))
        if nuevos_bloques & bloques_existentes:
            return True

    return False


def horarios_disponibles_online(cancha, fecha, duracion):
    cfg = get_config()
    todos = generar_slots(cfg["hora_apertura"], cfg["hora_cierre"], 30)
    libres = []

    hora_minima = hora_minima_reservable(fecha, 60)
    if hora_minima is None:
        return libres

    conn = get_db()
    c = conn.cursor()

    reservas = c.execute("""
        SELECT hora, duracion
        FROM reservas
        WHERE cancha=? AND fecha=? AND lower(trim(estado))!='cancelado'
    """, (cancha, fecha)).fetchall()

    conn.close()

    ocupados = set()
    for r in reservas:
        for b in bloques_que_ocupa(r[0], to_int(r[1], 90)):
            ocupados.add(b)

    minimo_mins = hora_a_minutos(hora_minima)
    cierre_mins = hora_a_minutos(cfg["hora_cierre"])

    for hora in todos:
        inicio = hora_a_minutos(hora)
        fin = inicio + duracion

        if inicio < minimo_mins:
            continue

        if fin > cierre_mins:
            continue

        bloques = bloques_que_ocupa(hora, duracion)
        if all(b not in ocupados for b in bloques):
            libres.append(hora)

    return libres


# =========================================================
# MERCADO PAGO HELPERS
# =========================================================

def crear_preferencia_mp(reserva_id, titulo, precio, tipo_pago):
    url = f"{BASE_URL_MP}/checkout/preferences"

    payload = {
        "items": [
            {
                "title": titulo,
                "quantity": 1,
                "currency_id": "ARS",
                "unit_price": float(precio)
            }
        ],
        "external_reference": str(reserva_id),
        "notification_url": f"{PUBLIC_BASE_URL}/webhook_mp",
        "back_urls": {
            "success": f"{PUBLIC_BASE_URL}/pago-exitoso",
            "failure": f"{PUBLIC_BASE_URL}/pago-fallido",
            "pending": f"{PUBLIC_BASE_URL}/pago-pendiente"
    },
        "auto_return": "approved",
        "statement_descriptor": "PADEL37"
    }

    headers = {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    r = requests.post(url, json=payload, headers=headers, timeout=30)
    return r.status_code, r.json()


def obtener_pago_mp(payment_id):
    url = f"{BASE_URL_MP}/v1/payments/{payment_id}"
    headers = {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}"
    }
    r = requests.get(url, headers=headers, timeout=30)
    return r.status_code, r.json()
# =========================================================
# LOGIN ROUTES
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_logueado"):
        return redirect("/")

    error = ""

    if request.method == "POST":
        usuario = (request.form.get("usuario") or "").strip()
        password = (request.form.get("password") or "").strip()

        if usuario == ADMIN_USER and password == ADMIN_PASS:
            session["admin_logueado"] = True
            return redirect("/")
        else:
            error = '<div class="err">Usuario o contraseña incorrectos.</div>'

    html = f"""
    <div class="card" style="max-width:420px;margin:40px auto;">
      <h2>Ingreso administrador</h2>
      {error}
      <form method="post">
        <label>Usuario</label>
        <input name="usuario" required>

        <label>Contraseña</label>
        <input type="password" name="password" required>

        <button class="btn btn-primary">Ingresar</button>
      </form>

      <p class="muted" style="margin-top:15px;">
        La reserva online sigue disponible para clientes desde /reservar
      </p>
    </div>
    """
    return render_page("Login", html)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =========================================================
# INICIO
# =========================================================

@app.route("/")
@login_required
def home():
    conn = get_db()
    c = conn.cursor()

    fecha_vista = request.args.get("fecha") or datetime.now().strftime("%Y-%m-%d")

    total_clientes = c.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
    total_turnos = c.execute(
        "SELECT COUNT(*) FROM reservas WHERE lower(trim(estado))!='cancelado'"
    ).fetchone()[0]

    turnos_fecha = c.execute(
        "SELECT COUNT(*) FROM reservas WHERE fecha=? AND lower(trim(estado))!='cancelado'",
        (fecha_vista,)
    ).fetchone()[0]

    confirmados_fecha = c.execute(
        "SELECT COUNT(*) FROM reservas WHERE fecha=? AND trim(estado)='Confirmado'",
        (fecha_vista,)
    ).fetchone()[0]

    pendientes_fecha = c.execute(
        "SELECT COUNT(*) FROM reservas WHERE fecha=? AND trim(estado)='Pendiente'",
        (fecha_vista,)
    ).fetchone()[0]

    cancelados_fecha = c.execute(
        "SELECT COUNT(*) FROM reservas WHERE fecha=? AND trim(estado)='Cancelado'",
        (fecha_vista,)
    ).fetchone()[0]

    conn.close()

    html = f"""
    <div class="card">
      <h2>Panel principal</h2>

      <form method="get" style="margin-bottom:20px;">
        <div class="row">
          <div>
            <label>Fecha a consultar</label>
            <input type="date" name="fecha" value="{fecha_vista}">
          </div>
          <div style="display:flex;align-items:end;">
            <button class="btn btn-primary">Ver</button>
          </div>
        </div>
      </form>

      <div class="summary-grid">
        <div class="summary-box">
          <h4>Clientes</h4>
          <p>{total_clientes}</p>
        </div>

        <div class="summary-box">
          <h4>Turnos activos totales</h4>
          <p>{total_turnos}</p>
        </div>

        <div class="summary-box">
          <h4>Turnos de la fecha</h4>
          <p>{turnos_fecha}</p>
        </div>

        <div class="summary-box">
          <h4>Fecha consultada</h4>
          <p style="font-size:18px;">{fecha_vista}</p>
        </div>
      </div>
    </div>

    <div class="card">
      <h3>Detalle de {fecha_vista}</h3>
      <div class="summary-grid">
        <div class="summary-box">
          <h4>Confirmados</h4>
          <p>{confirmados_fecha}</p>
        </div>

        <div class="summary-box">
          <h4>Pendientes</h4>
          <p>{pendientes_fecha}</p>
        </div>

        <div class="summary-box">
          <h4>Cancelados</h4>
          <p>{cancelados_fecha}</p>
        </div>

        <div class="summary-box">
          <h4>Total del día</h4>
          <p>{turnos_fecha + cancelados_fecha}</p>
        </div>
      </div>
    </div>
    """

    return render_page("Inicio", html)


# =========================================================
# PRECIOS Y HORARIOS
# =========================================================

@app.route("/precios", methods=["GET", "POST"])
@login_required
def precios():
    mensaje = ""

    if request.method == "POST":
        precio_1h_dia = max(0, to_int(request.form.get("precio_1h_dia")))
        precio_1h_noche = max(0, to_int(request.form.get("precio_1h_noche")))
        precio_90m_dia = max(0, to_int(request.form.get("precio_90m_dia")))
        precio_90m_noche = max(0, to_int(request.form.get("precio_90m_noche")))
        senia_porcentaje = to_float((request.form.get("senia_porcentaje") or "0.30").replace(",", "."), 0.30)

        if senia_porcentaje < 0:
            senia_porcentaje = 0
        if senia_porcentaje > 1:
            senia_porcentaje = 1

        hora_apertura = (request.form.get("hora_apertura") or "08:00").strip()
        hora_cierre = (request.form.get("hora_cierre") or "23:30").strip()

        try:
            if hora_a_minutos(hora_cierre) <= hora_a_minutos(hora_apertura):
                return render_page("Error", """
                <div class="card">
                  <div class="err">La hora de cierre debe ser mayor que la hora de apertura.</div>
                  <a class="btn btn-secondary" href="/precios">Volver</a>
                </div>
                """)
        except Exception:
            return render_page("Error", """
            <div class="card">
              <div class="err">Formato de horario inválido. Usá HH:MM, por ejemplo 08:00 o 23:30.</div>
              <a class="btn btn-secondary" href="/precios">Volver</a>
            </div>
            """)

        set_config_valores(
            precio_1h_dia,
            precio_1h_noche,
            precio_90m_dia,
            precio_90m_noche,
            senia_porcentaje,
            hora_apertura,
            hora_cierre
        )

        mensaje = '<div class="ok">Precios y horarios actualizados correctamente.</div>'

    cfg = get_config()

    html = f"""
    <div class="card">
      <h2>Configuración de precios y horarios</h2>
      {mensaje}

      <form method="post">
        <div class="row">
          <div>
            <label>1 hora - Día</label>
            <input type="number" name="precio_1h_dia" min="0" value="{cfg['precio_1h_dia']}" required>
          </div>
          <div>
            <label>1 hora - Noche (desde 18:00)</label>
            <input type="number" name="precio_1h_noche" min="0" value="{cfg['precio_1h_noche']}" required>
          </div>
        </div>

        <div class="row">
          <div>
            <label>1 hora y media - Día</label>
            <input type="number" name="precio_90m_dia" min="0" value="{cfg['precio_90m_dia']}" required>
          </div>
          <div>
            <label>1 hora y media - Noche (desde 18:00)</label>
            <input type="number" name="precio_90m_noche" min="0" value="{cfg['precio_90m_noche']}" required>
          </div>
        </div>

        <div class="row">
          <div>
            <label>Porcentaje de seña</label>
            <input type="number" step="0.01" min="0" max="1" name="senia_porcentaje" value="{cfg['senia_porcentaje']}" required>
            <div class="muted">Ejemplo: 0.30 = 30%</div>
          </div>
        </div>

        <div class="row">
          <div>
            <label>Hora apertura</label>
            <input type="time" name="hora_apertura" value="{e(cfg['hora_apertura'])}" required>
          </div>
          <div>
            <label>Hora cierre</label>
            <input type="time" name="hora_cierre" value="{e(cfg['hora_cierre'])}" required>
          </div>
        </div>

        <button class="btn btn-primary">Guardar cambios</button>
      </form>
    </div>
    """

    return render_page("Precios", html)


# =========================================================
# CLIENTES
# =========================================================

@app.route("/clientes", methods=["GET", "POST"])
@login_required
def clientes():
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        telefono = (request.form.get("telefono") or "").strip()

        if nombre:
            try:
                if telefono:
                    existe = c.execute(
                        "SELECT id FROM clientes WHERE telefono=?",
                        (telefono,)
                    ).fetchone()
                else:
                    existe = c.execute(
                        "SELECT id FROM clientes WHERE lower(nombre)=lower(?)",
                        (nombre,)
                    ).fetchone()

                if existe:
                    c.execute(
                        "UPDATE clientes SET nombre=?, telefono=? WHERE id=?",
                        (nombre, telefono, existe[0])
                    )
                else:
                    c.execute(
                        "INSERT INTO clientes (nombre, telefono) VALUES (?, ?)",
                        (nombre, telefono)
                    )

                conn.commit()

            except sqlite3.IntegrityError:
                conn.close()
                return render_page("Error", """
                <div class="card">
                  <div class="err">Ya existe un cliente con ese teléfono.</div>
                  <a class="btn btn-secondary" href="/clientes">Volver</a>
                </div>
                """)

        conn.close()
        return redirect("/clientes")

    rows = c.execute(
        "SELECT id, nombre, telefono FROM clientes ORDER BY nombre"
    ).fetchall()

    conn.close()

    tabla = ""
    for r in rows:
        tabla += f"""
        <tr>
          <td>{e(r[1])}</td>
          <td>{e(r[2] or "-")}</td>
          <td>
            <a class="btn btn-secondary" href="/clientes/editar/{r[0]}">Modificar</a>
            <a class="btn btn-danger" href="/clientes/borrar/{r[0]}" onclick="return confirm('¿Seguro que querés borrar este cliente?')">Borrar</a>
          </td>
        </tr>
        """

    html = f"""
    <div class="card">
      <h2>Clientes</h2>
      <form method="post">
        <div class="row">
          <div>
            <label>Nombre</label>
            <input name="nombre" required>
          </div>
          <div>
            <label>Teléfono</label>
            <input name="telefono" required>
          </div>
        </div>
        <button class="btn btn-primary">Guardar</button>
      </form>
    </div>

    <div class="card">
      <h3>Base de clientes</h3>
      <div class="table-wrap">
        <table>
          <tr>
            <th>Nombre</th>
            <th>Teléfono</th>
            <th>Acciones</th>
          </tr>
          {tabla or "<tr><td colspan='3'>Sin clientes todavía</td></tr>"}
        </table>
      </div>
    </div>
    """

    return render_page("Clientes", html)


@app.route("/clientes/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_cliente(id):
    conn = get_db()
    c = conn.cursor()

    cliente = c.execute(
        "SELECT id, nombre, telefono FROM clientes WHERE id=?",
        (id,)
    ).fetchone()

    if not cliente:
        conn.close()
        return redirect("/clientes")

    if request.method == "POST":
        nuevo_nombre = (request.form.get("nombre") or "").strip()
        nuevo_telefono = (request.form.get("telefono") or "").strip()

        if nuevo_nombre:
            conflicto = None
            if nuevo_telefono:
                conflicto = c.execute(
                    "SELECT id FROM clientes WHERE telefono=? AND id!=?",
                    (nuevo_telefono, id)
                ).fetchone()

            if conflicto:
                conn.close()
                return render_page("Error", """
                <div class="card">
                  <div class="err">Ese teléfono ya pertenece a otro cliente.</div>
                  <a class="btn btn-secondary" href="/clientes">Volver</a>
                </div>
                """)

            nombre_viejo = cliente[1]
            telefono_viejo = cliente[2] or ""

            c.execute(
                "UPDATE clientes SET nombre=?, telefono=? WHERE id=?",
                (nuevo_nombre, nuevo_telefono, id)
            )

            c.execute(
                "UPDATE reservas SET cliente=?, telefono=? WHERE cliente=? AND telefono=?",
                (nuevo_nombre, nuevo_telefono, nombre_viejo, telefono_viejo)
            )

            c.execute(
                "UPDATE reservas SET cliente=?, telefono=? WHERE cliente=? AND (telefono IS NULL OR telefono='')",
                (nuevo_nombre, nuevo_telefono, nombre_viejo)
            )

            conn.commit()

        conn.close()
        return redirect("/clientes")

    conn.close()

    html = f"""
    <div class="card">
      <h2>Editar cliente</h2>
      <form method="post">
        <div class="row">
          <div>
            <label>Nombre</label>
            <input name="nombre" value="{e(cliente[1])}" required>
          </div>
          <div>
            <label>Teléfono</label>
            <input name="telefono" value="{e(cliente[2] or '')}" required>
          </div>
        </div>
        <button class="btn btn-primary">Guardar cambios</button>
        <a class="btn btn-secondary" href="/clientes">Cancelar</a>
      </form>
    </div>
    """

    return render_page("Editar cliente", html)


@app.route("/clientes/borrar/<int:id>")
@login_required
def borrar_cliente(id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM clientes WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/clientes")
# =========================================================
# RESERVAS
# =========================================================

@app.route("/reservas")
@login_required
def reservas():
    cfg = get_config()
    fecha_vista = request.args.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    ver_cancelados = request.args.get("ver_cancelados") == "1"
    horarios = generar_slots(cfg["hora_apertura"], cfg["hora_cierre"], 30)

    conn = get_db()
    c = conn.cursor()

    reservas_dia = c.execute(
        "SELECT * FROM reservas WHERE fecha=? ORDER BY hora, cancha",
        (fecha_vista,)
    ).fetchall()

    if ver_cancelados:
        listado = c.execute(
            "SELECT * FROM reservas WHERE fecha=? ORDER BY hora ASC, cancha ASC",
            (fecha_vista,)
        ).fetchall()
    else:
        listado = c.execute(
            "SELECT * FROM reservas WHERE fecha=? AND lower(trim(estado))!='cancelado' ORDER BY hora ASC, cancha ASC",
            (fecha_vista,)
        ).fetchall()

    clientes_rows = c.execute(
        "SELECT nombre, telefono FROM clientes ORDER BY nombre"
    ).fetchall()

    conn.close()

    options_clientes = ""
    clientes_map = {}
    for nombre, telefono in clientes_rows:
        options_clientes += f"<option value='{e(nombre or '')}'>"
        clientes_map[nombre or ""] = telefono or ""

    clientes_map_js = json.dumps(clientes_map, ensure_ascii=False)

    inicio_turnos = {}
    continuaciones = set()

    for r in reservas_dia:
        if (r[10] or "").strip().lower() == "cancelado":
            continue

        cancha = int(r[3])
        hora_inicio = r[5]
        duracion = to_int(r[6], 90)
        bloques = bloques_que_ocupa(hora_inicio, duracion)

        inicio_turnos[(cancha, hora_inicio)] = r

        for i, bloque in enumerate(bloques):
            if i > 0:
                continuaciones.add((cancha, bloque))

    hora_minima_admin = hora_minima_reservable(fecha_vista, 60)
    minimo_admin_mins = hora_a_minutos(hora_minima_admin) if hora_minima_admin else None

    filas_grilla = ""
    for hora in horarios:
        fila = f"<tr><td><b>{e(hora)}</b></td>"

        for cancha in [1, 2, 3]:
            r_inicio = inicio_turnos.get((cancha, hora))
            es_continuacion = (cancha, hora) in continuaciones

            if r_inicio:
                duracion = to_int(r_inicio[6], 90)
                hora_fin = minutos_a_hora(hora_a_minutos(r_inicio[5]) + duracion)
                monto_pagado = to_int(r_inicio[11])
                rowspan = max(1, duracion // 30)

                fila += f"""
                <td rowspan="{rowspan}"
                    class="celda-turno {get_estado_class(r_inicio[10])}"
                    ondblclick='abrirModalEditar(
                        {js_str(r_inicio[0])},
                        {js_str(r_inicio[1] or "")},
                        {js_str(r_inicio[2] or "")},
                        {js_str(r_inicio[3])},
                        {js_str(r_inicio[4])},
                        {js_str(r_inicio[5])},
                        {js_str(duracion)},
                        {js_str(r_inicio[7] or "efectivo")},
                        {js_str(r_inicio[9] or 0)},
                        {js_str(r_inicio[10] or "Confirmado")},
                        {js_str(monto_pagado)}
                    )'>
                  <div class="contenido-turno">
                    <b>{e(r_inicio[1])}</b><br>
                    {e(r_inicio[2] or "-")}<br>
                    {e(r_inicio[5])} a {e(hora_fin)}<br>
                    {duracion} min<br>
                    ${to_int(r_inicio[9])} - {e(r_inicio[7] or "-")}<br>
                    Pagado: ${monto_pagado}<br>
                    {e(r_inicio[10])}<br><br>
                    <span class="muted" style="color:inherit;">Doble click para editar</span>
                  </div>
                </td>
                """
            elif es_continuacion:
                continue
            else:
                inicio_hora = hora_a_minutos(hora)

                if minimo_admin_mins is not None and inicio_hora < minimo_admin_mins:
                    fila += "<td></td>"
                else:
                    fila += f"""
                    <td ondblclick='abrirModalNuevo({js_str(cancha)}, {js_str(fecha_vista)}, {js_str(hora)})'>
                      <div class="libre">Libre</div>
                    </td>
                    """

        fila += "</tr>"
        filas_grilla += fila

    filas_listado = ""
    for r in listado:
        duracion = to_int(r[6], 90)
        monto_pagado = to_int(r[11])
        monto_reembolso = to_int(r[12])
        precio_total = to_int(r[13], to_int(r[9]))
        deuda = deuda_reserva(precio_total, monto_pagado, r[10])

        boton_completar = (
            f"<form method='post' action='/reservas/pago/{r[0]}' style='display:inline;'>"
            f"<input type='hidden' name='accion' value='completar'>"
            f"<button class='btn btn-primary btn-small' type='submit'>Completar</button>"
            f"</form>"
            if deuda > 0 and (r[10] or '').strip() != "Cancelado" else ""
        )

        link_mp = ""
        if r[18]:
            link_mp = f"<a class='btn btn-success btn-small' href='{e(r[18])}' target='_blank'>Cobrar MP</a>"

        filas_listado += f"""
        <tr>
          <td>{e(r[1])}</td>
          <td>{e(r[2] or "-")}</td>
          <td>{r[3]}</td>
          <td>{e(r[4])}</td>
          <td>{e(r[5])}</td>
          <td>{duracion} min</td>
          <td>{e(r[7] or "-")}</td>
          <td>${to_int(r[9])}</td>
          <td>${precio_total}</td>
          <td>{e(r[10])}</td>
          <td>${monto_pagado}</td>
          <td>${deuda}</td>
          <td>${monto_reembolso}</td>
          <td>
            <a class="btn btn-secondary btn-small"
               href="#"
               onclick='abrirModalEditar(
                    {js_str(r[0])},
                    {js_str(r[1] or "")},
                    {js_str(r[2] or "")},
                    {js_str(r[3])},
                    {js_str(r[4])},
                    {js_str(r[5])},
                    {js_str(duracion)},
                    {js_str(r[7] or "efectivo")},
                    {js_str(r[9] or 0)},
                    {js_str(r[10] or "Confirmado")},
                    {js_str(monto_pagado)}
               ); return false;'>
               Modificar
            </a>

            <a class="btn btn-success btn-small"
               href="#"
               onclick='abrirModalPago({js_str(r[0])}, {js_str(r[1] or "")}, {js_str(precio_total)}, {js_str(monto_pagado)}, {js_str(r[4])}, {js_str(r[5])}); return false;'>
               Registrar pago
            </a>

            {boton_completar}
            {link_mp}

            <a class="btn btn-danger btn-small" href="/reservas/cancelar/{r[0]}">Cancelar</a>
          </td>
        </tr>
        """

    boton_cancelados = f"""
    <a class="btn btn-secondary" href="/reservas?fecha={e(fecha_vista)}&ver_cancelados={'0' if ver_cancelados else '1'}">
      {'🙈 Ocultar cancelados' if ver_cancelados else '👁 Ver cancelados del día'}
    </a>
    """

    subtitulo_listado = (
        f"Mostrando también cancelados de {e(fecha_vista)}." if ver_cancelados
        else f"Mostrando solo turnos activos de {e(fecha_vista)}."
    )

    html = f"""
    <style>
      td.celda-turno {{
        padding: 0 !important;
        vertical-align: top;
        border-radius: 12px;
        overflow: hidden;
      }}

      td.celda-turno.color-confirmado {{
        background: #16a34a;
        color: white;
      }}

      td.celda-turno.color-pendiente {{
        background: #f59e0b;
        color: #111111;
      }}

      td.celda-turno.color-cancelado {{
        background: #dc2626;
        color: white;
      }}

      .contenido-turno {{
        padding: 12px;
        min-height: 100%;
        height: 100%;
        line-height: 1.35;
        font-size: 12px;
        box-shadow: inset 0 0 0 2px rgba(255,255,255,0.18);
        border-radius: 12px;
      }}

      .libre {{
        background: #0f5132;
        color: white;
        padding: 12px;
        border-radius: 8px;
        font-weight: bold;
        min-height: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
      }}

      .modal-fondo {{
        display: none;
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.60);
        z-index: 9999;
        justify-content: center;
        align-items: center;
        padding: 20px;
      }}

      .modal-caja {{
        background: #1a1a1a;
        border: 1px solid #4d3f11;
        border-radius: 14px;
        width: 100%;
        max-width: 780px;
        padding: 20px;
      }}

      .modal-caja h3 {{
        margin-top: 0;
        color: #d4af37;
      }}

      .precio-fijo {{
        background: #d1d5db !important;
        color: #111 !important;
        font-weight: bold;
      }}
    </style>

    <div class="card">
      <h2>Reservas</h2>
      <p class="muted">
        Doble click sobre una celda libre para crear un turno.
        Doble click sobre una ocupada para editarlo.
      </p>
      <form method="get">
        <div class="row">
          <div>
            <label>Fecha a ver</label>
            <input type="date" name="fecha" value="{e(fecha_vista)}">
          </div>
          <div style="display:flex;align-items:end;gap:8px;">
            <button class="btn btn-primary">Ver</button>
            {boton_cancelados}
          </div>
        </div>
      </form>
    </div>

    <div class="card">
      <h3>Agenda del día</h3>
      <div class="table-wrap">
        <table>
          <tr>
            <th>Horario</th>
            <th>Cancha 1</th>
            <th>Cancha 2</th>
            <th>Cancha 3</th>
          </tr>
          {filas_grilla}
        </table>
      </div>
    </div>

    <div class="card">
      <h3>Listado de {e(fecha_vista)}</h3>
      <p class="muted">{subtitulo_listado}</p>
      <div class="table-wrap">
        <table>
          <tr>
            <th>Cliente</th>
            <th>Teléfono</th>
            <th>Cancha</th>
            <th>Fecha</th>
            <th>Hora</th>
            <th>Duración</th>
            <th>Método</th>
            <th>Precio visible</th>
            <th>Precio total</th>
            <th>Estado</th>
            <th>Pagado</th>
            <th>Deuda</th>
            <th>Reembolso</th>
            <th>Acciones</th>
          </tr>
          {filas_listado or "<tr><td colspan='14'>Sin turnos para mostrar</td></tr>"}
        </table>
      </div>
    </div>

    <div id="modalReserva" class="modal-fondo">
      <div class="modal-caja">
        <h3 id="modalTitulo">Reserva</h3>
        <p class="muted" id="modalInfoTurno" style="margin-top:-6px;margin-bottom:14px;"></p>

        <form method="post" action="/reservas/guardar">
          <input type="hidden" name="id" id="reserva_id">
          <input type="hidden" name="cancha" id="cancha_modal">
          <input type="hidden" name="fecha" id="fecha_modal">
          <input type="hidden" name="hora" id="hora_modal">

          <datalist id="lista_clientes_modal">
            {options_clientes}
          </datalist>

          <div class="row">
            <div>
              <label>Cliente</label>
              <input name="cliente" id="cliente_modal" list="lista_clientes_modal" required>
            </div>
            <div>
              <label>Teléfono</label>
              <input name="telefono" id="telefono_modal" required>
            </div>
          </div>

          <div class="row">
            <div>
              <label>Duración</label>
              <select name="duracion" id="duracion_modal" onchange="actualizarPrecioAutomatico()">
                <option value="60">1 hora</option>
                <option value="90">1 hora y media</option>
              </select>
            </div>

            <div>
              <label>Método de pago</label>
              <select name="metodo" id="metodo_modal">
                <option value="efectivo">Efectivo</option>
                <option value="transferencia">Transferencia</option>
                <option value="qr">QR</option>
                <option value="online">Online</option>
              </select>
            </div>

            <div>
              <label>Estado</label>
              <select name="estado" id="estado_modal" onchange="actualizarPrecioAutomatico()">
                <option value="Confirmado">Confirmado</option>
                <option value="Pendiente">Pendiente</option>
                <option value="Cancelado">Cancelado</option>
              </select>
            </div>

            <div>
              <label>Precio</label>
              <input type="number" name="precio" id="precio_modal" class="precio-fijo" readonly>
            </div>
          </div>

          <div class="row">
            <div>
              <label>Monto pagado real</label>
              <input type="number" name="monto_pagado" id="monto_pagado_modal" min="0">
            </div>
          </div>

          <div style="margin-top:15px;">
            <button class="btn btn-primary" type="submit">Guardar</button>
            <a href="#" class="btn btn-danger" id="btnCancelarTurno" style="display:none;">Cancelar turno</a>
            <button class="btn btn-secondary" type="button" onclick="cerrarModal()">Cerrar</button>
          </div>
        </form>
      </div>
    </div>

    <div id="modalPago" class="modal-fondo">
      <div class="modal-caja">
        <h3>Registrar pago</h3>
        <p class="muted" id="modalPagoInfo" style="margin-top:-6px;margin-bottom:14px;"></p>

        <form method="post" id="formPagoReserva">
          <input type="hidden" name="accion" value="sumar">

          <div class="row">
            <div>
              <label>Precio total</label>
              <input type="text" id="pago_precio_total" readonly>
            </div>
            <div>
              <label>Pagado actual</label>
              <input type="text" id="pago_pagado_actual" readonly>
            </div>
            <div>
              <label>Deuda actual</label>
              <input type="text" id="pago_deuda_actual" readonly>
            </div>
          </div>

          <div class="row">
            <div>
              <label>Monto a sumar</label>
              <input type="number" name="monto" id="pago_monto" min="1" required>
            </div>
          </div>

          <div style="margin-top:15px;">
            <button class="btn btn-success" type="submit">Registrar pago</button>
            <button class="btn btn-secondary" type="button" onclick="cerrarModalPago()">Cerrar</button>
          </div>
        </form>
      </div>
    </div>

    <script>
      const clientesMap = {clientes_map_js};
      const CFG = {{
        precio_1h_dia: {cfg["precio_1h_dia"]},
        precio_1h_noche: {cfg["precio_1h_noche"]},
        precio_90m_dia: {cfg["precio_90m_dia"]},
        precio_90m_noche: {cfg["precio_90m_noche"]},
        senia_porcentaje: {cfg["senia_porcentaje"]}
      }};

      function precioConfirmadoPorTurno(hora, duracion) {{
        const partes = hora.split(":");
        const minutos = parseInt(partes[0]) * 60 + parseInt(partes[1]);
        const esNoche = minutos >= 18 * 60;

        if (parseInt(duracion) === 60) {{
          return esNoche ? CFG.precio_1h_noche : CFG.precio_1h_dia;
        }}

        return esNoche ? CFG.precio_90m_noche : CFG.precio_90m_dia;
      }}

      function precioPorEstadoYTurno(estado, hora, duracion) {{
        const confirmado = precioConfirmadoPorTurno(hora, duracion);

        if (estado === "Confirmado") return confirmado;
        if (estado === "Pendiente") return Math.round(confirmado * CFG.senia_porcentaje);
        if (estado === "Cancelado") return 0;

        return confirmado;
      }}

      function montoPagadoInicialPorEstado(estado, hora, duracion) {{
        const total = precioConfirmadoPorTurno(hora, duracion);

        if (estado === "Confirmado") return total;
        if (estado === "Pendiente") return Math.round(total * CFG.senia_porcentaje);
        if (estado === "Cancelado") return 0;

        return total;
      }}

      function actualizarPrecioAutomatico() {{
        const hora = document.getElementById("hora_modal").value;
        const estado = document.getElementById("estado_modal").value;
        const duracion = document.getElementById("duracion_modal").value;
        document.getElementById("precio_modal").value = precioPorEstadoYTurno(estado, hora, duracion);
      }}

      function abrirModalNuevo(cancha, fecha, hora) {{
        document.getElementById("modalTitulo").innerText = "Nuevo turno";
        document.getElementById("modalInfoTurno").innerText = "Cancha " + cancha + " — " + fecha + " — " + hora;
        document.getElementById("reserva_id").value = "";
        document.getElementById("cliente_modal").value = "";
        document.getElementById("telefono_modal").value = "";
        document.getElementById("cancha_modal").value = cancha;
        document.getElementById("fecha_modal").value = fecha;
        document.getElementById("hora_modal").value = hora;
        document.getElementById("duracion_modal").value = "90";
        document.getElementById("metodo_modal").value = "efectivo";
        document.getElementById("estado_modal").value = "Confirmado";
        document.getElementById("monto_pagado_modal").value = montoPagadoInicialPorEstado("Confirmado", hora, 90);
        document.getElementById("btnCancelarTurno").style.display = "none";
        actualizarPrecioAutomatico();
        document.getElementById("modalReserva").style.display = "flex";
      }}

      function abrirModalEditar(id, cliente, telefono, cancha, fecha, hora, duracion, metodo, precio, estado, monto_pagado) {{
        document.getElementById("modalTitulo").innerText = "Editar turno";
        document.getElementById("modalInfoTurno").innerText = "Cancha " + cancha + " — " + fecha + " — " + hora;
        document.getElementById("reserva_id").value = id;
        document.getElementById("cliente_modal").value = cliente;
        document.getElementById("telefono_modal").value = telefono;
        document.getElementById("cancha_modal").value = cancha;
        document.getElementById("fecha_modal").value = fecha;
        document.getElementById("hora_modal").value = hora;
        document.getElementById("duracion_modal").value = duracion;
        document.getElementById("metodo_modal").value = metodo;
        document.getElementById("estado_modal").value = estado;
        document.getElementById("monto_pagado_modal").value = monto_pagado || 0;
        document.getElementById("btnCancelarTurno").href = "/reservas/cancelar/" + id;
        document.getElementById("btnCancelarTurno").style.display = "inline-block";
        actualizarPrecioAutomatico();
        document.getElementById("modalReserva").style.display = "flex";
      }}

      function cerrarModal() {{
        document.getElementById("modalReserva").style.display = "none";
      }}

      function abrirModalPago(id, cliente, precioTotal, pagadoActual, fecha, hora) {{
        const deuda = Math.max(0, parseInt(precioTotal || 0) - parseInt(pagadoActual || 0));

        document.getElementById("modalPagoInfo").innerText =
          cliente + " — " + fecha + " — " + hora;

        document.getElementById("pago_precio_total").value = precioTotal;
        document.getElementById("pago_pagado_actual").value = pagadoActual;
        document.getElementById("pago_deuda_actual").value = deuda;
        document.getElementById("pago_monto").value = deuda > 0 ? deuda : "";
        document.getElementById("pago_monto").max = deuda;
        document.getElementById("formPagoReserva").action = "/reservas/pago/" + id;

        document.getElementById("modalPago").style.display = "flex";
      }}

      function cerrarModalPago() {{
        document.getElementById("modalPago").style.display = "none";
      }}

      document.getElementById("cliente_modal").addEventListener("change", function() {{
        const nombre = this.value.trim();
        if (clientesMap[nombre] !== undefined) {{
          document.getElementById("telefono_modal").value = clientesMap[nombre];
        }}
      }});

      document.getElementById("cliente_modal").addEventListener("blur", function() {{
        const nombre = this.value.trim();
        if (clientesMap[nombre] !== undefined) {{
          document.getElementById("telefono_modal").value = clientesMap[nombre];
        }}
      }});

      window.addEventListener("click", function(e) {{
        const modalReserva = document.getElementById("modalReserva");
        const modalPago = document.getElementById("modalPago");

        if (e.target === modalReserva) {{
          cerrarModal();
        }}
        if (e.target === modalPago) {{
          cerrarModalPago();
        }}
      }});
    </script>
    """

    return render_page("Reservas", html)


@app.route("/reservas/guardar", methods=["POST"])
@login_required
def guardar_reserva():
    cfg = get_config()

    rid = (request.form.get("id") or "").strip()
    cliente = (request.form.get("cliente") or "").strip()
    telefono = (request.form.get("telefono") or "").strip()
    cancha = int(request.form.get("cancha") or 1)
    fecha = request.form.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    hora = request.form.get("hora") or "08:00"
    duracion = to_int(request.form.get("duracion"), 90)
    if duracion not in [60, 90]:
        duracion = 90

    if not horario_habilitado_para_reservar(fecha, hora, 60):
        return render_page("Error", f"""
        <div class="card">
          <div class="err">Solo se pueden agendar turnos con al menos 1 hora de anticipación.</div>
          <a class="btn btn-secondary" href="/reservas?fecha={e(fecha)}">Volver</a>
        </div>
        """)

    metodo = request.form.get("metodo") or "efectivo"
    estado = request.form.get("estado") or "Confirmado"

    precio_total = precio_total_por_turno(hora, duracion, cfg)
    precio = precio_por_estado_y_turno(estado, hora, duracion, cfg)

    monto_pagado_form = request.form.get("monto_pagado")
    if monto_pagado_form is None or str(monto_pagado_form).strip() == "":
        monto_pagado = monto_pagado_inicial_por_estado(estado, hora, duracion, cfg)
    else:
        monto_pagado = max(0, min(precio_total, to_int(monto_pagado_form)))

    estado, color = get_estado_y_color(estado)

    if rid:
        if reserva_se_superpone(cancha, fecha, hora, duracion, excluir_id=int(rid)):
            return render_page("Error", f"""
            <div class="card">
              <div class="err">Ya existe otro turno superpuesto en esa cancha, fecha y hora.</div>
              <a class="btn btn-secondary" href="/reservas?fecha={e(fecha)}">Volver</a>
            </div>
            """)

        conn = get_db()
        c = conn.cursor()
        c.execute("""
            UPDATE reservas
            SET cliente=?, telefono=?, cancha=?, fecha=?, hora=?, duracion=?, metodo_pago=?, color=?, precio=?, precio_total=?, estado=?, monto_pagado=?, monto_reembolso=0
            WHERE id=?
        """, (
            cliente, telefono, cancha, fecha, hora, duracion, metodo, color,
            precio, precio_total, estado, monto_pagado, int(rid)
        ))
        conn.commit()
        conn.close()
    else:
        if reserva_se_superpone(cancha, fecha, hora, duracion):
            return render_page("Error", f"""
            <div class="card">
              <div class="err">Ya existe un turno superpuesto en esa cancha, fecha y hora.</div>
              <a class="btn btn-secondary" href="/reservas?fecha={e(fecha)}">Volver</a>
            </div>
            """)

        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO reservas
            (cliente, telefono, cancha, fecha, hora, duracion, metodo_pago, color, precio, precio_total, estado, monto_pagado, monto_reembolso)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cliente, telefono, cancha, fecha, hora, duracion, metodo, color,
            precio, precio_total, estado, monto_pagado, 0
        ))
        conn.commit()
        conn.close()

    guardar_o_actualizar_cliente(cliente, telefono)

    return redirect(f"/reservas?fecha={fecha}")


@app.route("/reservas/pago/<int:id>", methods=["POST"])
@login_required
def registrar_pago_reserva(id):
    conn = get_db()
    c = conn.cursor()

    reserva = c.execute("""
        SELECT id, fecha, precio_total, monto_pagado, estado
        FROM reservas
        WHERE id=?
    """, (id,)).fetchone()

    if not reserva:
        conn.close()
        return redirect("/reservas")

    fecha = reserva[1]
    precio_total = to_int(reserva[2])
    monto_pagado_actual = to_int(reserva[3])
    estado = reserva[4]

    if (estado or "").strip() == "Cancelado":
        conn.close()
        return render_page("Error", f"""
        <div class="card">
          <div class="err">No se puede registrar pago en una reserva cancelada.</div>
          <a class="btn btn-secondary" href="/reservas?fecha={e(fecha)}&ver_cancelados=1">Volver</a>
        </div>
        """)

    accion = (request.form.get("accion") or "").strip()
    monto_extra = to_int(request.form.get("monto"))
    deuda_actual = max(0, precio_total - monto_pagado_actual)

    if accion == "completar":
        nuevo_monto_pagado = precio_total
        nuevo_estado = "Confirmado"
        nuevo_color = "lightgreen"
        nuevo_precio = precio_total
    else:
        if monto_extra <= 0:
            conn.close()
            return render_page("Error", f"""
            <div class="card">
              <div class="err">El monto a registrar debe ser mayor a 0.</div>
              <a class="btn btn-secondary" href="/reservas?fecha={e(fecha)}">Volver</a>
            </div>
            """)

        if monto_extra > deuda_actual:
            monto_extra = deuda_actual

        nuevo_monto_pagado = monto_pagado_actual + monto_extra

        if nuevo_monto_pagado >= precio_total:
            nuevo_monto_pagado = precio_total
            nuevo_estado = "Confirmado"
            nuevo_color = "lightgreen"
            nuevo_precio = precio_total
        else:
            nuevo_estado = "Pendiente"
            nuevo_color = "orange"
            nuevo_precio = nuevo_monto_pagado

    c.execute("""
        UPDATE reservas
        SET monto_pagado=?,
            estado=?,
            color=?,
            precio=?
        WHERE id=?
    """, (
        nuevo_monto_pagado,
        nuevo_estado,
        nuevo_color,
        nuevo_precio,
        id
    ))

    conn.commit()
    conn.close()

    return redirect(f"/reservas?fecha={fecha}")


@app.route("/reservas/cancelar/<int:id>")
@login_required
def cancelar_reserva(id):
    conn = get_db()
    c = conn.cursor()

    reserva = c.execute("""
        SELECT fecha, hora, estado, precio_total, monto_pagado
        FROM reservas
        WHERE id=?
    """, (id,)).fetchone()

    if not reserva:
        conn.close()
        return redirect("/reservas")

    fecha = reserva[0]
    hora = reserva[1]
    estado_original = reserva[2]
    precio_total = to_int(reserva[3])
    monto_pagado = to_int(reserva[4])

    reembolso = monto_reembolso_por_cancelacion(
        estado_original,
        precio_total,
        monto_pagado,
        fecha,
        hora
    )

    c.execute("""
        UPDATE reservas
        SET estado='Cancelado',
            color='red',
            precio=0,
            monto_reembolso=?
        WHERE id=?
    """, (reembolso, id))

    conn.commit()
    conn.close()

    return redirect(f"/reservas?fecha={fecha}&ver_cancelados=1")


# =========================================================
# WEBHOOK MP + PÁGINAS DE RETORNO
# =========================================================

@app.route("/webhook_mp", methods=["POST"])
def webhook_mp():
    data = request.get_json(silent=True) or {}
    topic = data.get("type") or data.get("topic")
    pago_data = data.get("data") or {}
    payment_id = pago_data.get("id")

    if topic == "payment" and payment_id:
        try:
            status_code, pago = obtener_pago_mp(payment_id)
            if status_code == 200:
                external_reference = pago.get("external_reference")
                payment_status = pago.get("status") or ""
                transaction_amount = to_int(pago.get("transaction_amount"), 0)

                if external_reference:
                    conn = get_db()
                    c = conn.cursor()

                    reserva = c.execute("""
                        SELECT id, precio_total, monto_pagado, mp_tipo_pago
                        FROM reservas
                        WHERE id=?
                    """, (int(external_reference),)).fetchone()

                    if reserva:
                        precio_total = to_int(reserva[1])
                        monto_pagado_actual = to_int(reserva[2])
                        mp_tipo_pago = (reserva[3] or "").strip()

                        if payment_status == "approved":
                            nuevo_pagado = monto_pagado_actual

                            if mp_tipo_pago == "total":
                                nuevo_pagado = precio_total
                                nuevo_estado = "Confirmado"
                                nuevo_color = "lightgreen"
                                nuevo_precio = precio_total
                            else:
                                nuevo_pagado = min(precio_total, max(monto_pagado_actual, transaction_amount))
                                if nuevo_pagado >= precio_total:
                                    nuevo_estado = "Confirmado"
                                    nuevo_color = "lightgreen"
                                    nuevo_precio = precio_total
                                else:
                                    nuevo_estado = "Pendiente"
                                    nuevo_color = "orange"
                                    nuevo_precio = nuevo_pagado

                            c.execute("""
                                UPDATE reservas
                                SET monto_pagado=?,
                                    estado=?,
                                    color=?,
                                    precio=?,
                                    mp_payment_id=?,
                                    mp_status=?
                                WHERE id=?
                            """, (
                                nuevo_pagado,
                                nuevo_estado,
                                nuevo_color,
                                nuevo_precio,
                                str(payment_id),
                                payment_status,
                                int(external_reference)
                            ))
                        else:
                            c.execute("""
                                UPDATE reservas
                                SET mp_payment_id=?,
                                    mp_status=?
                                WHERE id=?
                            """, (
                                str(payment_id),
                                payment_status,
                                int(external_reference)
                            ))

                        conn.commit()

                    conn.close()
        except Exception as ex:
            print("ERROR WEBHOOK MP:", ex)

    return {"ok": True}, 200


@app.route("/pago_exitoso")
def pago_exitoso():
    return render_page("Pago exitoso", """
    <div class="card">
      <h2>Pago recibido</h2>
      <p>Tu pago fue procesado correctamente.</p>
      <p class="muted">La reserva se actualiza automáticamente en unos segundos.</p>
      <a class="btn btn-primary" href="/reservar">Volver</a>
    </div>
    """)


@app.route("/pago_pendiente")
def pago_pendiente():
    return render_page("Pago pendiente", """
    <div class="card">
      <h2>Pago pendiente</h2>
      <p>Mercado Pago informó que el pago todavía está pendiente.</p>
      <p class="muted">La reserva se confirmará automáticamente cuando el pago se acredite.</p>
      <a class="btn btn-primary" href="/reservar">Volver</a>
    </div>
    """)


@app.route("/pago_error")
def pago_error():
    return render_page("Pago no completado", """
    <div class="card">
      <h2>Pago no completado</h2>
      <p>No se pudo completar el pago.</p>
      <a class="btn btn-primary" href="/reservar">Volver</a>
    </div>
    """)


# =========================================================
# CAJA
# =========================================================

@app.route("/caja", methods=["GET", "POST"])
@login_required
def caja():
    conn = get_db()
    c = conn.cursor()

    hoy = datetime.now().strftime("%Y-%m-%d")
    mes_hoy = datetime.now().strftime("%Y-%m")
    anio_actual = datetime.now().strftime("%Y")

    if request.method == "POST":
        fecha_egreso = request.form.get("fecha_egreso") or hoy
        concepto = (request.form.get("concepto") or "").strip()
        monto = int(request.form.get("monto") or 0)

        if concepto and monto >= 0:
            c.execute(
                "INSERT INTO egresos (fecha, concepto, monto) VALUES (?, ?, ?)",
                (fecha_egreso, concepto, monto)
            )
            conn.commit()

    fecha_filtro = request.args.get("fecha") or hoy
    mes_filtro = request.args.get("mes") or mes_hoy
    anio_tabla = request.args.get("anio") or anio_actual

    ef_dia = c.execute(
        "SELECT COALESCE(SUM(monto_pagado),0) FROM reservas WHERE fecha=? AND metodo_pago='efectivo'",
        (fecha_filtro,)
    ).fetchone()[0]

    tr_dia = c.execute(
        "SELECT COALESCE(SUM(monto_pagado),0) FROM reservas WHERE fecha=? AND metodo_pago='transferencia'",
        (fecha_filtro,)
    ).fetchone()[0]

    qr_dia = c.execute(
        "SELECT COALESCE(SUM(monto_pagado),0) FROM reservas WHERE fecha=? AND metodo_pago='qr'",
        (fecha_filtro,)
    ).fetchone()[0]

    online_dia = c.execute(
        "SELECT COALESCE(SUM(monto_pagado),0) FROM reservas WHERE fecha=? AND metodo_pago='online'",
        (fecha_filtro,)
    ).fetchone()[0]

    ingresos_dia = ef_dia + tr_dia + qr_dia + online_dia

    reembolsos_dia = c.execute(
        "SELECT COALESCE(SUM(monto_reembolso),0) FROM reservas WHERE fecha=?",
        (fecha_filtro,)
    ).fetchone()[0]

    egresos_dia = c.execute(
        "SELECT COALESCE(SUM(monto),0) FROM egresos WHERE fecha=?",
        (fecha_filtro,)
    ).fetchone()[0]

    deuda_dia = c.execute("""
        SELECT COALESCE(SUM(precio_total - monto_pagado),0)
        FROM reservas
        WHERE fecha=? AND lower(trim(estado))!='cancelado'
    """, (fecha_filtro,)).fetchone()[0]

    total_dia = ingresos_dia - reembolsos_dia - egresos_dia

    ef_mes = c.execute(
        "SELECT COALESCE(SUM(monto_pagado),0) FROM reservas WHERE fecha LIKE ? AND metodo_pago='efectivo'",
        (mes_filtro + "%",)
    ).fetchone()[0]

    tr_mes = c.execute(
        "SELECT COALESCE(SUM(monto_pagado),0) FROM reservas WHERE fecha LIKE ? AND metodo_pago='transferencia'",
        (mes_filtro + "%",)
    ).fetchone()[0]

    qr_mes = c.execute(
        "SELECT COALESCE(SUM(monto_pagado),0) FROM reservas WHERE fecha LIKE ? AND metodo_pago='qr'",
        (mes_filtro + "%",)
    ).fetchone()[0]

    online_mes = c.execute(
        "SELECT COALESCE(SUM(monto_pagado),0) FROM reservas WHERE fecha LIKE ? AND metodo_pago='online'",
        (mes_filtro + "%",)
    ).fetchone()[0]

    ingresos_mes = ef_mes + tr_mes + qr_mes + online_mes

    reembolsos_mes = c.execute(
        "SELECT COALESCE(SUM(monto_reembolso),0) FROM reservas WHERE fecha LIKE ?",
        (mes_filtro + "%",)
    ).fetchone()[0]

    egresos_mes = c.execute(
        "SELECT COALESCE(SUM(monto),0) FROM egresos WHERE fecha LIKE ?",
        (mes_filtro + "%",)
    ).fetchone()[0]

    deuda_mes = c.execute("""
        SELECT COALESCE(SUM(precio_total - monto_pagado),0)
        FROM reservas
        WHERE fecha LIKE ? AND lower(trim(estado))!='cancelado'
    """, (mes_filtro + "%",)).fetchone()[0]

    total_mes = ingresos_mes - reembolsos_mes - egresos_mes

    meses = [
        ("01", "Enero"), ("02", "Febrero"), ("03", "Marzo"), ("04", "Abril"),
        ("05", "Mayo"), ("06", "Junio"), ("07", "Julio"), ("08", "Agosto"),
        ("09", "Septiembre"), ("10", "Octubre"), ("11", "Noviembre"), ("12", "Diciembre")
    ]

    filas_anuales = ""
    for mm, nombre_mes in meses:
        patron = f"{anio_tabla}-{mm}%"

        ingresos_m = c.execute(
            "SELECT COALESCE(SUM(monto_pagado),0) FROM reservas WHERE fecha LIKE ?",
            (patron,)
        ).fetchone()[0]

        reembolsos_m = c.execute(
            "SELECT COALESCE(SUM(monto_reembolso),0) FROM reservas WHERE fecha LIKE ?",
            (patron,)
        ).fetchone()[0]

        egresos_m = c.execute(
            "SELECT COALESCE(SUM(monto),0) FROM egresos WHERE fecha LIKE ?",
            (patron,)
        ).fetchone()[0]

        saldo_m = ingresos_m - reembolsos_m - egresos_m

        filas_anuales += f"""
        <tr>
          <td>{e(nombre_mes)}</td>
          <td>${to_int(ingresos_m)}</td>
          <td>${to_int(reembolsos_m)}</td>
          <td>${to_int(egresos_m)}</td>
          <td>${to_int(saldo_m)}</td>
        </tr>
        """

    egresos_rows = c.execute(
        "SELECT fecha, concepto, monto FROM egresos ORDER BY fecha DESC, id DESC"
    ).fetchall()

    filas_egresos = ""
    for egr in egresos_rows:
        filas_egresos += f"""
        <tr>
          <td>{e(egr[0])}</td>
          <td>{e(egr[1])}</td>
          <td>${to_int(egr[2])}</td>
        </tr>
        """

    conn.close()

    html = f"""
    <div class="card">
      <h2>Filtros de caja</h2>
      <form method="get">
        <div class="row">
          <div>
            <label>Fecha</label>
            <input type="date" name="fecha" value="{e(fecha_filtro)}">
          </div>
          <div>
            <label>Mes</label>
            <input type="month" name="mes" value="{e(mes_filtro)}">
          </div>
          <div>
            <label>Año</label>
            <input type="number" name="anio" value="{e(anio_tabla)}">
          </div>
        </div>
        <button class="btn btn-primary">Actualizar</button>
      </form>
    </div>

    <div class="card">
      <h2>Caja diaria ({e(fecha_filtro)})</h2>
      <div class="summary-grid">
        <div class="summary-box"><h4>Efectivo</h4><p>${to_int(ef_dia)}</p></div>
        <div class="summary-box"><h4>Transferencia</h4><p>${to_int(tr_dia)}</p></div>
        <div class="summary-box"><h4>QR</h4><p>${to_int(qr_dia)}</p></div>
        <div class="summary-box"><h4>Online</h4><p>${to_int(online_dia)}</p></div>
        <div class="summary-box"><h4>Ingresos</h4><p>${to_int(ingresos_dia)}</p></div>
        <div class="summary-box"><h4>Reembolsos</h4><p>${to_int(reembolsos_dia)}</p></div>
        <div class="summary-box"><h4>Egresos</h4><p>${to_int(egresos_dia)}</p></div>
        <div class="summary-box"><h4>Deuda pendiente</h4><p>${to_int(deuda_dia)}</p></div>
        <div class="summary-box"><h4>Total real</h4><p>${to_int(total_dia)}</p></div>
      </div>
    </div>

    <div class="card">
      <h2>Caja mensual ({e(mes_filtro)})</h2>
      <div class="summary-grid">
        <div class="summary-box"><h4>Efectivo</h4><p>${to_int(ef_mes)}</p></div>
        <div class="summary-box"><h4>Transferencia</h4><p>${to_int(tr_mes)}</p></div>
        <div class="summary-box"><h4>QR</h4><p>${to_int(qr_mes)}</p></div>
        <div class="summary-box"><h4>Online</h4><p>${to_int(online_mes)}</p></div>
        <div class="summary-box"><h4>Ingresos</h4><p>${to_int(ingresos_mes)}</p></div>
        <div class="summary-box"><h4>Reembolsos</h4><p>${to_int(reembolsos_mes)}</p></div>
        <div class="summary-box"><h4>Egresos</h4><p>${to_int(egresos_mes)}</p></div>
        <div class="summary-box"><h4>Deuda pendiente</h4><p>${to_int(deuda_mes)}</p></div>
        <div class="summary-box"><h4>Total real</h4><p>${to_int(total_mes)}</p></div>
      </div>
    </div>

    <div class="card">
      <h2>Cargar egreso</h2>
      <form method="post">
        <div class="row">
          <div>
            <label>Fecha</label>
            <input type="date" name="fecha_egreso" value="{e(fecha_filtro)}" required>
          </div>
          <div>
            <label>Concepto</label>
            <input name="concepto" required>
          </div>
          <div>
            <label>Monto</label>
            <input type="number" name="monto" min="0" required>
          </div>
        </div>
        <button class="btn btn-primary">Guardar egreso</button>
      </form>
    </div>

    <div class="card">
      <h3>Egresos</h3>
      <button class="btn btn-secondary" onclick="toggleEgresos()">
        👁 Ver / Ocultar egresos
      </button>

      <div id="tablaEgresos" style="display:none; margin-top:15px;">
        <div class="table-wrap">
          <table>
            <tr>
              <th>Fecha</th>
              <th>Concepto</th>
              <th>Monto</th>
            </tr>
            {filas_egresos or "<tr><td colspan='3'>Sin egresos todavía</td></tr>"}
          </table>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>Tabla anual ({e(anio_tabla)})</h2>
      <div class="table-wrap">
        <table>
          <tr>
            <th>Mes</th>
            <th>Ingresos</th>
            <th>Reembolsos</th>
            <th>Egresos</th>
            <th>Saldo</th>
          </tr>
          {filas_anuales}
        </table>
      </div>
    </div>

    <script>
    function toggleEgresos(){{
        var tabla = document.getElementById("tablaEgresos");
        tabla.style.display = (tabla.style.display === "none") ? "block" : "none";
    }}
    </script>
    """

    return render_page("Caja", html)


# =========================================================
# RESERVA ONLINE (PÚBLICA) + MP
# =========================================================

@app.route("/reservar", methods=["GET", "POST"])
def reservar_online():
    cfg = get_config()
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    if request.method == "POST":
        cliente = (request.form.get("cliente") or "").strip()
        telefono = (request.form.get("telefono") or "").strip()
        cancha_txt = request.form.get("cancha")
        fecha = request.form.get("fecha")
        hora = (request.form.get("hora") or "").strip()
        tipo_pago = request.form.get("tipo_pago")
        duracion = to_int(request.form.get("duracion"), 90)
        if duracion not in [60, 90]:
            duracion = 90

        if not cliente or not telefono or not cancha_txt or not fecha or not hora or not tipo_pago:
            return render_page("Error", """
            <div class="card">
              <div class="err">Faltan datos obligatorios</div>
              <a class="btn btn-secondary" href="/reservar">Volver</a>
            </div>
            """)

        cancha = int(cancha_txt)
        hora = hora[:5]

        if not horario_habilitado_para_reservar(fecha, hora, 60):
            return render_page("Error", """
            <div class="card">
              <div class="err">Solo se pueden reservar turnos con al menos 1 hora de anticipación.</div>
              <a class="btn btn-secondary" href="/reservar">Volver</a>
            </div>
            """)

        if reserva_se_superpone(cancha, fecha, hora, duracion):
            return render_page("Error", """
            <div class="card">
              <div class="err">Ese turno ya está ocupado</div>
              <a class="btn btn-secondary" href="/reservar">Volver</a>
            </div>
            """)

        if tipo_pago == "total":
            estado = "Confirmado"
            texto_pago = "Pago total"
        else:
            estado = "Pendiente"
            texto_pago = "Seña"

        precio_total = precio_total_por_turno(hora, duracion, cfg)
        monto_inicial = monto_pagado_inicial_por_estado(estado, hora, duracion, cfg)

        # Siempre se crea como pendiente hasta confirmación de MP
        estado_inicial_db = "Pendiente"
        color = "orange"
        precio_visible = monto_inicial

        conn = get_db()
        c = conn.cursor()

        c.execute("""
            INSERT INTO reservas
            (cliente, telefono, cancha, fecha, hora, duracion, metodo_pago, color, precio, precio_total, estado, monto_pagado, monto_reembolso, mp_tipo_pago)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cliente,
            telefono,
            cancha,
            fecha,
            hora,
            duracion,
            "online",
            color,
            precio_visible,
            precio_total,
            estado_inicial_db,
            0,
            0,
            tipo_pago
        ))

        reserva_id = c.lastrowid
        conn.commit()
        conn.close()

        guardar_o_actualizar_cliente(cliente, telefono)

        titulo = f"Reserva Pádel 37 - Cancha {cancha} - {fecha} {hora} - {texto_pago}"
        monto_a_cobrar = precio_total if tipo_pago == "total" else monto_inicial

        status_code, pref = crear_preferencia_mp(
            reserva_id=reserva_id,
            titulo=titulo,
            precio=monto_a_cobrar,
            tipo_pago=tipo_pago
        )

        if status_code not in [200, 201]:
            return render_page("Error", f"""
            <div class="card">
              <div class="err">No se pudo generar el pago en Mercado Pago.</div>
              <pre class="muted">{e(json.dumps(pref, ensure_ascii=False, indent=2))}</pre>
              <a class="btn btn-secondary" href="/reservar">Volver</a>
            </div>
            """)

        pref_id = pref.get("id")
        init_point = pref.get("init_point") or pref.get("sandbox_init_point") or ""

        conn = get_db()
        c = conn.cursor()
        c.execute("""
            UPDATE reservas
            SET mp_preference_id=?, mp_checkout_url=?, mp_status='pending'
            WHERE id=?
        """, (
            pref_id,
            init_point,
            reserva_id
        ))
        conn.commit()
        conn.close()

        return redirect(init_point)

    fecha = request.args.get("fecha") or fecha_hoy
    cancha = int(request.args.get("cancha") or 1)
    hora_sel = request.args.get("hora") or ""
    duracion = to_int(request.args.get("duracion"), 90)
    if duracion not in [60, 90]:
        duracion = 90

    disponibles = horarios_disponibles_online(cancha, fecha, duracion)

    botones = ""
    for h in disponibles:
        clase = "btn btn-secondary"
        estilo = "margin:5px; min-width:90px;"

        if h == hora_sel:
            clase = "btn btn-primary"
            estilo += " outline:2px solid #fff;"

        botones += f'''
        <a href="/reservar?fecha={e(fecha)}&cancha={cancha}&duracion={duracion}&hora={e(h)}"
           class="{clase}"
           style="{estilo}">
           {e(h)}
        </a>
        '''

    estado_horarios = (
        f"<p class='muted'>Horarios disponibles para Cancha {cancha} el {e(fecha)} ({duracion} min): {len(disponibles)}</p>"
        if disponibles else
        f"<p class='err'>No hay horarios disponibles para Cancha {cancha} el {e(fecha)}.</p>"
    )

    precio_estimado = ""
    if hora_sel:
        total_turno = precio_total_por_turno(hora_sel, duracion, cfg)
        senia = monto_pagado_inicial_por_estado("Pendiente", hora_sel, duracion, cfg)
        precio_estimado = f"""
        <div class="card">
          <h3>Importes</h3>
          <p><b>Total del turno:</b> ${total_turno}</p>
          <p><b>Seña:</b> ${senia}</p>
        </div>
        """

    html = f"""
    <div class="card">
      <h2>Reservar turno</h2>

      <form method="get" action="/reservar">
        <div class="row">
          <div>
            <label>Fecha</label>
            <input type="date" name="fecha" value="{e(fecha)}" required>
          </div>

          <div>
            <label>Cancha</label>
            <select name="cancha" required>
              <option value="1" {"selected" if cancha == 1 else ""}>Cancha 1</option>
              <option value="2" {"selected" if cancha == 2 else ""}>Cancha 2</option>
              <option value="3" {"selected" if cancha == 3 else ""}>Cancha 3</option>
            </select>
          </div>

          <div>
            <label>Duración</label>
            <select name="duracion" required>
              <option value="60" {"selected" if duracion == 60 else ""}>1 hora</option>
              <option value="90" {"selected" if duracion == 90 else ""}>1 hora y media</option>
            </select>
          </div>

          <div style="display:flex;align-items:end;">
            <button class="btn btn-secondary" type="submit">Ver horarios</button>
          </div>
        </div>
      </form>
    </div>

    <div class="card">
      <h3>Horarios disponibles</h3>
      {estado_horarios}
      <div style="display:flex;flex-wrap:wrap;gap:8px;">
        {botones or "<span class='muted'>No hay horarios para mostrar.</span>"}
      </div>
    </div>

    {precio_estimado}

    <div class="card">
      <h3>Completar reserva</h3>

      <form method="post" action="/reservar">
        <input type="hidden" name="fecha" value="{e(fecha)}">
        <input type="hidden" name="cancha" value="{cancha}">
        <input type="hidden" name="duracion" value="{duracion}">
        <input type="hidden" name="hora" value="{e(hora_sel)}">

        <div class="row">
          <div>
            <label>Nombre</label>
            <input type="text" name="cliente" required>
          </div>

          <div>
            <label>Teléfono</label>
            <input type="text" name="telefono" required>
          </div>
        </div>

        <div class="row">
          <div>
            <label>Cancha elegida</label>
            <input type="text" value="Cancha {cancha}" readonly>
          </div>

          <div>
            <label>Fecha elegida</label>
            <input type="text" value="{e(fecha)}" readonly>
          </div>

          <div>
            <label>Duración elegida</label>
            <input type="text" value="{duracion} min" readonly>
          </div>

          <div>
            <label>Horario elegido</label>
            <input type="text" value="{e(hora_sel or 'Elegí un horario arriba')}" readonly>
          </div>
        </div>

        <div class="row">
          <div>
            <label>Cómo querés pagar</label>
            <select name="tipo_pago" required>
              <option value="">Seleccionar opción</option>
              <option value="pendiente">Seña</option>
              <option value="total">Pago total</option>
            </select>
          </div>
        </div>

        <p class="muted">Los turnos pueden ser de 1 hora o 1 hora y media.</p>
        <p class="muted">Al hacer click te redirigimos a Mercado Pago para completar el pago.</p>

        <button class="btn btn-primary" type="submit">Continuar a pagar</button>
      </form>
    </div>
    """

    return render_page("Reservar online", html)


if __name__ == "__main__":
    app.run(debug=True)