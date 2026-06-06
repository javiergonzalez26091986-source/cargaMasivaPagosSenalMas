import streamlit as st
import pandas as pd
import requests
import re
import io
import os
import time
import base64
from datetime import datetime
from PIL import Image

# --- CONFIGURACIÓN DE APIS ---
CLOUDINARY_CLOUD_NAME = "dgdtwbmot"
CLOUDINARY_PRESET = "conexion_pagos_preset1"
OCR_SPACE_API_KEY = "helloworld" 

# --- INICIALIZACIÓN DE ESTADOS (PARA LIMPIAR LOS CAMPOS AUTOMÁTICAMENTE) ---
if "file_key" not in st.session_state:
    st.session_state.file_key = 0
if "excel_data" not in st.session_state:
    st.session_state.excel_data = None
if "df_preview" not in st.session_state:
    st.session_state.df_preview = None
if "lote_fecha" not in st.session_state:
    st.session_state.lote_fecha = ""

# --- FUNCIÓN DE LIMPIEZA POST-DESCARGA ---
def limpiar_sesion():
    st.session_state.file_key += 1
    st.session_state.excel_data = None
    st.session_state.df_preview = None
    st.session_state.lote_fecha = ""

# --- CARGAR IMÁGENES (LOGO E ÍCONO) ---
ruta_logo = 'logoSenalMas.jpeg'
ruta_icono = 'logoSenalMas.ico'

# Función para convertir la imagen local a base64 (para pegarla al título sin espacios)
def get_image_base64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None

logo_b64 = get_image_base64(ruta_logo)

try:
    if os.path.exists(ruta_icono):
        isotipo = Image.open(ruta_icono)
    else:
        isotipo = "🪄"
except Exception:
    isotipo = "🪄"

