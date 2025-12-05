# app.py
import os, io, json, base64, math, sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
from functools import wraps
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.utils import ImageReader
from PIL import Image
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Database path
DATABASE = "inair_reportes.db"


# Import database functions
from database import (
    init_db, get_all_users, get_user_by_username, create_user, delete_user,
    get_all_reports, get_report_by_folio, save_report, search_reports,
    get_next_folio, get_dashboard_stats,
    get_all_clients, get_client_by_id, create_client, update_client, delete_client,
    add_client_equipment, get_client_equipment, get_equipment_by_id,
    update_client_equipment, delete_client_equipment,
    get_equipment_types_by_client, get_models_by_client_and_type,
    # Draft report functions
    save_draft_report, get_draft_by_folio, get_all_drafts, delete_draft,
    mark_draft_as_sent, update_draft_pdf
)

# ===== Helpers para unidades y tipos de equipo =====
def _is_oilfree(tipo_equipo: str) -> bool:
    """True si el tipo de equipo contiene 'libre de aceite'."""
    return "libre de aceite" in (tipo_equipo or "").lower()

def _is_secador(tipo_equipo: str) -> bool:
    """True si el tipo de equipo es un secador."""
    return "secador" in (tipo_equipo or "").lower()

def _join_val_unit(val: str, unit: str) -> str:
    """
    Une valor y unidad como 'valor (unidad)'. Usa N/A si faltan.
    Si tu HTML no envía unidades, esto seguirá mostrando algo válido.
    """
    v = (val or "").strip() or "N/A"
    u = (unit or "").strip() or "N/A"
    return f"{v} ({u})"

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_ROOT, "data")
UPLOAD_DIR = os.path.join(APP_ROOT, "static", "uploads")
FIRMAS_DIR = os.path.join(APP_ROOT, "static", "firmas")
GENERADOS_DIR = os.path.join(APP_ROOT, "static")

app = Flask(__name__)
app.secret_key = "inair_secret_key_change_me"

# Initialize database
init_db()

