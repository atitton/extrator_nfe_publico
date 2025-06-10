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
        c.execute("SELECT * FROM produtos WHERE CNPJ=?", (cnpj,))
    else:
        c.execute("SELECT * FROM produtos")
    
    dados = c.fetchall()
    conn.close()
    return dados


def resetar_banco():
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute("DROP TABLE IF EXISTS produtos")
        criar_tabela() # Recria a tabela após apagar
        conn.commit()
        print("✅ Banco de dados resetado com sucesso.")
    except Exception as e:
        print(f"Erro ao resetar o banco de dados: {e}")
    finally:
        conn.close()



def apagar_produtos_por_cnpj(cnpj):
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM produtos WHERE CNPJ = ?", (cnpj,))
        conn.commit()
        print(f"✅ Produtos do CNPJ {cnpj} apagados com sucesso.")
    except Exception as e:
        print(f"Erro ao apagar produtos do CNPJ {cnpj}: {e}")
    finally:
        conn.close()
        
def excluir_produtos_por_data(cnpj, data_ini, data_fim):
    conn = conectar()
    c = conn.cursor()
    c.execute("""
        DELETE FROM produtos
        WHERE CNPJ = ? AND date(Data) BETWEEN ? AND ?
    """, (cnpj, data_ini.isoformat(), data_fim.isoformat()))
    conn.commit()
    conn.close()
