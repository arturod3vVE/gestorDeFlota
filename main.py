import streamlit as st
from datetime import datetime

# IMPORTACIONES
from database import cargar_datos_db, guardar_datos_db, guardar_historial_db, recuperar_historial_por_fecha
from image_gen import generar_imagen_en_memoria
from utils import inyectar_css, verificar_login, selector_de_rangos, obtener_lista_horas_puntuales

# 1. Configuración de la página
st.set_page_config(page_title="Gestor de Flota", page_icon="⛽", layout="wide")
inyectar_css()

# 2. Control de Acceso
if verificar_login():
    
    usuario_actual = st.session_state.usuario_actual
    
    with st.sidebar:
        st.header("Panel de Control")
        st.success(f"👤 Hola, **{usuario_actual.capitalize()}**")
        st.divider()
        
        if st.button("🔄 Actualizar Datos (DB)", width='stretch', help="Pulsa si editaste el Excel manualmente"):
            if 'datos_app' in st.session_state: del st.session_state['datos_app']
            if 'reporte_diario' in st.session_state: del st.session_state['reporte_diario']
            st.toast("Datos recargados.")
            st.rerun()
            
        st.divider()
        if st.button("🚪 Cerrar Sesión", type="secondary", width='stretch'):
            st.session_state.autenticado = False
            st.session_state.usuario_actual = None
            keys_to_clear = ["datos_app", "reporte_diario", "k_width", "k_font", "k_bg", "new_min", "new_max", "input_new_st"] + [f"k_c_{i}" for i in range(6)]
            for k in keys_to_clear:
                if k in st.session_state: del st.session_state[k]
            st.rerun()
    
    # Carga de Datos
    if 'datos_app' not in st.session_state:
        with st.spinner(f"Sincronizando con la nube de {usuario_actual}..."):
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

    tab_asig, tab_taller, tab_conf = st.tabs(["⛽ Asignación", "🔧 Taller", "⚙️ Configuración"])
    d = st.session_state.datos_app
    
    # --- CONSTRUCCIÓN DE LA LISTA DE UNIDADES ---
    all_u = []
    if "rangos" in d:
        for r in d["rangos"]:
            all_u.extend(list(range(r[0], r[1] + 1)))
    all_u = sorted(list(set(all_u)))
    
    LISTA_HORAS = obtener_lista_horas_puntuales()

    # ---------------- PESTAÑA CONFIGURACIÓN ----------------
    with tab_conf:
        # Variables visuales
        if "k_width" not in st.session_state: st.session_state.k_width = d.get("img_width", 450)
        if "k_font" not in st.session_state: st.session_state.k_font = d.get("font_size", 24)
        if "k_bg" not in st.session_state: st.session_state.k_bg = d.get("bg_color", "#ECE5DD")
        db_colors = d.get("st_colors", ["#f8d7da"]*6)
        for i in range(6):
            if f"k_c_{i}" not in st.session_state: st.session_state[f"k_c_{i}"] = db_colors[i]

        def revertir_cambios():
            st.session_state.k_width = d.get("img_width", 450)
            st.session_state.k_font = d.get("font_size", 24)
            st.session_state.k_bg = d.get("bg_color", "#ECE5DD")
            rc = d.get("st_colors", ["#f8d7da"]*6)
            for i in range(6): st.session_state[f"k_c_{i}"] = rc[i]
            st.toast("↺ Restaurado")

        col_config, col_preview = st.columns([1.5, 1])
        
        with col_config:
            st.header("⚙️ Ajustes")
            
            with st.expander("1. Rangos de Unidades (Flota)", expanded=True):
                rangos_actuales = d.get("rangos", [])
                for i, r in enumerate(rangos_actuales):
                    c_txt, c_del = st.columns([4, 1])
                    c_txt.text(f"📍 Rango {i+1}: {r[0]} - {r[1]}")
                    if c_del.button("🗑️", key=f"del_r_{i}"):
                        d["rangos"].pop(i); guardar(); st.rerun()

                st.divider()
                with st.form("form_rangos", clear_on_submit=True):
                    c_n1, c_n2 = st.columns(2)
                    n_min = c_n1.number_input("Desde", min_value=1, value=1)
                    n_max = c_n2.number_input("Hasta", min_value=1, value=100)
                    btn_rango = st.form_submit_button("➕ Agregar Rango")
                    
                    if btn_rango:
                        if n_max < n_min: st.error("Error: Final < Inicio.")
                        else:
                            choca = False
                            for r in d["rangos"]:
                                if n_min <= r[1] and n_max >= r[0]: choca = True; break
                            if choca: st.error("⚠️ El rango se cruza con uno existente.")
                            else:
                                d["rangos"].append([n_min, n_max]); d["rangos"].sort(key=lambda x: x[0]); guardar(); st.rerun()

            with st.expander("2. Apariencia Visual", expanded=True):
                c3, c4 = st.columns(2)
                ni = c3.slider("Ancho Imagen", 300, 800, key="k_width")
                nf = c4.slider("Tamaño Fuente", 14, 40, key="k_font")
                st.write("**Colores:**")
                nuevo_bg = st.color_picker("Fondo", key="k_bg")
                nuevos_st_colors = []
                f1 = st.columns(3)
                for i in range(3): nuevos_st_colors.append(f1[i].color_picker(f"C{i+1}", key=f"k_c_{i}"))
                f2 = st.columns(3)
                for i in range(3, 6): nuevos_st_colors.append(f2[i-3].color_picker(f"C{i+4}", key=f"k_c_{i}"))

            st.divider()
            b_save, b_cancel = st.columns([1, 1])
            with b_save:
                if st.button("💾 Guardar Apariencia", type="primary", width='stretch'):
                    d["img_width"] = ni; d["font_size"] = nf
                    d["bg_color"] = nuevo_bg; d["st_colors"] = nuevos_st_colors
                    if guardar(): st.success("Guardado!"); st.rerun()
            with b_cancel:
                st.button("✖️ Reset Apariencia", type="secondary", width='stretch', on_click=revertir_cambios)

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
                try:
                    img_prev = generar_imagen_en_memoria(datos_demo, datetime.now(), f"Flota: {r_txt}", cfg_temp)
                    st.image(img_prev, width=350)
                except Exception as e: st.error(str(e))

        st.divider()
        st.subheader("3. Gestión de Estaciones")
        
        # --- SOLUCIÓN VISUAL: AMBOS LADOS CON FORMULARIO ---
        c_add, c_del = st.columns(2)
        
        # COLUMNA IZQUIERDA: AGREGAR (CON FORMULARIO)
        with c_add:
            st.write("**Agregar Estación:**")
            with st.form("form_add_estacion", clear_on_submit=True):
                nueva_st_input = st.text_input("Nombre:")
                btn_add_st = st.form_submit_button("➕ Agregar")
                
                if btn_add_st and nueva_st_input:
                    nueva = nueva_st_input.strip()
                    est_actuales = d.get("estaciones", [])
                    est_lower = [str(e).lower().strip() for e in est_actuales]
                    
                    if nueva.lower() not in est_lower:
                        d.setdefault("estaciones", []).append(nueva)
                        if guardar():
                            st.toast(f"✅ Agregada: {nueva}")
                            st.rerun()
                        else: st.toast("❌ Error DB")
                    else: st.toast(f"⚠️ '{nueva}' ya existe.")

        # COLUMNA DERECHA: ELIMINAR (AHORA TAMBIÉN CON FORMULARIO PARA SIMETRÍA)
        with c_del:
            st.write("**Eliminar Estaciones:**")
            # Usamos st.form aquí también para que se vea igual (caja con borde)
            with st.form("form_del_estacion"):
                ests = d.get("estaciones", [])
                
                if ests:
                    st.caption(f"Total registradas: {len(ests)}")
                    rem = st.multiselect("Seleccionar:", ests)
                    
                    # Botón de submit del formulario
                    if st.form_submit_button("🗑️ Eliminar Seleccionadas"):
                        if rem:
                            for x in rem: 
                                if x in d["estaciones"]: d["estaciones"].remove(x)
                            if guardar(): 
                                st.success("Eliminadas.")
                                st.rerun()
                        else:
                            st.warning("Selecciona al menos una estación.")
                else:
                    st.info("Lista vacía.")
                    # Botón deshabilitado para mantener la estructura visual
                    st.form_submit_button("---", disabled=True)

    # --- TALLER Y ASIGNACIÓN ---
    with tab_taller:
        st.header("🔧 Taller")
        avs = d.get("averiadas", [])
        sanas = [u for u in all_u if u not in avs]
        news = selector_de_rangos(sanas, "taller_add", default_str=None)
        
        if st.button("🔴 Reportar", type="primary", width='stretch'):
            if news: d.setdefault("averiadas", []).extend(news); d["averiadas"].sort(); guardar(); st.rerun()
        st.divider()
        if avs:
            reps = st.multiselect("Reparar", avs)
            if st.button("🔧 Reparar", width='stretch'):
                if reps: 
                    for x in reps: d["averiadas"].remove(x)
                    guardar(); st.rerun()
        else: st.success("Operativa")

    with tab_asig:
        if 'ed_idx' not in st.session_state: st.session_state.ed_idx = None
        def ch_date():
            dt = recuperar_historial_por_fecha(st.session_state.key_fecha_rep, usuario_actual)
            st.session_state.reporte_diario = dt if dt else []
            if dt: st.toast(f"Cargado: {len(dt)} registros")

        c1, c2 = st.columns([1, 2], vertical_alignment="center")
        fr = c1.date_input("Fecha", datetime.now(), key="key_fecha_rep", on_change=ch_date)
        c2.info(f"Reporte: **{fr.strftime('%d/%m/%Y')}**")
        st.divider()
        
        avs = d.get("averiadas", [])
        op = [u for u in all_u if u not in avs]
        ya = [u for e in st.session_state.reporte_diario for u in e['unidades']]
        disp = [u for u in op if u not in ya]

        m1,m2,m3 = st.columns(3)
        m1.metric("Total", len(all_u)); m2.metric("Taller", len(avs)); m3.metric("Libres", len(disp))

        with st.expander("➕ Asignar", expanded=True):
            test = d.get("estaciones", [])
            ocup = [r['nombre'] for r in st.session_state.reporte_diario]
            dis = [e for e in test if e not in ocup]
            
            if dis: nom = st.selectbox("Estación", dis)
            else: st.warning("Sin estaciones libres."); nom = None
            
            st.divider()
            sh = st.checkbox("Sin horario")
            h_str = ""
            if not sh:
                c_h1, c_h2 = st.columns(2)
                h_str = f"{c_h1.selectbox('Abre', LISTA_HORAS, 9)} a {c_h2.selectbox('Cierra', LISTA_HORAS, 14)}"
            
            st.divider()
            st.write("**Seleccionar Unidades:**")
            sel = selector_de_rangos(disp, "main_asig", default_str=None)
            
            if st.button("Guardar Asignación", type="primary", width='stretch'):
                if nom and sel: 
                    st.session_state.reporte_diario.append({"nombre": nom, "horario": h_str, "unidades": sorted(sel)})
                    st.rerun()
                elif not nom: st.error("Falta Estación")
                elif not sel: st.error("Faltan Unidades")

        if st.session_state.reporte_diario:
            st.divider()
            for i, e in enumerate(st.session_state.reporte_diario):
                with st.container(border=True):
                    c_t, c_b = st.columns([0.7, 0.3])
                    c_t.markdown(f"**{e['nombre']}** {e['horario']}")
                    if c_b.button("🗑️", key=f"d{i}"): st.session_state.reporte_diario.pop(i); st.rerun()
                    
                    if st.session_state.ed_idx == i:
                        st.info("Editando...")
                        to_rm = st.multiselect("Quitar", e['unidades'], key=f"md{i}")
                        if st.button("Quitar", key=f"brm{i}") and to_rm:
                            for x in to_rm: e['unidades'].remove(x)
                            st.rerun()
                        
                        others = [u for ix, r in enumerate(st.session_state.reporte_diario) if ix != i for u in r['unidades']]
                        cands = [u for u in op if u not in others and u not in e['unidades']]
                        to_add = selector_de_rangos(cands, f"ea{i}", default_str=None)
                        if st.button("Agregar", key=f"bad{i}") and to_add:
                            e['unidades'].extend(to_add); e['unidades'].sort(); st.rerun()
                        if st.button("✅ Listo", key=f"ok{i}", width='stretch'):
                            st.session_state.ed_idx = None; st.rerun()
                    else:
                        st.markdown(f"<div style='display:flex;flex-wrap:wrap;gap:5px;'>{''.join([f'<span style=background:#eee;padding:2px;border:1px solid #ccc>{u:02d}</span>' for u in e['unidades']])}</div>", unsafe_allow_html=True)
            
            st.divider()
            txt_r = st.text_input("Texto Rango", value="Reporte Diario")
            if st.button("📸 FOTO", type="primary", width='stretch'):
                st.session_state.img_mem = generar_imagen_en_memoria(st.session_state.reporte_diario, fr, txt_r, d)
            if 'img_mem' in st.session_state:
                st.image(st.session_state.img_mem, width=300)
                st.download_button("📥", st.session_state.img_mem, "R.png", "image/png", width='stretch')
            if st.button("💾 Historial", width='stretch'):
                if guardar_historial_db(fr, st.session_state.reporte_diario, usuario_actual): st.success("OK")