# ------------------ Role-based access control ------------------
def require_role(role):
    """Decorator to require specific role for route access"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            if session.get('role') != role:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ------------------ helpers de estado ------------------
def _load_json(path, default):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def cargar_usuarios():
    return _load_json(os.path.join(DATA_DIR, "usuarios.json"), {
        "fernando": {"password": "fernando123", "nombre": "Fernando", "prefijo":"F"},
        "cesar": {"password": "cesar123", "nombre": "César", "prefijo":"C"},
        "hiorvard": {"password": "hiorvard123", "nombre": "Hiorvard", "prefijo":"H"},
    })

def cargar_folios():
    return _load_json(os.path.join(DATA_DIR, "folios.json"), {})

def guardar_folios(data):
    with open(os.path.join(DATA_DIR, "folios.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generar_siguiente_folio(prefijo):
    folios = cargar_folios()
    folios[prefijo] = folios.get(prefijo, 0) + 1
    guardar_folios(folios)
    return f"{prefijo}-{folios[prefijo]:04d}"

# ------------------ catálogos ------------------
LISTA_EQUIPOS = [
    "Compresor tornillo lubricado capacidad variable",
    "Compresor tornillo lubricado velocidad variable",
    "Compresor tornillo libre de aceite velocidad fija",
    "Compresor tornillo libre de aceite velocidad variable",
    "Compresor booster pistón 1 etapa",
    "Compresor booster pistón 2 etapas",
    "Compresor booster pistón 3 etapa",
    "Compresor booster pistón 4 etapa",
    "Compresor booster pistón 5 etapa",
    "Compresor tornillo lubricado velocidad fija",
    "Compresor pistón 3 etapas",
    "Compresor tornillo lubricado velocidad fija x bandas",
    "Compresor tornillo lubricado velocidad fija 2 etapas",
    "Compresor tornillo lubricado velocidad variable 2 etapas",
    "Compresor pistón 2 etapas",
    "Compresor reciprocante",
    "Secador refrigerativo cíclico",
    "Secador refrigerativo no cíclico",
    "Secador regenerativo",
]

ACTIVIDADES_SENTENCE = [
    "Cambio de filtro de aire","Cambio de filtro de aceite","Cambio de elemento separador",
    "Cambio de filtro panel control","Recuperar nivel de aceite","Cambio de aceite",
    "Cambio de mangueras","Cambio válvula de desfogue","Cambio válvula check descarga",
    "Cambio kit válvula mpcv","Cambio kit, válvula admisión","Cambio válvula paro de aceite",
    "Cambio kit, val. termocontrol","Cambio de bandas","Reapretar conexiones mecánicas",
    "Reapretar conexiones eléctricas","Limpieza línea de barrido","Limpieza trampa de condensados",
    "Limpieza a enfriadores aire/aceite","Revisar funcionamiento de válvulas",
    "Limpieza a platinos de contactores","Lubricación rodamiento de motor",
    "Servicio a motor eléctrico","Limpieza general del equipo",
    "Toma de muestra de aceite para análisis",
]

# --- Lecturas de compresor (web + pdf) ---
DG_LABELS = [
    "Horas totales","Horas de carga","Presión objetivo/descarga","Presión de carga",
    "Presión descarga del paquete","Temperatura ambiente","Temp. descarga del paquete",
    "Temp. descarga del aire-end","Temp. inyección de refrigerante","Caída de presión separador"
]
OF_LABELS = [
    "Temp. entrada aire 1ra etapa","Temp. descarga aire 1ra etapa","Presión descarga 1ra etapa",
    "Temp. entrada 2da etapa","Temp. descarga 2da etapa","Presión descarga 2da etapa",
    "Temperatura del aceite","Presión de aceite","Vacío de entrada","(otro)"
]

# --- Lecturas de SECADOR (solo PDF; en el HTML ya tienes estos campos) ---
SEC_LABELS = [
    "Temperatura de aire de entrada",
    "Temperatura de aire de salida",
    "Temperatura del calentador",
    "Temperatura ambiente",
    "Punto de rocío",
    "Tiempo de ciclo",
    "Horas totales",
    "Condiciones de prefiltro",
    "Condiciones de pos filtro",
]

# --- Datos eléctricos estándar (compresores) ---
E3 = [
    ("Voltaje comp. en carga","v_carga"),
    ("Voltaje comp. en descarga","v_descarga"),
    ("Voltaje a tierra","v_tierra"),
    ("Corriente comp. en carga","i_carga"),
    ("Corriente comp. en descarga","i_descarga"),
    ("Corriente total del paquete","i_total"),
]
E1 = [
    ("Corriente de placa","i_placa"),
    ("Voltaje del bus DC","v_busdc"),
    ("RPM del motor (VFD)","rpm_vfd"),
    ("Temp. IGBT U=","t_igbt_u"),("Temp. IGBT V=","t_igbt_v"),("Temp. IGBT W=","t_igbt_w"),
    ("Temp. rectificador","t_rect"),
]

# --- Datos eléctricos especiales para SECADOR (solo 2 filas) ---
SEC_E3 = [
    ("Corriente comp. en carga", "i_carga"),
    ("Voltaje comp. en carga", "v_carga"),  # esta usa L1-2 / L2-3 / L3-1
]
SEC_E1 = []  # sin filas individuales para secador

# ------------------ rutas ------------------
@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    
    # Redirect based on role
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    else:
        return redirect(url_for("formulario"))

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username","").strip().lower()
        pw = request.form.get("password","").strip()
        
        # Get user from database
        user = get_user_by_username(username)
        
        if user and user["password"] == pw:
            session["user"] = username
            session["user_nombre"] = user["nombre"]
            session["prefijo"] = user["prefijo"]
            session["role"] = user["role"]
            
            # Redirect based on role
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("formulario"))
        
        error = "Usuario o contraseña incorrectos"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/formulario")
def formulario():
    if "user" not in session:
        return redirect(url_for("login"))

    # ⬇️ Si viene ?folio=... en la URL, úsalo (no incrementa el contador)
    folio_q = request.args.get("folio", "").strip()
    if folio_q:
        session["folio_actual"] = folio_q

    # Si no hay folio en sesión, genera uno nuevo
    if "folio_actual" not in session:
        session["folio_actual"] = get_next_folio(session["prefijo"])

    folio = session["folio_actual"]
    return render_template(
        "formulario.html",
        folio=folio,
        lista_equipos=LISTA_EQUIPOS,
        dg_labels=DG_LABELS, of_labels=OF_LABELS, e3=E3, e1=E1
    )

@app.route("/nuevo_folio", methods=["POST"])
def nuevo_folio():
    if "user" not in session:
        return redirect(url_for("login"))
    session["folio_actual"] = get_next_folio(session["prefijo"])
    return redirect(url_for("formulario"))


# ------------------ util texto/medidas ------------------
def _text_or_na(v):
    v = (v or "").strip()
    return v if v else "N/A"

def _join_val_unit(value, unit):
    """Join a value with its unit. Returns 'N/A' if value is empty."""
    value = (value or "").strip()
    unit = (unit or "").strip()
    if not value or value == "N/A":
        return "N/A"
    if unit:
        return f"{value} {unit}"
    return value


def _wrap_text_force(text, max_w, font="Helvetica", size=9):
    if not text: return [""] if text == "" else []
    words = text.split(" ")
    lines, line = [], ""
    def w(s): return stringWidth(s, font, size)
    for word in words:
        cand = (line + " " + word).strip()
        if w(cand) <= max_w:
            line = cand
        else:
            if line: lines.append(line); line = ""
            buf = ""
            for ch in word:
                if w(buf + ch) <= max_w:
                    buf += ch
                else:
                    lines.append(buf); buf = ch
            line = buf
    if line: lines.append(line)
    return lines

# ------------------ dibujo piezas comunes ------------------
def _draw_header_and_footer(c, folio, fecha, tecnico, localidad):
    try:
        logo_path = os.path.join(APP_ROOT, "static", "img", "logo_inair.png")
        if os.path.exists(logo_path):
            c.drawImage(ImageReader(logo_path), 1.5*cm, 27.6*cm, width=4.2*cm, height=1.6*cm,
                        preserveAspectRatio=True, anchor='sw')
    except Exception:
        pass
    c.setFont("Helvetica-Bold", 14); c.drawString(7.5*cm, 28.1*cm, "REPORTE TÉCNICO")
    c.setFont("Helvetica", 9)
    c.drawRightString(16.5*cm, 28.2*cm, "Folio:")
    c.setFillColorRGB(0.82,0,0); c.setFont("Helvetica-Bold", 10)
    c.drawRightString(19.0*cm, 28.2*cm, folio)
    c.setFillColorRGB(0,0,0); c.setFont("Helvetica", 9)
    c.drawRightString(19.0*cm, 27.7*cm, f"Fecha: {fecha}")
    c.drawRightString(19.0*cm, 27.2*cm, f"Técnico: {tecnico}")
    c.drawString(1.5*cm, 27.2*cm, f"Localidad: {localidad}")
    c.setStrokeColorRGB(0.82,0.82,0.82); c.line(1.5*cm, 26.9*cm, 19.5*cm, 26.9*cm)
    c.setStrokeColorRGB(0,0,0)

    # Pie con fondo suave
    base_y = 1.35*cm
    rect_h = 1.9*cm
    c.setFillColorRGB(0.95, 0.96, 0.99)
    c.roundRect(1.5*cm, base_y-0.2*cm, 18.0*cm, rect_h, 6, fill=1, stroke=0)
    c.setStrokeColorRGB(0.75,0.75,0.8); c.roundRect(1.5*cm, base_y-0.2*cm, 18.0*cm, rect_h, 6, fill=0, stroke=1)
    c.setFillColorRGB(0,0,0)

    col_w = 8.8*cm; gap = 0.4*cm
    x1 = 1.7*cm; x2 = 1.7*cm + col_w + gap
    def draw_col(x, title, lines):
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x, base_y + rect_h - 0.55*cm, title)
        c.setFont("Helvetica", 7.6)
        maxw = col_w - 0.2*cm
        yy = base_y + rect_h - 1.0*cm
        for ln in lines:
            for piece in _wrap_text_force(ln, maxw, "Helvetica", 7.6):
                c.drawString(x, yy, piece); yy -= 0.34*cm
    draw_col(x1, "INGENIERIA EN AIRE SA DE CV        RFC: IAI1605258G6",
             ["Avenida Alfonso Vidal y Planas #445, Interior S/N, Colonia Nueva Tijuana,",
              "Tijuana, Baja California, México, CP: 22435, Lada 664 Tel(s) 250-0022"])
    draw_col(x2, "INGENIERIA EN AIRE SA DE CV        RFC: IAI1605258G6",
             ["Avenida del Carmen #3863, Fracc. Residencias, Mexicali, Baja California, México,",
              "CP: 21280, Lada 686 Tel(s) 962-9932"])

def _draw_section(c, title, y, box_h):
    c.setStrokeColorRGB(0.7,0.7,0.7); c.setLineWidth(1)
    c.roundRect(1.5*cm, y-box_h, 18.0*cm, box_h, 6, stroke=1, fill=0)
    c.setFillColorRGB(0.95,0.95,0.98); c.rect(1.5*cm, y-18, 18.0*cm, 18, fill=1, stroke=0)
    c.setFillColorRGB(0,0,0); c.setFont("Helvetica-Bold", 10); c.drawString(1.7*cm, y-13, title)
    return y-22

def _ensure_space(c, y, need, folio, fecha, tecnico, localidad):
    _, height = A4
    if y - need < 2.3*cm:
        c.showPage()
        _draw_header_and_footer(c, folio, fecha, tecnico, localidad)
        return height - 3.2*cm
    return y

def _row_box_multi(c, y, total_w, cols, line_h, inner_x):
    widths = [total_w * col["ratio"] for col in cols]
    for w, col in zip(widths, cols):
        lab = col["label"] + ": "
        lab_w = stringWidth(lab, "Helvetica-Bold", 9)
        avail = max(10, w - 8 - lab_w)
        parts = _wrap_text_force(col["value"], avail, "Helvetica", 9)
        col["_parts"], col["_lab_w"] = parts, lab_w
    max_lines = max(len(col["_parts"]) for col in cols)
    rect_h = max_lines*line_h + 0.40*cm
    c.setStrokeColorRGB(0.85,0.85,0.85)
    c.rect(inner_x-0.3*cm, y-rect_h+0.2*cm, total_w, rect_h, fill=0, stroke=1)
    c.setStrokeColorRGB(0,0,0)
    x = inner_x
    for w, col in zip(widths, cols):
        c.setFont("Helvetica-Bold", 9); c.drawString(x, y-0.3*cm, col["label"] + ": ")
        c.setFont("Helvetica", 9)
        yy = y-0.3*cm
        for i, ln in enumerate(col["_parts"]):
            if i == 0: c.drawString(x + col["_lab_w"], yy, ln)
            else:      c.drawString(x, yy - i*line_h, ln)
        x += w
    return y - rect_h

def _save_signature_png(data_url, filename):
    if not data_url or not data_url.startswith("data:image"): return None
    header, b64 = data_url.split(",", 1)
    raw = base64.b64decode(b64)
    os.makedirs(FIRMAS_DIR, exist_ok=True)
    path = os.path.join(FIRMAS_DIR, filename)
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        bg = Image.new("RGBA", img.size, (255,255,255,255))
        bg.alpha_composite(img)
        bg.convert("RGB").save(path, format="PNG")
    except Exception:
        with open(path, "wb") as f: f.write(raw)
    return path

# ------------------ generación PDF ------------------
@app.route("/generar_pdf", methods=["POST"])
def generar_pdf():
    if "user" not in session:
        return redirect(url_for("login"))

    width, height = A4
    folio = request.form.get("folio") or session.get("folio_actual")
    fecha = _text_or_na(request.form.get("fecha"))
    tecnico = _text_or_na(request.form.get("tecnico"))
    localidad = _text_or_na(request.form.get("localidad"))

    tipo_servicio = _text_or_na(request.form.get("tipo_servicio"))
    desc_servicio = _text_or_na(request.form.get("descripcion_servicio"))

    cliente = _text_or_na(request.form.get("cliente"))
    contacto = _text_or_na(request.form.get("contacto"))
    direccion = _text_or_na(request.form.get("direccion"))
    telefono = _text_or_na(request.form.get("telefono"))
    email = _text_or_na(request.form.get("email"))

    tipo_equipo = _text_or_na(request.form.get("tipo_equipo"))
    modelo = _text_or_na(request.form.get("modelo"))
    serie = _text_or_na(request.form.get("serie"))
    marca_sel = request.form.get("marca") or ""
    # Acepta "Otros" en cualquier capitalización
    if marca_sel.strip().lower() == "otros":
        marca = _text_or_na(request.form.get("otra_marca"))
    else:
        marca = _text_or_na(marca_sel)
    if marca and marca != "N/A":
        marca = marca.title()

    # Potencia: HP normal / CFM para secador
    potencia_num = (request.form.get("potencia", "") or "").strip()
    if potencia_num:
        if _is_secador(tipo_equipo):
            potencia = f"{potencia_num} CFM"
        else:
            potencia = f"{potencia_num} HP"
    else:
        potencia = "N/A"

    observaciones = _text_or_na(request.form.get("observaciones"))

    # fotos
    fotos = []
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    for i in range(1,5):
        ffile = request.files.get(f"foto{i}")
        desc = _text_or_na(request.form.get(f"foto{i}_desc"))
        path = os.path.join(UPLOAD_DIR, f"{folio}_foto{i}.png")
        
        if ffile and ffile.filename:
            # New file uploaded
            ffile.save(path)
            fotos.append((path, desc))
        else:
            # Check for auto-saved base64 data (foto#_data)
            foto_data = request.form.get(f"foto{i}_data")
            if not foto_data:
                # Fallback: check old field name
                foto_data = request.form.get(f"foto{i}_existing")
            
            if foto_data:
                try:
                    # Remove header if present (data:image/png;base64,...)
                    if "," in foto_data:
                        foto_data = foto_data.split(",")[1]
                    
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(foto_data))
                    fotos.append((path, desc))
                except Exception as e:
                    print(f"Error decoding existing photo {i}: {e}")

    # firmas
    firma_tecnico_nombre = _text_or_na(request.form.get("firma_tecnico_nombre"))
    firma_cliente_nombre = _text_or_na(request.form.get("firma_cliente_nombre"))
    firma_tecnico_path = _save_signature_png(request.form.get("firma_tecnico_data"), f"{folio}_firma_tecnico.png")
    firma_cliente_path = _save_signature_png(request.form.get("firma_cliente_data"), f"{folio}_firma_cliente.png")

    # actividades (para compresor estándar; en secador tú ya estás imprimiendo otras actividades)
    analisis_ruido_marcado = request.form.get("act_analisis_ruido") == "1" or bool(request.form.get("act_analisis_ruido"))
    actividades = []
    for idx, nombre in enumerate(ACTIVIDADES_SENTENCE, start=1):
        # Check if checkbox is marked: value should be "1" or "on"
        val = request.form.get(f"act_{idx}")
        marcado = val == "1" or val == "on"
        actividades.append((nombre, "Realizado" if marcado else "N/A"))
    actividades.append(("Análisis de ruidos en rodamientos (R30)", "Realizado" if analisis_ruido_marcado else "N/A"))
    act_otras = _text_or_na(request.form.get("act_otras"))

    # ruido R30/SPM
    ruido_tipo = _text_or_na(request.form.get("ruido_tipo")) if analisis_ruido_marcado else "N/A"
    ruido_resultado = _text_or_na(request.form.get("ruido_resultado")) if analisis_ruido_marcado else "N/A"
    ruido_obs = _text_or_na(request.form.get("ruido_observaciones")) if analisis_ruido_marcado else "N/A"

    spm_vals = {}
    if analisis_ruido_marcado and ruido_tipo == "SPM":
        rows = [("carga_dbm","CARGA dBm"),("carga_dbc","CARGA dBc"),("carga_dbi","CARGA dBi"),
                ("descarga_dbm","DESCARGA dbm"),("descarga_dbc","DESCARGA dBc"),("descarga_dbi","DESCARGA dBi")]
        cols = ["mbrg","bg","lpmi_mri","lpm2_mr2","hpm1","hpm2","hpf1","hpf2","lpf1","lpf2"]
        for rk,_ in rows:
            for ck in cols:
                spm_vals[f"{rk}_{ck}"] = _text_or_na(request.form.get(f"{rk}_{ck}"))

    # Lecturas (compresor; para secador usaremos otros campos)
    dg_vals = []
    for i in range(len(DG_LABELS)):
        val = request.form.get(f"dg_{i+1}", "")
        unit = request.form.get(f"dg_{i+1}_unit", "")
        dg_vals.append(_join_val_unit(val, unit))

    # Oil-free
    of_vals = []
    for i in range(len(OF_LABELS)):
        val = request.form.get(f"of_{i+1}", "")
        unit = request.form.get(f"of_{i+1}_unit", "")
        of_vals.append(_join_val_unit(val, unit))

    # --- Datos eléctricos: E3 (trifásicos) y E1 (individuales) ---
    e3_vals = {}
    for _, key in E3:
        fases = ("l12", "l23", "l31") if key in ("v_carga", "v_descarga") else ("l1", "l2", "l3")
        for ph in fases:
            e3_vals[f"{key}_{ph}"] = _text_or_na(request.form.get(f"{key}_{ph}"))

    e1_vals = { key: _text_or_na(request.form.get(key)) for _, key in E1 }

    # Bandera: ¿estamos en Preventivo + Secador?
    ts = (tipo_servicio or "").lower()
    es_secador_preventivo = (_is_secador(tipo_equipo) and ts == "preventivo")

    # === PDF ===
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _draw_header_and_footer(c, folio, fecha, tecnico, localidad)
    y = height - 3.2*cm
    inner_x = 1.8*cm
    inner_w = 17.6*cm
    line_h = 0.52*cm

    # DATOS DEL CLIENTE
    need = 18 + (1*line_h) + 0.8*cm
    y = _ensure_space(c, y, need, folio, fecha, tecnico, localidad)
    yc = _draw_section(c, "Datos del cliente", y, need + (2*line_h))
    yc = _row_box_multi(c, yc, inner_w, [{"label":"Cliente","value":cliente,"ratio":1.0}], line_h, inner_x)
    cols = [
        {"label":"Contacto","value":contacto,"ratio":0.45},
        {"label":"Teléfono","value":telefono,"ratio":0.22},
        {"label":"Email","value":email,"ratio":0.33},
    ]
    yc = _row_box_multi(c, yc, inner_w, cols, line_h, inner_x)
    yc = _row_box_multi(c, yc, inner_w, [{"label":"Dirección","value":direccion,"ratio":1.0}], line_h, inner_x)
    y = yc - 0.2*cm

    # SERVICIO (si el tipo es Bitácora, aseguramos la descripción)
    if ts in ("bitácora", "bitacora"):
        desc_servicio = "Bitácora"

    cols = [{"label":"Tipo","value":tipo_servicio,"ratio":0.30},{"label":"Descripción","value":desc_servicio,"ratio":0.70}]
    max_lines = 0
    for col in cols:
        w = inner_w*col["ratio"]; lab_w = stringWidth(col["label"]+": ", "Helvetica-Bold", 9)
        avail = max(10, w - lab_w - 8)
        parts = _wrap_text_force(col["value"], avail, "Helvetica", 9)
        max_lines = max(max_lines, len(parts))
    need_serv = 18 + max_lines*line_h + 0.8*cm
    y = _ensure_space(c, y, need_serv, folio, fecha, tecnico, localidad)
    ys = _draw_section(c, "Servicio", y, need_serv)
    ys = _row_box_multi(c, ys, inner_w, cols, line_h, inner_x)
    y = ys - 0.2*cm

    # EQUIPO
    need_eq = 18 + 1*line_h + 0.8*cm
    y = _ensure_space(c, y, need_eq + 2*line_h, folio, fecha, tecnico, localidad)
    ye = _draw_section(c, "Datos del equipo", y, need_eq + 2*line_h)
    ye = _row_box_multi(c, ye, inner_w, [{"label":"Tipo","value":tipo_equipo,"ratio":1.0}], line_h, inner_x)
    cols = [
        {"label":"Modelo","value":modelo,"ratio":0.25},
        {"label":"Serie","value":serie,"ratio":0.25},
        {"label":"Marca","value":marca,"ratio":0.25},
        {"label":"Potencia","value":potencia,"ratio":0.25},
    ]
    ye = _row_box_multi(c, ye, inner_w, cols, line_h, inner_x)
    y = ye - 0.2*cm

    # ===== Flujo por tipo de servicio =====
    if ts == "preventivo":
        # OJO: aquí sigues viendo la tabla de actividades estándar solo para compresores.
        # Para secadores tú ya tienes el bloque de actividades específico en el formulario
        # y podríamos hacer una tabla aparte si lo necesitas después.
        
        # Filter out activities where estado is "N/A" (not performed)
        filtered_actividades = [(act, est) for act, est in actividades if est and est.strip() and est.strip() != "N/A"]
        
        if not filtered_actividades:
            # Skip this section if no activities were performed
            pass
        else:
            rows = filtered_actividades[:]
            n = len(rows); left_rows = math.ceil(n/2); right_rows = n - left_rows
            row_h = 0.52*cm; gutter = 0.6*cm; col_w_act = 5.9*cm; col_w_estado = 2.0*cm
            need_h = 18 + (1 + max(left_rows, right_rows))*row_h + 1.2*cm
            otras_text = "" if act_otras == "N/A" else act_otras
            if otras_text:
                lab = "OTRAS ACTIVIDADES: "; labw = stringWidth(lab, "Helvetica-Bold", 9)
                otras_lines = _wrap_text_force(otras_text, inner_w-0.6*cm-labw-6, "Helvetica", 9)
                need_h += (len(otras_lines)*line_h + 0.8*cm + 16)
            y = _ensure_space(c, y, need_h, folio, fecha, tecnico, localidad)
            ya = _draw_section(c, "Actividades de mantenimiento preventivo", y, need_h)
            left_x = inner_x; right_x = left_x + (col_w_act + col_w_estado) + gutter
            c.setFont("Helvetica-Bold", 8.4)
            for base_x in (left_x, right_x):
                c.rect(base_x, ya-row_h, col_w_act, row_h, fill=0, stroke=1)
                c.rect(base_x+col_w_act, ya-row_h, col_w_estado, row_h, fill=0, stroke=1)
                c.drawString(base_x+3, ya-row_h+3, "Actividad")
                c.drawString(base_x+col_w_act+3, ya-row_h+3, "Estado")
            c.setFont("Helvetica", 7.8)
            yline_l = ya - row_h
            for i in range(left_rows):
                # Check space before each row (except first)
                if i > 0:
                    temp_y = yline_l
                    temp_y = _ensure_space(c, temp_y, row_h + 0.1*cm, folio, fecha, tecnico, localidad)
                    if temp_y > yline_l:
                        yline_l = temp_y
                
                act, est = rows[i]
                c.rect(left_x, yline_l-row_h, col_w_act, row_h, fill=0, stroke=1)
                c.rect(left_x+col_w_act, yline_l-row_h, col_w_estado, row_h, fill=0, stroke=1)
                maxw = col_w_act - 6; txt = act
                while stringWidth(txt, "Helvetica", 7.8) > maxw and len(txt) > 3:
                    txt = txt[:-4] + "…"
                c.drawString(left_x+3, yline_l-row_h+3, txt)
                c.drawString(left_x+col_w_act+3, yline_l-row_h+3, est)
                yline_l -= row_h
            yline_r = ya - row_h
            for j in range(right_rows):
                # Check space before each row (except first)
                if j > 0:
                    temp_y = yline_r
                    temp_y = _ensure_space(c, temp_y, row_h + 0.1*cm, folio, fecha, tecnico, localidad)
                    if temp_y > yline_r:
                        yline_r = temp_y
                
                act, est = rows[left_rows + j]
                c.rect(right_x, yline_r-row_h, col_w_act, row_h, fill=0, stroke=1)
                c.rect(right_x+col_w_act, yline_r-row_h, col_w_estado, row_h, fill=0, stroke=1)
                maxw = col_w_act - 6; txt = act
                while stringWidth(txt, "Helvetica", 7.8) > maxw and len(txt) > 3:
                    txt = txt[:-4] + "…"
                c.drawString(right_x+3, yline_r-row_h+3, txt)
                c.drawString(right_x+col_w_act+3, yline_r-row_h+3, est)
                yline_r -= row_h
            y_after = min(yline_l, yline_r) - 0.3*cm
            if otras_text:
                c.setFont("Helvetica-Bold", 9); lab = "OTRAS ACTIVIDADES: "
                labw = stringWidth(lab, "Helvetica-Bold", 9)
                parts = _wrap_text_force(otras_text, inner_w-0.6*cm-labw-6, "Helvetica", 9)
                rect_h = len(parts)*line_h + 0.8*cm
                c.setStrokeColorRGB(0.85,0.85,0.85)
                c.rect(inner_x-0.3*cm, y_after-rect_h+0.2*cm, inner_w, rect_h, fill=0, stroke=1)
                c.setStrokeColorRGB(0,0,0)
                yy = y_after - 0.3*cm; c.drawString(inner_x, yy, lab)
                c.setFont("Helvetica", 9)
                for i, ln in enumerate(parts):
                    c.drawString(inner_x + labw + 6, yy - i*line_h, ln)
                y = y_after - rect_h - 0.2*cm
            else:
                y = y_after

        # análisis de ruido
        if analisis_ruido_marcado:
            if ruido_tipo == "SPM":
                need_spm = 7.6*cm
                y = _ensure_space(c, y, need_spm, folio, fecha, tecnico, localidad)
                yr = _draw_section(c, "Análisis de ruido", y, need_spm)
                headers = ["", "MBRG","BG","LPMI-MRI","LPM2-MR2","HPM1","HPM2","HPF1","HPF2","LPF1","LPF2"]
                row_defs = [("CARGA dBm","carga_dbm"),("CARGA dBc","carga_dbc"),("CARGA dBi","carga_dbi"),
                            ("DESCARGA dbm","descarga_dbm"),("DESCARGA dBc","descarga_dbc"),("DESCARGA dBi","descarga_dbi")]
                
                # Filter out rows where all values are N/A or empty
                cols = ["mbrg","bg","lpmi_mri","lpm2_mr2","hpm1","hpm2","hpf1","hpf2","lpf1","lpf2"]
                filtered_row_defs = []
                for lbl, key in row_defs:
                    row_vals = [spm_vals.get(f"{key}_{col}", "N/A") for col in cols]
                    # Keep row if at least one value is not N/A and not empty
                    if any(v and v.strip() and v.strip() != "N/A" for v in row_vals):
                        filtered_row_defs.append((lbl, key))
                
                if filtered_row_defs:
                    # Only draw table if there are rows with data
                    left_x2 = inner_x; colw0 = 3.4*cm; colw = 1.45*cm; rh = 0.68*cm
                    c.setFont("Helvetica-Bold", 8); c.setStrokeColorRGB(0.7,0.7,0.7)
                    c.rect(left_x2, yr-rh, colw0 + 10*colw, rh, fill=0, stroke=1)
                    c.drawString(left_x2+2, yr-rh+3, "ANÁLISIS DE RUIDO EN RODAMIENTOS (SPM)")
                    yline = yr - rh; x = left_x2 + colw0
                    c.setFont("Helvetica-Bold", 7.2)
                    for h in headers[1:]:
                        c.rect(x, yline-rh, colw, rh, fill=0, stroke=1); c.drawString(x+2, yline-rh+3, h); x += colw
                    yy2 = yline - rh; c.setFont("Helvetica", 7.0)
                    for idx, (lbl, key) in enumerate(filtered_row_defs):
                        # Check space before each row (except first, already checked for header)
                        if idx > 0:
                            temp_y = yy2
                            temp_y = _ensure_space(c, temp_y, rh + 0.1*cm, folio, fecha, tecnico, localidad)
                            if temp_y > yy2:
                                yy2 = temp_y
                        
                        c.rect(left_x2, yy2-rh, colw0, rh, fill=0, stroke=1)
                        c.setFont("Helvetica-Bold", 8); c.drawString(left_x2+2, yy2-rh+3, lbl)
                        x = left_x2 + colw0; c.setFont("Helvetica", 7.0)
                        for col in cols:
                            val = spm_vals.get(f"{key}_{col}", "N/A")
                            c.rect(x, yy2-rh, colw, rh, fill=0, stroke=1); c.drawString(x+2, yy2-rh+3, val[:8]); x += colw
                        yy2 -= rh
                    c.setStrokeColorRGB(0,0,0); y = yy2 - 0.3*cm
            else:
                need_r30 = 2.6*cm
                y = _ensure_space(c, y, need_r30, folio, fecha, tecnico, localidad)
                yr = _draw_section(c, "Análisis de ruido", y, need_r30)
                c.setFont("Helvetica-Bold", 9); c.drawString(inner_x, yr-0.7*cm, "Tipo:")
                c.setFont("Helvetica", 9); c.drawString(inner_x + stringWidth("Tipo:", "Helvetica-Bold", 9) + 6, yr-0.7*cm, ruido_tipo)
                c.setFont("Helvetica-Bold", 9); c.drawString(inner_x, yr-1.3*cm, "Resultado:")
                c.setFont("Helvetica", 9); c.drawString(inner_x + stringWidth("Resultado:", "Helvetica-Bold", 9) + 6, yr-1.3*cm, ruido_resultado)
                c.setFont("Helvetica-Bold", 9); c.drawString(inner_x, yr-1.9*cm, "Observaciones:")
                c.setFont("Helvetica", 9); c.drawString(inner_x + stringWidth("Observaciones:", "Helvetica-Bold", 9) + 6, yr-1.9*cm, ruido_obs)
                y = yr - 2.2*cm

    elif ts in ("correctivo", "diagnóstico", "diagnostico", "revisión", "revision"):
        blocks = [
            ("Diagnóstico del problema", _text_or_na(request.form.get("diag_problema"))),
            ("Causa raíz", _text_or_na(request.form.get("causa_raiz"))),
            ("Actividades realizadas", _text_or_na(request.form.get("actividades_realizadas"))),
            ("Refacciones utilizadas", _text_or_na(request.form.get("refacciones"))),
            ("Condiciones en que se encontró el equipo", _text_or_na(request.form.get("cond_encontro"))),
            ("Condiciones en que se entrega el equipo", _text_or_na(request.form.get("cond_entrega"))),
        ]
        for title, content in blocks:
            lines = _wrap_text_force(content, inner_w-0.6*cm)
            need = 18 + len(lines)*line_h + 0.8*cm
            y = _ensure_space(c, y, need, folio, fecha, tecnico, localidad)
            yb = _draw_section(c, title, y, need)
            c.setFont("Helvetica", 9)
            yy = yb - 0.5*cm
            for i, ln in enumerate(lines):
                c.drawString(inner_x, yy - i*line_h, ln)
            y = yy - len(lines)*line_h - 0.4*cm

    elif ts in ("bitácora", "bitacora"):
        # Bitácora: no pintamos preventivo/correctivo aquí
        pass

    # ===== LECTURAS DEL EQUIPO =====
    def draw_kv_table(title, labels, values):
        nonlocal y
        # Filter out rows where value is empty or "N/A"
        filtered_rows = [(lab, val) for lab, val in zip(labels, values) if val and val.strip() and val.strip() != "N/A"]
        
        if not filtered_rows:
            return  # Don't draw the table if no data
        
        row_h = 0.52*cm
        need = 18 + len(filtered_rows)*row_h + 0.7*cm
        y = _ensure_space(c, y, need, folio, fecha, tecnico, localidad)
        yt = _draw_section(c, title, y, need)
        c.setFont("Helvetica-Bold", 8.7)
        lab_w = 10.8*cm
        val_w = inner_w - lab_w
        yline = yt - 0.25*cm
        c.setFont("Helvetica", 8.7)
        for i,(lab,val) in enumerate(filtered_rows):
            # Check space before drawing each row (except first, already checked)
            if i > 0:
                # Check if we need to move to a new page
                temp_y = yline
                temp_y = _ensure_space(c, temp_y, row_h + 0.15*cm, folio, fecha, tecnico, localidad)
                # If new page was created, update yline to new page position
                if temp_y > yline:
                    yline = temp_y
            
            c.setStrokeColorRGB(0.85,0.85,0.85)
            c.rect(inner_x-0.3*cm, yline-row_h, lab_w+val_w, row_h, fill=0, stroke=1)
            c.setStrokeColorRGB(0,0,0)
            c.setFont("Helvetica", 8.6)
            c.drawString(inner_x, yline-row_h+3, lab)
            c.setFont("Helvetica-Bold", 8.6)
            c.drawString(inner_x + lab_w, yline-row_h+3, val)
            yline -= row_h
        y = yline - 0.2*cm

    if es_secador_preventivo:
        # Leemos campos específicos del SECADOR (los nombres deben coincidir con tu HTML)
        sec_vals = []
        for i in range(1, 7+1):  # 1..7 con unidad
            val = request.form.get(f"sec_{i}", "")
            unit = request.form.get(f"sec_{i}_unit", "")
            sec_vals.append(_join_val_unit(val, unit))
        sec_pref = _text_or_na(request.form.get("sec_prefiltro"))
        sec_pos = _text_or_na(request.form.get("sec_posfiltro"))
        sec_vals.append(sec_pref)
        sec_vals.append(sec_pos)

        draw_kv_table("Lecturas del equipo (Secador)", SEC_LABELS, sec_vals)
    else:
        draw_kv_table("Lecturas del equipo", DG_LABELS, dg_vals)
        if _is_oilfree(tipo_equipo):
            draw_kv_table("Compresor (oil free)", OF_LABELS, of_vals)

    # ===== DATOS ELÉCTRICOS =====
    def draw_electric(e3_vals_map, e1_vals_map, e3_rows, e1_rows):
        nonlocal y
        row_h = 0.52*cm
        
        # Filter e3_rows: keep only rows where at least one phase has data
        filtered_e3 = []
        for titulo, key in e3_rows:
            # Get units for each phase
            unit_l1 = request.form.get(f"{key}_unit", "").strip()
            unit_l2 = request.form.get(f"{key}_unit_l2", "").strip()
            unit_l3 = request.form.get(f"{key}_unit_l3", "").strip()
            
            fases = ("l12","l23","l31") if key in ("v_carga", "v_descarga") else ("l1","l2","l3")
            vals_raw = [e3_vals_map.get(f"{key}_{ph}", "N/A") for ph in fases]
            units = [unit_l1, unit_l2, unit_l3]
            
            # Check if at least one value is not empty and not "N/A"
            if any(v and v.strip() and v.strip() != "N/A" for v in vals_raw):
                # Join each value with its unit
                vals_with_units = [_join_val_unit(v, u) for v, u in zip(vals_raw, units)]
                filtered_e3.append((titulo, vals_with_units))
        
        # Filter e1_rows: keep only rows with data
        filtered_e1 = []
        for titulo, key in e1_rows:
            unit = request.form.get(f"{key}_unit", "").strip()
            val_raw = e1_vals_map.get(key, "N/A")
            if val_raw and val_raw.strip() and val_raw.strip() != "N/A":
                val_with_unit = _join_val_unit(val_raw, unit)
                filtered_e1.append((titulo, val_with_unit))
        
        if not filtered_e3 and not filtered_e1:
            return  # Don't draw section if no data
        
        need = 18 + (len(filtered_e3)+len(filtered_e1))*row_h + 0.9*cm
        y = _ensure_space(c, y, need, folio, fecha, tecnico, localidad)
        ye = _draw_section(c, "Datos eléctricos", y, need)

        c.setFont("Helvetica-Bold", 8.7)
        x0 = inner_x-0.3*cm; lab_w = 7.6*cm; cell = 3.1*cm
        yline = ye - 0.25*cm

        # Encabezado
        c.rect(x0, yline-row_h, lab_w+3*cell, row_h, fill=0, stroke=1)
        c.drawString(x0+2, yline-row_h+3, "MEDICIÓN")
        c.drawString(x0+lab_w+2,        yline-row_h+3, "L1 / L1-2")
        c.drawString(x0+lab_w+cell+2,   yline-row_h+3, "L2 / L2-3")
        c.drawString(x0+lab_w+2*cell+2, yline-row_h+3, "L3 / L3-1")
        yline -= row_h

        c.setFont("Helvetica", 8.6)

        # Trifásicos
        for idx, (titulo, vals) in enumerate(filtered_e3):
            # Check space before each row (except first, already checked for header)
            if idx > 0:
                temp_y = yline
                temp_y = _ensure_space(c, temp_y, row_h + 0.15*cm, folio, fecha, tecnico, localidad)
                if temp_y > yline:
                    yline = temp_y
            
            c.rect(x0, yline-row_h, lab_w, row_h, fill=0, stroke=1)
            c.drawString(x0+2, yline-row_h+3, titulo)

            for j, val in enumerate(vals):
                c.rect(x0+lab_w+j*cell, yline-row_h, cell, row_h, fill=0, stroke=1)
                c.drawString(x0+lab_w+j*cell+2, yline-row_h+3, val)
            yline -= row_h

        # Individuales
        for idx, (titulo, val) in enumerate(filtered_e1):
            # Check space before each individual row
            temp_y = yline
            temp_y = _ensure_space(c, temp_y, row_h + 0.15*cm, folio, fecha, tecnico, localidad)
            if temp_y > yline:
                yline = temp_y
            
            c.rect(x0, yline-row_h, lab_w+3*cell, row_h, fill=0, stroke=1)
            c.drawString(x0+2, yline-row_h+3, titulo)
            c.setFont("Helvetica-Bold", 8.6)
            c.drawRightString(x0+lab_w+3*cell-4, yline-row_h+3, val)
            c.setFont("Helvetica", 8.6)
            yline -= row_h

        y = yline - 0.2*cm

    if es_secador_preventivo:
        # Solo Corriente comp. en carga (L1,L2,L3) y Voltaje comp. en carga (L1-2,L2-3,L3-1)
        draw_electric(e3_vals, e1_vals, SEC_E3, SEC_E1)
    else:
        draw_electric(e3_vals, e1_vals, E3, E1)

    # OBSERVACIONES
    obs_lines = _wrap_text_force(observaciones, inner_w-0.6*cm)
    need_obs = 18 + len(obs_lines)*line_h + 0.9*cm
    y = _ensure_space(c, y, need_obs, folio, fecha, tecnico, localidad)
    yo = _draw_section(c, "Observaciones y recomendaciones", y, need_obs)
    c.setFont("Helvetica", 9)
    yy = yo - 0.55*cm
    for i, ln in enumerate(obs_lines):
        c.drawString(inner_x, yy - i*line_h, ln)
    y = yy - len(obs_lines)*line_h - 0.4*cm

    # FOTOS
    def draw_fotos(items):
        nonlocal y
        if not items:
            return

        gutter_col = 0.9*cm
        col_w = (inner_w - gutter_col) / 2.0
        img_w = col_w
        img_h = img_w * 0.70
        caption_h = 1.10*cm
        row_gap = 0.6*cm
        per_row_h = img_h + caption_h + row_gap

        idx = 0
        foto_num = 1

        def ellipsize(text, maxw):
            s = (text or "N/A").strip() or "N/A"
            while stringWidth(s, "Helvetica", 8.2) > maxw and len(s) > 3:
                s = s[:-2] + "…"
            return s

        while idx < len(items):
            disponible = y - 2.3*cm
            max_rows_fit = int((disponible - (18 + 0.8*cm)) // per_row_h)
            if max_rows_fit < 1:
                c.showPage(); _draw_header_and_footer(c, folio, fecha, tecnico, localidad)
                y = height - 3.2*cm
                continue

            rem_rows = math.ceil((len(items) - idx)/2)
            rows = min(max_rows_fit, rem_rows)
            need_here = 18 + rows*per_row_h + 0.8*cm
            yf = _draw_section(c, "Evidencias fotográficas", y, need_here)

            left_x = inner_x
            right_x = inner_x + col_w + gutter_col
            top = yf - 0.5*cm

            def draw_one(path, desc, x, ytop, num):
                c.rect(x, ytop - img_h, img_w, img_h, stroke=1, fill=0)
                if path and os.path.exists(path):
                    try:
                        c.drawImage(ImageReader(path), x, ytop - img_h, width=img_w, height=img_h,
                                    preserveAspectRatio=True, anchor='sw')
                    except Exception:
                        pass
                c.setFont("Helvetica", 8.2)
                maxw = img_w - 6
                lines = _wrap_text_force(desc or "N/A", maxw, "Helvetica", 8.2)
                line1 = ellipsize(lines[0] if lines else "N/A", maxw)
                line2 = ellipsize(lines[1] if len(lines) > 1 else "", maxw)
                base = ytop - img_h - 0.32*cm
                c.drawString(x, base, f"Foto {num}: {line1}")
                if line2:
                    c.drawString(x, base - 0.34*cm, line2)

            for r in range(rows):
                if idx < len(items):
                    p, d = items[idx]; idx += 1
                    draw_one(p, d, left_x, top - r*per_row_h, foto_num); foto_num += 1
                if idx < len(items):
                    p, d = items[idx]; idx += 1
                    draw_one(p, d, right_x, top - r*per_row_h, foto_num); foto_num += 1

            y = yf - rows*per_row_h - 0.3*cm

    # Si es Bitácora, limitamos a 2 fotos
    if ts in ("bitácora", "bitacora"):
        fotos = fotos[:2]
    draw_fotos(fotos)

    # FIRMAS
    need_firmas = 4.2*cm
    y = _ensure_space(c, y, need_firmas, folio, fecha, tecnico, localidad)
    yfm = _draw_section(c, "Firmas", y, need_firmas)
    c.setFont("Helvetica", 9)
    c.drawString(2.0*cm, yfm-1.0*cm, f"Técnico: {firma_tecnico_nombre}")
    c.line(2.0*cm, yfm-2.7*cm, 9.2*cm, yfm-2.7*cm)
    if firma_tecnico_path and os.path.exists(firma_tecnico_path):
        c.drawImage(ImageReader(firma_tecnico_path), 2.0*cm, yfm-2.6*cm, width=7.2*cm, height=1.6*cm,
                    preserveAspectRatio=True, anchor='sw')
    c.drawString(10.2*cm, yfm-1.0*cm, f"Cliente: {firma_cliente_nombre}")
    c.line(10.2*cm, yfm-2.7*cm, 17.2*cm, yfm-2.7*cm)
    if firma_cliente_path and os.path.exists(firma_cliente_path):
        c.drawImage(ImageReader(firma_cliente_path), 10.2*cm, yfm-2.6*cm, width=7.2*cm, height=1.6*cm,
                    preserveAspectRatio=True, anchor='sw')

    # --- cerrar el PDF y guardar en borrador ---
    c.showPage(); c.save(); buf.seek(0)
    pdf_bytes = buf.read()
    nombre_pdf = f"REPORTE_{tipo_servicio.upper()}_{cliente.replace(' ', '_')}.pdf"

    # Save report metadata to database for service history
    save_report(
        folio=folio,
        fecha=fecha,
        cliente=cliente,
        tipo_equipo=tipo_equipo,
        modelo=modelo,
        serie=serie,
        marca=marca,
        potencia=potencia,
        tipo_servicio=tipo_servicio,
        descripcion_servicio=desc_servicio,
        tecnico=tecnico,
        localidad=localidad
    )

    # Convertir fotos a base64 para guardar en borrador
    # Convertir fotos a base64 para guardar en borrador
    fotos_base64 = {}
    for i in range(1, 5):
        foto_file = request.files.get(f"foto{i}")
        existing_b64 = request.form.get(f"foto{i}_existing")
        
        if foto_file and foto_file.filename:
            # Re-read the file (it was already saved to disk above)
            foto_file.seek(0)
            foto_bytes = foto_file.read()
            fotos_base64[f"foto{i}"] = base64.b64encode(foto_bytes).decode('utf-8')
        elif existing_b64:
            # Use existing base64 data
            if "," in existing_b64:
                existing_b64 = existing_b64.split(",")[1]
            fotos_base64[f"foto{i}"] = existing_b64
    
    # Preparar form_data para guardar en borrador
    form_data = {}
    for key in request.form:
        form_data[key] = request.form.get(key)
    
    # Guardar borrador completo con PDF
    save_draft_report(
        folio=folio,
        form_data=form_data,
        foto1=fotos_base64.get("foto1"),
        foto2=fotos_base64.get("foto2"),
        foto3=fotos_base64.get("foto3"),
        foto4=fotos_base64.get("foto4"),
        firma_tecnico=request.form.get("firma_tecnico_data"),
        firma_cliente=request.form.get("firma_cliente_data"),
        pdf_preview=pdf_bytes
    )

    # Redirigir a vista previa en lugar de descargar
    return redirect(url_for("vista_previa", folio=folio))


# === API: crear un nuevo folio y dejarlo en la sesión ===
@app.route("/api/nuevo_folio", methods=["POST"])
def api_nuevo_folio():
    if "user" not in session:
        return ("", 401)
    session["folio_actual"] = get_next_folio(session["prefijo"])
    return {"folio": session["folio_actual"]}

# ==================== DRAFT REPORT ROUTES ====================

@app.route("/api/autosave_draft", methods=["POST"])
def api_autosave_draft():
    """Auto-save draft report (called every few seconds from JavaScript)"""
    if "user" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data"}), 400
        
        folio = data.get("folio")
        form_data = data.get("form_data", {})
        
        # Extract photos and signatures from form_data (they're stored there by serializeForm)
        foto1 = form_data.get("foto1_data") or data.get("foto1_data")
        foto2 = form_data.get("foto2_data") or data.get("foto2_data")
        foto3 = form_data.get("foto3_data") or data.get("foto3_data")
        foto4 = form_data.get("foto4_data") or data.get("foto4_data")
        firma_tecnico = form_data.get("firma_tecnico_data") or data.get("firma_tecnico_data")
        firma_cliente = form_data.get("firma_cliente_data") or data.get("firma_cliente_data")
        
        if not folio:
            return jsonify({"error": "Missing folio"}), 400
        
        # Save to database
        save_draft_report(
            folio=folio,
            form_data=form_data,
            foto1=foto1,
            foto2=foto2,
            foto3=foto3,
            foto4=foto4,
            firma_tecnico=firma_tecnico,
            firma_cliente=firma_cliente
        )
        
        return jsonify({"success": True, "message": "Draft saved"})
    
    except Exception as e:
        print(f"Error saving draft: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/guardar_borrador", methods=["POST"])
def guardar_borrador():
    """Generate PDF preview and redirect to preview page"""
    if "user" not in session:
        return redirect(url_for("login"))
    
    # This route will reuse the existing PDF generation logic from generar_pdf
    # but instead of downloading, it saves to database and redirects to preview
    
    folio = request.form.get("folio") or session.get("folio_actual")
    
    # First, save all form data to draft (similar to autosave but with files)
    form_data = {}
    for key in request.form:
        form_data[key] = request.form.get(key)
    
    # Handle photo uploads - convert to Base64
    fotos_base64 = {}
    for i in range(1, 5):
        foto_file = request.files.get(f"foto{i}")
        if foto_file and foto_file.filename:
            foto_bytes = foto_file.read()
            fotos_base64[f"foto{i}_data"] = base64.b64encode(foto_bytes).decode('utf-8')
    
    # Generate PDF (reuse existing logic but capture to bytes)
    pdf_bytes = _generate_pdf_bytes(request.form, request.files)
    
    # Save complete draft including PDF
    save_draft_report(
        folio=folio,
        form_data=form_data,
        foto1=fotos_base64.get("foto1_data"),
        foto2=fotos_base64.get("foto2_data"),
        foto3=fotos_base64.get("foto3_data"),
        foto4=fotos_base64.get("foto4_data"),
        firma_tecnico=request.form.get("firma_tecnico_data"),
        firma_cliente=request.form.get("firma_cliente_data"),
        pdf_preview=pdf_bytes
    )
    
    return redirect(url_for("vista_previa", folio=folio))

@app.route("/vista_previa/<folio>")
def vista_previa(folio):
    """Show PDF preview page with Edit and Send buttons"""
    if "user" not in session:
        return redirect(url_for("login"))
    
    draft = get_draft_by_folio(folio)
    if not draft:
        return "Borrador no encontrado", 404
    
    # Parse form_data to get client email
    try:
        form_data = json.loads(draft["form_data"]) if isinstance(draft["form_data"], str) else draft["form_data"]
        client_email = form_data.get("email", "")
    except:
        client_email = ""
    
    return render_template("vista_previa.html", 
                         folio=folio,
                         client_email=client_email,
                         draft=draft)


def _get_filename_from_draft(draft, folio):
    """Generate filename: Tipo_Descripcion_Folio.pdf"""
    try:
        form_data = json.loads(draft["form_data"]) if isinstance(draft["form_data"], str) else draft["form_data"]
        tipo = form_data.get("tipo_servicio", "Servicio").strip().replace(" ", "_")
        desc = form_data.get("descripcion_servicio", "Descripcion").strip().replace(" ", "_")
        
        # Sanitize
        import re
        tipo = re.sub(r'[\\/*?:"<>|]', "", tipo)
        desc = re.sub(r'[\\/*?:"<>|]', "", desc)
        
        # Limit length just in case
        if len(desc) > 30: desc = desc[:30]
        
        return f"{tipo}_{desc}_{folio}.pdf"
    except:
        return f"Reporte_{folio}.pdf"

@app.route("/api/pdf_preview/<folio>")
def api_pdf_preview(folio):
    """Return PDF file for preview or download"""
    if "user" not in session:
        return ("", 401)
    
    draft = get_draft_by_folio(folio)
    if not draft or not draft.get("pdf_preview"):
        return "PDF no encontrado", 404
    
    should_download = request.args.get('download') == 'true'
    filename = _get_filename_from_draft(draft, folio)
    
    return send_file(
        io.BytesIO(draft["pdf_preview"]),
        mimetype="application/pdf",
        as_attachment=should_download,
        download_name=filename
    )

@app.route("/editar_reporte/<folio>")
def editar_reporte(folio):
    """Load form with draft data for editing"""
    if "user" not in session:
        return redirect(url_for("login"))
    
    # Set the folio in session for the form to use
    session["folio_actual"] = folio
    
    # Render the form - JavaScript will load the draft data
    return render_template(
        "formulario.html",
        folio=folio,
        lista_equipos=LISTA_EQUIPOS,
        dg_labels=DG_LABELS, 
        of_labels=OF_LABELS, 
        e3=E3, 
        e1=E1,
        edit_mode=True  # Flag to tell the template we're editing
    )

@app.route("/api/load_draft/<folio>")
def api_load_draft(folio):
    """Return draft data as JSON for form population"""
    if "user" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    draft = get_draft_by_folio(folio)
    if not draft:
        return jsonify({"error": "Draft not found"}), 404
    
    # Parse form_data
    try:
        form_data = json.loads(draft["form_data"]) if isinstance(draft["form_data"], str) else draft["form_data"]
    except:
        form_data = {}
    
    return jsonify({
        "form_data": form_data,
        "foto1_data": draft.get("foto1_data"),
        "foto2_data": draft.get("foto2_data"),
        "foto3_data": draft.get("foto3_data"),
        "foto4_data": draft.get("foto4_data"),
        "firma_tecnico_data": draft.get("firma_tecnico_data"),
        "firma_cliente_data": draft.get("firma_cliente_data")
    })

@app.route("/enviar_reporte/<folio>", methods=["POST"])
def enviar_reporte(folio):
    """Send report via email to client"""
    if "user" not in session:
        return redirect(url_for("login"))
    
    # Get draft data
    draft = get_draft_by_folio(folio)
    if not draft or not draft.get("pdf_preview"):
        return "Reporte no encontrado", 404
    
    # Get client email from form data
    try:
        form_data = json.loads(draft["form_data"]) if isinstance(draft["form_data"], str) else draft["form_data"]
        client_email = form_data.get("email", "").strip()
        cliente_nombre = form_data.get("cliente", "Cliente")
        tipo_servicio = form_data.get("tipo_servicio", "servicio")
    except:
        return "Error al obtener datos del cliente", 400
    
    if not client_email:
        return "No se especificó email del cliente", 400
    
    # Configure SMTP (use environment variables for production)
    # For Gmail: you need to use an App Password if 2FA is enabled
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "customerg0179@gmail.com")
    smtp_password = os.environ.get("SMTP_PASSWORD", "bhzt jwak cfdc vjjx")
    
    if not smtp_user or not smtp_password:
        return "Configuración de email no disponible. Configure SMTP_USER y SMTP_PASSWORD", 500
    
    try:
        # Create email
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = client_email
        msg['Cc'] = "customerservice@inair.com.mx"
        msg['Subject'] = f"Reporte de {tipo_servicio} - Folio {folio}"
        
        # Email body
        body = f"""
