"""Dark / Light mode management via CSS injection."""
from __future__ import annotations

import streamlit as st


DARK_CSS = """
<style>
  .stApp, .stApp * { color-scheme: dark; }
  .stApp { background-color: #0f1117 !important; }
  .stApp p, .stApp span, .stApp label, .stApp div,
  .stApp li, .stApp td, .stApp th { color: #e8eaf0 !important; }
  .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 { color: #f1f3f9 !important; }
  section[data-testid="stSidebar"] { background-color: #12151f !important; }
  section[data-testid="stSidebar"] * { color: #e8eaf0 !important; }
  section[data-testid="stSidebar"] a { color: #a5b4fc !important; }
  .stChatMessage { background-color: #1e2235 !important; border-radius: 12px !important; border: 1px solid #2d3250 !important; }
  .stChatMessage p, .stChatMessage span, .stChatMessage div { color: #e8eaf0 !important; }
  .metric-card {
    background: #1e2235 !important;
    border: 1px solid #2d3250 !important;
    border-radius: 12px !important;
    padding: 1rem 1.25rem !important;
    margin-bottom: .75rem !important;
  }
  .metric-card h4, .metric-card p { color: #e8eaf0 !important; }
  .stButton > button { background: #4f8ef7 !important; color: #fff !important; border-radius: 8px !important; border: none !important; font-weight: 600 !important; }
  .stButton > button:hover { background: #3a7ae0 !important; }
  .stExpander { background: #1e2235 !important; border: 1px solid #2d3250 !important; border-radius: 8px !important; }
  .stExpander summary, .stExpander p { color: #e8eaf0 !important; }
  .stSelectbox label, .stMultiSelect label, .stTextInput label, .stSlider label { color: #e8eaf0 !important; }
  [data-testid="stMetricValue"] { color: #f1f3f9 !important; }
  [data-testid="stMetricLabel"] { color: #9ba4b5 !important; }
  .stDataFrame { border-radius: 8px !important; }
  .stMarkdown p, .stMarkdown li, .stMarkdown span { color: #e8eaf0 !important; }
  .stCaption, .stCaption p { color: #9ba4b5 !important; }
  [data-testid="stSidebarNav"] a span { color: #e8eaf0 !important; }
  /* Marca no topo da barra lateral (acima do menu de navegação) */
  [data-testid="stSidebarNav"]::before {
    content: "SINAN Analytics";
    display: block;
    font-size: 1.1rem; font-weight: 700; letter-spacing: -.4px;
    color: #f1f3f9 !important;
    padding: .15rem 0 .8rem .9rem;
    margin-bottom: .35rem;
    border-bottom: 2px solid;
    border-image: linear-gradient(90deg,#4f8ef7,#22c55e) 1;
  }
  /* Barra superior e rodapé do chat acompanham o fundo escuro */
  header[data-testid="stHeader"] { background: rgba(15,17,23,.85) !important; backdrop-filter: blur(6px); }
  [data-testid="stToolbar"] { color: #e8eaf0 !important; }
  [data-testid="stBottom"] > div,
  [data-testid="stBottomBlockContainer"] { background: #0f1117 !important; }
  [data-testid="stChatInput"] { background: #1e2235 !important; border: 1px solid #2d3250 !important; border-radius: 12px !important; }
  [data-testid="stChatInput"] textarea { color: #e8eaf0 !important; }
</style>
"""

