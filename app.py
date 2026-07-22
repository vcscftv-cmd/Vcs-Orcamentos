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

# ==========================================
# 1. BANCO DE DADOS E MIGRAÇÃO
# ==========================================
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
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            documento TEXT UNIQUE,
            telefone TEXT,
            endereco TEXT
        )
    """)
    
    cursor.execute("PRAGMA table_info(orcamentos)")
    colunas_orc = [col[1] for col in cursor.fetchall()]
    if "servico_desc" not in colunas_orc:
        cursor.execute("ALTER TABLE orcamentos ADD COLUMN servico_desc TEXT")
    if "servico_valor" not in colunas_orc:
        cursor.execute("ALTER TABLE orcamentos ADD COLUMN servico_valor REAL")
    if "defeito" not in colunas_orc:
        cursor.execute("ALTER TABLE orcamentos ADD COLUMN defeito TEXT")

    # Produtos iniciais padrão
    produtos_iniciais = [
        ("CAM1120D", "CAMERA IR DOME HDCVI LITE 20M 2.8MM VHL 1120 D INTELBRAS", 170.00, "CFTV"),
        ("CAM1120B", "CAMERA IR HDCVI LITE 20M 2.8MM VHL 1120 B G2 INTELBRAS", 175.00, "CFTV"),
        ("DVR01", "MHDX 1108 DVR 8 CANAIS MULTI HD INTELBRAS", 550.00, "CFTV"),
        ("CAB01", "CABO COAXIAL CFTV 4MM + ALIMENTACAO 80% MALHA (100M)", 150.00, "CFTV"),
        ("COOLINT", "COOLER INTEL E97379-003 P/ PROCESSA 1151/1150/1155/1156", 19.99, "Informática"),
        ("SSDKING", "SSD KINGSPEC 240GB SATA 2.5", 234.16, "Informática"),
        ("MON215", "MONITOR LED WIDE NEWDRIVE (21.5\" / VGA / HDMI / FULL HD)", 220.00, "Informática"),
        ("SERV01", "Serviço de Formatação e Backup", 120.00, "Serviços"),
        ("SERV02", "Instalação de Sistema de Câmeras (CFTV)", 250.00, "Serviços")
    ]
    
    for codigo, desc, preco, cat in produtos_iniciais:
        cursor.execute("""
            INSERT OR IGNORE INTO produtos (codigo, descricao, preco, categoria) 
            VALUES (?, ?, ?, ?)
        """, (codigo, desc, preco, cat))
    
    conn.commit()
    conn.close()

iniciar_banco()

def obter_numero_orcamento():
    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM orcamentos")
    qtd = cursor.fetchone()[0] + 1
    conn.close()
    ano = datetime.datetime.now().year
    return f"ORÇ-{qtd:03d}/{ano}"

def salvar_cliente_banco(nome, documento, telefone, endereco):
    if not nome:
        return
    conn = sqlite3.connect("banco_vcs.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO clientes (nome, documento, telefone, endereco)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(documento) DO UPDATE SET
        nome=excluded.nome, telefone=excluded.telefone, endereco=excluded.endereco
    """, (nome, documento, telefone, endereco))
    conn.commit()
    conn.close()

