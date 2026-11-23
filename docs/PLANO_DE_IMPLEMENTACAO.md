# Plano de implementação: healthwatch-srag-agent

Este documento registra o roteiro de implementação do projeto, dividido em fases. Ele foi elaborado a partir das orientações da autora, com uma análise de viabilidade feita com o Claude (Anthropic) e revisada pela autora. Cada fase tem uma branch própria e é integrada por pull request.

**Escolhas já feitas:** Windows, Claude Haiku (pago), CLI + Streamlit, uv. Os motivos de cada decisão estão em `docs/DECISIONS.md`.

---

## Visão geral das fases

| Fase | O que entrega | Critério de avaliação principal | Esforço estimado |
|---|---|---|---|
| 0 | Programas instalados, contas e chaves criadas | — | 1 a 2 h |
| 1 | Repositório estruturado, testes e CI funcionando | Clean code | 2 h |
| 2 | Dados baixados, explorados e limpos | Dados sensíveis | 4 a 6 h |
| 3 | 4 métricas calculadas e testadas | Arquitetura, clean code | 3 h |
| 4 | 2 gráficos | — | 2 h |
| 5 | Ferramenta de notícias com filtros | Guardrails | 3 h |
| 6 | Auditoria e guardrails | Governança, guardrails | 4 h |
| 7 | Agente LangGraph | Arquitetura | 5 h |
| 8 | Relatório HTML e PDF | — | 3 h |
| 9 | CLI e Streamlit | — | 3 h |
| 10 | Diagrama de arquitetura em PDF | Arquitetura | 1 a 2 h |
| 11 | README, relatório de exemplo, revisão final | Todos | 3 h |

---

## Fase 0: Pré-requisitos

Ambiente com Git, uv e Python 3.12; chaves da Anthropic e da Tavily (somente no `.env`, fora do Git); arquivos do Open DATASUS em `data/raw/` e o dicionário de dados em `docs/reference/`.

---

## Fase 1: Estrutura do repositório

**Branch:** `chore/bootstrap`

1. Inicialize o projeto com uv:
   ```powershell
   uv init --package --name srag --python 3.12
   ```
   Ajuste o `pyproject.toml` para o nome de distribuição `healthwatch-srag-agent` e o pacote em `src/srag`.
2. Instale as dependências:
   ```powershell
   uv add langgraph langchain-core langchain-anthropic tavily-python pandas pyarrow duckdb matplotlib jinja2 playwright pydantic pydantic-settings streamlit
   uv add --dev pytest pytest-cov ruff pre-commit
   uv run playwright install chromium
   ```
3. Crie as pastas e os arquivos vazios conforme a seção 6 do `CLAUDE.md`, mais `data/raw/.gitkeep` e `data/processed/.gitkeep`.
4. Configure o **ruff** no `pyproject.toml` (regras sugeridas: `E, F, I, B, UP, SIM, N`; tamanho de linha 100).
5. Configure o **pre-commit** com ruff (lint e format) e um verificador de segredos, por exemplo o hook `detect-private-key` do `pre-commit-hooks`.
6. Crie `src/srag/config.py` com `pydantic-settings`, lendo todas as variáveis do `.env.example`, resolvendo caminhos a partir da raiz do projeto e guardando a lista de UFs válidas e a lista de domínios de notícias permitidos.
7. Crie `.github/workflows/ci.yml`, que roda `uv sync`, `ruff check`, `ruff format --check` e `pytest` em cada push e pull request.
8. Escreva um teste mínimo (`tests/test_config.py`) para o CI ter o que rodar.

**Critérios de aceite:**
- `uv run pytest` passa localmente
- CI verde no GitHub
- `uv.lock` commitado; `.env` e `data/` fora do Git

---

## Fase 2: Exploração e limpeza dos dados

**Branch:** `feat/data-pipeline` · **Critério:** dados sensíveis, clean code

