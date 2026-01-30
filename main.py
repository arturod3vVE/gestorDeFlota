import streamlit as st
from datetime import datetime
import urllib.parse
import base64 
import time 
import streamlit.components.v1 as components 

# IMPORTACIONES
from database import cargar_datos_db, guardar_datos_db, guardar_historial_db, recuperar_historial_por_fecha
from image_gen import generar_imagen_en_memoria
from utils import inyectar_css, verificar_login, selector_de_rangos, obtener_lista_horas_puntuales

# 1. Configuración de la página
st.set_page_config(page_title="Gestor de Flota", page_icon="⛽", layout="wide")
inyectar_css()

# --- FUNCIÓN ESPECIAL: COMPARTIR NATIVO ---
def accion_compartir_nativa(img_bytes, nombre_archivo="reporte.png"):
    """
    Botón 'Compartir' con color AZUL para diferenciarlo.
    """
    b64 = base64.b64encode(img_bytes.getvalue()).decode()
    
    html_code = f"""
    <html>
        <head>
        <style>
            body {{
                margin: 0;
                padding: 0;
                background-color: transparent;
            }}
            .btn-share {{
                display: flex;
                align-items: center;
                justify-content: center;
                width: 100%;
                height: 2.5rem;
                background-color: #007BFF; 
                color: white;
                font-weight: 600;
                border: 1px solid rgba(0,0,0,0.1);
                border-radius: 0.5rem;
                cursor: pointer;
                font-family: "Source Sans Pro", sans-serif;
                font-size: 1rem;
                text-decoration: none;
                box-sizing: border-box;
                transition: background-color 0.2s, box-shadow 0.2s;
            }}
            .btn-share:hover {{
                background-color: #0056b3;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .btn-share:active {{
                transform: scale(0.99);
                background-color: #004494;
            }}
        </style>
        </head>
        <body>
            <button class="btn-share" onclick="compartir()">
                📲 Compartir
            </button>

            <script>
            async function compartir() {{
                const b64 = "{b64}";
                const res = await fetch("data:image/png;base64," + b64);
                const blob = await res.blob();
                const file = new File([blob], "{nombre_archivo}", {{ type: "image/png" }});

                if (navigator.share && navigator.canShare({{ files: [file] }})) {{
                    try {{
                        await navigator.share({{
                            files: [file],
                            title: 'Reporte de Flota',
                            text: 'Reporte de asignación.'
                        }});
                    }} catch (err) {{
                        console.log('Cancelado/Error:', err);
                    }}
                }} else {{
                    alert('Tu navegador no soporta compartir imágenes directo. Usa el botón "Descargar".');
                }}
            }}
            </script>
        </body>
    </html>
    """
    components.html(html_code, height=45)

# 2. Control de Acceso
is_authenticated, cookie_manager = verificar_login()

