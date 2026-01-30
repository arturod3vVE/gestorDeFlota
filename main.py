import streamlit as st
from datetime import datetime
import json
import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import gspread
import re

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
    default_colors = ["#f8d7da", "#fff3cd", "#d1e7dd", "#cff4fc", "#e2e3e5", "#f0f2f6"]
    
    datos = {
        "averiadas": [],
        "rango_min": 1,
        "rango_max": 500,
        "estaciones": ["bp", "Texaco", "Cartonera Petare"],
        "password": "admin",
        "font_size": 24,
        "img_width": 450,
        "bg_color": "#ECE5DD",
        "st_colors": default_colors
    }
    
    sh = conectar_google_sheets()
    if not sh: return datos

    try:
        ws_config = sh.worksheet("Config")
        vals_config = ws_config.get_all_values()
        
        # Carga básica
        if len(vals_config) >= 1: datos["rango_min"] = int(vals_config[0][1])
        if len(vals_config) >= 2: datos["rango_max"] = int(vals_config[1][1])
        if len(vals_config) >= 3: datos["password"] = vals_config[2][1]
        if len(vals_config) >= 4: datos["font_size"] = int(vals_config[3][1])
        if len(vals_config) >= 5: datos["img_width"] = int(vals_config[4][1])
        
        # Carga de colores (Filas nuevas)
        if len(vals_config) >= 6 and len(vals_config[5]) > 1: 
            datos["bg_color"] = vals_config[5][1]
        
        loaded_st_colors = []
        for i in range(6):
            row_idx = 6 + i
            if len(vals_config) > row_idx and len(vals_config[row_idx]) > 1:
                 loaded_st_colors.append(vals_config[row_idx][1])
        if loaded_st_colors:
             while len(loaded_st_colors) < 6:
                 loaded_st_colors.append(default_colors[len(loaded_st_colors)])
             datos["st_colors"] = loaded_st_colors
        
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
        
        # Guardamos todo, incluyendo colores
        config_rows = [
            ['Min', datos["rango_min"]], 
            ['Max', datos["rango_max"]],
            ['Password', datos["password"]],
            ['FontSize', datos["font_size"]],
            ['ImgWidth', datos["img_width"]],
            ['BgColor', datos["bg_color"]]
        ]
        for i, col in enumerate(datos["st_colors"]):
             config_rows.append([f'StColor{i+1}', col])

        ws_config.update('A1', config_rows)
        
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
            st.title("🔒 Acceso")
            
            # --- CAMBIO CLAVE AQUÍ: Usamos st.form ---
            with st.form("login_form"):
                pwd = st.text_input("Contraseña", type="password")
                # El botón ahora es un submit_button, que reacciona al Enter
                submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
            
            if submitted:
                if pwd == st.session_state.datos_app.get("password", "admin"):
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta")
                    
        return False
    return True

# --- 4. RECURSOS GRÁFICOS (FUENTES Y TEXTO) ---
ICONO_BOMBA = "icono_bomba.png"
FONT_REGULAR = "Roboto-Regular.ttf"
FONT_BOLD = "Roboto-Bold.ttf"

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

def descargar_fuentes():
    # Descargamos Roboto para soporte de tildes
    urls = {
        FONT_REGULAR: "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf",
        FONT_BOLD: "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
    }
    for filename, url in urls.items():
        if not os.path.exists(filename):
            try:
                r = requests.get(url)
                with open(filename, 'wb') as f:
                    f.write(r.content)
            except: pass

def limpiar_texto(texto):
    # CORREGIDO: Agregamos '\/' para permitir la barra de la fecha
    # Elimina emojis, permite tildes, ñ y barras (/)
    return re.sub(r'[^\w\s\.,:;\-\(\)\/\u00C0-\u00FF]', '', str(texto))

