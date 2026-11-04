import os
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation

def crear_plantilla_blanca():
    wb = openpyxl.Workbook()
    
    # ──────────────────────────────────────────────────────────────────────────
    # 1. PESTAÑA: CATALOGOS (Para los Dropdowns / Lookups)
    # ──────────────────────────────────────────────────────────────────────────
    ws_cat = wb.active
    ws_cat.title = "CATALOGOS"
    ws_cat.views.sheetView[0].showGridLines = True
    
    productos = [
        "GRAVA DE 3/4\"",
        "ARENA GRIS",
        "ARENA LAVADA",
        "GRAVILLA DE 3/8\"",
        "CEMENTO GRIS PORTLAND",
        "CASCAJO",
        "CORALINA",
        "BASE",
        "SUB-BASE",
        "CALICHE",
        "POLVILLO",
        "AGREGADO RECICLADO"
    ]
    
    plantas = [
        "Metaldom",
        "Haina",
        "Circunvalacion",
        "Esperanza",
        "Barahona",
        "Punta Cana",
        "SanIsidro",
        "Agua Clara"
    ]
    
    minas = [
        "Cantera San Cristóbal",
        "Cantera Bisonó",
        "Cantera Haina",
        "Cantera Baní",
        "Cantera Nizao",
        "Cantera Palenque",
        "Otras Canteras"
    ]
    
    # Encabezados de Catálogos
    ws_cat["A1"] = "PRODUCTOS_AUTORIZADOS"
    ws_cat["B1"] = "PLANTAS_DESTINO"
    ws_cat["C1"] = "MINAS_REFERENCIA"
    
    cat_header_fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
    cat_header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    
    for col_idx in ["A1", "B1", "C1"]:
        ws_cat[col_idx].fill = cat_header_fill
        ws_cat[col_idx].font = cat_header_font
        ws_cat[col_idx].alignment = Alignment(horizontal="center")
        
    for i, p in enumerate(productos, start=2):
        ws_cat[f"A{i}"] = p
    for i, pl in enumerate(plantas, start=2):
        ws_cat[f"B{i}"] = pl
    for i, m in enumerate(minas, start=2):
        ws_cat[f"C{i}"] = m
        
    ws_cat.column_dimensions["A"].width = 28
    ws_cat.column_dimensions["B"].width = 22
    ws_cat.column_dimensions["C"].width = 26
    
    # ──────────────────────────────────────────────────────────────────────────
    # 2. PESTAÑA: PLANTILLA (Oficial en Blanco para Suplidores)
    # ──────────────────────────────────────────────────────────────────────────
    ws = wb.create_sheet(title="PLANTILLA", index=0)
    ws.views.sheetView[0].showGridLines = True
    
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fill_header = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid") # Azul Marino
    
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )
    
    # Fila 1: Encabezados Directos (Fecha, No. conduce, Producto, Mina, Planta, Cantidad, Precio, Total)
    headers = [
        ("Fecha", "A", 15, Alignment(horizontal="center", vertical="center")),
        ("No. conduce", "B", 18, Alignment(horizontal="center", vertical="center")),
        ("Producto", "C", 26, Alignment(horizontal="left", vertical="center")),
        ("Mina", "D", 24, Alignment(horizontal="left", vertical="center")),
        ("Planta", "E", 20, Alignment(horizontal="center", vertical="center")),
        ("Cantidad", "F", 16, Alignment(horizontal="right", vertical="center")),
        ("Precio", "G", 16, Alignment(horizontal="right", vertical="center")),
        ("Total", "H", 18, Alignment(horizontal="right", vertical="center"))
    ]
    
    ws.row_dimensions[1].height = 28
    for texto, col, ancho, align in headers:
        cell = ws[f"{col}1"]
        cell.value = texto
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align
        cell.border = thin_border
        ws.column_dimensions[col].width = ancho
        
    # Filas 2 a 100: Totalmente en blanco con formatos y fórmulas pre-configuradas
    for row_idx in range(2, 101):
        ws.row_dimensions[row_idx].height = 20
        ws[f"A{row_idx}"].number_format = 'yyyy-mm-dd'
        ws[f"A{row_idx}"].alignment = Alignment(horizontal="center")
        
        ws[f"B{row_idx}"].number_format = '@' # Formato texto para conduce
        ws[f"B{row_idx}"].alignment = Alignment(horizontal="center")
        
        ws[f"C{row_idx}"].alignment = Alignment(horizontal="left")
        ws[f"D{row_idx}"].alignment = Alignment(horizontal="left")
        ws[f"E{row_idx}"].alignment = Alignment(horizontal="center")
        
        ws[f"F{row_idx}"].number_format = '#,##0.00' # Cantidad
        ws[f"F{row_idx}"].alignment = Alignment(horizontal="right")
        
        ws[f"G{row_idx}"].number_format = '"RD$"#,##0.00' # Precio
        ws[f"G{row_idx}"].alignment = Alignment(horizontal="right")
        
        ws[f"H{row_idx}"] = f'=IF(OR(ISBLANK(F{row_idx}),ISBLANK(G{row_idx})), "", F{row_idx}*G{row_idx})' # Total automático
        ws[f"H{row_idx}"].number_format = '"RD$"#,##0.00'
        ws[f"H{row_idx}"].alignment = Alignment(horizontal="right")
        
        for col_letter in ["A", "B", "C", "D", "E", "F", "G", "H"]:
            ws[f"{col_letter}{row_idx}"].border = thin_border

    # ──────────────────────────────────────────────────────────────────────────
    # 3. LOOKUPS / DATA VALIDATION (Listas desplegables)
    # ──────────────────────────────────────────────────────────────────────────
    dv_producto = DataValidation(
        type="list",
        formula1="=CATALOGOS!$A$2:$A$13",
        allow_blank=True,
        showDropDown=False
    )
    dv_producto.error = "Debe elegir un producto válido de la lista de catálogos autorizados."
    dv_producto.errorTitle = "Producto no autorizado"
    dv_producto.prompt = "Seleccione el producto entregado en planta."
    dv_producto.promptTitle = "Producto Autorizado"
    ws.add_data_validation(dv_producto)
    dv_producto.add("C2:C100")
    
    dv_planta = DataValidation(
        type="list",
        formula1="=CATALOGOS!$B$2:$B$9",
        allow_blank=True,
        showDropDown=False
    )
    dv_planta.error = "Debe elegir una planta de destino válida."
    dv_planta.errorTitle = "Planta no válida"
    dv_planta.prompt = "Seleccione la planta de descarga."
    dv_planta.promptTitle = "Planta Destino"
    ws.add_data_validation(dv_planta)
    dv_planta.add("E2:E100")
    
    # ──────────────────────────────────────────────────────────────────────────
    # 4. PESTAÑA: INSTRUCCIONES
    # ──────────────────────────────────────────────────────────────────────────
    ws_ins = wb.create_sheet(title="INSTRUCCIONES")
    ws_ins.views.sheetView[0].showGridLines = True
    
    ws_ins["A1"] = "REGLA / CAMPO"
    ws_ins["B1"] = "INSTRUCCIONES PARA EL SUPLIDOR"
    ws_ins["A1"].font = cat_header_font
    ws_ins["A1"].fill = cat_header_fill
    ws_ins["B1"].font = cat_header_font
    ws_ins["B1"].fill = cat_header_fill
    
    instrucciones = [
        ("1. Plantilla en Blanco", "Complete las filas vacías de la hoja 'PLANTILLA' con los datos de sus conduces entregados en planta."),
        ("2. Encabezados", "No modifique ni elimine la fila 1 de encabezados (Fecha, No. conduce, Producto, Mina, Planta, Cantidad, Precio, Total)."),
        ("3. Fecha", "Coloque la fecha de entrega en formato AAAA-MM-DD (ej: 2026-11-04)."),
        ("4. No. conduce", "Digite el número exacto del conduce físico entregado en planta (sin espacios ni caracteres extra)."),
        ("5. Producto", "Seleccione o digite el producto de la lista desplegable autorizada en la pestaña 'CATALOGOS'."),
        ("6. Mina", "Indique la cantera o mina de procedencia del material."),
        ("7. Planta", "Seleccione la planta donde fue descargado el material (ej: Metaldom, Haina, Circunvalacion)."),
        ("8. Cantidad", "Digite los metros cúbicos (M3) o toneladas recibidas según su conduce."),
        ("9. Precio", "Digite el precio unitario pactado sin símbolos de moneda."),
        ("10. Total", "Se calcula automáticamente mediante la fórmula (Cantidad x Precio)."),
        ("11. Conciliación", "El sistema conciliará automáticamente cada conduce contra el registro de báscula/puerta para autorizar el pago.")
    ]
    
    for i, (regla, desc) in enumerate(instrucciones, start=2):
        ws_ins.row_dimensions[i].height = 24
        ws_ins[f"A{i}"] = regla
        ws_ins[f"A{i}"].font = Font(bold=True)
        ws_ins[f"A{i}"].border = thin_border
        ws_ins[f"B{i}"] = desc
        ws_ins[f"B{i}"].border = thin_border
        
    ws_ins.column_dimensions["A"].width = 26
    ws_ins.column_dimensions["B"].width = 95
    
    # ──────────────────────────────────────────────────────────────────────────
    # 5. PESTAÑA: EJEMPLO_LLENADO (Para referencia visual del suplidor)
    # ──────────────────────────────────────────────────────────────────────────
    ws_ej = wb.create_sheet(title="EJEMPLO_LLENADO")
    ws_ej.views.sheetView[0].showGridLines = True
    
    for texto, col, ancho, align in headers:
        cell = ws_ej[f"{col}1"]
        cell.value = texto
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align
        cell.border = thin_border
        ws_ej.column_dimensions[col].width = ancho
        
    ejemplos_referencia = [
        ("2026-11-04", "672867", "GRAVA DE 3/4\"", "Cantera San Cristóbal", "Metaldom", 26.46, 850.00, 22491.00),
        ("2026-11-04", "672812", "ARENA GRIS", "Cantera San Cristóbal", "Metaldom", 26.61, 700.00, 18627.00)
    ]
    
    font_ejemplo = Font(name="Calibri", size=10, color="000000")
    fill_ejemplo = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    
    for r_idx, ej in enumerate(ejemplos_referencia, start=2):
        ws_ej.row_dimensions[r_idx].height = 22
        ws_ej[f"A{r_idx}"] = ej[0]
        ws_ej[f"A{r_idx}"].alignment = Alignment(horizontal="center")
        ws_ej[f"B{r_idx}"] = ej[1]
        ws_ej[f"B{r_idx}"].alignment = Alignment(horizontal="center")
        ws_ej[f"B{r_idx}"].number_format = '@'
        ws_ej[f"C{r_idx}"] = ej[2]
        ws_ej[f"D{r_idx}"] = ej[3]
        ws_ej[f"E{r_idx}"] = ej[4]
        ws_ej[f"E{r_idx}"].alignment = Alignment(horizontal="center")
        ws_ej[f"F{r_idx}"] = ej[5]
        ws_ej[f"F{r_idx}"].number_format = '#,##0.00'
        ws_ej[f"F{r_idx}"].alignment = Alignment(horizontal="right")
        ws_ej[f"G{r_idx}"] = ej[6]
        ws_ej[f"G{r_idx}"].number_format = '"RD$"#,##0.00'
        ws_ej[f"G{r_idx}"].alignment = Alignment(horizontal="right")
        ws_ej[f"H{r_idx}"] = ej[7]
        ws_ej[f"H{r_idx}"].number_format = '"RD$"#,##0.00'
        ws_ej[f"H{r_idx}"].alignment = Alignment(horizontal="right")
        for col_l in ["A", "B", "C", "D", "E", "F", "G", "H"]:
            ws_ej[f"{col_l}{r_idx}"].font = font_ejemplo
            ws_ej[f"{col_l}{r_idx}"].fill = fill_ejemplo
            ws_ej[f"{col_l}{r_idx}"].border = thin_border

    return wb

