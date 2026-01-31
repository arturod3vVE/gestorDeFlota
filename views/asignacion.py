import streamlit as st
import time
import base64
import urllib.parse
from datetime import datetime
import streamlit.components.v1 as components

from database import guardar_datos_db, guardar_historial_db, recuperar_historial_por_fecha
from image_gen import generar_imagen_en_memoria
from utils import selector_de_rangos, obtener_lista_horas_puntuales

# Función auxiliar local para el botón de WhatsApp
def boton_whatsapp_directo(img_bytes, nombre_archivo):
    b64 = base64.b64encode(img_bytes.getvalue()).decode()
    html_code = f"""
    <html>
        <head>
        <style>
            body {{ margin: 0; padding: 0; background-color: transparent; }}
            .btn-wa {{
                display: flex; align-items: center; justify-content: center;
                width: 100%; height: 2.5rem;
                background-color: #007BFF; color: white;
                font-weight: 600; border: 1px solid rgba(0,0,0,0.1);
                border-radius: 0.5rem; cursor: pointer;
                font-family: "Source Sans Pro", sans-serif;
                font-size: 1rem; text-decoration: none;
                box-sizing: border-box; white-space: nowrap;
            }}
            .btn-wa:hover {{ background-color: #0056b3; }}
            .btn-wa:active {{ transform: scale(0.98); }}
        </style>
        </head>
        <body>
            <button class="btn-wa" onclick="compartir()">📲 WhatsApp</button>
            <script>
            async function compartir() {{
                const b64 = "{b64}";
                const res = await fetch("data:image/png;base64," + b64);
                const blob = await res.blob();
                const file = new File([blob], "{nombre_archivo}", {{ type: "image/png" }});
                if (navigator.share && navigator.canShare({{ files: [file] }})) {{
                    try {{ await navigator.share({{ files: [file], title: 'Reporte', text: 'Reporte: {nombre_archivo}' }}); }} 
                    catch (err) {{ console.log(err); }}
                }} else {{ alert('Tu navegador no soporta compartir nativo.'); }}
            }}
            </script>
        </body>
    </html>
    """
    components.html(html_code, height=42)

