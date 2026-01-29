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

# --- 2. CONEXIÓN A GOOGLE SHEETS ---
NOMBRE_HOJA = "DB_GestorFlota"

def conectar_google_sheets():
    """Conecta a Google Sheets usando los secretos de Streamlit Cloud."""
    try:
        # Intenta usar secretos de la nube, si falla (local), usa archivo json si existe
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            gc = gspread.service_account_from_dict(creds_dict)
            return gc.open(NOMBRE_HOJA)
        else:
            # Fallback para desarrollo local si tienes el json
            gc = gspread.service_account("datos_sistema.json") # Asegúrate de tener el json si corres local
            return gc.open(NOMBRE_HOJA)
    except Exception as e:
        return None

def cargar_datos_db():
    """Carga configuración, contraseña y datos."""
    datos = {
        "averiadas": [],
        "rango_min": 1,
        "rango_max": 500,
        "estaciones": ["bp", "Texaco", "Cartonera Petare"],
        "password": "admin" # Contraseña de respaldo por si falla la conexión
    }
    
    sh = conectar_google_sheets()
    if not sh: return datos

    try:
        # 1. Cargar Configuración y PASSWORD (Pestaña 'Config')
        ws_config = sh.worksheet("Config")
        vals_config = ws_config.get_all_values()
        
        # Esperamos estructura: 
        # Fila 1: Min | 1
        # Fila 2: Max | 500
        # Fila 3: Password | TuClave
        
        if len(vals_config) >= 1:
            datos["rango_min"] = int(vals_config[0][1]) if len(vals_config[0]) > 1 else 1
        if len(vals_config) >= 2:
            datos["rango_max"] = int(vals_config[1][1]) if len(vals_config[1]) > 1 else 500
        if len(vals_config) >= 3:
            # AQUÍ TOMAMOS LA CONTRASEÑA DE LA NUBE
            datos["password"] = vals_config[2][1] if len(vals_config[2]) > 1 else "admin"
        
        # 2. Cargar Estaciones
        try:
            ws_est = sh.worksheet("Estaciones")
            lista_est = ws_est.col_values(1)
            if lista_est: datos["estaciones"] = lista_est
        except: pass
            
        # 3. Cargar Averiadas
        try:
            ws_av = sh.worksheet("Averiadas")
            lista_av = ws_av.col_values(1)
            if lista_av: datos["averiadas"] = [int(x) for x in lista_av if x.isdigit()]
        except: pass
            
        return datos
    except Exception as e:
        return datos

def guardar_datos_db(datos):
    """Guarda cambios en la nube."""
    sh = conectar_google_sheets()
    if not sh: return

    try:
        # Guardar Config (Incluyendo mantener la contraseña que ya estaba)
        ws_config = sh.worksheet("Config")
        ws_config.clear()
        # Reescribimos las 3 filas para no perder la clave
        ws_config.update('A1', [
            ['Min', datos["rango_min"]], 
            ['Max', datos["rango_max"]],
            ['Password', datos["password"]]
        ])
        
        # Guardar Estaciones
        ws_est = sh.worksheet("Estaciones")
        ws_est.clear()
        if datos["estaciones"]:
            ws_est.update('A1', [[e] for e in datos["estaciones"]])
            
        # Guardar Averiadas
        ws_av = sh.worksheet("Averiadas")
        ws_av.clear()
        if datos["averiadas"]:
            ws_av.update('A1', [[str(a)] for a in datos["averiadas"]])
            
    except Exception as e:
        st.error(f"Error guardando: {e}")

# --- 3. CARGA DE DATOS (ANTES DEL LOGIN) ---
# Necesitamos cargar los datos AHORA para saber cuál es la contraseña real
if 'datos_app' not in st.session_state:
    with st.spinner("Conectando con base de datos segura..."):
        st.session_state.datos_app = cargar_datos_db()

# Wrapper para guardar
def guardar_datos(datos):
    guardar_datos_db(datos)


# --- 4. SISTEMA DE LOGIN SEGURO ---
def verificar_login():
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🔒 Acceso Seguro")
            st.markdown("Gestor de Flota v2.0")
            
            # Obtenemos la contraseña real desde los datos cargados
            password_real = st.session_state.datos_app.get("password", "admin")
            
            password_input = st.text_input("Contraseña de acceso", type="password")
            
            if st.button("Iniciar Sesión", type="primary", use_container_width=True):
                # Comparamos lo que escribió el usuario con lo que bajamos de Sheets
                if password_input == password_real:
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta.")
        return False
    return True

# --- 5. RECURSOS GRÁFICOS ---
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

