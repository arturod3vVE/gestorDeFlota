import streamlit as st
import gspread
import json
import os
import hashlib

NOMBRE_HOJA = "DB_GestorFlota"

# --- CONEXIÓN ---
def conectar_google_sheets():
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            gc = gspread.service_account_from_dict(creds_dict)
            return gc.open(NOMBRE_HOJA)
        else:
            gc = gspread.service_account("datos_sistema.json")
            return gc.open(NOMBRE_HOJA)
    except Exception as e:
        print(f"Error conexión: {e}")
        return None

# --- NUEVO: VALIDAR USUARIO ---
def hacer_hash(texto):
    return hashlib.sha256(str(texto).encode('utf-8')).hexdigest()

# --- VALIDAR USUARIO (LOGIN NORMAL) ---
def validar_usuario_db(usuario, password):
    sh = conectar_google_sheets()
    if not sh: return False
    try:
        ws = sh.worksheet("Usuarios")
        registros = ws.get_all_records()
        pass_hash = hacer_hash(password)
        
        for reg in registros:
            if str(reg['Usuario']).strip().lower() == usuario.strip().lower():
                if str(reg['Password']) == pass_hash:
                    return True
        return False
    except: return False

# --- FUNCIÓN AUXILIAR PARA OBTENER NOMBRE DE PESTAÑA ---
def get_tab_name(base, usuario):
    # Ejemplo: "Config" + "juan" -> "Config_juan"
    return f"{base}_{usuario.lower()}"

def asegurar_pestana(sh, nombre_pestana, columnas_iniciales=[]):
    """Crea la pestaña si no existe para ese usuario"""
    try:
        ws = sh.worksheet(nombre_pestana)
        return ws
    except:
        # Si falla, la creamos
        ws = sh.add_worksheet(title=nombre_pestana, rows=100, cols=10)
        if columnas_iniciales:
            ws.append_row(columnas_iniciales)
        return ws

# --- CARGAR DATOS (POR USUARIO) ---
def cargar_datos_db(usuario):
    default_colors = ["#f8d7da", "#fff3cd", "#d1e7dd", "#cff4fc", "#e2e3e5", "#f0f2f6"]
    
    # Datos base vacíos
    datos = {
        "averiadas": [], "rango_min": 1, "rango_max": 500,
        "estaciones": [], "font_size": 24, "img_width": 450,
        "bg_color": "#ECE5DD", "st_colors": default_colors
    }
    
    sh = conectar_google_sheets()
    if not sh: return datos

    # Nombres de pestañas personalizados
    tab_config = get_tab_name("Config", usuario)
    tab_est = get_tab_name("Estaciones", usuario)
    tab_av = get_tab_name("Averiadas", usuario)

    try:
        # 1. Cargar Config (Si no existe, la crea vacía)
        ws_config = asegurar_pestana(sh, tab_config)
        vals_config = ws_config.get_all_values()
        
        if len(vals_config) >= 1: datos["rango_min"] = int(vals_config[0][1])
        if len(vals_config) >= 2: datos["rango_max"] = int(vals_config[1][1])
        # (Password ya no se guarda en config individual)
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
        
        # 2. Cargar Estaciones
        ws_est = asegurar_pestana(sh, tab_est)
        lista_est = ws_est.col_values(1)
        if lista_est: datos["estaciones"] = lista_est

        # 3. Cargar Averiadas
        ws_av = asegurar_pestana(sh, tab_av)
        raw_av = ws_av.col_values(1)
        datos["averiadas"] = [int(x) for x in raw_av if x.isdigit()]
            
        return datos
    except Exception as e:
        print(f"Error cargando usuario {usuario}: {e}")
        return datos

# --- GUARDAR DATOS (POR USUARIO) ---
def guardar_datos_db(datos, usuario):
    sh = conectar_google_sheets()
    if not sh: return

    tab_config = get_tab_name("Config", usuario)
    tab_est = get_tab_name("Estaciones", usuario)
    tab_av = get_tab_name("Averiadas", usuario)

    try:
        # Guardar Config
        ws_config = sh.worksheet(tab_config)
        ws_config.clear()
        
        config_rows = [
            ['Min', datos["rango_min"]], 
            ['Max', datos["rango_max"]],
            ['Reserved', 'NA'], # Placeholder donde antes iba password
            ['FontSize', datos["font_size"]],
            ['ImgWidth', datos["img_width"]],
            ['BgColor', datos["bg_color"]]
        ]
        for i, col in enumerate(datos["st_colors"]):
             config_rows.append([f'StColor{i+1}', col])

        ws_config.update(range_name='A1', values=config_rows)
        
        # Guardar Estaciones
        ws_est = sh.worksheet(tab_est)
        ws_est.clear()
        if datos["estaciones"]:
            ws_est.update(range_name='A1', values=[[e] for e in datos["estaciones"]])
            
        # Guardar Averiadas
        ws_av = sh.worksheet(tab_av)
        ws_av.clear()
        if datos["averiadas"]:
            ws_av.update(range_name='A1', values=[[str(a)] for a in datos["averiadas"]])
            
    except Exception as e:
        st.error(f"Error guardando: {e}")

