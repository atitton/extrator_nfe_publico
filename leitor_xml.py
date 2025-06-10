import xml.etree.ElementTree as ET

def parse_nfe(xml_file):
    xml_file.seek(0)
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Namespace direto (sem prefixo nfe:)
    ns = {"ns": "http://www.portalfiscal.inf.br/nfe"}

    # Pega o nó infNFe corretamente
    infNFe = root.find(".//ns:infNFe", ns)
    if infNFe is None:
        return []

    # Extrai emitente
    emit = infNFe.find("ns:emit", ns)
    emitente = emit.find("ns:xNome", ns).text.strip() if emit is not None else "Desconhecida"
    cnpj = emit.find("ns:CNPJ", ns).text.strip() if emit is not None else ""

    # Data de emissão
    data_emissao = infNFe.findtext("ns:ide/ns:dhEmi", default="", namespaces=ns)

    produtos = []
    for det in infNFe.findall("ns:det", ns):
        nome = det.findtext("ns:prod/ns:xProd", default="", namespaces=ns)
        qtd_str = det.findtext("ns:prod/ns:qCom", default="0", namespaces=ns)
        valor_unit_str = det.findtext("ns:prod/ns:vUnCom", default="0", namespaces=ns)
        valor_total_str = det.findtext("ns:prod/ns:vProd", default="0", namespaces=ns)

        try:
            qtd = float(qtd_str.replace(",", "."))
            valor_unit = float(valor_unit_str.replace(",", "."))
            valor_total = float(valor_total_str.replace(",", "."))
        except Exception as e:
            print(f"[ERRO] Produto '{nome}' inválido: {e}")
            continue

        produtos.append({
            "Produto": nome,
            "Quantidade": qtd,
            "Valor Unitário": valor_unit,
            "Valor Total": valor_total,
            "CNPJ": cnpj,
            "Empresa": emitente,
            "Data": data_emissao,
            "Origem": "XML"
        })

    return produtos

