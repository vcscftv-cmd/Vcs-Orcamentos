@st.cache_data(show_spinner=False, ttl=600)
def carregar_todos_produtos():
    produtos_dict = {} 
    # Carrega diretamente da tabela global que já centraliza os produtos
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