# --- HISTORIAL (POR USUARIO) ---
def recuperar_historial_por_fecha(fecha_dt, usuario):
    sh = conectar_google_sheets()
    if not sh: return []
    
    tab_hist = get_tab_name("Historial", usuario)

    try:
        ws = asegurar_pestana(sh, tab_hist, ["Fecha", "Estación", "Horario", "Unidades"])
        all_rows = ws.get_all_values()
        target = fecha_dt.strftime('%d/%m/%Y')
        reporte_recuperado = []
        
        for row in all_rows[1:]:
            if len(row) >= 4 and row[0] == target:
                unidades_str = row[3].split(',')
                unidades_int = []
                for u in unidades_str:
                    u_limpio = u.strip()
                    if u_limpio.isdigit(): unidades_int.append(int(u_limpio))
                
                reporte_recuperado.append({
                    "nombre": row[1],
                    "horario": row[2],
                    "unidades": sorted(unidades_int)
                })
        return reporte_recuperado
    except: return []

def guardar_historial_db(fecha, reporte_diario, usuario):
    sh = conectar_google_sheets()
    if not sh: return False
    
    tab_hist = get_tab_name("Historial", usuario)

    try:
        ws_hist = asegurar_pestana(sh, tab_hist, ["Fecha", "Estación", "Horario", "Unidades"])
        all_rows = ws_hist.get_all_values()
        fecha_str = fecha.strftime('%d/%m/%Y')
        
        # Filtrar para no duplicar (sobrescribir día)
        new_data = []
        if all_rows:
            new_data.append(all_rows[0]) # Header
            for row in all_rows[1:]:
                if len(row) > 0 and row[0] != fecha_str:
                    new_data.append(row)
        else:
            new_data.append(["Fecha", "Estación", "Horario", "Unidades"])

        for item in reporte_diario:
            unidades_str = ", ".join([f"{u:02d}" for u in item['unidades']])
            row = [fecha_str, item['nombre'], item['horario'], unidades_str]
            new_data.append(row)

        ws_hist.clear()
        ws_hist.update(range_name='A1', values=new_data)
        return True
            
    except Exception as e:
        print(f"Error historial: {e}")
        return False
    
def registrar_usuario_con_totp(usuario, password, totp_secret):
    """Guarda usuario, pass hasheado y el secreto de Google Auth"""
    sh = conectar_google_sheets()
    if not sh: return False, "Error conexión."
    
    usuario_limpio = usuario.strip().lower()
    
    try:
        ws = sh.worksheet("Usuarios")
        usuarios_existentes = [str(u).lower() for u in ws.col_values(1)]
        
        if usuario_limpio in usuarios_existentes:
            return False, "⚠️ Usuario ya existe."
        
        pass_hash = hacer_hash(password)
        # Guardamos el secreto TOTP tal cual (es necesario para validar después)
        ws.append_row([usuario_limpio, pass_hash, totp_secret])
        
        # --- CREACIÓN DE PESTAÑAS (Igual que antes) ---
        # ... Copia aquí tu código de asegurar_pestana y la inicialización ...
        # (Para resumir, asumo que tienes las funciones auxiliares aquí abajo)
        return True, "✅ Usuario registrado. Configura tu Google Authenticator."
    except Exception as e:
        return False, f"Error: {e}"

# --- RECUPERAR CONTRASEÑA USANDO CÓDIGO TOTP ---
def restablecer_con_totp(usuario, codigo_input, nueva_password):
    sh = conectar_google_sheets()
    if not sh: return False, "Error conexión."

    try:
        ws = sh.worksheet("Usuarios")
        filas = ws.get_all_values()
        usuario_target = usuario.strip().lower()
        
        fila_encontrada = -1
        secreto_db = None
        
        # 1. Buscar usuario y obtener su secreto
        for i, fila in enumerate(filas):
            if i == 0: continue
            if len(fila) >= 3:
                if str(fila[0]).strip().lower() == usuario_target:
                    secreto_db = str(fila[2]) # Columna 3 es TOTP_Secret
                    fila_encontrada = i + 1
                    break
        
        if not secreto_db:
            return False, "Usuario no encontrado."

        # 2. VALIDAR EL CÓDIGO DE GOOGLE AUTH
        totp = pyotp.TOTP(secreto_db)
        # verify(codigo) devuelve True si el código es correcto y actual
        if totp.verify(codigo_input):
            # 3. Si es correcto, cambiamos la contraseña
            nuevo_hash = hacer_hash(nueva_password)
            ws.update_cell(fila_encontrada, 2, nuevo_hash)
            return True, "✅ Contraseña restablecida correctamente."
        else:
            return False, "❌ Código de Google Authenticator inválido o expirado."

    except Exception as e:
        return False, f"Error: {e}"