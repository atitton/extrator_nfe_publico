import fitz  # PyMuPDF
from PIL import Image
import pytesseract
# Removed redundant import of re
from pdf2image import convert_from_path
from datetime import datetime
import tempfile
import re
import os


# Caminho do Tesseract no Windows (ajuste se necessário)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
POPPLER_PATH = r'C:\Program Files (x86)\Poppler\poppler\Library\bin'

# -------- Leitura de PDF (com fallback para OCR) --------
def extrair_texto_pdf(caminho_pdf):
    caminho_pdf.seek(0)  # 🧠 ESSENCIAL
    doc = fitz.open(stream=caminho_pdf.read(), filetype="pdf")

    texto = ""
    for pagina in doc:
        texto += pagina.get_text()
    doc.close()

    if len(texto.strip()) < 50:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(caminho_pdf.read())
            tmp_path = tmp_file.name

        imagens = convert_from_path(tmp_path, poppler_path=POPPLER_PATH)
        texto = ""
        for img in imagens:
            texto += pytesseract.image_to_string(img, lang='por')
    return texto

# -------- Leitura de Imagem com OCR --------
def extrair_texto_imagem(caminho_imagem):
    imagem = Image.open(caminho_imagem)
    texto = pytesseract.image_to_string(imagem, lang='por')
    return texto

# -------- Extração de Produtos --------
def extrair_produtos_pdf_livre(texto):
    import re

    linhas = texto.split('\n')
    produtos = []
    capturar = False

    for idx in range(len(linhas)):
        linha = linhas[idx].strip()

        # Começar a capturar depois do título correto
        if "DESCRIÇÃO DO PRODUTO" in linha.upper():
            capturar = True
            continue

        if not capturar:
            continue

        try:
            if linha.upper() in ["UN", "KG", "CX", "LT"]:
                qtd = float(linhas[idx + 1].replace(",", ".").strip())
                v_unit = float(linhas[idx + 2].replace(",", ".").strip())
                v_total = float(linhas[idx + 3].replace(",", ".").strip())

                # Busca a primeira linha textual real como descrição
                descricao = ""
                for offset in range(4, 10):
                    if idx + offset < len(linhas):
                        linha_potencial = linhas[idx + offset].strip()
                        if re.search(r"[a-zA-Záéíóúçãõâêô]", linha_potencial):
                            descricao = linha_potencial
                            break

                if descricao:
                    produtos.append({
                        "Produto": descricao,
                        "Quantidade": qtd,
                        "Valor Unitário": v_unit,
                        "Valor Total": v_total
                    })
        except:
            continue

    return produtos







    return produtos

# -------- Extração de Empresa, CNPJ e Data --------
def extrair_dados_cabecalho(texto):
    empresa = ""
    cnpj = ""
    data = ""

    # Empresa
    match_emp = re.search(r'(?i)([A-Z0-9\s\.\-\&]{5,}(LTDA|EIRELI|ME|M[EÉ]))', texto)

    if match_emp:
        empresa = match_emp.group(1).strip()

    # CNPJ
    match_cnpj = re.search(r'\d{2}[.,]?\d{3}[.,]?\d{3}[\/]?\d{4}-?\d{2}', texto)
    if match_cnpj:
        cnpj = re.sub(r'\D', '', match_cnpj.group(0))

    # Data (transforma para tipo datetime.date)
    match_data = re.search(r'\d{2}/\d{2}/\d{4}', texto)
    if match_data:
        try:
            data = datetime.strptime(match_data.group(0), "%d/%m/%Y").date()
        except:
            data = ""

    return empresa, cnpj, data