# --- CONFIGURACIÓN DE PÁGINA Y ESTILOS ---
st.set_page_config(page_title="Señal Más | Cargue Masivo", page_icon=isotipo, layout="wide")

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        .stAppDeployButton {display:none;} div[data-testid="stToolbar"] { visibility: hidden !important; }
        .main { background-color: #00233c; } .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
        h1, h3 { text-align: center !important; }
        h1 { color: #ffffff; font-size: 2.2rem; font-weight: 700; }
        h3 { color: #b0c4de; font-size: 1.1rem; font-weight: 400; margin-bottom: 2.5rem; }
        p, .stMarkdown p { color: #ffffff; }
        .stTextInput > div > div > input { background-color: #ffffff; color: #00233c; border-radius: 8px; border: 2px solid #00a896; }
        div[data-testid="stFormSubmitButton"] button, .stButton button {
            background-color: #00a896 !important; color: #ffffff !important; border-radius: 8px !important;
            font-weight: 700 !important; border: none !important; box-shadow: 0 4px 10px rgba(0,168,150,0.3) !important;
        }
        .stButton button:hover { background-color: #02c3b1 !important; box-shadow: 0 6px 15px rgba(2,195,177,0.5) !important; }
        .stDataFrame {background-color: white;}
    </style>
    """, unsafe_allow_html=True)

# --- ENCABEZADO CON LOGO Y TÍTULO CENTRADOS ---
if logo_b64:
    st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: center; gap: 15px; margin-bottom: 5px;">
            <img src="data:image/jpeg;base64,{logo_b64}" style="height: 55px; border-radius: 8px;">
            <h1 style="margin: 0; padding: 0; text-align: center !important;">🪄 Portal de Cargue Masivo</h1>
        </div>
        """, unsafe_allow_html=True)
else:
    st.markdown("<h1 style='text-align: center !important;'>🪄 Portal de Cargue Masivo</h1>", unsafe_allow_html=True)

st.subheader("Análisis óptico, validación de contratos y consolidación de reportes")

# --- FUNCIONES NÚCLEO ---

def subir_a_cloudinary(archivo_subido):
    url_api = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/auto/upload"
    payload = {"upload_preset": CLOUDINARY_PRESET}
    files = {"file": (archivo_subido.name, archivo_subido.getvalue(), archivo_subido.type)}
    try:
        response = requests.post(url_api, data=payload, files=files)
        return response.json().get("secure_url") if response.status_code == 200 else "Error de subida"
    except Exception:
        return "Error de subida"

def ejecutar_lector_optico(archivo):
    texto_completo = ""
    
    # 1. Intentar leer si es PDF
    if archivo.type == "application/pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(archivo)
            for page in reader.pages: texto_completo += page.extract_text() or ""
        except Exception: pass
            
    # 2. Si está vacío, usar OCR.space
    if not texto_completo.strip():
        try:
            url_ocr = "https://api.ocr.space/parse/image"
            payload = {
                "apikey": OCR_SPACE_API_KEY, 
                "language": "spa", 
                "isOverlayRequired": False,
                "OCREngine": "2",  
                "scale": "true"    
            }
            files = {"file": (archivo.name, archivo.getvalue(), archivo.type)}
            res = requests.post(url_ocr, data=payload, files=files, timeout=20)
            
            if res.status_code == 200 and not res.json().get("IsErroredOnProcessing"):
                resultados = res.json().get("ParsedResults", [])
                if resultados:
                    texto_completo = resultados[0].get("ParsedText", "")
        except Exception: pass
            
    valor_detectado = 0
    ref_detectada = "Lectura IA"
    
    # 3. Lógica de extracción de datos
    if texto_completo:
        texto_clean = texto_completo.lower().replace('\n', ' ').replace('\r', ' ')
        texto_clean = re.sub(r'\s+', ' ', texto_clean)
        
        # --- EXTRACCIÓN DE VALOR MONETARIO ---
        patrones_valor = [
            r'(?:valor|monto|total|efectivo|pagar)\s*[:\$]*\s*([\d\.,]{4,15})', 
            r'[\$s5]\s*([\d\.,]{4,15})' 
        ]
        
        for patron in patrones_valor:
            match = re.search(patron, texto_clean)
            if match:
                raw_val = match.group(1)
                raw_val = re.sub(r'[,.]\d{2}$', '', raw_val)
                num_clean = raw_val.replace(".", "").replace(",", "")
                if num_clean.isdigit(): 
                    v = int(num_clean)
                    if 10000 <= v <= 500000:
                        valor_detectado = v
                        break
        
        if valor_detectado == 0:
            posibles_numeros = re.findall(r'\b\d{2,3}[\.,]?\d{3}\b', texto_clean)
            for pv in posibles_numeros:
                num_clean = pv.replace(".", "").replace(",", "")
                if num_clean.isdigit():
                    v = int(num_clean)
                    if 10000 <= v <= 500000 and v % 1000 == 0:
                        valor_detectado = v
                        break 

        # --- EXTRACCIÓN DE REFERENCIA (SISTEMA DE 4 NIVELES) ---
        patrones_ref = [
            r'movimiento\s*[:\-\s]*([a-z0-9]{6,20})', 
            r'(?:referencia|comprobante|aprobaci[óo]n|autorizaci[óo]n|transacci[óo]n|recibo)\s*[:\-\s]*(?:n[oó]?|num)?\s*([a-z0-9]{5,20})', 
            r'\b(m\d{6,15})\b', 
            r'\b(\d{9,15})\b'   
        ]
        
        for patron in patrones_ref:
            match = re.search(patron, texto_clean)
            if match:
                posible_ref = match.group(1).upper()
                if not posible_ref.isalpha() and posible_ref not in ["BANCOLOMBIA", "TRANSFERENCIA", "MOVIMIENTO"]:
                    if posible_ref.isdigit() and len(posible_ref) == 8 and posible_ref.startswith("202"):
                        continue
                    ref_detectada = posible_ref
                    break 
                     
    return valor_detectado, ref_detectada

# --- INTERFAZ DE CARGA DINÁMICA ---
col1, col2 = st.columns(2)
with col1:
    archivo_bd = st.file_uploader("1. Sube la Base de Datos (Excel o CSV)", type=['xlsx', 'csv'], key=f"bd_{st.session_state.file_key}")
with col2:
    archivos_soportes = st.file_uploader("2. Sube los Soportes de Pago", type=['png', 'jpg', 'jpeg', 'pdf'], accept_multiple_files=True, key=f"sop_{st.session_state.file_key}")

if archivo_bd and archivos_soportes:
    if st.button("🚀 Procesar Lote Completo", use_container_width=True):
        
        # 1. Cargar y limpiar la base de datos local
        try:
            if archivo_bd.name.endswith('.csv'):
                df_bd = pd.read_csv(archivo_bd)
            else:
                df_bd = pd.read_excel(archivo_bd)
            df_bd['CODIGO'] = df_bd['CODIGO'].astype(str).str.strip().str.replace('.0', '', regex=False)
        except Exception as e:
            st.error(f"Error al leer la base de datos: {e}")
            st.stop()

        # 2. Conteo de archivos para la asignación de contratos
        conteo_archivos = {}
        for archivo in archivos_soportes:
            partes = archivo.name.split('-')
            if len(partes) > 0:
                cedula = partes[0].strip()
                conteo_archivos[cedula] = conteo_archivos.get(cedula, 0) + 1

        contratos_disponibles = {}
        for cedula in conteo_archivos.keys():
            filas_cliente = df_bd[df_bd['CODIGO'] == cedula]
            if not filas_cliente.empty:
                contratos_disponibles[cedula] = filas_cliente['CONTRATO'].dropna().astype(str).tolist()
            else:
                contratos_disponibles[cedula] = []

        datos_excel = []
        barra_progreso = st.progress(0)
        texto_progreso = st.empty()

        # 3. Bucle de Procesamiento
        for i, archivo in enumerate(archivos_soportes):
            texto_progreso.markdown(f"<p style='text-align:center'>Procesando {i+1} de {len(archivos_soportes)}: <b>{archivo.name}</b>...</p>", unsafe_allow_html=True)
            
            partes = archivo.name.split('-')
            cedula = partes[0].strip() if len(partes) > 0 else "Sin Cedula"
            nombre_cliente = partes[1].strip() if len(partes) > 1 else archivo.name
            
            mes_pago = "Revisar"
            if len(partes) > 2:
                texto_mes = partes[2].upper().replace("PAGO MES ", "").split('.')[0].strip()
                mes_pago = texto_mes.capitalize()

            valor_ocr, ref_ocr = ejecutar_lector_optico(archivo)

            contrato_asignado = "Sin contrato en BD"
            lista_contratos_cliente = contratos_disponibles.get(cedula, [])
            
            if len(lista_contratos_cliente) == 1:
                contrato_asignado = lista_contratos_cliente[0]
            elif len(lista_contratos_cliente) > 1:
                if conteo_archivos.get(cedula, 0) == len(lista_contratos_cliente):
                    contrato_asignado = lista_contratos_cliente.pop(0) 
                else:
                    contrato_asignado = f"Revisar Múltiples ({', '.join(lista_contratos_cliente)})"

            url_soporte = subir_a_cloudinary(archivo)

            timestamp_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ref_sistema = f"Masivo_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}"
            
            fila = {
                "Timestamp": timestamp_actual,
                "Cedula": cedula,
                "NombreCliente": nombre_cliente,
                "Contrato": contrato_asignado,
                "ValorPagado": valor_ocr if valor_ocr > 0 else "",
                "FechaPago": timestamp_actual.split(" ")[0],
                "MesPago": mes_pago,
                "Estado": "Verificado (Cargue Masivo)",
                "Soporte de pago": url_soporte,
                "Referencia de Pago": ref_ocr,
                "Referencia del Sistema": ref_sistema,
                "Banco": "Pendiente Banco"
            }
            datos_excel.append(fila)
            
            barra_progreso.progress((i + 1) / len(archivos_soportes))

        # 4. Guardar datos en Memoria y preparar la vista (Ya no se limpia aquí automáticamente)
        df_resultado = pd.DataFrame(datos_excel)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_resultado.to_excel(writer, index=False, sheet_name='RegistroPagos')
        
        # Guardar en variables de sesión
        st.session_state.excel_data = output.getvalue()
        st.session_state.df_preview = df_resultado
        st.session_state.lote_fecha = datetime.now().strftime('%d%m%Y')
        
        texto_progreso.markdown("<p style='text-align:center; color:#00a896; font-weight:bold;'>✅ Procesamiento Óptico y Subida Completados.</p>", unsafe_allow_html=True)

# --- MOSTRAR RESULTADOS Y BOTONES DE ACCIÓN ---
if st.session_state.excel_data is not None:
    st.markdown("<br><h3 style='text-align:left !important;'>Vista Previa del Consolidado</h3>", unsafe_allow_html=True)
    st.dataframe(st.session_state.df_preview, use_container_width=True)
    
    col_dl, col_reset = st.columns(2)
    with col_dl:
        # El parámetro on_click=limpiar_sesion asegura que la limpieza se haga JUSTO después de descargar
        st.download_button(
            label="⬇️ Descargar Excel para Google Sheets",
            data=st.session_state.excel_data,
            file_name=f"Cargue_Masivo_{st.session_state.lote_fecha}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            on_click=limpiar_sesion 
        )
    with col_reset:
        if st.button("🔄 Reiniciar y Ocultar", use_container_width=True):
            limpiar_sesion()
            st.rerun()

st.markdown("---")
st.markdown('<p style="color: #b0c4de; text-align: center; font-size: 0.9rem;">Señal Más | Innovación y Conectividad | Automatización Masiva</p>', unsafe_allow_html=True)
