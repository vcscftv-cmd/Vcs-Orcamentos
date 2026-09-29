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
        """CREATE TABLE IF NOT EXISTS itens (id INTEGER PRIMARY KEY, nome TEXT, categoria TEXT)"""
    )
    c.execute("""CREATE TABLE IF NOT EXISTS orcamentos (
                     id INTEGER PRIMARY KEY, cliente TEXT, itens TEXT, 
                     servico_desc TEXT, valor_servico REAL,
                     subtotal REAL, taxa_cartao REAL, total_final REAL, 
                     pagamento TEXT, parcelas INTEGER, validade TEXT, data TEXT)""")

    try:
      c.execute("ALTER TABLE orcamentos ADD COLUMN servico_desc TEXT")
      c.execute(
          "ALTER TABLE orcamentos ADD COLUMN valor_servico REAL DEFAULT 0"
      )
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


# --- GERADOR DE PDF ---
def gerar_pdf(
    empresa_df,
    cliente,
    itens_formatados,
    servico_desc,
    valor_servico,
    pagamento,
    parcelas,
    total,
    validade_data,
):
  pdf = FPDF()
  pdf.add_page()

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

  pdf.set_font("helvetica", "B", 12)
  pdf.cell(0, 8, txt=f"Cliente: {cliente}", ln=True)

  pdf.set_font("helvetica", size=11)
  pdf.multi_cell(0, 7, txt=f"Itens do Orçamento:\n{itens_formatados}")

  if servico_desc:
    pdf.ln(2)
    pdf.multi_cell(
        0,
        7,
        txt=(
            f"Serviço Adicional: {servico_desc} (R$"
            f" {valor_servico:.2f})"
        ),
    )

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


# --- LOGIN ---
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

# --- MENU LATERAL ---
if os.path.exists("logo.png"):
  st.sidebar.image("logo.png", use_container_width=True)

st.sidebar.title("Navegação")
menu = st.sidebar.radio(
    "Módulos",
    ["Orçamentos", "Clientes", "Cadastro de Itens", "Minha Empresa", "Sair"],
)

if menu == "Sair":
  st.session_state["logado"] = False
  st.rerun()

# --- MINHA EMPRESA ---
if menu == "Minha Empresa":
  st.header("🏢 Dados da Empresa")
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
      st.success("Dados salvos!")
      st.rerun()

# --- CLIENTES ---
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
        st.success("Clientes atualizados!")
        st.rerun()

# --- CADASTRO DE ITENS ---
elif menu == "Cadastro de Itens":
  st.header("📦 Cadastro de Produtos / Equipamentos")
  aba1, aba2 = st.tabs(["Cadastrar Item", "Consultar / Editar"])

  with aba1:
    with st.form("novo_item", clear_on_submit=True):
      nome = st.text_input("Descrição do Item (Ex: Notebook Dell, Câmera Bullet)")
      categoria = st.selectbox(
          "Categoria do Item", ["CFTV", "Informática", "Outros"]
      )

      if st.form_submit_button("Cadastrar Item"):
        if nome:
          executar_query(
              "INSERT INTO itens (nome, categoria) VALUES (?, ?)",
              (nome, categoria),
          )
          st.success("Item cadastrado com sucesso!")
          st.rerun()
        else:
          st.error("Informe a descrição do item.")

  with aba2:
    df_itens = carregar_tabela("itens")
    if not df_itens.empty:
      df_editado = st.data_editor(
          df_itens, num_rows="dynamic", use_container_width=True
      )
      if st.button("Salvar Alterações em Itens"):
        executar_query("DELETE FROM itens")
        for _, row in df_editado.iterrows():
          executar_query(
              "INSERT INTO itens (id, nome, categoria) VALUES (?, ?, ?)",
              (row["id"], row["nome"], row["categoria"]),
          )
        st.success("Lista de itens atualizada!")
        st.rerun()
    else:
      st.info("Nenhum item cadastrado.")

