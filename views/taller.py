import streamlit as st
import time
from database import guardar_datos_db

# ==========================================
# 1. CSS FINAL (CONTROL TOTAL DE PÍXELES)
# ==========================================
def inyectar_css_final():
    st.markdown("""
        <style>
        /* ============================================================
           ZONA 0: ESTILOS BASE (GLOBALES)
           ============================================================ */
        button[kind="secondary"] {
            background-color: #f8f9fa !important;
            border: 1px solid #dee2e6 !important;
            color: #495057 !important;
            transition: all 0.2s !important;
        }
        button[kind="secondary"]:hover {
            border-color: #ff4b4b !important;
            color: #ff4b4b !important;
            background-color: #fff !important;
        }
        
        section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(div[data-testid="stButton"]) button {
            box-shadow: 0 1px 1px rgba(0,0,0,0.05) !important;
            border-radius: 6px !important;
        }

        /* Restaurar Menú Lateral y Modales */
        section[data-testid="stSidebar"] button,
        div[role="dialog"] button {
            width: 100% !important;
            height: auto !important;
            aspect-ratio: auto !important;
        }

        @media (min-width: 381px) and (max-width: 640px) {
            
            section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(div[data-testid="stButton"]) {
                display: grid !important;
                grid-template-columns: repeat(6, 1fr) !important;
                gap: 2px !important;
                padding: 1px !important;
                margin: 0px !important;
            }

            section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(div[data-testid="stButton"]) div[data-testid="column"] {
                width: auto !important; min-width: 0px !important; flex: 1 !important; padding: 0px !important;
            }

            section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(div[data-testid="stButton"]) button {
                width: 100% !important;
                aspect-ratio: 1 / 1 !important;
                padding: 0px !important; margin: 0px !important; min-width: 0px !important;
                display: flex !important; flex-direction: column !important;
                justify-content: center !important; align-items: center !important;
                line-height: 1.1 !important;
            }

            /* TEXTO: Aquí aumentamos el tamaño para que se vea mejor */
            section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(div[data-testid="stButton"]) button p {
                white-space: pre !important; 
                font-size: 12px !important; /* AUMENTADO (Antes 10px) */
                margin: 0px !important;
                font-weight: 800 !important;
                letter-spacing: -0.5px !important;
            }
        }

        @media (max-width: 380px) {
            
            /* Dejamos que Streamlit apile las columnas (Flex Column) */
            section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(div[data-testid="stButton"]) {
                display: flex !important;
                flex-direction: column !important;
                gap: 10px !important;
            }

            /* Reseteamos los botones a su forma natural rectangular */
            section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(div[data-testid="stButton"]) button {
                width: 100% !important;
                aspect-ratio: auto !important; /* Ya no cuadrados */
                padding: 10px !important;
                display: flex !important;
                flex-direction: row !important; /* Icono al lado del texto */
                justify-content: center !important;
            }

            section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(div[data-testid="stButton"]) button p {
                font-size: 14px !important;
                white-space: normal !important;
            }
        }

        /* ============================================================
           ZONA 4: ESCRITORIO (> 640px)
           ============================================================ */
        @media (min-width: 641px) {
            section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(div[data-testid="stButton"]) button {
                width: 100% !important;
                min-height: 60px !important;
                padding: 10px !important;
            }
            
            section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(div[data-testid="stButton"]) button p {
                font-size: 14px !important;
                white-space: nowrap !important;
            }
            
            div[data-testid="column"] {
                padding: 0 4px !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. MODAL (CONFIRMACIÓN)
# ==========================================
@st.dialog("Gestionar Unidad")
def gestionar_unidad(unidad, estado_actual, datos, usuario_actual):
    st.markdown(f"<h3 style='text-align:center'>Unidad {unidad}</h3>", unsafe_allow_html=True)
    
    with st.container():
        if estado_actual == "averiada":
            st.error("Estado: 🔴 EN TALLER")
            st.write("¿La unidad ya fue reparada?")
            if st.button("✅ Habilitar Unidad", type="primary", use_container_width=True):
                if unidad in datos["averiadas"]:
                    datos["averiadas"].remove(unidad)
                    guardar_datos_db(datos, usuario_actual)
                    st.toast(f"Unidad {unidad} habilitada")
                    time.sleep(0.5)
                    st.rerun()
        else:
            st.success("Estado: 🚛 OPERATIVA")
            st.write("¿Deseas enviar esta unidad a mantenimiento?")
            if st.button("🛠️ Reportar Daño", type="primary", use_container_width=True):
                if "averiadas" not in datos: datos["averiadas"] = []
                if unidad not in datos["averiadas"]:
                    datos["averiadas"].append(unidad)
                    datos["averiadas"].sort()
                    guardar_datos_db(datos, usuario_actual)
                    st.toast(f"Unidad {unidad} a taller")
                    time.sleep(0.5)
                    st.rerun()

# ==========================================
# 3. VISTA PRINCIPAL
# ==========================================
def render_vista(usuario_actual):
    inyectar_css_final()
    
    st.title("🔧 Taller Central")
    
    d = st.session_state.datos_app
    avs = d.get("averiadas", [])
    
    all_u = []
    if "rangos" in d:
        for r in d["rangos"]:
            all_u.extend(list(range(r[0], r[1] + 1)))
    all_u = sorted(list(set(all_u)))

    columnas_por_fila = 6
    
    for i in range(0, len(all_u), columnas_por_fila):
        fila = all_u[i : i + columnas_por_fila]
        cols = st.columns(columnas_por_fila)
        
        for j, u in enumerate(fila):
            # Python siempre manda el icono. CSS decide si lo oculta o no.
            if u in avs:
                label = f"🛠️\n{u}"
                tipo = "primary"
                estado = "averiada"
            else:
                label = f"🚛\n{u}"
                tipo = "secondary"
                estado = "sana"
            
            if cols[j].button(label, key=f"btn_{u}", type=tipo, use_container_width=True):
                gestionar_unidad(u, estado, d, usuario_actual)

    st.markdown("<br>", unsafe_allow_html=True)
    
    with st.container():
        st.divider()
        c1, c2 = st.columns(2)
        c1.metric("Total", len(all_u))
        c2.metric("Averiadas", len(avs))