if is_authenticated:
    
    usuario_actual = st.session_state.usuario_actual
    
    if 'vista_actual' not in st.session_state:
        st.session_state.vista_actual = "Asignacion"

    def cambiar_vista(nueva_vista):
        st.session_state.vista_actual = nueva_vista

    with st.sidebar:
        st.header("Panel de Control")
        st.info(f"👤 **{usuario_actual.capitalize()}**")
        
        st.divider()
        st.write("📍 **Navegación**")
        
        estilo_asig = "primary" if st.session_state.vista_actual == "Asignacion" else "secondary"
        st.button("⛽ Asignación", key="nav_asig", type=estilo_asig, use_container_width=True, on_click=cambiar_vista, args=("Asignacion",))
        
        estilo_taller = "primary" if st.session_state.vista_actual == "Taller" else "secondary"
        st.button("🔧 Taller", key="nav_taller", type=estilo_taller, use_container_width=True, on_click=cambiar_vista, args=("Taller",))
        
        estilo_conf = "primary" if st.session_state.vista_actual == "Configuracion" else "secondary"
        st.button("⚙️ Configuración", key="nav_conf", type=estilo_conf, use_container_width=True, on_click=cambiar_vista, args=("Configuracion",))
        
        st.divider()
        
        if st.button("🔄 Recargar Datos", use_container_width=True, help="Fuerza la recarga desde la base de datos"):
            if 'datos_app' in st.session_state: del st.session_state['datos_app']
            if 'reporte_diario' in st.session_state: del st.session_state['reporte_diario']
            st.toast("☁️ Datos actualizados")
            st.rerun()
            
        st.write("") 
        
        with st.popover("🚪 Cerrar Sesión", use_container_width=True):
            st.markdown("¿Salir del sistema?")
            if st.button("✅ Confirmar", type="primary", use_container_width=True):
                try: cookie_manager.delete("gestor_flota_user")
                except: pass
                st.session_state.autenticado = False
                st.session_state.usuario_actual = None
                keys_to_clear = ["datos_app", "reporte_diario", "k_width", "k_font", "k_bg", "k_text", "new_min", "new_max", "input_new_st", "vista_actual"] + [f"k_c_{i}" for i in range(6)]
                for k in keys_to_clear:
                    if k in st.session_state: del st.session_state[k]
                
                st.session_state["logout_pending"] = True
                st.rerun()
    
    # --- LÓGICA DE DATOS ---
    if 'datos_app' not in st.session_state:
        st.session_state.datos_app = cargar_datos_db(usuario_actual)
        if "rangos" not in st.session_state.datos_app:
            st.session_state.datos_app["rangos"] = [[1, 100]]
        est_raw = st.session_state.datos_app.get("estaciones", [])
        if isinstance(est_raw, str):
            st.session_state.datos_app["estaciones"] = [e.strip() for e in est_raw.split(';;') if e.strip()]
        elif not isinstance(est_raw, list):
            st.session_state.datos_app["estaciones"] = []

    if 'reporte_diario' not in st.session_state:
        hoy = datetime.now()
        datos_hoy = recuperar_historial_por_fecha(hoy, usuario_actual)
        st.session_state.reporte_diario = datos_hoy if datos_hoy else []

    def guardar(): 
        return guardar_datos_db(st.session_state.datos_app, usuario_actual)

    d = st.session_state.datos_app
    all_u = []
    if "rangos" in d:
        for r in d["rangos"]:
            all_u.extend(list(range(r[0], r[1] + 1)))
    all_u = sorted(list(set(all_u)))
    LISTA_HORAS = obtener_lista_horas_puntuales()

    # ==============================================================================
    #                             VISTA: ASIGNACIÓN
    # ==============================================================================
    if st.session_state.vista_actual == "Asignacion":
        st.title("⛽ Asignación de Unidades")
        
        if 'ed_idx' not in st.session_state: st.session_state.ed_idx = None
        
        def ch_date():
            dt = recuperar_historial_por_fecha(st.session_state.key_fecha_rep, usuario_actual)
            st.session_state.reporte_diario = dt if dt else []
            if dt: st.toast(f"📅 Registros cargados: {len(dt)}")

        c1, c2 = st.columns([1, 2], vertical_alignment="center")
        fr = c1.date_input("Fecha del Reporte", datetime.now(), key="key_fecha_rep", on_change=ch_date)
        c2.info(f"Visualizando: **{fr.strftime('%d/%m/%Y')}**")
        st.divider()
        
        avs = d.get("averiadas", [])
        op = [u for u in all_u if u not in avs]
        ya = [u for e in st.session_state.reporte_diario for u in e['unidades']]
        disp = [u for u in op if u not in ya]

        with st.container(border=True):
            m1,m2,m3 = st.columns(3)
            m1.metric("Total Flota", len(all_u))
            m2.metric("En Taller", len(avs), delta_color="inverse")
            m3.metric("Disponibles", len(disp))

        with st.expander("➕ Nueva Asignación", expanded=True):
            test = d.get("estaciones", [])
            ocup = [r['nombre'] for r in st.session_state.reporte_diario]
            dis = [e for e in test if e not in ocup]
            
            c_sel_st, c_sel_h = st.columns([1, 1])
            with c_sel_st:
                if dis: nom = st.selectbox("Estación", dis)
                else: st.warning("No hay estaciones disponibles."); nom = None
            
            with c_sel_h:
                sh = st.checkbox("Sin horario")
                h_str = ""
                if not sh:
                    col_h1, col_h2 = st.columns(2)
                    h1 = col_h1.selectbox("Abre", LISTA_HORAS, 9)
                    h2 = col_h2.selectbox("Cierra", LISTA_HORAS, 14)
                    h_str = f"{h1} a {h2}"
            
            st.markdown("---")
            st.write("**Seleccionar Unidades:**")
            sel = selector_de_rangos(disp, "main_asig", default_str=None)
            
            if st.button("💾 Guardar Asignación", type="primary", use_container_width=True):
                if nom and sel: 
                    st.session_state.reporte_diario.append({"nombre": nom, "horario": h_str, "unidades": sorted(sel)})
                    st.rerun()
                elif not nom: st.error("Selecciona una estación")
                elif not sel: st.error("Selecciona al menos una unidad")

        if st.session_state.reporte_diario:
            st.divider()
            st.subheader("📋 Resumen del Reporte")
            for i, e in enumerate(st.session_state.reporte_diario):
                with st.container(border=True):
                    c_t, c_b = st.columns([0.8, 0.2], vertical_alignment="center")
                    c_t.markdown(f"#### {e['nombre']}")
                    c_t.caption(f"Horario: {e['horario'] if e['horario'] else 'Sin horario'}")
                    
                    with c_b.popover("Opciones", use_container_width=True):
                        if st.button("✏️ Editar", key=f"ed_rep_{i}", use_container_width=True):
                            st.session_state.ed_idx = i
                            st.rerun()
                        if st.button("🗑️ Borrar", key=f"del_rep_{i}", type="primary", use_container_width=True):
                             st.session_state.reporte_diario.pop(i); st.rerun()
                    
                    if st.session_state.ed_idx == i:
                        st.info("✏️ Editando unidades...")
                        to_rm = st.multiselect("Quitar:", e['unidades'], key=f"md{i}")
                        if st.button("Quitar selección", key=f"brm{i}") and to_rm:
                            for x in to_rm: e['unidades'].remove(x)
                            st.rerun()
                        others = [u for ix, r in enumerate(st.session_state.reporte_diario) if ix != i for u in r['unidades']]
                        cands = [u for u in op if u not in others and u not in e['unidades']]
                        to_add = selector_de_rangos(cands, f"ea{i}", default_str=None)
                        if st.button("Agregar selección", key=f"bad{i}") and to_add:
                            e['unidades'].extend(to_add); e['unidades'].sort(); st.rerun()
                        if st.button("✅ Finalizar Edición", key=f"ok{i}", use_container_width=True):
                            st.session_state.ed_idx = None; st.rerun()
                    else:
                        # --- CAMBIO AQUÍ: MARGEN INFERIOR AÑADIDO (margin-bottom:10px) ---
                        st.markdown(f"<div style='display:flex;flex-wrap:wrap;gap:5px;margin-top:10px;margin-bottom:10px;'>{''.join([f'<span style=background:#eee;padding:4px;border-radius:4px;border:1px solid #ccc;font-weight:bold;>{u:02d}</span>' for u in e['unidades']])}</div>", unsafe_allow_html=True)
            
            st.divider()
            st.subheader("📤 Exportar y Compartir")
            txt_r = st.text_input("Pie de página (Texto Rango)", value="Reporte Diario")
            
            c_fot, c_wa, c_his = st.columns(3)
            
            if c_fot.button("📸 FOTO", type="primary", use_container_width=True):
                st.session_state.img_mem = generar_imagen_en_memoria(st.session_state.reporte_diario, fr, txt_r, d)
            
            if 'img_mem' in st.session_state:
                st.image(st.session_state.img_mem, caption="Vista Previa", width=350)
                bc1, bc2, bc3 = st.columns(3)
                with bc1:
                    accion_compartir_nativa(st.session_state.img_mem, "Reporte.png")
                with bc2:
                    st.download_button("📥 Guardar", st.session_state.img_mem, "Reporte.png", "image/png", use_container_width=True)
                with bc3:
                    if st.button("💾 Historial", use_container_width=True):
                        if guardar_historial_db(fr, st.session_state.reporte_diario, usuario_actual): 
                            st.success("OK")

            st.caption("Opción alternativa (Solo texto):")
            msg_wa = f"*REPORTE DE FLOTA - {fr.strftime('%d/%m/%Y')}*\n_{usuario_actual.upper()}_\n\n"
            for item in st.session_state.reporte_diario:
                msg_wa += f"⛽ *{item['nombre'].upper()}*\n"
                if item['horario']: msg_wa += f"🕒 {item['horario']}\n"
                unidades_str = ", ".join([str(u) for u in item['unidades']])
                msg_wa += f"🚛 {unidades_str}\n\n"
            if txt_r: msg_wa += f"ℹ️ _{txt_r}_"
            msg_encoded = urllib.parse.quote(msg_wa)
            st.link_button("💬 Enviar Resumen Texto a WhatsApp", f"https://wa.me/?text={msg_encoded}")

    # ==============================================================================
    #                             VISTA: TALLER
    # ==============================================================================
    elif st.session_state.vista_actual == "Taller":
        st.title("🔧 Taller de Mantenimiento")
        avs = d.get("averiadas", [])
        sanas = [u for u in all_u if u not in avs]
        with st.container(border=True):
            st.subheader("🔴 Reportar Avería")
            st.caption("Selecciona las unidades que entran al taller:")
            news = selector_de_rangos(sanas, "taller_add", default_str=None)
            if st.button("Enviar a Taller", type="primary", use_container_width=True):
                if news: 
                    d.setdefault("averiadas", []).extend(news)
                    d["averiadas"].sort()
                    guardar()
                    st.toast(f"🛠️ {len(news)} unidades enviadas a taller")
                    st.rerun()
        st.divider()
        if avs:
            with st.container(border=True):
                st.subheader("🟢 Reparaciones (Salida)")
                st.caption(f"Unidades actualmente en taller: {len(avs)}")
                reps = st.multiselect("Selecciona unidades reparadas:", avs)
                if st.button("Marcar como Operativas", use_container_width=True):
                    if reps: 
                        for x in reps: d["averiadas"].remove(x)
                        guardar()
                        st.toast(f"✅ {len(reps)} unidades recuperadas")
                        st.rerun()
        else: 
            st.success("✅ Toda la flota está operativa.")

    # ==============================================================================
    #                             VISTA: CONFIGURACIÓN
    # ==============================================================================
    elif st.session_state.vista_actual == "Configuracion":
        st.title("⚙️ Configuración del Sistema")
        if "k_width" not in st.session_state: st.session_state.k_width = d.get("img_width", 450)
        if "k_font" not in st.session_state: st.session_state.k_font = d.get("font_size", 24)
        if "k_bg" not in st.session_state: st.session_state.k_bg = d.get("bg_color", "#ECE5DD")
        if "k_text" not in st.session_state: st.session_state.k_text = d.get("text_color", "#000000")
        db_colors = d.get("st_colors", ["#f8d7da"]*6)
        for i in range(6):
            if f"k_c_{i}" not in st.session_state: st.session_state[f"k_c_{i}"] = db_colors[i]
        
        def revertir_cambios():
            st.session_state.k_width = d.get("img_width", 450)
            st.session_state.k_font = d.get("font_size", 24)
            st.session_state.k_bg = d.get("bg_color", "#ECE5DD")
            st.session_state.k_text = d.get("text_color", "#000000")
            rc = d.get("st_colors", ["#f8d7da"]*6)
            for i in range(6): st.session_state[f"k_c_{i}"] = rc[i]
            st.toast("↺ Valores restaurados")

        mostrar_preview = st.toggle("👁️ Mostrar Vista Previa en tiempo real", value=False)
        st.markdown("---")
        
        if mostrar_preview:
            col_config, col_preview = st.columns([1.5, 1])
        else:
            col_config = st.container()
            col_preview = None
        
        with col_config:
            with st.expander("📍 1. Rangos de Flota", expanded=True):
                rangos_actuales = d.get("rangos", [])
                if rangos_actuales:
                    st.caption("Rangos activos:")
                    for i, r in enumerate(rangos_actuales):
                        c_info, c_action = st.columns([5, 1], vertical_alignment="center")
                        c_info.code(f"{r[0]} ➝ {r[1]}")
                        with c_action.popover("🗑️"):
                            st.write("¿Eliminar?")
                            if st.button("Sí", key=f"del_r_{i}", type="primary", use_container_width=True):
                                d["rangos"].pop(i); guardar(); st.rerun()
                else: st.info("No hay rangos definidos.")
                st.divider()
                st.caption("➕ Crear nuevo rango:")
                c_n1, c_n2, c_btn = st.columns([2, 2, 2], vertical_alignment="bottom")
                n_min = c_n1.number_input("Desde", min_value=1, value=1)
                n_max = c_n2.number_input("Hasta", min_value=1, value=100)
                if c_btn.button("Agregar", type="primary", use_container_width=True):
                    if n_max < n_min: st.error("Error: Final < Inicio.")
                    else:
                        choca = False
                        for r in d["rangos"]:
                            if n_min <= r[1] and n_max >= r[0]: choca = True; break
                        if choca: st.error("⚠️ Cruce de rangos.")
                        else:
                            d["rangos"].append([n_min, n_max]); d["rangos"].sort(key=lambda x: x[0]); guardar(); st.rerun()

            with st.expander("🎨 2. Personalizar Apariencia", expanded=False):
                c3, c4 = st.columns(2)
                ni = c3.slider("Ancho Imagen", 300, 800, key="k_width")
                nf = c4.slider("Tamaño Fuente", 14, 40, key="k_font")
                st.write("**Colores:**")
                cc1, cc2 = st.columns(2)
                nuevo_bg = cc1.color_picker("Fondo Imagen", key="k_bg")
                nuevo_text = cc2.color_picker("Color Texto", key="k_text")
                st.write("**Colores de Estaciones:**")
                nuevos_st_colors = []
                f1 = st.columns(3)
                for i in range(3): nuevos_st_colors.append(f1[i].color_picker(f"C{i+1}", key=f"k_c_{i}"))
                f2 = st.columns(3)
                for i in range(3, 6): nuevos_st_colors.append(f2[i-3].color_picker(f"C{i+4}", key=f"k_c_{i}"))
                st.divider()
                b_save, b_cancel = st.columns([1, 1])
                with b_save:
                    if st.button("💾 Guardar Cambios", type="primary", width='stretch'):
                        d["img_width"] = ni; d["font_size"] = nf
                        d["bg_color"] = nuevo_bg; d["text_color"] = nuevo_text
                        d["st_colors"] = nuevos_st_colors
                        if guardar(): st.success("Guardado!"); st.rerun()
                with b_cancel:
                    st.button("✖️ Restaurar", type="secondary", width='stretch', on_click=revertir_cambios)

            with st.expander("⛽ 3. Gestión de Estaciones", expanded=False):
                c_add, c_del = st.columns(2, gap="large")
                with c_add:
                    st.write("**:green[➕] Nueva Estación**")
                    nueva_st_input = st.text_input("Nombre:", placeholder="Ej: Texaco Norte", key="in_st")
                    if st.button("Guardar Estación", use_container_width=True):
                        if nueva_st_input:
                            nueva = nueva_st_input.strip()
                            est_actuales = d.get("estaciones", [])
                            if nueva.lower() not in [e.lower() for e in est_actuales]:
                                d.setdefault("estaciones", []).append(nueva)
                                if guardar(): st.toast(f"✅ Agregada: {nueva}"); st.rerun()
                                else: st.toast("❌ Error DB")
                            else: st.toast("⚠️ Ya existe.")
                with c_del:
                    st.write("**:red[🗑️] Eliminar Estaciones**")
                    ests = d.get("estaciones", [])
                    if ests:
                        rem = st.multiselect("Seleccionar:", ests, placeholder="Elige para borrar...")
                        with st.popover("Eliminar Seleccionadas", use_container_width=True, disabled=not rem):
                            st.write("⚠️ **¿Confirmar borrado?**")
                            if st.button("Sí, borrar definitivamente", type="primary", use_container_width=True):
                                for x in rem: 
                                    if x in d["estaciones"]: d["estaciones"].remove(x)
                                if guardar(): st.toast("🗑️ Eliminadas"); st.rerun()
                    else: st.info("Lista vacía.")

        if col_preview:
            with col_preview:
                st.subheader("👁️ Vista Previa")
                with st.container(border=True):
                    r_txt = " / ".join([f"{r[0]}-{r[1]}" for r in d.get("rangos",[])]) if d.get("rangos") else "Sin rangos"
                    u_demo = [1, 2, 3]
                    if d.get("rangos"):
                        r1 = d["rangos"][0]
                        u_demo = list(range(r1[0], min(r1[0]+5, r1[1]+1)))
                    datos_demo = [
                        {"nombre": "Estación Demo", "horario": "8 AM - 1 PM", "unidades": u_demo},
                        {"nombre": "Estación B", "horario": "2 PM - 6 PM", "unidades": []}
                    ]
                    cfg_temp = d.copy(); cfg_temp["img_width"] = ni; cfg_temp["font_size"] = nf
                    cfg_temp["bg_color"] = nuevo_bg; cfg_temp["st_colors"] = nuevos_st_colors
                    cfg_temp["text_color"] = nuevo_text
                    try:
                        img_prev = generar_imagen_en_memoria(datos_demo, datetime.now(), f"Flota: {r_txt}", cfg_temp)
                        st.image(img_prev, width=350)
                    except Exception as e: st.error(str(e))