# --- ORÇAMENTOS ---
elif menu == "Orçamentos":
  st.header("📄 Gestão de Orçamentos")
  aba1, aba2 = st.tabs(["Criar Novo Orçamento", "Histórico"])

  df_clientes = carregar_tabela("clientes")
  df_itens = carregar_tabela("itens")
  df_empresa = carregar_tabela("empresa")

  with aba1:
    # Verificação ajustada para garantir que ambas as listas contenham dados válidos
    tem_clientes = not df_clientes.empty and "nome" in df_clientes.columns and len(df_clientes["nome"].dropna()) > 0
    tem_itens = not df_itens.empty and "nome" in df_itens.columns and len(df_itens["nome"].dropna()) > 0

    if not tem_clientes or not tem_itens:
      if not tem_clientes:
        st.warning("Nenhum cliente cadastrado. Acesse o módulo 'Clientes' para cadastrar.")
      if not tem_itens:
        st.warning("Nenhum item cadastrado. Acesse o módulo 'Cadastro de Itens' para cadastrar ao menos 1 produto/equipamento.")
    else:
      cliente = st.selectbox("Cliente", df_clientes["nome"].dropna().tolist())

      st.subheader("1. Seleção de Equipamentos / Produtos")
      itens_selecionados = st.multiselect(
          "Selecione os Itens", df_itens["nome"].dropna().tolist()
      )

      precos_itens = {}
      if itens_selecionados:
        st.write("Informe o valor de venda para cada item selecionado:")
        for item in itens_selecionados:
          precos_itens[item] = st.number_input(
              f"Valor de Venda - {item} (R$)",
              min_value=0.0,
              format="%.2f",
              key=f"val_{item}",
          )

      st.subheader("2. Serviço Adicional")
      incluir_servico = st.checkbox("Deseja incluir mão de obra ou serviço?")

      servico_desc = ""
      valor_servico = 0.0

      if incluir_servico:
        col_s1, col_s2 = st.columns([2, 1])
        servico_desc = col_s1.text_input(
            "Descrição do Serviço",
            placeholder="Ex: Instalação e configuração de CFTV",
        )
        valor_servico = col_s2.number_input(
            "Valor do Serviço (R$)", min_value=0.0, format="%.2f"
        )

      st.subheader("3. Condições de Pagamento")
      with st.form("form_finalizar"):
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
          if not itens_selecionados and not (
              incluir_servico and valor_servico > 0
          ):
            st.error("Selecione ao menos um item ou informe um serviço.")
          else:
            subtotal_itens = sum(precos_itens.values())
            subtotal_geral = subtotal_itens + valor_servico

            valor_taxa = subtotal_geral * (taxa / 100)
            total_final = subtotal_geral + valor_taxa

            linhas_itens = [
                f"- {item}: R$ {preco:.2f}"
                for item, preco in precos_itens.items()
            ]
            str_itens_formatado = "\n".join(linhas_itens)
            data_str = validade.strftime("%d/%m/%Y")

            executar_query(
                """INSERT INTO orcamentos 
                                (cliente, itens, servico_desc, valor_servico, subtotal, taxa_cartao, total_final, pagamento, parcelas, validade, data) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cliente,
                    str_itens_formatado,
                    servico_desc,
                    valor_servico,
                    subtotal_geral,
                    valor_taxa,
                    total_final,
                    pagamento,
                    parcelas,
                    data_str,
                    datetime.now().strftime("%d/%m/%Y"),
                ),
            )

            st.success("Orçamento gerado com sucesso!")

            # WhatsApp
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

            resumo_whats = (
                f"*Orçamento - {empresa_nome}*\n\nOlá,"
                f" {cliente}!\n\n*Produtos:*\n{str_itens_formatado}\n"
            )
            if incluir_servico and servico_desc:
              resumo_whats += (
                  f"\n*Serviço:* {servico_desc} (R$ {valor_servico:.2f})\n"
              )
            resumo_whats += (
                f"\n💳 *Pagamento:* {pagamento} em {parcelas}x\n💰 *Total:* R$"
                f" {total_final:.2f}\n⏳ *Válido até:* {data_str}"
            )

            msg_codificada = urllib.parse.quote(resumo_whats)
            link_whats = (
                f"https://wa.me/55{telefone_limpo}?text={msg_codificada}"
                if len(telefone_limpo) >= 10
                else f"https://api.whatsapp.com/send?text={msg_codificada}"
            )

            pdf_bytes = gerar_pdf(
                df_empresa,
                cliente,
                str_itens_formatado,
                servico_desc,
                valor_servico,
                pagamento,
                parcelas,
                total_final,
                validade,
            )

            st.markdown(
                f"### Valor Final para o Cliente: R$ {total_final:.2f}"
            )
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
        st.success("Excluído!")
        st.rerun()
    else:
      st.info("Nenhum orçamento gerado.")
