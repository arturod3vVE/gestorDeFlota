import os
import re
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import streamlit as st

# --- RUTAS ABSOLUTAS LOCALES ---
# Esto buscará las fuentes en la misma carpeta donde está este script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_REGULAR = os.path.join(BASE_DIR, "Roboto-Regular.ttf")
FONT_BOLD = os.path.join(BASE_DIR, "Roboto-Bold.ttf")
ICONO_BOMBA = os.path.join(BASE_DIR, "icono_bomba.png")

@st.cache_resource
def obtener_icono_local():
    """Descarga el icono si no existe, o lo carga desde el disco."""
    img_icon = None
    url_icon = "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/26fd.png"
    
    if not os.path.exists(ICONO_BOMBA):
        try:
            r = requests.get(url_icon, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            if r.status_code == 200:
                with open(ICONO_BOMBA, 'wb') as f:
                    f.write(r.content)
        except: pass
        
    if os.path.exists(ICONO_BOMBA):
        try:
            img_icon = Image.open(ICONO_BOMBA).convert("RGBA")
            img_icon = img_icon.resize((40, 40))
        except: pass
        
    return img_icon

def cargar_fuente_local(ruta_fuente, tamaño):
    """Carga la fuente directamente desde el archivo local."""
    if not os.path.exists(ruta_fuente):
        print(f"⚠️ ERROR: No se encontró el archivo {ruta_fuente}. Asegúrate de subirlo al servidor.")
        return ImageFont.load_default()
        
    try:
        return ImageFont.truetype(ruta_fuente, tamaño)
    except Exception as e:
        print(f"⚠️ Error cargando {ruta_fuente}: {e}")
        return ImageFont.load_default()

def limpiar_texto(texto):
    # Se mantienen los caracteres válidos, incluyendo tildes y eñes
    return re.sub(r'[^\w\s\.,:;\-\(\)\/áéíóúÁÉÍÓÚñÑ]', '', str(texto))

def generar_imagen_en_memoria(reporte_lista, fecha_dt, rango_txt, config_datos):
    icon_res = obtener_icono_local()
    
    ANCHO = config_datos.get("img_width", 450)
    FONT_S = config_datos.get("font_size", 24)
    BG = config_datos.get("bg_color", "#ECE5DD")
    try: PALETA = config_datos.get("st_colors", ["#f8d7da"])
    except: PALETA = ["#f8d7da"]
    TXT_COL = config_datos.get("text_color", "#000000")
    
    LH = int(FONT_S * 1.3)
    GAP = int(FONT_S * 1.5)
    
    # Cargamos las fuentes LOCALES directamente
    f_ti = cargar_fuente_local(FONT_BOLD, FONT_S + 4)
    f_bd = cargar_fuente_local(FONT_BOLD, FONT_S)
    f_no = cargar_fuente_local(FONT_REGULAR, FONT_S)

    img = Image.new('RGB', (ANCHO, 3000), color=BG)
    d = ImageDraw.Draw(img)
    y = 40
    w_draw = ANCHO - 40

    def draw_centered(txt, y_pos, fnt, bg_col="#d1e7dd"):
        if not txt: return y_pos
        txt = limpiar_texto(str(txt)).upper()
        
        lines = []
        cur = ""
        words = txt.split()
        
        for w in words:
            bbox = d.textbbox((0,0), w, font=fnt)
            w_word = bbox[2] - bbox[0]
            
            if w_word > w_draw:
                if cur: lines.append(cur)
                lines.append(w)
                cur = ""
                continue

            bbox_line = d.textbbox((0,0), cur + w + " ", font=fnt)
            if (bbox_line[2] - bbox_line[0]) > w_draw:
                lines.append(cur)
                cur = w + " "
            else:
                cur += w + " "
        if cur: lines.append(cur)
        
        for l in lines:
            l = l.strip()
            if not l: continue
            bb = d.textbbox((0,0), l, font=fnt)
            w_l = bb[2] - bb[0]
            
            x_start = (ANCHO - w_l) / 2
            d.rectangle([(x_start - 5, y_pos), (x_start + w_l + 5, y_pos + LH + 2)], fill=bg_col)
            d.text((x_start, y_pos), l, font=fnt, fill=TXT_COL)
            y_pos += int(LH * 1.3)
        return y_pos + 8

    dias = {0:"LUNES",1:"MARTES",2:"MIÉRCOLES",3:"JUEVES",4:"VIERNES",5:"SÁBADO",6:"DOMINGO"}
    dia_txt = dias.get(fecha_dt.weekday(), "")
    f_str = f"{dia_txt} {fecha_dt.strftime('%d/%m/%y')}"
    
    col_ti = PALETA[2] if len(PALETA)>2 else "#d1e7dd"
    y = draw_centered("REPORTE DE ESTACIONES DE", y, f_ti, col_ti)
    y = draw_centered(f"SERVICIO Y UNIDADES {f_str}", y, f_ti, col_ti)
    
    if icon_res:
        isz = int(FONT_S * 1.5)
        try:
            icon_draw = icon_res.resize((isz, isz))
            cnt = 5
            tot_w = (isz*cnt) + (8*(cnt-1))
            if tot_w > w_draw: 
                cnt = 3
                tot_w = (isz*cnt) + (8*(cnt-1))
            sx = (ANCHO - tot_w)/2
            for i in range(cnt):
                img.paste(icon_draw, (int(sx + i*(isz+8)), y), icon_draw)
            y += int(isz * 1.5)
        except: y += LH
    else:
        y += LH

    for i, st_data in enumerate(reporte_lista):
        col = PALETA[i % len(PALETA)]
        nom = limpiar_texto(st_data['nombre']).upper()
        hor = limpiar_texto(st_data['horario']).upper()
        
        txt_st = f"• ESTACIÓN {nom}: {hor}" if hor else f"• ESTACIÓN {nom}"
            
        lines_t = []
        cur_t = ""
        for w in txt_st.split():
            if d.textbbox((0,0), cur_t + w + " ", font=f_bd)[2] > w_draw:
                lines_t.append(cur_t)
                cur_t = w + " "
            else:
                cur_t += w + " "
        if cur_t: lines_t.append(cur_t)
        
        for l in lines_t:
            bb = d.textbbox((0,0), l, font=f_bd)
            w_l = bb[2] - bb[0]
            d.rectangle([(20, y), (20 + w_l + 10, y + LH + 4)], fill=col)
            d.text((25, y + 2), l, font=f_bd, fill=TXT_COL)
            y += int(LH * 1.2)
        
        nums = " ".join([f"{u:02d}" for u in st_data['unidades']])
        lines_n = []
        cur_n = ""
        for w in nums.split():
            if d.textbbox((0,0), cur_n + w + " ", font=f_no)[2] > w_draw:
                lines_n.append(cur_n)
                cur_n = w + " "
            else:
                cur_n += w + " "
        if cur_n: lines_n.append(cur_n)
        
        for l in lines_n:
            d.text((20, y), l, font=f_no, fill=TXT_COL)
            y += LH
        y += GAP

    if rango_txt:
        txt_r = "• RANGO DE UNIDADES"
        bb_r = d.textbbox((0,0), txt_r, font=f_bd)
        w_r = bb_r[2] - bb_r[0]
        d.rectangle([(20, y), (20 + w_r + 10, y + LH + 4)], fill="#cff4fc")
        d.text((25, y + 2), txt_r, font=f_bd, fill=TXT_COL)
        y += int(LH * 1.2)
        
        ran_clean = limpiar_texto(rango_txt).upper()
        lines_r = []
        cur_r = ""
        for w in ran_clean.split():
            if d.textbbox((0,0), cur_r + w + " ", font=f_no)[2] > w_draw:
                lines_r.append(cur_r)
                cur_r = w + " "
            else:
                cur_r += w + " "
        if cur_r: lines_r.append(cur_r)
        
        for l in lines_r:
            d.text((20, y), l, font=f_no, fill=TXT_COL)
            y += LH
        y += GAP

    out = img.crop((0, 0, ANCHO, y + 20))
    buf = BytesIO()
    out.save(buf, "PNG")
    buf.seek(0)
    return buf
