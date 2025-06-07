import sqlite3

def conectar():
    return sqlite3.connect("banco.db")

def criar_tabela():
    conn = sqlite3.connect("banco.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            Empresa TEXT,
            CNPJ TEXT,
            Produto TEXT,
            Quantidade REAL,
            Valor_Unitário TEXT,
            Valor_Total TEXT,
            Origem TEXT,
            Data TEXT,
            PRIMARY KEY (Empresa, Produto, Data, CNPJ)
        )
    """)
    conn.commit()
    conn.close()

def inserir_produto(dados):
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO produtos (Empresa, CNPJ, Produto, Quantidade, Valor_Unitário, Valor_Total, Origem, Data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dados["Empresa"],
            dados["CNPJ"],
            dados["Produto"],
            dados["Quantidade"],
            dados["Valor Unitário"],
            dados["Valor Total"],
            dados["Origem"],
            dados["Data"]
        ))
        conn.commit()
        print(f"✅ Inserido no banco: {dados}")
    except Exception as e:
        print(f"Erro ao inserir: {e}")
    finally:
        conn.close()



def buscar_todos(cnpj=None):
    conn = sqlite3.connect("banco.db")
    c = conn.cursor()
    if cnpj:
        c.execute("SELECT * FROM produtos WHERE CNPJ = ?", (cnpj,))
    else:
        c.execute("SELECT * FROM produtos")
    dados = c.fetchall()
    conn.close()
    return dados


def resetar_banco():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS produtos")
    conn.commit()
    conn.close()
    criar_tabela()