Estimado/a {cliente_nombre},

Adjunto encontrará el reporte de {tipo_servicio} correspondiente al folio {folio}.

Si tiene alguna pregunta o comentario, no dude en contactarnos.

Saludos cordiales,
InAIR - Servicio Técnico
        """.strip()
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach PDF
        pdf_bytes = draft["pdf_preview"]
        filename = _get_filename_from_draft(draft, folio)
        pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
        pdf_attachment.add_header('Content-Disposition', 'attachment', 
                                 filename=filename)
        msg.attach(pdf_attachment)
        
        # Send email
        recipients = [client_email, "customerservice@inair.com.mx"]
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, recipients, msg.as_string())
        server.quit()
        
        # Mark draft as sent
        mark_draft_as_sent(folio)
        
        # Clear current folio from session
        session.pop("folio_actual", None)
        
        # Redirect to success page
        return render_template("envio_exitoso.html", folio=folio, email=client_email, filename=filename)
        
    except Exception as e:
        print(f"Error al enviar email: {e}")
        return f"Error al enviar el correo: {str(e)}", 500



# ==================== ADMIN ROUTES ====================

@app.route("/admin/dashboard")
@require_role("admin")
def admin_dashboard():
    """Admin dashboard with statistics and navigation"""
    stats = get_dashboard_stats()
    return render_template("admin_dashboard.html", stats=stats)

# ---------- Client Management ----------

@app.route("/admin/clientes")
@require_role("admin")
def admin_clientes():
    """List all clients"""
    clients = get_all_clients()
    return render_template("admin_clientes.html", clients=clients, lista_equipos=LISTA_EQUIPOS)

@app.route("/admin/clientes/nuevo", methods=["POST"])
@require_role("admin")
def admin_clientes_nuevo():
    """Create new client"""
    nombre = request.form.get("nombre", "").strip()
    contacto = request.form.get("contacto", "").strip()
    telefono = request.form.get("telefono", "").strip()
    email = request.form.get("email", "").strip()
    direccion = request.form.get("direccion", "").strip()
    
    if nombre:
        create_client(nombre, contacto, telefono, email, direccion)
    
    return redirect(url_for("admin_clientes"))

@app.route("/admin/clientes/editar/<int:client_id>", methods=["POST"])
@require_role("admin")
def admin_clientes_editar(client_id):
    """Update client information"""
    nombre = request.form.get("nombre", "").strip()
    contacto = request.form.get("contacto", "").strip()
    telefono = request.form.get("telefono", "").strip()
    email = request.form.get("email", "").strip()
    direccion = request.form.get("direccion", "").strip()
    
    if nombre:
        update_client(client_id, nombre, contacto, telefono, email, direccion)
    
    return redirect(url_for("admin_clientes"))

@app.route("/admin/clientes/eliminar/<int:client_id>", methods=["POST"])
@require_role("admin")
def admin_clientes_eliminar(client_id):
    """Delete client"""
    delete_client(client_id)
    return redirect(url_for("admin_clientes"))

# ---------- User Management ----------

@app.route("/admin/usuarios")
@require_role("admin")
def admin_usuarios():
    """List all users"""
    users = get_all_users()
    return render_template("admin_usuarios.html", users=users)

@app.route("/admin/usuarios/nuevo", methods=["POST"])
@require_role("admin")
def admin_usuarios_nuevo():
    """Create new user"""
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "").strip()
    nombre = request.form.get("nombre", "").strip()
    prefijo = request.form.get("prefijo", "").strip().upper()
    role = request.form.get("role", "technician").strip()
    
    if username and password and nombre and prefijo:
        try:
            create_user(username, password, nombre, prefijo, role)
        except:
            pass  # User already exists
    
    return redirect(url_for("admin_usuarios"))

@app.route("/admin/usuarios/eliminar/<int:user_id>", methods=["POST"])
@require_role("admin")
def admin_usuarios_eliminar(user_id):
    """Delete user"""
    # Get current user to prevent self-deletion
    current_user = get_user_by_username(session.get("user"))
    if current_user and current_user["id"] != user_id:
        delete_user(user_id)
    
    return redirect(url_for("admin_usuarios"))

# ---------- Service History ----------

@app.route("/admin/historial")
@require_role("admin")
def admin_historial():
    """View service history with filters"""
    search_term = request.args.get("search", "").strip()
    tipo_servicio = request.args.get("tipo_servicio", "").strip()
    fecha_inicio = request.args.get("fecha_inicio", "").strip()
    fecha_fin = request.args.get("fecha_fin", "").strip()
    
    if search_term or tipo_servicio or fecha_inicio or fecha_fin:
        reports = search_reports(search_term, tipo_servicio, fecha_inicio, fecha_fin)
    else:
        reports = get_all_reports()
    
    return render_template("admin_historial.html", reports=reports)

@app.route("/admin/historial/<folio>")
@require_role("admin")
def admin_historial_detalle(folio):
    """Get report details as JSON"""
    report = get_report_by_folio(folio)
    if report:
        return jsonify(report)
    return jsonify({"error": "Report not found"}), 404

# ---------- Maintenance Plans ----------
# NOTE: These routes are commented out because the maintenance plan functions
# don't exist in database.py. Equipment maintenance is now handled through
# the client equipment system instead.

# @app.route("/admin/mantenimiento")
# @require_role("admin")
# def admin_mantenimiento():
#     """List all maintenance plans"""
#     plans = get_all_maintenance_plans()
#     return render_template("admin_mantenimiento.html", plans=plans)

# @app.route("/admin/mantenimiento/nuevo", methods=["GET", "POST"])
# @require_role("admin")
# def admin_mantenimiento_nuevo():
#     """Create new maintenance plan"""
#     if request.method == "POST":
#         cliente_id = request.form.get("cliente_id", type=int)
#         tipo_equipo = request.form.get("tipo_equipo", "").strip()
#         modelo = request.form.get("modelo", "").strip()
#         serie = request.form.get("serie", "").strip()
#         frecuencia_dias = request.form.get("frecuencia_dias", type=int)
#         fecha_inicial = request.form.get("fecha_inicial", "").strip()
#         
#         if cliente_id and tipo_equipo and frecuencia_dias and fecha_inicial:
#             create_maintenance_plan(cliente_id, tipo_equipo, modelo, serie, 
#                                    frecuencia_dias, fecha_inicial)
#             return redirect(url_for("admin_mantenimiento"))
#     
#     # GET request - show form
#     clients = get_all_clients()
#     return render_template("admin_mantenimiento_nuevo.html", 
#                          clients=clients, 
#                          lista_equipos=LISTA_EQUIPOS)

# @app.route("/admin/mantenimiento/<int:plan_id>")
# @require_role("admin")
# def admin_mantenimiento_detalle(plan_id):
#     """View maintenance plan details"""
#     plan = get_maintenance_plan_by_id(plan_id)
#     if not plan:
#         return redirect(url_for("admin_mantenimiento"))
#     
#     services = get_services_by_plan(plan_id)
#     
#     # Get parts for each service
#     for service in services:
#         service['parts'] = get_parts_by_service(service['id'])
#     
#     return render_template("admin_mantenimiento_detalle.html", 
#                          plan=plan, 
#                          services=services)

# @app.route("/admin/mantenimiento/<int:plan_id>/servicio", methods=["POST"])
# @require_role("admin")
# def admin_mantenimiento_agregar_servicio(plan_id):
#     """Add service to maintenance plan"""
#     fecha_servicio = request.form.get("fecha_servicio", "").strip()
#     descripcion = request.form.get("descripcion", "").strip()
#     tecnico = request.form.get("tecnico", "").strip()
#     folio = request.form.get("folio", "").strip()
#     
#     if fecha_servicio and descripcion:
#         service_id = create_maintenance_service(plan_id, fecha_servicio, 
#                                                descripcion, tecnico, folio)
#         
#         # Add parts if provided
#         part_names = request.form.getlist("part_nombre[]")
#         part_quantities = request.form.getlist("part_cantidad[]")
#         part_descriptions = request.form.getlist("part_descripcion[]")
#         
#         for i, nombre in enumerate(part_names):
#             if nombre.strip():
#                 cantidad = int(part_quantities[i]) if i < len(part_quantities) and part_quantities[i].isdigit() else 1
#                 desc = part_descriptions[i] if i < len(part_descriptions) else ""
#                 create_part(service_id, nombre.strip(), cantidad, desc.strip())
#     
#     return redirect(url_for("admin_mantenimiento_detalle", plan_id=plan_id))

# @app.route("/admin/mantenimiento/<int:plan_id>/toggle", methods=["POST"])
# @require_role("admin")
# def admin_mantenimiento_toggle(plan_id):
#     """Toggle maintenance plan active status"""
#     from database import toggle_maintenance_plan
#     toggle_maintenance_plan(plan_id)
#     return redirect(url_for("admin_mantenimiento"))


# ==========================================
# API Routes for Auto-fill
# ==========================================

@app.route("/api/clientes")
def api_clientes():
    """Get list of all clients"""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    clients = get_all_clients()
    return jsonify([{
        "id": c["id"],
        "nombre": c["nombre"],
        "contacto": c.get("contacto", ""),
        "telefono": c.get("telefono", ""),
        "email": c.get("email", ""),
        "direccion": c.get("direccion", "")
    } for c in clients])

@app.route("/api/cliente/<int:client_id>")
def api_cliente_detalle(client_id):
    """Get client details"""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    client = get_client_by_id(client_id)
    if not client:
        return jsonify({"error": "Client not found"}), 404
    
    return jsonify({
        "id": client["id"],
        "nombre": client["nombre"],
        "contacto": client["contacto"],
        "telefono": client["telefono"],
        "email": client["email"],
        "direccion": client["direccion"]
    })

@app.route("/api/equipos/<int:client_id>")
def api_client_equipment(client_id):
    """Get all equipment for a client"""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    equipment = get_client_equipment(client_id)
    return jsonify([{
        "id": e["id"],
        "tipo_equipo": e["tipo_equipo"],
        "modelo": e["modelo"],
        "serie": e["serie"],
        "marca": e["marca"],
        "potencia": e["potencia"],
        "proximo_servicio": e["proximo_servicio"]
    } for e in equipment])
    return jsonify({
        "id": client["id"],
        "nombre": client["nombre"],
        "contacto": client["contacto"],
        "telefono": client["telefono"],
        "email": client["email"],
        "direccion": client["direccion"]
    })

@app.route("/api/tipos_equipo/<int:client_id>")
def api_tipos_equipo(client_id):
    """Get unique equipment types for a client"""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    types = get_equipment_types_by_client(client_id)
    return jsonify(types)

@app.route("/api/modelos/<int:client_id>/<path:tipo_equipo>")
def api_modelos(client_id, tipo_equipo):
    """Get models for a client and equipment type"""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    models = get_models_by_client_and_type(client_id, tipo_equipo)
    return jsonify(models)

@app.route("/api/equipo/<int:equipment_id>")
def api_equipo_detalle(equipment_id):
    """Get full equipment details"""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    equipment = get_equipment_by_id(equipment_id)
    if not equipment:
        return jsonify({"error": "Equipment not found"}), 404
        
    return jsonify(dict(equipment))

# ==========================================
# Admin Routes for Equipment Management
# ==========================================

@app.route("/admin/clientes/<int:client_id>/equipos", methods=["POST"])
@require_role("admin")
def admin_agregar_equipo(client_id):
    """Add equipment to a client"""
    tipo_equipo = request.form.get("tipo_equipo")
    modelo = request.form.get("modelo")
    serie = request.form.get("serie")
    marca = request.form.get("marca")
    potencia = request.form.get("potencia")
    
    # Maintenance Info
    ultimo_servicio = request.form.get("ultimo_servicio")
    frecuencia_meses = int(request.form.get("frecuencia_meses", 1))
    
    # Calculate next service
    proximo_servicio = None
    if ultimo_servicio:
        try:
            last_date = datetime.strptime(ultimo_servicio, '%Y-%m-%d')
            # Add months (approximate as 30 days * months for simplicity, or use relativedelta if available, but standard lib doesn't have it. 
            # Let's use a simple approximation or a custom function if needed. 
            # For now, 30 days * months is a reasonable approximation for maintenance intervals usually defined in hours/months.)
            # Better: Use a helper to add months correctly if possible, but standard datetime doesn't support adding months directly.
            # Let's just use 30 days per month for now to avoid external deps like dateutil.
            next_date = last_date + timedelta(days=frecuencia_meses * 30)
            proximo_servicio = next_date.strftime('%Y-%m-%d')
        except ValueError:
            pass

    # Kits (JSON strings)
    # We will receive lists of parts (qty, desc) for each kit.
    # The form will likely send arrays like kit_2000_qty[], kit_2000_desc[]
    import json
    
    def get_kit_data(prefix):
        qtys = request.form.getlist(f"{prefix}_qty[]")
        descs = request.form.getlist(f"{prefix}_desc[]")
        parts = []
        for q, d in zip(qtys, descs):
            if q.strip() or d.strip(): # Only add if not empty
                parts.append({"cantidad": q, "descripcion": d})
        return json.dumps(parts) if parts else None

    kit_2000 = get_kit_data("kit_2000")
    kit_4000 = get_kit_data("kit_4000")
    kit_6000 = get_kit_data("kit_6000")
    kit_8000 = get_kit_data("kit_8000")
    kit_16000 = get_kit_data("kit_16000")
    
    if tipo_equipo:
        add_client_equipment(client_id, tipo_equipo, modelo, serie, marca, potencia,
                             ultimo_servicio, frecuencia_meses, proximo_servicio,
                             kit_2000, kit_4000, kit_6000, kit_8000, kit_16000)
        
    return redirect(url_for("admin_clientes"))

@app.route("/admin/equipos/eliminar/<int:equipment_id>", methods=["POST"])
@require_role("admin")
def admin_eliminar_equipo(equipment_id):
    """Delete equipment"""
    # We need client_id to redirect back properly, but for now redirecting to clients list
    delete_client_equipment(equipment_id)
    return redirect(url_for("admin_clientes"))



# ==================== MÓDULO DE EQUIPOS ====================
# Rutas independientes para gestión de equipos (no tocar lógica de reportes)

@app.route("/admin/equipos_modulo")
@require_role("admin")
def admin_equipos_modulo():
    """Vista principal del módulo de equipos"""
    return render_template("equipos.html", LISTA_EQUIPOS=LISTA_EQUIPOS)

@app.route("/admin/calendario")
@require_role("admin")
def admin_calendario():
    """Vista del calendario de mantenimiento"""
    return render_template("calendario_mantenimiento.html")

@app.route("/api/clientes/<int:cliente_id>/equipos", methods=["GET"])
def api_cliente_equipos(cliente_id):
    """Obtener equipos asignados a un cliente desde equipos_calendario + info del cliente"""
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get client info
        c.execute("SELECT * FROM clients WHERE id = ?", (cliente_id,))
        cliente = c.fetchone()
        
        # Get equipment
        c.execute("""
            SELECT id, serie, tipo_equipo, modelo, marca, potencia 
            FROM equipos_calendario 
            WHERE cliente_id = ? AND activo = 1
            ORDER BY tipo_equipo, modelo, serie
        """, (cliente_id,))
        
        equipos = [dict(row) for row in c.fetchall()]
        conn.close()
        
        return jsonify({
            "cliente": dict(cliente) if cliente else None,
            "equipos": equipos
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/equipos_list", methods=["GET"])
@require_role("admin")
def api_equipos_list():
    """Listar todos los equipos del calendario"""
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("""
            SELECT 
                e.*,
                c.nombre as cliente_nombre
            FROM equipos_calendario e
            LEFT JOIN clients c ON e.cliente_id = c.id
            WHERE e.activo = 1
            ORDER BY e.id DESC
        """)
        
        equipos = [dict(row) for row in c.fetchall()]
        conn.close()
        
        return jsonify(equipos)
    except Exception as e:
        print(f"ERROR API EQUIPOS: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/equipos_create", methods=["POST"])
@require_role("admin")
def api_equipos_create():
    """Crear nuevo equipo en calendario"""
    data = request.json
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    print(f"DEBUG CREATE EQUIPO: {data}") # Debug log
    
    try:
        c.execute("""
            INSERT INTO equipos_calendario 
            (cliente_id, serie, tipo_equipo, modelo, marca, potencia, 
             frecuencia_meses, mes_inicio, anio_inicio, tipo_servicio_inicial, reiniciar_en_horas, notas, clasificacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(data.get("cliente_id")) if data.get("cliente_id") else None,
            data.get("serie"),
            data.get("tipo_equipo"),
            data.get("modelo"),
            data.get("marca"),
            data.get("potencia"),
            data.get("frecuencia_meses"),
            data.get("mes_inicio"),
            data.get("anio_inicio"),
            data.get("tipo_servicio_inicial", "2000 Horas"),
            int(data.get("reiniciar_en_horas")) if data.get("reiniciar_en_horas") else None,
            data.get("notas"),
            data.get("clasificacion", "General")
        ))
        
        conn.commit()
        equipo_id = c.lastrowid
        conn.close()
        
        return jsonify({"success": True, "id": equipo_id})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"success": False, "error": "Serie ya existe"}), 400

