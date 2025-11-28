# app.py
import os, io, json, base64, math
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.utils import ImageReader
from PIL import Image

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
    return redirect(url_for("login") if "user" not in session else url_for("formulario"))

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        user = request.form.get("username","").strip().lower()
        pw = request.form.get("password","").strip()
        usuarios = cargar_usuarios()
        if user in usuarios and usuarios[user]["password"] == pw:
            session["user"] = user
            session["user_nombre"] = usuarios[user]["nombre"]
            session["prefijo"] = usuarios[user]["prefijo"]
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
        session["folio_actual"] = generar_siguiente_folio(session["prefijo"])

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
    session["folio_actual"] = generar_siguiente_folio(session["prefijo"])
    return redirect(url_for("formulario"))


# ------------------ util texto/medidas ------------------
def _text_or_na(v):
    v = (v or "").strip()
    return v if v else "N/A"

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
        if ffile and ffile.filename:
            path = os.path.join(UPLOAD_DIR, f"{folio}_foto{i}.png")
            ffile.save(path)
            desc = _text_or_na(request.form.get(f"foto{i}_desc"))
            fotos.append((path, desc))

    # firmas
    firma_tecnico_nombre = _text_or_na(request.form.get("firma_tecnico_nombre"))
    firma_cliente_nombre = _text_or_na(request.form.get("firma_cliente_nombre"))
    firma_tecnico_path = _save_signature_png(request.form.get("firma_tecnico_data"), f"{folio}_firma_tecnico.png")
    firma_cliente_path = _save_signature_png(request.form.get("firma_cliente_data"), f"{folio}_firma_cliente.png")

    # actividades (para compresor estándar; en secador tú ya estás imprimiendo otras actividades)
    analisis_ruido_marcado = bool(request.form.get("act_analisis_ruido"))
    actividades = []
    for idx, nombre in enumerate(ACTIVIDADES_SENTENCE, start=1):
        marcado = bool(request.form.get(f"act_{idx}"))
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
        rows = actividades[:]
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
                left_x2 = inner_x; colw0 = 3.4*cm; colw = 1.45*cm; rh = 0.68*cm
                c.setFont("Helvetica-Bold", 8); c.setStrokeColorRGB(0.7,0.7,0.7)
                c.rect(left_x2, yr-rh, colw0 + 10*colw, rh, fill=0, stroke=1)
                c.drawString(left_x2+2, yr-rh+3, "ANÁLISIS DE RUIDO EN RODAMIENTOS (SPM)")
                yline = yr - rh; x = left_x2 + colw0
                c.setFont("Helvetica-Bold", 7.2)
                for h in headers[1:]:
                    c.rect(x, yline-rh, colw, rh, fill=0, stroke=1); c.drawString(x+2, yline-rh+3, h); x += colw
                yy2 = yline - rh; c.setFont("Helvetica", 7.0)
                cols = ["mbrg","bg","lpmi_mri","lpm2_mr2","hpm1","hpm2","hpf1","hpf2","lpf1","lpf2"]
                for lbl, key in row_defs:
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
        row_h = 0.52*cm
        need = 18 + len(labels)*row_h + 0.7*cm
        y = _ensure_space(c, y, need, folio, fecha, tecnico, localidad)
        yt = _draw_section(c, title, y, need)
        c.setFont("Helvetica-Bold", 8.7)
        lab_w = 10.8*cm
        val_w = inner_w - lab_w
        yline = yt - 0.25*cm
        c.setFont("Helvetica", 8.7)
        for i,(lab,val) in enumerate(zip(labels, values)):
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
        need = 18 + (len(e3_rows)+len(e1_rows))*row_h + 0.9*cm
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
        for titulo, key in e3_rows:
            c.rect(x0, yline-row_h, lab_w, row_h, fill=0, stroke=1)
            c.drawString(x0+2, yline-row_h+3, titulo)

            fases = ("l12","l23","l31") if key in ("v_carga", "v_descarga") else ("l1","l2","l3")
            for j, ph in enumerate(fases):
                val = e3_vals_map.get(f"{key}_{ph}", "N/A")
                c.rect(x0+lab_w+j*cell, yline-row_h, cell, row_h, fill=0, stroke=1)
                c.drawString(x0+lab_w+j*cell+2, yline-row_h+3, val)
            yline -= row_h

        # Individuales
        for titulo, key in e1_rows:
            c.rect(x0, yline-row_h, lab_w+3*cell, row_h, fill=0, stroke=1)
            c.drawString(x0+2, yline-row_h+3, titulo)
            c.setFont("Helvetica-Bold", 8.6)
            c.drawRightString(x0+lab_w+3*cell-4, yline-row_h+3, e1_vals_map.get(key, "N/A"))
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

    # --- cerrar el PDF y descargar directo al teléfono/PC ---
    c.showPage(); c.save(); buf.seek(0)
    pdf_bytes = buf.read()
    nombre_pdf = f"REPORTE_{tipo_servicio.upper()}_{cliente.replace(' ', '_')}.pdf"

    # limpiar folio de la sesión
    session.pop("folio_actual", None)

    # Enviar archivo directamente (descarga inmediata)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=nombre_pdf
    )

# === API: crear un nuevo folio y dejarlo en la sesión ===
@app.route("/api/nuevo_folio", methods=["POST"])
def api_nuevo_folio():
    if "user" not in session:
        return ("", 401)
    session["folio_actual"] = generar_siguiente_folio(session["prefijo"])
    return {"folio": session["folio_actual"]}

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