# ==========================================
# 2. GERADOR DE PDF
# ==========================================
def gerar_pdf(numero_orc, dados_cliente, itens, desconto, total):
    nome_pasta = "OS"
    os.makedirs(nome_pasta, exist_ok=True)
    
    data_atual = datetime.date.today().strftime('%Y-%m-%d')
    orc_limpo = numero_orc.replace('/', '-')
    nome_arquivo_pdf = f"Orcamento_{orc_limpo}_{data_atual}.pdf"
    caminho_completo = os.path.join(nome_pasta, nome_arquivo_pdf)
    
    doc = SimpleDocTemplate(caminho_completo, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elementos = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1a365d'), alignment=1)
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#4a5568'), alignment=1)
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#2b2b2b'))
    
    elementos.append(Paragraph("<b>VCS INFORMÁTICA — Soluções em Tecnologia</b>", title_style))
    elementos.append(Paragraph("Proposta Comercial de Equipamentos e Serviços", sub_style))
    elementos.append(Spacer(1, 10))
    
    dados_cab = [
        [Paragraph(f"<b>Orçamento Nº:</b> {numero_orc}", cell_style), Paragraph(f"<b>Data:</b> {datetime.date.today().strftime('%d/%m/%Y')}", cell_style)],
        [Paragraph(f"<b>Cliente/Empresa:</b> {dados_cliente['nome']}", cell_style), Paragraph(f"<b>CPF/CNPJ:</b> {dados_cliente['documento']}", cell_style)],
        [Paragraph(f"<b>Telefone:</b> {dados_cliente['telefone']}", cell_style), Paragraph(f"<b>Validade:</b> {dados_cliente['validade']}", cell_style)],
        [Paragraph(f"<b>Endereço:</b> {dados_cliente['endereco']}", cell_style), Paragraph(f"<b>Garantia:</b> {dados_cliente['garantia']}", cell_style)]
    ]
    t_cab = Table(dados_cab, colWidths=[280, 260])
    t_cab.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f7fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elementos.append(t_cab)
    elementos.append(Spacer(1, 8))
    
    if dados_cliente['defeito']:
        dados_def = [[Paragraph(f"<b>Descrição do Defeito / Relato:</b> {dados_cliente['defeito']}", cell_style)]]
        t_def = Table(dados_def, colWidths=[540])
        t_def.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fffbeb')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#fcd34d')),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        elementos.append(t_def)
        elementos.append(Spacer(1, 8))
    
    dados_itens = [["Item", "Descrição do Produto / Serviço", "Qtd", "Valor Unit.", "Total"]]
    for i, item in enumerate(itens, 1):
        dados_itens.append([str(i), item['desc'], str(item['qtd']), f"R$ {item['preco']:.2f}", f"R$ {item['total']:.2f}"])
    
    if desconto > 0:
        dados_itens.append(["", "Desconto Aplicado (Condição Especial)", "", "", f"- R$ {desconto:.2f}"])
        
    dados_itens.append(["", "", "", "TOTAL GERAL:", f"R$ {total:.2f}"])
    
    t_itens = Table(dados_itens, colWidths=[30, 310, 40, 80, 80])
    t_itens.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2b6cb0')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (2,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-2), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#edf2f7')),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 5),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    elementos.append(t_itens)
    elementos.append(Spacer(1, 10))
    
    dados_cond = [[Paragraph(f"<b>Condições de Pagamento:</b> {dados_cliente['pagamento']}", cell_style)]]
    t_cond = Table(dados_cond, colWidths=[540])
    t_cond.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#edf2f7')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elementos.append(t_cond)
    
    doc.build(elementos)
    return caminho_completo

# ==========================================
# 3. INTERFACE WEB COM STREAMLIT
# ==========================================
st.title("💻 VCS Informática - Gerador de Orçamentos")

if "carrinho" not in st.session_state:
    st.session_state.carrinho = []

# --- DADOS DO CLIENTE ---
st.subheader("1. Dados do Cliente")
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    cli_nome = st.text_input("Nome do Cliente / Empresa")
with col2:
    cli_doc = st.text_input("CPF ou CNPJ")
with col3:
    cli_tel = st.text_input("Telefone / WhatsApp")

cli_end = st.text_input("Endereço Completo")

# --- PERGUNTA: ADICIONAR SERVIÇO? ---
st.markdown("---")
st.subheader("2. Serviços e Pontos Opcionais")
tem_servico_opcao = st.radio("Deseja adicionar serviço ou pontos de rede/câmera?", ["Não", "Sim"], horizontal=True)

serv_desc, serv_val, qtd_p, val_p, desconto, defeito = "", 0.0, 0, 0.0, 0.0, ""

if tem_servico_opcao == "Sim":
    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
        serv_desc = st.text_input("Descrição do Serviço / Mão de Obra", value="Instalação Geral")
    with col_s2:
        serv_val = st.number_input("Valor Serviço (R$)", min_value=0.0, value=0.0, step=10.0)
        
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        qtd_p = st.number_input("Qtd Pontos (Rede/Câm.)", min_value=0, value=0, step=1)
    with col_p2:
        val_p = st.number_input("Valor por Ponto (R$)", min_value=0.0, value=0.0, step=10.0)
    with col_p3:
        desconto = st.number_input("Desconto Opcional (R$)", min_value=0.0, value=0.0, step=10.0)
        
    defeito = st.text_input("Descrição do Defeito / Relato (Opcional)")

# --- SELEÇÃO DE PRODUTOS ---
st.markdown("---")
st.subheader("3. Adicionar Produtos e Materiais")

conn = sqlite3.connect("banco_vcs.db")
cursor = conn.cursor()
cursor.execute("SELECT DISTINCT categoria FROM produtos")
categorias = [row[0] for row in cursor.fetchall()]
conn.close()

col_cat, col_prod, col_qtd, col_btn = st.columns([1, 2, 0.5, 0.5])
with col_cat:
    cat_sel = st.selectbox("Categoria", categorias)