@app.route("/api/equipos_update/<int:equipo_id>", methods=["PUT"])
@require_role("admin")
def api_equipos_update(equipo_id):
    """Actualizar equipo"""
    data = request.json
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    print(f"DEBUG UPDATE EQUIPO {equipo_id}: {data}") # Debug log
    
    c.execute("""
        UPDATE equipos_calendario 
        SET cliente_id=?, tipo_equipo=?, modelo=?, marca=?, potencia=?,
            frecuencia_meses=?, mes_inicio=?, anio_inicio=?, tipo_servicio_inicial=?, reiniciar_en_horas=?, notas=?, clasificacion=?
        WHERE id=?
    """, (
        int(data.get("cliente_id")) if data.get("cliente_id") else None,
        data.get("tipo_equipo"),
        data.get("modelo"),
        data.get("marca"),
        data.get("potencia"),
        data.get("frecuencia_meses"),
        data.get("mes_inicio"),
        data.get("anio_inicio"),
        data.get("tipo_servicio_inicial", "2000 Horas"),
        int(data.get("reiniciar_en_horas")) if data.get("reiniciar_en_horas") else None,
        data.get("notas"),
        data.get("clasificacion", "General"),
        equipo_id
    ))
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True})

@app.route("/api/equipos/<int:equipo_id>/kits", methods=["GET"])
@require_role("admin")
def api_equipos_kits_get(equipo_id):
    """Obtener kits de refacciones para un equipo"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT * FROM equipos_kits WHERE equipo_id = ?", (equipo_id,))
    kits = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return jsonify(kits)

@app.route("/api/equipos/<int:equipo_id>/kits", methods=["POST"])
@require_role("admin")
def api_equipos_kits_save(equipo_id):
    """Guardar kits de refacciones para un equipo"""
    data = request.json # Expects list of kits: [{tipo_servicio, refacciones_json}, ...]
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    try:
        # Delete existing kits for this equipment to replace with new list
        c.execute("DELETE FROM equipos_kits WHERE equipo_id = ?", (equipo_id,))
        
        for kit in data:
            c.execute("""
                INSERT INTO equipos_kits (equipo_id, tipo_servicio, refacciones_json)
                VALUES (?, ?, ?)
            """, (equipo_id, kit['tipo_servicio'], kit['refacciones_json']))
        
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        conn.close()
        print(f"ERROR SAVING KITS: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/equipos_delete/<int:equipo_id>", methods=["DELETE"])
@require_role("admin")
def api_equipos_delete(equipo_id):
    """Eliminar equipo (soft delete)"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    c.execute("UPDATE equipos_calendario SET activo = 0 WHERE id = ?", (equipo_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True})

