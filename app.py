import os
import sqlite3
import urllib.parse
from datetime import datetime
from fpdf import FPDF
import pandas as pd
import streamlit as st

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Sistema de Orçamentos e Propostas",
    layout="wide",
    page_icon="📄",
)

DB_NAME = "banco_vcs.db"


# --- CONEXÃO E CRIAÇÃO DO BANCO DE DADOS ---
def get_conn():
  return sqlite3.connect(
      DB_NAME, check_same_thread=False, timeout=10, isolation_level=None
  )


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
        """CREATE TABLE IF NOT EXISTS itens (id INTEGER PRIMARY KEY, nome TEXT, categoria TEXT, valor_compra REAL DEFAULT 0, valor_venda REAL DEFAULT 0)"""
    )
    c.execute("""CREATE TABLE IF NOT EXISTS orcamentos (
                     id INTEGER PRIMARY KEY, tipo_doc TEXT DEFAULT 'Orçamento', cliente TEXT, itens TEXT, 
                     servico_desc TEXT, valor_servico REAL DEFAULT 0,
                     subtotal REAL DEFAULT 0, taxa_cartao REAL DEFAULT 0, total_final REAL DEFAULT 0, 
                     custo_total REAL DEFAULT 0, lucro_real REAL DEFAULT 0, status TEXT DEFAULT 'Pendente',
                     pagamento TEXT, parcelas INTEGER, validade TEXT, data TEXT)""")

    colunas_novas = [
        ("orcamentos", "tipo_doc TEXT DEFAULT 'Orçamento'"),
        ("clientes", "nome TEXT"),
        ("clientes", "telefone TEXT"),
        ("clientes", "email TEXT"),
        ("itens", "valor_compra REAL DEFAULT 0"),
        ("itens", "valor_venda REAL DEFAULT 0"),
        ("orcamentos", "servico_desc TEXT"),
        ("orcamentos", "valor_servico REAL DEFAULT 0"),
        ("orcamentos", "custo_total REAL DEFAULT 0"),
        ("orcamentos", "lucro_real REAL DEFAULT 0"),
        ("orcamentos", "status TEXT DEFAULT 'Pendente'"),
    ]
    for tabela, col_def in colunas_novas:
      try:
        c.execute(f"ALTER TABLE {tabela} ADD COLUMN {col_def}")
      except sqlite3.OperationalError:
        pass


init_db()


def executar_query(query, params=()):
  with get_conn() as conn:
    c = conn.cursor()
    c.execute(query, params)


def carregar_tabela(tabela):
  with get_conn() as conn:
    return pd.read_sql(f"SELECT * FROM {tabela}", conn)


# --- GERADOR DE PDF ---
def gerar_pdf(
    tipo_doc,
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
      else "Nossa Empresa"
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

  pdf.set_font("helvetica", "B", 14)
  pdf.cell(
      0,
      10,
      txt=f"{tipo_doc.upper()} COMERCIAL",
      ln=True,
      align="C",
  )
  pdf.ln(4)

  pdf.set_font("helvetica", "B", 11)
  pdf.cell(0, 7, txt=f"Cliente / Solicitante: {cliente}", ln=True)
  pdf.ln(3)

  if itens_formatados:
    pdf.set_font("helvetica", "B", 11)
    titulo_itens = (
        "Equipamentos e Materiais:"
        if tipo_doc == "Proposta de Serviço"
        else "Itens do Orçamento:"
    )
    pdf.cell(0, 7, txt=titulo_itens, ln=True)
    pdf.set_font("helvetica", size=10)
    pdf.multi_cell(0, 6, txt=itens_formatados)
    pdf.ln(2)

  if servico_desc:
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 7, txt="Escopo do Serviço / Mão de Obra:", ln=True)
    pdf.set_font("helvetica", size=10)
    pdf.multi_cell(
        0, 6, txt=f"- {servico_desc} (R$ {valor_servico:.2f})"
    )
    pdf.ln(2)

  pdf.ln(4)
  pdf.set_font("helvetica", size=10)
  pdf.cell(
      0, 6, txt=f"Forma de Pagamento: {pagamento} em {parcelas}x", ln=True
  )
  pdf.cell(
      0,
      6,
      txt=f"Validade da Proposta: {validade_data.strftime('%d/%m/%Y')}",
      ln=True,
  )

  pdf.ln(6)
  pdf.set_font("helvetica", "B", 14)
  pdf.cell(0, 10, txt=f"INVESTIMENTO TOTAL: R$ {total:.2f}", ln=True)

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
    [
        "Propostas e Orçamentos",
        "Relatório de Lucro",
        "Clientes",
        "Cadastro de Itens",
        "Minha Empresa",
        "Sair",
    ],
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
      st.success("Dados salvos com sucesso!")
      st.rerun()

