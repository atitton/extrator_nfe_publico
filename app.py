from io import BytesIO
import streamlit as st
import pandas as pd
import datetime
import os
import json
import sqlite3
import hashlib
from dotenv import load_dotenv
import plotly.express as px
import calplot
import fitz
import plotly.graph_objects as go

from armazenamento import verificar_arquivo_existente, salvar_arquivo_em_nuvem
from leitor_xml import parse_nfe
from leitor_pdf_imagem import (
    extrair_texto_pdf,
    extrair_texto_imagem,
    extrair_produtos_pdf_livre,
    extrair_dados_cabecalho
)
from db import criar_tabela, inserir_produto, buscar_todos, resetar_banco

# Streamlit setup
st.set_page_config(page_title="Extrator de Documentos", layout="wide")
SESSION_FILE = "sessao.json"

# Inicialização do banco de dados de usuários
def init_usuarios():
    conn = sqlite3.connect("banco.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            usuario TEXT PRIMARY KEY,
            senha_hash TEXT,
            cnpj TEXT
        )
    """)
    conn.commit()
    conn.close()

def cadastrar_usuario(usuario, senha, cnpj):
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    conn = sqlite3.connect("banco.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO usuarios (usuario, senha_hash, cnpj) VALUES (?, ?, ?)", (usuario, senha_hash, cnpj))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def autenticar_usuario(usuario, senha):
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    conn = sqlite3.connect("banco.db")
    c = conn.cursor()
    c.execute("SELECT cnpj FROM usuarios WHERE usuario=? AND senha_hash=?", (usuario, senha_hash))
    resultado = c.fetchone()
    conn.close()
    return resultado[0] if resultado else None

def salvar_sessao(usuario, cnpj):
    with open(SESSION_FILE, "w") as f:
        json.dump({"usuario": usuario, "cnpj": cnpj}, f)

def carregar_sessao():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            return json.load(f)
    return None

def limpar_sessao():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)

# Função gerar Excel
def gerar_excel(df):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Histórico')
    buffer.seek(0)
    return buffer

# Função segura para formatar valores numéricos
def formatar_valor(val):
    try:
        return f"{float(val):.2f}"
    except:
        return val

# Função para gerar relatório PDF
def gerar_pdf_relatorio(df, usuario=None, cnpj=None, mostrar_usuario=False, mostrar_cnpj=False):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elementos = []

    styles = getSampleStyleSheet()
    estilo_titulo = styles['Heading1']
    estilo_subtitulo = styles['Heading3']
    estilo_normal = styles['Normal']

    # Logo
    logo_path = os.path.join("logos", cnpj, "logo.png") if cnpj else None
    if logo_path and os.path.exists(logo_path):
        elementos.append(Image(logo_path, width=120, height=50))
        elementos.append(Spacer(1, 12))

    # Título e cabeçalho
    elementos.append(Paragraph("Relatório de Produtos Extraídos", estilo_titulo))
    elementos.append(Spacer(1, 12))
    elementos.append(Paragraph(f"Data do relatório: {datetime.date.today().strftime('%d/%m/%Y')}", estilo_subtitulo))

    if mostrar_usuario and usuario:
        elementos.append(Paragraph(f"Usuário: {usuario}", estilo_normal))
    if mostrar_cnpj and cnpj:
        elementos.append(Paragraph(f"CNPJ: {cnpj}", estilo_normal))

    elementos.append(Spacer(1, 12))

    # Total filtrado
    try:
        df["Valor Total"] = pd.to_numeric(df["Valor Total"], errors="coerce")
        df["Valor Unitário"] = pd.to_numeric(df["Valor Unitário"], errors="coerce")
        total = df["Valor Total"].sum()
        elementos.append(Paragraph(f"💰 Total filtrado: R$ {total:,.2f}", estilo_subtitulo))
    except:
        pass

    elementos.append(Spacer(1, 12))

    # Formatação numérica com 2 casas
    df["Valor Total"] = df["Valor Total"].map(formatar_valor)
    df["Valor Unitário"] = df["Valor Unitário"].map(formatar_valor)

    # Define colunas e estilo para Produto
    colunas_exibir = ["Produto", "Quantidade", "Valor Unitário", "Valor Total", "Origem"]
    estilo_produto = ParagraphStyle(name="Produto", fontSize=10, leading=12)

    dados_tabela_formatada = [colunas_exibir]
    for linha in df[colunas_exibir].astype(str).values.tolist():
        linha[0] = Paragraph(linha[0], estilo_produto)
        dados_tabela_formatada.append(linha)

    # Define larguras das colunas
    col_widths = [200, 60, 70, 70, 60]
    tabela = Table(dados_tabela_formatada, colWidths=col_widths, repeatRows=1)

    # Estilo visual
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    elementos.append(tabela)
    doc.build(elementos)
    buffer.seek(0)
    return buffer

# Inicialização de sessão
init_usuarios()
if "usuario" not in st.session_state:
    sessao = carregar_sessao()
    if sessao:
        st.session_state.usuario = sessao["usuario"]
        st.session_state.cnpj = sessao["cnpj"]

if "usuario" not in st.session_state:
    st.sidebar.markdown("## 🔐 Login de Cliente")
    opcao = st.sidebar.radio("Escolha:", ["Entrar", "Cadastrar"])
    usuario = st.sidebar.text_input("Usuário")
    senha = st.sidebar.text_input("Senha", type="password")

    if opcao == "Cadastrar":
        cnpj = st.sidebar.text_input("CNPJ")
        if st.sidebar.button("Cadastrar"):
            if cadastrar_usuario(usuario, senha, cnpj):
                st.sidebar.success("Usuário cadastrado. Agora entre.")
            else:
                st.sidebar.error("Usuário já existe.")

    elif opcao == "Entrar":
        if st.sidebar.button("Entrar"):
            cnpj = autenticar_usuario(usuario, senha)
            if cnpj:
                st.session_state.usuario = usuario
                st.session_state.cnpj = cnpj
                salvar_sessao(usuario, cnpj)
                st.rerun()
            else:
                st.sidebar.error("Usuário ou senha incorretos.")

if "usuario" in st.session_state:
    if st.sidebar.button("🚪 Sair"):
        limpar_sessao()
        del st.session_state.usuario
        del st.session_state.cnpj
        st.rerun()

if "usuario" not in st.session_state:
    st.stop()

# APP principal
load_dotenv()
criar_tabela()
if "arquivos_processados" not in st.session_state:
    st.session_state.arquivos_processados = False




if st.query_params.get("uploaded") == "ok":
    del st.query_params["uploaded"]
    st.rerun()


st.markdown("### 👋 Bem-vindo!")
st.markdown("Envie notas fiscais e acompanhe seus gastos organizados.")

arquivos = []

# Upload múltiplo e simplificado
with st.sidebar:
    st.markdown("## ☁️ Armazenar Documentos")
    st.markdown("Envie aqui qualquer documento XML, PDF ou imagem.")
    arquivos = st.file_uploader("📎 Selecione os arquivos", type=["xml", "pdf"], accept_multiple_files=True, key="multiupload")
    if arquivos:
        st.markdown("### 📄 Arquivos selecionados:")
        for arq in arquivos:
            nome = arq.name
            if verificar_arquivo_existente(nome, st.session_state.cnpj):
                st.markdown(f"- {nome} ✅ *Já enviado*")
            else:
                st.markdown(f"- {nome} 🆕 *Novo*")

    if arquivos:
        st.session_state.arquivos_processados = False

with st.sidebar.expander("⚙️ Configurações de Conta", expanded=False):
    st.markdown("### 📷 Logo personalizado para relatórios")
    logo_path = os.path.join("logos", st.session_state.cnpj)
    os.makedirs(logo_path, exist_ok=True)
    caminho_logo = os.path.join(logo_path, "logo.png")

    logo_file = st.file_uploader("Upload do logo (PNG)", type=["png"], key="logo_upload")
    
    if logo_file is not None:
        with open(caminho_logo, "wb") as f:
            f.write(logo_file.read())
        st.success("✅ Logo salvo com sucesso!")

    if os.path.exists(caminho_logo):
        st.image(caminho_logo, width=150, caption="Logo atual")


# Bloco de processamento de arquivos com PDF ajustado
if arquivos and not st.session_state.get("arquivos_processados", False):
    with st.spinner("⏳ Processando arquivos..."):
        total = len(arquivos)
        progress_bar = st.progress(0, text="🔄 Iniciando...")

        for i, arq in enumerate(arquivos):
            progresso = int((i + 1) / total * 100)
            progress_bar.progress(progresso, text=f"📄 Processando {i+1}/{total}: {arq.name}")

            nome_arquivo = arq.name
            cnpj = st.session_state.cnpj

            salvar_arquivo_em_nuvem(
                arquivo=arq,
                nome_arquivo=arq.name,
                cnpj=cnpj,
                data_str=datetime.date.today()
            )

            if arq.name.lower().endswith(".xml"):
                try:
                    arq.seek(0)
                    produtos = parse_nfe(arq)
                    for p in produtos:
                        inserir_produto(p)
                except Exception as e:
                    st.error(f"❌ Erro ao processar XML {arq.name}: {e}")

            elif arq.name.lower().endswith(".pdf"):
                try:
                    texto = extrair_texto_pdf(arq)
                    produtos = extrair_produtos_pdf_livre(texto)
                    empresa, cnpj_lido, data = extrair_dados_cabecalho(texto)

                    if not isinstance(data, datetime.date):
                        data = datetime.date.today()
                    data_str = data.strftime("%Y-%m-%d")

                    for p in produtos:
                        p.update({
                            "Empresa": empresa or "Desconhecida",
                            "CNPJ": cnpj_lido or "00000000000000",
                            "Data": data_str,
                            "Origem": "PDF"

                        })
                        inserir_produto(p)
                except Exception as e:
                    st.error(f"Erro ao processar PDF {arq.name}: {e}")


    st.success(f"✅ {len(arquivos)} df_filtradoquivo(s) armazenado(s) com sucesso!")
    if st.button("Voltar"):
        st.query_params.clear()
        st.rerun()
    
               
        
aba_historico, aba_envio = st.tabs(["📊 Histórico de Produtos", "📤 Meus Arquivos"])

with st.expander("🧹 Excluir por período", expanded=False):
    data_ini = st.date_input("📆 De:", value=datetime.date.today() - datetime.timedelta(days=30), key="excl_ini")
    data_fim = st.date_input("📆 Até:", value=datetime.date.today(), key="excl_fim")

    if st.button("🗑️ Excluir arquivos neste período", key="pedir_confirmacao_periodo"):
        st.session_state["confirmar_exclusao_periodo"] = True

    if st.session_state.get("confirmar_exclusao_periodo", False):
        st.warning(f"⚠️ Tem certeza que deseja excluir arquivos entre {data_ini} e {data_fim}?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Sim, excluir agora", key="confirma_excluir_periodo"):
                base_path = os.path.join("documentos_armazenados", st.session_state.cnpj)
                excluidos = 0
                if os.path.exists(base_path):
                    for ano in os.listdir(base_path):
                        pasta_ano = os.path.join(base_path, ano)
                        for mes in os.listdir(pasta_ano):
                            pasta_mes = os.path.join(pasta_ano, mes)
                            for nome_arquivo in os.listdir(pasta_mes):
                                caminho = os.path.join(pasta_mes, nome_arquivo)
                                data_arquivo = datetime.datetime.fromtimestamp(os.path.getmtime(caminho)).date()
                                if data_ini <= data_arquivo <= data_fim:
                                    os.remove(caminho)
                                    excluidos += 1
                    st.success(f"✅ {excluidos} arquivo(s) excluído(s) entre {data_ini} e {data_fim}")
                    st.session_state.pop("confirmar_exclusao_periodo")
                    st.rerun()
                else:
                    st.warning("Nenhum arquivo encontrado.")
        with col2:
            if st.button("❌ Cancelar exclusão", key="cancela_excluir_periodo"):
                st.session_state.pop("confirmar_exclusao_periodo")


with aba_envio:
    st.markdown("## 📁 Meus Arquivos Enviados")
    cnpj = st.session_state.cnpj
    pasta_base = os.path.join("documentos_armazenados", cnpj)

    if os.path.exists(pasta_base):
        for ano in sorted(os.listdir(pasta_base)):
            st.markdown(f"### 📅 Ano {ano}")
            pasta_ano = os.path.join(pasta_base, ano)
            for mes in sorted(os.listdir(pasta_ano)):
                col_mes, col_botao_mes = st.columns([6, 1])
                with col_mes:
                    st.markdown(f"#### 🗓️ Mês {mes}")
                chave_conf = f"confirmar_mes_{ano}_{mes}"
                if st.button("🗑️ Excluir mês", key=f"excluir_mes_{ano}_{mes}"):
                    st.session_state[chave_conf] = True

                if st.session_state.get(chave_conf, False):
                    st.warning(f"⚠️ Tem certeza que deseja excluir TODOS os arquivos do mês {mes}/{ano}?")
                    col_ok, col_cancel = st.columns(2)
                    with col_ok:
                        if st.button("✅ Sim, excluir", key=f"sim_{ano}_{mes}"):
                            import shutil
                            shutil.rmtree(os.path.join(pasta_ano, mes))
                            st.success(f"Mês {mes}/{ano} excluído com sucesso.")
                            st.session_state.pop(chave_conf)
                            st.rerun()
                    with col_cancel:
                        if st.button("❌ Cancelar", key=f"cancela_{ano}_{mes}"):
                            st.session_state.pop(chave_conf)


                pasta_mes = os.path.join(pasta_ano, mes)
                arquivos = os.listdir(pasta_mes)
                for arquivo in arquivos:
                    caminho_arquivo = os.path.join(pasta_mes, arquivo)
                    col1, col2 = st.columns([6, 1])
                    with col1:
                        with open(caminho_arquivo, "rb") as f:
                            st.download_button(
                                label=f"📄 {arquivo}",
                                data=f.read(),
                                file_name=arquivo,
                                mime="application/octet-stream"
                            )
                    with col2:
                        if st.button("🗑️", key=f"del_{ano}_{mes}_{arquivo}"):
                            os.remove(caminho_arquivo)
                            st.success(f"Arquivo {arquivo} excluído com sucesso.")
                            st.rerun()
    else:
        st.info("Nenhum arquivo enviado ainda.")



with aba_historico:
    with st.expander("📂 Histórico de produtos extraídos", expanded=True):
        registros = buscar_todos(st.session_state.cnpj)

        if registros:
            df_hist = pd.DataFrame(registros, columns=[
                "Empresa", "CNPJ", "Produto", "Quantidade", "Valor Unitário", "Valor Total", "Origem", "Data"
            ])

            colf1, colf2 = st.columns(2)
            with colf1:
                data_ini = st.date_input("📆 De:", value=datetime.date.today() - datetime.timedelta(days=30), key="filtro_de")
            with colf2:
                data_fim = st.date_input("📆 Até:", value=datetime.date.today(), key="filtro_ate")

            df_hist["Data"] = pd.to_datetime(df_hist["Data"].str[:10], errors="coerce").dt.tz_localize(None)

            df_filtrado = df_hist[
                df_hist["Data"].notna() &
                (df_hist["Data"] >= pd.to_datetime(data_ini)) &
                (df_hist["Data"] <= pd.to_datetime(data_fim))
            ]

            if not df_filtrado.empty:
                # Conversão para cálculo (mantém como float)
                df_filtrado["Valor Total"] = pd.to_numeric(df_filtrado["Valor Total"], errors="coerce").fillna(0)
                df_filtrado["Valor Unitário"] = pd.to_numeric(df_filtrado["Valor Unitário"], errors="coerce").fillna(0)

                # Calcula total antes de formatar
                total_filtrado = df_filtrado["Valor Total"].sum()

                # Filtros por empresa e produto
                filtros_empresas = st.multiselect(
                    "🏢 Filtrar por empresas",
                    options=sorted(df_filtrado["Empresa"].dropna().unique()),
                    default=[]
                )

                filtros_produtos = st.multiselect(
                    "📦 Filtrar por produtos",
                    options=sorted(df_filtrado["Produto"].dropna().unique()),
                    default=[]
                )

                if filtros_empresas:
                    df_filtrado = df_filtrado[df_filtrado["Empresa"].isin(filtros_empresas)]

                if filtros_produtos:
                    df_filtrado = df_filtrado[df_filtrado["Produto"].isin(filtros_produtos)]

                if st.button("🔄 Limpar filtros"):
                    st.experimental_rerun()

                # Recalcula total após filtro
                total_filtrado = df_filtrado["Valor Total"].sum()

                # Métricas
                col1, col2, col3 = st.columns(3)
                col1.metric("📦 Total de Produtos", f"{len(df_filtrado):,}")
                col2.metric("💰 Valor Total", f"R$ {total_filtrado:,.2f}")
                try:
                    top_empresa = df_filtrado.groupby("Empresa")["Valor Total"].sum().idxmax()
                    col3.metric("🏆 Fornecedor Destaque", top_empresa)
                except:
                    col3.metric("🏆 Fornecedor Destaque", "N/A")

                # 🔒 Checkboxes PDF
                mostrar_usuario = st.checkbox("Incluir nome de usuário no PDF", value=False, key="chk_usuario_pdf")
                mostrar_cnpj = st.checkbox("Incluir CNPJ no PDF", value=False, key="chk_cnpj_pdf")


                # Gera arquivos exportáveis
                excel_buffer = gerar_excel(df_filtrado)

                st.download_button(
                    "📥 Baixar tabela como Excel",
                    data=excel_buffer,
                    file_name="historico_produtos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                pdf_buffer = gerar_pdf_relatorio(
                    df_filtrado,
                    usuario=st.session_state.usuario,
                    cnpj=st.session_state.cnpj,
                    mostrar_usuario=mostrar_usuario,
                    mostrar_cnpj=mostrar_cnpj
                )

                st.download_button(
                    "📄 Baixar relatório em PDF",
                    data=pdf_buffer,
                    file_name="relatorio_produtos.pdf",
                    mime="application/pdf"
                )

                # Agora sim: formatar para exibição (SEM quebrar nada)
                df_filtrado["Valor Total"] = df_filtrado["Valor Total"].map(formatar_valor)

                df_filtrado["Valor Unitário"] = df_filtrado["Valor Unitário"].map(formatar_valor)



                st.markdown("### 📋 Produtos encontrados")
                if 'df_filtrado' in locals() and not df_filtrado.empty:
                    st.dataframe(df_filtrado, use_container_width=True, height=300)
                else:
                    st.info("📭 Nenhum dado para exibir na tabela.")

                # 📊 Gasto por empresa (gráfico de barras)
                with st.container():
                    col1, col2 = st.columns(2)

                    with col1:
                        df_filtrado["Valor Total"] = pd.to_numeric(df_filtrado["Valor Total"], errors="coerce")
                        df_soma = df_filtrado.groupby("Empresa")["Valor Total"].sum().reset_index()
                        df_soma = df_soma.sort_values("Valor Total", ascending=True)
                        fig1 = px.bar(
                            df_soma,
                            x="Valor Total",
                            y="Empresa",
                            orientation="h",
                            title="💼 Gasto por empresa",
                            height=300 + len(df_soma) * 10,
                            template="plotly_white"
                        )
                        st.plotly_chart(fig1, use_container_width=True, key="grafico_gasto_empresa")


                    with col2:
                        df_origem = df_filtrado["Origem"].value_counts().reset_index()
                        df_origem.columns = ["Origem", "Total"]

                        if len(df_origem) > 1:
                            fig2 = px.pie(
                                df_origem,
                                values="Total",
                                names="Origem",
                                hole=0.4,
                                title="📦 Origem dos produtos",
                                template="plotly_white"
                            )
                            st.plotly_chart(fig2, use_container_width=True, key="grafico_origem_produtos")

                        else:
                            st.info(f"Todos os produtos vieram da origem: {df_origem.iloc[0]['Origem']}")

                # 📈 Evolução dos gastos
                df_filtrado["Valor Total"] = pd.to_numeric(df_filtrado["Valor Total"], errors="coerce")
                df_por_dia = df_filtrado.groupby("Data")["Valor Total"].sum().reset_index()
                fig_linha = go.Figure()
                fig_linha.add_trace(go.Scatter(
                    x=df_por_dia["Data"],
                    y=df_por_dia["Valor Total"],
                    mode="lines+markers",
                    line=dict(color="royalblue", width=2),
                    marker=dict(size=6),
                    hovertemplate='R$ %{y:.2f}<br>%{x|%d %b %Y}<extra></extra>',
                    name=""
                ))
                fig_linha.update_layout(
                    title="📈 Evolução dos gastos",
                    xaxis_title="Data",
                    yaxis_title="Valor Total (R$)",
                    template="plotly_white",
                    height=400,
                    showlegend=False
                )
                st.plotly_chart(fig_linha, use_container_width=True, key="grafico_evolucao_gastos")


                # 🗓️ Mapa de calor
                st.markdown("### 🗓️ Mapa de calor por dia")
                serie = df_filtrado.groupby("Data")["Valor Total"].sum()
                if not serie.empty:
                    serie.index = pd.to_datetime(serie.index)
                    serie = pd.to_numeric(serie, errors="coerce").fillna(0)
                    fig_cal, _ = calplot.calplot(
                        serie,
                        cmap="Blues",
                        suptitle="🗓️ Mapa de calor de gastos por dia",
                        colorbar=True
                    )
                    st.pyplot(fig_cal)
                else:
                    st.warning("⚠️ Não há dados suficientes para gerar o mapa de calor.")
            else:
                st.info("📭 Nenhum produto encontrado nesse período.")
        else:
            st.info("📭 Nenhum dado armazenado no banco ainda.")


        

        def limpar_coluna_valores(coluna):
            return (
                coluna.astype(str)
                .str.replace(",", ".", regex=False)
                .str.replace("R\\$", "", regex=True)
                .str.extract(r'(\d+\.?\d*)')[0]
                .astype(float)
            )



    if st.session_state.usuario == "admin":
        with st.expander("🔒 Acesso administrativo", expanded=False):
            st.warning("⚠️ Esta ação apagará TODOS os dados do banco. Operação irreversível.")
            senha_digitada = st.text_input("Digite a senha de administrador para continuar", type="password")
            senha_correta = os.getenv("SENHA_ADMIN")
            if senha_digitada:
                if senha_digitada == senha_correta:
                    if st.button("🧹 Apagar histórico de produtos e arquivos"):
                        resetar_banco()

                        # 🗑️ Deleta os arquivos da pasta do usuário logado
                        pasta_base = os.path.join("documentos_armazenados", st.session_state.cnpj)
                        if os.path.exists(pasta_base):
                            import shutil
                            shutil.rmtree(pasta_base)

                        st.success("✅ Histórico e arquivos apagados com sucesso.")
                        st.rerun()

                else:
                    st.error("❌ Senha incorreta.")
