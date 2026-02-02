import streamlit as st
import pyotp
import qrcode
import time
from io import BytesIO
from datetime import datetime, timedelta
import extra_streamlit_components as stx
import streamlit.components.v1 as components 
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

# --- ANIMACIÓN DEL AUTOBÚS (USO GENERAL) ---
def mostrar_bus_loading():
    loading_html = """
    <style>
        .bus-overlay {
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background-color: #ffffff; z-index: 999999;
            display: flex; flex-direction: column; justify-content: center; align-items: center;
        }
        .bus-emoji { font-size: 80px; animation: bounceBus 0.6s infinite alternate; margin-bottom: 20px; }
        .loading-bar { width: 200px; height: 6px; background-color: #eee; border-radius: 3px; overflow: hidden; }
        .loading-progress { width: 100%; height: 100%; background-color: #007BFF; animation: loadBar 1.5s infinite ease-in-out; transform-origin: left; }
        .loading-text { margin-top: 15px; font-family: sans-serif; color: #555; font-weight: 600; font-size: 18px; animation: pulseText 1.5s infinite; }
        @keyframes bounceBus { from { transform: translateY(0); } to { transform: translateY(-10px); } }
        @keyframes loadBar { 0% { transform: scaleX(0); } 50% { transform: scaleX(0.7); } 100% { transform: scaleX(1); opacity: 0; } }
        @keyframes pulseText { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
    </style>
    <div class="bus-overlay">
        <div class="bus-emoji">🚌</div>
        <div class="loading-bar"><div class="loading-progress"></div></div>
        <div class="loading-text">Cargando flota...</div>
    </div>
    """
    st.markdown(loading_html, unsafe_allow_html=True)

# --- TRUCO JS PARA ACTIVAR HUELLA/AUTOCOMPLETE ---
def inyectar_js_autocomplete():
    js = """
    <script>
        function enableAutocomplete() {
            const inputs = window.parent.document.querySelectorAll('input');
            inputs.forEach(input => {
                if (input.getAttribute('aria-label') === 'Usuario') {
                    input.setAttribute('autocomplete', 'username');
                    input.setAttribute('name', 'username');
                }
                if (input.getAttribute('aria-label') === 'Contraseña') {
                    input.setAttribute('autocomplete', 'current-password');
                    input.setAttribute('name', 'password');
                }
            });
        }
        setTimeout(enableAutocomplete, 300);
        setTimeout(enableAutocomplete, 1000);
    </script>
    """
    components.html(js, height=0, width=0)

# --- LOGOUT "HARDCORE" CON ANIMACIÓN ---
def ejecutar_logout_hardcore():
    """
    1. Cubre la pantalla con el autobús (HTML/CSS).
    2. Borra la cookie (JS).
    3. Fuerza la recarga (JS) después de una pausa para evitar ver el error de desconexión.
    """
    html_code = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            /* Capa que cubre TODO, incluso errores de Streamlit */
            .logout-overlay {
                position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
                background-color: #ffffff; z-index: 2147483647; /* Z-index máximo posible */
                display: flex; flex-direction: column; justify-content: center; align-items: center;
            }
            .bus-emoji { font-size: 80px; animation: driveOut 2s forwards ease-in; margin-bottom: 20px; }
            .bye-text { font-family: sans-serif; color: #555; font-weight: 600; font-size: 18px; }
            
            @keyframes driveOut {
                0% { transform: translateX(0); opacity: 1; }
                20% { transform: translateX(-20px); }
                100% { transform: translateX(100vw); opacity: 0; }
            }
        </style>
    </head>
    <body>
        <div class="logout-overlay">
            <div class="bus-emoji">🚌💨</div>
            <div class="bye-text">Cerrando sesión...</div>
        </div>

        <script>
            // Función asíncrona para asegurar tiempos
            async function killSession() {
                // A. Borrar cookies (Nuclear)
                document.cookie = "gestor_flota_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                
                // B. Esperar 1 segundo para que la animación se vea y tape cualquier error de red
                await new Promise(r => setTimeout(r, 1000));
                
                // C. Recarga forzada (Hard Reload)
                window.parent.location.reload(true);
            }
            
            killSession();
        </script>
    </body>
    </html>
    """
    # Altura 0 para que no desplace el layout, pero el CSS 'fixed' lo mostrará fullscreen
    components.html(html_code, height=0, width=0)

def verificar_login():
    cookie_manager = get_cookie_manager()
    
    if st.session_state.get("logout_pending", False):
        st.session_state["logout_pending"] = False
        st.session_state.autenticado = False
        st.session_state.usuario_actual = None
        return False, cookie_manager

    cookie_user = cookie_manager.get(cookie="gestor_flota_user")

    if 'autenticado' not in st.session_state: st.session_state.autenticado = False
    if 'usuario_actual' not in st.session_state: st.session_state.usuario_actual = None

    if cookie_user and not st.session_state.autenticado:
        mostrar_bus_loading()
        st.session_state.autenticado = True
        st.session_state.usuario_actual = cookie_user
        try:
            cookie_manager.set("gestor_flota_user", cookie_user, expires_at=datetime.now() + timedelta(days=30))
        except: pass
        time.sleep(1.5)
        st.rerun()

    if st.session_state.autenticado:
        return True, cookie_manager

    # --- PANTALLA DE LOGIN ---
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Gestor de Flota ⛽")
        tab_login, tab_registro, tab_recuperar = st.tabs(["🔒 Entrar", "📲 Registro 2FA", "🔄 Recuperar"])
        
        with tab_login:
            inyectar_js_autocomplete()
            with st.form("login_form"):
                user = st.text_input("Usuario", key="l_u")
                pwd = st.text_input("Contraseña", type="password", key="l_p")
                mantener = st.checkbox("Mantener sesión iniciada", value=True)
                btn_in = st.form_submit_button("Iniciar Sesión", type="primary", use_container_width=True)
            
            if btn_in:
                if validar_usuario_db(user, pwd):
                    mostrar_bus_loading()
                    st.session_state.autenticado = True
                    st.session_state.usuario_actual = user.lower().strip()
                    if mantener:
                        cookie_manager.set("gestor_flota_user", user.lower().strip(), expires_at=datetime.now() + timedelta(days=30))
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
            st.caption("2. Escanea con Google Authenticator:")
            secret = st.session_state.temp_totp_secret
            uri = pyotp.totp.TOTP(secret).provisioning_uri(name=reg_u or "Usuario", issuer_name="GestorFlota")
            qr = qrcode.make(uri)
            img_bytes = BytesIO()
            qr.save(img_bytes, format='PNG')
            st.image(img_bytes.getvalue(), width=200)
            st.caption(f"Clave manual: `{secret}`")
            st.divider()
            st.caption("3. Confirma código:")
            code_check = st.text_input("Código 6 dígitos", key="r_code")
            
            if st.button("Finalizar Registro", type="primary", use_container_width=True):
                code_limpio = code_check.replace(" ", "").strip()
                totp_check = pyotp.TOTP(secret)
                if totp_check.verify(code_limpio, valid_window=1):
                    ok, msg = registrar_usuario_con_totp(reg_u, reg_p, secret)
                    if ok:
                        mostrar_bus_loading()
                        del st.session_state['temp_totp_secret']
                        cookie_manager.set("gestor_flota_user", reg_u.lower().strip(), expires_at=datetime.now() + timedelta(days=30))
                        st.session_state.autenticado = True
                        st.session_state.usuario_actual = reg_u.lower().strip()
                        time.sleep(1.5)
                        st.rerun()
                    else: st.error(msg)
                else: st.error("❌ Código incorrecto.")

        with tab_recuperar:
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