# --- 5. GENERADOR DE IMAGEN (MEJORADO) ---
def generar_imagen_en_memoria(reporte_lista, fecha_dt, rango_txt, config_datos):
    # 1. Aseguramos tener las fuentes
    descargar_fuentes()
    
    ANCHO = config_datos.get("img_width", 450)
    FONT_S = config_datos.get("font_size", 24)
    BG = config_datos.get("bg_color", "#ECE5DD")
    PALETA = config_datos.get("st_colors", ["#f8d7da"])
    LH = int(FONT_S * 1.3); GAP = int(FONT_S * 1.5)
    
    # 2. Intentamos cargar la fuente descargada (Roboto), si falla, Arial, si falla, Default
    try:
        f_ti = ImageFont.truetype(FONT_BOLD, FONT_S + 4)
        f_no = ImageFont.truetype(FONT_REGULAR, FONT_S)
        f_bd = ImageFont.truetype(FONT_BOLD, FONT_S)
    except:
        try:
            f_ti = ImageFont.truetype("arial.ttf", FONT_S + 4)
            f_no = ImageFont.truetype("arial.ttf", FONT_S)
            f_bd = ImageFont.truetype("arialbd.ttf", FONT_S)
        except:
            f_ti = f_no = f_bd = ImageFont.load_default()

    img = Image.new('RGB', (ANCHO, 3000), color=BG)
    d = ImageDraw.Draw(img)
    y = 40; w_draw = ANCHO - 40

    def draw_centered(txt, y_pos, fnt, bg_col="#d1e7dd"):
        txt = limpiar_texto(txt) # Limpieza de emojis
        lines = []; cur = ""
        for w in txt.split():
            if d.textbbox((0,0), cur + w + " ", fnt)[2] > w_draw: lines.append(cur); cur = w + " "
            else: cur += w + " "
        if cur: lines.append(cur)
        for l in lines:
            bb = d.textbbox((0,0), l, fnt); w_l = bb[2] - bb[0]
            d.rectangle([(ANCHO/2 - w_l/2 - 10, y_pos), (ANCHO/2 + w_l/2 + 10, y_pos + LH + 5)], fill=bg_col)
            d.text((ANCHO/2 - w_l/2, y_pos), l, font=fnt, fill="black"); y_pos += int(LH * 1.4)
        return y_pos + 10

    dias = {0:"lunes",1:"martes",2:"miércoles",3:"jueves",4:"viernes",5:"sábado",6:"domingo"}
    fecha_str = f"{dias[fecha_dt.weekday()]} {fecha_dt.strftime('%d/%m/%y')}"
    
    col_ti = PALETA[2] if len(PALETA)>2 else "#d1e7dd"
    y = draw_centered("Reporte de Estaciones de", y, f_ti, col_ti)
    y = draw_centered(f"Servicio y Unidades {fecha_str}", y, f_ti, col_ti)
    
    icon = obtener_icono_bomba()
    if icon:
        isz = int(FONT_S * 1.5); icon = icon.resize((isz, isz))
        cnt = 5; tot_w = (isz*cnt) + (8*(cnt-1))
        if tot_w > w_draw: cnt = 3; tot_w = (isz*cnt) + (8*(cnt-1))
        sx = (ANCHO - tot_w)/2
        for i in range(cnt): img.paste(icon, (int(sx + i*(isz+8)), y), icon)
        y += int(isz * 1.5)
    else:
        y += LINE_HEIGHT_NORMAL

    for i, st_data in enumerate(reporte_lista):
        col = PALETA[i % len(PALETA)]
        # Limpieza de emojis en nombres y horarios
        nom = limpiar_texto(st_data['nombre']); hor = limpiar_texto(st_data['horario'])
        
        lines_t = []; cur_t = ""
        for w in f"• Estación {nom}: {hor}".split():
            if d.textbbox((0,0), cur_t + w + " ", f_bd)[2] > w_draw: lines_t.append(cur_t); cur_t = w + " "
            else: cur_t += w + " "
        if cur_t: lines_t.append(cur_t)
        
        for l in lines_t:
            bb = d.textbbox((0,0), l, f_bd); w_l = bb[2]
            d.rectangle([(20, y), (20 + w_l + 10, y + LH + 4)], fill=col)
            d.text((25, y + 2), l, font=f_bd, fill="black"); y += int(LH * 1.2)
        
        # Ceros a la izquierda
        nums = " ".join([f"{u:02d}" for u in st_data['unidades']])
        lines_n = []; cur_n = ""
        for w in nums.split():
            if d.textbbox((0,0), cur_n + w + " ", f_no)[2] > w_draw: lines_n.append(cur_n); cur_n = w + " "
            else: cur_n += w + " "
        if cur_n: lines_n.append(cur_n)
        for l in lines_n: d.text((20, y), l, font=f_no, fill="black"); y += LH
        y += GAP

    bb_r = d.textbbox((0,0), "• Rango de unidades", f_bd)
    d.rectangle([(20, y), (20 + bb_r[2] + 10, y + LH + 4)], fill="#cff4fc")
    d.text((25, y + 2), "• Rango de unidades", font=f_bd, fill="black"); y += int(LH * 1.2)
    
    ran_clean = limpiar_texto(rango_txt)
    lines_r = []; cur_r = ""
    for w in ran_clean.split():
        if d.textbbox((0,0), cur_r + w + " ", f_no)[2] > w_draw: lines_r.append(cur_r); cur_r = w + " "
        else: cur_r += w + " "
    if cur_r: lines_r.append(cur_r)
    for l in lines_r: d.text((20, y), l, font=f_no, fill="black"); y += LH
    y += GAP

    out = img.crop((0, 0, ANCHO, y + 20))
    buf = BytesIO(); out.save(buf, "PNG"); buf.seek(0)
    return buf

