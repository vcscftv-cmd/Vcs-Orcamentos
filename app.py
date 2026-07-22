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

# Função para gerar número sequencial simples (ex: Orcamento_001-27-02-2026)
def gerar_numero_orcamento():
    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM orcamentos")
    qtd = cursor.fetchone()[0]
    conn.close()
    
    proximo_id = qtd + 1
    data_hoje = datetime.datetime.now().strftime("%d-%m-%Y")
    return f"Orcamento_{proximo_id:03d}-{data_hoje}"

# Funções de Conversão e Formatação Brasileira
def converter_para_float(texto_valor):
    try:
        limpo = str(texto_valor).strip().replace("R$", "").strip()
        if not limpo:
            return 0.0
        limpo = limpo.replace(".", "").replace(",", ".")
        return float(limpo)
    except:
        return 0.0

def formatar_moeda(valor):
    try:
        val_str = f"{float(valor):,.2f}"
        val_str = val_str.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {val_str}"
    except:
        return "R$ 0,00"

def formatar_documento(doc):
    doc_limpo = "".join(filter(str.isdigit, str(doc)))
    if len(doc_limpo) == 11:
        return f"{doc_limpo[:3]}.{doc_limpo[3:6]}.{doc_limpo[6:9]}-{doc_limpo[9:]}"
    elif len(doc_limpo) == 14:
        return f"{doc_limpo[:2]}.{doc_limpo[2:5]}.{doc_limpo[5:8]}/{doc_limpo[8:12]}-{doc_limpo[12:]}"
    return doc

def formatar_telefone(tel):
    tel_limpo = "".join(filter(str.isdigit, str(tel)))
    if len(tel_limpo) == 11:
        return f"({tel_limpo[:2]}) {tel_limpo[2]} {tel_limpo[3:7]}-{tel_limpo[7:]}"
    elif len(tel_limpo) == 10:
        return f"({tel_limpo[:2]}) {tel_limpo[2:6]}-{tel_limpo[6:]}"
    return tel

# MENU LATERAL
st.sidebar.title("🛠️ VCS Informática")
menu = st.sidebar.radio("Navegação", ["Criar Orçamento", "Consultar Orçamentos", "Gerenciar Produtos", "Gerenciar Clientes"])

