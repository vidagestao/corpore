import streamlit as st
import pandas as pd
from datetime import date, datetime
import os
import hashlib
from cryptography.fernet import Fernet
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
BASE_FILES_DIR = "user_files" # Pasta raiz para documentos

# Campos sensíveis (criptografia no banco de dados)
SENSITIVE_COLUMNS = ['CPF', 'Mãe', 'Email', 'Telefone', 'Pix', 'Banco']

# --- FUNÇÕES DE UTILIDADE (Files, Auth, Crypto) ---

def ensure_directories(cpf):
    """Cria a estrutura de pastas para um usuário específico se não existir."""
    # Pasta para arquivos que o Admin envia para o usuário (Relatórios)
    admin_to_user = os.path.join(BASE_FILES_DIR, cpf, "recebidos_gestao")
    # Pasta para arquivos que o Usuário envia (Certificados, Fotos)
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
    """Lista arquivos em um diretório."""
    if os.path.exists(directory):
        return [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    return []

def get_key():
    """Recupera a chave de criptografia."""
    if 'ENCRYPTION_KEY' in st.secrets:
        return st.secrets['ENCRYPTION_KEY'].encode()
    if os.path.exists("secret.key"):
        with open("secret.key", "rb") as key_file:
            return key_file.read()
    key = Fernet.generate_key()
    with open("secret.key", "wb") as key_file:
        key_file.write(key)
    return key

cipher_suite = Fernet(get_key())

def encrypt_data(text):
    if not isinstance(text, str): text = str(text)
    return cipher_suite.encrypt(text.encode()).decode()

def decrypt_data(text):
    try:
        return cipher_suite.decrypt(text.encode()).decode()
    except:
        return text

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_hash, provided_password):
    return stored_hash == hash_password(provided_password)

# --- FUNÇÕES DE BANCO DE DADOS ---

def load_data_secure():
    if os.path.exists(FILE_DB):
        df = pd.read_csv(FILE_DB)
        # Descriptografa apenas se necessário para visualização interna
        # Para login, precisamos do CPF cru ou verificar hash, 
        # aqui vamos descriptografar tudo para facilitar manipulação em memória
        for col in SENSITIVE_COLUMNS:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: decrypt_data(x) if pd.notnull(x) else x)
        return df
    return pd.DataFrame(columns=['CPF', 'Senha', 'Nome'])

def save_professional_secure(data, is_update=False):
    """Salva ou atualiza usuário."""
    data_encrypted = data.copy()
    
    # Criptografa campos sensíveis
    for col in SENSITIVE_COLUMNS:
        if col in data_encrypted and data_encrypted[col]:
             data_encrypted[col] = encrypt_data(data_encrypted[col])
    
    df_new = pd.DataFrame([data_encrypted])
    
    if not os.path.exists(FILE_DB):
        df_new.to_csv(FILE_DB, index=False)
    else:
        df_old = pd.read_csv(FILE_DB)
        if is_update:
            # Remove a entrada antiga baseada no CPF (encriptado)
            # Obs: Como o CPF muda a cifra cada vez, o ideal seria usar ID único ou descriptografar para achar.
            # Abordagem simplificada: Carregar tudo, atualizar, salvar tudo re-encriptado.
            df_curr = load_data_secure() # Carrega decriptado
            # Atualiza o registro onde CPF bate
            idx = df_curr[df_curr['CPF'] == data['CPF']].index
            if not idx.empty:
                for key, value in data.items():
                    df_curr.at[idx[0], key] = value
            else:
                df_curr = pd.concat([df_curr, pd.DataFrame([data])], ignore_index=True)
            
            # Re-encripta tudo para salvar
            for col in SENSITIVE_COLUMNS:
                if col in df_curr.columns:
                    df_curr[col] = df_curr[col].apply(lambda x: encrypt_data(x) if pd.notnull(x) else x)
            df_curr.to_csv(FILE_DB, index=False)
        else:
            df_combined = pd.concat([df_old, df_new], ignore_index=True)
            df_combined.to_csv(FILE_DB, index=False)

# --- SISTEMA DE SESSÃO ---
if 'user' not in st.session_state:
    st.session_state['user'] = None # Pode ser um dicionário com dados do usuário
