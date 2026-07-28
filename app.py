import streamlit as st
import sqlite3
import datetime
import requests
import hashlib
import time
import base64
import os
import pandas as pd

# Configuração da página para ocupar a largura total
st.set_page_config(page_title="Sistema de Orçamentos e Propostas", page_icon="💻", layout="wide")

# 🏢 BANCOS DE DADOS DAS EMPRESAS (ORÇAMENTOS E LOGS)
EMPRESAS = {
    "VCS Informática": "vcs_informatica.db",
    "STI TECNOLOGIA": "sti_tecnologia.db",
    "VORTICE GRAFTENG": "vortice_grafteng.db"
}

# 🌍 BANCOS GLOBAIS (COMPARTILHADOS PARA CLIENTES E PRODUTOS)
DB_CLIENTES_GLOBAL = "clientes_global.db"
DB_PRODUTOS_GLOBAL = "produtos_global.db"

st.sidebar.title("🏢 Seleção de Empresa")
empresa_selecionada = st.sidebar.selectbox("Escolha a Empresa Atual:", list(EMPRESAS.keys()))
DB_ARQUIVO = EMPRESAS[empresa_selecionada]

def conectar():
    return sqlite3.connect(DB_ARQUIVO)

def conectar_clientes():
    return sqlite3.connect(DB_CLIENTES_GLOBAL)

def conectar_produtos():
    return sqlite3.connect(DB_PRODUTOS_GLOBAL)

# ⚙️ CONFIGURAÇÃO DA LOGOMARCA INDIVIDUAL POR EMPRESA
@st.cache_data(show_spinner=False)
def obter_logo_base64_cached(empresa):
    nome_limpo = "".join(c if c.isalnum() else "_" for c in empresa.lower())
    arquivo_logo_empresa = f"logo_{nome_limpo}.png"
    
    if os.path.exists(arquivo_logo_empresa):
        with open(arquivo_logo_empresa, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return None

def obter_logo_base64():
    return obter_logo_base64_cached(empresa_selecionada)

def hash_senha(senha):
    return hashlib.sha256(str(senha).encode()).hexdigest()

def iniciar_banco():
    conn = conectar()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        perfil TEXT NOT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT NOT NULL,
        acao TEXT NOT NULL,
        detalhes TEXT NOT NULL,
        data TEXT NOT NULL
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
        total REAL NOT NULL,
        criado_por TEXT,
        tipo_documento TEXT DEFAULT 'Orçamento'
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
    
    try:
        cursor.execute("ALTER TABLE orcamentos ADD COLUMN criado_por TEXT")
        conn.commit()
    except:
        pass

    try:
        cursor.execute("ALTER TABLE orcamentos ADD COLUMN tipo_documento TEXT DEFAULT 'Orçamento'")
        conn.commit()
    except:
        pass

    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        senha_padrao = hash_senha("samu@2707")
        cursor.execute("INSERT INTO usuarios (usuario, senha, perfil) VALUES (?, ?, ?)", ("admin", senha_padrao, "Admin"))
        conn.commit()
        
    conn.close()

    conn_cli = conectar_clientes()
    cursor_cli = conn_cli.cursor()
    cursor_cli.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        documento TEXT,
        telefone TEXT,
        endereco TEXT
    )
    """)
    conn_cli.commit()
    conn_cli.close()

    conn_prod = conectar_produtos()
    cursor_prod = conn_prod.cursor()
    cursor_prod.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT,
        descricao TEXT NOT NULL,
        preco REAL NOT NULL,
        categoria TEXT NOT NULL
    )
    """)
    conn_prod.commit()
    conn_prod.close()

    # 🔄 MIGRAÇÃO ÚNICA: Importa produtos antigos das empresas para o banco global se faltarem
    try:
        conn_gp = conectar_produtos()
        cursor_gp = conn_gp.cursor()
        
        cursor_gp.execute("SELECT descricao FROM produtos")
        existentes_global = {row[0].strip().lower() for row in cursor_gp.fetchall()}

        for db_emp in EMPRESAS.values():
            if os.path.exists(db_emp):
                try:
                    conn_e = sqlite3.connect(db_emp)
                    cursor_e = conn_e.cursor()
                    cursor_e.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='produtos'")
                    if cursor_e.fetchone():
                        cursor_e.execute("SELECT codigo, descricao, preco, categoria FROM produtos")
                        for p in cursor_e.fetchall():
                            desc = p[1].strip()
                            if desc.lower() not in existentes_global:
                                codigo_val = p[0] if p[0] else ""
                                cursor_gp.execute("INSERT INTO produtos (codigo, descricao, preco, categoria) VALUES (?, ?, ?, ?)", (codigo_val, desc, p[2], p[3]))
                                existentes_global.add(desc.lower())
                    conn_e.close()
                except:
                    pass
        conn_gp.commit()
        conn_gp.close()
    except:
        pass

iniciar_banco()

