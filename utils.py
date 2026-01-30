import streamlit as st
import pyotp
import qrcode
import time
from io import BytesIO
from datetime import datetime, timedelta
import extra_streamlit_components as stx
from database import validar_usuario_db, registrar_usuario_con_totp, restablecer_con_totp

def inyectar_css():
    st.markdown("""
        <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

def get_cookie_manager():
    return stx.CookieManager(key="gestor_cookies_flota")

# --- FUNCIÓN DE LOADER ANIMADO ---
def mostrar_bus_loading():
    """Muestra una animación CSS de un autobús viajando."""
    loading_html = """
    <style>
        .loader-container {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 200px;
            width: 100%;
            overflow: hidden;
            background-color: transparent;
        }
        .bus-wrapper {
            font-size: 60px;
            animation: drive 2.5s infinite linear;
            position: relative;
        }
        .loading-text {
            margin-top: 10px;
            font-family: sans-serif;
            color: #666;
            font-weight: bold;
            font-size: 16px;
            animation: blink 1.5s infinite;
        }
        @keyframes drive {
            0% { transform: translateX(-150%); }
            100% { transform: translateX(150%); }
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>
    <div class="loader-container">
        <div class="bus-wrapper">🚌💨</div>
        <div class="loading-text">Cargando flota...</div>
    </div>
    """
    return st.markdown(loading_html, unsafe_allow_html=True)

def verificar_login():
    """
    Retorna una tupla: (Estado_Autenticacion (bool), Objeto_Cookie_Manager)
    """
    # 1. Creamos un placeholder para la animación
    loader_placeholder = st.empty()
    
    # 2. Mostramos el autobús MIENTRAS cargamos el manager
    # (Solo si no estamos autenticados aún, para no molestar en cada interacción pequeña)
    if 'autenticado' not in st.session_state or not st.session_state.autenticado:
        with loader_placeholder:
            mostrar_bus_loading()
    
    # 3. Inicializamos el gestor y buscamos la cookie
    cookie_manager = get_cookie_manager()
    cookie_user = cookie_manager.get(cookie="gestor_flota_user")
    
    # Una vez cargado, limpiamos la animación inmediatamente
    loader_placeholder.empty()

    # Inicializamos variables
    if 'autenticado' not in st.session_state: st.session_state.autenticado = False
    if 'usuario_actual' not in st.session_state: st.session_state.usuario_actual = None

    # Lógica de Autologin
    if cookie_user and not st.session_state.autenticado:
        st.session_state.autenticado = True
        st.session_state.usuario_actual = cookie_user

    if st.session_state.autenticado:
        return True, cookie_manager

    # --- LOGIN ---
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Gestor de Flota ⛽")
        tab_login, tab_registro, tab_recuperar = st.tabs(["🔒 Entrar", "📲 Registro 2FA", "🔄 Recuperar"])
        
        with tab_login:
            with st.form("login_form"):
                user = st.text_input("Usuario", key="l_u")
                pwd = st.text_input("Contraseña", type="password", key="l_p")
                mantener = st.checkbox("Mantener sesión iniciada", value=True)
                btn_in = st.form_submit_button("Iniciar Sesión", type="primary", use_container_width=True)
            
            if btn_in:
                if validar_usuario_db(user, pwd):
                    st.session_state.autenticado = True
                    st.session_state.usuario_actual = user.lower().strip()
                    
                    if mantener:
                        cookie_manager.set("gestor_flota_user", user.lower().strip(), expires_at=datetime.now() + timedelta(days=30))
                    
                    with loader_placeholder:
                        mostrar_bus_loading() # Mostramos bus al entrar
                    time.sleep(1.5) 
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas.")

        with tab_registro:
            st.caption("1. Crea tu usuario y contraseña.")
            reg_u = st.text_input("Nuevo Usuario", key="r_u")
            reg_p = st.text_input("Nueva Contraseña", type="password", key="r_p")
            
            if 'temp_totp_secret' not in st.session_state:
                st.session_state.temp_totp_secret = pyotp.random_base32()
            
            st.divider()
            st.caption("2. Escanea este código con Google Authenticator:")
            
            secret = st.session_state.temp_totp_secret
            uri = pyotp.totp.TOTP(secret).provisioning_uri(name=reg_u or "Usuario", issuer_name="GestorFlota")
            
            qr = qrcode.make(uri)
            img_bytes = BytesIO()
            qr.save(img_bytes, format='PNG')
            st.image(img_bytes.getvalue(), width=200)
            
            st.caption(f"O escribe la clave manual: `{secret}`")
            st.divider()
            
            st.caption("3. Confirma el código que te da la App:")
            code_check = st.text_input("Código de 6 dígitos", key="r_code")
            
            if st.button("Finalizar Registro", type="primary", use_container_width=True):
                code_limpio = code_check.replace(" ", "").strip()
                totp_check = pyotp.TOTP(secret)
                
                if totp_check.verify(code_limpio, valid_window=1):
                    ok, msg = registrar_usuario_con_totp(reg_u, reg_p, secret)
                    if ok:
                        st.success("✅ Registro Exitoso!")
                        del st.session_state['temp_totp_secret']
                        
                        cookie_manager.set("gestor_flota_user", reg_u.lower().strip(), expires_at=datetime.now() + timedelta(days=30))
                        st.session_state.autenticado = True
                        st.session_state.usuario_actual = reg_u.lower().strip()
                        
                        with loader_placeholder:
                            mostrar_bus_loading()
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.error("❌ Código incorrecto.")

        with tab_recuperar:
            st.caption("Recuperar contraseña con 2FA")
            with st.form("rec_form"):
                rec_u = st.text_input("Usuario", key="rec_u")
                rec_code = st.text_input("Código Auth", key="rec_c")
                rec_new_p = st.text_input("Nueva Contraseña", type="password", key="rec_np")
                btn_rec = st.form_submit_button("Restablecer", use_container_width=True)
            
            if btn_rec:
                ok, msg = restablecer_con_totp(rec_u, rec_code, rec_new_p)
                if ok: st.success(msg)
                else: st.error(msg)

    return False, cookie_manager

def obtener_lista_horas_puntuales():
    horas = []
    for h in range(24):
        t = datetime(2000, 1, 1, h, 0).strftime("%I %p").lstrip('0')
        horas.append(t)
    return horas

def selector_de_rangos(pool_unidades, key_unico, default_str=None):
    if not pool_unidades:
        st.info("No hay unidades disponibles.")
        return []

    pool_sorted = sorted(pool_unidades)
    min_total = pool_sorted[0]
    max_total = pool_sorted[-1]

    usar_filtro = st.checkbox("🔎 Filtrar lista por rango", value=False, key=f"chk_f_{key_unico}")

    f_min = min_total
    f_max = max_total

    if usar_filtro:
        c1, c2 = st.columns(2)
        with c1:
            f_min = st.number_input("Desde:", min_value=0, value=min_total, step=1, key=f"fm_{key_unico}")
        with c2:
            f_max = st.number_input("Hasta:", min_value=0, value=max_total, step=1, key=f"fx_{key_unico}")
        
        opciones_filtradas = [u for u in pool_sorted if f_min <= u <= f_max]
        
        if not opciones_filtradas:
            st.warning(f"No hay unidades entre {f_min} y {f_max}.")
    else:
        opciones_filtradas = pool_sorted

    seleccion = st.multiselect(
        f"Seleccionar unidades ({len(opciones_filtradas)}):", 
        opciones_filtradas, 
        key=f"multi_{key_unico}"
    )
    
    return seleccion
