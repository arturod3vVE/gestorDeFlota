import streamlit as st
from datetime import datetime
import json
import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import gspread

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Gestor de Flota", page_icon="⛽", layout="wide")

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stApp { margin-top: -60px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CONEXIÓN A GOOGLE SHEETS ---
NOMBRE_HOJA = "DB_GestorFlota"

def conectar_google_sheets():
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            gc = gspread.service_account_from_dict(creds_dict)
            return gc.open(NOMBRE_HOJA)
        else:
            gc = gspread.service_account("datos_sistema.json")
            return gc.open(NOMBRE_HOJA)
    except Exception as e:
        return None

def cargar_datos_db():
    datos = {
        "averiadas": [],
        "rango_min": 1,
        "rango_max": 500,
        "estaciones": ["bp", "Texaco", "Cartonera Petare"],
        "password": "admin",
        "font_size": 24,
        "img_width": 450
    }
    
    sh = conectar_google_sheets()
    if not sh: return datos

    try:
        ws_config = sh.worksheet("Config")
        vals_config = ws_config.get_all_values()
        
        if len(vals_config) >= 1: datos["rango_min"] = int(vals_config[0][1])
        if len(vals_config) >= 2: datos["rango_max"] = int(vals_config[1][1])
        if len(vals_config) >= 3: datos["password"] = vals_config[2][1]
        if len(vals_config) >= 4: datos["font_size"] = int(vals_config[3][1])
        if len(vals_config) >= 5: datos["img_width"] = int(vals_config[4][1])
        
        try:
            ws_est = sh.worksheet("Estaciones")
            lista_est = ws_est.col_values(1)
            if lista_est: datos["estaciones"] = lista_est
        except: pass
            
        try:
            ws_av = sh.worksheet("Averiadas")
            lista_av = ws_av.col_values(1)
            if lista_av: datos["averiadas"] = [int(x) for x in lista_av if x.isdigit()]
        except: pass
            
        return datos
    except Exception as e:
        return datos

def guardar_datos_db(datos):
    sh = conectar_google_sheets()
    if not sh: return

    try:
        ws_config = sh.worksheet("Config")
        ws_config.clear()
        ws_config.update('A1', [
            ['Min', datos["rango_min"]], 
            ['Max', datos["rango_max"]],
            ['Password', datos["password"]],
            ['FontSize', datos["font_size"]],
            ['ImgWidth', datos["img_width"]]
        ])
        
        ws_est = sh.worksheet("Estaciones")
        ws_est.clear()
        if datos["estaciones"]:
            ws_est.update('A1', [[e] for e in datos["estaciones"]])
            
        ws_av = sh.worksheet("Averiadas")
        ws_av.clear()
        if datos["averiadas"]:
            ws_av.update('A1', [[str(a)] for a in datos["averiadas"]])
            
    except Exception as e:
        st.error(f"Error guardando: {e}")

if 'datos_app' not in st.session_state:
    with st.spinner("Cargando sistema..."):
        st.session_state.datos_app = cargar_datos_db()

def guardar_datos(datos):
    guardar_datos_db(datos)

# --- 3. LOGIN ---
def verificar_login():
    if 'autenticado' not in st.session_state: st.session_state.autenticado = False
    if not st.session_state.autenticado:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🔒 Acceso Seguro")
            password_real = st.session_state.datos_app.get("password", "admin")
            password_input = st.text_input("Contraseña", type="password")
            if st.button("Entrar", type="primary", use_container_width=True):
                if password_input == password_real:
                    st.session_state.autenticado = True
                    st.rerun()
                else: st.error("Incorrecto")
        return False
    return True

# --- 4. RECURSOS GRÁFICOS ---
ICONO_BOMBA = "icono_bomba.png"
def obtener_icono_bomba():
    if not os.path.exists(ICONO_BOMBA):
        try:
            url = "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/26fd.png"
            response = requests.get(url)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content)).convert("RGBA")
                img = img.resize((40, 40))
                img.save(ICONO_BOMBA)
                return img
        except: return None
    else:
        try: return Image.open(ICONO_BOMBA).convert("RGBA")
        except: return None
    return None

