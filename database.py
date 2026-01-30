import streamlit as st
import gspread
import hashlib
import json
import pyotp

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
        print(f"Error de conexión: {e}")
        return None

def hacer_hash(texto):
    return hashlib.sha256(str(texto).encode('utf-8')).hexdigest()

def asegurar_pestana(sh, nombre):
    try:
        return sh.worksheet(nombre)
    except:
        return sh.add_worksheet(nombre, 100, 20)

# --- USUARIOS ---
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

def registrar_usuario_con_totp(usuario, password, totp_secret):
    sh = conectar_google_sheets()
    if not sh: return False, "Error conexión."
    usuario_limpio = usuario.strip().lower()
    try:
        ws = sh.worksheet("Usuarios")
        usuarios_existentes = [str(u).lower() for u in ws.col_values(1)]
        if usuario_limpio in usuarios_existentes: return False, "Usuario ya existe."
        pass_hash = hacer_hash(password)
        ws.append_row([usuario_limpio, pass_hash, totp_secret])
        return True, "Registrado."
    except Exception as e: return False, f"Error: {e}"

def restablecer_con_totp(usuario, codigo_input, nueva_password):
    sh = conectar_google_sheets()
    if not sh: return False, "Error conexión."
    try:
        ws = sh.worksheet("Usuarios")
        filas = ws.get_all_values()
        u_target = usuario.strip().lower()
        for i, fila in enumerate(filas):
            if i == 0: continue
            if len(fila) >= 3 and str(fila[0]).strip().lower() == u_target:
                secret = str(fila[2])
                totp = pyotp.TOTP(secret)
                if totp.verify(codigo_input, valid_window=1):
                    ws.update_cell(i + 1, 2, hacer_hash(nueva_password))
                    return True, "Contraseña cambiada."
                else: return False, "Código inválido."
        return False, "Usuario no encontrado."
    except: return False, "Error inesperado."

# --- CONFIGURACIÓN ---
def cargar_datos_db(usuario):
    sh = conectar_google_sheets()
    if not sh: return {}
    
    # Datos por defecto
    datos = {
        "rangos": [[1, 500]],
        "averiadas": [],
        "estaciones": [],
        "font_size": 24,
        "img_width": 450,
        "bg_color": "#ECE5DD",
        "text_color": "#000000",
        "st_colors": ["#f8d7da"]*6
    }
    
    try:
        nombre_pestana = f"Config_{usuario.strip().lower()}"
        ws = asegurar_pestana(sh, nombre_pestana)
        
        raw_data = ws.get_all_values()
        config_dict = {}
        for fila in raw_data:
            if len(fila) >= 2:
                config_dict[str(fila[0]).strip()] = str(fila[1]).strip()
        
        # 1. RANGOS
        if "Rangos" in config_dict:
            txt = config_dict["Rangos"]
            try:
                parsed = []
                for p in txt.split(','):
                    if '-' in p:
                        a, b = p.split('-')
                        parsed.append([int(a), int(b)])
                if parsed: datos["rangos"] = parsed
            except: pass

        # 2. ESTACIONES
        if "Estaciones" in config_dict:
            txt = config_dict["Estaciones"]
            if txt:
                datos["estaciones"] = [e.strip() for e in txt.split(';;') if e.strip()]

        # 3. AVERIADAS
        if "Averiadas" in config_dict:
            txt = config_dict["Averiadas"]
            if txt:
                datos["averiadas"] = [int(x) for x in txt.split(',') if x.strip().isdigit()]

        # 4. APARIENCIA
        if "FontSize" in config_dict: datos["font_size"] = int(config_dict["FontSize"])
        if "ImgWidth" in config_dict: datos["img_width"] = int(config_dict["ImgWidth"])
        if "BgColor" in config_dict: datos["bg_color"] = config_dict["BgColor"]
        if "TextColor" in config_dict: datos["text_color"] = config_dict["TextColor"]
        if "StColors" in config_dict:
            try: datos["st_colors"] = json.loads(config_dict["StColors"])
            except: pass

    except Exception as e:
        print(f"Error cargando config: {e}")
        
    return datos

def guardar_datos_db(datos, usuario):
    sh = conectar_google_sheets()
    if not sh: return False
    
    try:
        nombre_pestana = f"Config_{usuario.strip().lower()}"
        ws = asegurar_pestana(sh, nombre_pestana)
        
        txt_rangos = ", ".join([f"{r[0]}-{r[1]}" for r in datos.get("rangos", [[1,500]])])
        txt_estaciones = ";;".join(datos.get("estaciones", []))
        txt_averiadas = ", ".join(map(str, datos.get("averiadas", [])))
        json_colors = json.dumps(datos.get("st_colors", ["#fff"]*6))
        
        rows = [
            ["Rangos", txt_rangos],
            ["Estaciones", txt_estaciones],
            ["Averiadas", txt_averiadas],
            ["FontSize", datos.get("font_size", 24)],
            ["ImgWidth", datos.get("img_width", 450)],
            ["BgColor", datos.get("bg_color", "#ECE5DD")],
            ["TextColor", datos.get("text_color", "#000000")],
            ["StColors", json_colors]
        ]
        
        ws.clear()
        ws.update(range_name="A1", values=rows)
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

# --- HISTORIAL (CORREGIDO) ---
def guardar_historial_db(fecha, reporte, usuario):
    sh = conectar_google_sheets()
    if not sh: return False
    try:
        nombre_pestana = f"Historial_{usuario.strip().lower()}"
        ws = asegurar_pestana(sh, nombre_pestana)
        
        # --- CORRECCIÓN: Verificar encabezados explícitamente ---
        encabezados = ["Fecha", "Usuario", "JSON"]
        
        # Leemos solo la primera fila
        primera_fila = ws.row_values(1)
        
        # Si la primera fila no coincide con los encabezados (o está vacía)
        if not primera_fila or primera_fila != encabezados:
            # Insertamos los encabezados en la Fila 1
            ws.insert_row(encabezados, index=1)
            
        fecha_str = fecha.strftime("%Y-%m-%d")
        json_reporte = json.dumps(reporte, ensure_ascii=False)
        
        # Guardamos la fila nueva (se añadirá DESPUÉS de los encabezados)
        ws.append_row([fecha_str, usuario, json_reporte])
        return True
    except Exception as e: 
        print(f"Error guardando historial: {e}")
        return False

def recuperar_historial_por_fecha(fecha, usuario):
    sh = conectar_google_sheets()
    if not sh: return []
    try:
        nombre_pestana = f"Historial_{usuario.strip().lower()}"
        ws = asegurar_pestana(sh, nombre_pestana)
        
        # Usamos get_all_records que espera encabezados en la fila 1
        # Si no hay encabezados, puede fallar, así que lo protegemos
        try:
            records = ws.get_all_records()
        except:
            # Si falla (ej: hoja vacía o corrupta), devolvemos lista vacía
            return []
            
        fecha_target = fecha.strftime("%Y-%m-%d")
        encontrado = []
        for r in records:
            # Convertimos a string por seguridad
            if str(r.get("Fecha")) == fecha_target:
                try: encontrado = json.loads(r.get("JSON", "[]"))
                except: pass
        return encontrado
    except: return []