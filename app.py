import streamlit as st
import sqlite3
import datetime
import requests
import hashlib
import time
import base64
import os

# Configuração da página para ocupar a largura total
st.set_page_config(page_title="VCS Informática - Orçamentos", page_icon="💻", layout="wide")

# ⚙️ CONFIGURAÇÃO DA LOGOMARCA
ARQUIVO_LOGO = "logo.png" 

def obter_logo_base64():
    if os.path.exists(ARQUIVO_LOGO):
        with open(ARQUIVO_LOGO, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return None

def hash_senha(senha):
    return hashlib.sha256(str(senha).encode()).hexdigest()

def iniciar_banco():
    conn = sqlite3.connect("banco_vcs.db")
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
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT UNIQUE,
        descricao TEXT NOT NULL,
        preco REAL NOT NULL,
        categoria TEXT NOT NULL
    )
    """)
    
    # Garante a tabela de clientes com UNIQUE no nome para evitar erros de conflito
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL,
        documento TEXT,
        telefone TEXT,
        endereco TEXT
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
        criado_por TEXT
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

    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        senha_padrao = hash_senha("samu@2707")
        cursor.execute("INSERT INTO usuarios (usuario, senha, perfil) VALUES (?, ?, ?)", ("admin", senha_padrao, "Admin"))
        conn.commit()
        
    conn.close()

iniciar_banco()

def registrar_log(usuario, acao, detalhes):
    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    data_hora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
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

def gerar_numero_orcamento():
    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM orcamentos")
    qtd = cursor.fetchone()[0]
    conn.close()
    
    proximo_id = qtd + 1
    return f"Orcamento_{proximo_id:03d}"

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

if st.session_state.autenticado:
    tempo_atual = time.time()
    inatividade = tempo_atual - st.session_state.ultimo_acesso
    if inatividade > TEMPO_INATIVIDADE_MAX:
        registrar_log(st.session_state.usuario_atual, "LOGOUT AUTOMÁTICO", "Deslogado por inatividade (> 10 min)")
        st.session_state.autenticado = False
        st.session_state.usuario_atual = ""
        st.session_state.perfil_atual = ""
        st.warning("⚠️ Sessão expirada por inatividade (mais de 10 minutos sem uso). Faça login novamente.")
        st.rerun()
    else:
        st.session_state.ultimo_acesso = time.time()

if not st.session_state.autenticado:
    st.title("🔐 VCS Informática - Login")
    with st.form("form_login"):
        user_input = st.text_input("Usuário")
        senha_input = st.text_input("Senha", type="password")
        btn_login = st.form_submit_button("Entrar")
        
        if btn_login:
            conn = sqlite3.connect("banco_vcs.db")
            cursor = conn.cursor()
            cursor.execute("SELECT perfil FROM usuarios WHERE usuario = ? AND senha = ?", (user_input, hash_senha(senha_input)))
            res = cursor.fetchone()
            conn.close()
            
            if res:
                st.session_state.autenticado = True
                st.session_state.usuario_atual = user_input
                st.session_state.perfil_atual = res[0]
                st.session_state.ultimo_acesso = time.time()
                registrar_log(user_input, "LOGIN", "Usuário entrou no sistema")
                st.success("Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos!")
    
    st.stop()

st.sidebar.title(f"🛠️ VCS Informática")
st.sidebar.write(f"👤 Logado como: **{st.session_state.usuario_atual}** ({st.session_state.perfil_atual})")

opcoes_menu = ["Criar Orçamento", "Consultar Orçamentos", "Gerenciar Produtos", "Gerenciar Clientes"]

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
# TELA 1: CRIAR ORÇAMENTO
# ---------------------------------------------------------
if menu == "Criar Orçamento":
    st.subheader("📝 Novo Orçamento")
    
    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    cursor.execute("SELECT descricao, preco, categoria FROM produtos")
    produtos_db = cursor.fetchall()
    
    cursor.execute("SELECT nome, documento, telefone, endereco FROM clientes ORDER BY nome ASC")
    clientes_cadastrados = cursor.fetchall()
    conn.close()

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
                
                conn = sqlite3.connect("banco_vcs.db")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO clientes (nome, documento, telefone, endereco)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(nome) DO UPDATE SET
                        documento = excluded.documento,
                        telefone = excluded.telefone,
                        endereco = excluded.endereco
                """, (cliente.strip(), doc_formatado, tel_formatado, endereco.strip()))
                conn.commit()
                conn.close()
                
                st.success("Dados do cliente salvos e fixados com sucesso!")
                st.rerun()
            else:
                st.error("Preencha o nome do cliente.")

    st.markdown("---")
    
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
    
    st.subheader("⚠️ Defeito Relatado")
    incluir_defeito = st.radio("Deseja relatar algum defeito no equipamento?", ["Não", "Sim"], horizontal=True, key="radio_defeito")
    
    possui_defeito = "Não"
    desc_defeito = ""

    if incluir_defeito == "Sim":
        possui_defeito = "Sim"
        desc_defeito = st.text_input("Descrição do Defeito", placeholder="Ex: Equipamento não liga, sem imagem na câmera...")

    st.markdown("---")
    
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

                conn = sqlite3.connect("banco_vcs.db")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO orcamentos (numero_orcamento, cliente, documento, telefone, endereco, garantia, validade, pagamento, data, total, criado_por)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (num_orc, cliente, documento, telefone, endereco, garantia, validade, pagamento, data_atual, total_geral, st.session_state.usuario_atual))
                
                for item in st.session_state.carrinho:
                    cursor.execute("""
                        INSERT INTO itens_orcamento (numero_orcamento, produto, quantidade, preco_unitario, subtotal)
                        VALUES (?, ?, ?, ?, ?)
                    """, (num_orc, item["produto"], item["quantidade"], item["preco_unitario"], item["subtotal"]))
                
                if srv_instalacao == "Sim" and valor_instalacao > 0:
                    nome_servico_final = desc_servico if desc_servico.strip() else "Serviço de Instalação"
                    cursor.execute("""
                        INSERT INTO itens_orcamento (numero_orcamento, produto, quantidade, preco_unitario, subtotal)
                        VALUES (?, ?, ?, ?, ?)
                    """, (num_orc, nome_servico_final, 1, valor_instalacao, valor_instalacao))

                conn.commit()
                conn.close()
                
                registrar_log(st.session_state.usuario_atual, "CRIAR ORÇAMENTO", f"Orçamento {num_orc} criado para o cliente {cliente}")
                st.session_state.carrinho = []
                st.session_state.ultimo_orcamento_imprimir = num_orc
                st.success(f"Orçamento nº {num_orc} salvo com sucesso no banco de dados!")
                st.rerun()

    if st.session_state.ultimo_orcamento_imprimir:
        st.markdown("---")
        st.success(f"🖨️ O último orçamento gerado (**{st.session_state.ultimo_orcamento_imprimir}**) está pronto para impressão ou salvamento em PDF!")
        if st.button("📄 Abrir Página de Impressão / PDF do Orçamento Recente"):
            st.session_state.modo_impressao = st.session_state.ultimo_orcamento_imprimir
            st.rerun()