def crear_archivo_prueba():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PLANTILLA"
    ws.views.sheetView[0].showGridLines = True
    
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fill_header = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )
    
    headers = [
        ("Fecha", "A", 15, Alignment(horizontal="center", vertical="center")),
        ("No. conduce", "B", 18, Alignment(horizontal="center", vertical="center")),
        ("Producto", "C", 26, Alignment(horizontal="left", vertical="center")),
        ("Mina", "D", 24, Alignment(horizontal="left", vertical="center")),
        ("Planta", "E", 20, Alignment(horizontal="center", vertical="center")),
        ("Cantidad", "F", 16, Alignment(horizontal="right", vertical="center")),
        ("Precio", "G", 16, Alignment(horizontal="right", vertical="center")),
        ("Total", "H", 18, Alignment(horizontal="right", vertical="center"))
    ]
    
    ws.row_dimensions[1].height = 28
    for texto, col, ancho, align in headers:
        cell = ws[f"{col}1"]
        cell.value = texto
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align
        cell.border = thin_border
        ws.column_dimensions[col].width = ancho
        
    # Datos de los dos conduces reales de A. ALBA SANCHEZ Y ASOC. existentes en CBSVMO
    conduces_reales = [
        ("2026-11-04", "672867", "GRAVA DE 3/4\"", "Cantera San Cristóbal", "Metaldom", 26.46, 850.00, 22491.00),
        ("2026-11-04", "672812", "ARENA GRIS", "Cantera San Cristóbal", "Metaldom", 26.61, 700.00, 18627.00)
    ]
    
    for r_idx, d in enumerate(conduces_reales, start=2):
        ws.row_dimensions[r_idx].height = 22
        ws[f"A{r_idx}"] = d[0]
        ws[f"A{r_idx}"].alignment = Alignment(horizontal="center")
        ws[f"B{r_idx}"] = d[1]
        ws[f"B{r_idx}"].alignment = Alignment(horizontal="center")
        ws[f"B{r_idx}"].number_format = '@'
        ws[f"C{r_idx}"] = d[2]
        ws[f"D{r_idx}"] = d[3]
        ws[f"E{r_idx}"] = d[4]
        ws[f"E{r_idx}"].alignment = Alignment(horizontal="center")
        ws[f"F{r_idx}"] = d[5]
        ws[f"F{r_idx}"].number_format = '#,##0.00'
        ws[f"F{r_idx}"].alignment = Alignment(horizontal="right")
        ws[f"G{r_idx}"] = d[6]
        ws[f"G{r_idx}"].number_format = '"RD$"#,##0.00'
        ws[f"G{r_idx}"].alignment = Alignment(horizontal="right")
        ws[f"H{r_idx}"] = d[7]
        ws[f"H{r_idx}"].number_format = '"RD$"#,##0.00'
        ws[f"H{r_idx}"].alignment = Alignment(horizontal="right")
        for col_l in ["A", "B", "C", "D", "E", "F", "G", "H"]:
            ws[f"{col_l}{r_idx}"].border = thin_border
            
    return wb