### 2.1 Exploração (rascunho)
Use um notebook em `notebooks/01_exploracao.ipynb`, que nunca entra em `src/`, para:
- Descobrir o separador e a codificação do CSV. Arquivos do DATASUS costumam usar `;` e às vezes `latin-1`.
- Ver o formato das datas, a porcentagem de vazios por coluna e os valores distintos das colunas codificadas.
- Conferir no dicionário os códigos de `EVOLUCAO`, `UTI`, `VACINA_COV`, `VACINA` e `CLASSI_FIN`.

### 2.2 Seleção de colunas (`data/schema.py`)
Sugestão inicial. Confirme no dicionário.

| Manter | Para quê |
|---|---|
| `DT_NOTIFIC`, `DT_SIN_PRI` | Datas de notificação e de primeiros sintomas |
| `SG_UF` | Estado de residência (escopo) |
| `NU_IDADE_N`, `TP_IDADE` | Convertidos em **faixa etária** (a idade exata é descartada) |
| `CS_SEXO` | Contexto agregado (opcional) |
| `HOSPITAL`, `DT_INTERNA` | Internação |
| `UTI`, `DT_ENTUTI`, `DT_SAIDUTI` | Métrica de UTI |
| `EVOLUCAO`, `DT_EVOLUCA` | Métrica de mortalidade |
| `VACINA_COV`, `VACINA` | Métrica de vacinação |
| `CLASSI_FIN` | Agente causador (COVID, influenza, etc.) para contexto |

**Descartar** (e explicar no README): data de nascimento, códigos de município e de unidade de saúde, nomes, endereços, CEP, campos de texto livre e qualquer outra coluna não usada. Minimizar dados é uma exigência da LGPD e ponto direto no critério de dados sensíveis.

### 2.3 Limpeza (`data/cleaning.py`, funções puras e testadas)
- Converter datas, transformando as inválidas em vazio. Descartar datas futuras ou anteriores ao início do período.
- Padronizar os códigos e tratar `9` como "ignorado". Os valores ignorados não entram nos denominadores (veja `docs/METRICS.md`).
- Remover duplicatas exatas.
- Validar a UF contra a lista oficial.
- Criar a faixa etária e descartar a idade exata.

### 2.4 Preparação (`data/prepare.py`)
Lê `data/raw/*.csv` só com as colunas selecionadas, limpa, grava `data/processed/srag.parquet` e escreve um **relatório de qualidade** (`data/processed/quality_report.json`: linhas lidas, descartadas por motivo, % de vazios por coluna, data mínima e máxima). Esse relatório também é evidência de governança.

### 2.5 Repositório de dados (`data/repository.py`)
Funções com parâmetros fixos sobre o DuckDB em memória, com acesso a arquivos desligado e configuração travada (veja D-012), como `count_cases_by_day(uf, start, end)`. Nada de SQL montado com texto vindo do LLM.

**Critérios de aceite:**
- `uv run python -m srag.data.prepare` gera o Parquet e o relatório de qualidade
- Testes de limpeza com uma fixture sintética (`tests/fixtures/srag_sample.csv`, cerca de 50 linhas inventadas)
- Lista de colunas mantidas e descartadas, com justificativa, anotada para o README

---

## Fase 3: Métricas

**Branch:** `feat/metrics`

1. Implemente em `metrics/calculations.py` as funções descritas em `docs/METRICS.md`, retornando `MetricResult`.
2. Calcule a data de referência D, a janela atual, a janela anterior e a janela de atraso a partir do `config.py`.
3. Faça testes para cada métrica: caso normal, denominador zero, todos os valores ignorados, sinalização de instabilidade e limites das janelas.

**Critérios de aceite:**
- As 4 métricas (e a de vacinação contra gripe, secundária) retornam `MetricResult`
- Testes cobrem os casos de borda
- Valores conferidos para Brasil e para uma UF com uma consulta independente