@app.route("/api/equipos_historial/<int:equipo_id>", methods=["GET"])
@require_role("admin")
def api_equipos_historial(equipo_id):
    """Obtener historial de servicios del equipo"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Obtener serie del equipo
    c.execute("SELECT serie FROM equipos_calendario WHERE id = ?", (equipo_id,))
    result = c.fetchone()
    
    if not result:
        conn.close()
        return jsonify([])
    
    serie = result["serie"]
    
    # Buscar reportes que contengan esa serie
    c.execute("""
        SELECT folio, fecha_creation, form_data
        FROM drafts
        WHERE form_data LIKE ?
        ORDER BY fecha_creation DESC
    """, (f"%{serie}%",))
    
    reportes = []
    for row in c.fetchall():
        try:
            form_data = json.loads(row["form_data"])
            if form_data.get("serie") == serie:
                reportes.append({
                    "folio": row["folio"],
                    "fecha": row["fecha_creation"],
                    "tipo_servicio": form_data.get("tipo_servicio"),
                    "descripcion": form_data.get("descripcion_servicio")
                })
        except:
            pass
    
    conn.close()
    return jsonify(reportes)

# ==================== FASE 4: CATÁLOGO DE REFACCIONES ====================

@app.route("/api/refacciones_catalogo", methods=["GET"])
@require_role("admin")
def api_refacciones_catalogo():
    """Listar catálogo de refacciones"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT * FROM refacciones_catalogo ORDER BY tipo_equipo, tipo_servicio")
    refacciones = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return jsonify(refacciones)

