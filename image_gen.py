import os
import requests
import re
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# Nombres de archivos
FONT_REGULAR = "Roboto-Regular.ttf"
FONT_BOLD = "Roboto-Bold.ttf"
ICONO_BOMBA = "icono_bomba.png"

def descargar_fuentes():
    urls = {
        FONT_REGULAR: "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf",
        FONT_BOLD: "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
    }
    for filename, url in urls.items():
        if not os.path.exists(filename):
            try:
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    with open(filename, 'wb') as f:
                        f.write(r.content)
            except Exception as e:
                print(f"No se pudo descargar {filename}: {e}")
                pass

def obtener_icono_bomba():
    if not os.path.exists(ICONO_BOMBA):
        try:
            url = "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/26fd.png"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content)).convert("RGBA")
                img = img.resize((40, 40))
                img.save(ICONO_BOMBA)
                return img
        except: return None
    else:
        try: return Image.open(ICONO_BOMBA).convert("RGBA")
        except: return None

def limpiar_texto(texto):
    return re.sub(r'[^\w\s\.,:;\-\(\)\/\u00C0-\u00FF]', '', str(texto))

def cargar_fuente_segura(tipo, tamaño):
    if tipo == "bold":
        archivo_roboto = FONT_BOLD
        sistema_arial = "arialbd.ttf"
        sistema_linux = "DejaVuSans-Bold.ttf"
    else:
        archivo_roboto = FONT_REGULAR
        sistema_arial = "arial.ttf"
        sistema_linux = "DejaVuSans.ttf"

    try: return ImageFont.truetype(archivo_roboto, tamaño)
    except: pass
    try: return ImageFont.truetype(sistema_arial, tamaño)
    except: pass
    try: return ImageFont.truetype(sistema_linux, tamaño)
    except: pass
    return ImageFont.load_default()

def generar_imagen_en_memoria(reporte_lista, fecha_dt, rango_txt, config_datos):
    descargar_fuentes()
    
    ANCHO = config_datos.get("img_width", 450)
    FONT_S = config_datos.get("font_size", 24)
    BG = config_datos.get("bg_color", "#ECE5DD")
    PALETA = config_datos.get("st_colors", ["#f8d7da"])
    # COLOR DE TEXTO DINÁMICO
    TXT_COL = config_datos.get("text_color", "#000000")
    
    LH = int(FONT_S * 1.3)
    GAP = int(FONT_S * 1.5)
    
    f_ti = cargar_fuente_segura("bold", FONT_S + 4)
    f_bd = cargar_fuente_segura("bold", FONT_S)
    f_no = cargar_fuente_segura("regular", FONT_S)

    img = Image.new('RGB', (ANCHO, 3000), color=BG)
    d = ImageDraw.Draw(img)
    y = 40
    w_draw = ANCHO - 40

    def draw_centered(txt, y_pos, fnt, bg_col="#d1e7dd"):
        txt = limpiar_texto(txt).upper()
        lines = []
        cur = ""
        for w in txt.split():
            if d.textbbox((0,0), cur + w + " ", font=fnt)[2] > w_draw:
                lines.append(cur)
                cur = w + " "
            else:
                cur += w + " "
        if cur: lines.append(cur)
        
        for l in lines:
            bb = d.textbbox((0,0), l, font=fnt)
            w_l = bb[2] - bb[0]
            d.rectangle([(ANCHO/2 - w_l/2 - 10, y_pos), (ANCHO/2 + w_l/2 + 10, y_pos + LH + 5)], fill=bg_col)
            # Usamos el color de texto dinámico
            d.text((ANCHO/2 - w_l/2, y_pos), l, font=fnt, fill=TXT_COL)
            y_pos += int(LH * 1.4)
        return y_pos + 10

    dias = {0:"lunes",1:"martes",2:"miércoles",3:"jueves",4:"viernes",5:"sábado",6:"domingo"}
    f_str = f"{dias[fecha_dt.weekday()]} {fecha_dt.strftime('%d/%m/%y')}".upper()
    
    col_ti = PALETA[2] if len(PALETA)>2 else "#d1e7dd"
    y = draw_centered("REPORTE DE ESTACIONES DE", y, f_ti, col_ti)
    y = draw_centered(f"SERVICIO Y UNIDADES {f_str}", y, f_ti, col_ti)
    
    icon = obtener_icono_bomba()
    if icon:
        isz = int(FONT_S * 1.5)
        icon_res = icon.resize((isz, isz))
        cnt = 5
        tot_w = (isz*cnt) + (8*(cnt-1))
        if tot_w > w_draw: 
            cnt = 3
            tot_w = (isz*cnt) + (8*(cnt-1))
        sx = (ANCHO - tot_w)/2
        for i in range(cnt):
            img.paste(icon_res, (int(sx + i*(isz+8)), y), icon_res)
        y += int(isz * 1.5)
    else:
        y += LH

    for i, st_data in enumerate(reporte_lista):
        col = PALETA[i % len(PALETA)]
        nom = limpiar_texto(st_data['nombre']).upper()
        hor = limpiar_texto(st_data['horario']).upper()
        
        if hor: 
            txt_st = f"• ESTACIÓN {nom}: {hor}"
        else: 
            txt_st = f"• ESTACIÓN {nom}"
            
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
            w_l = bb[2]
            d.rectangle([(20, y), (20 + w_l + 10, y + LH + 4)], fill=col)
            # Texto dinámico
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
            # Texto dinámico
            d.text((20, y), l, font=f_no, fill=TXT_COL)
            y += LH
        y += GAP

    bb_r = d.textbbox((0,0), "• RANGO DE UNIDADES", font=f_bd)
    d.rectangle([(20, y), (20 + bb_r[2] + 10, y + LH + 4)], fill="#cff4fc")
    # Texto dinámico
    d.text((25, y + 2), "• RANGO DE UNIDADES", font=f_bd, fill=TXT_COL)
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
        # Texto dinámico
        d.text((20, y), l, font=f_no, fill=TXT_COL)
        y += LH
    y += GAP

    out = img.crop((0, 0, ANCHO, y + 20))
    buf = BytesIO()
    out.save(buf, "PNG")
    buf.seek(0)
    return buf