def generar_imagen_en_memoria(reporte_lista, fecha_dt, rango_txt):
    ANCHO = 600
    COLOR_FONDO = "#ECE5DD" 
    try:
        font_titulo = ImageFont.truetype("arial.ttf", 28)
        font_normal = ImageFont.truetype("arial.ttf", 22)
        font_bold = ImageFont.truetype("arialbd.ttf", 22)
    except IOError:
        font_titulo = ImageFont.load_default()
        font_normal = ImageFont.load_default()
        font_bold = ImageFont.load_default()

    img = Image.new('RGB', (ANCHO, 2000), color=COLOR_FONDO)
    draw = ImageDraw.Draw(img)
    y = 30; margen = 30; ancho_texto = ANCHO - (margen * 2)

    dias = {0:"lunes",1:"martes",2:"miércoles",3:"jueves",4:"viernes",5:"sábado",6:"domingo"}
    fecha_str = f"{dias[fecha_dt.weekday()]} {fecha_dt.strftime('%d/%m/%y')}"
    
    titulo1 = "Reporte de Estaciones de"
    bbox = draw.textbbox((0, 0), titulo1, font=font_titulo)
    w_t1 = bbox[2] - bbox[0]
    draw.rectangle([(ANCHO/2 - w_t1/2 - 10, y), (ANCHO/2 + w_t1/2 + 10, y + 35)], fill="#d1e7dd")
    draw.text((ANCHO/2 - w_t1/2, y), titulo1, font=font_titulo, fill="black")
    y += 40
    
    titulo2 = f"Servicio y Unidades {fecha_str}"
    bbox2 = draw.textbbox((0, 0), titulo2, font=font_titulo)
    w_t2 = bbox2[2] - bbox2[0]
    draw.rectangle([(ANCHO/2 - w_t2/2 - 10, y), (ANCHO/2 + w_t2/2 + 10, y + 35)], fill="#d1e7dd")
    draw.text((ANCHO/2 - w_t2/2, y), titulo2, font=font_titulo, fill="black")
    y += 50
    
    icono = obtener_icono_bomba()
    if icono:
        cantidad = 5; ancho_icon = icono.width; espacio = 5
        total_w = (ancho_icon * cantidad) + (espacio * (cantidad - 1))
        start_x = (ANCHO - total_w) / 2
        for i in range(cantidad):
            pos_x = int(start_x + (i * (ancho_icon + espacio)))
            img.paste(icono, (pos_x, y), icono)
        y += 50
    else:
        draw.text((ANCHO/2 - 60, y), "⛽⛽⛽⛽⛽", font=font_normal, fill="red")
        y += 40

    colores = ["#f8d7da", "#fff3cd", "#d1e7dd"] 
    for i, est in enumerate(reporte_lista):
        color = colores[i % 3]
        txt_st = f"• Estación {est['nombre']}: {est['horario']}"
        bbox_st = draw.textbbox((0, 0), txt_st, font=font_bold)
        draw.rectangle([(margen, y), (margen + bbox_st[2] - bbox_st[0] + 10, y + 30)], fill=color)
        draw.text((margen + 5, y + 2), txt_st, font=font_bold, fill="black")
        y += 35
        
        numeros = " ".join(map(str, est['unidades']))
        palabras = numeros.split(); linea = ""
        for p in palabras:
            prueba = linea + p + " "
            if draw.textbbox((0, 0), prueba, font=font_normal)[2] > ancho_texto:
                draw.text((margen, y), linea, font=font_normal, fill="black")
                y += 28; linea = p + " "
            else: linea = prueba
        if linea:
            draw.text((margen, y), linea, font=font_normal, fill="black"); y += 45 

    txt_ran = "• Rango de unidades"
    bbox_r = draw.textbbox((0, 0), txt_ran, font=font_bold)
    draw.rectangle([(margen, y), (margen + bbox_r[2] - bbox_r[0] + 10, y + 30)], fill="#cff4fc") 
    draw.text((margen + 5, y + 2), txt_ran, font=font_bold, fill="black")
    y += 35
    draw.text((margen, y), rango_txt, font=font_normal, fill="black"); y += 50

    img_final = img.crop((0, 0, ANCHO, y))
    buffer = BytesIO()
    img_final.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# =========================================================
# LOGICA PRINCIPAL
# =========================================================

