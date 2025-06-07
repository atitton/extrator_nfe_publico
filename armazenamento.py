# arquivo: armazenamento.py
import os
from datetime import datetime
import pandas as pd  # importante manter isso aqui

def salvar_arquivo_em_nuvem(arquivo, nome_arquivo, cnpj, data_str):
    try:
        data = pd.to_datetime(data_str)
    except:
        data = datetime.today()

    ano = str(data.year)
    mes = str(data.month).zfill(2)
    caminho = os.path.join("documentos_armazenados", cnpj, ano, mes)
    os.makedirs(caminho, exist_ok=True)

    caminho_arquivo = os.path.join(caminho, nome_arquivo)
    with open(caminho_arquivo, "wb") as f:
        f.write(arquivo.read())

    return caminho_arquivo

def verificar_arquivo_existente(nome_arquivo, cnpj):
    import os
    base_path = os.path.join("documentos_armazenados", cnpj)
    for root, _, files in os.walk(base_path):
        if nome_arquivo in files:
            return True
    return False