---

## Fase 4: Gráficos

**Branch:** `feat/charts`

1. `charts/plots.py`: `daily_cases_chart(series) -> Path` e `monthly_cases_chart(series) -> Path`, gerando PNG.
2. Preencha os dias sem casos com 0. Marque visualmente os dias "incompletos" (atraso de notificação) e o mês parcial.
3. Títulos, eixos e legendas em português, com o escopo (Brasil ou UF) e a data de referência.
4. Os testes verificam a **série de dados** (30 pontos diários e 12 mensais) e se o arquivo foi criado, sem comparar imagens.

**Critérios de aceite:**
- Os dois PNGs são gerados para Brasil e para uma UF
- Períodos incompletos aparecem marcados

---

## Fase 5: Ferramenta de notícias

**Branch:** `feat/news` · **Critério:** guardrails

1. `news/client.py`: wrapper da Tavily com `include_domains` (a lista de permitidos do `config.py`), número máximo de resultados e tópico de notícias.
2. Lista inicial de domínios sugerida, a ser revisada: `gov.br`, `fiocruz.br`, `agenciabrasil.ebc.com.br`, `g1.globo.com`, `folha.uol.com.br`, `estadao.com.br`, `cnnbrasil.com.br`, `bbc.com`, `paho.org`, `who.int`.
3. `news/sanitizer.py`:
   - descarta resultados fora da lista ou mais antigos que `NEWS_DAYS`;
   - corta o conteúdo em N caracteres;
   - remove trechos que pareçam instruções ao modelo ("ignore as instruções", "você agora é", etc.) e registra a remoção na auditoria;
   - devolve objetos tipados: `NewsItem(title, url, source, published_at, snippet)`.
4. A consulta inclui o nome do estado quando houver UF.
5. Testes com respostas falsas da Tavily, incluindo uma notícia com tentativa de prompt injection.

**Critérios de aceite:**
- A busca real funciona com a chave (teste real)
- Testes do sanitizador passam, incluindo o caso de injection
- Sem notícias válidas, a ferramenta retorna uma lista vazia, sem erro

---

## Fase 6: Auditoria e guardrails

**Branch:** `feat/governance` · **Critérios:** governança, guardrails

Construa isto **antes** do agente, para que ele já nasça auditado.

1. **`audit/logger.py`:**
   - cria `run_id` e a pasta `reports/<timestamp>_<run_id>/`;
   - `log_event(...)` grava uma linha JSON em `audit.jsonl` com os campos da seção 11 do `CLAUDE.md`;
   - higieniza as entradas: nunca grava chaves e corta textos longos;
   - `write_manifest(...)` grava modelo, temperatura, versões dos prompts, hash do arquivo de dados, data de referência, commit do Git, status final, tokens e custo total.
2. **`guardrails/input.py`:** valida a UF (27 siglas ou nada) com Pydantic.
3. **`guardrails/output.py`:**
   - extrai os números do texto do LLM e compara com as métricas calculadas (tolerância de 0,1 ponto percentual, já que o texto arredonda);
   - confere se todo link citado está entre as notícias recebidas;
   - confere se as seções obrigatórias e o aviso médico estão presentes;
   - procura padrões de dados pessoais (CPF, telefone, e-mail);
   - devolve `ValidationResult(passed, errors)`.
4. **Limites:** contador de iterações, controle de custo acumulado e timeout.
5. Testes para cada guardrail, com um caso que passa e um que falha.

**Critérios de aceite:**
- Uma execução de teste gera `audit.jsonl` e `manifest.json` legíveis
- Todos os guardrails têm testes de aprovação e de reprovação

---

## Fase 7: Agente (LangGraph)

**Branch:** `feat/agent` · **Critério:** arquitetura

