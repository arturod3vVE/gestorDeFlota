import streamlit as st
import pyotp
import qrcode
import time
from io import BytesIO
from datetime import datetime, timedelta
import extra_streamlit_components as stx
import streamlit.components.v1 as components # Necesario para el truco de JS
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

# --- ANIMACIÓN DEL AUTOBÚS (PANTALLA COMPLETA) ---
def mostrar_bus_loading(fade_out=False):
    # Si fade_out es True, aplicamos opacidad 0 y animación
    # Si es False, opacidad 1
    opacity = "0" if fade_out else "1"
    
    # Z-Index 90: Cubre el contenido (0) pero deja ver el Sidebar (100) cerrándose
    z_index = "90" 
    
    loading_html = f"""
    <style>
        .bus-overlay {{
            position: fixed; 
            top: 0; 
            left: 0; 
            width: 100vw; 
            height: 100vh;
            background-color: #ffffff; 
            z-index: {z_index}; 
            display: flex; 
            flex-direction: column; 
            justify-content: center; 
            align-items: center;
            
            /* PROPIEDADES DE ANIMACIÓN SUAVE */
            opacity: {opacity};
            transition: opacity 0.6s ease-in-out;
            pointer-events: none; /* Para que no bloquee clics mientras se desvanece */
        }}
        .bus-emoji {{ font-size: 80px; animation: bounceBus 0.6s infinite alternate; margin-bottom: 20px; }}
        .loading-bar {{ width: 200px; height: 6px; background-color: #eee; border-radius: 3px; overflow: hidden; }}
        .loading-progress {{ width: 100%; height: 100%; background-color: #007BFF; animation: loadBar 1.5s infinite ease-in-out; transform-origin: left; }}
        .loading-text {{ margin-top: 15px; font-family: sans-serif; color: #555; font-weight: 600; font-size: 18px; animation: pulseText 1.5s infinite; }}
        
        @keyframes bounceBus {{ from {{ transform: translateY(0); }} to {{ transform: translateY(-10px); }} }}
        @keyframes loadBar {{ 0% {{ transform: scaleX(0); }} 50% {{ transform: scaleX(0.7); }} 100% {{ transform: scaleX(1); opacity: 0; }} }}
        @keyframes pulseText {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.6; }} }}
    </style>
    <div class="bus-overlay">
        <div class="bus-emoji">🚌</div>
        <div class="loading-bar"><div class="loading-progress"></div></div>
        <div class="loading-text">Cargando flota...</div>
    </div>
    """
    st.markdown(loading_html, unsafe_allow_html=True)

def verificar_fase_cierre():
    """
    Se ejecuta al principio de main.py.
    Si detecta que el usuario quiere salir, toma el control total,
    muestra la animación y mata la sesión.
    """
    if st.session_state.get("fase_salida"):
        # 1. Mostrar la Animación (Overlay CSS puro que cubre todo)
        st.markdown("""
            <style>
                .logout-overlay {
                    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
                    background-color: #ffffff; z-index: 99999999;
                    display: flex; flex-direction: column; justify-content: center; align-items: center;
                }
                .bus-out { font-size: 80px; animation: driveOut 2s forwards ease-in; margin-bottom: 20px; }
                .bye-text { font-family: sans-serif; color: #555; font-weight: bold; font-size: 20px; }
                @keyframes driveOut {
                    0% { transform: translateX(0); opacity: 1; }
                    100% { transform: translateX(120vw); opacity: 0; }
                }
            </style>
            <div class="logout-overlay">
                <div class="bus-out">🚌💨</div>
                <div class="bye-text">Cerrando sesión...</div>
            </div>
        """, unsafe_allow_html=True)

        # 2. Ejecutar Javascript para borrar cookies y recargar
        # Usamos un pequeño delay en JS para asegurar que el CSS se haya pintado
        js = """
        <script>
            async function kill() {
                // Esperar 1.5 seg visualizando el bus
                await new Promise(r => setTimeout(r, 1500));
                
                // Borrar cookies
                document.cookie = "gestor_flota_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                
                // Forzar recarga completa
                window.parent.location.reload(true);
            }
            kill();
        </script>
        """
        components.html(js, height=0, width=0)
        
        # 3. DETENER PYTHON AQUÍ. No cargar el resto de la app.
        time.sleep(5) # Mantiene el script vivo mientras el JS hace su trabajo
        st.stop()

