from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from flask import Flask, request, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, func

APP_TITLE = "Pádel 37"
CANTIDAD_CANCHAS = 3

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///padel.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# =========================
# MODELOS (IDs automáticos)
# =========================

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # autoincrement
    nombre = db.Column(db.String(120), nullable=False, index=True)
    telefono = db.Column(db.String(50), nullable=True)

    turnos = db.relationship("Turno", backref="cliente", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Cliente {self.id} {self.nombre}>"


class Turno(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # autoincrement
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False, index=True)

    cancha = db.Column(db.Integer, nullable=False)  # 1..3
    fecha = db.Column(db.String(10), nullable=False, index=True)  # "YYYY-MM-DD"
    hora = db.Column(db.String(5), nullable=False)  # "HH:MM"

    precio = db.Column(db.Integer, nullable=True)  # opcional (pesos)
    estado_pago = db.Column(db.String(20), nullable=False, default="pendiente")  # pendiente / pagado
    metodo_pago = db.Column(db.String(20), nullable=True)  # efectivo / transferencia / qr

    __table_args__ = (
        UniqueConstraint("cancha", "fecha", "hora", name="uq_turno_cancha_fecha_hora"),
    )

    def __repr__(self):
        return f"<Turno {self.id} C{self.cancha} {self.fecha} {self.hora}>"


class Movimiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # autoincrement
    fecha = db.Column(db.String(10), nullable=False, index=True)  # "YYYY-MM-DD"
    tipo = db.Column(db.String(10), nullable=False)  # ingreso / egreso
    monto = db.Column(db.Integer, nullable=False)  # pesos (entero)
    metodo_pago = db.Column(db.String(20), nullable=True)  # efectivo / transferencia / qr
    descripcion = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f"<Mov {self.id} {self.tipo} {self.fecha} {self.monto}>"


# Crear DB/tablas (Flask 3 compatible)
with app.app_context():
    db.create_all()


# =========================
# UTILIDADES HTML SIMPLES
# =========================

def header(title: str = APP_TITLE) -> str:
    return f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>{APP_TITLE}</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 24px; }}
          a {{ text-decoration: none; }}
          .menu a {{ margin-right: 12px; }}
          .box {{ border: 1px solid #ddd; padding: 12px; border-radius: 8px; margin: 12px 0; }}
          input, select {{ padding: 6px; margin: 4px 0; }}
          button {{ padding: 8px 12px; cursor: pointer; }}
          table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
          th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
          th {{ background: #f5f5f5; }}
          .ok {{ color: green; font-weight: bold; }}
          .err {{ color: #b00020; font-weight: bold; }}
          .muted {{ color: #666; }}
        </style>
      </head>
      <body>
        <h1>{title}</h1>
        <div class="menu">
          <a href="/">Inicio</a>
          <a href="/clientes">Clientes</a>
          <a href="/turnos">Turnos</a>
          <a href="/buscar">Buscar</a>
          <a href="/movimientos">Ingresos/Gastos</a>
          <a href="/reportes">Saldos</a>
        </div>
        <hr/>
    """


def footer() -> str:
    return "</body></html>"


def hoy_str() -> str:
    return date.today().strftime("%Y-%m-%d")


def parse_int(value: str | None, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        # acepta "1000" o "1.000" o "1,000" y lo convierte
        cleaned = value.replace(".", "").replace(",", "")
        return int(cleaned)
    except Exception:
        return default


# =========================
# RUTAS
# =========================

@app.route("/")
def home():
    return (
        header(APP_TITLE)
        + f"""
        <div class="box">
          <p class="ok">Sistema iniciado correctamente ✅</p>
          <p class="muted">Canchas: {CANTIDAD_CANCHAS}</p>
        </div>

        <div class="box">
          <h3>Qué podés hacer</h3>
          <ul>
            <li>Cargar clientes (con ID automático)</li>
            <li>Reservar turnos (evita doble reserva por cancha/fecha/hora)</li>
            <li>Buscar por nombre de cliente y ver sus turnos</li>
            <li>Cargar ingresos y egresos (efectivo/transferencia/QR)</li>
            <li>Ver saldos por día y por mes</li>
          </ul>
        </div>
        """
        + footer()
    )


# ---------- CLIENTES ----------
@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    msg = ""
    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        telefono = (request.form.get("telefono") or "").strip() or None

        if not nombre:
            msg = '<p class="err">Falta el nombre.</p>'
        else:
            c = Cliente(nombre=nombre, telefono=telefono)
            db.session.add(c)
            db.session.commit()
            msg = f'<p class="ok">Cliente creado ✅ (ID {c.id})</p>'

    lista = Cliente.query.order_by(Cliente.nombre.asc()).all()

    rows = ""
    for c in lista:
        rows += f"""
        <tr>
          <td>{c.id}</td>
          <td>{c.nombre}</td>
          <td>{c.telefono or "-"}</td>
          <td><a href="/buscar/cliente?id={c.id}">Ver turnos</a></td>
        </tr>
        """

    return (
        header("Clientes")
        + f"""
        {msg}
        <div class="box">
          <h3>Agregar cliente</h3>
          <form method="post">
            <div>Nombre:<br><input name="nombre" required></div>
            <div>Teléfono (opcional):<br><input name="telefono"></div>
            <button type="submit">Guardar</button>
          </form>
        </div>

        <div class="box">
          <h3>Agenda de clientes</h3>
          <table>
            <tr><th>ID</th><th>Nombre</th><th>Teléfono</th><th>Acción</th></tr>
            {rows or "<tr><td colspan='4'>Sin clientes todavía</td></tr>"}
          </table>
        </div>
        """
        + footer()
    )


# ---------- TURNOS ----------
@app.route("/turnos", methods=["GET", "POST"])
def turnos():
    msg = ""
    if request.method == "POST":
        cliente_id = parse_int(request.form.get("cliente_id"))
        cancha = parse_int(request.form.get("cancha"))
        fecha = (request.form.get("fecha") or "").strip()
        hora = (request.form.get("hora") or "").strip()
        precio = parse_int(request.form.get("precio"), default=None)

        estado_pago = (request.form.get("estado_pago") or "pendiente").strip()
        metodo_pago = (request.form.get("metodo_pago") or "").strip() or None

        # Validaciones
        cliente = Cliente.query.get(cliente_id) if cliente_id else None
        if not cliente:
            msg = '<p class="err">Cliente ID inválido.</p>'
        elif cancha not in range(1, CANTIDAD_CANCHAS + 1):
            msg = f'<p class="err">Cancha inválida. Debe ser 1 a {CANTIDAD_CANCHAS}.</p>'
        elif len(fecha) != 10 or len(hora) != 5:
            msg = '<p class="err">Fecha u hora inválida.</p>'
        else:
            # Evitar doble reserva
            existente = Turno.query.filter_by(cancha=cancha, fecha=fecha, hora=hora).first()
            if existente:
                msg = f'<p class="err">Ya existe un turno en Cancha {cancha} para {fecha} {hora}.</p>'
            else:
                t = Turno(
                    cliente_id=cliente.id,
                    cancha=cancha,
                    fecha=fecha,
                    hora=hora,
                    precio=precio,
                    estado_pago=estado_pago,
                    metodo_pago=metodo_pago,
                )
                db.session.add(t)
                db.session.commit()
                msg = f'<p class="ok">Turno creado ✅ (ID {t.id})</p>'

    # Listado
    lista = Turno.query.order_by(Turno.fecha.desc(), Turno.hora.desc()).limit(200).all()

    rows = ""
    for t in lista:
        rows += f"""
        <tr>
          <td>{t.id}</td>
          <td>{t.fecha}</td>
          <td>{t.hora}</td>
          <td>{t.cancha}</td>
          <td>{t.cliente.nombre} (ID {t.cliente.id})</td>
          <td>{t.precio if t.precio is not None else "-"}</td>
          <td>{t.estado_pago}</td>
          <td>{t.metodo_pago or "-"}</td>
        </tr>
        """

    # opciones canchas
    cancha_opts = "".join([f'<option value="{i}">Cancha {i}</option>' for i in range(1, CANTIDAD_CANCHAS + 1)])

    return (
        header("Turnos (Agenda)")
        + f"""
        {msg}

        <div class="box">
          <h3>Crear turno</h3>
          <form method="post">
            <div>Cliente ID:<br><input name="cliente_id" type="number" min="1" required></div>

            <div>Cancha:<br>
              <select name="cancha" required>
                {cancha_opts}
              </select>
            </div>

            <div>Fecha:<br><input name="fecha" type="date" value="{hoy_str()}" required></div>
            <div>Hora:<br><input name="hora" type="time" required></div>

            <div>Precio (opcional):<br><input name="precio" type="number" min="0"></div>

            <div>Estado pago:<br>
              <select name="estado_pago">
                <option value="pendiente">pendiente</option>
                <option value="pagado">pagado</option>
              </select>
            </div>

            <div>Método pago (si está pagado):<br>
              <select name="metodo_pago">
                <option value="">(vacío)</option>
                <option value="efectivo">efectivo</option>
                <option value="transferencia">transferencia</option>
                <option value="qr">qr</option>
              </select>
            </div>

            <button type="submit">Reservar</button>
          </form>
          <p class="muted">Tip: si querés buscar cliente por nombre, usá “Buscar”.</p>
        </div>

        <div class="box">
          <h3>Agenda de turnos (últimos 200)</h3>
          <table>
            <tr>
              <th>ID Turno</th><th>Fecha</th><th>Hora</th><th>Cancha</th>
              <th>Cliente</th><th>Precio</th><th>Pago</th><th>Método</th>
            </tr>
            {rows or "<tr><td colspan='8'>Sin turnos todavía</td></tr>"}
          </table>
        </div>
        """
        + footer()
    )


# ---------- BUSCAR ----------
@app.route("/buscar")
def buscar():
    return (
        header("Buscar")
        + """
        <div class="box">
          <h3>Buscar cliente por nombre</h3>
          <form action="/buscar/nombre" method="get">
            Nombre: <input name="q" required>
            <button>Buscar</button>
          </form>
          <p class="muted">Busca por coincidencia (no importa mayúsculas/minúsculas).</p>
        </div>

        <div class="box">
          <h3>Ver turnos por Cliente ID</h3>
          <form action="/buscar/cliente" method="get">
            ID Cliente: <input name="id" type="number" min="1" required>
            <button>Ver</button>
          </form>
        </div>
        """
        + footer()
    )


@app.route("/buscar/nombre")
def buscar_nombre():
    q = (request.args.get("q") or "").strip()
    if not q:
        return redirect("/buscar")

    clientes = (
        Cliente.query
        .filter(Cliente.nombre.ilike(f"%{q}%"))
        .order_by(Cliente.nombre.asc())
        .all()
    )

    if not clientes:
        return (
            header("Buscar por nombre")
            + f"<p class='err'>No se encontraron clientes con: <b>{q}</b></p>"
            + "<a href='/buscar'>Volver</a>"
            + footer()
        )

    html = header("Resultados de búsqueda")
    html += f"<h2>Resultados para: {q}</h2><ul>"
    for c in clientes:
        html += f"""
        <li>
          <b>{c.nombre}</b> (ID {c.id}) - Tel: {c.telefono or "-"}
          — <a href="/buscar/cliente?id={c.id}">Ver turnos</a>
        </li>
        """
    html += "</ul><a href='/buscar'>Volver</a>"
    html += footer()
    return html


@app.route("/buscar/cliente")
def buscar_cliente():
    cid = parse_int(request.args.get("id"))
    if not cid:
        return redirect("/buscar")

    cliente = Cliente.query.get(cid)
    if not cliente:
        return (
            header("Cliente")
            + f"<p class='err'>No existe cliente con ID {cid}</p>"
            + "<a href='/buscar'>Volver</a>"
            + footer()
        )

    turnos = (
        Turno.query
        .filter_by(cliente_id=cid)
        .order_by(Turno.fecha.desc(), Turno.hora.desc())
        .all()
    )

    if not turnos:
        lista = "<li>Este cliente no tiene turnos</li>"
    else:
        lista = ""
        for t in turnos:
            lista += (
                f"<li><b>Turno ID {t.id}</b> — {t.fecha} {t.hora} — Cancha {t.cancha} "
                f"— Precio: {t.precio if t.precio is not None else '-'} "
                f"— Pago: {t.estado_pago} {('('+t.metodo_pago+')') if t.metodo_pago else ''}"
                f"</li>"
            )

    return (
        header("Cliente")
        + f"""
        <h2>Cliente: {cliente.nombre} (ID {cliente.id})</h2>
        <p>Tel: {cliente.telefono or "-"}</p>
        <h3>Turnos</h3>
        <ul>{lista}</ul>
        <a href="/buscar">Volver</a>
        """
        + footer()
    )


# ---------- INGRESOS / EGRESOS ----------
@app.route("/movimientos", methods=["GET", "POST"])
def movimientos():
    msg = ""
    if request.method == "POST":
        fecha = (request.form.get("fecha") or hoy_str()).strip()
        tipo = (request.form.get("tipo") or "").strip()
        monto = parse_int(request.form.get("monto"))
        metodo = (request.form.get("metodo_pago") or "").strip() or None
        desc = (request.form.get("descripcion") or "").strip() or None

        if tipo not in ("ingreso", "egreso"):
            msg = '<p class="err">Tipo inválido.</p>'
        elif monto is None or monto < 0:
            msg = '<p class="err">Monto inválido.</p>'
        else:
            m = Movimiento(fecha=fecha, tipo=tipo, monto=monto, metodo_pago=metodo, descripcion=desc)
            db.session.add(m)
            db.session.commit()
            msg = f'<p class="ok">Movimiento guardado ✅ (ID {m.id})</p>'

    lista = Movimiento.query.order_by(Movimiento.fecha.desc(), Movimiento.id.desc()).limit(300).all()

    rows = ""
    for m in lista:
        rows += f"""
        <tr>
          <td>{m.id}</td>
          <td>{m.fecha}</td>
          <td>{m.tipo}</td>
          <td>{m.monto}</td>
          <td>{m.metodo_pago or "-"}</td>
          <td>{m.descripcion or "-"}</td>
        </tr>
        """

    return (
        header("Ingresos y Gastos")
        + f"""
        {msg}

        <div class="box">
          <h3>Agregar movimiento</h3>
          <form method="post">
            <div>Fecha:<br><input name="fecha" type="date" value="{hoy_str()}" required></div>
            <div>Tipo:<br>
              <select name="tipo" required>
                <option value="ingreso">ingreso</option>
                <option value="egreso">egreso</option>
              </select>
            </div>
            <div>Monto (pesos):<br><input name="monto" type="number" min="0" required></div>
            <div>Método de pago:<br>
              <select name="metodo_pago">
                <option value="">(vacío)</option>
                <option value="efectivo">efectivo</option>
                <option value="transferencia">transferencia</option>
                <option value="qr">qr</option>
              </select>
            </div>
            <div>Descripción (opcional):<br><input name="descripcion"></div>
            <button type="submit">Guardar</button>
          </form>
        </div>

        <div class="box">
          <h3>Listado (últimos 300)</h3>
          <table>
            <tr><th>ID</th><th>Fecha</th><th>Tipo</th><th>Monto</th><th>Método</th><th>Descripción</th></tr>
            {rows or "<tr><td colspan='6'>Sin movimientos todavía</td></tr>"}
          </table>
        </div>
        """
        + footer()
    )


# ---------- REPORTES SALDOS ----------
@app.route("/reportes")
def reportes():
    # Saldos por día (sum ingresos - egresos)
    por_dia = (
        db.session.query(
            Movimiento.fecha,
            func.sum(func.case((Movimiento.tipo == "ingreso", Movimiento.monto), else_=0)).label("ingresos"),
            func.sum(func.case((Movimiento.tipo == "egreso", Movimiento.monto), else_=0)).label("egresos"),
        )
        .group_by(Movimiento.fecha)
        .order_by(Movimiento.fecha.desc())
        .limit(60)
        .all()
    )

    rows_dia = ""
    for f, ing, egr in por_dia:
        ing = ing or 0
        egr = egr or 0
        saldo = ing - egr
        rows_dia += f"<tr><td>{f}</td><td>{ing}</td><td>{egr}</td><td><b>{saldo}</b></td></tr>"

    # Saldos por mes: usa YYYY-MM (substr)
    por_mes = (
        db.session.query(
            func.substr(Movimiento.fecha, 1, 7).label("mes"),
            func.sum(func.case((Movimiento.tipo == "ingreso", Movimiento.monto), else_=0)).label("ingresos"),
            func.sum(func.case((Movimiento.tipo == "egreso", Movimiento.monto), else_=0)).label("egresos"),
        )
        .group_by("mes")
        .order_by(func.substr(Movimiento.fecha, 1, 7).desc())
        .limit(24)
        .all()
    )

    rows_mes = ""
    for mes, ing, egr in por_mes:
        ing = ing or 0
        egr = egr or 0
        saldo = ing - egr
        rows_mes += f"<tr><td>{mes}</td><td>{ing}</td><td>{egr}</td><td><b>{saldo}</b></td></tr>"

    return (
        header("Saldos diarios y mensuales")
        + f"""
        <div class="box">
          <h3>Saldos por día (últimos 60 días cargados)</h3>
          <table>
            <tr><th>Fecha</th><th>Ingresos</th><th>Egresos</th><th>Saldo</th></tr>
            {rows_dia or "<tr><td colspan='4'>Sin datos todavía</td></tr>"}
          </table>
        </div>

        <div class="box">
          <h3>Saldos por mes (últimos 24 meses cargados)</h3>
          <table>
            <tr><th>Mes</th><th>Ingresos</th><th>Egresos</th><th>Saldo</th></tr>
            {rows_mes or "<tr><td colspan='4'>Sin datos todavía</td></tr>"}
          </table>
        </div>
        """
        + footer()
    )


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    app.run(debug=True)