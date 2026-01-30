import streamlit as st
from datetime import datetime

def inyectar_css():
    st.markdown("""
        <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            .stApp { margin-top: -60px; }
        </style>
    """, unsafe_allow_html=True)

def verificar_login():
    if 'autenticado' not in st.session_state: st.session_state.autenticado = False
    if not st.session_state.autenticado:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🔒 Acceso")
            with st.form("login_form"):
                pwd = st.text_input("Contraseña", type="password")
                submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
            
            if submitted:
                # Accedemos a los datos cargados en session_state desde main
                if pwd == st.session_state.datos_app.get("password", "admin"):
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta")
        return False
    return True

# --- MODIFICACIÓN AQUÍ: Horas limpias (9 AM, 10 AM...) ---
def obtener_lista_horas_puntuales():
    horas = []
    # Generamos las 24 horas del día
    for h in range(24):
        # %I: Hora 12h (01-12)
        # %p: AM/PM
        # lstrip('0'): Quita el cero inicial (09 AM -> 9 AM)
        t = datetime(2000, 1, 1, h, 0).strftime("%I %p").lstrip('0')
        horas.append(t)
    return horas

def selector_de_rangos(pool_unidades, key_unico):
    if not pool_unidades:
        st.caption("No hay unidades disponibles."); return []
    
    pool_sorted = sorted(pool_unidades)
    grupos = {}
    for u in pool_sorted:
        inicio_rango = ((u - 1) // 100) * 100 + 1
        fin_rango = inicio_rango + 99
        nombre_rango = f"{inicio_rango}-{fin_rango}"
        if nombre_rango not in grupos: grupos[nombre_rango] = []
        grupos[nombre_rango].append(u)
    
    nombres_tabs = list(grupos.keys())
    tabs = st.tabs(nombres_tabs)
    seleccion_total = []
    
    for i, nombre_tab in enumerate(nombres_tabs):
        with tabs[i]:
            sel = st.multiselect(f"Selecciona ({nombre_tab}):", grupos[nombre_tab], key=f"multi_{key_unico}_{nombre_tab}")
            seleccion_total.extend(sel)
    return seleccion_total