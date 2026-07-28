@st.cache_data(show_spinner=False)
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

    for db_emp in EMPRESAS.values():
        if os.path.exists(db_emp):
            try:
                conn_e = sqlite3.connect(db_emp)
                cursor_e = conn_e.cursor()
                cursor_e.execute("SELECT descricao, preco, categoria FROM produtos")
                for p in cursor_e.fetchall():
                    desc = p[0].strip()
                    if desc.lower() not in produtos_dict:
                        produtos_dict[desc.lower()] = (p[0], p[1], p[2])
                        # Sincroniza em segundo plano sem travar a interface principal
                        try:
                            conn_gp = conectar_produtos()
                            cursor_gp = conn_gp.cursor()
                            cursor_gp.execute("INSERT INTO produtos (codigo, descricao, preco, categoria) VALUES (?, ?, ?, ?)", ("", p[0], p[1], p[2]))
                            conn_gp.commit()
                            conn_gp.close()
                        except:
                            pass
                conn_e.close()
            except:
                pass
                
    return list(produtos_dict.values())
