"""SINAN Analytics — entry point / landing page."""
from __future__ import annotations

import streamlit as st

from components.theme import apply_theme
from components.sidebar import render_sidebar
from config.settings import get_settings

st.set_page_config(
    page_title="SINAN Analytics",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "**SINAN Analytics** — Plataforma de análise da base SINAN/SUS "
                 "com IA generativa (AWS Bedrock), geração de SQL e RAG.",
    },
)

if "theme" not in st.session_state:
    st.session_state.theme = "dark"

apply_theme()
render_sidebar()
settings = get_settings()


# ── Helpers ────────────────────────────────────────────────────────────────────
def fmt_br(n: int | float) -> str:
    """Formata número no padrão brasileiro: 1234567 -> '1.234.567'."""
    return f"{n:,.0f}".replace(",", ".")


@st.cache_data(ttl=120, show_spinner=False)
def _check_database() -> tuple[bool, bool]:
    """Retorna (conecta, tem_permissao_schema)."""
    try:
        from database.connection import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT 1 FROM information_schema.tables '
                    'WHERE table_schema = %s LIMIT 1;',
                    (settings.db_schema,),
                )
                has_perm = cur.fetchone() is not None
        return True, has_perm
    except Exception:
        return False, False


def _check_bedrock() -> bool:
    """Verifica se há chave Bedrock válida configurada (sem chamada de rede)."""
    key = settings.bedrock_api_key
    return bool(key) and "XXXX" not in key and len(key) > 30


# ── Page-local styling ─────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
      .hero-wrap { padding: .5rem 0 1.25rem; }
      .hero-mark {
        display:inline-flex; align-items:center; gap:.6rem;
        font-size: 2rem; font-weight: 700; letter-spacing: -.5px;
      }
      .hero-mark .dot {
        width: 14px; height: 14px; border-radius: 4px;
        background: linear-gradient(135deg,#4f8ef7,#22c55e);
        display:inline-block;
      }
      .hero-sub { font-size: 1rem; opacity:.65; margin-top:.35rem; max-width: 640px; }
      .status-pill {
        display:inline-flex; align-items:center; gap:.5rem;
        padding:.45rem .85rem; border-radius:10px; font-size:.85rem; font-weight:600;
        border:1px solid rgba(128,128,128,.25);
      }
      .status-pill .led { width:9px; height:9px; border-radius:50%; }
      .led-on  { background:#22c55e; box-shadow:0 0 8px #22c55e88; }
      .led-off { background:#ef4444; box-shadow:0 0 8px #ef444488; }
      .led-warn{ background:#f59e0b; box-shadow:0 0 8px #f59e0b88; }
      .feat-card {
        border:1px solid rgba(128,128,128,.22);
        border-left:3px solid #4f8ef7;
        border-radius:12px; padding:1.1rem 1.25rem; height:100%;
        transition: transform .15s ease, border-color .15s ease;
        background: rgba(128,128,128,.05);
      }
      .feat-card:hover { transform: translateY(-2px); border-left-color:#22c55e; }
      .feat-card .klabel {
        font-size:.7rem; text-transform:uppercase; letter-spacing:.8px;
        opacity:.55; font-weight:700;
      }
      .feat-card h4 { margin:.35rem 0 .4rem; font-size:1.05rem; }
      .feat-card p  { font-size:.85rem; opacity:.7; line-height:1.45; margin:0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero-wrap">
      <div class="hero-mark"><span class="dot"></span>SINAN Analytics</div>
      <div class="hero-sub">
        Plataforma de análise epidemiológica da base SINAN/SUS — consultas em
        linguagem natural convertidas em SQL auditável, com interpretação por IA.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Connection status row ──────────────────────────────────────────────────────
db_ok, db_perm = _check_database()
bedrock_ok = _check_bedrock()

if bedrock_ok:
    b_led, b_txt = "led-on", "IA · Operacional"
else:
    b_led, b_txt = "led-off", "IA · Não configurada"

if db_ok and db_perm:
    d_led, d_txt = "led-on", "Banco · Conectado"
elif db_ok and not db_perm:
    d_led, d_txt = "led-warn", "Banco · Sem permissão no schema"
else:
    d_led, d_txt = "led-off", "Banco · Offline"

s1, s2, _sp = st.columns([1.1, 1.4, 3])
with s1:
    st.markdown(
        f'<span class="status-pill"><span class="led {b_led}"></span>{b_txt}</span>',
        unsafe_allow_html=True,
    )
with s2:
    st.markdown(
        f'<span class="status-pill"><span class="led {d_led}"></span>{d_txt}</span>',
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

# ── KPI strip (fatos reais do dataset) ─────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Tabelas catalogadas", fmt_br(len(settings.sinan_tables)))
k2.metric("Campos no dicionário", fmt_br(70))
k3.metric("Agravos monitorados", "3", help="Dengue, Botulismo e Doença de Chagas")
k4.metric("Municípios cobertos", fmt_br(5570), help="Cobertura nacional via código IBGE")

st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
st.divider()

# ── Feature grid ───────────────────────────────────────────────────────────────
st.markdown("##### Recursos da plataforma")

features = [
    ("Análise", "Chat Analítico",
     "Pergunte em português. O agente identifica as tabelas, gera o SQL, "
     "executa e interpreta o resultado com gráficos."),
    ("Catálogo", "Dicionário de Dados",
     "Metadados completos das tabelas SINAN: tipos, descrições e exemplos "
     "de cada um dos campos disponíveis."),
    ("Exploração", "Painel Epidemiológico",
     "Indicadores, séries temporais e recortes por UF, ano e faixa "
     "demográfica para os três agravos."),
    ("Governança", "Monitoramento",
     "Auditoria de consultas, consumo de tokens, custo estimado e "
     "latência — rastreabilidade ponta a ponta."),
]

cols = st.columns(4)
for col, (label, title, desc) in zip(cols, features):
    with col:
        st.markdown(
            f"""
            <div class="feat-card">
              <div class="klabel">{label}</div>
              <h4>{title}</h4>
              <p>{desc}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

# ── Guidance / next step ───────────────────────────────────────────────────────
if not bedrock_ok:
    st.warning(
        "Configure a chave AWS Bedrock em **Configurações** para habilitar o chat analítico.",
        icon="⚙️",
    )
elif db_ok and not db_perm:
    st.info(
        f"A IA está pronta, mas o usuário `{settings.db_user}` ainda não tem permissão "
        f"de leitura no schema `{settings.db_schema}`. Solicite ao administrador:\n\n"
        f"```sql\nGRANT USAGE ON SCHEMA \"{settings.db_schema}\" TO {settings.db_user};\n"
        f"GRANT SELECT ON ALL TABLES IN SCHEMA \"{settings.db_schema}\" TO {settings.db_user};\n```",
        icon="🔐",
    )
else:
    st.success("Tudo pronto. Abra o **Chat Analítico** na barra lateral para começar.", icon="✓")

st.divider()
st.caption("AWS Bedrock · LangGraph · ChromaDB · PostgreSQL")
