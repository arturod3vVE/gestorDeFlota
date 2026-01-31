import streamlit as st
from database import guardar_datos_db
from image_gen import generar_imagen_en_memoria
from datetime import datetime

# ESTA ES LA FUNCIÓN QUE PYTHON NO ENCUENTRA
def render_vista(usuario_actual):
    st.title("⚙️ Configuración")
    
    d = st.session_state.datos_app
    
    # Inicialización de defaults visuales
    if "k_width" not in st.session_state: st.session_state.k_width = d.get("img_width", 450)
    if "k_font" not in st.session_state: st.session_state.k_font = d.get("font_size", 24)
    if "k_bg" not in st.session_state: st.session_state.k_bg = d.get("bg_color", "#ECE5DD")
    if "k_text" not in st.session_state: st.session_state.k_text = d.get("text_color", "#000000")
    db_colors = d.get("st_colors", ["#f8d7da"]*6)
    for i in range(6):
        if f"k_c_{i}" not in st.session_state: st.session_state[f"k_c_{i}"] = db_colors[i]

    def guardar():
        return guardar_datos_db(d, usuario_actual)

    def revertir_cambios():
        st.session_state.k_width = d.get("img_width", 450)
        st.session_state.k_font = d.get("font_size", 24)
        st.session_state.k_bg = d.get("bg_color", "#ECE5DD")
        st.session_state.k_text = d.get("text_color", "#000000")
        rc = d.get("st_colors", ["#f8d7da"]*6)
        for i in range(6): st.session_state[f"k_c_{i}"] = rc[i]
        st.toast("↺ Restaurado")

    mostrar_preview = st.toggle("👁️ Mostrar Vista Previa en tiempo real", value=False)
    st.markdown("---")
    
    if mostrar_preview:
        col_config, col_preview = st.columns([1.5, 1])
    else:
        col_config = st.container()
        col_preview = None
    
    with col_config:
        # 1. RANGOS
        with st.expander("📍 1. Rangos de Flota", expanded=True):
            rangos_actuales = d.get("rangos", [])
            if rangos_actuales:
                st.caption("Rangos activos:")
                for i, r in enumerate(rangos_actuales):
                    c_info, c_action = st.columns([5, 1], vertical_alignment="center")
                    c_info.code(f"{r[0]} ➝ {r[1]}")
                    with c_action.popover("🗑️"):
                        st.write("¿Borrar?")
                        if st.button("Sí", key=f"del_r_{i}", type="primary", use_container_width=True):
                            d["rangos"].pop(i); guardar(); st.rerun()
            else: st.info("Sin rangos.")
            
            st.divider()
            st.caption("➕ Crear rango:")
            c_n1, c_n2, c_btn = st.columns([2, 2, 2], vertical_alignment="bottom")
            n_min = c_n1.number_input("Desde", min_value=1, value=1)
            n_max = c_n2.number_input("Hasta", min_value=1, value=100)
            if c_btn.button("Agregar", type="primary", use_container_width=True):
                if n_max < n_min: st.error("Error: Fin < Inicio.")
                else:
                    d["rangos"].append([n_min, n_max]); d["rangos"].sort(key=lambda x: x[0])
                    guardar(); st.rerun()

        # 2. APARIENCIA
        with st.expander("🎨 2. Apariencia", expanded=False):
            c3, c4 = st.columns(2)
            ni = c3.slider("Ancho", 300, 800, key="k_width")
            nf = c4.slider("Fuente", 14, 40, key="k_font")
            st.write("**Colores:**")
            cc1, cc2 = st.columns(2)
            nuevo_bg = cc1.color_picker("Fondo", key="k_bg")
            nuevo_text = cc2.color_picker("Texto", key="k_text")
            st.write("**Estaciones:**")
            nuevos_st_colors = []
            f1 = st.columns(3)
            for i in range(3): nuevos_st_colors.append(f1[i].color_picker(f"C{i+1}", key=f"k_c_{i}"))
            f2 = st.columns(3)
            for i in range(3, 6): nuevos_st_colors.append(f2[i-3].color_picker(f"C{i+4}", key=f"k_c_{i}"))
            
            st.divider()
            b_save, b_cancel = st.columns([1, 1])
            with b_save:
                if st.button("💾 Guardar", type="primary", width='stretch'):
                    d["img_width"] = ni; d["font_size"] = nf
                    d["bg_color"] = nuevo_bg; d["text_color"] = nuevo_text
                    d["st_colors"] = nuevos_st_colors
                    if guardar(): st.success("Guardado!"); st.rerun()
            with b_cancel:
                st.button("✖️ Restaurar", type="secondary", width='stretch', on_click=revertir_cambios)

        # 3. ESTACIONES
        with st.expander("⛽ 3. Gestión Estaciones", expanded=False):
            c_add, c_del = st.columns(2, gap="large")
            with c_add:
                st.write("**:green[➕] Nueva**")
                nueva = st.text_input("Nombre:", key="in_st")
                if st.button("Guardar Estación", use_container_width=True):
                    if nueva:
                        d.setdefault("estaciones", []).append(nueva.strip())
                        guardar(); st.rerun()
            with c_del:
                st.write("**:red[🗑️] Borrar**")
                ests = d.get("estaciones", [])
                rem = st.multiselect("Seleccionar:", ests)
                with st.popover("Confirmar Borrado", use_container_width=True, disabled=not rem):
                    if st.button("Sí, borrar", type="primary", use_container_width=True):
                        for x in rem: 
                            if x in d["estaciones"]: d["estaciones"].remove(x)
                        guardar(); st.rerun()

    if col_preview:
        with col_preview:
            st.subheader("👁️ Vista Previa")
            with st.container(border=True):
                r_txt = " / ".join([f"{r[0]}-{r[1]}" for r in d.get("rangos",[])])
                u_demo = list(range(1, 6))
                datos_demo = [{"nombre": "Estación Demo", "horario": "9 AM - 2 PM", "unidades": u_demo}]
                cfg_temp = d.copy()
                cfg_temp.update({"img_width": ni, "font_size": nf, "bg_color": nuevo_bg, "text_color": nuevo_text, "st_colors": nuevos_st_colors})
                
                try:
                    img = generar_imagen_en_memoria(datos_demo, datetime.now(), f"Flota: {r_txt}", cfg_temp)
                    st.image(img, width=350)
                except Exception as e: st.error(str(e))