# ---------------------------------------------------------
# TELA 1: CRIAR ORÇAMENTO
# ---------------------------------------------------------
if menu == "Criar Orçamento":
    st.subheader("📝 Novo Orçamento")
    
    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    cursor.execute("SELECT descricao, preco, categoria FROM produtos")
    produtos_db = cursor.fetchall()
    
    cursor.execute("SELECT DISTINCT cliente, documento, telefone, endereco FROM orcamentos")
    clientes_salvos = cursor.fetchall()
    conn.close()

    dict_clientes = {c[0]: {"documento": c[1], "telefone": c[2], "endereco": c[3]} for c in clientes_salvos}
    lista_nomes_clientes = [""] + list(dict_clientes.keys())

    st.markdown("### 👤 Dados do Cliente")
    
    if "form_cliente" not in st.session_state:
        st.session_state.form_cliente = ""
    if "form_documento" not in st.session_state:
        st.session_state.form_documento = ""
    if "form_telefone" not in st.session_state:
        st.session_state.form_telefone = ""
    if "form_endereco" not in st.session_state:
        st.session_state.form_endereco = ""

    def atualizar_campos_cliente():
        sel = st.session_state.sel_cliente_box
        if sel in dict_clientes:
            st.session_state.form_cliente = sel
            st.session_state.form_documento = dict_clientes[sel]["documento"] or ""
            st.session_state.form_telefone = dict_clientes[sel]["telefone"] or ""
            st.session_state.form_endereco = dict_clientes[sel]["endereco"] or ""

    st.selectbox("Buscar Cliente Cadastrado (Opcional)", lista_nomes_clientes, key="sel_cliente_box", on_change=atualizar_campos_cliente)

    with st.form("form_dados_cliente"):
        col_cad1, col_cad2 = st.columns(2)
        with col_cad1:
            cliente = st.text_input("Nome do Cliente", value=st.session_state.form_cliente)
            documento = st.text_input("CPF ou CNPJ", value=st.session_state.form_documento, placeholder="Ex: 000.000.000-00")
        with col_cad2:
            telefone = st.text_input("Telefone / WhatsApp", value=st.session_state.form_telefone, placeholder="Ex: (71) 99999-9999")
            endereco = st.text_input("Endereço", value=st.session_state.form_endereco)
        
        btn_atualizar_dados = st.form_submit_button("Atualizar / Fixar Dados do Cliente")

    st.markdown("---")
    
    # Seção condicional: Serviço / Instalação
    st.subheader("🛠️ Serviço e Instalação")
    incluir_servico = st.radio("Deseja incluir Serviço / Instalação neste orçamento?", ["Não", "Sim"], horizontal=True, key="radio_servico")
    
    valor_instalacao = 0.0
    desc_servico = ""
    srv_instalacao = "Não"

    if incluir_servico == "Sim":
        srv_instalacao = "Sim"
        col_s1, col_s2 = st.columns([1, 2])
        with col_s1:
            txt_valor_inst = st.text_input("Valor da Instalação (R$)", value="0,00", placeholder="Ex: 150,00 ou 1000")
            valor_instalacao = converter_para_float(txt_valor_inst)
        with col_s2:
            desc_servico = st.text_input("Descrição do Serviço / Observações", placeholder="Ex: Passagem de cabos, configuração de rede...")

    st.markdown("---")
    
    # Seção condicional: Defeito Relatado
    st.subheader("⚠️ Defeito Relatado")
    incluir_defeito = st.radio("Deseja relatar algum defeito no equipamento?", ["Não", "Sim"], horizontal=True, key="radio_defeito")
    
    possui_defeito = "Não"
    desc_defeito = ""

    if incluir_defeito == "Sim":
        possui_defeito = "Sim"
        desc_defeito = st.text_input("Descrição do Defeito", placeholder="Ex: Equipamento não liga, sem imagem na câmera...")

    st.markdown("---")
    
    # Seção condicional: Adicionar Itens / Produtos
    st.subheader("🛍️ Itens do Orçamento")
    incluir_itens = st.radio("Deseja adicionar itens (produtos) neste orçamento?", ["Não", "Sim"], horizontal=True, key="radio_itens")

    if "carrinho" not in st.session_state:
        st.session_state.carrinho = []

    if incluir_itens == "Sim":
        if not produtos_db:
            st.warning("⚠️ Cadastre alguns produtos na aba 'Gerenciar Produtos' antes de emitir um orçamento.")
        else:
            cat_escolhida = st.selectbox("Selecione a Categoria / Setor", ["CFTV", "Informática"])
            produtos_filtrados = [p for p in produtos_db if p[2].strip().lower() == cat_escolhida.lower()]
            
            if not produtos_filtrados:
                st.info(f"Nenhum produto cadastrado na categoria '{cat_escolhida}' no momento.")
            else:
                opcoes_produtos = {p[0]: p[1] for p in produtos_filtrados}
                col_p1, col_p2, col_p3 = st.columns([3, 1, 1])
                with col_p1:
                    produto_selecionado = st.selectbox(f"Produto de {cat_escolhida}", list(opcoes_produtos.keys()))
                with col_p2:
                    quantidade = st.number_input("Qtd", min_value=1, value=1)
                with col_p3:
                    st.text("")
                    st.text("")
                    if st.button("Adicionar Item"):
                        preco_unit = opcoes_produtos[produto_selecionado]
                        
                        item_encontrado = False
                        for item in st.session_state.carrinho:
                            if item["produto"] == produto_selecionado:
                                item["quantidade"] += quantidade
                                item["subtotal"] = item["quantidade"] * item["preco_unitario"]
                                item_encontrado = True
                                break
                        
                        if not item_encontrado:
                            subtotal = preco_unit * quantidade
                            st.session_state.carrinho.append({
                                "produto": produto_selecionado,
                                "quantidade": quantidade,
                                "preco_unitario": preco_unit,
                                "subtotal": subtotal
                            })
                        st.success("Item adicionado / atualizado!")

    total_instalacao_calculado = valor_instalacao if srv_instalacao == "Sim" else 0.0

    if st.session_state.carrinho or total_instalacao_calculado > 0:
        if st.session_state.carrinho:
            st.markdown("### Carrinho Atual")
            subtotal_produtos = 0
            novos_itens = []
            for i, item in enumerate(st.session_state.carrinho):
                col_i1, col_i2, col_i3, col_i4 = st.columns([3, 1, 1, 1])
                col_i1.write(item["produto"])
                col_i2.write(f"Qtd: {item['quantidade']}")
                col_i3.write(formatar_moeda(item['subtotal']))
                subtotal_produtos += item["subtotal"]
                if not col_i4.button("🗑️", key=f"del_{i}"):
                    novos_itens.append(item)
            st.session_state.carrinho = novos_itens
        else:
            subtotal_produtos = 0.0

        if srv_instalacao == "Sim" and valor_instalacao > 0:
            st.markdown(f"**Taxa / Valor de Instalação:** {formatar_moeda(valor_instalacao)}")

        subtotal_geral = subtotal_produtos + total_instalacao_calculado

        col_desc1, col_desc2 = st.columns([2, 2])
        with col_desc1:
            tipo_desconto = st.selectbox("Tipo de Desconto", ["Nenhum", "Valor (R$)", "Porcentagem (%)"])
        with col_desc2:
            txt_valor_desc = st.text_input("Valor do Desconto", value="0,00")
            valor_desconto = converter_para_float(txt_valor_desc)

        if tipo_desconto == "Valor (R$)":
            total_geral = max(0.0, subtotal_geral - valor_desconto)
        elif tipo_desconto == "Porcentagem (%)":
            total_geral = max(0.0, subtotal_geral * (1 - valor_desconto / 100.0))
        else:
            total_geral = subtotal_geral

        st.markdown(f"### **Total Geral: {formatar_moeda(total_geral)}**")

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
                num_orc = gerar_numero_orcamento()
                data_atual = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                
                doc_fmt = documento if any(c in documento for c in ".-/") else formatar_documento(documento)
                tel_fmt = telefone if any(c in telefone for c in "()- ") else formatar_telefone(telefone)

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
                
                if srv_instalacao == "Sim" and valor_instalacao > 0:
                    cursor.execute("""
                        INSERT INTO itens_orcamento (numero_orcamento, produto, quantidade, preco_unitario, subtotal)
                        VALUES (?, ?, ?, ?, ?)
                    """, (num_orc, f"Serviço de Instalação: {desc_servico if desc_servico else 'Instalação padrão'}", 1, valor_instalacao, valor_instalacao))

                conn.commit()
                conn.close()
                st.session_state.carrinho = []
                st.success(f"Orçamento nº {num_orc} salvo com sucesso!")

