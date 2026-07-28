import streamlit as st
import sqlite3
import datetime

# ------------------------------------------------
# 1. CONFIGURAÇÃO DO FUSO HORÁRIO (BRASIL: UTC-3)
# ------------------------------------------------
fuso_br = datetime.timezone(datetime.timedelta(hours=-3))

# ------------------------------------------------
# 2. CONEXÃO E CRIAÇÃO DO BANCO DE DADOS
# ------------------------------------------------
def conectar():
    conn = sqlite3.connect('sistema.db')
    cursor = conn.cursor()
    # Criar tabela de logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            acao TEXT,
            detalhes TEXT,
            data TEXT
        )
    ''')
    # Criar tabela de orçamentos/propostas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orcamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            valor REAL,
            data TEXT
        )
    ''')
    conn.commit()
    return conn

# ------------------------------------------------
# 3. FUNÇÃO DE REGISTRAR LOG (COM A HORA CORRIGIDA)
# ------------------------------------------------
def registrar_log(usuario, acao, detalhes):
    conn = conectar()
    cursor = conn.cursor()
    
    # Pega a hora certa forçando o fuso do Brasil
    data_hora = datetime.datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M:%S")
    
    cursor.execute("INSERT INTO logs (usuario, acao, detalhes, data) VALUES (?, ?, ?, ?)", (usuario, acao, detalhes, data_hora))
    conn.commit()
    conn.close()

# ------------------------------------------------
# 4. INTERFACE DO SISTEMA (FRONT-END)
# ------------------------------------------------
st.title("⚙️ Sistema de Orçamentos")

usuario_logado = "Admin" # Simulação do usuário ativo

with st.form("form_orcamento"):
    st.subheader("Novo / Editar Orçamento")
    
    cliente = st.text_input("Nome do Cliente")
    valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
    
    editando_num = st.checkbox("Estou editando um orçamento existente")
    
    salvar = st.form_submit_button("Salvar")

# ------------------------------------------------
# 5. LÓGICA DE SALVAR (COM A HORA CORRIGIDA)
# ------------------------------------------------
if salvar:
    if not cliente:
        st.error("Preencha o nome do cliente!")
    else:
        conn = conectar()
        cursor = conn.cursor()
        
        # Pega a data atual com o fuso corrigido para salvar no orçamento
        data_atual = datetime.datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M")
        
        if editando_num:
            # Lógica se estiver editando
            st.success(f"Orçamento de {cliente} atualizado com sucesso! (Hora registrada: {data_atual})")
            registrar_log(usuario_logado, "Edição", f"Orçamento editado: {cliente}")
        else:
            # Lógica se for um orçamento novo
            cursor.execute("INSERT INTO orcamentos (cliente, valor, data) VALUES (?, ?, ?)", (cliente, valor, data_atual))
            st.success(f"Novo orçamento para {cliente} salvo com sucesso! (Hora registrada: {data_atual})")
            registrar_log(usuario_logado, "Criação", f"Orçamento criado: {cliente}")
            
        conn.commit()
        conn.close()

# ------------------------------------------------
# 6. EXIBIÇÃO PARA VOCÊ TESTAR SE O HORÁRIO BATEU
# ------------------------------------------------
st.divider()
st.subheader("📋 Últimos Logs Registrados (Verifique a Hora)")

conn = conectar()
logs = conn.execute("SELECT data, usuario, acao, detalhes FROM logs ORDER BY id DESC LIMIT 5").fetchall()
conn.close()

if logs:
    for log in logs:
        st.write(f"**[{log[0]}]** | {log[1]} | {log[2]} | {log[3]}")
else:
    st.info("Nenhum log registrado ainda.")
