import streamlit as st
import time
import sys
import os

# --- CORRECCIÓN DE IMPORTS GLOBAL ---
# Aseguramos que Python encuentre los módulos siempre
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import inyectar_css, verificar_login
from database import cargar_datos_db, recuperar_historial_por_fecha

# IMPORTAMOS LAS VISTAS
# (Asegúrate de haber aplicado el PASO 1 en estos archivos también)
from views import asignacion, taller, configuracion

# 1. Configuración de la página
st.set_page_config(page_title="Gestor de Flota", page_icon="⛽", layout="wide")
inyectar_css()

# 2. Control de Acceso
is_authenticated, cookie_manager = verificar_login()

if is_authenticated:
    usuario_actual = st.session_state.usuario_actual
    
    # Inicializar navegación
    if 'vista_actual' not in st.session_state:
        st.session_state.vista_actual = "Asignacion"

    def cambiar_vista(nueva_vista):
        st.session_state.vista_actual = nueva_vista

    # --- LÓGICA DE DATOS GLOBAL ---
    # Cargamos datos frescos en cada reinicio si el heartbeat lo pide
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
        from datetime import datetime
        hoy = datetime.now()
        datos_hoy = recuperar_historial_por_fecha(hoy, usuario_actual)
        st.session_state.reporte_diario = datos_hoy if datos_hoy else []

    # --- MENÚ LATERAL ---
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
        
        # --- HEARTBEAT / AUTO-REFRESH ---
        st.write("🔄 **Sincronización**")
        # El usuario puede activar esto si está monitoreando en tiempo real
        modo_vivo = st.toggle("📡 Modo Vivo (Auto-update)", value=False, help="Actualiza la pantalla cada 10 segundos para ver cambios hechos desde otros dispositivos.")
        
        if st.button("🔄 Recargar Manual", use_container_width=True):
            if 'datos_app' in st.session_state: del st.session_state['datos_app']
            if 'reporte_diario' in st.session_state: del st.session_state['reporte_diario']
            st.toast("☁️ Datos actualizados")
            st.rerun()
        
        st.write("") 
        
        # Logout
        with st.popover("🚪 Cerrar Sesión", use_container_width=True):
            st.markdown("¿Salir del sistema?")
            if st.button("✅ Confirmar", type="primary", use_container_width=True):
                # 1. Limpieza Python (Backend)
                st.session_state.clear()
                st.session_state["logout_pending"] = True
                
                # 2. Mensaje visual
                st.warning("Cerrando sesión de forma segura...")
                
                # 3. Limpieza Navegador (Frontend - JS)
                # Importamos la función aquí mismo para usarla
                from utils import ejecutar_logout_hardcore
                ejecutar_logout_hardcore()

    # --- RUTEO DE VISTAS ---
    if st.session_state.vista_actual == "Asignacion":
        asignacion.render_vista(usuario_actual)
    
    elif st.session_state.vista_actual == "Taller":
        taller.render_vista(usuario_actual)
        
    elif st.session_state.vista_actual == "Configuracion":
        configuracion.render_vista(usuario_actual)

    # --- LÓGICA DEL HEARTBEAT ---
    # Si el Modo Vivo está activo, esperamos y recargamos
    if modo_vivo:
        time.sleep(10) # Espera 10 segundos
        # Borramos caché local para forzar la lectura de DB
        if 'datos_app' in st.session_state: del st.session_state['datos_app']
        # NOTA: No borramos reporte_diario aquí para no perder la fecha seleccionada en Asignación,
        # pero Taller sí se beneficiará de borrar 'datos_app' (donde están las averías).
        st.rerun()
