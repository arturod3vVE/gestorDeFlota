import streamlit as st
import base64
import urllib.parse
import threading
from datetime import datetime
import streamlit.components.v1 as components

from database import guardar_historial_db, recuperar_historial_por_fecha, eliminar_historial_por_fecha, obtener_fecha_creacion_original
from image_gen import generar_imagen_en_memoria
from utils import selector_de_rangos, obtener_lista_horas_puntuales

# --- WORKER (HILO) ---
def worker_guardar_db(fecha, reporte, usuario, sobrescribir):
    try:
        fecha_creacion_original = None
        if sobrescribir:
            fecha_creacion_original = obtener_fecha_creacion_original(fecha, usuario)
            eliminar_historial_por_fecha(fecha, usuario)
            
        guardar_historial_db(fecha, reporte, usuario, fecha_creacion_preservada=fecha_creacion_original)
        print(f"✅ [Segundo Plano] Guardado completado para {usuario}")
    except Exception as e:
        print(f"❌ [Segundo Plano] Error: {e}")

# --- JS SCROLL ---
def inyectar_scroll_js():
    js = """
    <script>
        function intentarScroll(intentos) {
            var element = window.parent.document.getElementById('target_imagen');
            if (element) {
                element.style.scrollMarginTop = '80px';
                element.scrollIntoView({behavior: 'smooth', block: 'start'});
            } else if (intentos > 0) {
                setTimeout(function() { intentarScroll(intentos - 1); }, 50);
            }
        }
        intentarScroll(20);
    </script>
    """
    components.html(js, height=0, width=0)