@st.cache_data(show_spinner=False, ttl=600)
def carregar_todos_produtos():
    produtos_dict = {} 
    try:
        conn_p = conectar_produtos()
        cursor_p = conn_p.cursor()
        cursor_p.execute("SELECT descricao, preco, categoria FROM produtos")
        for p in cursor_p.fetchall():
            desc = p[0].strip()
            produtos_dict[desc.lower()] = (p[0], p[1], p[2])
        conn_p.close()
    except:
        pass
                
    return list(produtos_dict.values())

@st.cache_data(show_spinner=False, ttl=300)
def carregar_clientes_cadastrados():
    try:
        conn_c = conectar_clientes()
        cursor_c = conn_c.cursor()
        cursor_c.execute("SELECT nome, documento, telefone, endereco FROM clientes ORDER BY nome ASC")
        dados = cursor_c.fetchall()
        conn_c.close()
        return dados
    except:
        return []

# HORÁRIO CORRIGIDO: Define a timezone do Brasil (UTC-3)
def registrar_log(usuario, acao, detalhes):
    conn = conectar()
    cursor = conn.cursor()
    fuso_br = datetime.timezone(datetime.timedelta(hours=-3))
    data_hora = datetime.datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M:%S")
    cursor.execute("INSERT INTO logs (usuario, acao, detalhes, data) VALUES (?, ?, ?, ?)", (usuario, acao, detalhes, data_hora))
    conn.commit()
    conn.close()

def buscar_cep(cep):
    cep_limpo = "".join(filter(str.isdigit, str(cep)))
    if len(cep_limpo) == 8:
        try:
            url = f"https://viacep.com.br/ws/{cep_limpo}/json/"
            response = requests.get(url, timeout=3)
            dados = response.json()
            if not dados.get("erro"):
                logradouro = dados.get("logradouro", "")
                bairro = dados.get("bairro", "")
                cidade = dados.get("localidade", "")
                uf = dados.get("uf", "")
                return f"{logradouro}, {bairro} - {cidade}/{uf}"
        except:
            pass
    return None

def formatar_documento(doc):
    digitos = "".join(filter(str.isdigit, str(doc)))
    if len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    elif len(digitos) == 14:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"
    return doc

def formatar_telefone(tel):
    digitos = "".join(filter(str.isdigit, str(tel)))
    if len(digitos) == 11:
        return f"{digitos[:2]} {digitos[2]} {digitos[3:7]}-{digitos[7:]}"
    elif len(digitos) == 10:
        return f"{digitos[:2]} {digitos[2:6]}-{digitos[6:]}"
    return tel

def gerar_numero_documento(tipo_doc):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM orcamentos")
    qtd = cursor.fetchone()[0]
    conn.close()
    
    proximo_id = qtd + 1
    return f"{proximo_id:03d}"

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

TEMPO_INATIVIDADE_MAX = 600 

# Inicialização segura do session_state
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_atual" not in st.session_state:
    st.session_state.usuario_atual = ""
if "perfil_atual" not in st.session_state:
    st.session_state.perfil_atual = ""
if "ultimo_acesso" not in st.session_state:
    st.session_state.ultimo_acesso = time.time()
if "ultimo_orcamento_imprimir" not in st.session_state:
    st.session_state.ultimo_orcamento_imprimir = None
if "modo_edicao_orcamento" not in st.session_state:
    st.session_state.modo_edicao_orcamento = None

if st.session_state.autenticado:
    tempo_atual = time.time()
    inatividade = tempo_atual - st.session_state.ultimo_acesso
    if inatividade > TEMPO_INATIVIDADE_MAX:
        registrar_log(st.session_state.usuario_atual, "LOGOUT AUTOMÁTICO", "Deslogado por inatividade (> 10 min)")
        st.session_state.autenticado = False
        st.session_state.usuario_atual = ""
        st.session_state.perfil_atual = ""
        st.warning("⚠️ Sessão expirada por inatividade. Faça login novamente.")
        st.rerun()
    else:
        st.session_state.ultimo_acesso = time.time()

if not st.session_state.autenticado:
    st.title(f"🔐 {empresa_selecionada} - Login")
    with st.form("form_login"):
        user_input = st.text_input("Usuário")
        senha_input = st.text_input("Senha", type="password")
        btn_login = st.form_submit_button("Entrar")
        
        if btn_login:
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute("SELECT perfil FROM usuarios WHERE usuario = ? AND senha = ?", (user_input, hash_senha(senha_input)))
            res = cursor.fetchone()
            conn.close()
            
            if res:
                st.session_state.autenticado = True
                st.session_state.usuario_atual = user_input
                st.session_state.perfil_atual = res[0]
                st.session_state.ultimo_acesso = time.time()
                
                registrar_log(user_input, "LOGIN", f"Usuário entrou no sistema ({empresa_selecionada})")
                st.success("Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos!")
    
    st.stop()

st.sidebar.markdown("---")
st.sidebar.write(f"👤 Logado como: **{st.session_state.usuario_atual}** ({st.session_state.perfil_atual})")
st.sidebar.info(f"📁 Empresa Ativa: **{empresa_selecionada}**")

opcoes_menu = ["Criar Orçamento / Proposta", "Consultar Documentos", "Gerenciar Produtos", "Gerenciar Clientes"]

if st.session_state.perfil_atual == "Admin":
    opcoes_menu.extend(["Gerenciar Usuários", "Logs de Auditoria"])

