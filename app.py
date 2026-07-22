import streamlit as st
import sqlite3
import datetime
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Configuração da página para ocupar a largura total
st.set_page_config(page_title="VCS Informática - Orçamentos", page_icon="💻", layout="wide")

# 1. BANCO DE DADOS E MIGRAÇÃO
def iniciar_banco():
    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT UNIQUE,
        descricao TEXT NOT NULL,
        preco REAL NOT NULL,
        categoria TEXT NOT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orcamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_orcamento TEXT NOT NULL,
        cliente TEXT NOT NULL,
        documento TEXT,
        telefone TEXT,
        endereco TEXT,
        garantia TEXT,
        validade TEXT,
        pagamento TEXT,
        data TEXT NOT NULL,
        total REAL NOT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS itens_orcamento (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_orcamento TEXT NOT NULL,
        produto TEXT NOT NULL,
        quantidade INTEGER NOT NULL,
        preco_unitario REAL NOT NULL,
        subtotal REAL NOT NULL
    )
    """)
    conn.commit()
    conn.close()

iniciar_banco()

# Função para formatar CPF/CNPJ e Telefone dinamicamente
def formatar_documento(doc):
    doc_limpo = "".join(filter(str.isdigit, str(doc)))
    if len(doc_limpo) == 11:  # CPF
        return f"{doc_limpo[:3]}.{doc_limpo[3:6]}.{doc_limpo[6:9]}-{doc_limpo[9:]}"
    elif len(doc_limpo) == 14:  # CNPJ
        return f"{doc_limpo[:2]}.{doc_limpo[2:5]}.{doc_limpo[5:8]}/{doc_limpo[8:12]}-{doc_limpo[12:]}"
    return doc

def formatar_telefone(tel):
    tel_limpo = "".join(filter(str.isdigit, str(tel)))
    if len(tel_limpo) == 11:  # Celular com 9 dígitos
        return f"({tel_limpo[:2]}) {tel_limpo[2]} {tel_limpo[3:7]}-{tel_limpo[7:]}"
    elif len(tel_limpo) == 10:  # Telefone fixo
        return f"({tel_limpo[:2]}) {tel_limpo[2:6]}-{tel_limpo[6:]}"
    return tel

# MENU LATERAL
st.sidebar.title("🛠️ VCS Informática")
menu = st.sidebar.radio("Navegação", ["Criar Orçamento", "Consultar Orçamentos", "Pesquisar Clientes", "Gerenciar Produtos"])

# ---------------------------------------------------------
# TELA 1: CRIAR ORÇAMENTO
# ---------------------------------------------------------
if menu == "Criar Orçamento":
    st.subheader("📝 Novo Orçamento")
    
    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    cursor.execute("SELECT descricao, preco FROM produtos")
    produtos_db = cursor.fetchall()
    conn.close()

    if not produtos_db:
        st.warning("⚠️ Cadastre alguns produtos na aba 'Gerenciar Produtos' antes de emitir um orçamento.")
    
    col1, col2 = st.columns(2)
    with col1:
        cliente = st.text_input("Nome do Cliente")
        documento = st.text_input("CPF ou CNPJ")
    with col2:
        telefone = st.text_input("Telefone / Celular")
        endereco = st.text_input("Endereço")

    st.markdown("---")
    st.subheader("🛍️ Itens do Orçamento")

    if "carrinho" not in st.session_state:
        st.session_state.carrinho = []

    if produtos_db:
        opcoes_produtos = {p[0]: p[1] for p in produtos_db}
        col_p1, col_p2, col_p3 = st.columns([3, 1, 1])
        with col_p1:
            produto_selecionado = st.selectbox("Selecionar Produto", list(opcoes_produtos.keys()))
        with col_p2:
            quantidade = st.number_input("Qtd", min_value=1, value=1)
        with col_p3:
            st.text("")
            st.text("")
            if st.button("Adicionar Item"):
                preco_unit = opcoes_produtos[produto_selecionado]
                subtotal = preco_unit * quantidade
                st.session_state.carrinho.append({
                    "produto": produto_selecionado,
                    "quantidade": quantidade,
                    "preco_unitario": preco_unit,
                    "subtotal": subtotal
                })
                st.success("Item adicionado!")

    if st.session_state.carrinho:
        st.markdown("### Carrinho Atual")
        total_geral = 0
        novos_itens = []
        for i, item in enumerate(st.session_state.carrinho):
            col_i1, col_i2, col_i3, col_i4 = st.columns([3, 1, 1, 1])
            col_i1.write(item["produto"])
            col_i2.write(f"Qtd: {item['quantidade']}")
            col_i3.write(f"R$ {item['subtotal']:.2f}")
            total_geral += item["subtotal"]
            if not col_i4.button("🗑️", key=f"del_{i}"):
                novos_itens.append(item)
        st.session_state.carrinho = novos_itens
        st.markdown(f"### **Total Geral: R$ {total_geral:.2f}**")

        st.markdown("---")
        st.subheader("⚙️ Condições")
        c1, c2, c3 = st.columns(3)
        with c1:
            garantia = st.text_input("Garantia", value="90 dias")
        with c2:
            validade = st.text_input("Validade da Proposta", value="10 dias")
        with c3:
            pagamento = st.text_input("Forma de Pagamento", value="À vista / PIX")

        if st.button("💾 Salvar Orçamento"):
            if not cliente:
                st.error("Preencha o nome do cliente!")
            else:
                num_orc = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                data_atual = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                doc_fmt = formatar_documento(documento)
                tel_fmt = formatar_telefone(telefone)

                conn = sqlite3.connect("banco_vcs.db")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO orcamentos (numero_orcamento, cliente, documento, telefone, endereco, garantia, validade, pagamento, data, total)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (num_orc, cliente, doc_fmt, tel_fmt, endereco, garantia, validade, pagamento, data_atual, total_geral))
                
                for item in st.session_state.carrinho:
                    cursor.execute("""
                        INSERT INTO itens_orcamento (numero_orcamento, produto, quantidade, preco_unitario, subtotal)
                        VALUES (?, ?, ?, ?, ?)
                    """, (num_orc, item["produto"], item["quantidade"], item["preco_unitario"], item["subtotal"]))
                
                conn.commit()
                conn.close()
                st.session_state.carrinho = []
                st.success(f"Orçamento nº {num_orc} salvo com sucesso!")

# ---------------------------------------------------------
# TELA 2: CONSULTAR ORÇAMENTOS
# ---------------------------------------------------------
elif menu == "Consultar Orçamentos":
    st.subheader("🔍 Consultar e Pesquisar Orçamentos")
    
    pesquisa = st.text_input("Pesquisar por Nome do Cliente ou CPF/CNPJ:")

    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    
    if pesquisa:
        cursor.execute("SELECT * FROM orcamentos WHERE cliente LIKE ? OR documento LIKE ? ORDER BY id DESC", (f"%{pesquisa}%", f"%{pesquisa}%"))
    else:
        cursor.execute("SELECT * FROM orcamentos ORDER BY id DESC")
        
    orcamentos = cursor.fetchall()
    conn.close()

    if not orcamentos:
        st.info("Nenhum orçamento encontrado.")
    else:
        for orc in orcamentos:
            with st.expander(f"Orçamento #{orc[1]} - Cliente: {orc[2]} - Data: {orc[9]} - Total: R$ {orc[10]:.2f}"):
                st.write(f"**CPF/CNPJ:** {orc[3]}")
                st.write(f"**Telefone:** {orc[4]}")
                st.write(f"**Endereço:** {orc[5]}")
                st.write(f"**Garantia:** {orc[6]} | **Validade:** {orc[7]} | **Pagamento:** {orc[8]}")
                
                conn = sqlite3.connect("banco_vcs.db")
                cursor = conn.cursor()
                cursor.execute("SELECT produto, quantidade, preco_unitario, subtotal FROM itens_orcamento WHERE numero_orcamento = ?", (orc[1],))
                itens = cursor.fetchall()
                conn.close()
                
                st.markdown("**Itens:**")
                for item in itens:
                    st.text(f"- {item[0]} | Qtd: {item[1]} | Unit: R$ {item[2]:.2f} | Subtotal: R$ {item[3]:.2f}")

# ---------------------------------------------------------
# TELA 3: PESQUISAR CLIENTES
# ---------------------------------------------------------
elif menu == "Pesquisar Clientes":
    st.subheader("👥 Consulta e Histórico de Clientes")
    
    pesquisa_cliente = st.text_input("Digite o nome ou CPF/CNPJ do cliente para buscar:")

    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    
    if pesquisa_cliente:
        cursor.execute("SELECT DISTINCT cliente, documento, telefone, endereco FROM orcamentos WHERE cliente LIKE ? OR documento LIKE ?", (f"%{pesquisa_cliente}%", f"%{pesquisa_cliente}%"))
    else:
        cursor.execute("SELECT DISTINCT cliente, documento, telefone, endereco FROM orcamentos")
        
    clientes = cursor.fetchall()
    conn.close()

    if not clientes:
        st.info("Nenhum cliente cadastrado via orçamentos ainda.")
    else:
        for cli in clientes:
            with st.expander(f"👤 {cli[0]} — CPF/CNPJ: {cli[1] or 'Não informado'}"):
                st.write(f"**Telefone / Celular:** {cli[2] or 'Não informado'}")
                st.write(f"**Endereço:** {cli[3] or 'Não informado'}")
                
                # Buscar histórico de orçamentos deste cliente específico
                conn = sqlite3.connect("banco_vcs.db")
                cursor = conn.cursor()
                cursor.execute("SELECT numero_orcamento, data, total FROM orcamentos WHERE cliente = ? ORDER BY id DESC", (cli[0],))
                historico = cursor.fetchall()
                conn.close()
                
                st.markdown("---")
                st.markdown("**Histórico de Orçamentos deste Cliente:**")
                if historico:
                    for h in historico:
                        st.text(f"• Orçamento #{h[0]} | Data: {h[1]} | Total: R$ {h[2]:.2f}")
                else:
                    st.text("Nenhum orçamento registrado.")

# ---------------------------------------------------------
# TELA 4: GERENCIAR PRODUTOS
# ---------------------------------------------------------
elif menu == "Gerenciar Produtos":
    st.subheader("📦 Gerenciamento de Produtos")
    
    with st.form("cad_prod"):
        codigo = st.text_input("Código do Produto")
        descricao = st.text_input("Descrição do Produto")
        preco = st.number_input("Preço (R$)", min_value=0.0, format="%.2f")
        categoria = st.text_input("Categoria")
        submit = st.form_submit_button("Cadastrar Produto")
        
        if submit:
            if descricao and preco > 0:
                try:
                    conn = sqlite3.connect("banco_vcs.db")
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO produtos (codigo, descricao, preco, categoria) VALUES (?, ?, ?, ?)", (codigo, descricao, preco, categoria))
                    conn.commit()
                    conn.close()
                    st.success("Produto cadastrado com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao cadastrar (código duplicado?): {e}")
            else:
                st.error("Preencha a descrição e um preço válido.")

    st.markdown("---")
    st.subheader("Lista de Produtos Cadastrados")
    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    cursor.execute("SELECT codigo, descricao, preco, categoria FROM produtos")
    prods = cursor.fetchall()
    conn.close()
    
    for p in prods:
        st.text(f"[{p[0]}] {p[1]} - R$ {p[2]:.2f} ({p[3]})")