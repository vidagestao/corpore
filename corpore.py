import streamlit as st
import pandas as pd
from datetime import datetime
import os
import hashlib
import base64
import shutil

# --- Configuração da Página (Deve ser a primeira linha) ---
st.set_page_config(
    page_title="Portal Corpore",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONFIGURAÇÕES GLOBAIS ---
FILE_DB = 'profissionais_db_secure.csv'
BASE_FILES_DIR = "corpore_docs"
SENSITIVE_COLUMNS = ['CPF', 'Mãe', 'Email', 'Telefone', 'Pix', 'Banco']

# CSS Personalizado para visual profissional
st.markdown("""
    <style>
    .main-header {font-size: 2.5rem; color: #004E98; font-weight: 700;}
    .sub-header {font-size: 1.5rem; color: #3A6EA5; margin-top: 1rem;}
    .card {background-color: #f9f9f9; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #004E98; margin-bottom: 1rem;}
    .success-box {padding: 1rem; background-color: #d4edda; color: #155724; border-radius: 5px;}
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES CORE (Segurança, Arquivos, DB) ---

def init_environment():
    """Garante que pastas e arquivos essenciais existam."""
    if not os.path.exists(BASE_FILES_DIR):
        os.makedirs(BASE_FILES_DIR)

def ensure_user_dirs(cpf):
    """Cria pastas isoladas para cada usuário."""
    # Estrutura: corpore_docs/12345678900/recebidos e .../enviados
    user_root = os.path.join(BASE_FILES_DIR, str(cpf))
    inbox = os.path.join(user_root, "recebidos_gestao") # Admin -> Usuário
    outbox = os.path.join(user_root, "enviados_usuario") # Usuário -> Admin
    
    os.makedirs(inbox, exist_ok=True)
    os.makedirs(outbox, exist_ok=True)
    return inbox, outbox

def save_uploaded_file(uploaded_file, target_folder):
    """Salva arquivo com tratamento de erros."""
    try:
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
            
        file_path = os.path.join(target_folder, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return True
    except Exception as e:
        st.error(f"Erro ao salvar arquivo: {e}")
        return False

def get_files(directory):
    if os.path.exists(directory):
        return [f for f in os.listdir(directory) if not f.startswith('.')]
    return []

# --- SEGURANÇA ---
def encrypt(text):
    """Ofuscação simples para persistência (Base64)."""
    return base64.b64encode(str(text).encode()).decode() if text else ""

def decrypt(text):
    """Reverte ofuscação."""
    try:
        return base64.b64decode(str(text).encode()).decode() if text else ""
    except:
        return text

def hash_pass(password):
    return hashlib.sha256(str(password).encode()).hexdigest()

def verify_pass(stored, provided):
    return stored == hash_pass(provided)

# --- BANCO DE DADOS ---
def load_db():
    if os.path.exists(FILE_DB):
        df = pd.read_csv(FILE_DB, dtype=str) # Lê tudo como string para evitar erros de CPF
        # Desofusca para uso na memória
        for col in SENSITIVE_COLUMNS:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: decrypt(x))
        return df
    return pd.DataFrame(columns=['CPF', 'Senha', 'Nome', 'Role', 'Unidade', 'Email', 'Telefone', 'Pix', 'Banco', 'Disponibilidade'])

def save_user(user_data, update=False):
    """Salva ou atualiza um usuário."""
    df = load_db()
    
    # Prepara dados para salvar (criptografar)
    data_to_save = user_data.copy()
    for col in SENSITIVE_COLUMNS:
        if col in data_to_save:
            data_to_save[col] = encrypt(data_to_save[col])
            
    # Hash da senha se for novo cadastro ou alteração de senha
    if 'Senha' in data_to_save and len(data_to_save['Senha']) < 50: # Assume que se for curto, não é hash
        data_to_save['Senha'] = hash_pass(data_to_save['Senha'])

    df_new_row = pd.DataFrame([data_to_save])

    if update:
        # Remove antigo e adiciona novo (pelo CPF que é a chave)
        # Nota: CPF criptografado muda, então buscamos pelo CPF decriptado antes
        df = df[df['CPF'] != user_data['CPF']] # Remove user atual da memória decriptada
        
        # Re-criptografa todo o DF da memória para salvar
        for col in SENSITIVE_COLUMNS:
            if col in df.columns:
                df[col] = df[col].apply(encrypt)
        
        # Concatena o novo (já criptografado)
        df_final = pd.concat([df, df_new_row], ignore_index=True)
    else:
        # Modo Append: Carrega o arquivo bruto para não precisar re-criptografar tudo
        if os.path.exists(FILE_DB):
            df_raw = pd.read_csv(FILE_DB, dtype=str)
            df_final = pd.concat([df_raw, df_new_row], ignore_index=True)
        else:
            df_final = df_new_row
            
    df_final.to_csv(FILE_DB, index=False)

# --- INTERFACE: TELAS ---

def screen_setup_admin():
    st.markdown("<h1 class='main-header'>🚀 Configuração Inicial</h1>", unsafe_allow_html=True)
    st.info("O sistema detectou que não há usuários cadastrados. Crie a conta do ADMINISTRADOR MASTER.")
    
    with st.form("setup_form"):
        col1, col2 = st.columns(2)
        nome = col1.text_input("Nome do Gestor")
        cpf = col2.text_input("CPF (Login)", max_chars=11)
        senha = col1.text_input("Senha", type="password")
        senha_conf = col2.text_input("Confirmar Senha", type="password")
        
        if st.form_submit_button("Inicializar Sistema"):
            if senha != senha_conf:
                st.error("Senhas não conferem.")
            elif not cpf or not nome:
                st.error("Preencha todos os campos.")
            else:
                admin_data = {
                    "Nome": nome, "CPF": cpf, "Senha": senha, 
                    "Role": "admin", "Unidade": "Matriz",
                    "Data Cadastro": datetime.now().strftime("%Y-%m-%d")
                }
                save_user(admin_data)
                ensure_user_dirs(cpf)
                st.success("Administrador criado! Atualize a página para fazer login.")
                st.balloons()

def screen_login():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<div style='text-align: center; margin-top: 50px;'>", unsafe_allow_html=True)
        st.image("https://img.icons8.com/ios/100/228BE6/hospital-3.png", width=80)
        st.markdown("<h2 style='color: #004E98;'>Portal Corpore</h2></div>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            cpf = st.text_input("CPF / Usuário", placeholder="Digite apenas números")
            senha = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar no Portal", use_container_width=True)
            
            if submitted:
                df = load_db()
                user = df[df['CPF'] == cpf]
                
                if not user.empty:
                    stored_pass = user.iloc[0]['Senha']
                    # Verifica hash (ou texto puro de legado)
                    if stored_pass == hash_pass(senha) or stored_pass == senha:
                        st.session_state['user'] = user.iloc[0].to_dict()
                        st.success("Login efetuado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Senha incorreta.")
                else:
                    st.error("Usuário não encontrado.")

def screen_admin_dashboard(user):
    st.markdown(f"<h1 class='main-header'>Painel de Gestão</h1>", unsafe_allow_html=True)
    st.write(f"Logado como: **{user['Nome']}** (Administrador)")
    
    tabs = st.tabs(["📊 Visão Geral", "👥 Gestão de Profissionais", "📤 Central de Arquivos", "📅 Calendário"])
    
    df = load_db()
    
    with tabs[0]: # Dashboard
        col1, col2, col3 = st.columns(3)
        col1.metric("Profissionais Cadastrados", len(df))
        col2.metric("Unidades Ativas", df['Unidade'].nunique())
        col3.metric("Cadastros Hoje", len(df[df['Data Cadastro'] == datetime.now().strftime("%Y-%m-%d")]) if 'Data Cadastro' in df else 0)
        
        st.markdown("---")
        st.subheader("Profissionais por Unidade")
        st.bar_chart(df['Unidade'].value_counts())

    with tabs[1]: # Gestão de Pessoas (Cadastro)
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.markdown("### ➕ Novo Profissional")
            with st.form("new_user_admin"):
                new_nome = st.text_input("Nome Completo")
                new_cpf = st.text_input("CPF (Apenas números)", max_chars=11)
                new_pass = st.text_input("Senha Temporária", type="password")
                new_unit = st.selectbox("Unidade", ["Unidade 1 - Centro", "Unidade 2 - Zona Sul"])
                
                if st.form_submit_button("Cadastrar Profissional"):
                    if new_cpf in df['CPF'].values:
                        st.error("CPF já existe no sistema.")
                    else:
                        new_data = {
                            "Nome": new_nome, "CPF": new_cpf, "Senha": new_pass,
                            "Role": "user", "Unidade": new_unit,
                            "Data Cadastro": datetime.now().strftime("%Y-%m-%d")
                        }
                        save_user(new_data)
                        ensure_user_dirs(new_cpf)
                        st.success(f"Profissional {new_nome} cadastrado!")
                        st.rerun()
        
        with c2:
            st.markdown("### 📋 Lista de Profissionais")
            # Mostra tabela simplificada
            display_cols = ['Nome', 'CPF', 'Unidade', 'Telefone', 'Email']
            st.dataframe(df[display_cols], use_container_width=True)

    with tabs[2]: # Arquivos
        st.subheader("Envio de Relatórios e Holerites")
        
        # Selecionar Destinatário
        users_list = df[df['Role'] != 'admin']
        if not users_list.empty:
            destinatario = st.selectbox("Selecione o Profissional", users_list['Nome'] + " - " + users_list['CPF'])
            cpf_dest = destinatario.split(" - ")[-1]
            
            # Área de Upload
            file = st.file_uploader("Arraste o documento aqui (PDF, Excel, Imagem)", type=['pdf', 'xlsx', 'jpg', 'png'])
            
            if file and st.button("Enviar Documento"):
                path_dest, _ = ensure_user_dirs(cpf_dest)
                if save_uploaded_file(file, path_dest):
                    st.success(f"Arquivo enviado para {destinatario} com sucesso!")
            
            st.markdown("---")
            st.markdown(f"**Arquivos enviados pelo usuário {cpf_dest}:**")
            _, path_from_user = ensure_user_dirs(cpf_dest)
            arquivos_user = get_files(path_from_user)
            
            if arquivos_user:
                for arq in arquivos_user:
                    col_f1, col_f2 = st.columns([4, 1])
                    col_f1.text(f"📎 {arq}")
                    with open(os.path.join(path_from_user, arq), "rb") as f:
                        col_f2.download_button("Baixar", f, file_name=f"RECEBIDO_{cpf_dest}_{arq}")
            else:
                st.info("Este usuário ainda não enviou documentos.")
        else:
            st.warning("Cadastre profissionais primeiro.")

    with tabs[3]: # Calendário Admin
        st.subheader("Gerenciar Avisos (Futuro)")
        st.info("Funcionalidade de editar calendário será implementada na próxima versão.")

def screen_user_dashboard(user):
    st.markdown(f"<h1 class='main-header'>Portal do Colaborador</h1>", unsafe_allow_html=True)
    
    # Sidebar Info
    st.sidebar.markdown(f"### 👤 {user['Nome']}")
    st.sidebar.text(f"Unidade: {user.get('Unidade', '-')}")
    if st.sidebar.button("Sair"):
        st.session_state['user'] = None
        st.rerun()

    tabs = st.tabs(["📌 Mural & Calendário", "📂 Meus Documentos", "📝 Meus Dados"])

    with tabs[0]:
        c1, c2, c3 = st.columns(3)
        c1.warning("🎉 Confraternização: 12/Dez")
        c2.error("🚨 Recesso: 22/Dez a 04/Jan")
        c3.info("📅 Reunião: 06/12 - Sábado")
        
        st.markdown("### Calendário Operacional")
        data_cal = [
            {"Data": "06/12/2025", "Evento": "Reunião Geral", "Tipo": "Obrigatório"},
            {"Data": "22/12/2025", "Evento": "Início Recesso", "Tipo": "Feriado"},
            {"Data": "05/01/2026", "Evento": "Retorno Atividades", "Tipo": "Normal"}
        ]
        st.dataframe(pd.DataFrame(data_cal), use_container_width=True)

    with tabs[1]:
        inbox, outbox = ensure_user_dirs(user['CPF'])
        
        col_in, col_out = st.columns(2)
        
        with col_in:
            st.markdown("<div class='card'><h3>📥 Recebidos da Clínica</h3>", unsafe_allow_html=True)
            files_in = get_files(inbox)
            if files_in:
                for f in files_in:
                    with open(os.path.join(inbox, f), "rb") as doc:
                        st.download_button(f"📄 Baixar {f}", doc, file_name=f, key=f"dl_{f}")
            else:
                st.info("Nenhum documento novo.")
            st.markdown("</div>", unsafe_allow_html=True)
            
        with col_out:
            st.markdown("<div class='card'><h3>📤 Enviar Documento</h3>", unsafe_allow_html=True)
            st.caption("Envie certificados, comprovantes ou fotos.")
            uploaded = st.file_uploader("Selecionar Arquivo", key="uploader_user")
            
            if uploaded:
                if st.button("Confirmar Envio"):
                    if save_uploaded_file(uploaded, outbox):
                        st.success("Enviado com sucesso!")
                        # Gambiarra para limpar o uploader: rerun
                        st.rerun()
            
            st.markdown("#### Histórico de Envios")
            files_out = get_files(outbox)
            for f in files_out:
                st.text(f"✅ {f}")
            st.markdown("</div>", unsafe_allow_html=True)

    with tabs[2]:
        st.subheader("Atualização Cadastral")
        with st.form("user_update"):
            c1, c2 = st.columns(2)
            email = c1.text_input("E-mail", value=user.get('Email', ''))
            tel = c2.text_input("Telefone", value=user.get('Telefone', ''))
            pix = c1.text_input("Chave PIX", value=user.get('Pix', ''))
            banco = c2.text_input("Banco", value=user.get('Banco', ''))
            disp = st.text_area("Disponibilidade", value=user.get('Disponibilidade', ''))
            
            if st.form_submit_button("Salvar Alterações"):
                user_updated = user.copy()
                user_updated.update({
                    "Email": email, "Telefone": tel, 
                    "Pix": pix, "Banco": banco, "Disponibilidade": disp
                })
                save_user(user_updated, update=True)
                st.session_state['user'] = user_updated
                st.success("Dados atualizados com sucesso!")

# --- ORQUESTRADOR PRINCIPAL ---

def main():
    init_environment()
    
    # Verifica se existe algum usuário no DB. Se vazio, vai para Setup.
    df = load_db()
    if df.empty:
        screen_setup_admin()
        return

    # Verifica sessão
    if 'user' not in st.session_state or st.session_state['user'] is None:
        screen_login()
    else:
        user = st.session_state['user']
        # Roteamento baseado na Role
        if user.get('Role') == 'admin':
            screen_admin_dashboard(user)
        else:
            screen_user_dashboard(user)

if __name__ == "__main__":
    main()
