import streamlit as st
import gspread
import json
import os

NOMBRE_HOJA = "DB_GestorFlota"

def conectar_google_sheets():
    print("--- INICIANDO CONEXIÓN GOOGLE SHEETS ---")
    try:
        if "gcp_service_account" in st.secrets:
            print("1. Usando Secretos de Streamlit Cloud...")
            creds_dict = dict(st.secrets["gcp_service_account"])
            gc = gspread.service_account_from_dict(creds_dict)
        else:
            print("1. Buscando archivo local datos_sistema.json...")
            if not os.path.exists("datos_sistema.json"):
                print("❌ ERROR: No se encuentra datos_sistema.json")
                return None
            gc = gspread.service_account("datos_sistema.json")
        
        print(f"2. Intentando abrir hoja: {NOMBRE_HOJA}...")
        sh = gc.open(NOMBRE_HOJA)
        print("✅ Conexión exitosa.")
        return sh
    except Exception as e:
        print(f"❌ ERROR CONECTANDO: {e}")
        return None

def cargar_datos_db():
    print("--- CARGANDO DATOS ---")
    # Valores por defecto
    default_colors = ["#f8d7da", "#fff3cd", "#d1e7dd", "#cff4fc", "#e2e3e5", "#f0f2f6"]
    datos = {
        "averiadas": [], "rango_min": 1, "rango_max": 500,
        "estaciones": ["bp", "Texaco", "Cartonera Petare"],
        "password": "admin", "font_size": 24, "img_width": 450,
        "bg_color": "#ECE5DD", "st_colors": default_colors
    }
    
    sh = conectar_google_sheets()
    if not sh: 
        print("⚠️ Usando datos por defecto (Modo Offline).")
        return datos

    try:
        print("3. Leyendo pestaña Config...")
        ws_config = sh.worksheet("Config")
        vals_config = ws_config.get_all_values()
        
        if len(vals_config) >= 1: datos["rango_min"] = int(vals_config[0][1])
        if len(vals_config) >= 2: datos["rango_max"] = int(vals_config[1][1])
        if len(vals_config) >= 3: datos["password"] = vals_config[2][1]
        if len(vals_config) >= 4: datos["font_size"] = int(vals_config[3][1])
        if len(vals_config) >= 5: datos["img_width"] = int(vals_config[4][1])
        if len(vals_config) >= 6 and len(vals_config[5]) > 1: datos["bg_color"] = vals_config[5][1]
        
        loaded_st_colors = []
        for i in range(6):
            row_idx = 6 + i
            if len(vals_config) > row_idx and len(vals_config[row_idx]) > 1:
                 loaded_st_colors.append(vals_config[row_idx][1])
        if loaded_st_colors:
             while len(loaded_st_colors) < 6:
                 loaded_st_colors.append(default_colors[len(loaded_st_colors)])
             datos["st_colors"] = loaded_st_colors
        
        print("4. Leyendo Estaciones y Averiadas...")
        try: datos["estaciones"] = sh.worksheet("Estaciones").col_values(1)
        except: pass
        try: 
            raw_av = sh.worksheet("Averiadas").col_values(1)
            datos["averiadas"] = [int(x) for x in raw_av if x.isdigit()]
        except: pass
            
        print("✅ Carga completada.")
        return datos
    except Exception as e:
        print(f"❌ ERROR LEYENDO DATOS: {e}")
        return datos

def guardar_datos_db(datos):
    print("--- GUARDANDO DATOS ---")
    sh = conectar_google_sheets()
    if not sh: return

    try:
        ws_config = sh.worksheet("Config")
        ws_config.clear()
        
        config_rows = [
            ['Min', datos["rango_min"]], ['Max', datos["rango_max"]],
            ['Password', datos["password"]], ['FontSize', datos["font_size"]],
            ['ImgWidth', datos["img_width"]], ['BgColor', datos["bg_color"]]
        ]
        for i, col in enumerate(datos["st_colors"]):
             config_rows.append([f'StColor{i+1}', col])

        ws_config.update(range_name='A1', values=config_rows)
        
        ws_est = sh.worksheet("Estaciones")
        ws_est.clear()
        if datos["estaciones"]:
            ws_est.update(range_name='A1', values=[[e] for e in datos["estaciones"]])
            
        ws_av = sh.worksheet("Averiadas")
        ws_av.clear()
        if datos["averiadas"]:
            ws_av.update(range_name='A1', values=[[str(a)] for a in datos["averiadas"]])
        print("✅ Guardado exitoso.")
            
    except Exception as e:
        st.error(f"Error guardando: {e}")
        print(f"❌ ERROR GUARDANDO: {e}")

# --- AGREGAR ESTO AL FINAL DE database.py ---

def guardar_historial_db(fecha, reporte_diario):
    """Guarda el reporte actual en la hoja 'Historial'"""
    sh = conectar_google_sheets()
    if not sh: return False

    try:
        # Intentamos abrir la hoja, si no existe la crea (opcional, pero mejor tenerla creada)
        try:
            ws_hist = sh.worksheet("Historial")
        except:
            ws_hist = sh.add_worksheet(title="Historial", rows=1000, cols=10)
            ws_hist.append_row(["Fecha", "Estación", "Horario", "Unidades"])

        # Preparamos las filas para subir
        # Formato: [Fecha, Nombre Estación, Horario, "01, 05, 10..."]
        nuevas_filas = []
        fecha_str = fecha.strftime('%d/%m/%Y')
        
        for item in reporte_diario:
            unidades_str = ", ".join([f"{u:02d}" for u in item['unidades']])
            row = [fecha_str, item['nombre'], item['horario'], unidades_str]
            nuevas_filas.append(row)

        if nuevas_filas:
            # append_rows es más eficiente que hacerlo uno por uno
            ws_hist.append_rows(nuevas_filas)
            return True
        return False
            
    except Exception as e:
        print(f"Error guardando historial: {e}")
        return False
    
# --- AGREGAR AL FINAL DE database.py ---

def recuperar_historial_por_fecha(fecha_dt):
    """Busca en el historial registros de una fecha específica y los formatea."""
    sh = conectar_google_sheets()
    if not sh: return []

    try:
        ws = sh.worksheet("Historial")
        all_rows = ws.get_all_values()
        
        # La fecha que buscamos (string)
        target = fecha_dt.strftime('%d/%m/%Y')
        
        reporte_recuperado = []
        
        # Saltamos la cabecera (fila 0)
        for row in all_rows[1:]:
            # Estructura esperada: [Fecha, Estación, Horario, Unidades]
            if len(row) >= 4 and row[0] == target:
                
                # Convertimos el string "01, 05, 10" de nuevo a lista [1, 5, 10]
                unidades_str = row[3].split(',')
                unidades_int = []
                for u in unidades_str:
                    u_limpio = u.strip()
                    if u_limpio.isdigit():
                        unidades_int.append(int(u_limpio))
                
                reporte_recuperado.append({
                    "nombre": row[1],
                    "horario": row[2],
                    "unidades": sorted(unidades_int)
                })
                
        return reporte_recuperado
            
    except Exception as e:
        print(f"Error recuperando: {e}")
        return []