# ================= MAIN =================
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
        
        with st.expander("1. Rangos y Dimensiones", expanded=False):
            c1, c2 = st.columns(2)
            nuevo_min = c1.number_input("Inicial", value=datos.get("rango_min", 1), min_value=1)
            nuevo_max = c2.number_input("Final", value=datos.get("rango_max", 500), min_value=1)
            st.divider()
            c3, c4 = st.columns(2)
            nuevo_ancho = c3.slider("Ancho (px)", 300, 800, value=datos.get("img_width", 450))
            nueva_fuente = c4.slider("Tamaño Letra", 14, 40, value=datos.get("font_size", 24))

        with st.expander("2. Personalizar Colores 🎨", expanded=True):
            st.caption("Fondo y colores de estaciones:")
            col_bg, col_preview = st.columns([1, 3])
            nuevo_bg = col_bg.color_picker("Color de Fondo", value=datos.get("bg_color", "#ECE5DD"))
            col_preview.markdown(f'<div style="background-color:{nuevo_bg}; padding: 10px; border-radius: 5px; text-align: center;">Vista Previa</div>', unsafe_allow_html=True)
            
            st.divider()
            st.write("Paleta de Estaciones:")
            current_st_colors = datos.get("st_colors", ["#f8d7da"]*6)
            nuevos_st_colors = []
            
            cols_c1 = st.columns(3)
            for i in range(3):
                c = cols_c1[i].color_picker(f"Color {i+1}", value=current_st_colors[i], key=f"cp_{i}")
                nuevos_st_colors.append(c)
                
            cols_c2 = st.columns(3)
            for i in range(3, 6):
                c = cols_c2[i-3].color_picker(f"Color {i+1}", value=current_st_colors[i], key=f"cp_{i}")
                nuevos_st_colors.append(c)
        
        if st.button("💾 Guardar Configuración", type="primary"):
            datos["rango_min"] = nuevo_min
            datos["rango_max"] = nuevo_max
            datos["img_width"] = nuevo_ancho
            datos["font_size"] = nueva_fuente
            datos["bg_color"] = nuevo_bg
            datos["st_colors"] = nuevos_st_colors
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

    # --- ASIGNACIÓN (ESTABLE) ---
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
                    
                    # --- MODO EDICIÓN ---
                    if st.session_state.editando_idx == i:
                        st.info("Editando lista de unidades:")
                        
                        # 1. BORRAR
                        if unidades_lista:
                            st.caption("Toca para eliminar:")
                            cols = st.columns(4) 
                            for idx_u, u in enumerate(unidades_lista):
                                if cols[idx_u % 4].button(f"❌ {u}", key=f"del_u_{i}_{u}", use_container_width=True):
                                    est['unidades'].remove(u)
                                    st.rerun()
                        else: st.warning("Lista vacía.")
                        
                        st.divider()
                        
                        # 2. AGREGAR
                        otros_asignados = []
                        for idx_req, req in enumerate(st.session_state.reporte_diario):
                            if idx_req != i:
                                otros_asignados.extend(req['unidades'])
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
                            
                    # --- MODO VISTA ---
                    else:
                        if unidades_lista:
                            estilo_flex = "display: flex; flex-wrap: wrap; gap: 8px; align-items: center;"
                            estilo_ficha = "background-color: #f0f2f6; color: #31333F; padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 15px; border: 1px solid #d0d0d0; box-shadow: 0 1px 2px rgba(0,0,0,0.05);"
                            html_badges = f'<div style="{estilo_flex}">'
                            for u in unidades_lista: html_badges += f'<div style="{estilo_ficha}">🚍 {u:02d}</div>'
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