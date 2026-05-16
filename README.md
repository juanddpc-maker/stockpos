# 📦 StockPOS — Inventario & Punto de Venta

Sistema completo de inventario y punto de venta con agente IA (GROQ).

## 🚀 Inicio Rápido (Local / Dev)

```bash
# 1. Clona o descomprime el proyecto
cd stockpos

# 2. Instala dependencias
pip install -r requirements.txt

# 3. Corre la app
streamlit run app.py
```

La base de datos SQLite se crea automáticamente en `data/stockpos.db` con datos de muestra.

---

## 🛢️ Base de Datos

### Modo Local (SQLite)
- **No requiere configuración.** Se usa automáticamente cuando `DATABASE_URL` no está definida.
- Archivo: `data/stockpos.db`

### Modo Producción (PostgreSQL)
1. Crea tu base de datos en Railway / Render / Heroku / Supabase
2. Copia `.env.example` como `.env`
3. Define `DATABASE_URL=postgresql://...`

```env
DATABASE_URL=postgresql://usuario:contraseña@host:5432/stockpos
```

La app detecta el motor automáticamente y crea las tablas en el primer arranque.

---

## 🤖 Agente IA (GROQ)

1. Crea cuenta gratuita en [console.groq.com](https://console.groq.com)
2. Genera una API Key
3. Ingresa la key en **⚙️ Configuración → GROQ / IA** dentro de la app

Modelos disponibles: Llama 3.3 70B, Llama 3.1 8B, Mixtral 8x7B, Gemma 2 9B

---

## 📁 Estructura

```
stockpos/
├── app.py                    # Entrada principal, sidebar, routing
├── database.py               # Capa de datos (SQLite + PostgreSQL)
├── requirements.txt
├── .env.example              # Plantilla de variables de entorno
├── .gitignore
├── assets/
│   └── logo.png              # Logo de la empresa (se sube desde la app)
├── data/
│   └── stockpos.db           # SQLite local (auto-generado)
└── pages/
    ├── dashboard_ventas.py
    ├── dashboard_inventario.py
    ├── punto_de_venta.py
    ├── productos.py
    ├── inventario.py
    ├── ventas.py
    ├── clientes.py
    ├── categorias.py
    ├── agente_ia.py
    ├── gestor_bd.py
    └── configuracion.py
```

## 🗄️ Esquema de Base de Datos

| Tabla | Descripción |
|---|---|
| `categorias` | Categorías de productos |
| `productos` | Catálogo (nombre, precio, categoría, emoji) |
| `inventario` | Stock por producto y localidad (con min/max) |
| `clientes` | RFC, teléfono, email, dirección |
| `ventas` | Folio, fecha, cliente, totales, método de pago |
| `venta_items` | Líneas de cada venta (producto, cantidad, precio) |
| `config` | Configuración general (nombre empresa, IVA, etc.) |

## 🚢 Deploy en Render (ejemplo)

1. Sube el código a GitHub
2. Crea un nuevo **Web Service** en [render.com](https://render.com)
3. Build command: `pip install -r requirements.txt`
4. Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
5. Agrega la variable `DATABASE_URL` con tu PostgreSQL de Render
