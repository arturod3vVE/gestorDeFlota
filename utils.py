import streamlit as st
import pyotp
import qrcode
from io import BytesIO
from database import validar_usuario_db, registrar_usuario_con_totp, restablecer_con_totp
from datetime import datetime

def inyectar_css():
    st.markdown("""
        <style>
            /* Ocultamos el menú de hamburguesa (derecha) */
            #MainMenu {visibility: hidden;}
            
            /* Ocultamos el pie de página "Made with Streamlit" */
            footer {visibility: hidden;}
            
            /* --- LÍNEAS COMENTADAS (ELIMINADAS) PARA QUE SE VEA EL SIDEBAR --- */
            /* header {visibility: hidden;} */
            /* .stApp { margin-top: -60px; } */
            
        </style>
    """, unsafe_allow_html=True)

def verificar_login():
    if 'autenticado' not in st.session_state: st.session_state.autenticado = False
    if 'usuario_actual' not in st.session_state: st.session_state.usuario_actual = None

    if st.session_state.autenticado: return True

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Gestor de Flota ⛽")
        tab_login, tab_registro, tab_recuperar = st.tabs(["🔒 Entrar", "📲 Registro 2FA", "🔄 Recuperar"])
        
        # --- 1. LOGIN ---
        with tab_login:
            with st.form("login_form"):
                user = st.text_input("Usuario", key="l_u")
                pwd = st.text_input("Contraseña", type="password", key="l_p")
                btn_in = st.form_submit_button("Iniciar Sesión", type="primary", use_container_width=True)
            if btn_in:
                if validar_usuario_db(user, pwd):
                    st.session_state.autenticado = True
                    st.session_state.usuario_actual = user.lower().strip()
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas.")

        # --- 2. REGISTRO CON CÓDIGO QR ---
        with tab_registro:
            st.caption("1. Crea tu usuario y contraseña.")
            reg_u = st.text_input("Nuevo Usuario", key="r_u")
            reg_p = st.text_input("Nueva Contraseña", type="password", key="r_p")
            
            # Generamos un secreto temporal en session_state si no existe
            if 'temp_totp_secret' not in st.session_state:
                st.session_state.temp_totp_secret = pyotp.random_base32()
            
            st.divider()
            st.caption("2. Escanea este código con Google Authenticator:")
            
            # Generar QR
            secret = st.session_state.temp_totp_secret
            # URI para que la app entienda (NombreApp:Usuario)
            uri = pyotp.totp.TOTP(secret).provisioning_uri(name=reg_u or "Usuario", issuer_name="GestorFlota")
            
            # Crear imagen QR
            qr = qrcode.make(uri)
            img_bytes = BytesIO()
            qr.save(img_bytes, format='PNG')
            st.image(img_bytes.getvalue(), width=200)
            
            st.caption(f"O escribe la clave manual: `{secret}`")
            st.divider()
            
            st.caption("3. Confirma el código que te da la App:")
            code_check = st.text_input("Código de 6 dígitos", key="r_code")
            
            if st.button("Finalizar Registro", type="primary", use_container_width=True):
                # LIMPIEZA: Quitamos espacios en blanco por si el usuario escribe "123 456"
                code_limpio = code_check.replace(" ", "").strip()

                # VALIDACIÓN: Creamos el objeto TOTP
                totp_check = pyotp.TOTP(secret)
                
                # --- AQUÍ ESTÁ EL TRUCO ---
                # valid_window=1 permite un margen de error de 30 segundos
                # (acepta el código anterior, el actual y el siguiente)
                if totp_check.verify(code_limpio, valid_window=1):
                    ok, msg = registrar_usuario_con_totp(reg_u, reg_p, secret)
                    if ok:
                        st.success("✅ Registro Exitoso!")
                        del st.session_state['temp_totp_secret']
                        st.session_state.autenticado = True
                        st.session_state.usuario_actual = reg_u.lower().strip()
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.error(f"❌ El código es incorrecto. Asegúrate de que la hora de tu celular esté en 'Automática'.")

        # --- 3. RECUPERAR CON AUTHENTICATOR ---
        with tab_recuperar:
            st.caption("Usa tu App Autenticadora para cambiar la contraseña.")
            with st.form("rec_form"):
                rec_u = st.text_input("Usuario", key="rec_u")
                rec_code = st.text_input("Código de Google Auth (6 dígitos)", key="rec_c")
                rec_new_p = st.text_input("Nueva Contraseña", type="password", key="rec_np")
                btn_rec = st.form_submit_button("Restablecer", use_container_width=True)
            
            if btn_rec:
                ok, msg = restablecer_con_totp(rec_u, rec_code, rec_new_p)
                if ok:
                    st.success(msg)
                    st.info("Ahora puedes iniciar sesión en la pestaña 1.")
                else:
                    st.error(msg)

    return False

def obtener_lista_horas_puntuales():
    horas = []
    for h in range(24):
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