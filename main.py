import streamlit as st
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import inyectar_css, verificar_login, verificar_fase_cierre, mostrar_bus_loading
from database import cargar_datos_db, recuperar_historial_por_fecha
from image_gen import obtener_recursos_graficos 
from views import asignacion, taller, configuracion, historial

# 1. Configuración
st.set_page_config(page_title="Gestor de Flota", page_icon="⛽", layout="wide")

# 2. Verificar cierre
verificar_fase_cierre()

# 3. Pre-carga
obtener_recursos_graficos() 

# 4. Estilos y Auth
inyectar_css()
is_authenticated, cookie_manager = verificar_login()

if is_authenticated:
    # --- 🧠 LÓGICA INTELIGENTE DE CARGA ---
    if 'vista_actual' not in st.session_state: st.session_state.vista_actual = "Asignacion"
    
    # Variable para rastrear dónde estábamos antes
    if 'vista_anterior' not in st.session_state: st.session_state.vista_anterior = None
    
    # Decidimos si mostrar el autobús
    debe_mostrar_loader = False
    
    # CASO 1: Cambio de vista (ej: Asignación -> Taller)
    if st.session_state.vista_actual != st.session_state.vista_anterior:
        debe_mostrar_loader = True
        st.session_state.vista_anterior = st.session_state.vista_actual # Actualizamos para la próxima
        
    # CASO 2: Recarga manual forzada (Botón del sidebar)
    if st.session_state.get("force_reload"):
        debe_mostrar_loader = True
        st.session_state.force_reload = False

    # --- RENDERIZAR LOADER (SOLO SI ES NECESARIO) ---
    loader_placeholder = st.empty()
    if debe_mostrar_loader:
        with loader_placeholder:
            mostrar_bus_loading()

    # --- LÓGICA DE LA APP ---
    usuario_actual = st.session_state.usuario_actual
    
    def cambiar_vista(nueva_vista): st.session_state.vista_actual = nueva_vista

    if 'datos_app' not in st.session_state:
        st.session_state.datos_app = cargar_datos_db(usuario_actual)
        if "rangos" not in st.session_state.datos_app: st.session_state.datos_app["rangos"] = [[1, 100]]

    if 'reporte_diario' not in st.session_state: st.session_state.reporte_diario = [] 

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("Panel de Control")
        st.info(f"👤 **{usuario_actual.capitalize()}**")
        st.divider()
        
        st.button("⛽ Asignación", type=("primary" if st.session_state.vista_actual=="Asignacion" else "secondary"), use_container_width=True, on_click=cambiar_vista, args=("Asignacion",))
        st.button("🔧 Taller", type=("primary" if st.session_state.vista_actual=="Taller" else "secondary"), use_container_width=True, on_click=cambiar_vista, args=("Taller",))
        st.button("📜 Historial", type=("primary" if st.session_state.vista_actual=="Historial" else "secondary"), use_container_width=True, on_click=cambiar_vista, args=("Historial",))
        st.button("⚙️ Configuración", type=("primary" if st.session_state.vista_actual=="Configuracion" else "secondary"), use_container_width=True, on_click=cambiar_vista, args=("Configuracion",))
        
        st.divider()
        st.write("🔄 **Sincronización**")
        modo_vivo = st.toggle("📡 Modo Vivo", value=False)
        
        # Botón especial que SÍ activa el autobús
        if st.button("🔄 Recargar Manual", use_container_width=True):
            if 'datos_app' in st.session_state: del st.session_state['datos_app']
            if 'reporte_diario' in st.session_state: del st.session_state['reporte_diario']
            st.session_state.force_reload = True # Activamos bandera
            st.rerun()
            
        st.write("") 
        with st.popover("🚪 Cerrar Sesión", use_container_width=True):
            st.markdown("¿Salir del sistema?")
            if st.button("✅ Confirmar Salida", type="primary", use_container_width=True):
                st.session_state["fase_salida"] = True
                st.rerun()

    # --- RUTEO ---
    if st.session_state.vista_actual == "Asignacion": asignacion.render_vista(usuario_actual)
    elif st.session_state.vista_actual == "Taller": taller.render_vista(usuario_actual)
    elif st.session_state.vista_actual == "Historial": historial.render_vista(usuario_actual)
    elif st.session_state.vista_actual == "Configuracion": configuracion.render_vista(usuario_actual)

    if modo_vivo:
        time.sleep(10)
        if 'datos_app' in st.session_state: del st.session_state['datos_app']
        st.rerun()

    if debe_mostrar_loader:
        time.sleep(0.5)
        loader_placeholder.empty()