# ---------------------------------------------------------
# TELA DE IMPRESSÃO / PDF (Modo dedicado)
# ---------------------------------------------------------
if "modo_impressao" in st.session_state and st.session_state.modo_impressao:
    num_alvo = st.session_state.modo_impressao
    
    conn = sqlite3.connect("banco_vcs.db")
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

        html_orcamento = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Orçamento {orc_dados[1]}</title>
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
        </head>
        <body>
            <div class="sheet">
                <button class="btn-print" onclick="window.print()">🖨️ Imprimir / Salvar em PDF</button>
                
                <div class="header">
                    {tag_logo}
                    <h1>VCS Informática</h1>
                    <p style="margin: 5px 0 0 0; font-size: 14px; color: #555;">Manutenção, Redes, CFTV e Suprimentos</p>
                    <h3 style="margin: 15px 0 0 0; color: #333;">ORÇAMENTO DE SERVIÇOS E PRODUTOS</h3>
                    <p style="margin: 5px 0; font-weight: bold; color: #d9534f;">Nº: {orc_dados[1]}</p>
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
                            <th>Descrição do Item / Produto</th>
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
                    <p style="margin: 5px 0;"><strong>Validade da Proposta:</strong> {orc_dados[7]}</p>
                    <p style="margin: 5px 0;"><strong>Forma de Pagamento:</strong> {orc_dados[8]}</p>
                    <h2 style="color: #004080; margin-top: 15px;">Total Geral: {formatar_moeda(orc_dados[10])}</h2>
                </div>

                <div style="border-top: 1px dashed #aaa; padding-top: 15px; text-align: center; font-size: 12px; color: #777;">
                    <p>Obrigado pela preferência! Emitido por {orc_dados[11] if len(orc_dados) > 11 and orc_dados[11] else 'VCS Informática'}.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        st.components.v1.html(html_orcamento, height=850, scrolling=True)
        st.stop()

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
            with st.expander(f"{orc[1]} - Cliente: {orc[2]} - Data: {orc[9]} - Total: {formatar_moeda(orc[10])}"):
                st.write(f"**CPF/CNPJ:** {orc[3]}")
                st.write(f"**Telefone:** {orc[4]}")
                st.write(f"**Endereço:** {orc[5]}")
                st.write(f"**Garantia:** {orc[6]} | **Validade:** {orc[7]} | **Pagamento:** {orc[8]}")
                st.write(f"**Criado por:** {orc[11] if len(orc) > 11 and orc[11] else 'Não registrado'}")
                
                conn = sqlite3.connect("banco_vcs.db")
                cursor = conn.cursor()
                cursor.execute("SELECT produto, quantidade, preco_unitario, subtotal FROM itens_orcamento WHERE numero_orcamento = ?", (orc[1],))
                itens = cursor.fetchall()
                conn.close()
                
                st.markdown("**Itens:**")
                for item in itens:
                    st.text(f"- {item[0]} | Qtd: {item[1]} | Unit: {formatar_moeda(item[2])} | Subtotal: {formatar_moeda(item[3])}")

                col_b_imp, col_b_exc = st.columns([1, 4])
                with col_b_imp:
                    if st.button(f"🖨️ Imprimir / PDF {orc[1]}", key=f"imp_orc_{orc[0]}"):
                        st.session_state.modo_impressao = orc[1]
                        st.rerun()

                if st.session_state.perfil_atual == "Admin":
                    with col_b_exc:
                        if st.button(f"🗑️ Excluir Orçamento {orc[1]}", key=f"exc_orc_{orc[0]}"):
                            conn = sqlite3.connect("banco_vcs.db")
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM orcamentos WHERE id = ?", (orc[0],))
                            cursor.execute("DELETE FROM itens_orcamento WHERE numero_orcamento = ?", (orc[1],))
                            conn.commit()
                            conn.close()
                            registrar_log(st.session_state.usuario_atual, "EXCLUIR ORÇAMENTO", f"Orçamento {orc[1]} excluído")
                            st.success(f"Orçamento {orc[1]} excluído com sucesso!")
                            st.rerun()