conn = sqlite3.connect("banco_vcs.db")
cursor = conn.cursor()
cursor.execute("SELECT descricao, preco FROM produtos WHERE categoria = ? ORDER BY descricao ASC", (cat_sel,))
produtos_disponiveis = cursor.fetchall()
conn.close()

prod_dict = {p[0]: p[1] for p in produtos_disponiveis}

with col_prod:
    prod_sel = st.selectbox("Produto", list(prod_dict.keys()) if prod_dict else ["Nenhum"])
with col_qtd:
    qtd_sel = st.number_input("Qtd", min_value=1, value=1, step=1)
with col_btn:
    st.text("") # Espaçamento visual
    if st.button("Adicionar"):
        if prod_sel and prod_sel != "Nenhum":
            preco_unit = prod_dict[prod_sel]
            total_item = preco_unit * qtd_sel
            st.session_state.carrinho.append({"desc": prod_sel, "qtd": qtd_sel, "preco": preco_unit, "total": total_item})
            st.success("Item adicionado!")

# --- CARRINHO / ITENS SELECIONADOS ---
st.markdown("### Itens no Orçamento")
if st.session_state.carrinho:
    for idx, item in enumerate(st.session_state.carrinho):
        col_i1, col_i2, col_i3, col_i4 = st.columns([3, 1, 1, 1])
        col_i1.text(item['desc'])
        col_i2.text(f"Qtd: {item['qtd']}")
        col_i3.text(f"R$ {item['total']:.2f}")
        if col_i4.button("❌ Remover", key=f"rem_{idx}"):
            st.session_state.carrinho.pop(idx)
            st.rerun()
else:
    st.info("Nenhum produto adicionado ainda.")

# --- CONDIÇÕES GERAIS ---
st.markdown("---")
st.subheader("4. Prazos e Condições")
col_c1, col_c2, col_c3 = st.columns(3)
with col_c1:
    garantia = st.text_input("Garantia", value="6 Meses")
with col_c2:
    validade = st.text_input("Validade do Orçamento", value="15 Dias")
with col_c3:
    pagamento = st.text_input("Condição de Pagamento", value="À Vista / Pix")

# --- CÁLCULO DO TOTAL ---
subtotal_carrinho = sum(item["total"] for item in st.session_state.carrinho)
total_servicos = serv_val + (qtd_p * val_p)
subtotal_geral = subtotal_carrinho + total_servicos
total_geral = max(0.0, subtotal_geral - desconto)

st.markdown(f"### 💰 **Total Geral: R$ {total_geral:.2f}**")

# --- BOTÃO DE GERAR PDF ---
if st.button("💾 Gerar PDF do Orçamento", type="primary"):
    if not cli_nome:
        st.error("Por favor, preencha o nome do cliente antes de gerar o orçamento.")
    else:
        salvar_cliente_banco(cli_nome, cli_doc, cli_tel, cli_end)
        
        itens_finais = list(st.session_state.carrinho)
        if serv_val > 0 and serv_desc:
            itens_finais.append({"desc": serv_desc, "qtd": 1, "preco": serv_val, "total": serv_val})
        if qtd_p > 0 and val_p > 0:
            itens_finais.append({"desc": f"Instalação / Execução de Pontos (Qtd: {qtd_p})", "qtd": qtd_p, "preco": val_p, "total": qtd_p * val_p})

        dados_cliente = {
            "nome": cli_nome,
            "documento": cli_doc or "Não informado",
            "telefone": cli_tel or "Não informado",
            "endereco": cli_end or "Não informado",
            "garantia": garantia,
            "validade": validade,
            "pagamento": pagamento,
            "defeito": defeito
        }
        
        num_orc = obter_numero_orcamento()
        
        # Salva no banco
        conn = sqlite3.connect("banco_vcs.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO orcamentos (numero_orcamento, cliente, documento, telefone, endereco, garantia, validade, pagamento, servico_desc, servico_valor, defeito, data, total) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (num_orc, dados_cliente['nome'], dados_cliente['documento'], dados_cliente['telefone'], 
              dados_cliente['endereco'], dados_cliente['garantia'], dados_cliente['validade'], 
              dados_cliente['pagamento'], serv_desc, serv_val, dados_cliente['defeito'], datetime.date.today().strftime('%d/%m/%Y'), total_geral))
        conn.commit()
        conn.close()
        
        caminho_pdf = gerar_pdf(num_orc, dados_cliente, itens_finais, desconto, total_geral)
        st.success(f"Orçamento {num_orc} gerado com sucesso!")
        
        with open(caminho_pdf, "rb") as pdf_file:
            st.download_button(
                label="📥 Baixar PDF Agora",
                data=pdf_file,
                file_name=os.path.basename(caminho_pdf),
                mime="application/octet-stream"
            )