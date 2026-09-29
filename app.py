import os
import sqlite3
import urllib.parse
from datetime import datetime
from fpdf import FPDF
import pandas as pd
import streamlit as st

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Sistema de Orçamentos", layout="wide", page_icon="📄"
)

DB_NAME = "banco_vcs.db"


# --- CONEXÃO E CRIAÇÃO DO BANCO DE DADOS ---
def get_conn():
  return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
  with get_conn() as conn:
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS empresa (id INTEGER PRIMARY KEY, nome TEXT, cnpj TEXT, telefone TEXT)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY, nome TEXT, telefone TEXT, email TEXT)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS itens (id INTEGER PRIMARY KEY, nome TEXT, tipo TEXT, custo REAL, venda REAL)"""
    )
    c.execute("""CREATE TABLE IF NOT EXISTS orcamentos (
                 id INTEGER PRIMARY KEY, cliente TEXT, itens TEXT, 
                 subtotal REAL, taxa_cartao REAL, total_final REAL, 
                 custo_total REAL, lucro REAL, pagamento TEXT, 
                 parcelas INTEGER, validade TEXT, data TEXT)""")

    try:
      c.execute("ALTER TABLE orcamentos ADD COLUMN validade TEXT")
    except sqlite3.OperationalError:
      pass
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


# --- FUNÇÃO GERADORA DE PDF COM LOGO ---
def gerar_pdf(
    empresa_df, cliente, itens, pagamento, parcelas, total, validade_data
):
  pdf = FPDF()
  pdf.add_page()

  # Se existir a logo.png na pasta, adiciona no topo do PDF
  if os.path.exists("logo.png"):
    pdf.image("logo.png", x=10, y=8, w=30)
    pdf.set_y(10)

  nome_emp = (
      empresa_df["nome"].iloc[0]
      if not empresa_df.empty and pd.notna(empresa_df["nome"].iloc[0])
      else "Orçamento"
  )
  cnpj = (
      empresa_df["cnpj"].iloc[0]
      if not empresa_df.empty and pd.notna(empresa_df["cnpj"].iloc[0])
      else ""
  )
  telefone = (
      empresa_df["telefone"].iloc[0]
      if not empresa_df.empty and pd.notna(empresa_df["telefone"].iloc[0])
      else ""
  )

  pdf.set_font("helvetica", "B", 16)
  pdf.cell(0, 10, txt=nome_emp, ln=True, align="C")

  pdf.set_font("helvetica", size=10)
  if cnpj or telefone:
    pdf.cell(0, 5, txt=f"CNPJ: {cnpj} | Tel: {telefone}", ln=True, align="C")

  pdf.line(
      10,
      42 if os.path.exists("logo.png") else 30,
      200,
      42 if os.path.exists("logo.png") else 30,
  )
  pdf.ln(12)

  # Dados do Orçamento
  pdf.set_font("helvetica", "B", 12)
  pdf.cell(0, 8, txt=f"Cliente: {cliente}", ln=True)

  pdf.set_font("helvetica", size=11)
  pdf.multi_cell(0, 7, txt=f"Itens / Serviços inclusos:\n{itens}")
  pdf.ln(4)

  pdf.cell(
      0, 7, txt=f"Forma de Pagamento: {pagamento} em {parcelas}x", ln=True
  )
  pdf.cell(
      0,
      7,
      txt=f"Validade da Proposta: {validade_data.strftime('%d/%m/%Y')}",
      ln=True,
  )

  pdf.ln(6)
  pdf.set_font("helvetica", "B", 14)
  pdf.cell(0, 10, txt=f"VALOR TOTAL: R$ {total:.2f}", ln=True)

  return bytes(pdf.output())


# --- TELA DE LOGIN ---
if "logado" not in st.session_state:
  st.session_state["logado"] = False

if not st.session_state["logado"]:
  col_a, col_b, col_c = st.columns([1, 2, 1])
  with col_b:
    if os.path.exists("logo.png"):
      st.image("logo.png", width=180)
    st.title("🔒 Login no Sistema")
    with st.form("login"):
      usuario = st.text_input("Usuário")
      senha = st.text_input("Senha", type="password")
      if st.form_submit_button("Entrar"):
        if usuario == "admin" and senha == "samu@2707":
          st.session_state["logado"] = True
          st.rerun()
        else:
          st.error("Credenciais inválidas!")
  st.stop()

# --- BARRA LATERAL (MENU & LOGO) ---
if os.path.exists("logo.png"):
  st.sidebar.image("logo.png", use_container_width=True)

st.sidebar.title("Navegação")
menu = st.sidebar.radio(
    "Módulos",
    ["Orçamentos", "Clientes", "Itens e Serviços", "Minha Empresa", "Sair"],
)

if menu == "Sair":
  st.session_state["logado"] = False
  st.rerun()

# --- MÓDULO: MINHA EMPRESA ---
if menu == "Minha Empresa":
  st.header("🏢 Dados da Empresa")
  st.write("Estes dados aparecerão no cabeçalho dos orçamentos e do PDF.")

  df_empresa = carregar_tabela("empresa")
  nome_atual = df_empresa.iloc[0]["nome"] if not df_empresa.empty else ""
  cnpj_atual = df_empresa.iloc[0]["cnpj"] if not df_empresa.empty else ""
  tel_atual = df_empresa.iloc[0]["telefone"] if not df_empresa.empty else ""

  with st.form("form_empresa"):
    nome = st.text_input("Nome da Empresa", value=nome_atual)
    cnpj = st.text_input("CNPJ", value=cnpj_atual)
    telefone = st.text_input("Telefone / WhatsApp", value=tel_atual)
    if st.form_submit_button("Salvar Dados"):
      if not df_empresa.empty:
        executar_query(
            "UPDATE empresa SET nome=?, cnpj=?, telefone=? WHERE id=?",
            (nome, cnpj, telefone, df_empresa.iloc[0]["id"]),
        )
      else:
        executar_query(
            "INSERT INTO empresa (nome, cnpj, telefone) VALUES (?, ?, ?)",
            (nome, cnpj, telefone),
        )
      st.success("Dados salvos com sucesso!")
      st.rerun()

# --- MÓDULO: CLIENTES ---
elif menu == "Clientes":
  st.header("👥 Gestão de Clientes")
  aba1, aba2 = st.tabs(["Cadastrar", "Consultar / Editar / Excluir"])

  with aba1:
    with st.form("novo_cliente", clear_on_submit=True):
      nome = st.text_input("Nome do Cliente")
      telefone = st.text_input("Telefone (ex: 11999999999)")
      email = st.text_input("E-mail")
      if st.form_submit_button("Cadastrar Cliente"):
        executar_query(
            "INSERT INTO clientes (nome, telefone, email) VALUES (?, ?, ?)",
            (nome, telefone, email),
        )
        st.success("Cliente cadastrado!")
        st.rerun()

  with aba2:
    df_clientes = carregar_tabela("clientes")
    if not df_clientes.empty:
      df_editado = st.data_editor(
          df_clientes, num_rows="dynamic", use_container_width=True
      )
      if st.button("Salvar Alterações em Clientes"):
        executar_query("DELETE FROM clientes")
        for _, row in df_editado.iterrows():
          executar_query(
              "INSERT INTO clientes (id, nome, telefone, email) VALUES (?,"
              " ?, ?, ?)",
              (row["id"], row["nome"], row["telefone"], row["email"]),
          )
        st.success("Tabela de clientes atualizada!")
        st.rerun()
    else:
      st.info("Nenhum cliente cadastrado.")

# --- MÓDULO: ITENS E SERVIÇOS ---
elif menu == "Itens e Serviços":
  st.header("📦 Materiais e Serviços")
  aba1, aba2 = st.tabs(["Cadastrar", "Consultar / Editar"])

  with aba1:
    with st.form("novo_item", clear_on_submit=True):
      nome = st.text_input("Descrição do Item/Serviço")
      tipo = st.selectbox("Classificação", ["Material", "Serviço", "Ambos"])
      c1, c2 = st.columns(2)
      custo = c1.number_input(
          "Valor de Custo/Compra (R$)", min_value=0.0, format="%.2f"
      )
      venda = c2.number_input(
          "Valor de Venda (R$)", min_value=0.0, format="%.2f"
      )
      if st.form_submit_button("Cadastrar"):
        executar_query(
            "INSERT INTO itens (nome, tipo, custo, venda) VALUES (?, ?, ?,"
            " ?)",
            (nome, tipo, custo, venda),
        )
        st.success("Item cadastrado!")
        st.rerun()

  with aba2:
    df_itens = carregar_tabela("itens")
    if not df_itens.empty:
      df_itens["Lucro R$"] = df_itens["venda"] - df_itens["custo"]
      df_itens_editado = st.data_editor(
          df_itens, num_rows="dynamic", use_container_width=True
      )
      if st.button("Salvar Alterações em Itens"):
        executar_query("DELETE FROM itens")
        for _, row in df_itens_editado.iterrows():
          executar_query(
              "INSERT INTO itens (id, nome, tipo, custo, venda) VALUES (?, ?,"
              " ?, ?, ?)",
              (
                  row["id"],
                  row["nome"],
                  row["tipo"],
                  row["custo"],
                  row["venda"],
              ),
          )
        st.success("Tabela de itens atualizada!")
        st.rerun()
    else:
      st.info("Nenhum item cadastrado.")

# --- MÓDULO: ORÇAMENTOS ---
elif menu == "Orçamentos":
  st.header("📄 Gestão de Orçamentos")
  aba1, aba2 = st.tabs(["Criar Novo Orçamento", "Histórico"])

  df_clientes = carregar_tabela("clientes")
  df_itens = carregar_tabela("itens")
  df_empresa = carregar_tabela("empresa")

  with aba1:
    if df_clientes.empty or df_itens.empty:
      st.warning("Cadastre ao menos 1 cliente e 1 item antes de prosseguir.")
    else:
      with st.form("novo_orcamento"):
        cliente = st.selectbox("Cliente", df_clientes["nome"].tolist())
        itens_selecionados = st.multiselect(
            "Itens/Serviços", df_itens["nome"].tolist()
        )

        col1, col2, col3, col4 = st.columns(4)
        pagamento = col1.selectbox(
            "Forma de Pagamento",
            ["Dinheiro / Pix", "Cartão de Débito", "Cartão de Crédito"],
        )
        parcelas = (
            col2.number_input("Parcelas", min_value=1, max_value=12, step=1)
            if pagamento == "Cartão de Crédito"
            else 1
        )
        taxa = col3.number_input(
            "Taxa Maquininha (%)",
            value=(
                5.0
                if pagamento == "Cartão de Crédito"
                else 2.0 if pagamento == "Cartão de Débito" else 0.0
            ),
            step=0.1,
        )
        validade = col4.date_input("Validade da Proposta")

        if st.form_submit_button("Gerar Orçamento"):
          if not itens_selecionados:
            st.error("Selecione ao menos um item.")
          else:
            subtotal = sum(
                float(df_itens[df_itens["nome"] == i].iloc[0]["venda"])
                for i in itens_selecionados
            )
            custo = sum(
                float(df_itens[df_itens["nome"] == i].iloc[0]["custo"])
                for i in itens_selecionados
            )

            valor_taxa = subtotal * (taxa / 100)
            total = subtotal + valor_taxa
            lucro = total - custo - valor_taxa
            str_itens = "\n- ".join(itens_selecionados)
            str_itens = "- " + str_itens
            data_str = validade.strftime("%d/%m/%Y")

            executar_query(
                """INSERT INTO orcamentos 
                                (cliente, itens, subtotal, taxa_cartao, total_final, custo_total, lucro, pagamento, parcelas, validade, data) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cliente,
                    str_itens,
                    subtotal,
                    valor_taxa,
                    total,
                    custo,
                    lucro,
                    pagamento,
                    parcelas,
                    data_str,
                    datetime.now().strftime("%d/%m/%Y"),
                ),
            )

            st.success("Orçamento gerado e salvo!")

            # Preparações para Envio de WhatsApp e PDF
            telefone_cliente = df_clientes[
                df_clientes["nome"] == cliente
            ].iloc[0]["telefone"]
            telefone_limpo = "".join(
                filter(str.isdigit, str(telefone_cliente))
            )

            empresa_nome = (
                df_empresa.iloc[0]["nome"]
                if not df_empresa.empty
                else "Nossa Empresa"
            )
            msg_whats = (
                f"*Orçamento - {empresa_nome}*\n\nOlá,"
                f" {cliente}! Segue o resumo do seu"
                f" orçamento:\n\n*Itens:*\n{str_itens}\n\n💳 *Pagamento:*"
                f" {pagamento} em {parcelas}x\n💰 *Total:* R$"
                f" {total:.2f}\n⏳ *Válido até:* {data_str}\n\nQualquer dúvida,"
                " estou à disposição!"
            )
            msg_codificada = urllib.parse.quote(msg_whats)

            if len(telefone_limpo) >= 10:
              link_whats = (
                  f"https://wa.me/55{telefone_limpo}?text={msg_codificada}"
              )
            else:
              link_whats = (
                  f"https://api.whatsapp.com/send?text={msg_codificada}"
              )

            pdf_bytes = gerar_pdf(
                df_empresa,
                cliente,
                str_itens,
                pagamento,
                parcelas,
                total,
                validade,
            )

            # Exibição de Métricas e Botões
            st.markdown(f"### Valor Final para o Cliente: R$ {total:.2f}")
            c1, c2 = st.columns(2)

            with c1:
              st.download_button(
                  label="📄 Baixar PDF do Orçamento",
                  data=pdf_bytes,
                  file_name=f"Orcamento_{cliente}.pdf",
                  mime="application/pdf",
              )
            with c2:
              st.markdown(
                  f'<a href="{link_whats}" target="_blank" style="display:'
                  " inline-block; padding: 0.5em 1em; color: white;"
                  " background-color: #25D366; border-radius: 5px;"
                  ' text-decoration: none; font-weight: bold;">💬 Enviar por'
                  " WhatsApp</a>",
                  unsafe_allow_html=True,
              )

  with aba2:
    df_orcamentos = carregar_tabela("orcamentos")
    if not df_orcamentos.empty:
      st.dataframe(df_orcamentos, use_container_width=True)
      st.write("---")
      id_excluir = st.selectbox(
          "ID para excluir:", df_orcamentos["id"].tolist()
      )
      if st.button("Excluir Orçamento"):
        executar_query(
            "DELETE FROM orcamentos WHERE id=?", (id_excluir,)
        )
        st.success("Orçamento excluído!")
        st.rerun()
    else:
      st.info("Nenhum orçamento cadastrado.")