# --- CLIENTES ---
elif menu == "Clientes":
  st.header("👥 Gestão de Clientes")
  aba1, aba2 = st.tabs(["Cadastrar Cliente", "Consultar / Editar / Excluir"])

  with aba1:
    with st.form("novo_cliente", clear_on_submit=True):
      nome = st.text_input("Nome do Cliente")
      telefone = st.text_input("Telefone (ex: 11999999999)")
      email = st.text_input("E-mail")
      if st.form_submit_button("Cadastrar Cliente"):
        if nome:
          executar_query(
              "INSERT INTO clientes (nome, telefone, email) VALUES (?, ?, ?)",
              (nome, telefone, email),
          )
          st.success("Cliente cadastrado com sucesso!")
          st.rerun()
        else:
          st.error("Por favor, preencha o nome do cliente.")

  with aba2:
    df_clientes = carregar_tabela("clientes")
    if not df_clientes.empty:
      st.write("### ✏️ Edição de Clientes (Altere diretamente na tabela)")
      df_editado = st.data_editor(
          df_clientes,
          num_rows="dynamic",
          use_container_width=True,
          key="editor_clientes",
      )

      col_save, col_del = st.columns(2)

      with col_save:
        if st.button("💾 Salvar Alterações na Tabela"):
          for _, row in df_editado.iterrows():
            if pd.notna(row.get("id")) and str(row.get("id")).strip() != "":
              # Atualiza cliente existente
              executar_query(
                  "UPDATE clientes SET nome=?, telefone=?, email=? WHERE id=?",
                  (
                      row.get("nome"),
                      row.get("telefone", ""),
                      row.get("email", ""),
                      row.get("id"),
                  ),
              )
            elif pd.notna(row.get("nome")) and str(row.get("nome")).strip() != "":
              # Insere novo cliente inserido via tabela
              executar_query(
                  "INSERT INTO clientes (nome, telefone, email) VALUES (?, ?,"
                  " ?)",
                  (
                      row.get("nome"),
                      row.get("telefone", ""),
                      row.get("email", ""),
                  ),
              )
          st.success("Alterações salvas com segurança!")
          st.rerun()

      with col_del:
        st.write("### 🗑️ Excluir Clientes")
        clientes_para_deletar = st.multiselect(
            "Selecione os clientes para remover:",
            df_clientes["nome"].tolist(),
            key="del_mult_clientes",
        )
        if st.button("Confirmar Exclusão Selecionada", type="primary"):
          if clientes_para_deletar:
            for cli in clientes_para_deletar:
              executar_query("DELETE FROM clientes WHERE nome=?", (cli,))
            st.success("Clientes excluídos com sucesso!")
            st.rerun()
    else:
      st.info("Nenhum cliente cadastrado.")

