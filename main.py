import streamlit as st
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importamos la nueva función
from utils import inyectar_css, verificar_login, verificar_fase_cierre
from database import cargar_datos_db, recuperar_historial_por_fecha
from views import asignacion, taller, configuracion

# 1. Configuración de página
st.set_page_config(page_title="Gestor de Flota", page_icon="⛽", layout="wide")

# 2. [NUEVO] Verificar si estamos en fase de salida ANTES DE CARGAR NADA
# Si esto es True, el script se detendrá aquí mostrando solo el autobús.
verificar_fase_cierre()

# 3. Resto de la app normal
inyectar_css()
is_authenticated, cookie_manager = verificar_login()

if is_authenticated:
    usuario_actual = st.session_state.usuario_actual
    
    if 'vista_actual' not in st.session_state: st.session_state.vista_actual = "Asignacion"
    def cambiar_vista(nueva_vista): st.session_state.vista_actual = nueva_vista

    # Datos globales
    if 'datos_app' not in st.session_state:
        st.session_state.datos_app = cargar_datos_db(usuario_actual)
        if "rangos" not in st.session_state.datos_app: st.session_state.datos_app["rangos"] = [[1, 100]]
        # (Resto de validaciones de datos...)

    if 'reporte_diario' not in st.session_state:
        from datetime import datetime
        hoy = datetime.now()
        datos = recuperar_historial_por_fecha(hoy, usuario_actual)
        st.session_state.reporte_diario = datos if datos else []

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("Panel de Control")
        st.info(f"👤 **{usuario_actual.capitalize()}**")
        st.divider()
        
        st.button("⛽ Asignación", type=("primary" if st.session_state.vista_actual=="Asignacion" else "secondary"), use_container_width=True, on_click=cambiar_vista, args=("Asignacion",))
        st.button("🔧 Taller", type=("primary" if st.session_state.vista_actual=="Taller" else "secondary"), use_container_width=True, on_click=cambiar_vista, args=("Taller",))
        st.button("⚙️ Configuración", type=("primary" if st.session_state.vista_actual=="Configuracion" else "secondary"), use_container_width=True, on_click=cambiar_vista, args=("Configuracion",))
        
        st.divider()
        st.write("🔄 **Sincronización**")
        modo_vivo = st.toggle("📡 Modo Vivo", value=False)
        if st.button("🔄 Recargar Manual", use_container_width=True):
            if 'datos_app' in st.session_state: del st.session_state['datos_app']
            if 'reporte_diario' in st.session_state: del st.session_state['reporte_diario']
            st.rerun()
            
        st.write("") 
        
        # --- LOGOUT MODIFICADO ---
        # Ahora el botón es muy simple: solo activa la bandera y recarga.
        with st.popover("🚪 Cerrar Sesión", use_container_width=True):
            st.markdown("¿Salir del sistema?")
            if st.button("✅ Confirmar Salida", type="primary", use_container_width=True):
                # Solo marcamos la bandera. 
                # La función verificar_fase_cierre() al inicio del script hará el trabajo sucio en la siguiente recarga.
                st.session_state["fase_salida"] = True
                st.rerun()

    # --- RUTEO ---
    if st.session_state.vista_actual == "Asignacion": asignacion.render_vista(usuario_actual)
    elif st.session_state.vista_actual == "Taller": taller.render_vista(usuario_actual)
    elif st.session_state.vista_actual == "Configuracion": configuracion.render_vista(usuario_actual)

    if modo_vivo:
        time.sleep(10)
        if 'datos_app' in st.session_state: del st.session_state['datos_app']
        st.rerun()