# --- 5. GENERADOR DE IMAGEN (CON CEROS A LA IZQUIERDA) ---
def generar_imagen_en_memoria(reporte_lista, fecha_dt, rango_txt, config_datos):
    ANCHO = config_datos.get("img_width", 450)
    BASE_FONT_SIZE = config_datos.get("font_size", 24)
    
    LINE_HEIGHT_NORMAL = int(BASE_FONT_SIZE * 1.3)
    ESPACIO_BLOQUES = int(BASE_FONT_SIZE * 1.5)
    
    COLOR_FONDO = "#ECE5DD" 
    try:
        font_titulo = ImageFont.truetype("arial.ttf", BASE_FONT_SIZE + 4)
        font_normal = ImageFont.truetype("arial.ttf", BASE_FONT_SIZE)
        font_bold = ImageFont.truetype("arialbd.ttf", BASE_FONT_SIZE)
    except IOError:
        font_titulo = ImageFont.load_default()
        font_normal = ImageFont.load_default()
        font_bold = ImageFont.load_default()

    img = Image.new('RGB', (ANCHO, 3000), color=COLOR_FONDO)
    draw = ImageDraw.Draw(img)
    
    y = 40
    margen = 20
    ancho_util = ANCHO - (margen * 2)

    def dibujar_titulo_centrado(texto, y_pos, fuente, color_bg="#d1e7dd"):
        palabras = texto.split()
        lineas = []
        linea_actual = ""
        for palabra in palabras:
            prueba = linea_actual + palabra + " "
            w_prueba = draw.textbbox((0, 0), prueba, font=fuente)[2]
            if w_prueba > ancho_util:
                lineas.append(linea_actual)
                linea_actual = palabra + " "
            else:
                linea_actual = prueba
        if linea_actual: lineas.append(linea_actual)
        
        for linea in lineas:
            bbox = draw.textbbox((0, 0), linea, font=fuente)
            w_linea = bbox[2] - bbox[0]
            draw.rectangle([(ANCHO/2 - w_linea/2 - 10, y_pos), (ANCHO/2 + w_linea/2 + 10, y_pos + LINE_HEIGHT_NORMAL + 5)], fill=color_bg)
            draw.text((ANCHO/2 - w_linea/2, y_pos), linea, font=fuente, fill="black")
            y_pos += int(LINE_HEIGHT_NORMAL * 1.4)
        return y_pos + 10

    dias = {0:"lunes",1:"martes",2:"miércoles",3:"jueves",4:"viernes",5:"sábado",6:"domingo"}
    fecha_str = f"{dias[fecha_dt.weekday()]} {fecha_dt.strftime('%d/%m/%y')}"
    
    y = dibujar_titulo_centrado("Reporte de Estaciones de", y, font_titulo)
    y = dibujar_titulo_centrado(f"Servicio y Unidades {fecha_str}", y, font_titulo)
    
    icono = obtener_icono_bomba()
    if icono:
        nuevo_size = int(BASE_FONT_SIZE * 1.5)
        icono_res = icono.resize((nuevo_size, nuevo_size))
        cantidad = 5
        espacio = 8
        total_w = (nuevo_size * cantidad) + (espacio * (cantidad - 1))
        if total_w > ancho_util: cantidad = 3; total_w = (nuevo_size * cantidad) + (espacio * (cantidad - 1))
        start_x = (ANCHO - total_w) / 2
        for i in range(cantidad):
            pos_x = int(start_x + (i * (nuevo_size + espacio)))
            img.paste(icono_res, (pos_x, y), icono_res)
        y += int(nuevo_size * 1.5)
    else:
        y += LINE_HEIGHT_NORMAL

    colores = ["#f8d7da", "#fff3cd", "#d1e7dd"] 
    for i, est in enumerate(reporte_lista):
        color = colores[i % 3]
        txt_st = f"• Estación {est['nombre']}: {est['horario']}"
        palabras_titulo = txt_st.split()
        linea_t = ""
        for pt in palabras_titulo:
            prueba_t = linea_t + pt + " "
            if draw.textbbox((0, 0), prueba_t, font=font_bold)[2] > ancho_util:
                bbox_bg = draw.textbbox((0, 0), linea_t, font=font_bold)
                draw.rectangle([(margen, y), (margen + bbox_bg[2] + 10, y + LINE_HEIGHT_NORMAL + 4)], fill=color)
                draw.text((margen + 5, y + 2), linea_t, font=font_bold, fill="black")
                y += int(LINE_HEIGHT_NORMAL * 1.1)
                linea_t = pt + " "
            else: linea_t = prueba_t
        if linea_t:
            bbox_bg = draw.textbbox((0, 0), linea_t, font=font_bold)
            draw.rectangle([(margen, y), (margen + bbox_bg[2] + 10, y + LINE_HEIGHT_NORMAL + 4)], fill=color)
            draw.text((margen + 5, y + 2), linea_t, font=font_bold, fill="black")
            y += int(LINE_HEIGHT_NORMAL * 1.2)
        
        # --- CAMBIO AQUÍ: Formato con ceros a la izquierda ---
        # Usamos f-strings: f"{u:02d}" significa "formatea 'u' con al menos 2 dígitos, rellenando con ceros"
        numeros = " ".join([f"{u:02d}" for u in est['unidades']])
        
        palabras = numeros.split()
        linea = ""
        for p in palabras:
            prueba = linea + p + " "
            if draw.textbbox((0, 0), prueba, font=font_normal)[2] > ancho_util:
                draw.text((margen, y), linea, font=font_normal, fill="black")
                y += LINE_HEIGHT_NORMAL 
                linea = p + " "
            else: linea = prueba
        if linea:
            draw.text((margen, y), linea, font=font_normal, fill="black")
            y += ESPACIO_BLOQUES

    txt_ran = "• Rango de unidades"
    bbox_r = draw.textbbox((0, 0), txt_ran, font=font_bold)
    draw.rectangle([(margen, y), (margen + bbox_r[2] - bbox_r[0] + 10, y + LINE_HEIGHT_NORMAL + 4)], fill="#cff4fc") 
    draw.text((margen + 5, y + 2), txt_ran, font=font_bold, fill="black")
    y += int(LINE_HEIGHT_NORMAL * 1.2)
    
    palabras_r = rango_txt.split()
    linea_r = ""
    for pr in palabras_r:
        prueba_r = linea_r + pr + " "
        if draw.textbbox((0, 0), prueba_r, font=font_normal)[2] > ancho_util:
            draw.text((margen, y), linea_r, font=font_normal, fill="black")
            y += LINE_HEIGHT_NORMAL
            linea_r = pr + " "
        else: linea_r = prueba_r
    if linea_r:
        draw.text((margen, y), linea_r, font=font_normal, fill="black")
        y += ESPACIO_BLOQUES

    img_final = img.crop((0, 0, ANCHO, y + 20))
    buffer = BytesIO()
    img_final.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# =========================================================