# ---------------------------------------------------------
# TELA 2: CONSULTAR ORÇAMENTOS (COM OPÇÃO DE EXCLUIR)
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
            with st.expander(f"{orc[1]} - Cliente: {orc[2]} - Data: {orc[9]} - Total: {formatar_moeda(orc[10])}"):
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
                    st.text(f"- {item[0]} | Qtd: {item[1]} | Unit: {formatar_moeda(item[2])} | Subtotal: {formatar_moeda(item[3])}")

                st.markdown("---")
                if st.button(f"🗑️ Excluir Orçamento {orc[1]}", key=f"exc_orc_{orc[0]}"):
                    conn = sqlite3.connect("banco_vcs.db")
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM orcamentos WHERE id = ?", (orc[0],))
                    cursor.execute("DELETE FROM itens_orcamento WHERE numero_orcamento = ?", (orc[1],))
                    conn.commit()
                    conn.close()
                    st.success(f"Orçamento {orc[1]} excluído com sucesso!")
                    st.rerun()

# ---------------------------------------------------------
# TELA 3: GERENCIAR PRODUTOS (COM EDIÇÃO E EXCLUSÃO)
# ---------------------------------------------------------
elif menu == "Gerenciar Produtos":
    st.subheader("📦 Gerenciamento de Produtos")
    
    with st.form("cad_prod"):
        st.markdown("### Cadastrar Novo Produto")
        codigo = st.text_input("Código do Produto")
        descricao = st.text_input("Descrição do Produto")
        preco = st.number_input("Preço (R$)", min_value=0.0, format="%.2f")
        categoria = st.selectbox("Categoria", ["CFTV", "Informática"])
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
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao cadastrar (código duplicado?): {e}")
            else:
                st.error("Preencha a descrição e um preço válido.")

    st.markdown("---")
    st.subheader("Lista e Edição de Produtos Cadastrados")
    
    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, codigo, descricao, preco, categoria FROM produtos")
    prods = cursor.fetchall()
    conn.close()

    if not prods:
        st.info("Nenhum produto cadastrado.")
    else:
        for p in prods:
            p_id, p_cod, p_desc, p_preco, p_cat = p
            with st.expander(f"[{p_cod}] {p_desc} - {formatar_moeda(p_preco)} ({p_cat})"):
                with st.form(f"form_edit_prod_{p_id}"):
                    novo_desc = st.text_input("Editar Descrição", value=p_desc, key=f"desc_{p_id}")
                    
                    # Campo de texto flexível para preço formatado
                    txt_novo_preco = st.text_input("Editar Preço (R$)", value=str(p_preco).replace('.', ','), key=f"preco_{p_id}")
                    
                    nova_cat = st.selectbox("Editar Categoria", ["CFTV", "Informática"], index=0 if p_cat == "CFTV" else 1, key=f"cat_{p_id}")
                    
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        salvar_edicao = st.form_submit_button("💾 Salvar Alterações")
                    with col_b2:
                        excluir_prod = st.form_submit_button("🗑️ Excluir Produto")

                    if salvar_edicao:
                        preco_convertido = converter_para_float(txt_novo_preco)
                        if novo_desc and preco_convertido > 0:
                            conn = sqlite3.connect("banco_vcs.db")
                            cursor = conn.cursor()
                            cursor.execute("UPDATE produtos SET descricao = ?, preco = ?, categoria = ? WHERE id = ?", (novo_desc, preco_convertido, nova_cat, p_id))
                            conn.commit()
                            conn.close()
                            st.success("Produto atualizado com sucesso!")
                            st.rerun()
                        else:
                            st.error("Preencha uma descrição e um preço válidos.")

                    if excluir_prod:
                        conn = sqlite3.connect("banco_vcs.db")
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM produtos WHERE id = ?", (p_id,))
                        conn.commit()
                        conn.close()
                        st.success("Produto excluído com sucesso!")
                        st.rerun()