# ---------------------------------------------------------
# TELA 3: GERENCIAR PRODUTOS
# ---------------------------------------------------------
elif menu == "Gerenciar Produtos":
    st.subheader("📦 Gerenciamento de Produtos")
    
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
                        conn = sqlite3.connect("banco_vcs.db")
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO produtos (codigo, descricao, preco, categoria) VALUES (?, ?, ?, ?)", (codigo, descricao, preco, categoria))
                        conn.commit()
                        conn.close()
                        registrar_log(st.session_state.usuario_atual, "CRIAR PRODUTO", f"Produto {descricao} cadastrado")
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
                            conn = sqlite3.connect("banco_vcs.db")
                            cursor = conn.cursor()
                            cursor.execute("UPDATE produtos SET descricao = ?, preco = ?, categoria = ? WHERE id = ?", (novo_desc, preco_convertido, nova_cat, p_id))
                            conn.commit()
                            conn.close()
                            registrar_log(st.session_state.usuario_atual, "EDITAR PRODUTO", f"Produto ID {p_id} alterado para {novo_desc} - {preco_convertido}")
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
                        registrar_log(st.session_state.usuario_atual, "EXCLUIR PRODUTO", f"Produto {p_desc} excluído")
                        st.success("Produto excluído com sucesso!")
                        st.rerun()

