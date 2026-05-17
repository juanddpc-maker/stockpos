"""
database.py — UniControl
SQLite (local/dev) ↔ PostgreSQL (producción)
Detección automática por variable DATABASE_URL
"""
import os, sqlite3, random
from contextlib import contextmanager
from datetime import datetime, timedelta

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_PG = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")
_SQLITE = os.path.join(os.path.dirname(__file__), "data", "stockpos.db")


def _adapt(sql):
    if USE_PG:
        sql = sql.replace("?", "%s")
        sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        sql = sql.replace("INSERT OR IGNORE", "INSERT")
        sql = sql.replace("INSERT OR REPLACE", "INSERT")
    return sql


def _sqlite():
    os.makedirs(os.path.dirname(_SQLITE), exist_ok=True)
    c = sqlite3.connect(_SQLITE, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def _pg():
    import psycopg2, psycopg2.extras
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


@contextmanager
def _ctx():
    if USE_PG:
        conn = _pg()
        try:
            yield conn; conn.commit()
        except:
            conn.rollback(); raise
        finally:
            conn.close()
    else:
        conn = _sqlite()
        try:
            yield conn; conn.commit()
        finally:
            conn.close()


_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS categorias(
  id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE,
  emoji TEXT DEFAULT '🗂️', descripcion TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS productos(
  id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
  precio REAL NOT NULL, categoria_id INTEGER, emoji TEXT DEFAULT '📦',
  codigo_barras TEXT, descripcion TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(categoria_id) REFERENCES categorias(id));
CREATE TABLE IF NOT EXISTS inventario(
  id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER NOT NULL,
  localidad TEXT NOT NULL DEFAULT 'Almacén Central', cantidad INTEGER NOT NULL DEFAULT 0,
  min_stock INTEGER DEFAULT 5, max_stock INTEGER DEFAULT 100,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(producto_id) REFERENCES productos(id));
CREATE TABLE IF NOT EXISTS clientes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
  telefono TEXT, email TEXT, rfc TEXT, direccion TEXT, notas TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS ventas(
  id INTEGER PRIMARY KEY AUTOINCREMENT, folio TEXT NOT NULL UNIQUE,
  fecha TEXT NOT NULL, cliente_id INTEGER, subtotal REAL NOT NULL DEFAULT 0,
  impuesto REAL NOT NULL DEFAULT 0, total REAL NOT NULL DEFAULT 0,
  metodo_pago TEXT DEFAULT 'Efectivo', estado TEXT DEFAULT 'Completada',
  notas TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(cliente_id) REFERENCES clientes(id));
CREATE TABLE IF NOT EXISTS venta_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT, venta_id INTEGER NOT NULL,
  producto_id INTEGER NOT NULL, cantidad INTEGER NOT NULL,
  precio_unitario REAL NOT NULL, subtotal REAL NOT NULL,
  FOREIGN KEY(venta_id) REFERENCES ventas(id),
  FOREIGN KEY(producto_id) REFERENCES productos(id));
CREATE TABLE IF NOT EXISTS config(clave TEXT PRIMARY KEY, valor TEXT);
"""

_DDL_PG = """
CREATE TABLE IF NOT EXISTS categorias(
  id SERIAL PRIMARY KEY, nombre TEXT NOT NULL UNIQUE,
  emoji TEXT DEFAULT '🗂️', descripcion TEXT, created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS productos(
  id SERIAL PRIMARY KEY, nombre TEXT NOT NULL, precio NUMERIC(12,2) NOT NULL,
  categoria_id INTEGER REFERENCES categorias(id), emoji TEXT DEFAULT '📦',
  codigo_barras TEXT, descripcion TEXT, created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS inventario(
  id SERIAL PRIMARY KEY, producto_id INTEGER NOT NULL REFERENCES productos(id),
  localidad TEXT NOT NULL DEFAULT 'Almacén Central', cantidad INTEGER NOT NULL DEFAULT 0,
  min_stock INTEGER DEFAULT 5, max_stock INTEGER DEFAULT 100, updated_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS clientes(
  id SERIAL PRIMARY KEY, nombre TEXT NOT NULL, telefono TEXT, email TEXT,
  rfc TEXT, direccion TEXT, notas TEXT, created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS ventas(
  id SERIAL PRIMARY KEY, folio TEXT NOT NULL UNIQUE, fecha TIMESTAMPTZ NOT NULL,
  cliente_id INTEGER REFERENCES clientes(id), subtotal NUMERIC(12,2) NOT NULL DEFAULT 0,
  impuesto NUMERIC(12,2) NOT NULL DEFAULT 0, total NUMERIC(12,2) NOT NULL DEFAULT 0,
  metodo_pago TEXT DEFAULT 'Efectivo', estado TEXT DEFAULT 'Completada',
  notas TEXT, created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS venta_items(
  id SERIAL PRIMARY KEY, venta_id INTEGER NOT NULL REFERENCES ventas(id),
  producto_id INTEGER NOT NULL REFERENCES productos(id), cantidad INTEGER NOT NULL,
  precio_unitario NUMERIC(12,2) NOT NULL, subtotal NUMERIC(12,2) NOT NULL);
CREATE TABLE IF NOT EXISTS config(clave TEXT PRIMARY KEY, valor TEXT);
"""


def init_db():
    with _ctx() as conn:
        cur = conn.cursor()
        if USE_PG:
            for s in _DDL_PG.split(";"):
                s = s.strip()
                if s: cur.execute(s)
            cur.execute("SELECT COUNT(*) as n FROM categorias")
            n = cur.fetchone()['n']
        else:
            conn.executescript(_DDL_SQLITE)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM categorias")
            n = cur.fetchone()[0]
        if n == 0:
            _seed(conn, cur)


def _seed(conn, cur):
    ph = "%s" if USE_PG else "?"

    def ins(sql, rows):
        cur.executemany(sql.replace("?", ph), rows)

    ins("INSERT INTO categorias(nombre,emoji,descripcion) VALUES(?,?,?)", [
        ('Uniformes Escolares','🎒','Uniformes para nivel básico y medio'),
        ('Uniformes Deportivos','⚽','Pants, shorts y playeras deportivas'),
        ('Uniformes Empresariales','👔','Camisas, chalecos y pantalones de trabajo'),
        ('Calzado','👟','Zapatos y tenis escolares/deportivos'),
        ('Accesorios','🧢','Corbatas, cinturones, gorras y más'),
    ])
    ins("INSERT INTO productos(nombre,precio,categoria_id,emoji) VALUES(?,?,?,?)", [
        ('Camisa Escolar Blanca',   185, 1, '👕'),
        ('Pantalón Escolar Azul',   220, 1, '👖'),
        ('Falda Escolar Cuadros',   195, 1, '🩱'),
        ('Sudadera Escolar',        280, 1, '🧥'),
        ('Pants Deportivo Completo',350, 2, '🩳'),
        ('Playera Deportiva',       150, 2, '👕'),
        ('Short Deportivo',         120, 2, '🩲'),
        ('Camisa Empresarial',      320, 3, '👔'),
        ('Chaleco Empresarial',     280, 3, '🦺'),
        ('Pantalón de Trabajo',     350, 3, '👖'),
        ('Zapato Escolar Negro',    480, 4, '👞'),
        ('Tenis Deportivo Blanco',  520, 4, '👟'),
        ('Corbata Escolar',          85, 5, '👔'),
        ('Cinturón Negro',          110, 5, '🪢'),
        ('Gorra con Logo',          145, 5, '🧢'),
    ])
    ins("INSERT INTO inventario(producto_id,localidad,cantidad,min_stock,max_stock) VALUES(?,?,?,?,?)", [
        (1,'Tienda Principal',45,10,100),(2,'Tienda Principal',38,10,80),
        (3,'Tienda Principal',22,8,60),(4,'Almacén',30,10,80),
        (5,'Almacén',15,5,50),(6,'Tienda Principal',60,15,120),
        (7,'Tienda Principal',55,15,100),(8,'Almacén',20,8,60),
        (9,'Almacén',12,5,40),(10,'Almacén',18,5,50),
        (11,'Tienda Principal',4,10,60),(12,'Tienda Principal',8,10,60),
        (13,'Tienda Principal',35,10,80),(14,'Almacén',25,10,60),
        (15,'Almacén',3,5,40),
    ])
    ins("INSERT INTO clientes(nombre,telefono,email,rfc,direccion,notas) VALUES(?,?,?,?,?,?)", [
        ('Escuela Primaria Benito Juárez','664-100-0001','compras@juarez.edu.mx','ESB900101AA1','Av. Principal 100, TJ','Pedido anual en agosto'),
        ('Secundaria Lázaro Cárdenas',   '664-100-0002','admin@lazaro.edu.mx',  'SLC850615BB2','Blvd. Centro 200, TJ', 'Cliente frecuente'),
        ('Empresa Logística MX',         '664-100-0003','rh@logisticamx.com',   'ELM920320CC3','Zona Industrial 45, TJ','Uniformes ejecutivos'),
        ('Deportivo Municipal',          '664-100-0004','contacto@deportivo.mx','DMP880712DD4','Parque Central s/n, TJ','Equipos de fútbol'),
        ('Prepa Técnica No. 5',          '664-100-0005','prepa5@edu.mx',        'PTN950815EE5','Col. Libertad 78, TJ', ''),
    ])
    cfg = [('app_nombre','UniControl'),('app_subtitulo','Sistema de Uniformes'),
           ('empresa_nombre','Mi Empresa de Uniformes'),('empresa_rfc',''),
           ('empresa_direccion',''),('empresa_telefono',''),('empresa_email',''),
           ('iva_pct','16'),('moneda','MXN'),('groq_api_key','')]
    if USE_PG:
        for k,v in cfg:
            cur.execute("INSERT INTO config VALUES(%s,%s) ON CONFLICT DO NOTHING",(k,v))
    else:
        for k,v in cfg:
            cur.execute("INSERT OR IGNORE INTO config VALUES(?,?)",(k,v))

    # Ventas de muestra
    precios = [185,220,195,280,350,150,120,320,280,350,480,520,85,110,145]
    now = datetime.now()
    for i in range(15):
        fecha  = now - timedelta(days=random.randint(0,13), hours=random.randint(0,8))
        folio  = f"V-{1001+i}"
        cli_id = random.randint(1,5)
        metodo = random.choice(['Efectivo','Tarjeta','Transferencia'])
        fv = fecha if USE_PG else fecha.isoformat()
        if USE_PG:
            cur.execute("INSERT INTO ventas(folio,fecha,cliente_id,subtotal,impuesto,total,metodo_pago,estado)"
                        " VALUES(%s,%s,%s,0,0,0,%s,'Completada') RETURNING id",(folio,fv,cli_id,metodo))
            vid = cur.fetchone()['id']
        else:
            cur.execute("INSERT INTO ventas(folio,fecha,cliente_id,subtotal,impuesto,total,metodo_pago,estado)"
                        " VALUES(?,?,?,0,0,0,?,'Completada')",(folio,fv,cli_id,metodo))
            vid = cur.lastrowid
        sub = 0
        for _ in range(random.randint(1,4)):
            pid=random.randint(1,15); qty=random.randint(1,6)
            p=precios[pid-1]; line=p*qty; sub+=line
            cur.execute(("INSERT INTO venta_items(venta_id,producto_id,cantidad,precio_unitario,subtotal)"
                         " VALUES(%s,%s,%s,%s,%s)" if USE_PG else
                         "INSERT INTO venta_items(venta_id,producto_id,cantidad,precio_unitario,subtotal)"
                         " VALUES(?,?,?,?,?)"),(vid,pid,qty,p,line))
        imp=round(sub*0.16,2)
        cur.execute(("UPDATE ventas SET subtotal=%s,impuesto=%s,total=%s WHERE id=%s" if USE_PG else
                     "UPDATE ventas SET subtotal=?,impuesto=?,total=? WHERE id=?"),(sub,imp,sub+imp,vid))


# ── Public API ────────────────────────────────────────────────────────────────

def q(sql, params=()):
    with _ctx() as conn:
        cur = conn.cursor()
        cur.execute(_adapt(sql), params)
        return [dict(r) for r in cur.fetchall()]


def run(sql, params=()):
    adapted = _adapt(sql)
    with _ctx() as conn:
        cur = conn.cursor()
        if USE_PG and adapted.strip().upper().startswith("INSERT"):
            cur.execute(adapted + " RETURNING id", params)
            row = cur.fetchone()
            return row['id'] if row else None
        cur.execute(adapted, params)
        return getattr(cur, 'lastrowid', None)


def run_many(sql, rows):
    with _ctx() as conn:
        conn.cursor().executemany(_adapt(sql), rows)


def raw_query(sql):
    """Returns (columns, rows, error)"""
    try:
        with _ctx() as conn:
            cur = conn.cursor()
            cur.execute(_adapt(sql))
            if cur.description:
                cols = [d[0] for d in cur.description]
                rows = [list(r.values()) if isinstance(r,dict) else list(r) for r in cur.fetchall()]
                return cols, rows, None
            # DML affected rows
            affected = getattr(cur, 'rowcount', 0)
            return [], [], None  # success, no rows
    except Exception as e:
        return [], [], str(e)


def raw_exec(sql):
    """Execute DML (INSERT/UPDATE/DELETE) — returns (affected, error)"""
    try:
        with _ctx() as conn:
            cur = conn.cursor()
            cur.execute(_adapt(sql))
            return getattr(cur, 'rowcount', 0), None
    except Exception as e:
        return 0, str(e)


def get_config(k, default=""):
    r = q("SELECT valor FROM config WHERE clave=?", (k,))
    return r[0]['valor'] if r else default


def set_config(k, v):
    if USE_PG:
        with _ctx() as conn:
            conn.cursor().execute(
                "INSERT INTO config(clave,valor) VALUES(%s,%s) ON CONFLICT(clave) DO UPDATE SET valor=EXCLUDED.valor",
                (k,v))
    else:
        run("INSERT OR REPLACE INTO config(clave,valor) VALUES(?,?)",(k,v))


def next_folio():
    r = q("SELECT folio FROM ventas ORDER BY id DESC LIMIT 1")
    if not r: return "V-1001"
    try: return f"V-{int(r[0]['folio'].split('-')[1])+1}"
    except: return "V-1001"


def engine_info():
    return {"motor":"PostgreSQL" if USE_PG else "SQLite",
            "url": DATABASE_URL if USE_PG else _SQLITE,
            "icono":"🐘" if USE_PG else "🗃️",
            "prod": USE_PG}
