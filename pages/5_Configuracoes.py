"""⚙️ Configurações — gerenciamento de credenciais e conexões."""
from __future__ import annotations

import streamlit as st

from components.sidebar import render_sidebar
from components.theme import apply_theme
from components.ui import page_header
from config.settings import get_settings, _ENV_PATH
from database.connection import test_connection
from services.bedrock_service import BedrockService

st.set_page_config(page_title="Configurações | SINAN Analytics", page_icon="◆", layout="wide")
apply_theme()
render_sidebar()

settings = get_settings()
bedrock = BedrockService()


def _mask(value: str, show_last: int = 4) -> str:
    if not value:
        return ""
    return "*" * max(0, len(value) - show_last) + value[-show_last:]


page_header(
    "Configurações",
    "Credenciais, modelos e conexões — sem alterar código",
)
st.caption(f"Arquivo `.env`: `{_ENV_PATH}`")

# Status da chave atual
_current_key = settings.bedrock_api_key
_key_ok = _current_key and "XXXX" not in _current_key and len(_current_key) > 30
if _key_ok:
    st.success(f"🔑 Chave Bedrock configurada: `{_current_key[:20]}...{_current_key[-6:]}` — "
               f"lembre-se: expira em **12h**, gere uma nova se der 403.")
else:
    st.warning("⚠️ **Nenhuma chave Bedrock válida configurada.** Cole a chave no campo abaixo e salve.")

# ── Bedrock ───────────────────────────────────────────────────────────────────
st.markdown("##### AWS Bedrock")

with st.form("form_bedrock"):
    st.markdown("**Método de autenticação**")
    auth_method = st.radio(
        "Escolha como autenticar",
        ["API Key (chave única — recomendado)", "Credenciais AWS completas"],
        horizontal=True,
        index=0 if settings.use_api_key else 1,
        label_visibility="collapsed",
    )

    if "API Key" in auth_method:
        st.info(
            "Para atualizar a chave: **apague** o campo abaixo e **cole** a nova chave "
            "(gerada em AWS Console → Bedrock → API Keys → Criar chave de curto prazo)."
        )
        api_key = st.text_input(
            "Bedrock API Key",
            value=_mask(settings.bedrock_api_key) if _key_ok else "",
            type="password",
            placeholder="bedrock-api-key-XXXXXXXX",
            help="Chave no formato bedrock-api-key-XXXX gerada no console AWS Bedrock",
        )
    else:
        col1, col2 = st.columns(2)
        with col1:
            aws_key_id = st.text_input("AWS Access Key ID", value=_mask(settings.aws_access_key_id or ""), type="password")
            aws_token = st.text_input("AWS Session Token (opcional)", value=_mask(settings.aws_session_token or ""), type="password")
        with col2:
            aws_secret = st.text_input("AWS Secret Access Key", value=_mask(settings.aws_secret_access_key or ""), type="password")
            aws_region = st.text_input("AWS Region", value=settings.aws_region)

    st.markdown("**Endpoint e Modelo**")
    col_e, col_m = st.columns(2)
    with col_e:
        endpoint = st.text_input("Endpoint URL", value=settings.bedrock_endpoint)
    with col_m:
        model_names = list(settings.available_models.keys())
        current_name = next(
            (k for k, v in settings.available_models.items() if v == settings.bedrock_model_id),
            model_names[0],
        )
        model_label = st.selectbox("Modelo", model_names, index=model_names.index(current_name))
        model_id = settings.available_models[model_label]

    saved = st.form_submit_button("💾 Salvar credenciais", type="primary", use_container_width=True)

if saved:
    updates: dict[str, str] = {
        "BEDROCK_ENDPOINT": endpoint,
        "BEDROCK_MODEL_ID": model_id,
    }
    if "API Key" in auth_method and api_key and not api_key.startswith("*"):
        updates["BEDROCK_API_KEY"] = api_key.strip()
    elif "Credenciais" in auth_method:
        if aws_key_id and not aws_key_id.startswith("***"):
            updates["AWS_ACCESS_KEY_ID"] = aws_key_id
        if aws_secret and not aws_secret.startswith("***"):
            updates["AWS_SECRET_ACCESS_KEY"] = aws_secret
        if aws_token and not aws_token.startswith("***"):
            updates["AWS_SESSION_TOKEN"] = aws_token
        updates["AWS_REGION"] = aws_region

    settings.save_to_env(updates)
    saved_keys = list(updates.keys())
    st.success(f"✅ Salvo: {', '.join(saved_keys)} → `{_ENV_PATH}`")
    st.rerun()

# Test Bedrock connection
if st.button("Testar conexão Bedrock", use_container_width=False):
    with st.spinner("Testando..."):
        ok, msg = bedrock.test_connection()
    if ok:
        st.success(msg)
    else:
        st.error(msg)

st.divider()

# ── PostgreSQL ────────────────────────────────────────────────────────────────
st.markdown("##### Banco de Dados — PostgreSQL")

with st.form("form_db"):
    c1, c2 = st.columns(2)
    with c1:
        db_host = st.text_input("Host", value=settings.db_host)
        db_name = st.text_input("Database", value=settings.db_name)
        db_user = st.text_input("Usuário", value=settings.db_user)
    with c2:
        db_port = st.text_input("Porta", value=str(settings.db_port))
        db_pass = st.text_input("Senha", value=_mask(settings.db_password), type="password")

    db_saved = st.form_submit_button("💾 Salvar conexão", use_container_width=True)

if db_saved:
    updates = {
        "DB_HOST": db_host, "DB_PORT": db_port, "DB_NAME": db_name, "DB_USER": db_user,
    }
    if db_pass and not db_pass.startswith("***"):
        updates["DB_PASSWORD"] = db_pass
    settings.save_to_env(updates)
    st.success("✅ Conexão do banco salva.")

if st.button("Testar conexão PostgreSQL", use_container_width=False):
    with st.spinner("Conectando..."):
        ok, msg = test_connection()
    if ok:
        st.success(f"✅ Conectado — {msg[:120]}")
    else:
        st.error(f"❌ {msg}")

st.divider()

# ── Advanced ──────────────────────────────────────────────────────────────────
st.markdown("##### Configurações Avançadas")
with st.form("form_advanced"):
    c1, c2 = st.columns(2)
    with c1:
        max_rows = st.slider("Máximo de linhas por consulta", 100, 5000, settings.max_sql_rows, 100)
    with c2:
        sql_timeout = st.slider("Timeout SQL (segundos)", 5, 120, settings.sql_timeout, 5)
    if st.form_submit_button("💾 Salvar", use_container_width=True):
        settings.save_to_env({"MAX_SQL_ROWS": str(max_rows), "SQL_TIMEOUT": str(sql_timeout)})
        st.success("✅ Configurações avançadas salvas.")

st.divider()
st.caption(
    f"ℹ️ Credenciais salvas em: `{_ENV_PATH}`  "
    "| Nunca são enviadas a terceiros  "
    "| Chaves de curto prazo expiram em 12h — gere uma nova se der 403."
)