# Solo si pasa el login, mostramos la app
if verificar_login():
    
    with st.sidebar:
        st.success("☁️ Conectado")
        if st.button("Cerrar Sesión", type="secondary"):
            st.session_state.autenticado = False
            st.rerun()
        st.divider()
    
    tab_asignacion, tab_flota, tab_config = st.tabs(["⛽ Asignación Diaria", "🔧 Gestión de Flota", "⚙️ Configuración"])

    rango_min_val = st.session_state.datos_app.get("rango_min", 1)
    rango_max_val = st.session_state.datos_app.get("rango_max", 500)
    todas_las_unidades = list(range(rango_min_val, rango_max_val + 1))

    # --- CONFIGURACIÓN ---
    with tab_config:
        st.header("⚙️ Configuración")
        c1, c2 = st.columns(2)
        nuevo_min = c1.number_input("Inicial", value=rango_min_val, min_value=1)
        nuevo_max = c2.number_input("Final", value=rango_max_val, min_value=1)
        if st.button("💾 Guardar Cambios"):
            st.session_state.datos_app["rango_min"] = nuevo_min
            st.session_state.datos_app["rango_max"] = nuevo_max
            guardar_datos(st.session_state.datos_app)
            st.success("Configuración actualizada en la nube.")
            st.rerun()

        st.subheader("Estaciones")
        nueva = st.text_input("Nueva estación:")
        if st.button("➕ Agregar"):
            if nueva and nueva not in st.session_state.datos_app["estaciones"]:
                st.session_state.datos_app["estaciones"].append(nueva)
                guardar_datos(st.session_state.datos_app)
                st.rerun()
        
        estaciones_actuales = st.session_state.datos_app.get("estaciones", [])
        if estaciones_actuales:
            for n in estaciones_actuales:
                c_a, c_b = st.columns([4,1])
                c_a.text(f"⛽ {n}")
                if c_b.button("❌", key=f"del_{n}"):
                    st.session_state.datos_app["estaciones"].remove(n)
                    guardar_datos(st.session_state.datos_app)
                    st.rerun()

    # --- TALLER ---
    with tab_flota:
        st.header("🔧 Taller")
        averiadas = st.session_state.datos_app.get("averiadas", [])
        sanas = [u for u in todas_las_unidades if u not in averiadas]
        
        c_add1, c_add2 = st.columns([3, 1], vertical_alignment="bottom")
        nuevas = c_add1.multiselect("Enviar a taller:", sanas)
        if c_add2.button("🔴 Reportar", use_container_width=True):
            if nuevas:
                st.session_state.datos_app["averiadas"].extend(nuevas)
                st.session_state.datos_app["averiadas"].sort()
                guardar_datos(st.session_state.datos_app)
                st.rerun()
        
        st.divider()
        if averiadas:
            st.info("Clic para reparar:")
            cols = st.columns(6)
            for i, u in enumerate(averiadas):
                if cols[i % 6].button(f"🚍 {u} 🔧", key=f"fix_{u}", use_container_width=True):
                    st.session_state.datos_app["averiadas"].remove(u)
                    guardar_datos(st.session_state.datos_app)
                    st.rerun()
        else: st.success("Flota operativa.")

    # --- ASIGNACIÓN ---
    with tab_asignacion:
        if 'editando_idx' not in st.session_state: st.session_state.editando_idx = None
        
        cf1, cf2 = st.columns([1, 3], vertical_alignment="bottom")
        fecha_rep = cf1.date_input("📅 Fecha", datetime.now())
        cf2.info(f"Reporte: **{fecha_rep.strftime('%d/%m/%Y')}**")
        st.divider()
        
        averiadas = st.session_state.datos_app.get("averiadas", [])
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
                nombres = st.session_state.datos_app.get("estaciones", [])
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
            st.subheader("Resumen de Asignaciones")
            for i, est in enumerate(st.session_state.reporte_diario):
                with st.container(border=True):
                    c_head1, c_head2 = st.columns([0.65, 0.35], vertical_alignment="center")
                    with c_head1:
                        st.markdown(f"#### ⛽ {est['nombre']}")
                        st.caption(f"🕒 {est['horario']}")
                    with c_head2:
                        ce1, ce2 = st.columns(2)
                        if ce1.button("✏️", key=f"edit_btn_{i}", help="Editar", use_container_width=True):
                            st.session_state.editando_idx = i if st.session_state.editando_idx != i else None
                            st.rerun()
                        if ce2.button("🗑️", key=f"del_all_{i}", help="Borrar todo", use_container_width=True):
                            st.session_state.reporte_diario.pop(i)
                            st.session_state.editando_idx = None 
                            st.rerun()
                    unidades_lista = est['unidades']
                    if st.session_state.editando_idx == i:
                        st.info("Toca una unidad para eliminarla:")
                        if unidades_lista:
                            cols = st.columns(4) 
                            for idx_u, u in enumerate(unidades_lista):
                                if cols[idx_u % 4].button(f"❌ {u}", key=f"del_u_{i}_{u}", use_container_width=True):
                                    est['unidades'].remove(u)
                                    st.rerun()
                        else: st.warning("Sin unidades.")
                        if st.button("✅ Terminar", key=f"close_{i}", use_container_width=True):
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
                        else: st.caption("Sin unidades.")

            st.divider()
            st.subheader("🖼️ Imagen Final")
            texto_rango_default = f"Unidades desde la {rango_min_val} a {rango_max_val}"
            rango_manual = st.text_input("Texto del Rango Final:", value=texto_rango_default)

            if st.button("📸 GENERAR IMAGEN", type="primary", use_container_width=True):
                 with st.spinner("Generando..."):
                     st.session_state.imagen_en_memoria = generar_imagen_en_memoria(st.session_state.reporte_diario, fecha_rep, rango_manual)
            
            if 'imagen_en_memoria' in st.session_state:
                st.image(st.session_state.imagen_en_memoria)
                st.download_button("📥 Descargar Imagen", st.session_state.imagen_en_memoria, f"Reporte_{fecha_rep.strftime('%d-%m-%y')}.png", "image/png", use_container_width=True)