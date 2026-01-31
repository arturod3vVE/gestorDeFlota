import streamlit as st
import time
from database import guardar_datos_db
from utils import selector_de_rangos

def render_vista(usuario_actual):
    st.title("🔧 Taller de Mantenimiento")
    
    d = st.session_state.datos_app
    avs = d.get("averiadas", [])
    
    # Generamos todas las unidades
    all_u = []
    if "rangos" in d:
        for r in d["rangos"]:
            all_u.extend(list(range(r[0], r[1] + 1)))
    all_u = sorted(list(set(all_u)))
    
    sanas = [u for u in all_u if u not in avs]
    
    # Función auxiliar para guardar
    def guardar(): 
        guardar_datos_db(d, usuario_actual)

    # --- VISOR DE FLOTA GLOBAL ---
    with st.expander("👀 Ver Estado General de la Flota", expanded=False):
        ya_ocupadas = [u for e in st.session_state.reporte_diario for u in e['unidades']]
        set_taller = set(avs)
        set_ocupadas = set(ya_ocupadas)
        
        st.markdown("""
        <div style='margin-bottom:15px; font-size:0.9rem;'>
            <span style='margin-right:15px;'>🔵 <b>Disponible</b></span>
            <span style='margin-right:15px;'>🟢 <b>Asignada</b></span>
            <span style='color:#ff4b4b'>🔴 <b>En Taller</b></span>
        </div>
        """, unsafe_allow_html=True)

        html_grid = "<div style='display:flex; flex-wrap:wrap; gap:6px;'>"
        for u in all_u:
            if u in set_taller:
                bg = "#ff4b4b"; tip = "En Taller"
            elif u in set_ocupadas:
                bg = "#28a745"; tip = "Asignada"
            else:
                bg = "#007bff"; tip = "Disponible"
            
            html_grid += f"<div style='background-color:{bg}; color:white; width:32px; height:32px; display:flex; align-items:center; justify-content:center; border-radius:4px; font-weight:bold; font-size:13px; cursor:default;' title='Unidad {u}: {tip}'>{u}</div>"
        
        html_grid += "</div>"
        st.markdown(html_grid, unsafe_allow_html=True)
    
    st.divider()

    # --- MATRIZ INTERACTIVA ROJA (SALIDA TALLER) ---
    if avs:
        st.subheader("🔴 En Taller (Click para Habilitar)")
        st.info("👇 Click en una unidad para marcarla como **Disponible**.")
        
        cols = st.columns(6)
        for i, u in enumerate(avs):
            if cols[i % 6].button(f"🛠️ {u}", key=f"fix_{u}", use_container_width=True, type="primary"):
                d["averiadas"].remove(u)
                guardar()
                st.toast(f"✅ Unidad {u} reparada.")
                time.sleep(0.2)
                st.rerun()
    else:
        st.success("✅ No hay unidades en taller.")

    st.divider()

    # --- MATRIZ INTERACTIVA AZUL (ENTRADA TALLER) ---
    with st.expander("🔵 Reportar Avería (Click para enviar a Taller)", expanded=False):
        st.warning("👇 Click en una unidad para enviarla a **Taller**.")
        
        cols_sanas = st.columns(8)
        for i, u in enumerate(sanas):
            if cols_sanas[i % 8].button(f"🚛 {u}", key=f"break_{u}", use_container_width=True):
                d.setdefault("averiadas", []).append(u)
                d["averiadas"].sort()
                guardar()
                st.toast(f"⚠️ Unidad {u} enviada a taller.")
                time.sleep(0.2)
                st.rerun()