if __name__ == "__main__":
    downloads_path = os.path.expanduser(r"~\Downloads")
    
    # 1. Generar Plantilla Oficial en Blanco para Suplidores
    wb_blanca = crear_plantilla_blanca()
    ruta_plantilla_downloads = os.path.join(downloads_path, "PLANTILLA_CONDUCES_SUPLIDOR.xlsx")
    wb_blanca.save(ruta_plantilla_downloads)
    print(f"[OK] Plantilla en blanco guardada en: {ruta_plantilla_downloads}")
    
    # Guardar copia en ControlPuerta
    ruta_plantilla_local = r"ControlPuerta\PLANTILLA_CONDUCES_SUPLIDOR.xlsx"
    wb_blanca.save(ruta_plantilla_local)
    print(f"[OK] Plantilla en blanco guardada en: {ruta_plantilla_local}")
    
    # 2. Generar Archivo de Prueba con los 2 conduces reales de Alba Sanchez
    wb_prueba = crear_archivo_prueba()
    ruta_prueba_downloads = os.path.join(downloads_path, "PRUEBA_CONDUCES_ALBA_SANCHEZ.xlsx")
    wb_prueba.save(ruta_prueba_downloads)
    print(f"[OK] Archivo de prueba con conduces reales guardado en: {ruta_prueba_downloads}")
    
    ruta_prueba_local = r"ControlPuerta\PRUEBA_CONDUCES_ALBA_SANCHEZ.xlsx"
    wb_prueba.save(ruta_prueba_local)
    print(f"[OK] Archivo de prueba guardado en: {ruta_prueba_local}")