# ---------------------------------------------------------
# TELA 4: GERENCIAR / PESQUISAR CLIENTES (COM EDIÇÃO)
# ---------------------------------------------------------
elif menu == "Gerenciar Clientes":
    st.subheader("👥 Pesquisa e Gerenciamento de Clientes")
    
    pesq_cliente = st.text_input("Pesquisar Cliente por Nome ou CPF/CNPJ:")

    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    
    if pesq_cliente:
        cursor.execute("SELECT DISTINCT cliente, documento, telefone, endereco FROM orcamentos WHERE cliente LIKE ? OR documento LIKE ?", (f"%{pesq_cliente}%", f"%{pesq_cliente}%"))
    else:
        cursor.execute("SELECT DISTINCT cliente, documento, telefone, endereco FROM orcamentos")
        
    clientes_encontrados = cursor.fetchall()
    conn.close()

    if not clientes_encontrados:
        st.info("Nenhum cliente encontrado nos orçamentos salvos.")
    else:
        for cli in clientes_encontrados:
            c_nome, c_doc, c_tel, c_end = cli
            with st.expander(f"Cliente: {c_nome} | Doc: {c_doc or 'Não informado'}"):
                with st.form(f"form_edit_cli_{c_nome}"):
                    novo_nome = st.text_input("Nome do Cliente", value=c_nome)
                    novo_doc = st.text_input("CPF ou CNPJ", value=c_doc or "")
                    novo_tel = st.text_input("Telefone / WhatsApp", value=c_tel or "")
                    novo_end = st.text_input("Endereço", value=c_end or "")
                    
                    salvar_cli = st.form_submit_button("💾 Atualizar Dados do Cliente em todos os Orçamentos")
                    
                    if salvar_cli:
                        if not novo_nome:
                            st.error("O nome do cliente não pode ficar vazio.")
                        else:
                            conn = sqlite3.connect("banco_vcs.db")
                            cursor = conn.cursor()
                            # Atualiza todos os registros onde o cliente original aparecia
                            cursor.execute("""
                                UPDATE orcamentos 
                                SET cliente = ?, documento = ?, telefone = ?, endereco = ? 
                                WHERE cliente = ?
                            """, (novo_nome, novo_doc, novo_tel, novo_end, c_nome))
                            conn.commit()
                            conn.close()
                            st.success("Dados do cliente atualizados com sucesso em todos os orçamentos!")
                            st.rerun()