if 'role' not in st.session_state:
    st.session_state['role'] = None # 'admin', 'user', ou None

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
    
    if col_l2.button("Cadastrar"):
        st.session_state['menu_option'] = "cadastro_novo"

else:
    st.sidebar.success(f"Olá, {st.session_state['user']['Nome']}")
    if st.sidebar.button("Sair / Logout"):
        st.session_state['user'] = None
        st.session_state['role'] = None
        st.rerun()

st.sidebar.markdown("---")

# Menu de Navegação baseado no Role
if st.session_state['role'] == 'admin':
    menu = st.sidebar.radio("Menu Administrativo", ["Painel Admin", "Enviar Relatórios", "Ver Envios dos Usuários", "Mural de Avisos"])
elif st.session_state['role'] == 'user':
    menu = st.sidebar.radio("Menu do Colaborador", ["Meu Painel", "Meus Documentos", "Editar Meus Dados", "Mural de Avisos", "Calendário"])
else:
    # Menu para não logados (ou em processo de cadastro)
    menu = st.sidebar.radio("Menu Visitante", ["Mural de Avisos", "Calendário", "Criar Conta"])

# --- LÓGICA DAS PÁGINAS ---

# 1. MURAL (Público/Comum)
if menu == "Mural de Avisos":
    st.title("📌 Mural de Comunicação")
    col1, col2, col3 = st.columns(3)
    col1.error("🚨 Recesso: 22/Dez a 04/Jan"); col2.warning("🎉 Festa: 12/Dez"); col3.info("🩺 Reunião: 06/12")
    st.markdown("---")
    st.write("Bem-vindo ao portal. Faça login para acessar seus documentos.")

# 2. CALENDÁRIO (Público/Comum)
elif menu == "Calendário":
    st.title("📅 Calendário 2025/26")
    data_calendario = [
        {"Data": "06/12/2025", "Evento": "Reunião Corpo Clínico", "Tipo": "Reunião"},
        {"Data": "12/12/2025", "Evento": "Confraternização", "Tipo": "Festa"},
        {"Data": "22/12/2025", "Evento": "Início Recesso", "Tipo": "Recesso"},
        {"Data": "05/01/2026", "Evento": "Retorno", "Tipo": "Operacional"},
    ]
    st.dataframe(pd.DataFrame(data_calendario), use_container_width=True)

# 3. CRIAR CONTA (Visitante)
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
        
        # Outros campos simplificados para o exemplo...
        chave_pix = st.text_input("Chave PIX")
        
        if st.form_submit_button("Criar Conta"):
            if not cpf or not senha or not nome:
                st.error("CPF, Senha e Nome são obrigatórios.")
            else:
                # Verifica se CPF já existe
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
                        "Data Cadastro": datetime.now().strftime("%Y-%m-%d")
                    }
                    save_professional_secure(novo_usuario)
                    # Cria pastas do usuário
                    ensure_directories(cpf)
                    st.success("Conta criada com sucesso! Faça login na barra lateral.")

# --- ÁREA DO USUÁRIO LOGADO ---

elif menu == "Meu Painel" and st.session_state['role'] == 'user':
    user = st.session_state['user']
    st.title(f"👋 Olá, {user['Nome']}")
    st.info(f"Unidade: {user.get('Unidade', 'N/A')} | CPF: {user['CPF']}")
    
    st.subheader("Atalhos Rápidos")
    col_u1, col_u2 = st.columns(2)
    col_u1.metric("Mensagens Não Lidas", "0")
    
    # Verifica arquivos recebidos
    path_recebidos, _ = ensure_directories(user['CPF'])
    qtd_relatorios = len(list_files_in_dir(path_recebidos))
    col_u2.metric("Relatórios Disponíveis", f"{qtd_relatorios}")