# ---------------------------------------------------------
# TELA 4: GERENCIAR CLIENTES
# ---------------------------------------------------------
elif menu == "Gerenciar Clientes":
    st.subheader("👥 Pesquisa e Gerenciamento de Clientes")
    
    pesq_cliente = st.text_input("Pesquisar Cliente por Nome ou CPF/CNPJ:")

    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    
    if pesq_cliente:
        cursor.execute("SELECT id, nome, documento, telefone, endereco FROM clientes WHERE nome LIKE ? OR documento LIKE ?", (f"%{pesq_cliente}%", f"%{pesq_cliente}%"))
    else:
        cursor.execute("SELECT id, nome, documento, telefone, endereco FROM clientes ORDER BY nome ASC")
        
    clientes_encontrados = cursor.fetchall()
    conn.close()

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
                            conn = sqlite3.connect("banco_vcs.db")
                            cursor = conn.cursor()
                            try:
                                cursor.execute("""
                                    UPDATE clientes 
                                    SET nome = ?, documento = ?, telefone = ?, endereco = ? 
                                    WHERE id = ?
                                """, (novo_nome.strip(), doc_f, tel_f, novo_end.strip(), c_id))
                                conn.commit()
                                conn.close()
                                registrar_log(st.session_state.usuario_atual, "EDITAR CLIENTE", f"Cliente {c_nome} atualizado para {novo_nome}")
                                st.success("Dados do cliente atualizados com sucesso!")
                                st.rerun()
                            except Exception as e:
                                conn.close()
                                st.error(f"Erro ao atualizar (nome já existe?): {e}")

                    if excluir_cli:
                        conn = sqlite3.connect("banco_vcs.db")
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM clientes WHERE id = ?", (c_id,))
                        conn.commit()
                        conn.close()
                        registrar_log(st.session_state.usuario_atual, "EXCLUIR CLIENTE", f"Cliente {c_nome} excluído")
                        st.success("Cliente excluído com sucesso!")
                        st.rerun()

# ---------------------------------------------------------
# TELA 5: GERENCIAR USUÁRIOS
# ---------------------------------------------------------
elif menu == "Gerenciar Usuários" and st.session_state.perfil_atual == "Admin":
    st.subheader("👤 Gerenciamento de Usuários do Sistema")
    
    with st.form("cad_usuario"):
        st.markdown("### Criar Novo Usuário")
        novo_user = st.text_input("Nome de Usuário (Login)")
        nova_senha = st.text_input("Senha", type="password")
        novo_perfil = st.selectbox("Perfil de Acesso", ["Funcionário", "Admin"])
        btn_criar_user = st.form_submit_button("Cadastrar Usuário")
        
        if btn_criar_user:
            if novo_user and nova_senha:
                try:
                    conn = sqlite3.connect("banco_vcs.db")
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO usuarios (usuario, senha, perfil) VALUES (?, ?, ?)", (novo_user, hash_senha(nova_senha), novo_perfil))
                    conn.commit()
                    conn.close()
                    registrar_log(st.session_state.usuario_atual, "CRIAR USUÁRIO", f"Usuário {novo_user} criado com perfil {novo_perfil}")
                    st.success(f"Usuário '{novo_user}' criado com sucesso!")
                    st.rerun()
                except:
                    st.error("Erro: Este nome de usuário já existe.")
            else:
                st.error("Preencha o usuário e a senha.")

    st.markdown("---")
    st.subheader("Lista e Edição de Usuários Cadastrados")
    
    conn = sqlite3.connect("banco_vcs.db")
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
                        conn = sqlite3.connect("banco_vcs.db")
                        cursor = conn.cursor()
                        try:
                            if edit_senha.strip():
                                senha_cripto = hash_senha(edit_senha)
                                cursor.execute("UPDATE usuarios SET usuario = ?, senha = ?, perfil = ? WHERE id = ?", (edit_nome, senha_cripto, edit_perfil, u_id))
                            else:
                                cursor.execute("UPDATE usuarios SET usuario = ?, perfil = ? WHERE id = ?", (edit_nome, edit_perfil, u_id))
                            
                            conn.commit()
                            conn.close()
                            registrar_log(st.session_state.usuario_atual, "EDITAR USUÁRIO", f"Usuário {u_nome} atualizado")
                            st.success("Usuário atualizado com sucesso!")
                            st.rerun()
                        except:
                            conn.close()
                            st.error("Erro: Este nome de usuário já está em uso por outro cadastro.")

                if excluir_user:
                    conn = sqlite3.connect("banco_vcs.db")
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
    st.subheader("📋 Logs de Auditoria (Histórico de Alterações)")
    
    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    cursor.execute("SELECT usuario, acao, detalhes, data FROM logs ORDER BY id DESC")
    logs = cursor.fetchall()
    conn.close()

    if not logs:
        st.info("Nenhum registro de log encontrado.")
    else:
        for log in logs:
            usuario, acao, detalhes, data = log
            st.markdown(f"🕒 **{data}** | 👤 **{usuario}** | ⚡ **{acao}**: {detalhes}")
            st.divider()