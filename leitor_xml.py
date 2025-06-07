import xml.etree.ElementTree as ET

def parse_nfe(xml_file):
    xml_file.seek(0)
    tree = ET.parse(xml_file)

    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}  # ✅ Definido ANTES de usar

    root = tree.getroot().find(".//nfe:NFe", ns)

    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

    emitente = root.find(".//nfe:emit/nfe:xNome", ns)
    emitente = emitente.text if emitente is not None else ""

    cnpj = root.findtext(".//nfe:emit/nfe:CNPJ", default="", namespaces=ns)
    data_emissao = root.findtext(".//nfe:ide/nfe:dhEmi", default="", namespaces=ns)

    produtos = []
    for det in root.findall(".//nfe:det", ns):
        nome = det.findtext("nfe:prod/nfe:xProd", default="", namespaces=ns)
        try:
            qtd = float(det.findtext("nfe:prod/nfe:qCom", default="0", namespaces=ns).replace(",", "."))
            valor_unit = float(det.findtext("nfe:prod/nfe:vUnCom", default="0", namespaces=ns).replace(",", "."))
            valor_total = float(det.findtext("nfe:prod/nfe:vProd", default="0", namespaces=ns).replace(",", "."))
        except:
            continue

        if nome:
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