elif menu == "Meus Documentos" and st.session_state['role'] == 'user':
    user = st.session_state['user']
    path_recebidos, path_enviados = ensure_directories(user['CPF'])
    
    st.title("📂 Gestão de Documentos")
    
    tab1, tab2 = st.tabs(["📥 Recebidos da Gestão", "📤 Meus Envios (Upload)"])
    
    with tab1:
        st.subheader("Relatórios de Produtividade e Informes")
        arquivos = list_files_in_dir(path_recebidos)
        if arquivos:
            for arq in arquivos:
                c1, c2 = st.columns([3, 1])
                c1.text(f"📄 {arq}")
                with open(os.path.join(path_recebidos, arq), "rb") as f:
                    c2.download_button("Baixar", f, file_name=arq)
                st.divider()
        else:
            st.info("Nenhum documento recebido ainda.")

    with tab2:
        st.subheader("Enviar Arquivo para a Gestão")
        st.caption("Use este espaço para enviar certificados, fotos ou documentos solicitados.")
        uploaded = st.file_uploader("Escolha um arquivo", type=['pdf', 'jpg', 'png', 'docx'])
        if uploaded is not None:
            if st.button("Confirmar Envio"):
                if save_uploaded_file(uploaded, path_enviados):
                    st.success("Arquivo enviado com sucesso!")
                    st.rerun()
        
        st.subheader("Histórico de Envios")
        meus_envios = list_files_in_dir(path_enviados)
        for env in meus_envios:
            st.text(f"✅ Enviado: {env}")

elif menu == "Editar Meus Dados" and st.session_state['role'] == 'user':
    st.title("📝 Editar Perfil")
    user = st.session_state['user']
    
    with st.form("edit_profile"):
        col_e1, col_e2 = st.columns(2)
        # Preenche com dados atuais da sessão (que vieram do CSV)
        email = col_e1.text_input("E-mail", value=user.get('Email', ''))
        tel = col_e2.text_input("Telefone", value=user.get('Telefone', ''))
        pix = col_e1.text_input("Chave PIX", value=user.get('Pix', ''))
        banco = col_e2.text_input("Banco", value=user.get('Banco', ''))
        disp = st.text_area("Disponibilidade", value=user.get('Disponibilidade', ''))
        
        if st.form_submit_button("Atualizar Meus Dados"):
            # Atualiza objeto user
            user_updated = user.copy()
            user_updated.update({
                "Email": email, "Telefone": tel, "Pix": pix, "Banco": banco, "Disponibilidade": disp
            })
            # Salva no CSV
            save_professional_secure(user_updated, is_update=True)
            # Atualiza sessão
            st.session_state['user'] = user_updated
            st.success("Dados atualizados com sucesso!")

# --- ÁREA DO ADMIN ---

elif menu == "Painel Admin" and st.session_state['role'] == 'admin':
    st.title("🔒 Gestão Geral")
    df = load_data_secure()
    st.metric("Total de Profissionais", len(df))
    st.dataframe(df)

elif menu == "Enviar Relatórios" and st.session_state['role'] == 'admin':
    st.title("📤 Enviar Relatório Individual")
    df = load_data_secure()
    
    if not df.empty:
        # Seleciona Profissional
        options = df.apply(lambda x: f"{x['Nome']} | CPF: {x['CPF']}", axis=1)
        selected_option = st.selectbox("Selecione o Profissional", options)
        
        if selected_option:
            cpf_target = selected_option.split("CPF: ")[1]
            path_target, _ = ensure_directories(cpf_target)
            
            uploaded_report = st.file_uploader("Upload do Relatório (PDF/Excel)", type=['pdf', 'xlsx', 'csv'])
            
            if uploaded_report and st.button("Enviar para o Profissional"):
                if save_uploaded_file(uploaded_report, path_target):
                    st.success(f"Arquivo enviado com sucesso para {selected_option}!")
    else:
        st.warning("Nenhum profissional cadastrado.")

elif menu == "Ver Envios dos Usuários" and st.session_state['role'] == 'admin':
    st.title("📥 Arquivos Recebidos dos Usuários")
    df = load_data_secure()
    
    if not df.empty:
        options = df.apply(lambda x: f"{x['Nome']} | CPF: {x['CPF']}", axis=1)
        selected_user = st.selectbox("Filtrar por Profissional", options)
        
        if selected_user:
            cpf_target = selected_user.split("CPF: ")[1]
            _, path_user_uploads = ensure_directories(cpf_target)
            
            arquivos = list_files_in_dir(path_user_uploads)
            if arquivos:
                st.write(f"Arquivos enviados por **{selected_user.split('|')[0]}**:")
                for arq in arquivos:
                    with open(os.path.join(path_user_uploads, arq), "rb") as f:
                        st.download_button(f"⬇️ Baixar {arq}", f, file_name=f"USER_{cpf_target}_{arq}")
            else:
                st.info("Este usuário não enviou arquivos.")