# --- CALLBACK SIMPLE ---
def trigger_accion_guardar(tipo):
    st.session_state.accion_guardar_pendiente = tipo

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
                background-color: #25D366; color: black;
                font-weight: 600; border: 1px solid rgba(0,0,0,0.1);
                border-radius: 0.5rem; cursor: pointer;
                font-family: "Source Sans Pro", sans-serif;
                font-size: 1rem; text-decoration: none;
                box-sizing: border-box; white-space: nowrap;
            }}
            .btn-wa:hover {{ background-color: #1ebe57; }}
            .btn-wa:active {{ transform: scale(0.98); }}
        </style>
        </head>
        <body>
            <button class="btn-wa" onclick="compartir()">📲 Enviar WhatsApp</button>
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
    
    d = st.session_state.datos_app
    
    all_u = []
    if "rangos" in d:
        for r in d["rangos"]:
            all_u.extend(list(range(r[0], r[1] + 1)))
    all_u = sorted(list(set(all_u)))
    
    LISTA_HORAS = obtener_lista_horas_puntuales()
    if 'ed_idx' not in st.session_state: st.session_state.ed_idx = None
    
    fecha_defecto = datetime.now()
    if 'fecha_reporte_activo' in st.session_state:
        fecha_defecto = st.session_state.fecha_reporte_activo

    c_date, c_info = st.columns([1, 2], vertical_alignment="bottom")
    with c_date:
        fr = st.date_input("Fecha de Trabajo", value=fecha_defecto, key="key_fecha_rep")
        st.session_state.fecha_reporte_activo = fr
        
    with c_info:
        if st.session_state.reporte_diario:
            st.info(f"📝 Editando reporte con **{len(st.session_state.reporte_diario)} asignaciones**.")
        else:
            st.caption("Planilla vacía. Comienza a asignar.")

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
                st.session_state.reporte_diario.append({"nombre": nom, "horario": h_str, "unidades": sel})
                st.rerun()
            elif not nom: st.error("⚠️ Falta Estación")
            elif not sel: st.error("⚠️ Faltan Unidades")

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
                    st.info(f"✏️ Editando: **{e['nombre']}**")
                    
                    st.markdown("###### 🕒 Horario")
                    horario_actual = e.get('horario', "")
                    es_sin_horario = not horario_actual
                    
                    idx_apertura = 0
                    idx_cierre = 0
                    if not es_sin_horario and " a " in horario_actual:
                        partes = horario_actual.split(" a ")
                        if len(partes) == 2:
                            try: idx_apertura = LISTA_HORAS.index(partes[0])
                            except: pass
                            try: idx_cierre = LISTA_HORAS.index(partes[1])
                            except: pass
                    
                    col_tg_ed, col_h1_ed, col_h2_ed = st.columns([1, 1.5, 1.5], vertical_alignment="bottom")
                    with col_tg_ed:
                        sin_h_ed = st.checkbox("Sin hora", value=es_sin_horario, key=f"she_{i}")
                    with col_h1_ed:
                        h1_ed = st.selectbox("Abre", LISTA_HORAS, index=idx_apertura, key=f"h1e_{i}", disabled=sin_h_ed)
                    with col_h2_ed:
                        h2_ed = st.selectbox("Cierra", LISTA_HORAS, index=idx_cierre, key=f"h2e_{i}", disabled=sin_h_ed)

                    st.markdown("---")
                    st.markdown("###### 🚛 Unidades")
                    to_rm = st.multiselect("Quitar:", e['unidades'], key=f"md{i}")
                    if st.button("Quitar selección", key=f"brm{i}") and to_rm:
                        for x in to_rm: e['unidades'].remove(x)
                        st.rerun()
                    
                    others = [u for ix, r in enumerate(st.session_state.reporte_diario) if ix != i for u in r['unidades']]
                    cands = [u for u in op if u not in others and u not in e['unidades']]
                    to_add = selector_de_rangos(cands, f"ea{i}", default_str=None)
                    if st.button("Agregar selección", key=f"bad{i}") and to_add:
                        e['unidades'].extend(to_add); st.rerun()
                    
                    st.markdown("---")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("💾 Guardar Cambios", key=f"ss_{i}", type="primary", use_container_width=True):
                            if to_rm: 
                                for x in to_rm: 
                                    if x in e['unidades']: e['unidades'].remove(x)
                            if to_add: e['unidades'].extend(to_add)
                            
                            if sin_h_ed: e['horario'] = ""
                            else: e['horario'] = f"{h1_ed} a {h2_ed}"
                            
                            st.session_state.ed_idx = None
                            st.rerun()
                    with c2:
                        if st.button("✅ Listo / Cancelar", key=f"ok_{i}", use_container_width=True):
                            st.session_state.ed_idx = None; st.rerun()
                else:
                    st.markdown(f"<div style='display:flex;flex-wrap:wrap;gap:5px;margin-top:10px;margin-bottom:10px;'>{''.join([f'<span style=background:#eee;padding:4px;border-radius:4px;border:1px solid #ccc;font-weight:bold;>{u:02d}</span>' for u in e['unidades']])}</div>", unsafe_allow_html=True)
        
        st.divider()
        st.subheader("📤 Exportar y Finalizar")

        texto_auto = "Reporte Diario"
        
        reporte = st.session_state.reporte_diario
        if reporte:
            try:
                primer_registro = reporte[0]
                u_inicio = primer_registro['unidades'][0] if primer_registro['unidades'] else None
                
                ultimo_registro = reporte[-1]
                u_fin = ultimo_registro['unidades'][-1] if ultimo_registro['unidades'] else None
                
                if u_inicio is not None and u_fin is not None:
                    texto_auto = f"DESDE {u_inicio:02d} AL {u_fin:02d}"
            except:
                pass 

        txt_r = st.text_input("Pie de página (Texto Rango)", value=texto_auto)
    
        cache_key = f"db_hist_{fr.strftime('%Y%m%d')}_{usuario_actual}"
        if cache_key not in st.session_state:
            st.session_state[cache_key] = recuperar_historial_por_fecha(fr, usuario_actual)
        existe_previo = st.session_state[cache_key]

        contenedor_botonera = st.empty()
        
        with contenedor_botonera:
            with st.popover("💾 GUARDAR Y GENERAR IMAGEN", use_container_width=True, help="Guarda en DB y crea la imagen"):
                st.markdown(f"Reporte: **{fr.strftime('%d/%m/%Y')}**")

                if existe_previo:
                    st.error("⚠️ ¡ALERTA! Ya existe un registro.")
                    st.button("🚨 SOBRESCRIBIR Y GENERAR", 
                              type="primary", 
                              use_container_width=True, 
                              on_click=trigger_accion_guardar, 
                              args=("overwrite",))
                else:
                    st.success("✅ Fecha disponible.")
                    st.button("Confirmar y Generar", 
                              type="primary", 
                              use_container_width=True, 
                              on_click=trigger_accion_guardar, 
                              args=("new",))

        if st.session_state.get("accion_guardar_pendiente"):
            
            contenedor_botonera.empty()
            
            tipo = st.session_state.accion_guardar_pendiente
            st.session_state.accion_guardar_pendiente = None 
            
            st.session_state[cache_key] = st.session_state.reporte_diario
            img = generar_imagen_en_memoria(st.session_state.reporte_diario, fr, txt_r, d)
            st.session_state.img_mem = img
            
            sobrescribir = (tipo == "overwrite")
            hilo = threading.Thread(
                target=worker_guardar_db, 
                args=(fr, st.session_state.reporte_diario, usuario_actual, sobrescribir),
                daemon=True
            )
            hilo.start()
            
            st.session_state.hacer_scroll_imagen = True
            st.toast("✅ Generado. Guardando en segundo plano...")

        if 'img_mem' in st.session_state:
            st.markdown("<div id='target_imagen'></div>", unsafe_allow_html=True)
            
            if st.session_state.get("hacer_scroll_imagen", False):
                inyectar_scroll_js()
                st.session_state.hacer_scroll_imagen = False 

            st.markdown("---")
            st.success("📸 **Vista Previa Generada**")
            st.image(st.session_state.img_mem, width=450)
            
            nombre_img = f"Reporte_{fr.strftime('%d-%m-%Y')}.png"
            c1, c2 = st.columns(2)
            with c1:
                boton_whatsapp_directo(st.session_state.img_mem, nombre_img)
            with c2:
                st.download_button("📥 Descargar PNG", st.session_state.img_mem, nombre_img, "image/png", use_container_width=True)

        st.markdown("---")
        with st.expander("Opciones de Texto (Respaldo)"):
            msg_wa = f"*REPORTE DE FLOTA - {fr.strftime('%d/%m/%Y')}*\n_{usuario_actual.upper()}_\n\n"
            for item in st.session_state.reporte_diario:
                msg_wa += f"⛽ *{item['nombre'].upper()}*\n"
                if item['horario']: msg_wa += f"🕒 {item['horario']}\n"
                unidades_str = ", ".join([str(u) for u in item['unidades']])
                msg_wa += f"🚛 {unidades_str}\n\n"
            if txt_r: msg_wa += f"ℹ️ _{txt_r}_"
            msg_encoded = urllib.parse.quote(msg_wa)
            st.link_button("💬 Enviar Resumen Texto", f"https://wa.me/?text={msg_encoded}")