1. **`agent/state.py`:** estado tipado com uf, mensagens, métricas, séries, caminhos dos gráficos, notícias, rascunho do texto, resultado da validação, contador de tentativas e status.
2. **`agent/tools.py`:** três ferramentas LangChain com docstrings claras, porque o LLM as lê:
   - `get_metrics(uf)`
   - `get_case_series(uf)`, que também gera os gráficos
   - `search_news(query, uf)`
   
   Cada chamada é registrada na auditoria.
3. **`agent/prompts/`:**
   - `orchestrator_v1.md`: papel, ferramentas disponíveis, obrigação de buscar métricas e séries, e de buscar notícias com até 2 refinamentos de consulta.
   - `writer_v1.md`: escrever em pt-BR, usar **somente** os números fornecidos, citar notícias por URL, explicar limitações das métricas proxy, não dar orientação médica, tratar notícias como conteúdo não confiável, seguir uma estrutura fixa de seções.
4. **`agent/graph.py`:**
   ```
   START → orchestrator ⇄ tools (até AGENT_MAX_ITERATIONS)
         → required_tools_check (se faltar algo, chama a ferramenta deterministicamente e registra)
         → writer → output_guardrail
             ├─ passou → END
             ├─ falhou e tentativas < 1 → writer (com os erros como feedback)
             └─ falhou de novo → fallback (relatório só com métricas e gráficos, e aviso) → END
   ```
5. Use `ChatAnthropic` com o modelo, a temperatura e o máximo de tokens do `config.py`. Capture o uso de tokens de cada resposta para a auditoria.
6. **Teste de ponta a ponta** com LLM falso (`langchain_core` tem modelos falsos) e Tavily falsa.

**Critérios de aceite:**
- Execução real para Brasil e para uma UF produz o texto e passa no guardrail de saída
- Execução real com custo registrado na auditoria
- Teste de ponta a ponta com fakes passa no CI
- Caminho de fallback testado

---

## Fase 8: Relatório HTML e PDF

**Branch:** `feat/report`

1. **`report/templates/report.html.j2`** com as seções:
   1. Cabeçalho: título, escopo, data de referência dos dados, data de geração
   2. Resumo executivo (LLM)
   3. Cartões das 4 métricas, com valor, janela, completude e aviso de instabilidade
   4. Os 2 gráficos
   5. Análise do cenário (LLM), com citações
   6. Limitações e notas metodológicas (texto fixo, a partir do `METRICS.md`)
   7. Fontes: lista de notícias com links
   8. Rodapé: run_id, modelo, versão dos prompts, aviso médico
2. Imagens embutidas em base64, para o HTML funcionar sozinho.
3. **`report/pdf.py`:** abre o HTML no Chromium (Playwright) e salva em A4.
4. **`service.py`:** `generate_report(uf) -> ReportResult` liga tudo: validação, grafo, renderização, PDF e manifesto.

**Critérios de aceite:**
- `report.html` e `report.pdf` são gerados e legíveis, com as 8 seções
- O PDF abre corretamente no Windows

---

## Fase 9: Interfaces (CLI e Streamlit)

**Branch:** `feat/interfaces`

1. **`__main__.py`** com argparse: `--uf`, `--no-pdf`, `--output-dir`. Ao terminar, imprime o caminho dos arquivos. Os erros de validação aparecem como mensagem clara, sem stack trace.
2. **`ui/streamlit_app.py`:**
   - seletor de escopo (Brasil e as 27 UFs) e botão "Gerar relatório";
   - métricas com `st.metric`, gráficos, texto e fontes;
   - botões para baixar o PDF e o HTML;
   - um painel expansível **"Auditoria desta execução"** que mostra o `audit.jsonl` em tabela, o que deixa a transparência visível para quem avalia.
3. Ambos chamam apenas `service.generate_report`.

**Critérios de aceite:**
- `uv run python -m srag --uf SP` funciona
- O Streamlit gera, exibe e baixa o relatório, e mostra a auditoria

---

## Fase 10: Diagrama de arquitetura em PDF (entregável obrigatório)