# --- CADASTRO DE ITENS ---
elif menu == "Cadastro de Itens":
  st.header("📦 Cadastro de Produtos / Equipamentos")
  aba1, aba2 = st.tabs(["Cadastrar Item", "Consultar / Editar / Excluir"])

  with aba1:
    with st.form("novo_item", clear_on_submit=True):
      nome = st.text_input("Descrição do Item (Ex: Notebook Dell, Câmera Bullet)")
      categoria = st.selectbox(
          "Categoria do Item", ["CFTV", "Informática", "Outros"]
      )

      col_c, col_v = st.columns(2)
      valor_compra = col_c.number_input(
          "Valor de Custo / Revenda (R$)", min_value=0.0, format="%.2f"
      )
      valor_venda = col_v.number_input(
          "Preço Final de Venda Padrão (R$)", min_value=0.0, format="%.2f"
      )

      if st.form_submit_button("Cadastrar Item"):
        if nome:
          executar_query(
              "INSERT INTO itens (nome, categoria, valor_compra, valor_venda)"
              " VALUES (?, ?, ?, ?)",
              (nome, categoria, valor_compra, valor_venda),
          )
          st.success("Item cadastrado com sucesso!")
          st.rerun()
        else:
          st.error("Informe a descrição do item.")

  with aba2:
    df_itens = carregar_tabela("itens")
    if not df_itens.empty:
      if "valor_compra" not in df_itens.columns:
        df_itens["valor_compra"] = 0.0
      if "valor_venda" not in df_itens.columns:
        df_itens["valor_venda"] = 0.0

      df_itens["valor_compra"] = df_itens["valor_compra"].fillna(0.0)
      df_itens["valor_venda"] = df_itens["valor_venda"].fillna(0.0)
      df_itens["Lucro Estimado (R$)"] = (
          df_itens["valor_venda"] - df_itens["valor_compra"]
      )

      st.write("### ✏️ Edição de Itens (Altere diretamente na tabela)")
      df_editado = st.data_editor(
          df_itens,
          num_rows="dynamic",
          use_container_width=True,
          key="editor_itens",
      )

      col_sav_item, col_del_item = st.columns(2)

      with col_sav_item:
        if st.button("💾 Salvar Alterações nos Itens"):
          for _, row in df_editado.iterrows():
            if pd.notna(row.get("id")) and str(row.get("id")).strip() != "":
              # Atualiza item existente
              executar_query(
                  "UPDATE itens SET nome=?, categoria=?, valor_compra=?,"
                  " valor_venda=? WHERE id=?",
                  (
                      row.get("nome"),
                      row.get("categoria", "Outros"),
                      row.get("valor_compra", 0.0),
                      row.get("valor_venda", 0.0),
                      row.get("id"),
                  ),
              )
            elif pd.notna(row.get("nome")) and str(row.get("nome")).strip() != "":
              # Insere novo item adicionado na tabela
              executar_query(
                  "INSERT INTO itens (nome, categoria, valor_compra,"
                  " valor_venda) VALUES (?, ?, ?, ?)",
                  (
                      row.get("nome"),
                      row.get("categoria", "Outros"),
                      row.get("valor_compra", 0.0),
                      row.get("valor_venda", 0.0),
                  ),
              )
          st.success("Lista de itens atualizada com segurança!")
          st.rerun()

      with col_del_item:
        st.write("### 🗑️ Excluir Itens")
        itens_para_deletar = st.multiselect(
            "Selecione os itens para remover:",
            df_itens["nome"].tolist(),
            key="del_mult_itens",
        )
        if st.button("Excluir Itens Selecionados", type="primary"):
          if itens_para_deletar:
            for item_nome in itens_para_deletar:
              executar_query("DELETE FROM itens WHERE nome=?", (item_nome,))
            st.success("Itens removidos!")
            st.rerun()
    else:
      st.info("Nenhum item cadastrado.")

