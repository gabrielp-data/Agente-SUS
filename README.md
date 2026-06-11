# SINAN Analytics

> Plataforma de análise epidemiológica da base **SINAN/SUS** com IA generativa.
> Pergunte em português; o agente gera **SQL auditável**, executa no PostgreSQL
> e interpreta o resultado com gráficos.

![CI](https://github.com/gabrielp-data/Agente-SUS/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.49+-FF4B4B)
![License](https://img.shields.io/badge/license-MIT-green)

**Stack:** Streamlit · AWS Bedrock (Claude Sonnet 4.6) · LangGraph · PostgreSQL · Plotly

---

## Demonstração

> _Substitua por um GIF/print real:_ `docs/demo.gif`

| Chat Analítico | Painel Epidemiológico |
|---|---|
| Pergunta → SQL → resposta + gráfico | Indicadores e séries por UF/ano |

Cobre dados reais de **dengue, botulismo e doença de Chagas** — ~1,1 milhão de
registros municipais, série histórica de **2007 a 2026**.

---

## Como funciona (pipeline LangGraph)

```
Pergunta
   │
   ▼
analyze_intent ─── conversacional? ──► conversational_answer ──► fim
   │ (consulta a dados)                  (responde do histórico/catálogo)
   ▼
query_rag           busca leve no dicionário SINAN (sem dependências pesadas)
   ▼
generate_sql        Claude gera SQL  (máx. 2 tentativas)
   ▼
validate_sql        bloqueia DELETE/UPDATE/DROP/... — só SELECT/WITH
   ▼
execute_sql ─── erro corrigível? ──► fix_sql ──► execute_sql (máx. 2x)
   ▼
generate_chart      Plotly automático (bar/line/pie), siglas de UF
   ▼
generate_answer     interpretação em streaming
```

---

## Decisões de arquitetura

- **Busca no dicionário sem banco vetorial.** O RAG inicial usava ChromaDB, mas
  ele exigia `sqlite ≥ 3.35`, casava versões de `protobuf` e baixava um modelo de
  embeddings — tudo isso para buscar em ~70 campos estáticos. Troquei por uma
  busca por sobreposição de termos em memória: zero dependências pesadas,
  instantânea e suficiente para o domínio.
- **SQL sempre auditável.** Toda resposta expõe o SQL gerado. Um validador
  (`utils/sql_validator.py`) recusa qualquer operação de escrita e qualifica as
  tabelas com o schema antes de executar.
- **Defesa em profundidade.** Usuário de banco read-only, `statement_timeout`,
  `LIMIT` forçado no servidor, página de credenciais protegida por senha e
  limites de uso por sessão (app público).
- **Tema dark/light real.** Tabelas e gráficos seguem o tema; o que o Streamlit
  não permite trocar ao vivo (canvas) é renderizado como HTML temático.

---

## Estrutura

```
agente-sus/
├── app.py                  # roteador (st.navigation)
├── views/                  # páginas (Início, Chat, Painel, Dicionário, ...)
├── agents/                 # grafo LangGraph + nós (intenção, SQL, resposta)
├── services/               # Bedrock (Converse + streaming), monitoramento
├── database/               # pool de conexões, schema loader
├── rag/                    # índice e busca em memória do dicionário
├── components/             # tema, sidebar, helpers de UI
├── utils/                  # validador SQL, auth, geo (UF), logger
├── data/                   # dicionário SINAN (JSON)
└── tests/                  # pytest (validador, RAG, formatação, geo)
```

---

## Rodando localmente

```bash
git clone https://github.com/gabrielp-data/Agente-SUS.git
cd Agente-SUS
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # edite com suas credenciais
streamlit run app.py
```

Acesse **http://localhost:8501**.

### Deploy no Streamlit Cloud
Configure as variáveis em **Settings → Secrets** (modelo em
`.streamlit/secrets.toml.example`). Defina **`ADMIN_PASSWORD`** para proteger a
página de Configurações.

---

## Testes

```bash
pip install pytest
pytest tests/ -q
```

53 testes cobrindo o validador de SQL, a busca do dicionário, a detecção
conversacional, a formatação BR e os mapeamentos de UF. CI no GitHub Actions
roda lint (`ruff`) + testes a cada push.

---

## Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `BEDROCK_API_KEY` | Chave da API do Bedrock |
| `BEDROCK_ENDPOINT` | Endpoint Bedrock Runtime (define a região) |
| `BEDROCK_MODEL_ID` | Modelo (padrão `us.anthropic.claude-sonnet-4-6`) |
| `BEDROCK_FAST_MODEL_ID` | Modelo rápido para etapas leves (opcional) |
| `DB_HOST` / `DB_PORT` / `DB_NAME` | Conexão PostgreSQL |
| `DB_SCHEMA` | Schema das tabelas SINAN (`SUS_SINAN`) |
| `DB_USER` / `DB_PASSWORD` | Credenciais (read-only recomendado) |
| `ADMIN_PASSWORD` | Senha das páginas restritas (obrigatória em produção) |
| `MAX_SQL_ROWS` / `SQL_TIMEOUT` | Limites de consulta |

---

## Tabelas

| Tabela | Agravo | Granularidade |
|---|---|---|
| `sus_sinan_dengue_anual` | Dengue | Anual (+ sexo, faixa etária, raça, evolução) |
| `sus_sinan_dengue_mensal` | Dengue | Mensal |
| `sus_sinan_dengue_antigo_anual` | Dengue (2007–2013) | Anual |
| `sus_sinan_dengue_antigo_mensal` | Dengue (2007–2013) | Mensal |
| `sus_sinan_botulismo_mensal` | Botulismo | Mensal |
| `sus_sinan_chagas_mensal` | Doença de Chagas | Mensal |

---

## Licença

MIT.