# --- TRUCO JS PARA ACTIVAR HUELLA/AUTOCOMPLETE ---
def inyectar_js_autocomplete():
    # Este script busca los inputs por su etiqueta (aria-label) y les fuerza el atributo autocomplete
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
        // Intentamos ejecutarlo varias veces por si Streamlit tarda en renderizar
        setTimeout(enableAutocomplete, 300);
        setTimeout(enableAutocomplete, 1000);
    </script>
    """
    components.html(js, height=0, width=0)

def verificar_login():
    """
    Retorna una tupla: (Estado_Autenticacion (bool), Objeto_Cookie_Manager)
    """
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
            # Inyectamos el script AQUÍ para que afecte a este formulario
            inyectar_js_autocomplete()
            
            with st.form("login_form"):
                # IMPORTANTE: Los labels deben coincidir con lo que busca el JS arriba ("Usuario", "Contraseña")
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
    
    # NOTA: En pantallas de móvil pequeñas, a veces es mejor ocultar el filtro si no se usa
    usar_filtro = st.checkbox("🔎 Filtrar lista por rango", value=False, key=f"chk_f_{key_unico}")

    if usar_filtro:
        c1, c2 = st.columns(2)
        with c1: f_min = st.number_input("Desde:", min_value=0, value=pool_sorted[0], step=1, key=f"fm_{key_unico}")
        with c2: f_max = st.number_input("Hasta:", min_value=0, value=pool_sorted[-1], step=1, key=f"fx_{key_unico}")
        opciones_filtradas = [u for u in pool_sorted if f_min <= u <= f_max]
    else:
        opciones_filtradas = pool_sorted

    seleccion = st.multiselect(
        f"Seleccionar unidades ({len(opciones_filtradas)}):", 
        opciones_filtradas, 
        key=f"multi_{key_unico}"
    )
    return seleccion
def ejecutar_logout_hardcore():
    """
    1. Usamos st.markdown para inyectar el CSS globalmente (rompe el iframe).
    2. Usamos components.html solo para el script de borrado con delay.
    """
    
    # 1. LA CAPA VISUAL (Directo al DOM principal)
    st.markdown("""
        <style>
            .logout-overlay {
                position: fixed !important;
                top: 0 !important;
                left: 0 !important;
                width: 100vw !important;
                height: 100vh !important;
                background-color: #ffffff !important;
                z-index: 99999999 !important; /* Encima de todo */
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                pointer-events: all; /* Bloquea clics */
            }
            .bus-out { font-size: 80px; animation: driveOut 2.5s forwards ease-in; margin-bottom: 20px; }
            .bye-text { font-family: sans-serif; color: #555; font-weight: bold; font-size: 20px; }
            
            @keyframes driveOut {
                0% { transform: translateX(0); opacity: 1; }
                100% { transform: translateX(120vw); opacity: 0; }
            }
        </style>
        <div class="logout-overlay">
            <div class="bus-out">🚌💨</div>
            <div class="bye-text">Cerrando sesión...</div>
        </div>
    """, unsafe_allow_html=True)

    # 2. LA BOMBA LÓGICA (Javascript con espera)
    # Esperamos 1500ms para que la animación se vea antes de matar la conexión
    js_killer = """
    <script>
        async function killSession() {
            // Esperamos 1.5 segundos viendo el autobús
            await new Promise(r => setTimeout(r, 1500));
            
            // Matamos la cookie
            document.cookie = "gestor_flota_user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            
            // Matamos la página (Hard Reload)
            window.parent.location.reload(true);
        }
        killSession();
    </script>
    """
    components.html(js_killer, height=0, width=0)