# --- ORÇAMENTOS E PROPOSTAS ---
elif menu == "Propostas e Orçamentos":
  st.header("📄 Gestão de Propostas e Orçamentos")
  aba1, aba2 = st.tabs(["Criar Nova Proposta", "Histórico e Status"])

  df_clientes = carregar_tabela("clientes")
  df_itens = carregar_tabela("itens")
  df_empresa = carregar_tabela("empresa")

  with aba1:
    tem_clientes = (
        not df_clientes.empty
        and "nome" in df_clientes.columns
        and len(df_clientes["nome"].dropna()) > 0
    )
    tem_itens = (
        not df_itens.empty
        and "nome" in df_itens.columns
        and len(df_itens["nome"].dropna()) > 0
    )

    if not tem_clientes or not tem_itens:
      if not tem_clientes:
        st.warning("Nenhum cliente cadastrado.")
      if not tem_itens:
        st.warning("Nenhum item cadastrado.")
    else:
      col_t1, col_t2 = st.columns([1, 2])
      tipo_doc = col_t1.selectbox(
          "Tipo de Documento",
          ["Orçamento", "Proposta de Serviço"],
      )
      cliente = col_t2.selectbox(
          "Cliente", df_clientes["nome"].dropna().tolist()
      )

      st.subheader("1. Seleção de Equipamentos / Produtos")
      itens_selecionados = st.multiselect(
          "Selecione os Itens", df_itens["nome"].dropna().tolist()
      )

      precos_venda = {}
      custos_compra = {}

      if itens_selecionados:
        st.write("Ajuste os valores se necessário:")
        for item in itens_selecionados:
          dados_item = df_itens[df_itens["nome"] == item].iloc[0]
          v_compra_padrao = float(dados_item.get("valor_compra", 0.0))
          v_venda_padrao = float(dados_item.get("valor_venda", 0.0))

          col_v1, col_v2 = st.columns(2)
          precos_venda[item] = col_v1.number_input(
              f"Preço Venda - {item} (R$)",
              value=v_venda_padrao,
              min_value=0.0,
              format="%.2f",
              key=f"venda_{item}",
          )
          custos_compra[item] = col_v2.number_input(
              f"Custo Compra - {item} (R$)",
              value=v_compra_padrao,
              min_value=0.0,
              format="%.2f",
              key=f"custo_{item}",
          )

      st.subheader("2. Mão de Obra e Serviço")
      incluir_servico = st.checkbox(
          "Deseja incluir descrição de mão de obra / serviço?",
          value=(tipo_doc == "Proposta de Serviço"),
      )

      servico_desc = ""
      valor_servico = 0.0

      if incluir_servico:
        col_s1, col_s2 = st.columns([2, 1])
        servico_desc = col_s1.text_input(
            "Descrição do Serviço / Escopo",
            placeholder="Ex: Instalação, passagem de cabos e configuração de CFTV",
        )
        valor_servico = col_s2.number_input(
            "Valor da Mão de Obra (R$)", min_value=0.0, format="%.2f"
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

        if st.form_submit_button(f"Gerar {tipo_doc}"):
          if not itens_selecionados and not (
              incluir_servico and valor_servico > 0
          ):
            st.error("Selecione ao menos um item ou informe um serviço.")
          else:
            subtotal_itens = sum(precos_venda.values())
            custo_itens = sum(custos_compra.values())

            subtotal_geral = subtotal_itens + valor_servico
            valor_taxa = subtotal_geral * (taxa / 100)
            total_final = subtotal_geral + valor_taxa

            lucro_real = total_final - custo_itens - valor_taxa

            linhas_itens = [
                f"- {item}: R$ {preco:.2f}"
                for item, preco in precos_venda.items()
            ]
            str_itens_formatado = "\n".join(linhas_itens)
            data_str = validade.strftime("%d/%m/%Y")

            executar_query(
                """INSERT INTO orcamentos 
                                (tipo_doc, cliente, itens, servico_desc, valor_servico, subtotal, taxa_cartao, total_final, custo_total, lucro_real, status, pagamento, parcelas, validade, data) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tipo_doc,
                    cliente,
                    str_itens_formatado,
                    servico_desc,
                    valor_servico,
                    subtotal_geral,
                    valor_taxa,
                    total_final,
                    custo_itens,
                    lucro_real,
                    "Pendente",
                    pagamento,
                    parcelas,
                    data_str,
                    datetime.now().strftime("%d/%m/%Y"),
                ),
            )

            st.success(f"{tipo_doc} gerado com sucesso!")

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
                f"*{tipo_doc} - {empresa_nome}*\n\nOlá, {cliente}!\n\n"
            )
            if str_itens_formatado:
              resumo_whats += f"*Itens/Produtos:*\n{str_itens_formatado}\n\n"
            if incluir_servico and servico_desc:
              resumo_whats += (
                  f"*Serviço:* {servico_desc} (R$ {valor_servico:.2f})\n\n"
              )
            resumo_whats += (
                f"💳 *Pagamento:* {pagamento} em {parcelas}x\n💰 *Total:* R$"
                f" {total_final:.2f}\n⏳ *Válido até:* {data_str}"
            )

            msg_codificada = urllib.parse.quote(resumo_whats)
            link_whats = (
                f"https://wa.me/55{telefone_limpo}?text={msg_codificada}"
                if len(telefone_limpo) >= 10
                else f"https://api.whatsapp.com/send?text={msg_codificada}"
            )

            pdf_bytes = gerar_pdf(
                tipo_doc,
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
                  label=f"📄 Baixar PDF do {tipo_doc}",
                  data=pdf_bytes,
                  file_name=f"{tipo_doc}_{cliente}.pdf",
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
      col_st, col_del = st.columns(2)

      with col_st:
        st.subheader("Alterar Status")
        orcamento_id = st.selectbox(
            "Selecione o ID", df_orcamentos["id"].tolist()
        )
        novo_status = st.selectbox(
            "Status da Proposta", ["Aprovado", "Pendente", "Recusado"]
        )
        if st.button("Atualizar Status"):
          executar_query(
              "UPDATE orcamentos SET status=? WHERE id=?",
              (novo_status, orcamento_id),
          )
          st.success(f"Status do Documento #{orcamento_id} atualizado!")
          st.rerun()

      with col_del:
        st.subheader("🗑️ Excluir Documentos")
        docs_para_deletar = st.multiselect(
            "Selecione os IDs para remover:",
            df_orcamentos["id"].tolist(),
            key="del_mult_orcamentos",
        )
        if st.button("Excluir Documentos Selecionados", type="primary"):
          if docs_para_deletar:
            for doc_id in docs_para_deletar:
              executar_query(
                  "DELETE FROM orcamentos WHERE id=?", (doc_id,)
              )
            st.success("Documentos removidos!")
            st.rerun()

      st.write("---")
      st.dataframe(df_orcamentos, use_container_width=True)
    else:
      st.info("Nenhum registro encontrado.")

# --- RELATÓRIO DE LUCRO ---
elif menu == "Relatório de Lucro":
  st.header("📊 Relatório Financeiro & Base de Lucro")
  df_orcamentos = carregar_tabela("orcamentos")

  if df_orcamentos.empty:
    st.info("Nenhum documento gerado para criar relatórios.")
  else:
    df_aprovados = df_orcamentos[df_orcamentos["status"] == "Aprovado"]

    total_faturado = (
        df_aprovados["total_final"].sum() if not df_aprovados.empty else 0.0
    )
    total_custo = (
        df_aprovados["custo_total"].sum() if not df_aprovados.empty else 0.0
    )
    total_taxas = (
        df_aprovados["taxa_cartao"].sum() if not df_aprovados.empty else 0.0
    )
    lucro_liquido = (
        df_aprovados["lucro_real"].sum() if not df_aprovados.empty else 0.0
    )

    st.subheader("Resumo de Vendas Aprovadas")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Faturamento Total", f"R$ {total_faturado:.2f}")
    m2.metric("Custo dos Materiais", f"R$ {total_custo:.2f}")
    m3.metric("Taxas de Maquininha", f"R$ {total_taxas:.2f}")
    m4.metric("Lucro Líquido Real", f"R$ {lucro_liquido:.2f}")

    st.write("---")
    st.subheader("Documentos Aprovados")
    if not df_aprovados.empty:
      st.dataframe(
          df_aprovados[[
              "id",
              "tipo_doc",
              "cliente",
              "total_final",
              "custo_total",
              "taxa_cartao",
              "lucro_real",
              "data",
          ]],
          use_container_width=True,
      )
    else:
      st.warning(
          "Você ainda não possui propostas ou orçamentos com o status"
          " 'Aprovado'."
      )
