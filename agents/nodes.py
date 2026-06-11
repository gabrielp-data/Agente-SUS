"""LangGraph node functions for the SINAN agent."""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from config.settings import get_settings
from database.connection import execute_query
from database.schema_loader import schema_to_prompt
from rag.retriever import RAGRetriever
from services.bedrock_service import BedrockService
from utils.logger import get_logger
from utils.sql_validator import sanitize_sql, validate_sql

logger = get_logger("agents.nodes")

_bedrock = BedrockService()
_rag = RAGRetriever()
settings = get_settings()

# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_json(text: str) -> dict:
    """Parse JSON from LLM output, handling markdown code fences."""
    for pattern in [r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```"]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    return json.loads(text)


def _format_history(history: list[dict]) -> list[dict]:
    """Convert chat history to Bedrock message format (last 6 turns)."""
    messages = []
    for turn in history[-6:]:
        messages.append({"role": "user",      "content": [{"text": turn["question"]}]})
        messages.append({"role": "assistant", "content": [{"text": turn["answer"]}]})
    return messages


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


# Saudações isoladas e padrões de perguntas sobre a própria conversa
_GREETINGS = {
    "oi", "ola", "ei", "eai", "e ai", "bom dia", "boa tarde", "boa noite",
    "obrigado", "obrigada", "valeu", "tudo bem", "tudo bom",
}
_CONVERSATIONAL_PATTERNS = [
    "ultima pergunta", "ultima questao", "que eu perguntei", "que perguntei",
    "perguntei antes", "pergunta anterior", "perguntas anteriores",
    "o que voce disse", "que voce falou", "voce falou", "voce ja disse",
    "voce disse antes", "disse antes", "respondeu antes", "resposta anterior",
    "ultima resposta", "minha primeira pergunta", "primeira pergunta",
    "resuma", "resumo da conversa", "nossa conversa", "do que falamos",
    "do que conversamos", "sobre o que conversamos", "historico",
    "quem e voce", "o que voce faz", "o que voce pode fazer", "como voce funciona",
    "para que voce serve", "o que voce e", "voce lembra",
]


def _is_conversational(question: str) -> bool:
    """Detecta perguntas sobre a própria conversa / saudações (não são consultas a dados)."""
    q = _strip_accents(question.lower()).strip()
    q_clean = q.rstrip("!?.,; ")
    if q_clean in _GREETINGS:
        return True
    return any(pat in q for pat in _CONVERSATIONAL_PATTERNS)


# ── Node functions ────────────────────────────────────────────────────────────


def analyze_intent(state: dict) -> dict:
    """Classify the question and identify candidate tables."""
    question = state["question"]

    # Atalho: pergunta conversacional (sobre a conversa, saudação) — não vira SQL
    if _is_conversational(question):
        state["intent"] = "conversational"
        state["disease"] = "geral"
        state["selected_tables"] = []
        state["needs_chart"] = False
        state["chart_type"] = "none"
        state["steps"].append("✅ Pergunta conversacional — respondendo pelo histórico")
        return state

    rag_tables = _rag.get_relevant_tables(question)

    system = """Você é um especialista em dados de saúde pública do Brasil (SINAN/SUS).
Analise a pergunta e retorne JSON:
{
  "intent": "aggregation|trend|comparison|detail|ranking|conversational|unknown",
  "disease": "dengue|botulismo|chagas|geral",
  "tables": ["lista das tabelas mais relevantes"],
  "needs_chart": true,
  "chart_type": "bar|line|pie|heatmap|scatter|none",
  "complexity": "simple|medium|complex"
}

REGRA IMPORTANTE sobre "conversational":
Use intent="conversational" SOMENTE quando a pergunta for sobre a PRÓPRIA CONVERSA
ou interação social, e NÃO sobre os dados. Exemplos (incluindo com erros de digitação):
- "qual foi a última pergunta?" / "qual foi minha ultima pergnta?"
- "o que você disse antes?" / "resuma nossa conversa"
- "oi", "bom dia", "obrigado", "o que você faz?", "quem é você?"
Nesses casos deixe "tables" como [] e "needs_chart" false.
Para QUALQUER pergunta que envolva números, casos, anos, óbitos, municípios ou
comparações entre dados, use os outros intents (NUNCA conversational)."""

    tables_hint = "\n".join(f"- {t}" for t in settings.sinan_tables)
    rag_hint = "\n".join(f"- {t}" for t in rag_tables) if rag_tables else "(nenhuma identificada)"

    user_text = f"""Pergunta: {question}

Tabelas disponíveis:
{tables_hint}

Tabelas sugeridas pelo RAG:
{rag_hint}"""

    history_msgs = _format_history(state.get("chat_history", []))
    messages = history_msgs + [{"role": "user", "content": [{"text": user_text}]}]

    try:
        raw, usage = _bedrock.invoke(messages, system, max_tokens=512)
        parsed = _extract_json(raw)
    except Exception as exc:
        logger.warning("analyze_intent falhou: %s", exc)
        parsed = {
            "intent": "unknown",
            "disease": "geral",
            "tables": rag_tables or settings.sinan_tables[:2],
            "needs_chart": False,
            "chart_type": "none",
            "complexity": "simple",
        }
        usage = {}

    state["intent"] = parsed.get("intent", "unknown")
    state["disease"] = parsed.get("disease", "geral")
    state["selected_tables"] = parsed.get("tables", settings.sinan_tables[:2])
    state["needs_chart"] = parsed.get("needs_chart", False)
    state["chart_type"] = parsed.get("chart_type", "none")
    state["steps"].append(f"✅ Intenção: {state['intent']} | Tabelas: {state['selected_tables']}")
    state["total_input_tokens"] = state.get("total_input_tokens", 0) + usage.get("input_tokens", 0)
    state["total_output_tokens"] = state.get("total_output_tokens", 0) + usage.get("output_tokens", 0)
    return state


def query_rag(state: dict) -> dict:
    """Retrieve relevant dictionary context."""
    context = _rag.retrieve(state["question"])
    state["rag_context"] = context
    state["steps"].append("✅ Dicionário consultado via RAG")
    return state


def generate_sql(state: dict) -> dict:
    """Generate a PostgreSQL SELECT statement."""
    schema_text = schema_to_prompt(state.get("db_schema", {}))
    rag_context = state.get("rag_context", "")
    history = _format_history(state.get("chat_history", []))

    system = f"""Você é um especialista em SQL para bases de dados de saúde pública brasileira (SINAN/SUS).

Schema disponível:
{schema_text}

{rag_context}

=== REGRAS CRÍTICAS DA BASE SINAN ===

ESTRUTURA REAL DAS TABELAS:
- Todas as tabelas usam codigo_municipio (bpchar 6 dígitos IBGE, SEM dígito verificador)
- Não existe coluna de nome do município nem de UF — use o código IBGE
- ano e mes são CHAR, não inteiros — compare como string: ano = '2023', mes = '03'
- Tabelas mensais: métrica principal = casos_mes
- Tabelas anuais: métrica principal = casos_ano (+ breakdowns de zona, faixa_etaria, sexo, raca, evolucao)
- tipo_municipio é um ENUM — para totais nacionais/estaduais, filtre pelo valor correto

FILTROS POR LOCALIDADE:
- Por UF: LEFT(codigo_municipio, 2) = '<codigo_uf>'
  Exemplos: DF='53', SP='35', RJ='33', MG='31', BA='29', CE='23', PR='41', RS='43', PE='26'
- Por município específico (use o código IBGE de 6 dígitos):
  Brasília: '530010' | São Paulo: '355030' | Rio de Janeiro: '330455'
  BH: '310620' | Salvador: '292740' | Fortaleza: '230440' | Curitiba: '410690'
  Manaus: '130260' | Recife: '261160' | Porto Alegre: '431490' | Goiânia: '520870'
- Se o usuário mencionar uma cidade que não está na lista acima, use: codigo_municipio LIKE '<2_primeiros_digitos_uf>%'

SÉRIE HISTÓRICA:
- Para dados recentes use sus_sinan_dengue_mensal / sus_sinan_dengue_anual
- Para dados históricos/antigos use sus_sinan_dengue_antigo_mensal / sus_sinan_dengue_antigo_anual
- Para série completa, faça UNION ALL das tabelas antigo + atual

REGRAS GERAIS:
1. Gere apenas SELECT/WITH — nunca DELETE, UPDATE, DROP, INSERT, ALTER
2. SEMPRE use o schema qualificado: FROM "SUS_SINAN".sus_sinan_dengue_mensal
   Exemplos corretos:
   - FROM "SUS_SINAN".sus_sinan_dengue_mensal
   - FROM "SUS_SINAN".sus_sinan_dengue_anual
   - JOIN "SUS_SINAN".sus_sinan_dengue_antigo_mensal
   NUNCA escreva apenas: FROM sus_sinan_dengue_mensal (sem schema causa erro)
3. Use SUM(casos_mes) ou SUM(casos_ano) para agregações — os valores podem ser NULL
4. Adicione LIMIT {settings.max_sql_rows} quando não for uma agregação
5. Para ordenar por UF, use LEFT(codigo_municipio, 2) AS uf

Retorne SOMENTE um JSON válido no formato:
{{
  "sql": "SELECT ...",
  "tables_used": ["tabela1"],
  "columns_used": ["col1", "col2"],
  "filters_applied": ["filtro1"],
  "explanation": "O que essa query faz"
}}"""

    question_with_context = state["question"]
    messages = history + [{"role": "user", "content": [{"text": question_with_context}]}]

    try:
        raw, usage = _bedrock.invoke(messages, system, max_tokens=1024)
        parsed = _extract_json(raw)
        sql = parsed.get("sql", "")
    except Exception as exc:
        logger.error("generate_sql falhou: %s", exc)
        state["sql_error"] = str(exc)
        state["sql"] = ""
        return state

    state["sql"] = sanitize_sql(sql)
    state["tables_used"] = parsed.get("tables_used", [])
    state["columns_used"] = parsed.get("columns_used", [])
    state["filters_applied"] = parsed.get("filters_applied", [])
    state["sql_explanation"] = parsed.get("explanation", "")
    state["steps"].append(f"✅ SQL gerado")
    state["total_input_tokens"] = state.get("total_input_tokens", 0) + usage.get("input_tokens", 0)
    state["total_output_tokens"] = state.get("total_output_tokens", 0) + usage.get("output_tokens", 0)
    return state


def validate_sql_node(state: dict) -> dict:
    """Validate SQL safety."""
    sql = state.get("sql", "")
    is_valid, error_msg = validate_sql(sql)
    state["sql_valid"] = is_valid
    if not is_valid:
        state["sql_error"] = error_msg
        state["steps"].append(f"❌ SQL inválido: {error_msg}")
    else:
        state["sql_error"] = ""
        state["steps"].append("✅ SQL validado")
    return state


def execute_sql_node(state: dict) -> dict:
    """Execute the SQL against PostgreSQL."""
    sql = state.get("sql", "")
    df, error = execute_query(sql)
    if error:
        state["execution_error"] = error
        state["results"] = None
        state["steps"].append(f"❌ Erro na execução: {error[:80]}")
    else:
        state["execution_error"] = ""
        state["results"] = df
        state["steps"].append(f"✅ Consulta executada — {len(df)} linhas retornadas")
    return state


def fix_sql_node(state: dict) -> dict:
    """Ask the LLM to fix a SQL that errored on execution."""
    retry = state.get("retry_count", 0)
    if retry >= 2:
        state["steps"].append("❌ Número máximo de tentativas de correção atingido")
        return state

    schema_text = schema_to_prompt(state.get("db_schema", {}))
    error = state.get("execution_error", "")

    system = f"""Você é um especialista em SQL PostgreSQL para bases SINAN/SUS.
Schema:
{schema_text}

O SQL abaixo gerou o seguinte erro no banco. Corrija-o.
Retorne SOMENTE JSON no formato:
{{"sql": "SELECT corrigido...", "explanation": "o que foi corrigido"}}"""

    user_text = f"""Pergunta original: {state['question']}

SQL com erro:
{state['sql']}

Erro retornado:
{error}"""

    try:
        raw, usage = _bedrock.invoke(
            [{"role": "user", "content": [{"text": user_text}]}],
            system, max_tokens=1024,
        )
        parsed = _extract_json(raw)
        state["sql"] = sanitize_sql(parsed.get("sql", state["sql"]))
        state["sql_explanation"] = parsed.get("explanation", "")
        state["retry_count"] = retry + 1
        state["steps"].append(f"🔄 SQL corrigido (tentativa {retry + 1})")
        state["total_input_tokens"] = state.get("total_input_tokens", 0) + usage.get("input_tokens", 0)
        state["total_output_tokens"] = state.get("total_output_tokens", 0) + usage.get("output_tokens", 0)
    except Exception as exc:
        logger.error("fix_sql falhou: %s", exc)
        state["steps"].append(f"❌ Correção do SQL falhou: {exc}")

    return state


def generate_chart_node(state: dict) -> dict:
    """Determine and build the Plotly chart if appropriate."""
    df = state.get("results")
    if df is None or df.empty or not state.get("needs_chart", False):
        state["chart"] = None
        return state

    chart_type = state.get("chart_type", "bar")

    try:
        import plotly.express as px
        import plotly.graph_objects as go

        fig = None
        cols = list(df.columns)

        # Identify numeric and categorical columns
        num_cols = df.select_dtypes(include="number").columns.tolist()
        cat_cols = df.select_dtypes(exclude="number").columns.tolist()

        if chart_type == "line" and len(num_cols) >= 1 and len(cat_cols) >= 1:
            fig = px.line(df, x=cat_cols[0], y=num_cols[0], title="Evolução temporal",
                          template="plotly_dark")
        elif chart_type == "pie" and len(num_cols) >= 1 and len(cat_cols) >= 1:
            fig = px.pie(df, names=cat_cols[0], values=num_cols[0], title="Distribuição",
                         template="plotly_dark")
        elif chart_type == "heatmap" and len(num_cols) >= 1:
            fig = px.imshow(df[num_cols], title="Heatmap", template="plotly_dark")
        elif len(num_cols) >= 1 and len(cat_cols) >= 1:
            fig = px.bar(df, x=cat_cols[0], y=num_cols[0], title="Resultado",
                         template="plotly_dark", color=cat_cols[0] if len(cat_cols) > 0 else None)
        elif len(num_cols) >= 2:
            fig = px.scatter(df, x=num_cols[0], y=num_cols[1], title="Dispersão",
                             template="plotly_dark")

        if fig:
            fig.update_layout(
                margin={"l": 20, "r": 20, "t": 40, "b": 20},
                font={"family": "Inter, sans-serif"},
            )

        state["chart"] = fig
        state["steps"].append(f"✅ Gráfico {chart_type} gerado")
    except Exception as exc:
        logger.warning("Erro ao gerar gráfico: %s", exc)
        state["chart"] = None

    return state


def conversational_answer_node(state: dict) -> dict:
    """Responde perguntas sobre a própria conversa / saudações, sem gerar SQL."""
    question = state["question"]
    history = state.get("chat_history", [])

    if history:
        linhas = []
        for i, turn in enumerate(history, 1):
            linhas.append(f"{i}. Usuário perguntou: {turn.get('question', '')}")
            resposta = (turn.get("answer", "") or "").strip()
            linhas.append(f"   Você respondeu: {resposta[:400]}")
        transcript = "\n".join(linhas)
    else:
        transcript = "(ainda não há perguntas anteriores nesta conversa)"

    system = """Você é o assistente do SINAN Analytics, especializado em dados de
saúde pública do Brasil (dengue, botulismo, doença de Chagas).
O usuário fez uma pergunta sobre a PRÓPRIA CONVERSA ou uma saudação — isso NÃO é
uma consulta a dados. Responda de forma breve, cordial e em português, usando o
histórico abaixo quando for relevante. Nunca invente dados nem gere SQL.
Se ele perguntar o que você faz, explique que pode responder perguntas sobre os
dados do SINAN gerando SQL automaticamente."""

    user_text = f"""Histórico da conversa até agora:
{transcript}

Pergunta atual do usuário: {question}

Responda diretamente, com base no histórico."""

    try:
        answer, usage = _bedrock.invoke(
            [{"role": "user", "content": [{"text": user_text}]}],
            system, max_tokens=512,
        )
        state["total_input_tokens"] = state.get("total_input_tokens", 0) + usage.get("input_tokens", 0)
        state["total_output_tokens"] = state.get("total_output_tokens", 0) + usage.get("output_tokens", 0)
    except Exception as exc:
        logger.error("conversational_answer falhou: %s", exc)
        answer = "Desculpe, não consegui processar agora. Pode tentar de novo?"

    state["answer"] = answer
    state["sql"] = ""
    state["results"] = None
    state["chart"] = None
    state["tables_used"] = []
    state["filters_applied"] = []
    state["steps"].append("✅ Resposta conversacional gerada")
    return state


def generate_answer_node(state: dict) -> dict:
    """Generate a natural language answer based on the query results."""
    question = state["question"]
    sql = state.get("sql", "")
    df = state.get("results")
    error = state.get("execution_error", "")

    if error and df is None:
        state["answer"] = (
            f"❌ Não foi possível executar a consulta após {state.get('retry_count', 0) + 1} tentativa(s).\n\n"
            f"**Erro:** {error}"
        )
        return state

    if df is None or df.empty:
        state["answer"] = "Nenhum dado foi encontrado para essa consulta. Tente reformular a pergunta."
        return state

    n_rows = len(df)
    preview = df.head(15).to_string() if n_rows > 15 else df.to_string()
    extra = f"\n*(e mais {n_rows - 15} linhas)*" if n_rows > 15 else ""

    system = """Você é um analista especializado em dados de saúde pública brasileira (SINAN/SUS).
Responda em português, de forma clara, objetiva e profissional.
Use markdown: **negrito** para números relevantes, listas quando necessário.
Destaque padrões, tendências ou anomalias nos dados."""

    user_text = f"""Pergunta: {question}

SQL executado:
```sql
{sql}
```

Resultado ({n_rows} linhas):
{preview}{extra}

Responda à pergunta com base nos dados acima. Destaque os principais números e insights."""

    history = _format_history(state.get("chat_history", []))
    messages = history + [{"role": "user", "content": [{"text": user_text}]}]

    try:
        answer, usage = _bedrock.invoke(messages, system, max_tokens=2048)
        state["total_input_tokens"] = state.get("total_input_tokens", 0) + usage.get("input_tokens", 0)
        state["total_output_tokens"] = state.get("total_output_tokens", 0) + usage.get("output_tokens", 0)
    except Exception as exc:
        logger.error("generate_answer falhou: %s", exc)
        answer = f"Consulta executada com sucesso ({n_rows} linhas retornadas), mas não foi possível gerar a interpretação: {exc}"

    state["answer"] = answer
    state["steps"].append("✅ Resposta gerada")
    return state