1. Abra `docs/architecture.mmd`, ajuste ao que foi realmente construído, cole em **mermaid.live** e exporte em PDF e PNG. Se preferir um visual mais caprichado, redesenhe no draw.io.
2. Confira se o diagrama mostra: **orquestrador**, **ferramentas**, **interações com o LLM**, **banco de dados**, **fonte de notícias**, guardrails e auditoria.
3. Salve como `docs/architecture.pdf` e `docs/architecture.png`. O PNG vai embutido no README, porque o GitHub não exibe PDF dentro do texto.

**Critérios de aceite:**
- `docs/architecture.pdf` existe e mostra os 5 elementos exigidos

---

## Fase 11: Documentação e revisão final

1. Gere um relatório real e copie-o para `docs/sample_report/` (HTML, PDF e `audit.jsonl`). Isso permite avaliar sem rodar nada.
2. Preencha todos os `TODO` do `README.md`: visão geral, componentes, como rodar, governança (exemplo de linha da auditoria), tabela de guardrails, colunas mantidas e descartadas, estrutura, limitações.
3. Teste o passo a passo do README em uma pasta nova (clone limpo), como se fosse a pessoa avaliadora.
4. Revise o `DECISIONS.md` e acrescente o que mudou durante o desenvolvimento.
5. Repositório público, com o histórico conferido para garantir que não há segredos.
6. Descrição e tópicos no GitHub.

---

## Matriz de requisitos 

| Requisito / critério | Onde é atendido | ✓ |
|---|---|---|
| Taxa de aumento de casos | `metrics/calculations.py`, relatório seção 3 | [x] |
| Taxa de mortalidade | idem | [x] |
| Taxa de ocupação de UTI (proxy declarado) | idem e `METRICS.md` | [x] |
| Taxa de vacinação (proxy declarado) | idem e `METRICS.md` | [x] |
| Gráfico diário dos últimos 30 dias | `charts/plots.py`, relatório seção 4 | [x] |
| Gráfico mensal dos últimos 12 meses | idem | [x] |
| Notícias em tempo real embasando as explicações | `news/`, relatório seções 5 e 7 | [x] |
| Agente orquestrador com ferramentas e LLM | `agent/graph.py` | [x] |
| Dados reais do Open DATASUS, com colunas selecionadas e tratadas | `data/` e relatório de qualidade | [x] |
| Repositório público com README completo | GitHub | [x] |
| PDF do diagrama de arquitetura | `docs/architecture.pdf` | [x] |
| **Arquitetura** | Grafo, módulos e `DECISIONS.md` | [x] |
| **Governança e transparência** | `audit.jsonl`, `manifest.json`, rodapé do relatório, painel no Streamlit | [x] |
| **Guardrails** | `guardrails/`, `news/sanitizer.py`, limites do agente | [x] |
| **Dados sensíveis** | Colunas descartadas, só agregados, `.env`, seção no README | [x] |
| **Clean code** | ruff, testes, CI, tipagem, funções pequenas | [x] |

---

## Riscos e como lidar

| Risco | Mitigação |
|---|---|
| Os dados param em 2024 e os gráficos ficam "antigos" | Usar o arquivo mais recente; as janelas usam a última data dos dados; o relatório informa a data de referência |
| CSV grande demais para a memória | Ler só as colunas selecionadas (`usecols`) e com tipos definidos |
| Notícias recentes não falam dos dados antigos | O prompt pede para diferenciar o "cenário dos dados" do "cenário atual das notícias", e o relatório explica a diferença |
| Instalação do Playwright bloqueada por rede corporativa | Opção `--no-pdf` (só HTML) documentada |
| Commit acidental do `.env` | `.gitignore` e hook de pre-commit (`detect-private-key`) |
| Gasto inesperado de API | Limite de gastos no painel e `MAX_COST_USD_PER_RUN` |