@app.route("/api/refacciones_catalogo/create", methods=["POST"])
@require_role("admin")
def api_refacciones_catalogo_create():
    """Crear refacción en catálogo"""
    data = request.json
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO refacciones_catalogo 
            (tipo_equipo, tipo_servicio, nombre_refaccion, cantidad, unidad)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data.get("tipo_equipo"),
            data.get("tipo_servicio"),
            data.get("nombre_refaccion"),
            data.get("cantidad"),
            data.get("unidad")
        ))
        
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"success": False, "error": "Refacción ya existe"}), 400

@app.route("/api/refacciones_catalogo/<int:id>", methods=["DELETE"])
@require_role("admin")
def api_refacciones_catalogo_delete(id):
    """Eliminar refacción del catálogo"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("DELETE FROM refacciones_catalogo WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/equipos/<int:equipo_id>/refacciones", methods=["GET"])
@require_role("admin")
def api_equipos_refacciones(equipo_id):
    """Obtener refacciones de un equipo (catálogo + custom)"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Obtener tipo de equipo
    c.execute("SELECT tipo_equipo FROM equipos_calendario WHERE id = ?", (equipo_id,))
    result = c.fetchone()
    
    if not result:
        conn.close()
        return jsonify({"catalogo": [], "custom": []})
    
    tipo_equipo = result["tipo_equipo"]
    
    # Catálogo general
    c.execute("""
        SELECT * FROM refacciones_catalogo 
        WHERE tipo_equipo = ?
        ORDER BY tipo_servicio, nombre_refaccion
    """, (tipo_equipo,))
    catalogo = [dict(row) for row in c.fetchall()]
    
    # Custom del equipo
    c.execute("""
        SELECT * FROM equipos_refacciones_custom 
        WHERE equipo_id = ?
        ORDER BY tipo_servicio, nombre_refaccion
    """, (equipo_id,))
    custom = [dict(row) for row in c.fetchall()]
    
    conn.close()
    return jsonify({"catalogo": catalogo, "custom": custom})