def render_vista(usuario_actual):
    st.title("⛽ Asignación de Unidades")
    
    # Recuperamos variables globales
    d = st.session_state.datos_app
    
    # Generamos la lista total de unidades
    all_u = []
    if "rangos" in d:
        for r in d["rangos"]:
            all_u.extend(list(range(r[0], r[1] + 1)))
    all_u = sorted(list(set(all_u)))
    
    LISTA_HORAS = obtener_lista_horas_puntuales()
    if 'ed_idx' not in st.session_state: st.session_state.ed_idx = None

    # --- SELECTOR DE FECHA Y CARGA ---
    c_date, c_load, c_info = st.columns([1.5, 1, 2], vertical_alignment="bottom")
    with c_date:
        fr = st.date_input("Seleccionar Fecha", datetime.now(), key="key_fecha_rep")
    with c_load:
        if st.button("📂 Cargar Fecha", use_container_width=True):
            dt = recuperar_historial_por_fecha(fr, usuario_actual)
            if dt:
                st.session_state.reporte_diario = dt
                st.success(f"✅ Datos del {fr.strftime('%d/%m')} cargados.")
            else:
                st.session_state.reporte_diario = []
                st.info(f"ℹ️ Sin datos para {fr.strftime('%d/%m')}. Iniciando vacío.")
            time.sleep(0.5)
            st.rerun()
    with c_info:
        if st.session_state.reporte_diario:
            st.caption(f"Visualizando: **{len(st.session_state.reporte_diario)} registros**.")
        else:
            st.caption("Planilla vacía.")

    st.divider()
    
    # Cálculos de Disponibilidad
    avs = d.get("averiadas", [])
    op = [u for u in all_u if u not in avs]
    ya = [u for e in st.session_state.reporte_diario for u in e['unidades']]
    disp = [u for u in op if u not in ya]

    with st.container(border=True):
        m1,m2,m3 = st.columns(3)
        m1.metric("Total Flota", len(all_u))
        m2.metric("En Taller", len(avs), delta_color="inverse")
        m3.metric("Disponibles", len(disp))

    # --- FORMULARIO NUEVA ASIGNACIÓN ---
    with st.expander("➕ Nueva Asignación", expanded=True):
        test = d.get("estaciones", [])
        ocup = [r['nombre'] for r in st.session_state.reporte_diario]
        dis_st = [e for e in test if e not in ocup]
        
        c_st, c_tg, c_h1, c_h2 = st.columns([3, 1, 1.2, 1.2], vertical_alignment="bottom")
        
        with c_st:
            if dis_st: nom = st.selectbox("Estación", dis_st, placeholder="Selecciona...", index=None)
            else: st.warning("Sin estaciones."); nom = None
        with c_tg:
            sin_h = st.toggle("Sin horario", value=False)
        with c_h1:
            h1 = st.selectbox("Abre", LISTA_HORAS, index=LISTA_HORAS.index("09 AM") if "09 AM" in LISTA_HORAS else 0, disabled=sin_h)
        with c_h2:
            h2 = st.selectbox("Cierra", LISTA_HORAS, index=LISTA_HORAS.index("02 PM") if "02 PM" in LISTA_HORAS else 0, disabled=sin_h)

        h_str = "" if sin_h else f"{h1} a {h2}"
        
        st.markdown("---")
        st.write("**Seleccionar Unidades:**")
        sel = selector_de_rangos(disp, "main_asig", default_str=None)
        
        if st.button("💾 Guardar Asignación", type="primary", use_container_width=True):
            if nom and sel: 
                # Guardamos respetando el orden de selección (sin sort)
                st.session_state.reporte_diario.append({"nombre": nom, "horario": h_str, "unidades": sel})
                st.rerun()
            elif not nom: st.error("⚠️ Falta Estación")
            elif not sel: st.error("⚠️ Faltan Unidades")

    # --- LISTA DE REPORTES ---
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
                
                # MODO EDICIÓN
                if st.session_state.ed_idx == i:
                    st.info("✏️ Editando unidades...")
                    to_rm = st.multiselect("Quitar:", e['unidades'], key=f"md{i}")
                    if st.button("Quitar selección", key=f"brm{i}") and to_rm:
                        for x in to_rm: e['unidades'].remove(x)
                        st.rerun()
                    st.markdown("---")
                    
                    st.write("**Agregar más:**")
                    others = [u for ix, r in enumerate(st.session_state.reporte_diario) if ix != i for u in r['unidades']]
                    cands = [u for u in op if u not in others and u not in e['unidades']]
                    to_add = selector_de_rangos(cands, f"ea{i}", default_str=None)
                    if st.button("Agregar selección", key=f"bad{i}") and to_add:
                        e['unidades'].extend(to_add); st.rerun()
                    
                    st.markdown("---")
                    cambios_pendientes = (len(to_rm) > 0) or (len(to_add) > 0)
                    if cambios_pendientes:
                        st.warning(f"⚠️ Cambios sin guardar.")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("💾 Guardar y Salir", key=f"ss_{i}", type="primary", use_container_width=True):
                                if to_rm: 
                                    for x in to_rm: 
                                        if x in e['unidades']: e['unidades'].remove(x)
                                if to_add: e['unidades'].extend(to_add)
                                st.session_state.ed_idx = None
                                st.rerun()
                        with c2:
                            if st.button("🗑️ Descartar", key=f"sd_{i}", use_container_width=True):
                                st.session_state.ed_idx = None; st.rerun()
                    else:
                        if st.button("✅ Finalizar", key=f"ok_{i}", type="primary", use_container_width=True):
                            st.session_state.ed_idx = None; st.rerun()
                else:
                    st.markdown(f"<div style='display:flex;flex-wrap:wrap;gap:5px;margin-top:10px;margin-bottom:10px;'>{''.join([f'<span style=background:#eee;padding:4px;border-radius:4px;border:1px solid #ccc;font-weight:bold;>{u:02d}</span>' for u in e['unidades']])}</div>", unsafe_allow_html=True)
        
        st.divider()
        st.subheader("📤 Exportar y Compartir")
        txt_r = st.text_input("Pie de página", value="Reporte Diario")
        
        # --- GENERACIÓN ---
        btn_generar = st.button("🔄 Generar Imagen", type="primary", use_container_width=True)
        
        if btn_generar or 'img_mem' not in st.session_state:
            st.session_state.img_mem = generar_imagen_en_memoria(st.session_state.reporte_diario, fr, txt_r, d)
            if btn_generar:
                if guardar_historial_db(fr, st.session_state.reporte_diario, usuario_actual):
                    st.toast("✅ Guardado automático")
        
        if 'img_mem' in st.session_state:
            st.image(st.session_state.img_mem, caption="Vista Previa", width=350)
            nombre_img = f"Reporte_{fr.strftime('%d-%m-%Y')}.png"
            c1, c2 = st.columns(2)
            with c1:
                boton_whatsapp_directo(st.session_state.img_mem, nombre_img)
            with c2:
                st.download_button("📥 Descargar", st.session_state.img_mem, nombre_img, "image/png", use_container_width=True)

        st.markdown("---")
        with st.expander("Opciones de Texto"):
            msg_wa = f"*REPORTE DE FLOTA - {fr.strftime('%d/%m/%Y')}*\n_{usuario_actual.upper()}_\n\n"
            for item in st.session_state.reporte_diario:
                msg_wa += f"⛽ *{item['nombre'].upper()}*\n"
                if item['horario']: msg_wa += f"🕒 {item['horario']}\n"
                unidades_str = ", ".join([str(u) for u in item['unidades']])
                msg_wa += f"🚛 {unidades_str}\n\n"
            if txt_r: msg_wa += f"ℹ️ _{txt_r}_"
            msg_encoded = urllib.parse.quote(msg_wa)
            st.link_button("💬 Enviar Resumen Texto", f"https://wa.me/?text={msg_encoded}")
