import streamlit as st
import gspread
import hashlib
import json
import pyotp
from datetime import datetime
import pytz

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

def obtener_fecha_creacion_original(fecha, usuario):
    sh = conectar_google_sheets()
    if not sh: return None
    try:
        nombre_pestana = f"Historial_{usuario.strip().lower()}"
        ws = asegurar_pestana(sh, nombre_pestana)
        
        fecha_target = fecha.strftime("%Y-%m-%d")
        records = ws.get_all_records() # Devuelve lista de diccionarios
        
        for r in records:
            if str(r.get("Fecha")) == fecha_target:
                # Retornamos lo que haya en la columna 'Creado'
                return r.get("Creado", None)
        return None
    except: return None

def recuperar_historial_rango(usuario, f_inicio, f_fin):
    sh = conectar_google_sheets()
    if not sh: return []
    try:
        nombre_pestana = f"Historial_{usuario.strip().lower()}"
        ws = asegurar_pestana(sh, nombre_pestana)
        
        try: records = ws.get_all_records()
        except: return []
        
        resultados = []
        
        s_inicio = f_inicio.strftime("%Y-%m-%d")
        s_fin = f_fin.strftime("%Y-%m-%d")
        
        for r in records:
            fecha_str = str(r.get("Fecha"))
            if s_inicio <= fecha_str <= s_fin:
                try:
                    data = {
                        "fecha": fecha_str,
                        "reporte": json.loads(r.get("JSON", "[]")),
                        "creado": r.get("Creado", ""),
                        "actualizado": r.get("Actualizado", "")
                    }
                    resultados.append(data)
                except: pass
                
        # Ordenamos: El más reciente primero
        resultados.sort(key=lambda x: x["fecha"], reverse=True)
        return resultados
    except Exception as e:
        print(f"Error historial rango: {e}")
        return []

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
def guardar_historial_db(fecha, reporte, usuario, fecha_creacion_preservada=None):
    sh = conectar_google_sheets()
    if not sh: return False
    try:
        nombre_pestana = f"Historial_{usuario.strip().lower()}"
        ws = asegurar_pestana(sh, nombre_pestana)
        
        # Nuevos encabezados
        nuevos_encabezados = ["Fecha", "Usuario", "JSON", "Creado", "Actualizado"]
        
        # Verificamos/Actualizamos encabezados
        primera_fila = ws.row_values(1)
        if not primera_fila:
            ws.append_row(nuevos_encabezados)
        elif len(primera_fila) < 5 and "Creado" not in primera_fila:
            ws.update(range_name="D1:E1", values=[["Creado", "Actualizado"]])

        fecha_str = fecha.strftime("%Y-%m-%d")
        json_reporte = json.dumps(reporte, ensure_ascii=False)
        
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        creado = fecha_creacion_preservada if fecha_creacion_preservada else ahora
        actualizado = ahora
        
        # Guardamos con las 5 columnas
        ws.append_row([fecha_str, usuario, json_reporte, creado, actualizado])
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
        
        try:
            records = ws.get_all_records()
        except:
            return []
            
        fecha_target = fecha.strftime("%Y-%m-%d")
        encontrado = []
        for r in records:
            if str(r.get("Fecha")) == fecha_target:
                try: encontrado = json.loads(r.get("JSON", "[]"))
                except: pass
        return encontrado
    except: return []

def eliminar_historial_por_fecha(fecha, usuario):
    sh = conectar_google_sheets()
    if not sh: return False
    try:
        nombre_pestana = f"Historial_{usuario.strip().lower()}"
        ws = asegurar_pestana(sh, nombre_pestana)
        
        fecha_target = fecha.strftime("%Y-%m-%d")
        
        rows = ws.get_all_values()
        if not rows: return True
        
        new_rows = [rows[0]] # Encabezados
        data_rows = rows[1:] # Datos
        filtrados = []

        for r in data_rows:
            if len(r) > 0:
                if str(r[0]).strip() == fecha_target:
                    continue 
            filtrados.append(r)
            
        final_rows = new_rows + filtrados
        
        # 3. Limpiar y reescribir
        ws.clear()
        ws.update(range_name="A1", values=final_rows)
        return True
        
    except Exception as e:
        print(f"Error eliminando historial: {e}")
        return False