# ==================== FASE 5: CALENDARIO DE MANTENIMIENTO ====================

@app.route("/api/calendario/<int:anio>/<int:mes>", methods=["GET"])
@require_role("admin")
def api_calendario_mes(anio, mes):
    """Obtener equipos que requieren servicio en un mes específico"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    equipos = []
    
    # Fetch all kits to avoid N+1 queries
    c.execute("SELECT * FROM equipos_kits")
    all_kits = [dict(row) for row in c.fetchall()]
    # Group kits by equipment_id
    kits_by_equipo = {}
    for k in all_kits:
        if k['equipo_id'] not in kits_by_equipo:
            kits_by_equipo[k['equipo_id']] = []
        kits_by_equipo[k['equipo_id']].append(k)

    for row in c.fetchall(): # This fetchall is empty because I already fetched above? No, different cursor execution.
        # Wait, I need to re-execute the equipment query or fetch before kits query.
        pass
    
    # Let's re-structure to be safe
    c.execute("""
        SELECT 
            e.*,
            c.nombre as cliente_nombre
        FROM equipos_calendario e
        LEFT JOIN clients c ON e.cliente_id = c.id
        WHERE e.activo = 1
    """)
    rows = c.fetchall()
    
    for row in rows:
        equipo = dict(row)
        # Calcular si le toca servicio este mes
        mes_inicio = equipo["mes_inicio"]
        anio_inicio = equipo["anio_inicio"]
        frecuencia = equipo["frecuencia_meses"]
        
        # Calcular meses desde inicio
        meses_desde_inicio = (anio - anio_inicio) * 12 + (mes - mes_inicio)
        
        if meses_desde_inicio >= 0 and meses_desde_inicio % frecuencia == 0:
            equipo["mes_servicio"] = mes
            equipo["anio_servicio"] = anio
            
            # Calculate Service Type with cycle reset support
            service_count = (meses_desde_inicio // frecuencia) + 1
            
            # Get tipo_servicio_inicial (default to 2000 Horas)
            servicio_inicial = equipo.get("tipo_servicio_inicial", "2000 Horas")
            
            # Extract initial hours value (e.g., "2000 Horas" -> 2000)
            try:
                horas_iniciales = int(servicio_inicial.split()[0])
            except:
                horas_iniciales = 2000
            
            # Apply cycle reset if configured
            reiniciar_en = equipo.get("reiniciar_en_horas")
            
            if reiniciar_en:
                # Build the cycle: [2000, 4000, 6000, 8000] and repeat
                servicios_en_ciclo = []
                hora_actual = horas_iniciales
                while hora_actual <= reiniciar_en:
                    servicios_en_ciclo.append(hora_actual)
                    hora_actual += 2000
                
                # Get position in cycle (0-indexed)
                ciclo_index = (service_count - 1) % len(servicios_en_ciclo)
                hours_est = servicios_en_ciclo[ciclo_index]
            else:
                # No cycle reset: continue incrementing
                hours_est = horas_iniciales + ((service_count - 1) * 2000)
            
            service_name_est = f"{hours_est} Horas"
            equipo["tipo_servicio_calculado"] = service_name_est
            
            # Find matching kit
            equipo_kits = kits_by_equipo.get(equipo['id'], [])
            suggested_parts = []
            
            # Try exact match
            matching_kit = next((k for k in equipo_kits if k['tipo_servicio'] == service_name_est), None)
            
            # If not found, try default service type
            if not matching_kit:
                 matching_kit = next((k for k in equipo_kits if k['tipo_servicio'] == equipo.get('tipo_servicio_inicial')), None)
            
            if matching_kit:
                try:
                    suggested_parts = json.loads(matching_kit['refacciones_json'])
                except:
                    pass
            
            equipo["refacciones_sugeridas"] = suggested_parts
            
            # Check if service was completed (report exists for this month/year)
            c.execute("""
                SELECT folio, fecha FROM reports 
                WHERE serie = ? 
                AND strftime('%Y', fecha) = ? 
                AND strftime('%m', fecha) = ?
                ORDER BY fecha DESC LIMIT 1
            """, (equipo['serie'], str(anio), str(mes).zfill(2)))
            
            report_row = c.fetchone()
            if report_row:
                equipo["estatus_servicio"] = "REALIZADO"
                equipo["folio_servicio"] = report_row[0]  # For clickable link
            else:
                equipo["estatus_servicio"] = "PENDIENTE"
                equipo["folio_servicio"] = None
            
            equipos.append(equipo)
    
    conn.close()
    return jsonify(equipos)




if __name__ == "__main__":

    import os
    port = int(os.environ.get("PORT", 5000))

    app.run(host="0.0.0.0", port=port, debug=True)

