import streamlit as st
import pandas as pd
from datetime import datetime
import os
import hashlib
import base64
import shutil
import re

# --- Configuração da Página (Deve ser a primeira linha) ---
st.set_page_config(
    page_title="Portal Corpore",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONFIGURAÇÕES GLOBAIS ---
FILE_DB = 'profissionais_db_secure.csv'
BASE_FILES_DIR = "corpore_docs"

# Campos Sensíveis (Criptografados)
SENSITIVE_COLUMNS = ['Mãe', 'Email', 'Pix', 'Banco', 'Notificacao', 'Resumo', 'Nascimento'] 

# Colunas do Banco de Dados
ALL_COLUMNS = ['Telefone', 'Senha', 'Nome', 'Role', 'Unidade', 'Email', 'Pix', 'Banco', 'Disponibilidade', 'Data Cadastro', 'Notificacao', 'Resumo', 'Nascimento']
UNIDADES_OPCOES = ["Corpore - São Mateus", "Corpore - Passos"]

# CSS Personalizado
st.markdown("""
    <style>
    .main-header {font-size: 2.5rem; color: #004E98; font-weight: 700;}
    .sub-header {font-size: 1.5rem; color: #3A6EA5; margin-top: 1rem;}
    .card {background-color: #f9f9f9; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #004E98; margin-bottom: 1rem;}
    .success-box {padding: 1rem; background-color: #d4edda; color: #155724; border-radius: 5px;}
    .whatsapp-btn {
        background-color: #25D366; color: white; padding: 5px 10px; border-radius: 5px; 
        text-decoration: none; font-weight: bold; border: none;
    }
    .whatsapp-btn:hover {color: #fff; background-color: #128C7E;}
    .delete-btn {
        background-color: #ff4b4b; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; text-decoration: none;
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES CORE (Segurança, Arquivos, DB, Utils) ---

def clean_phone_number(phone):
    """Remove caracteres não numéricos."""
    if not phone: return ""
    return re.sub(r'\D', '', str(phone))

def init_environment():
    """Garante que pastas e arquivos essenciais existam."""
    if not os.path.exists(BASE_FILES_DIR):
        os.makedirs(BASE_FILES_DIR)

def ensure_user_dirs(identifier):
    """Cria pastas isoladas para cada usuário usando o Telefone como ID."""
    clean_id = clean_phone_number(identifier)
    user_root = os.path.join(BASE_FILES_DIR, clean_id)
    inbox = os.path.join(user_root, "recebidos_gestao") 
    outbox = os.path.join(user_root, "enviados_usuario") 
    
    os.makedirs(inbox, exist_ok=True)
    os.makedirs(outbox, exist_ok=True)
    return inbox, outbox

def rename_user_dir(old_phone, new_phone):
    """Renomeia a pasta de arquivos se o telefone mudar."""
    old_id = clean_phone_number(old_phone)
    new_id = clean_phone_number(new_phone)
    
    old_path = os.path.join(BASE_FILES_DIR, old_id)
    new_path = os.path.join(BASE_FILES_DIR, new_id)
    
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
    else:
        ensure_user_dirs(new_phone)

def delete_user_dir(phone):
    """Apaga a pasta de arquivos do usuário."""
    clean_id = clean_phone_number(phone)
    path = os.path.join(BASE_FILES_DIR, clean_id)
    if os.path.exists(path):
        shutil.rmtree(path)

def save_uploaded_file(uploaded_file, target_folder):
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

def delete_file(folder, filename):
    """Exclui um arquivo específico."""
    try:
        file_path = os.path.join(folder, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")
        return False

def get_files(directory):
    if os.path.exists(directory):
        return [f for f in os.listdir(directory) if not f.startswith('.')]
    return []

# --- SEGURANÇA ---
def encrypt(text):
    return base64.b64encode(str(text).encode()).decode() if text else ""

def decrypt(text):
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
        df = pd.read_csv(FILE_DB, dtype=str)
        
        # Garante colunas novas e remove antigas se existirem
        for col in ALL_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        
        cols_to_keep = [c for c in df.columns if c in ALL_COLUMNS]
        df = df[cols_to_keep]

        # Desofusca
        for col in SENSITIVE_COLUMNS:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: decrypt(x))
        return df
    return pd.DataFrame(columns=ALL_COLUMNS)

def save_user(user_data, old_phone_key=None):
    df = load_db()
    data_to_save = user_data.copy()
    
    # Criptografa campos sensíveis
    for col in SENSITIVE_COLUMNS:
        if col in data_to_save:
            data_to_save[col] = encrypt(data_to_save[col])
            
    if 'Senha' in data_to_save and len(data_to_save['Senha']) < 50:
        data_to_save['Senha'] = hash_pass(data_to_save['Senha'])

    df_new_row = pd.DataFrame([data_to_save])
    for col in ALL_COLUMNS:
        if col not in df_new_row.columns:
            df_new_row[col] = ""

    target_phone = old_phone_key if old_phone_key else user_data['Telefone']
    
    df = df[df['Telefone'] != target_phone]
    
    for col in SENSITIVE_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(encrypt)
            
    df_final = pd.concat([df, df_new_row], ignore_index=True)
    df_final.to_csv(FILE_DB, index=False)

def delete_user(phone):
    df = load_db()
    df = df[df['Telefone'] != phone]
    for col in SENSITIVE_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(encrypt)
    df.to_csv(FILE_DB, index=False)
    delete_user_dir(phone)

def send_notification_to_all(message):
    df = load_db()
    users = df[df['Role'] != 'admin']
    count = 0
    for index, row in users.iterrows():
        user_data = row.to_dict()
        user_data['Notificacao'] = message
        save_user(user_data)
        count += 1
    return count

def send_notification_individual(phone, message):
    df = load_db()
    user = df[df['Telefone'] == phone]
    if not user.empty:
        user_data = user.iloc[0].to_dict()
        user_data['Notificacao'] = message
        save_user(user_data)
        return True
    return False

def clear_notification(user_data):
    user_data['Notificacao'] = ""
    save_user(user_data)
    st.session_state['user'] = user_data

# --- MANIPULAÇÃO DE DATAS ---
def check_birthday(date_str):
    """Verifica se a data (DD/MM/AAAA) é no mês atual."""
    try:
        if not date_str: return False
        birth_date = datetime.strptime(date_str, "%d/%m/%Y")
        today = datetime.now()
        return birth_date.month == today.month
    except:
        return False

# --- INTERFACE: TELAS ---

def screen_setup_admin():
    st.markdown("<h1 class='main-header'>🚀 Configuração Inicial</h1>", unsafe_allow_html=True)
    st.info("Bem-vindo! Crie a conta do ADMINISTRADOR MASTER para iniciar.")
    
    with st.form("setup_form"):
        col1, col2 = st.columns(2)
        nome = col1.text_input("Nome do Gestor")
        telefone = col1.text_input("Celular (Login)", placeholder="Ex: 11999998888")
        senha = col2.text_input("Senha", type="password")
        
        if st.form_submit_button("Inicializar Sistema"):
            if not telefone or not nome or not senha:
                st.error("Preencha todos os campos.")
            else:
                admin_data = {
                    "Nome": nome, "Senha": senha, 
                    "Role": "admin", "Unidade": "Matriz",
                    "Data Cadastro": datetime.now().strftime("%Y-%m-%d"),
                    "Email": "", "Telefone": telefone, "Notificacao": "", "Resumo": "",
                    "Nascimento": ""
                }
                save_user(admin_data)
                ensure_user_dirs(telefone)
                st.success("Administrador criado! Atualize a página.")
                st.balloons()

def screen_login():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<div style='text-align: center; margin-top: 50px;'>", unsafe_allow_html=True)
        st.image("https://img.icons8.com/ios/100/228BE6/hospital-3.png", width=80)
        st.markdown("<h2 style='color: #004E98;'>Portal Corpore</h2></div>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            st.markdown("##### Acesso Seguro")
            telefone_login = st.text_input("Celular Cadastrado", placeholder="Digite apenas números")
            senha = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar no Portal", use_container_width=True)
            
            if submitted:
                df = load_db()
                user = df[df['Telefone'] == telefone_login]
                
                if not user.empty:
                    user_data = user.iloc[0].to_dict()
                    stored_pass = user_data['Senha']
                    
                    if stored_pass == hash_pass(senha) or stored_pass == senha:
                        st.session_state['user'] = user_data
                        st.success("Login realizado!")
                        st.rerun()
                    else:
                        st.error("Senha incorreta.")
                else:
                    st.error("Celular não encontrado.")

        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🆘 Resetar Sistema (Apenas Emergência)"):
            confirm_code = st.text_input("Digite 'RESETAR' para confirmar:")
            if st.button("🗑️ DELETAR TUDO", type="primary"):
                if confirm_code == "RESETAR":
                    if os.path.exists(FILE_DB): os.remove(FILE_DB)
                    if os.path.exists(BASE_FILES_DIR): shutil.rmtree(BASE_FILES_DIR)
                    st.session_state.clear()
                    st.rerun()

def screen_admin_dashboard(user):
    st.markdown(f"<h1 class='main-header'>Painel de Gestão</h1>", unsafe_allow_html=True)
    st.write(f"Logado como: **{user['Nome']}** (Administrador)")
    
    tabs = st.tabs(["📊 Visão Geral", "📢 Comunicação", "👥 Gestão de Profissionais", "📤 Arquivos"])
    
    df = load_db()
    users_only = df[df['Role'] != 'admin']
    
    with tabs[0]: # Dashboard
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Profissionais", len(users_only))
        col2.metric("Unidades", df['Unidade'].nunique())
        col3.metric("Cadastros Hoje", len(df[df['Data Cadastro'] == datetime.now().strftime("%Y-%m-%d")]))
        
        st.markdown("---")
        
        # Aniversariantes
        st.subheader("🎂 Aniversariantes do Mês")
        birthdays = []
        for idx, row in users_only.iterrows():
            if check_birthday(row.get('Nascimento')):
                birthdays.append(f"{row['Nome']} ({row['Nascimento'][:5]}) - {row['Unidade']}")
        
        if birthdays:
            for b in birthdays:
                st.success(f"🎉 {b}")
        else:
            st.info("Nenhum aniversariante encontrado para este mês.")

        st.markdown("---")
        st.subheader("Profissionais por Unidade")
        st.bar_chart(df['Unidade'].value_counts())

    with tabs[1]: # Notificações
        st.subheader("Enviar Notificação (Pop-up)")
        
        with st.form("msg_form"):
            tipo_envio = st.radio("Destinatário", ["Todos os Usuários", "Individual"])
            texto_aviso = st.text_area("Mensagem do Aviso")
            
            phone_alvo = None
            if tipo_envio == "Individual":
                if not users_only.empty:
                    escolha = st.selectbox("Selecione:", users_only['Nome'] + " - " + users_only['Telefone'])
                    phone_alvo = escolha.split(" - ")[-1]
            
            if st.form_submit_button("Enviar Aviso"):
                if not texto_aviso:
                    st.error("Escreva uma mensagem.")
                else:
                    if tipo_envio == "Todos os Usuários":
                        qtd = send_notification_to_all(texto_aviso)
                        st.success(f"Mensagem enviada para {qtd} usuários!")
                    else:
                        if send_notification_individual(phone_alvo, texto_aviso):
                            st.success("Mensagem enviada para o usuário!")

    with tabs[2]: # Gestão (CRUD)
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.markdown("### ➕ Cadastrar Novo")
            with st.form("new_user"):
                nome = st.text_input("Nome")
                celular = st.text_input("Celular (Login)")
                senha_temp = st.text_input("Senha Inicial")
                unidade = st.selectbox("Unidade", UNIDADES_OPCOES)
                
                if st.form_submit_button("Criar Cadastro"):
                    if not celular or not nome:
                        st.error("Celular e Nome obrigatórios.")
                    elif celular in df['Telefone'].values:
                        st.error("Celular já cadastrado.")
                    else:
                        new_data = {
                            "Nome": nome, "Telefone": celular, "Senha": senha_temp,
                            "Role": "user", "Unidade": unidade, "Data Cadastro": datetime.now().strftime("%Y-%m-%d"),
                            "Email": "", "Notificacao": "", "Resumo": "", "Nascimento": "", "Pix": "", "Banco": ""
                        }
                        save_user(new_data)
                        ensure_user_dirs(celular)
                        st.success("Cadastrado com sucesso!")
                        st.rerun()
        
        with c2:
            st.markdown("### 📋 Lista de Profissionais")
            
            # Filtro de Busca
            search_term = st.text_input("🔍 Buscar Profissional", placeholder="Digite o nome...")
            
            if users_only.empty:
                st.info("Nenhum profissional cadastrado.")
            else:
                filtered_users = users_only
                if search_term:
                    filtered_users = users_only[users_only['Nome'].str.contains(search_term, case=False, na=False)]
                
                for idx, row in filtered_users.iterrows():
                    with st.expander(f"{row['Nome']} | {row['Unidade']}"):
                        
                        # --- VISUALIZAÇÃO DE DADOS (EMAIL, PIX, RESUMO) ---
                        st.markdown("#### 👤 Dados Cadastrais e Financeiros")
                        vd1, vd2, vd3 = st.columns(3)
                        with vd1:
                            st.caption("E-mail")
                            st.write(row.get('Email') if row.get('Email') else "🚫 Não informado")
                        with vd2:
                            st.caption("Chave PIX")
                            st.write(row.get('Pix') if row.get('Pix') else "🚫 Não informado")
                        with vd3:
                            st.caption("Banco")
                            st.write(row.get('Banco') if row.get('Banco') else "-")
                        
                        st.caption("Resumo Profissional / Técnicas:")
                        if row.get('Resumo'):
                            st.info(row['Resumo'])
                        else:
                            st.warning("Resumo pendente de preenchimento pelo profissional.")

                        st.divider()

                        # Form de Edição
                        with st.form(f"edit_{idx}"):
                            st.write("📝 **Editar Acesso/Unidade**")
                            col_e1, col_e2 = st.columns(2)
                            e_nome = col_e1.text_input("Nome", value=row['Nome'])
                            e_tel = col_e2.text_input("Celular (Login)", value=row['Telefone'])
                            e_unit = st.selectbox("Unidade", UNIDADES_OPCOES, index=UNIDADES_OPCOES.index(row['Unidade']) if row['Unidade'] in UNIDADES_OPCOES else 0)
                            e_pass = st.text_input("Nova Senha (deixe em branco para manter)", type="password")
                            
                            c_save, c_del = st.columns([3, 1])
                            saved = c_save.form_submit_button("💾 Salvar Alterações")
                            
                            if saved:
                                user_updated = row.to_dict()
                                user_updated['Nome'] = e_nome
                                user_updated['Telefone'] = e_tel
                                user_updated['Unidade'] = e_unit
                                if e_pass:
                                    user_updated['Senha'] = e_pass
                                
                                old_phone = row['Telefone']
                                if e_tel != old_phone:
                                    rename_user_dir(old_phone, e_tel)
                                    save_user(user_updated, old_phone_key=old_phone)
                                else:
                                    save_user(user_updated, old_phone_key=old_phone)
                                    
                                st.success("Atualizado!")
                                st.rerun()

                        # Botão Excluir
                        col_del_1, col_del_2 = st.columns([3,1])
                        with col_del_2:
                            if st.button("🗑️ Excluir Conta", key=f"del_{idx}"):
                                delete_user(row['Telefone'])
                                st.warning(f"Usuário {row['Nome']} excluído.")
                                st.rerun()
                        
                        # WhatsApp Link
                        st.markdown("---")
                        phone_clean = clean_phone_number(row['Telefone'])
                        if phone_clean:
                            link_wa = f"https://wa.me/55{phone_clean}"
                            st.markdown(f'<div style="text-align:right"><a href="{link_wa}" target="_blank" class="whatsapp-btn">💬 Conversar no WhatsApp</a></div>', unsafe_allow_html=True)

    with tabs[3]: # Arquivos (Gestão Completa)
        st.subheader("📂 Central de Arquivos")
        
        if not users_only.empty:
            # Seleção de usuário
            destinatario = st.selectbox("Gerenciar arquivos de:", users_only['Nome'] + " - " + users_only['Telefone'])
            phone_dest = destinatario.split(" - ")[-1]
            
            # Paths
            inbox, outbox = ensure_user_dirs(phone_dest) # Inbox: Admin -> User | Outbox: User -> Admin
            
            # Upload Admin
            st.markdown("#### 📤 Enviar novo arquivo")
            file = st.file_uploader("Selecione o documento (PDF/Imagem)", type=['pdf', 'xlsx', 'jpg', 'png'])
            if file and st.button("Enviar Arquivo"):
                if save_uploaded_file(file, inbox):
                    st.success("Arquivo enviado com sucesso!")
                    st.rerun()
            
            st.divider()

            # Gestão de Arquivos Existentes
            col_in, col_out = st.columns(2)
            
            with col_in:
                st.info(f"📂 Enviados pela GESTÃO (Visível para {phone_dest})")
                files_in = get_files(inbox)
                if files_in:
                    for f in files_in:
                        c1, c2 = st.columns([4, 1])
                        c1.text(f"📄 {f}")
                        if c2.button("🗑️", key=f"del_in_{f}"):
                            if delete_file(inbox, f):
                                st.rerun()
                else:
                    st.caption("Nenhum arquivo enviado.")
            
            with col_out:
                st.warning(f"📂 Enviados pelo PROFISSIONAL (Recebidos)")
                files_out = get_files(outbox)
                if files_out:
                    for f in files_out:
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.text(f"📎 {f}")
                        with open(os.path.join(outbox, f), "rb") as d:
                            c2.download_button("⬇️", d, file_name=f, key=f"dl_out_{f}")
                        if c3.button("🗑️", key=f"del_out_{f}"):
                            if delete_file(outbox, f):
                                st.rerun()
                else:
                    st.caption("O profissional ainda não enviou arquivos.")

        else:
            st.warning("Cadastre profissionais primeiro para gerenciar arquivos.")

def screen_user_dashboard(user):
    # Notificação
    if user.get('Notificacao'):
        st.markdown(f"""
        <div style="background-color: #fff3cd; color: #856404; padding: 15px; border-radius: 5px; border: 1px solid #ffeeba; margin-bottom: 20px;">
            <h4>🔔 Novo Aviso da Gestão</h4>
            <p>{user['Notificacao']}</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("✅ Marcar como lida e fechar"):
            clear_notification(user)
            st.rerun()

    st.markdown(f"<h1 class='main-header'>Portal do Colaborador</h1>", unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.markdown(f"### 👤 {user['Nome']}")
    st.sidebar.text(f"Unidade: {user.get('Unidade', '-')}")
    
    df = load_db()
    admin = df[df['Role'] == 'admin'].head(1)
    if not admin.empty:
        admin_phone = clean_phone_number(admin.iloc[0]['Telefone'])
        if admin_phone:
            link_admin = f"https://wa.me/55{admin_phone}"
            st.sidebar.markdown(f"""
                <br><a href="{link_admin}" target="_blank" class="whatsapp-btn" style="display:block; text-align:center;">
                📞 Falar com Gestão
                </a><br>
            """, unsafe_allow_html=True)
    
    if st.sidebar.button("Sair"):
        st.session_state['user'] = None
        st.rerun()

    tabs = st.tabs(["📌 Mural & Calendário", "📂 Documentos", "📝 Perfil Profissional"])

    with tabs[0]:
        st.subheader("📆 Calendário Dez/Jan")
        col1, col2 = st.columns([2, 1])
        
        with col1:
            data_cal = [
                {"Data": "12/12/2025", "Evento": "🎉 Confraternização", "Status": "Confirmado"},
                {"Data": "22/12/2025", "Evento": "🛑 Início Recesso", "Status": "Fechado"},
                {"Data": "25/12/2025", "Evento": "🎄 Natal", "Status": "Feriado"},
                {"Data": "01/01/2026", "Evento": "🎆 Ano Novo", "Status": "Feriado"},
                {"Data": "04/01/2026", "Evento": "🔚 Fim do Recesso", "Status": "Retorno dia 05"},
                {"Data": "05/01/2026", "Evento": "✅ Retorno Atividades", "Status": "Normal"}
            ]
            st.dataframe(pd.DataFrame(data_cal), use_container_width=True)
        
        with col2:
            st.warning("⚠️ **Aviso de Recesso**")
            st.write("A clínica estará fechada de **22/12 a 04/01**.")

    with tabs[1]:
        inbox, outbox = ensure_user_dirs(user['Telefone'])
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 📥 Recebidos")
            st.caption("Arquivos enviados pela Gestão para você.")
            files = get_files(inbox)
            if files:
                for f in files:
                    with open(os.path.join(inbox, f), "rb") as d:
                        st.download_button(f"📄 {f}", d, file_name=f)
            else:
                st.caption("Nenhum arquivo recebido.")
        with c2:
            st.markdown("### 📤 Enviar")
            st.caption("Envie certificados, comprovantes ou fotos para a Gestão.")
            up = st.file_uploader("Upload", key="up_u")
            if up and st.button("Enviar"):
                save_uploaded_file(up, outbox)
                st.success("Enviado!")
            
            st.markdown("#### Histórico de Envios")
            files_out = get_files(outbox)
            for f in files_out:
                st.text(f"✅ {f}")

    with tabs[2]:
        st.subheader("Meu Resumo Profissional")
        st.write("Mantenha seus dados atualizados para que a administração possa gerenciar repasses e direcionamentos.")
        
        with st.form("resumo_form"):
            novo_resumo = st.text_area("Descrição Técnica / Público Alvo", value=user.get('Resumo', ''), height=200, help="Descreva suas especialidades.")
            
            c1, c2 = st.columns(2)
            c_email = c1.text_input("E-mail", value=user.get('Email', ''))
            c_nasc = c2.text_input("Data Nascimento (DD/MM/AAAA)", value=user.get('Nascimento', ''))
            
            c3, c4 = st.columns(2)
            c_pix = c3.text_input("Chave PIX", value=user.get('Pix', ''))
            c_banco = c4.text_input("Banco", value=user.get('Banco', ''))
            
            if st.form_submit_button("Salvar Perfil"):
                user_updated = user.copy()
                user_updated.update({
                    "Resumo": novo_resumo, "Email": c_email, "Pix": c_pix, "Banco": c_banco, "Nascimento": c_nasc
                })
                save_user(user_updated, old_phone_key=user['Telefone'])
                st.session_state['user'] = user_updated
                st.success("Perfil atualizado com sucesso!")

# --- ORQUESTRADOR PRINCIPAL ---

def main():
    init_environment()
    df = load_db()
    
    if df.empty:
        screen_setup_admin()
        return

    if 'user' not in st.session_state or st.session_state['user'] is None:
        screen_login()
    else:
        user = st.session_state['user']
        if user.get('Role') == 'admin':
            screen_admin_dashboard(user)
        else:
            screen_user_dashboard(user)

if __name__ == "__main__":
    main()
