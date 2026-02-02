import streamlit as st
from datetime import datetime, timedelta
from database import recuperar_historial_rango

# --- DICCIONARIOS PARA TRADUCCIÓN MANUAL ---
DIAS_ES = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 
    4: "Viernes", 5: "Sábado", 6: "Domingo"
}
MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

def render_vista(usuario_actual):
    st.title("📜 Reporte de Asignaciones")
    
    # --- FILTRO DE RANGO ---
    c_filtro, c_metrics = st.columns([1, 2])
    
    with c_filtro:
        hoy = datetime.now()
        hace_semana = hoy - timedelta(days=7)
        
        rango = st.date_input(
            "📅 Seleccionar Periodo",
            value=(hace_semana, hoy),
            format="DD/MM/YYYY"
        )
    
    st.divider()

    if isinstance(rango, tuple) and len(rango) == 2:
        inicio, fin = rango
        datos = recuperar_historial_rango(usuario_actual, inicio, fin)
        
        if datos:
            # --- MÉTRICAS ---
            total_dias = len(datos)
            total_asig = sum([len(d["reporte"]) for d in datos])
            
            with c_metrics:
                m1, m2 = st.columns(2)
                m1.metric("Días Reportados", total_dias)
                m2.metric("Total Asignaciones", total_asig)
            
            # --- LISTA DE REPORTES ---
            for item in datos:
                # Convertir string a objeto fecha
                f_obj = datetime.strptime(item['fecha'], "%Y-%m-%d")
                
                # --- TRADUCCIÓN MANUAL ---
                # En vez de strftime que usa el sistema en inglés, construimos el string:
                nombre_dia = DIAS_ES[f_obj.weekday()]
                nombre_mes = MESES_ES[f_obj.month]
                fecha_bonita = f"{nombre_dia} {f_obj.day} de {nombre_mes}, {f_obj.year}"
                
                # Título del Expander
                titulo_expander = f"📅 {fecha_bonita} ({len(item['reporte'])} asignaciones)"
                
                with st.expander(titulo_expander, expanded=False):
                    
                    # Info auditoría
                    st.caption(f"📝 Creado: {item.get('creado', '--')} | 🔄 Última ed.: {item.get('actualizado', '--')}")
                    
                    # Detalles
                    for asig in item['reporte']:
                        c_nom, c_uni = st.columns([2, 3])
                        c_nom.markdown(f"**⛽ {asig['nombre']}**")
                        if asig.get('horario'):
                            c_nom.caption(f"🕒 {asig['horario']}")
                        
                        # Chips
                        html_chips = "".join([
                            f"<span style='background:#f0f2f6;padding:2px 6px;border-radius:4px;border:1px solid #ddd;font-weight:600;margin-right:4px;font-size:0.9em;display:inline-block;margin-bottom:2px;'>{u:02d}</span>" 
                            for u in asig['unidades']
                        ])
                        c_uni.markdown(html_chips, unsafe_allow_html=True)
                        st.markdown("<hr style='margin:5px 0;opacity:0.3'>", unsafe_allow_html=True)
                    
                    # Botón Editar
                    btn_col, _ = st.columns([1, 3])
                    if btn_col.button("✏️ Editar este reporte", key=f"btn_edit_{item['fecha']}"):
                        st.session_state.reporte_diario = item['reporte']
                        st.session_state.fecha_reporte_activo = f_obj
                        st.session_state.vista_actual = "Asignacion"
                        st.rerun()

        else:
            st.info("No se encontraron reportes en este rango de fechas.")
            
    else:
        st.warning("Selecciona una fecha de inicio y una de fin.")