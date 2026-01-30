import streamlit as st
import pyotp
import qrcode
from io import BytesIO
from datetime import datetime
from database import validar_usuario_db, registrar_usuario_con_totp, restablecer_con_totp

def inyectar_css():
    st.markdown("""
        <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
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
                        st.session_state.autenticado = True
                        st.session_state.usuario_actual = reg_u.lower().strip()
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

    return False

def obtener_lista_horas_puntuales():
    horas = []
    for h in range(24):
        t = datetime(2000, 1, 1, h, 0).strftime("%I %p").lstrip('0')
        horas.append(t)
    return horas

# --- SELECTOR DE RANGOS CON INPUTS ---
def selector_de_rangos(pool_unidades, key_unico, default_str=None):
    """
    Selector con Checkbox para habilitar filtro numérico (Inputs).
    """
    if not pool_unidades:
        st.info("No hay unidades disponibles.")
        return []

    pool_sorted = sorted(pool_unidades)
    min_total = pool_sorted[0]
    max_total = pool_sorted[-1]

    # 1. Checkbox para activar
    # Si está desactivado, mostramos todo.
    usar_filtro = st.checkbox("🔎 Filtrar lista por rango", value=False, key=f"chk_f_{key_unico}")

    f_min = min_total
    f_max = max_total

    # 2. Si activa el checkbox, mostramos los inputs numéricos
    if usar_filtro:
        c1, c2 = st.columns(2)
        with c1:
            # step=1 permite subir y bajar con flechas
            f_min = st.number_input("Desde:", min_value=0, value=min_total, step=1, key=f"fm_{key_unico}")
        with c2:
            f_max = st.number_input("Hasta:", min_value=0, value=max_total, step=1, key=f"fx_{key_unico}")
        
        # Filtramos la lista
        opciones_filtradas = [u for u in pool_sorted if f_min <= u <= f_max]
        
        if not opciones_filtradas:
            st.warning(f"No hay unidades entre {f_min} y {f_max}.")
    else:
        opciones_filtradas = pool_sorted

    # 3. Selector final
    seleccion = st.multiselect(
        f"Seleccionar unidades ({len(opciones_filtradas)}):", 
        opciones_filtradas, 
        key=f"multi_{key_unico}"
    )
    
    return seleccion