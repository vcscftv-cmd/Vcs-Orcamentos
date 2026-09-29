import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sistema de Orçamentos", layout="wide")

# --- CONEXÃO E CRIAÇÃO DO BANCO DE DADOS ---
def get_conn():
    return sqlite3.connect('sistema.db', check_same_thread=False)

def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS empresa (id INTEGER PRIMARY KEY, nome TEXT, cnpj TEXT, telefone TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY, nome TEXT, telefone TEXT, email TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS itens (id INTEGER PRIMARY KEY, nome TEXT, tipo TEXT, custo REAL, venda REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS orcamentos (
                     id INTEGER PRIMARY KEY, cliente TEXT, itens TEXT, 
                     subtotal REAL, taxa_cartao REAL, total_final REAL, 
                     custo_total REAL, lucro REAL, pagamento TEXT, 
                     parcelas INTEGER, data TEXT)''')
        conn.commit()

init_db()

def executar_query(query, params=()):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()

def carregar_tabela(tabela):
    with get_conn() as conn:
        return pd.read_sql(f"SELECT * FROM {tabela}", conn)

# --- TELA DE LOGIN ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

if not st.session_state['logado']:
    st.title("🔒 Login no Sistema")
    with st.form("login"):
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if usuario == "admin" and senha == "admin":
                st.session_state['logado'] = True
                st.rerun()
            else:
                st.error("Credenciais inválidas!")
    st.stop()

# --- MENU LATERAL ---
st.sidebar.title("Navegação")
menu = st.sidebar.radio("Módulos", ["Orçamentos", "Clientes", "Itens e Serviços", "Minha Empresa", "Sair"])

if menu == "Sair":
    st.session_state['logado'] = False
    st.rerun()

# --- MÓDULO: MINHA EMPRESA ---
if menu == "Minha Empresa":
    st.header("🏢 Dados da Empresa")
    st.write("Estas informações sairão no cabeçalho dos orçamentos.")
    
    df_empresa = carregar_tabela("empresa")
    nome_atual = df_empresa.iloc[0]['nome'] if not df_empresa.empty else ""
    cnpj_atual = df_empresa.iloc[0]['cnpj'] if not df_empresa.empty else ""
    tel_atual = df_empresa.iloc[0]['telefone'] if not df_empresa.empty else ""

    with st.form("form_empresa"):
        nome = st.text_input("Nome da Empresa", value=nome_atual)
        cnpj = st.text_input("CNPJ", value=cnpj_atual)
        telefone = st.text_input("Telefone / WhatsApp", value=tel_atual)
        
        if st.form_submit_button("Salvar Dados"):
            if not df_empresa.empty:
                executar_query("UPDATE empresa SET nome=?, cnpj=?, telefone=? WHERE id=?", 
                               (nome, cnpj, telefone, df_empresa.iloc[0]['id']))
            else:
                executar_query("INSERT INTO empresa (nome, cnpj, telefone) VALUES (?, ?, ?)", 
                               (nome, cnpj, telefone))
            st.success("Dados salvos com sucesso!")
            st.rerun()

# --- MÓDULO: CLIENTES ---
elif menu == "Clientes":
    st.header("👥 Gestão de Clientes")
    aba1, aba2 = st.tabs(["Cadastrar", "Consultar / Editar / Excluir"])
    
    with aba1:
        with st.form("novo_cliente", clear_on_submit=True):
            nome = st.text_input("Nome do Cliente")
            telefone = st.text_input("Telefone")
            email = st.text_input("E-mail")
            if st.form_submit_button("Cadastrar Cliente"):
                executar_query("INSERT INTO clientes (nome, telefone, email) VALUES (?, ?, ?)", (nome, telefone, email))
                st.success("Cliente cadastrado!")
                st.rerun()
                
    with aba2:
        df_clientes = carregar_tabela("clientes")
        if not df_clientes.empty:
            st.write("Edite os dados diretamente na tabela e clique em **Salvar Alterações**.")
            # st.data_editor permite edição direto na grade
            df_editado = st.data_editor(df_clientes, num_rows="dynamic", use_container_width=True, key="edit_cli")
            if st.button("Salvar Alterações de Clientes"):
                executar_query("DELETE FROM clientes") # Limpa a tabela atual
                for _, row in df_editado.iterrows(): # Reescreve com as edições/exclusões
                    executar_query("INSERT INTO clientes (id, nome, telefone, email) VALUES (?, ?, ?, ?)", 
                                   (row['id'], row['nome'], row['telefone'], row['email']))
                st.success("Banco de clientes atualizado!")
                st.rerun()
        else:
            st.info("Nenhum cliente cadastrado.")

# --- MÓDULO: ITENS E SERVIÇOS ---
elif menu == "Itens e Serviços":
    st.header("📦 Materiais e Serviços")
    aba1, aba2 = st.tabs(["Cadastrar", "Consultar / Editar / Excluir"])
    
    with aba1:
        with st.form("novo_item", clear_on_submit=True):
            nome = st.text_input("Descrição do Item/Serviço")
            tipo = st.selectbox("Classificação", ["Material", "Serviço", "Ambos"])
            col1, col2 = st.columns(2)
            custo = col1.number_input("Valor de Compra/Custo (R$)", min_value=0.0, format="%.2f")
            venda = col2.number_input("Valor de Venda (R$)", min_value=0.0, format="%.2f")
            
            if st.form_submit_button("Cadastrar Item"):
                executar_query("INSERT INTO itens (nome, tipo, custo, venda) VALUES (?, ?, ?, ?)", 
                               (nome, tipo, custo, venda))
                st.success("Item cadastrado!")
                st.rerun()

    with aba2:
        df_itens = carregar_tabela("itens")
        if not df_itens.empty:
            df_itens['Lucro R$'] = df_itens['venda'] - df_itens['custo']
            st.write("Edite os dados diretamente na tabela abaixo:")
            df_itens_editado = st.data_editor(df_itens, num_rows="dynamic", use_container_width=True, key="edit_itens")
            if st.button("Salvar Alterações de Itens"):
                executar_query("DELETE FROM itens")
                for _, row in df_itens_editado.iterrows():
                    executar_query("INSERT INTO itens (id, nome, tipo, custo, venda) VALUES (?, ?, ?, ?, ?)", 
                                   (row['id'], row['nome'], row['tipo'], row['custo'], row['venda']))
                st.success("Banco de itens atualizado!")
                st.rerun()
        else:
            st.info("Nenhum item cadastrado.")

# --- MÓDULO: ORÇAMENTOS ---
elif menu == "Orçamentos":
    st.header("📄 Orçamentos")
    aba1, aba2 = st.tabs(["Criar Novo Orçamento", "Consultar e Excluir"])
    
    df_clientes = carregar_tabela("clientes")
    df_itens = carregar_tabela("itens")
    
    with aba1:
        if df_clientes.empty or df_itens.empty:
            st.warning("É necessário cadastrar ao menos 1 cliente e 1 item antes de gerar orçamentos.")
        else:
            with st.form("novo_orcamento"):
                cliente = st.selectbox("Selecionar Cliente", df_clientes['nome'].tolist())
                itens_selecionados = st.multiselect("Selecionar Materiais e Serviços", df_itens['nome'].tolist())
                
                col1, col2, col3 = st.columns(3)
                pagamento = col1.selectbox("Forma de Pagamento", ["Dinheiro / Pix", "Cartão de Débito", "Cartão de Crédito"])
                
                parcelas = 1
                taxa = 0.0
                if pagamento == "Cartão de Crédito":
                    parcelas = col2.number_input("Parcelas", min_value=1, max_value=12, step=1)
                    taxa = col3.number_input("Taxa da Máquina (%)", min_value=0.0, value=5.0, step=0.1)
                elif pagamento == "Cartão de Débito":
                    taxa = col3.number_input("Taxa da Máquina (%)", min_value=0.0, value=2.0, step=0.1)

                if st.form_submit_button("Gerar Orçamento"):
                    if not itens_selecionados:
                        st.error("Selecione pelo menos um item.")
                    else:
                        subtotal = 0.0
                        custo_total = 0.0
                        
                        # Calcula custos e vendas baseados nos itens escolhidos
                        for item in itens_selecionados:
                            dados_item = df_itens[df_itens['nome'] == item].iloc[0]
                            subtotal += float(dados_item['venda'])
                            custo_total += float(dados_item['custo'])
                        
                        # Calcula acréscimo da maquininha
                        valor_taxa = subtotal * (taxa / 100)
                        total_final = subtotal + valor_taxa
                        lucro = total_final - custo_total - valor_taxa # Lucro limpo descontando a taxa
                        
                        str_itens = ", ".join(itens_selecionados)
                        data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
                        
                        executar_query('''INSERT INTO orcamentos 
                                        (cliente, itens, subtotal, taxa_cartao, total_final, custo_total, lucro, pagamento, parcelas, data) 
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                                       (cliente, str_itens, subtotal, valor_taxa, total_final, custo_total, lucro, pagamento, parcelas, data_atual))
                        
                        st.success("Orçamento salvo com sucesso!")
                        
                        # --- RESUMO NA TELA ---
                        st.markdown("### Resumo do Orçamento Gerado")
                        st.write(f"**Cliente:** {cliente}")
                        st.write(f"**Itens inclusos:** {str_itens}")
                        st.write(f"**Pagamento:** {pagamento} em {parcelas}x (Taxa aplicada: {taxa}%)")
                        
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Valor para o Cliente", f"R$ {total_final:.2f}")
                        c2.metric("Custo dos Materiais", f"R$ {custo_total:.2f}")
                        c3.metric("Seu Lucro Real", f"R$ {lucro:.2f}")

    with aba2:
        df_orcamentos = carregar_tabela("orcamentos")
        if not df_orcamentos.empty:
            st.dataframe(df_orcamentos, use_container_width=True)
            
            st.write("---")
            st.write("**Excluir Orçamento**")
            id_excluir = st.selectbox("Selecione o ID do orçamento para excluir:", df_orcamentos['id'].tolist())
            if st.button("Excluir Orçamento Selecionado"):
                executar_query("DELETE FROM orcamentos WHERE id=?", (id_excluir,))
                st.success("Orçamento excluído!")
                st.rerun()
        else:
            st.info("Nenhum orçamento gerado ainda.")