menu = st.sidebar.radio("Navegação", opcoes_menu)

if st.sidebar.button("🚪 Sair do Sistema"):
    registrar_log(st.session_state.usuario_atual, "LOGOUT", "Usuário saiu do sistema manualmente")
    st.session_state.autenticado = False
    st.session_state.usuario_atual = ""
    st.session_state.perfil_atual = ""
    st.rerun()

# ---------------------------------------------------------
# TELA 1: CRIAR OU EDITAR ORÇAMENTO / PROPOSTA
# ---------------------------------------------------------
if menu == "Criar Orçamento / Proposta":
    editando_num = st.session_state.modo_edicao_orcamento
    
    if editando_num:
        st.subheader(f"✏️ Editando Documento Nº {editando_num} — [{empresa_selecionada}]")
        if st.button("❌ Cancelar Edição / Criar Novo"):
            st.session_state.modo_edicao_orcamento = None
            st.session_state.carrinho = []
            st.rerun()
    else:
        tipo_documento = st.radio("Tipo de Documento", ["ORCAMENTO", "PROPOSTA"], horizontal=True)
        st.subheader(f"📝 Novo {tipo_documento} — [{empresa_selecionada}]")

    produtos_db = carregar_todos_produtos()
    clientes_cadastrados = carregar_clientes_cadastrados()

    dict_clientes = {}
    for c in clientes_cadastrados:
        nome_cli = c[0].strip()
        dict_clientes[nome_cli] = {"documento": c[1], "telefone": c[2], "endereco": c[3]}

    lista_nomes_clientes = [""] + list(dict_clientes.keys())

    st.markdown("### 👤 Dados do Cliente")
    
    if "form_cliente" not in st.session_state:
        st.session_state.form_cliente = ""
    if "form_documento" not in st.session_state:
        st.session_state.form_documento = ""
    if "form_telefone" not in st.session_state:
        st.session_state.form_telefone = ""
    if "form_cep" not in st.session_state:
        st.session_state.form_cep = ""
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
            documento = st.text_input("CPF ou CNPJ", value=st.session_state.form_documento, placeholder="Ex: 123.456.789-10")
        with col_cad2:
            telefone = st.text_input("Telefone / Celular", value=st.session_state.form_telefone, placeholder="Ex: 71 9 9999 9999")
            cep_input = st.text_input("CEP (Busca automática opcional)", value=st.session_state.form_cep, placeholder="Ex: 40010000")
            
            endereco_buscado = ""
            if cep_input:
                resultado_cep = buscar_cep(cep_input)
                if resultado_cep:
                    endereco_buscado = resultado_cep

            endereco = st.text_input("Endereço Completo", value=endereco_buscado if endereco_buscado else st.session_state.form_endereco)
        
        btn_atualizar_dados = st.form_submit_button("Atualizar / Fixar Dados do Cliente")
        
        if btn_atualizar_dados:
            if cliente.strip():
                doc_formatado = formatar_documento(documento.strip())
                tel_formatado = formatar_telefone(telefone.strip())
                
                st.session_state.form_cliente = cliente.strip()
                st.session_state.form_documento = doc_formatado
                st.session_state.form_telefone = tel_formatado
                st.session_state.form_endereco = endereco.strip()
                
                conn_c = conectar_clientes()
                cursor_c = conn_c.cursor()
                cursor_c.execute("SELECT id FROM clientes WHERE nome = ?", (cliente.strip(),))
                cliente_existe = cursor_c.fetchone()
                
                if cliente_existe:
                    cursor_c.execute("""
                        UPDATE clientes 
                        SET documento = ?, telefone = ?, endereco = ? 
                        WHERE nome = ?
                    """, (doc_formatado, tel_formatado, endereco.strip(), cliente.strip()))
                else:
                    cursor_c.execute("""
                        INSERT INTO clientes (nome, documento, telefone, endereco)
                        VALUES (?, ?, ?, ?)
                    """, (cliente.strip(), doc_formatado, tel_formatado, endereco.strip()))
                
                conn_c.commit()
                conn_c.close()
                
                st.cache_data.clear()
                st.success("Dados do cliente salvos e fixados com sucesso!")
                st.rerun()
            else:
                st.error("Preencha o nome do cliente.")

    st.markdown("---")
    
    st.subheader("🛠️ Serviços")
    incluir_servicos = st.radio("Deseja adicionar serviço?", ["Não", "Sim"], horizontal=True, key="radio_servicos")
    
    subtotal_servicos = 0.0
    lista_servicos_processados = []
    
    if incluir_servicos == "Sim":
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            servico_descricao = st.text_input("Descrição do Serviço", value="Instalação / Configuração")
        with col_s2:
            servico_valor = st.text_input("Valor do Serviço (R$)", value="0,00")
            
        val_s = converter_para_float(servico_valor)
        if servico_descricao.strip() and val_s > 0:
            subtotal_servicos = val_s
            lista_servicos_processados.append({
                "produto": servico_descricao.strip(),
                "quantidade": 1,
                "preco_unitario": val_s,
                "subtotal": val_s
            })

    st.markdown("---")
    
    titulo_carrinho_str = "🛍️ Itens do Documento (Produtos)" if editando_num else f"🛍️ Itens do Orçamento/Proposta (Produtos)"
    st.subheader(titulo_carrinho_str)
    incluir_itens = st.radio("Deseja adicionar produtos do estoque neste documento?", ["Não", "Sim"], horizontal=True, key="radio_itens")

    if "carrinho" not in st.session_state:
        st.session_state.carrinho = []

    if incluir_itens == "Sim":
        if not produtos_db:
            st.warning("⚠️ Cadastre alguns produtos na aba 'Gerenciar Produtos' antes de emitir um documento.")
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
                    if st.button("Adicionar Produto"):
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
                        st.success("Produto adicionado ao carrinho!")

    if st.session_state.carrinho:
        st.markdown("### Carrinho de Produtos")
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

    subtotal_geral = subtotal_produtos + subtotal_servicos

    if subtotal_geral > 0:
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
            validade = st.text_input("Validade", value="10 dias")
        with c3:
            pagamento = st.text_input("Forma de Pagamento", value="À vista / PIX")

        texto_btn_salvar = f"💾 Salvar Alterações do Documento {editando_num}" if editando_num else f"💾 Salvar {tipo_documento}"

        if st.button(texto_btn_salvar):
            cliente_val = st.session_state.form_cliente.strip()
            if not cliente_val:
                st.error("Preencha o nome do cliente!")
            else:
                conn = conectar()
                cursor = conn.cursor()
                
                fuso_br = datetime.timezone(datetime.timedelta(hours=-3))
                data_atual = datetime.datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M")
                
                if editando_num:
                    num_orc = editando_num
                    
                    cursor.execute("""
                        UPDATE orcamentos 
                        SET cliente = ?, documento = ?, telefone = ?, endereco = ?, garantia = ?, validade = ?, pagamento = ?, data = ?, total = ?
                        WHERE numero_orcamento = ?
                    """, (cliente_val, st.session_state.form_documento, st.session_state.form_telefone, st.session_state.form_endereco, garantia, validade, pagamento, data_atual, total_geral, num_orc))
                    
                    cursor.execute("DELETE FROM itens_orcamento WHERE numero_orcamento = ?", (num_orc,))
                    
                else:
                    tipo_doc_atual = tipo_documento if 'tipo_documento' in locals() else "ORCAMENTO"
                    num_orc = gerar_numero_documento(tipo_doc_atual)

                    cursor.execute("""
                        INSERT INTO orcamentos (numero_orcamento, cliente, documento, telefone, endereco, garantia, validade, pagamento, data, total, criado_por, tipo_documento)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (num_orc, cliente_val, st.session_state.form_documento, st.session_state.form_telefone, st.session_state.form_endereco, garantia, validade, pagamento, data_atual, total_geral, st.session_state.usuario_atual, tipo_doc_atual))
                
                for item in st.session_state.carrinho:
                    cursor.execute("""
                        INSERT INTO itens_orcamento (numero_orcamento, produto, quantidade, preco_unitario, subtotal)
                        VALUES (?, ?, ?, ?, ?)
                    """, (num_orc, item["produto"], item["quantidade"], item["preco_unitario"], item["subtotal"]))
                
                for srv in lista_servicos_processados:
                    cursor.execute("""
                        INSERT INTO itens_orcamento (numero_orcamento, produto, quantidade, preco_unitario, subtotal)
                        VALUES (?, ?, ?, ?, ?)
                    """, (num_orc, srv["produto"], srv["quantidade"], srv["preco_unitario"], srv["subtotal"]))

                conn.commit()
                conn.close()
                
                acao_log = f"EDITAR DOCUMENTO" if editando_num else f"CRIAR DOCUMENTO"
                registrar_log(st.session_state.usuario_atual, acao_log, f"Documento {num_orc} salvo para {cliente_val} em {empresa_selecionada}")
                
                st.session_state.carrinho = []
                st.session_state.modo_edicao_orcamento = None
                st.session_state.ultimo_orcamento_imprimir = num_orc
                st.success(f"Documento nº {num_orc} salvo com sucesso!")
                st.rerun()

    if st.session_state.ultimo_orcamento_imprimir:
        st.markdown("---")
        st.success(f"🖨️ O último documento gerado (**{st.session_state.ultimo_orcamento_imprimir}**) está pronto!")
        if st.button("📄 Abrir Página de Impressão / PDF"):
            st.session_state.modo_impressao = st.session_state.ultimo_orcamento_imprimir
            st.rerun()

# ---------------------------------------------------------
# TELA DE IMPRESSÃO / PDF COM NOME DO CLIENTE NO TÍTULO
# ---------------------------------------------------------
if "modo_impressao" in st.session_state and st.session_state.modo_impressao:
    num_alvo = st.session_state.modo_impressao
    
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orcamentos WHERE numero_orcamento = ?", (num_alvo,))
    orc_dados = cursor.fetchone()
    
    cursor.execute("SELECT produto, quantidade, preco_unitario, subtotal FROM itens_orcamento WHERE numero_orcamento = ?", (num_alvo,))
    itens_dados = cursor.fetchall()
    conn.close()

    if orc_dados:
        st.markdown("---")
        if st.button("⬅️ Voltar ao Sistema"):
            st.session_state.modo_impressao = None
            st.rerun()

        logo_b64 = obter_logo_base64()
        tag_logo = f'<img src="data:image/png;base64,{logo_b64}" style="max-height: 80px; margin-bottom: 10px;" />' if logo_b64 else ''
        
        tipo_doc_salvo = orc_dados[12] if len(orc_dados) > 12 and orc_dados[12] else "ORCAMENTO"
        
        nome_cliente_limpo = "".join(c if c.isalnum() else "_" for c in str(orc_dados[2]).strip())
        nome_arquivo_pdf = f"ORC_{nome_cliente_limpo}"

        html_orcamento = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{nome_arquivo_pdf}</title>
            <style>
                body {{ background-color: #f8f9fa; font-family: Arial, sans-serif; padding: 20px; }}
                .sheet {{ background: white; color: black; padding: 40px; border: 1px solid #ddd; border-radius: 8px; max-width: 800px; margin: auto; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
                .header {{ text-align: center; border-bottom: 2px solid #004080; padding-bottom: 15px; margin-bottom: 25px; }}
                .header h1 {{ margin: 0; color: #004080; }}
                .btn-print {{ background-color: #004080; color: white; padding: 12px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; font-weight: bold; display: block; margin: 0 auto 25px auto; }}
                .btn-print:hover {{ background-color: #00264d; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 25px; font-size: 14px; }}
                th {{ background-color: #f2f2f2; border-bottom: 2px solid #ddd; padding: 10px; text-align: left; }}
                td {{ padding: 10px; border-bottom: 1px solid #eee; }}
                @media print {{
                    body {{ background: white; padding: 0; }}
                    .sheet {{ border: none; box-shadow: none; padding: 0; }}
                    .btn-print {{ display: none; }}
                }}
            </style>
            <script>
                function imprimirPdf() {{
                    var nomeDoc = "{nome_arquivo_pdf}";
                    document.title = nomeDoc;
                    try {{ window.top.document.title = nomeDoc; }} catch(e) {{}}
                    window.print();
                }}
            </script>
        </head>
        <body>
            <div class="sheet">
                <button class="btn-print" onclick="imprimirPdf()">🖨️ Imprimir / Salvar em PDF</button>
                
                <div class="header">
                    {tag_logo}
                    <h1>{empresa_selecionada}</h1>
                    <h3 style="margin: 15px 0 0 0; color: #333;">{tipo_doc_salvo.upper()} DE SERVIÇOS E PRODUTOS</h3>
                </div>
                
                <div style="margin-bottom: 20px; font-size: 14px;">
                    <p style="margin: 4px 0;"><strong>Data:</strong> {orc_dados[9]}</p>
                    <p style="margin: 4px 0;"><strong>Cliente:</strong> {orc_dados[2]}</p>
                    <p style="margin: 4px 0;"><strong>CPF/CNPJ:</strong> {orc_dados[3] or 'Não informado'}</p>
                    <p style="margin: 4px 0;"><strong>Telefone:</strong> {orc_dados[4] or 'Não informado'}</p>
                    <p style="margin: 4px 0;"><strong>Endereço:</strong> {orc_dados[5] or 'Não informado'}</p>
                </div>

                <table>
                    <thead>
                        <tr>
                            <th>Descrição do Item / Serviço</th>
                            <th style="text-align: center;">Qtd</th>
                            <th style="text-align: right;">Preço Unit.</th>
                            <th style="text-align: right;">Subtotal</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for item in itens_dados:
            html_orcamento += f"""
                        <tr>
                            <td>{item[0]}</td>
                            <td style="text-align: center;">{item[1]}</td>
                            <td style="text-align: right;">{formatar_moeda(item[2])}</td>
                            <td style="text-align: right;">{formatar_moeda(item[3])}</td>
                        </tr>
            """

        html_orcamento += f"""
                    </tbody>
                </table>

                <div style="text-align: right; font-size: 16px; margin-bottom: 25px;">
                    <p style="margin: 5px 0;"><strong>Garantia:</strong> {orc_dados[6]}</p>
                    <p style="margin: 5px 0;"><strong>Validade:</strong> {orc_dados[7]}</p>
                    <p style="margin: 5px 0;"><strong>Forma de Pagamento:</strong> {orc_dados[8]}</p>
                    <h2 style="color: #004080; margin-top: 15px;">Total Geral: {formatar_moeda(orc_dados[10])}</h2>
                </div>

                <div style="border-top: 1px dashed #aaa; padding-top: 15px; text-align: center; font-size: 12px; color: #777;">
                    <p>Emitido por {orc_dados[11] if len(orc_dados) > 11 and orc_dados[11] else empresa_selecionada}.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        st.components.v1.html(html_orcamento, height=850, scrolling=True)
        st.stop()

# ---------------------------------------------------------
# TELA 2: CONSULTAR DOCUMENTOS
# ---------------------------------------------------------
elif menu == "Consultar Documentos":
    st.subheader(f"🔍 Consultar Documentos — [{empresa_selecionada}]")
    
    pesquisa = st.text_input("Pesquisar por Nome do Cliente ou CPF/CNPJ:")

    conn = conectar()
    cursor = conn.cursor()
    
    if pesquisa:
        cursor.execute("SELECT * FROM orcamentos WHERE cliente LIKE ? OR documento LIKE ? ORDER BY id DESC", (f"%{pesquisa}%", f"%{pesquisa}%"))
    else:
        cursor.execute("SELECT * FROM orcamentos ORDER BY id DESC")
        
    orcamentos = cursor.fetchall()
    conn.close()

    if not orcamentos:
        st.info("Nenhum documento encontrado nesta empresa.")
    else:
        for orc in orcamentos:
            tipo_doc_reg = orc[12] if len(orc) > 12 and orc[12] else "ORCAMENTO"
            with st.expander(f"[{tipo_doc_reg}] Nº {orc[1]} - Cliente: {orc[2]} - Data: {orc[9]} - Total: {formatar_moeda(orc[10])}"):
                st.write(f"**Tipo:** {tipo_doc_reg}")
                st.write(f"**CPF/CNPJ:** {orc[3]}")
                st.write(f"**Telefone:** {orc[4]}")
                st.write(f"**Endereço:** {orc[5]}")
                st.write(f"**Garantia:** {orc[6]} | **Validade:** {orc[7]} | **Pagamento:** {orc[8]}")
                
                criado_por_val = orc[11] if len(orc) > 11 and orc[11] else 'Não registrado'
                st.write(f"**Criado por:** {criado_por_val}")
                
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute("SELECT produto, quantidade, preco_unitario, subtotal FROM itens_orcamento WHERE numero_orcamento = ?", (orc[1],))
                itens = cursor.fetchall()
                conn.close()
                
                st.markdown("**Itens:**")
                for item in itens:
                    st.text(f"- {item[0]} | Qtd: {item[1]} | Unit: {formatar_moeda(item[2])} | Subtotal: {formatar_moeda(item[3])}")

                col_b_imp, col_b_edit, col_b_exc = st.columns([1, 1, 3])
                with col_b_imp:
                    if st.button(f"🖨️ Imprimir / PDF {orc[1]}", key=f"imp_orc_{orc[0]}"):
                        st.session_state.modo_impressao = orc[1]
                        st.rerun()

                with col_b_edit:
                    if st.button(f"✏️ Editar {orc[1]}", key=f"edit_orc_{orc[0]}"):
                        st.session_state.modo_edicao_orcamento = orc[1]
                        st.session_state.form_cliente = orc[2]
                        st.session_state.form_documento = orc[3] or ""
                        st.session_state.form_telefone = orc[4] or ""
                        st.session_state.form_endereco = orc[5] or ""
                        
                        st.session_state.carrinho = []
                        for it in itens:
                            st.session_state.carrinho.append({
                                "produto": it[0],
                                "quantidade": it[1],
                                "preco_unitario": it[2],
                                "subtotal": it[3]
                            })
                        st.success(f"Carregando orçamento {orc[1]} para edição...")
                        st.rerun()

                if st.session_state.perfil_atual == "Admin":
                    with col_b_exc:
                        if st.button(f"🗑️ Excluir Documento {orc[1]}", key=f"exc_orc_{orc[0]}"):
                            conn = conectar()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM orcamentos WHERE id = ?", (orc[0],))
                            cursor.execute("DELETE FROM itens_orcamento WHERE numero_orcamento = ?", (orc[1],))
                            conn.commit()
                            conn.close()
                            registrar_log(st.session_state.usuario_atual, "EXCLUIR DOCUMENTO", f"Documento {orc[1]} excluído")
                            st.success(f"Documento {orc[1]} excluído com sucesso!")
                            st.rerun()

# ---------------------------------------------------------
# TELA 3: GERENCIAR PRODUTOS (GLOBAL)
# ---------------------------------------------------------
elif menu == "Gerenciar Produtos":
    st.subheader("📦 Produtos (Global para todas as empresas)")
    
    if st.session_state.perfil_atual == "Admin":
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
                        conn_p = conectar_produtos()
                        cursor_p = conn_p.cursor()
                        cursor_p.execute("INSERT INTO produtos (codigo, descricao, preco, categoria) VALUES (?, ?, ?, ?)", (codigo, descricao, preco, categoria))
                        conn_p.commit()
                        conn_p.close()
                        st.cache_data.clear()
                        registrar_log(st.session_state.usuario_atual, "CRIAR PRODUTO", f"Produto {descricao} cadastrado")
                        st.success("Produto cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar: {e}")
                else:
                    st.error("Preencha a descrição e um preço válido.")
        st.markdown("---")

    st.subheader("Lista de Produtos Cadastrados")
    conn_p = conectar_produtos()
    cursor_p = conn_p.cursor()
    cursor_p.execute("SELECT id, codigo, descricao, preco, categoria FROM produtos")
    prods = cursor_p.fetchall()
    conn_p.close()

    if not prods:
        st.info("Nenhum produto cadastrado.")
    else:
        for p in prods:
            p_id, p_cod, p_desc, p_preco, p_cat = p
            with st.expander(f"[{p_cod or 'S/C'}] {p_desc} - {formatar_moeda(p_preco)} ({p_cat})"):
                with st.form(f"form_edit_prod_{p_id}"):
                    novo_cod = st.text_input("Editar Código", value=p_cod or "", key=f"cod_{p_id}")
                    novo_desc = st.text_input("Editar Descrição", value=p_desc, key=f"desc_{p_id}")
                    txt_novo_preco = st.text_input("Editar Preço (R$)", value=str(p_preco).replace('.', ','), key=f"preco_{p_id}")
                    nova_cat = st.selectbox("Editar Categoria", ["CFTV", "Informática"], index=0 if p_cat == "CFTV" else 1, key=f"cat_{p_id}")
                    
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        salvar_edicao = st.form_submit_button("💾 Salvar Alterações")
                    with col_b2:
                        excluir_prod = st.form_submit_button("🗑️ Excluir Produto") if st.session_state.perfil_atual == "Admin" else False

                    if salvar_edicao:
                        preco_convertido = converter_para_float(txt_novo_preco)
                        if novo_desc and preco_convertido > 0:
                            conn_p = conectar_produtos()
                            cursor_p = conn_p.cursor()
                            cursor_p.execute("UPDATE produtos SET codigo = ?, descricao = ?, preco = ?, categoria = ? WHERE id = ?", (novo_cod, novo_desc, preco_convertido, nova_cat, p_id))
                            conn_p.commit()
                            conn_p.close()
                            st.cache_data.clear()
                            registrar_log(st.session_state.usuario_atual, "EDITAR PRODUTO", f"Produto ID {p_id} alterado")
                            st.success("Produto atualizado com sucesso!")
                            st.rerun()
                        else:
                            st.error("Preencha uma descrição e um preço válidos.")

                    if excluir_prod:
                        conn_p = conectar_produtos()
                        cursor_p = conn_p.cursor()
                        cursor_p.execute("DELETE FROM produtos WHERE id = ?", (p_id,))
                        conn_p.commit()
                        conn_p.close()
                        st.cache_data.clear()
                        registrar_log(st.session_state.usuario_atual, "EXCLUIR PRODUTO", f"Produto {p_desc} excluído")
                        st.success("Produto excluído com sucesso!")
                        st.rerun()

# ---------------------------------------------------------
# TELA 4: GERENCIAR CLIENTES (GLOBAL)
# ---------------------------------------------------------
elif menu == "Gerenciar Clientes":
    st.subheader("👥 Clientes (Global para todas as empresas)")
    
    pesq_cliente = st.text_input("Pesquisar Cliente por Nome ou CPF/CNPJ:")

    conn_c = conectar_clientes()
    cursor_c = conn_c.cursor()
    
    if pesq_cliente:
        cursor_c.execute("SELECT id, nome, documento, telefone, endereco FROM clientes WHERE nome LIKE ? OR documento LIKE ?", (f"%{pesq_cliente}%", f"%{pesq_cliente}%"))
    else:
        cursor_c.execute("SELECT id, nome, documento, telefone, endereco FROM clientes ORDER BY nome ASC")
        
    clientes_encontrados = cursor_c.fetchall()
    conn_c.close()

    if not clientes_encontrados:
        st.info("Nenhum cliente cadastrado.")
    else:
        for cli in clientes_encontrados:
            c_id, c_nome, c_doc, c_tel, c_end = cli
            with st.expander(f"Cliente: {c_nome} | Doc: {c_doc or 'Não informado'}"):
                with st.form(f"form_edit_cli_{c_id}"):
                    novo_nome = st.text_input("Nome do Cliente", value=c_nome)
                    novo_doc = st.text_input("CPF ou CNPJ", value=c_doc or "")
                    novo_tel = st.text_input("Telefone / Celular", value=c_tel or "")
                    novo_end = st.text_input("Endereço", value=c_end or "")
                    
                    col_c1, col_c2 = st.columns(2)
                    with col_c1:
                        salvar_cli = st.form_submit_button("💾 Salvar Alterações")
                    with col_c2:
                        excluir_cli = st.form_submit_button("🗑️ Excluir Cliente")

                    if salvar_cli:
                        if not novo_nome.strip():
                            st.error("O nome do cliente não pode ficar vazio.")
                        else:
                            doc_f = formatar_documento(novo_doc.strip())
                            tel_f = formatar_telefone(novo_tel.strip())
                            conn_c = conectar_clientes()
                            cursor_c = conn_c.cursor()
                            try:
                                cursor_c.execute("""
                                    UPDATE clientes 
                                    SET nome = ?, documento = ?, telefone = ?, endereco = ? 
                                    WHERE id = ?
                                """, (novo_nome.strip(), doc_f, tel_f, novo_end.strip(), c_id))
                                conn_c.commit()
                                conn_c.close()
                                st.cache_data.clear()
                                registrar_log(st.session_state.usuario_atual, "EDITAR CLIENTE", f"Cliente {c_nome} atualizado")
                                st.success("Dados do cliente atualizados com sucesso!")
                                st.rerun()
                            except Exception as e:
                                conn_c.close()
                                st.error(f"Erro ao atualizar: {e}")

                    if excluir_cli:
                        conn_c = conectar_clientes()
                        cursor_c = conn_c.cursor()
                        cursor_c.execute("DELETE FROM clientes WHERE id = ?", (c_id,))
                        conn_c.commit()
                        conn_c.close()
                        st.cache_data.clear()
                        registrar_log(st.session_state.usuario_atual, "EXCLUIR CLIENTE", f"Cliente {c_nome} excluído")
                        st.success("Cliente excluído com sucesso!")
                        st.rerun()

# ---------------------------------------------------------
# TELA 5: GERENCIAR USUÁRIOS
# ---------------------------------------------------------
elif menu == "Gerenciar Usuários" and st.session_state.perfil_atual == "Admin":
    st.subheader(f"👤 Usuários — [{empresa_selecionada}]")
    
    with st.form("cad_usuario"):
        st.markdown("### Criar Novo Usuário")
        novo_user = st.text_input("Nome de Usuário (Login)")
        nova_senha = st.text_input("Senha", type="password")
        novo_perfil = st.selectbox("Perfil de Acesso", ["Funcionário", "Admin"])
        btn_criar_user = st.form_submit_button("Cadastrar Usuário")
        
        if btn_criar_user:
            if novo_user and nova_senha:
                try:
                    conn = conectar()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO usuarios (usuario, senha, perfil) VALUES (?, ?, ?)", (novo_user, hash_senha(nova_senha), novo_perfil))
                    conn.commit()
                    conn.close()
                    registrar_log(st.session_state.usuario_atual, "CRIAR USUÁRIO", f"Usuário {novo_user} criado")
                    st.success(f"Usuário '{novo_user}' criado com sucesso!")
                    st.rerun()
                except:
                    st.error("Erro: Este nome de usuário já existe.")
            else:
                st.error("Preencha o usuário e a senha.")

    st.markdown("---")
    st.subheader("Lista de Usuários Cadastrados")
    
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, usuario, perfil FROM usuarios")
    usuarios_cad = cursor.fetchall()
    conn.close()

    for u in usuarios_cad:
        u_id, u_nome, u_perfil = u
        with st.expander(f"Usuário: {u_nome} ({u_perfil})"):
            with st.form(f"form_edit_user_{u_id}"):
                edit_nome = st.text_input("Nome de Usuário", value=u_nome, key=f"unome_{u_id}")
                edit_senha = st.text_input("Nova Senha (deixe em branco para não alterar)", type="password", key=f"usenha_{u_id}")
                edit_perfil = st.selectbox("Perfil de Acesso", ["Funcionário", "Admin"], index=0 if u_perfil == "Funcionário" else 1, key=f"uperfil_{u_id}")
                
                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    salvar_user = st.form_submit_button("💾 Salvar Alterações")
                with col_u2:
                    excluir_user = st.form_submit_button("🗑️ Excluir Usuário") if u_nome != "admin" else False

                if salvar_user:
                    if not edit_nome:
                        st.error("O nome de usuário não pode ficar vazio.")
                    else:
                        conn = conectar()
                        cursor = conn.cursor()
                        try:
                            if edit_senha.strip():
                                senha_cripto = hash_senha(edit_senha)
                                cursor.execute("UPDATE usuarios SET usuario = ?, senha = ?, perfil = ? WHERE id = ?", (edit_nome, senha_cripto, edit_perfil, u_id))
                            else:
                                cursor.execute("UPDATE usuarios SET usuario = ?, perfil = ? WHERE id = ?", (edit_nome, edit_perfil, u_id))
                            
                            conn.commit()
                            conn.close()
                            registrar_log(st.session_state.usuario_atual, "EDITAR USUÁRIO", f"Usuário {u_nome} updated")
                            st.success("Usuário atualizado com sucesso!")
                            st.rerun()
                        except:
                            conn.close()
                            st.error("Erro: Este nome de usuário já está em uso.")

                if excluir_user:
                    conn = conectar()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM usuarios WHERE id = ?", (u_id,))
                    conn.commit()
                    conn.close()
                    registrar_log(st.session_state.usuario_atual, "EXCLUIR USUÁRIO", f"Usuário {u_nome} excluído")
                    st.success(f"Usuário {u_nome} excluído!")
                    st.rerun()

# ---------------------------------------------------------
# TELA 6: LOGS DE AUDITORIA
# ---------------------------------------------------------
elif menu == "Logs de Auditoria" and st.session_state.perfil_atual == "Admin":
    st.subheader(f"📋 Logs de Auditoria — [{empresa_selecionada}]")
    
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT usuario, acao, detalhes, data FROM logs ORDER BY id DESC")
    logs = cursor.fetchall()
    conn.close()

    if not logs:
        st.info("Nenhum registro de log encontrado nesta empresa.")
    else:
        for log in logs:
            usuario, acao, detalhes, data = log
            st.markdown(f"🕒 **{data}** | 👤 **{usuario}** | ⚡ **{acao}**: {detalhes}")
            st.divider()
