import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
from io import BytesIO
import datetime
# Si usas la librería oficial de Streamlit para Sheets:
from streamlit_gsheets import GSheetsConnection 

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Señal Más - Cargue Masivo", page_icon="🪄", layout="wide")

# Configurar Cloudinary usando los secretos de Streamlit
cloudinary.config(
    cloud_name = st.secrets["CLOUDINARY_CLOUD_NAME"],
    api_key = st.secrets["CLOUDINARY_API_KEY"],
    api_secret = st.secrets["CLOUDINARY_API_SECRET"]
)

# --- 2. FUNCIONES NÚCLEO ---

# Función para extraer valor con OCR (Debes adaptarla al motor que usaste en conexion-pagos-isp)
def extraer_valor_con_ocr(imagen_bytes):
    # AQUÍ VA TU LÓGICA DE INTELIGENCIA ARTIFICIAL / OCR
    # Ejemplo conceptual:
    # texto_extraido = mi_ia_ocr.analizar(imagen_bytes)
    # valor = buscar_regex_de_dinero(texto_extraido)
    
    # Retorno simulado para el ejemplo:
    return 85000 

@st.cache_data(ttl=600) # Caché de 10 minutos para no saturar la API de Google
def cargar_base_datos():
    # Conexión a Google Sheets usando st-gsheets-connection
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Reemplaza con la URL de tu archivo y el nombre de la pestaña
    df_bd = conn.read(spreadsheet="URL_DE_TU_GOOGLE_SHEETS", worksheet="baseDeDatos")
    return df_bd

# --- 3. INTERFAZ DE USUARIO ---
st.title("🪄 Señal Más - Cargue Masivo de Soportes")
st.write("Sube los soportes de pago. El sistema analizará las imágenes, cruzará los contratos y generará un archivo Excel listo para copiar y pegar en Google Sheets.")

archivos_subidos = st.file_uploader("Selecciona los soportes (imágenes)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

if archivos_subidos:
    if st.button("🚀 Procesar Soportes", type="primary"):
        
        # Cargar base de datos
        with st.spinner("Cargando base de datos de clientes..."):
            df_bd = cargar_base_datos()
            
        datos_excel = []
        barra_progreso = st.progress(0)
        
        for i, archivo in enumerate(archivos_subidos):
            # 1. Extraer Cédula y Mes del nombre del archivo
            nombre_limpio = archivo.name.split('.')[0]
            partes = nombre_limpio.split('-')
            
            cedula = partes[0].strip() if len(partes) > 0 else "Revisar"
            mes_pago = partes[2].replace("PAGO MES ", "").strip().capitalize() if len(partes) > 2 else "Revisar"
            nombre_cliente = partes[1].strip() if len(partes) > 1 else archivo.name
            
            # 2. Extraer Valor usando OCR
            valor_pagado = extraer_valor_con_ocr(archivo.getvalue())
            
            # 3. Lógica de Contratos en baseDeDatos
            # Filtramos la BD para ver cuántos contratos tiene esta cédula
            contratos_cliente = df_bd[df_bd['CODIGO'].astype(str).str.contains(cedula)]
            
            nota_contrato = ""
            if len(contratos_cliente) > 1:
                # Si tiene más de 1 contrato, buscamos cuál coincide con el valor del OCR
                match = contratos_cliente[contratos_cliente['VALOR_CONTRATO'] == valor_pagado]
                if not match.empty:
                    nota_contrato = f"Asignado automático: {valor_pagado}"
                else:
                    nota_contrato = f"Revisar: {len(contratos_cliente)} contratos. Valor OCR no coincide."
            else:
                nota_contrato = "Único contrato"

            # 4. Subir imagen a Cloudinary
            try:
                respuesta = cloudinary.uploader.upload(archivo.getvalue(), folder="Soportes_Masivos")
                url_soporte = respuesta.get("secure_url")
            except Exception as e:
                url_soporte = "Error al subir"
                
            # 5. Estructurar Fila para el Excel
            fila = {
                "Timestamp": datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                "Cedula": cedula,
                "NombreCliente": nombre_cliente,
                "Contrato": nota_contrato,
                "ValorPagado": valor_pagado,
                "FechaPago": "", # Puede extraerse con OCR también si lo deseas
                "MesPago": mes_pago,
                "Estado": "Verificado (Cargue Masivo)",
                "Soporte de pago": url_soporte,
                "Referencia de Pago": "Lectura OCR",
                "Referencia del Sistema": "Masivo_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
                "Banco": "Pendiente Banco"
            }
            datos_excel.append(fila)
            
            # Actualizar progreso
            barra_progreso.progress((i + 1) / len(archivos_subidos))
        
        st.success("✅ Procesamiento completado.")
        
        # --- 4. GENERACIÓN DEL EXCEL ---
        df_resultado = pd.DataFrame(datos_excel)
        
        # Mostrar vista previa en la Web App
        st.dataframe(df_resultado)
        
        # Convertir DataFrame a Excel en memoria (BytesIO) para el botón de descarga
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_resultado.to_excel(writer, index=False, sheet_name='RegistroPagos')
        datos_procesados = output.getvalue()
        
        st.download_button(
            label="⬇️ Descargar Archivo Excel",
            data=datos_procesados,
            file_name=f"Cargue_SenalMas_{datetime.datetime.now().strftime('%d%m%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
