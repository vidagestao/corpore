import streamlit as st
import pandas as pd
from datetime import date, datetime
import os
import hashlib
import base64
import shutil

# --- Configuração da Página ---
st.set_page_config(
    page_title="Portal Colaborador - Clínica Corpore",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONFIGURAÇÃO DE SEGURANÇA E ARQUIVOS ---
FILE_DB = 'profissionais_db_secure.csv'
BASE_FILES_DIR = "user_files" 

# Campos sensíveis
SENSITIVE_COLUMNS = ['CPF', 'Mãe', 'Email', 'Telefone', 'Pix', 'Banco']

# --- FUNÇÕES DE UTILIDADE (Files, Auth, Obfuscation) ---

def ensure_directories(cpf):
    """Cria a estrutura de pastas para um usuário específico se não existir."""
    admin_to_user = os.path.join(BASE_FILES_DIR, cpf, "recebidos_gestao")
    user_to_admin = os.path.join(BASE_FILES_DIR, cpf, "enviados_usuario")
    
    os.makedirs(admin_to_user, exist_ok=True)
    os.makedirs(user_to_admin, exist_ok=True)
    return admin_to_user, user_to_admin

def save_uploaded_file(uploaded_file, directory):
    """Salva um arquivo enviado via Streamlit no diretório local."""
    if uploaded_file is not None:
        file_path = os.path.join(directory, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return True
    return False

def list_files_in_dir(directory):
    if os.path.exists(directory):
        return [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    return []

# --- MUDANÇA: Substituindo Criptografia Pesada por Ofuscação Base64 (Standard Lib) ---
# Isso resolve o erro ModuleNotFoundError pois base64 vem com o Python.

def encrypt_data(text):
    """Ofusca o texto usando Base64 (Simples, mas sem dependência externa)."""
    if not isinstance(text, str): text = str(text)
    try:
        return base64.b64encode(text.encode("utf-8")).decode("utf-8")
    except Exception:
        return text

def decrypt_data(text):
    """Reverte a ofuscação Base64."""
    try:
        return base64.b64decode(text.encode("utf-8")).decode("utf-8")
    except Exception:
        return text

def hash_password(password):
    """Hash SHA-256 para senhas (Seguro e Standard Lib)."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_hash, provided_password):
    return stored_hash == hash_password(provided_password)

# --- FUNÇÕES DE BANCO DE DADOS ---

def load_data_secure():
    if os.path.exists(FILE_DB):
        df = pd.read_csv(FILE_DB)
        # Desofusca dados para uso interno
        for col in SENSITIVE_COLUMNS:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: decrypt_data(x) if pd.notnull(x) else x)
        return df
    return pd.DataFrame(columns=['CPF', 'Senha', 'Nome'])

def save_professional_secure(data, is_update=False):
    data_encrypted = data.copy()
    
    # Ofusca campos sensíveis
    for col in SENSITIVE_COLUMNS:
        if col in data_encrypted and data_encrypted[col]:
             data_encrypted[col] = encrypt_data(data_encrypted[col])
    
    df_new = pd.DataFrame([data_encrypted])
    
    if not os.path.exists(FILE_DB):
        df_new.to_csv(FILE_DB, index=False)
    else:
        # Carrega dados atuais (desofuscados para achar o registro)
        df_curr = load_data_secure()
        
        if is_update:
            # Atualiza registro existente
            idx = df_curr[df_curr['CPF'] == data['CPF']].index
            if not idx.empty:
                for key, value in data.items():
                    df_curr.at[idx[0], key] = value
            else:
                df_curr = pd.concat([df_curr, pd.DataFrame([data])], ignore_index=True)
            
            # Re-ofusca tudo para salvar
            for col in SENSITIVE_COLUMNS:
                if col in df_curr.columns:
                    df_curr[col] = df_curr[col].apply(lambda x: encrypt_data(x) if pd.notnull(x) else x)
            df_curr.to_csv(FILE_DB, index=False)
        else:
            # Adiciona novo registro ao arquivo existente (lendo o arquivo bruto para ser mais rápido)
            df_old_raw = pd.read_csv(FILE_DB)
            df_combined = pd.concat([df_old_raw, df_new], ignore_index=True)
            df_combined.to_csv(FILE_DB, index=False)

# --- SISTEMA DE SESSÃO ---
if 'user' not in st.session_state:
    st.session_state['user'] = None
if 'role' not in st.session_state:
    st.session_state['role'] = None 
if 'menu_option' not in st.session_state:
    st.session_state['menu_option'] = None

# --- SIDEBAR: LOGIN & MENU ---
st.sidebar.image("https://img.icons8.com/ios/100/228BE6/hospital-3.png", width=80) 
st.sidebar.title("Portal Corpore")

# Área de Login na Sidebar
if st.session_state['user'] is None:
    st.sidebar.header("Identifique-se")
    login_cpf = st.sidebar.text_input("CPF (Apenas números)", placeholder="12345678900")
    login_senha = st.sidebar.text_input("Senha", type="password")
    
    col_l1, col_l2 = st.sidebar.columns(2)
    if col_l1.button("Entrar"):
        if login_cpf == "admin" and login_senha == "admin123":
            st.session_state['user'] = {"Nome": "Administrador", "CPF": "admin"}
            st.session_state['role'] = "admin"
            st.rerun()
        else:
            df = load_data_secure()
            if not df.empty:
                user_row = df[df['CPF'] == login_cpf]
                if not user_row.empty:
                    stored_pass = user_row.iloc[0]['Senha']
                    if verify_password(stored_pass, login_senha):
                        st.session_state['user'] = user_row.iloc[0].to_dict()
                        st.session_state['role'] = "user"
                        st.success("Login realizado!")
                        st.rerun()
                    else:
                        st.sidebar.error("Senha incorreta.")
                else:
                    st.sidebar.error("Usuário não encontrado.")
            else:
                 st.sidebar.error("Base de dados vazia.")
    
    if col_l2.button("Cadastrar"):
        st.session_state['menu_option'] = "cadastro_novo"

else:
    st.sidebar.success(f"Olá, {st.session_state['user']['Nome']}")
    if st.sidebar.button("Sair / Logout"):
        st.session_state['user'] = None
        st.session_state['role'] = None
        st.rerun()

st.sidebar.markdown("---")

# Menu de Navegação
if st.session_state['role'] == 'admin':
    menu = st.sidebar.radio("Menu Administrativo", ["Painel Admin", "Enviar Relatórios", "Ver Envios dos Usuários", "Mural de Avisos"])
elif st.session_state['role'] == 'user':
    menu = st.sidebar.radio("Menu do Colaborador", ["Meu Painel", "Meus Documentos", "Editar Meus Dados", "Mural de Avisos", "Calendário"])
else:
    menu = st.sidebar.radio("Menu Visitante", ["Mural de Avisos", "Calendário", "Criar Conta"])

# --- LÓGICA DAS PÁGINAS ---

# 1. MURAL
if menu == "Mural de Avisos":
    st.title("📌 Mural de Comunicação")
    col1, col2, col3 = st.columns(3)
    col1.error("🚨 Recesso: 22/Dez a 04/Jan"); col2.warning("🎉 Festa: 12/Dez"); col3.info("🩺 Reunião: 06/12")
    st.markdown("---")
    st.write("Bem-vindo ao portal. Faça login para acessar seus documentos.")

# 2. CALENDÁRIO
elif menu == "Calendário":
    st.title("📅 Calendário 2025/26")
    data_calendario = [
        {"Data": "06/12/2025", "Evento": "Reunião Corpo Clínico", "Tipo": "Reunião"},
        {"Data": "12/12/2025", "Evento": "Confraternização", "Tipo": "Festa"},
        {"Data": "22/12/2025", "Evento": "Início Recesso", "Tipo": "Recesso"},
        {"Data": "05/01/2026", "Evento": "Retorno", "Tipo": "Operacional"},
    ]
    st.dataframe(pd.DataFrame(data_calendario), use_container_width=True)

# 3. CRIAR CONTA
elif menu == "Criar Conta" or (st.session_state.get('menu_option') == 'cadastro_novo' and st.session_state['role'] is None):
    st.title("📝 Novo Cadastro")
    with st.form("form_cadastro_novo"):
        st.write("Dados de Acesso")
        cpf = st.text_input("CPF (Apenas números)", max_chars=11)
        senha = st.text_input("Crie uma Senha", type="password")
        
        st.write("Dados Pessoais")
        nome = st.text_input("Nome Completo")
        email = st.text_input("E-mail")
        telefone = st.text_input("Telefone")
        unidade = st.selectbox("Unidade", ["Unidade 1 - Centro", "Unidade 2 - Zona Sul"])
        
        chave_pix = st.text_input("Chave PIX")
        banco_pix = st.text_input("Banco")
        
        if st.form_submit_button("Criar Conta"):
            if not cpf or not senha or not nome:
                st.error("CPF, Senha e Nome são obrigatórios.")
            else:
                df = load_data_secure()
                if not df.empty and cpf in df['CPF'].values:
                    st.error("CPF já cadastrado.")
                else:
                    novo_usuario = {
                        "CPF": cpf,
                        "Senha": hash_password(senha),
                        "Nome": nome,
                        "Email": email,
                        "Telefone": telefone,
                        "Unidade": unidade,
                        "Pix": chave_pix,
                        "Banco": banco_pix,
                        "Data Cadastro": datetime.now().strftime("%Y-%m-%d")
                    }
                    save_professional_secure(novo_usuario)
                    ensure_directories(cpf)
                    st.success("Conta criada! Faça login na barra lateral.")

# --- ÁREA DO USUÁRIO ---

elif menu == "Meu Painel" and st.session_state['role'] == 'user':
    user = st.session_state['user']
    st.title(f"👋 Olá, {user['Nome']}")
    st.info(f"Unidade: {user.get('Unidade', 'N/A')} | CPF: {user['CPF']}")
    
    path_recebidos, _ = ensure_directories(user['CPF'])
    qtd_relatorios = len(list_files_in_dir(path_recebidos))
    st.metric("Relatórios Disponíveis", f"{qtd_relatorios}")

elif menu == "Meus Documentos" and st.session_state['role'] == 'user':
    user = st.session_state['user']
    path_recebidos, path_enviados = ensure_directories(user['CPF'])
    
    st.title("📂 Gestão de Documentos")
    tab1, tab2 = st.tabs(["📥 Recebidos", "📤 Meus Envios"])
    
    with tab1:
        arquivos = list_files_in_dir(path_recebidos)
        if arquivos:
            for arq in arquivos:
                c1, c2 = st.columns([3, 1])
                c1.text(f"📄 {arq}")
                with open(os.path.join(path_recebidos, arq), "rb") as f:
                    c2.download_button("Baixar", f, file_name=arq)
                st.divider()
        else:
            st.info("Nenhum documento recebido.")

    with tab2:
        uploaded = st.file_uploader("Enviar arquivo para Gestão", type=['pdf', 'jpg', 'png', 'docx'])
        if uploaded and st.button("Confirmar Envio"):
            if save_uploaded_file(uploaded, path_enviados):
                st.success("Enviado com sucesso!")
                st.rerun()

elif menu == "Editar Meus Dados" and st.session_state['role'] == 'user':
    st.title("📝 Editar Perfil")
    user = st.session_state['user']
    with st.form("edit_profile"):
        col_e1, col_e2 = st.columns(2)
        email = col_e1.text_input("E-mail", value=user.get('Email', ''))
        tel = col_e2.text_input("Telefone", value=user.get('Telefone', ''))
        pix = col_e1.text_input("Chave PIX", value=user.get('Pix', ''))
        banco = col_e2.text_input("Banco", value=user.get('Banco', ''))
        
        if st.form_submit_button("Atualizar"):
            user_updated = user.copy()
            user_updated.update({"Email": email, "Telefone": tel, "Pix": pix, "Banco": banco})
            save_professional_secure(user_updated, is_update=True)
            st.session_state['user'] = user_updated
            st.success("Atualizado!")

# --- ÁREA DO ADMIN ---

elif menu == "Painel Admin" and st.session_state['role'] == 'admin':
    st.title("🔒 Gestão Geral")
    df = load_data_secure()
    st.dataframe(df)

elif menu == "Enviar Relatórios" and st.session_state['role'] == 'admin':
    st.title("📤 Enviar Relatório Individual")
    df = load_data_secure()
    if not df.empty:
        options = df.apply(lambda x: f"{x['Nome']} | CPF: {x['CPF']}", axis=1)
        selected = st.selectbox("Selecione o Profissional", options)
        if selected:
            cpf_target = selected.split("CPF: ")[1]
            path_target, _ = ensure_directories(cpf_target)
            uploaded_report = st.file_uploader("Upload (PDF/Excel)", type=['pdf', 'xlsx', 'csv'])
            if uploaded_report and st.button("Enviar"):
                save_uploaded_file(uploaded_report, path_target)
                st.success("Enviado!")

elif menu == "Ver Envios dos Usuários" and st.session_state['role'] == 'admin':
    st.title("📥 Arquivos dos Usuários")
    df = load_data_secure()
    if not df.empty:
        selected = st.selectbox("Filtrar Profissional", df.apply(lambda x: f"{x['Nome']} | CPF: {x['CPF']}", axis=1))
        if selected:
            cpf_target = selected.split("CPF: ")[1]
            _, path_user = ensure_directories(cpf_target)
            arquivos = list_files_in_dir(path_user)
            if arquivos:
                for arq in arquivos:
                    with open(os.path.join(path_user, arq), "rb") as f:
                        st.download_button(f"⬇️ {arq}", f, file_name=f"USER_{cpf_target}_{arq}")
            else:
                st.info("Vazio.")
