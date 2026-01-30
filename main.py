import streamlit as st
from datetime import datetime

# IMPORTACIONES
from database import cargar_datos_db, guardar_datos_db, guardar_historial_db, recuperar_historial_por_fecha
from image_gen import generar_imagen_en_memoria
from utils import inyectar_css, verificar_login, selector_de_rangos, obtener_lista_horas_puntuales

# 1. Configuración de la página (SIEMPRE PRIMERO)
st.set_page_config(page_title="Gestor de Flota", page_icon="⛽", layout="wide")
inyectar_css()

# 2. Control de Acceso
# Si verificar_login() devuelve True, significa que el usuario ya se autenticó correctamente
if verificar_login():
    
    # --- A. BARRA LATERAL (SIDEBAR) ---
    # Aquí es donde debe estar el botón de salir para que siempre se vea
    usuario_actual = st.session_state.usuario_actual
    
    with st.sidebar:
        st.header("Panel de Control")
        st.success(f"👤 Hola, **{usuario_actual.capitalize()}**")
        
        st.divider()
        
        # BOTÓN DE CERRAR SESIÓN
        if st.button("🚪 Cerrar Sesión", type="secondary", use_container_width=True):
            # Limpiamos las variables de sesión críticas
            st.session_state.autenticado = False
            st.session_state.usuario_actual = None
            
            # Limpiamos los datos cargados para seguridad
            if 'datos_app' in st.session_state: del st.session_state['datos_app']
            if 'reporte_diario' in st.session_state: del st.session_state['reporte_diario']
            
            # Recargamos la página para volver al Login
            st.rerun()
    
    # --- B. CARGA DE DATOS (Solo si está logueado) ---
    if 'datos_app' not in st.session_state:
        with st.spinner(f"Cargando datos de {usuario_actual}..."):
            st.session_state.datos_app = cargar_datos_db(usuario_actual)

    # Carga automática del historial de HOY (si existe)
    if 'reporte_diario' not in st.session_state:
        hoy = datetime.now()
        datos_hoy = recuperar_historial_por_fecha(hoy, usuario_actual)
        if datos_hoy:
            st.session_state.reporte_diario = datos_hoy
            # st.toast(f"📅 Se cargaron {len(datos_hoy)} registros de hoy.")
        else:
            st.session_state.reporte_diario = []

    # Función auxiliar para guardar (usando el usuario actual)
    def guardar(): 
        guardar_datos_db(st.session_state.datos_app, usuario_actual)

    # --- C. INTERFAZ PRINCIPAL (TABS) ---
    tab_asig, tab_taller, tab_conf = st.tabs(["⛽ Asignación", "🔧 Taller", "⚙️ Configuración"])
    d = st.session_state.datos_app
    
    # Generamos la lista total de unidades
    all_u = list(range(d.get("rango_min", 1), d.get("rango_max", 500) + 1))
    LISTA_HORAS = obtener_lista_horas_puntuales()

    # ---------------- PESTAÑA CONFIGURACIÓN ----------------
    with tab_conf:
        st.header("⚙️ Ajustes")
        with st.expander("1. Rangos y Dimensiones", expanded=False):
            c1, c2 = st.columns(2)
            nm = c1.slider("Inicio", 1, 1000, d.get("rango_min", 1))
            nx = c2.slider("Fin", 1, 1000, d.get("rango_max", 500))
            st.divider()
            c3, c4 = st.columns(2)
            ni = c3.slider("Ancho", 300, 800, d.get("img_width", 450))
            nf = c4.slider("Fuente", 14, 40, d.get("font_size", 24))

        with st.expander("2. Personalizar Colores 🎨", expanded=True):
            col_bg, col_preview = st.columns([1, 3])
            nuevo_bg = col_bg.color_picker("Color de Fondo", value=d.get("bg_color", "#ECE5DD"))
            col_preview.markdown(f'<div style="background-color:{nuevo_bg}; padding: 10px; border-radius: 5px; text-align: center;">Vista Previa</div>', unsafe_allow_html=True)
            
            st.divider()
            st.write("Paleta de Estaciones:")
            current_st_colors = d.get("st_colors", ["#f8d7da"]*6)
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
            d["rango_min"] = nm; d["rango_max"] = nx
            d["img_width"] = ni; d["font_size"] = nf
            d["bg_color"] = nuevo_bg; d["st_colors"] = nuevos_st_colors
            guardar()
            st.success("Guardado.")
            st.rerun()

        st.divider()
        st.subheader("3. Estaciones")
        nueva = st.text_input("Nueva estación:")
        if st.button("➕ Agregar"):
            if nueva and nueva not in d.get("estaciones", []):
                d.setdefault("estaciones", []).append(nueva)
                guardar()
                st.rerun()
        
        ests = d.get("estaciones", [])
        if ests:
            st.caption("Borrar:")
            rem = st.multiselect("Borrar Estación", ests)
            if st.button("Borrar Seleccionadas") and rem:
                for x in rem: d["estaciones"].remove(x)
                guardar()
                st.rerun()

    # ---------------- PESTAÑA TALLER ----------------
    with tab_taller:
        st.header("🔧 Taller")
        avs = d.get("averiadas", [])
        sanas = [u for u in all_u if u not in avs]
        
        st.write("**Reportar Avería (Busca en pestañas):**")
        news = selector_de_rangos(sanas, "taller_add")
        
        if st.button("🔴 Reportar", type="primary", use_container_width=True):
            if news: 
                d.setdefault("averiadas", []).extend(news)
                d["averiadas"].sort()
                guardar()
                st.rerun()
        
        st.divider()
        if avs:
            st.info("En Taller (Toca para reparar):")
            reps = st.multiselect("Reparar", avs)
            if st.button("🔧 Reparar", use_container_width=True):
                if reps: 
                    for x in reps: d["averiadas"].remove(x)
                    guardar()
                    st.rerun()
        else: st.success("Flota operativa.")

    # ---------------- PESTAÑA ASIGNACIÓN ----------------
    with tab_asig:
        if 'ed_idx' not in st.session_state: st.session_state.ed_idx = None
        
        # Callback para cambio de fecha
        def al_cambiar_fecha():
            nueva_fecha = st.session_state.key_fecha_rep
            # IMPORTANTE: Pasamos el usuario_actual para recuperar SU historial
            datos = recuperar_historial_por_fecha(nueva_fecha, usuario_actual)
            if datos:
                st.session_state.reporte_diario = datos
                st.toast(f"✅ Se cargaron {len(datos)} registros.")
            else:
                st.session_state.reporte_diario = []
                st.toast("ℹ️ No hay historial para esta fecha.")

        c_f1, c_f2 = st.columns([1, 2], vertical_alignment="center")
        f_rep = c_f1.date_input(
            "📅 Fecha de Reporte", 
            datetime.now(), 
            key="key_fecha_rep", 
            on_change=al_cambiar_fecha
        )
        c_f2.info(f"Mostrando datos del: **{f_rep.strftime('%d/%m/%Y')}**")
        st.divider()
        
        avs = d.get("averiadas", [])
        op = [u for u in all_u if u not in avs]
        
        if 'reporte_diario' not in st.session_state: st.session_state.reporte_diario = []
        ya_as = [u for e in st.session_state.reporte_diario for u in e['unidades']]
        disp = [u for u in op if u not in ya_as]

        c1,c2,c3 = st.columns(3)
        c1.metric("Flota", len(all_u))
        c2.metric("Taller", len(avs))
        c3.metric("Libres", len(disp))

        with st.expander("➕ Asignar Estación", expanded=True):
            todas_ests = d.get("estaciones", [])
            ocupadas = [r['nombre'] for r in st.session_state.reporte_diario]
            disponibles = [e for e in todas_ests if e not in ocupadas]
            
            if disponibles:
                nom = st.selectbox("Estación", disponibles)
            else:
                st.warning("¡Todas las estaciones ya han sido asignadas!")
                nom = None
            
            st.divider()
            st.write("**Horario:**")
            
            sin_horario = st.checkbox("Sin horario específico")
            
            hora_str = ""
            if not sin_horario:
                c_h1, c_h2 = st.columns(2)
                t1 = c_h1.selectbox("Abre", LISTA_HORAS, index=9)
                t2 = c_h2.selectbox("Cierra", LISTA_HORAS, index=14)
                hora_str = f"{t1} a {t2}"
            
            st.divider()
            st.write("**Selecciona Unidades:**")
            sel = selector_de_rangos(disp, "main_asig")
            
            if st.button("Guardar Asignación", type="primary", use_container_width=True):
                if nom and sel:
                    st.session_state.reporte_diario.append({
                        "nombre": nom, "horario": hora_str, "unidades": sorted(sel)
                    })
                    st.rerun()
                elif not nom:
                    st.error("No hay estación seleccionada.")
                else:
                    st.error("Faltan seleccionar unidades.")

        if st.session_state.reporte_diario:
            st.divider()
            st.subheader("Resumen")
            for i, e in enumerate(st.session_state.reporte_diario):
                with st.container(border=True):
                    ch1, ch2 = st.columns([0.7, 0.3], vertical_alignment="center")
                    txt_titulo = f"**{e['nombre']}**"
                    if e['horario']:
                        txt_titulo += f" | {e['horario']}"
                    ch1.markdown(txt_titulo)
                    
                    with ch2:
                        c_e1, c_e2 = st.columns(2)
                        if c_e1.button("✏️", key=f"e{i}", use_container_width=True):
                            st.session_state.ed_idx = i if st.session_state.ed_idx != i else None
                            st.rerun()
                        if c_e2.button("🗑️", key=f"d{i}", use_container_width=True):
                            st.session_state.reporte_diario.pop(i)
                            st.session_state.ed_idx = None
                            st.rerun()
                    
                    if st.session_state.ed_idx == i:
                        st.info("Editando:")
                        to_rm = st.multiselect("Quitar", e['unidades'], key=f"mul_del_{i}")
                        if st.button("Quitar Marcadas", key=f"b_rm_{i}") and to_rm:
                            for x in to_rm: e['unidades'].remove(x)
                            st.rerun()
                        
                        st.divider()
                        others = []
                        for ix, r in enumerate(st.session_state.reporte_diario):
                            if ix != i: others.extend(r['unidades'])
                        cands = [u for u in op if u not in others and u not in e['unidades']]
                        
                        st.write("Agregar nuevas:")
                        to_add = selector_de_rangos(cands, f"ed_add_{i}")
                        
                        if st.button("Agregar Marcadas", key=f"b_add_{i}") and to_add:
                            e['unidades'].extend(to_add); e['unidades'].sort(); st.rerun()
                            
                        if st.button("✅ Listo", key=f"ok_{i}", use_container_width=True):
                            st.session_state.ed_idx = None; st.rerun()
                    else:
                        st.markdown(f"""
                        <div style="display:flex; flex-wrap:wrap; gap:5px;">
                        {''.join([f'<span style="background:#f0f2f6;padding:2px 8px;border-radius:4px;font-size:0.9em;border:1px solid #ddd">🚍 {u:02d}</span>' for u in e['unidades']])}
                        </div>
                        """, unsafe_allow_html=True)

            st.divider()
            st.subheader("🖼️ Imagen Final")
            txt_r = st.text_input("Rango:", value=f"Unidades desde la {d.get('rango_min',1)} a {d.get('rango_max',500)}")
            
            if st.button("📸 GENERAR", type="primary", use_container_width=True):
                with st.spinner("Creando..."):
                    st.session_state.img_mem = generar_imagen_en_memoria(st.session_state.reporte_diario, f_rep, txt_r, d)
            
            if 'img_mem' in st.session_state:
                st.image(st.session_state.img_mem, width=300)
                st.download_button("📥 Descargar", st.session_state.img_mem, "Reporte.png", "image/png", use_container_width=True)

            # BOTÓN DE GUARDAR HISTORIAL
            st.divider()
            st.caption("Base de Datos:")
            if st.button("💾 Guardar en Historial", use_container_width=True):
                if st.session_state.reporte_diario:
                    with st.spinner("Guardando en la nube..."):
                        # Pasamos USER al guardar para que vaya a la hoja correcta
                        exito = guardar_historial_db(f_rep, st.session_state.reporte_diario, usuario_actual)
                        if exito:
                            st.success(f"¡Datos guardados en historial de {usuario_actual}!")
                        else:
                            st.error("Error al conectar con Google Sheets.")
                else:
                    st.warning("El reporte está vacío.")