LIGHT_CSS = """
<style>
  .stApp, .stApp * { color-scheme: light; }
  .stApp { background-color: #f8fafc !important; }
  .stApp p, .stApp span, .stApp label, .stApp div,
  .stApp li, .stApp td, .stApp th { color: #1e293b !important; }
  .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 { color: #0f172a !important; }
  section[data-testid="stSidebar"] { background-color: #e8edf5 !important; }
  section[data-testid="stSidebar"] * { color: #1e293b !important; }
  section[data-testid="stSidebar"] a { color: #2563eb !important; }
  .stChatMessage { background-color: #ffffff !important; border-radius: 12px !important; border: 1px solid #e2e8f0 !important; box-shadow: 0 1px 4px rgba(0,0,0,.06) !important; }
  .stChatMessage p, .stChatMessage span, .stChatMessage div { color: #1e293b !important; }
  .metric-card {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    padding: 1rem 1.25rem !important;
    margin-bottom: .75rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,.06) !important;
  }
  .metric-card h4 { color: #0f172a !important; }
  .metric-card p { color: #475569 !important; }
  .stButton > button { background: #3b82f6 !important; color: #fff !important; border-radius: 8px !important; border: none !important; font-weight: 600 !important; }
  .stButton > button:hover { background: #2563eb !important; }
  .stExpander { background: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 8px !important; }
  .stExpander summary, .stExpander p { color: #1e293b !important; }
  .stSelectbox label, .stMultiSelect label, .stTextInput label, .stSlider label { color: #1e293b !important; }
  [data-testid="stMetricValue"] { color: #0f172a !important; }
  [data-testid="stMetricLabel"] { color: #64748b !important; }
  .stDataFrame { border-radius: 8px !important; }
  .stMarkdown p, .stMarkdown li, .stMarkdown span { color: #1e293b !important; }
  .stCaption, .stCaption p { color: #64748b !important; }
  [data-testid="stSidebarNav"] a span { color: #1e293b !important; }
  code { background: #f1f5f9 !important; color: #0f172a !important; }
  /* Marca no topo da barra lateral (acima do menu de navegação) */
  [data-testid="stSidebarNav"]::before {
    content: "SINAN Analytics";
    display: block;
    font-size: 1.1rem; font-weight: 700; letter-spacing: -.4px;
    color: #0f172a !important;
    padding: .15rem 0 .8rem .9rem;
    margin-bottom: .35rem;
    border-bottom: 2px solid;
    border-image: linear-gradient(90deg,#4f8ef7,#22c55e) 1;
  }
  /* Barra superior e rodapé do chat acompanham o fundo claro */
  header[data-testid="stHeader"] { background: rgba(248,250,252,.85) !important; backdrop-filter: blur(6px); }
  [data-testid="stToolbar"] { color: #1e293b !important; }
  [data-testid="stBottom"] > div,
  [data-testid="stBottomBlockContainer"] { background: #f8fafc !important; }
  [data-testid="stChatInput"] { background: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 12px !important; box-shadow: 0 1px 4px rgba(0,0,0,.06) !important; }
  [data-testid="stChatInput"] textarea { color: #1e293b !important; }
  [data-testid="stChatInput"] textarea::placeholder { color: #94a3b8 !important; }
</style>
"""

COMMON_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
  .stChatMessage { animation: fadeIn 0.3s ease-in; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
  .stChatInputContainer textarea { border-radius: 12px !important; font-size: 15px !important; }
  /* Espaço suficiente para o título não ficar sob a barra fixa do topo */
  .block-container { padding-top: 3.25rem !important; }
  .tag { display:inline-block; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; margin-right: 4px; }
  .tag-blue { background: #dbeafe; color: #1d4ed8; }
  .tag-green { background: #dcfce7; color: #166534; }
  .tag-orange { background: #ffedd5; color: #9a3412; }
</style>
"""


def apply_theme() -> None:
    """Inject CSS for the current theme from session_state."""
    theme = st.session_state.get("theme", "dark")
    css = DARK_CSS if theme == "dark" else LIGHT_CSS
    st.markdown(COMMON_CSS + css, unsafe_allow_html=True)


def render_theme_toggle() -> None:
    """Render a toggle button in the sidebar."""
    theme = st.session_state.get("theme", "dark")
    label = "☀️ Light Mode" if theme == "dark" else "🌙 Dark Mode"
    if st.sidebar.button(label, key="theme_toggle", use_container_width=True):
        st.session_state.theme = "light" if theme == "dark" else "dark"
        st.rerun()