# LÓGICA PRINCIPAL
# =========================================================

if verificar_login():
    with st.sidebar:
        st.success("Conectado")
        if st.button("Salir", type="secondary"):
            st.session_state.autenticado = False
            st.rerun()
    
    tab_asignacion, tab_flota, tab_config = st.tabs(["⛽ Asignación", "🔧 Taller", "⚙️ Configuración"])

    datos = st.session_state.datos_app
    todas_las_unidades = list(range(datos.get("rango_min", 1), datos.get("rango_max", 500) + 1))

    # --- CONFIGURACIÓN ---
    with tab_config:
        st.header("⚙️ Ajustes")
        st.subheader("1. Rangos")
        c1, c2 = st.columns(2)
        nuevo_min = c1.number_input("Inicial", value=datos.get("rango_min", 1), min_value=1)
        nuevo_max = c2.number_input("Final", value=datos.get("rango_max", 500), min_value=1)
        
        st.divider()
        st.subheader("2. Imagen")
        c3, c4 = st.columns(2)
        nuevo_ancho = c3.slider("Ancho (px)", 300, 800, value=datos.get("img_width", 450))
        nueva_fuente = c4.slider("Tamaño Letra", 14, 40, value=datos.get("font_size", 24))
        
        if st.button("💾 Guardar Configuración", type="primary"):
            datos["rango_min"] = nuevo_min
            datos["rango_max"] = nuevo_max
            datos["img_width"] = nuevo_ancho
            datos["font_size"] = nueva_fuente
            guardar_datos(datos)
            st.success("Guardado.")
            st.rerun()

        st.divider()
        st.subheader("3. Estaciones")
        nueva = st.text_input("Nueva estación:")
        if st.button("➕ Agregar"):
            if nueva and nueva not in datos.get("estaciones", []):
                datos.setdefault("estaciones", []).append(nueva)
                guardar_datos(datos)
                st.rerun()
        
        ests = datos.get("estaciones", [])
        if ests:
            for n in ests:
                c_a, c_b = st.columns([4,1])
                c_a.text(f"⛽ {n}")
                if c_b.button("❌", key=f"del_{n}"):
                    datos["estaciones"].remove(n)
                    guardar_datos(datos)
                    st.rerun()

    # --- TALLER ---
    with tab_flota:
        st.header("🔧 Taller")
        averiadas = datos.get("averiadas", [])
        sanas = [u for u in todas_las_unidades if u not in averiadas]
        
        c_add1, c_add2 = st.columns([3, 1], vertical_alignment="bottom")
        nuevas = c_add1.multiselect("Enviar a taller:", sanas)
        if c_add2.button("🔴 Reportar", use_container_width=True):
            if nuevas:
                datos.setdefault("averiadas", []).extend(nuevas)
                datos["averiadas"].sort()
                guardar_datos(datos)
                st.rerun()
        
        st.divider()
        if averiadas:
            st.info("Clic para reparar:")
            cols = st.columns(6)
            for i, u in enumerate(averiadas):
                if cols[i % 6].button(f"🚍 {u}", key=f"fix_{u}", use_container_width=True):
                    datos["averiadas"].remove(u)
                    guardar_datos(datos)
                    st.rerun()
        else: st.success("Flota operativa.")

    # --- ASIGNACIÓN ---
    with tab_asignacion:
        if 'editando_idx' not in st.session_state: st.session_state.editando_idx = None
        
        cf1, cf2 = st.columns([1, 3], vertical_alignment="bottom")
        fecha_rep = cf1.date_input("📅 Fecha", datetime.now())
        cf2.info(f"Reporte: **{fecha_rep.strftime('%d/%m/%Y')}**")
        st.divider()
        
        averiadas = datos.get("averiadas", [])
        unidades_op = [u for u in todas_las_unidades if u not in averiadas]
        if 'reporte_diario' not in st.session_state: st.session_state.reporte_diario = []
        
        ya_asig = [u for est in st.session_state.reporte_diario for u in est['unidades']]
        disp = [u for u in unidades_op if u not in ya_asig]

        cm1, cm2, cm3 = st.columns(3)
        cm1.metric("Flota", len(todas_las_unidades))
        cm2.metric("Taller", len(averiadas))
        cm3.metric("Libres", len(disp))

        with st.expander("➕ Asignar Estación", expanded=True):
            with st.form("main_form"):
                ca, cb = st.columns([1, 2])
                nombres = datos.get("estaciones", [])
                nom = ca.selectbox("Estación", nombres) if nombres else ca.text_input("Nombre")
                ch1, ch2 = cb.columns(2)
                t1 = ch1.time_input("Abre", datetime.strptime("09:00", "%H:%M").time())
                t2 = ch2.time_input("Cierra", datetime.strptime("14:00", "%H:%M").time())
                sel = st.multiselect("Unidades:", disp)
                if st.form_submit_button("Guardar", type="primary", use_container_width=True):
                    if nom and sel:
                        hora = f"{t1.strftime('%I:%M%p').lstrip('0')} a {t2.strftime('%I:%M%p').lstrip('0')}"
                        st.session_state.reporte_diario.append({"nombre": nom, "horario": hora, "unidades": sorted(sel)})
                        st.rerun()
                    else: st.error("Faltan datos")

        if st.session_state.reporte_diario:
            st.divider()
            st.subheader("Resumen")
            for i, est in enumerate(st.session_state.reporte_diario):
                with st.container(border=True):
                    c_head1, c_head2 = st.columns([0.65, 0.35], vertical_alignment="center")
                    with c_head1:
                        st.markdown(f"#### ⛽ {est['nombre']}")
                        st.caption(f"🕒 {est['horario']}")
                    with c_head2:
                        ce1, ce2 = st.columns(2)
                        if ce1.button("✏️", key=f"edit_btn_{i}", use_container_width=True):
                            st.session_state.editando_idx = i if st.session_state.editando_idx != i else None
                            st.rerun()
                        if ce2.button("🗑️", key=f"del_all_{i}", use_container_width=True):
                            st.session_state.reporte_diario.pop(i)
                            st.session_state.editando_idx = None 
                            st.rerun()
                    
                    unidades_lista = est['unidades']
                    
                    if st.session_state.editando_idx == i:
                        st.info("Editando lista de unidades:")
                        if unidades_lista:
                            st.caption("Toca para eliminar:")
                            cols = st.columns(4) 
                            for idx_u, u in enumerate(unidades_lista):
                                if cols[idx_u % 4].button(f"❌ {u}", key=f"del_u_{i}_{u}", use_container_width=True):
                                    est['unidades'].remove(u)
                                    st.rerun()
                        else: st.warning("Lista vacía.")
                        st.divider()
                        
                        otros_asignados = []
                        for idx_req, req in enumerate(st.session_state.reporte_diario):
                            if idx_req != i: otros_asignados.extend(req['unidades'])
                        candidatas = [u for u in unidades_op if u not in otros_asignados and u not in unidades_lista]
                        
                        col_new1, col_new2 = st.columns([3, 1], vertical_alignment="bottom")
                        nuevas_agregar = col_new1.multiselect("Agregar extra:", candidatas, key=f"add_u_{i}", placeholder="Selecciona...")
                        if col_new2.button("➕ Sumar", key=f"btn_add_{i}", use_container_width=True):
                            if nuevas_agregar:
                                est['unidades'].extend(nuevas_agregar)
                                est['unidades'].sort()
                                st.rerun()

                        st.divider()
                        if st.button("✅ Terminar Edición", key=f"close_{i}", use_container_width=True):
                            st.session_state.editando_idx = None
                            st.rerun()
                            
                    else:
                        if unidades_lista:
                            estilo_flex = "display: flex; flex-wrap: wrap; gap: 8px; align-items: center;"
                            estilo_ficha = "background-color: #f0f2f6; color: #31333F; padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 15px; border: 1px solid #d0d0d0; box-shadow: 0 1px 2px rgba(0,0,0,0.05);"
                            html_badges = f'<div style="{estilo_flex}">'
                            for u in unidades_lista: html_badges += f'<div style="{estilo_ficha}">🚍 {u}</div>'
                            html_badges += "</div>"
                            st.markdown(html_badges, unsafe_allow_html=True)
                        else: st.caption("Vacío")

            st.divider()
            st.subheader("🖼️ Imagen Final")
            txt_rango = st.text_input("Rango manual:", value=f"Unidades desde la {datos.get('rango_min',1)} a {datos.get('rango_max',500)}")

            if st.button("📸 GENERAR IMAGEN", type="primary", use_container_width=True):
                 with st.spinner("Generando..."):
                     st.session_state.img_mem = generar_imagen_en_memoria(st.session_state.reporte_diario, fecha_rep, txt_rango, datos)
            
            if 'img_mem' in st.session_state:
                st.image(st.session_state.img_mem, width=300)
                st.download_button("📥 Descargar", st.session_state.img_mem, f"Reporte.png", "image/png", use_container_width=True)