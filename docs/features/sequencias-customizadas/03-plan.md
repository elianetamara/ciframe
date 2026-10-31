# Sequências de Acordes Customizadas Design Document

## Current Context
- Aplicação Flask single-file (`main.py`), sem banco: músicas e gêneros vêm de `data/top/dataset_final.csv` para memória no startup.
- As 6 sequências “famosas” estão hardcoded em `main.py:40-45`; a busca por sequência usa a tag `SEQ_FAMOSA` do CSV e retorna 199/296/4/5/7/3 músicas para os ids 0–5.
- O frontend AngularJS tem 4 sequências hardcoded em `static/assets/js/controllers/sequencia.js`, não lista o catálogo real e não oferece cadastro.
- A feature precisa de catálogo persistente, cadastro anônimo, busca por qualquer sequência e manutenção exata dos resultados das 6 originais.
- Decisões já registradas em `docs/features/sequencias-customizadas/02-proposal.md` e `docs/adr/0002-persist-custom-sequences.md`.
- Premissas de escopo e prazo: implementação em ~1–1,5 dia de trabalho focado, sem datas de calendário; não inclui edição/exclusão, login, moderação, troca do dropdown de gêneros ou remoção de `SEQ_FAMOSA`.

## Requirements

### Functional Requirements
- Persistir o catálogo de sequências em SQLite, com seed idempotente das 6 originais (ids 0–5).
- Permitir cadastro anônimo de sequências via `POST /sequencias`, com validação e deduplicação.
- Listar o catálogo real via `GET /sequencias`.
- Buscar músicas por sequência cadastrada via `GET /similares?sequencia_id=<id>`, com filtros de gênero e paginação existentes.
- Manter `GET /similares?sequencia=<acordes>` compatível com o contrato atual e com as 6 originais.
- Aplicar a mesma regra de matching a todas as sequências: bloco contíguo e ordenado em `musica.cifra` + todos os acordes da música contidos no conjunto da sequência.
- Preservar exatamente os resultados e a ordem das 6 originais.
- Fazer `#/porsequencia` carregar o catálogo da API, permitir cadastro e buscar por `sequencia_id`.
- Manter músicas/gêneros no CSV em memória; somente o catálogo de sequências vai para o banco.
- Manter respostas com `json.dumps`, não `jsonify`, e o deploy em um único `Dockerfile` local.

### Non-Functional Requirements
- Desempenho esperado: ordem de ~0,2 s por busca sobre 67.585 músicas; não degradar a paginação nem a ordem dos resultados.
- Persistência: sobreviver a reinício do processo e à recriação do container quando o volume nomeado for usado.
- Compatibilidade: Python 3.9, Flask 3.1, gunicorn, sem dependência nova em `requirements.txt`.
- Limites de proteção: 1–32 acordes por sequência e 32 caracteres por acorde.
- Segurança: consultas SQL parametrizadas, validação de entrada e catálogo anônimo por decisão; sem rate limiting nesta fase.
- Observabilidade mínima: logar caminho do banco, criação/seed e erros de persistência no startup.
- Escalabilidade: uma instância/um worker; sem necessidade de otimização para múltiplos escritores.

## Design Decisions

### 1. Matching único compatível com legado
Will implement a regra contígua + subset para todas as sequências porque:
- Foi a única regra validada que reproduz exatamente os 6 resultados atuais.
- Evita dois comportamentos no mesmo endpoint e remove a dependência de runtime da tag `SEQ_FAMOSA`.
- Normalização `strip()` + primeira letra maiúscula preserva `F7M`/`F7m` e foi validada contra as 6.
- Trade-off: a regra é restritiva para sequências novas e o cálculo é feito em tempo real; contíguo puro, subsequência com lacunas e subset não ordenado foram descartados por mudarem os resultados.

### 2. SQLite local com volume Docker
Will implement SQLite via stdlib com arquivo em `/app/instance/sequences.db` porque:
- Não adiciona serviço, container ou dependência e cabe no deploy local-only do ADR 0001.
- É transacional e suficiente para o volume de escrita de uma instância.
- O volume nomeado `ciframe-sequences` garante persistência na recriação do container.
- Trade-off: exige lifecycle de banco, seed e documentação de volume; TinyDB, JSON/pickle, banco em memória e PostgreSQL/MySQL foram descartados.

### 3. API compatível e baseada em id
Will implement `GET /sequencias`, `POST /sequencias` e `?sequencia_id=` mantendo `?sequencia=` porque:
- `sequencia_id` dá identidade estável ao catálogo e evita a ambiguidade da concatenação sem separador.
- Manter `?sequencia=` preserva links e o contrato atual das 6 originais.
- Duplicatas são rejeitadas com `409`; entradas inválidas com `400`.
- Trade-off: dois parâmetros de busca coexistem; somente o formato concatenado continua ambíguo para sequências novas, que devem usar id.

### 4. Frontend dinâmico e cadastro simples
Will implement a lista dinâmica e um formulário de texto separado por vírgulas porque:
- Atende ao requisito de refletir o catálogo real e permitir cadastro pela página.
- Reaproveita `ng-repeat` e a diretiva `df-hex` já existentes.
- Trade-off: seletor/catálogo curado de acordes e troca do dropdown de gêneros ficam fora do escopo.

### 5. Escopo append-only e limites de proteção
Will keep o catálogo append-only, limites 1–32/32 e `SEQ_FAMOSA` no CSV porque:
- Edição/exclusão não está no enunciado; limites protegem contra abuso sem virar regra musical.
- `SEQ_FAMOSA` é necessária como referência histórica para a regressão das 6.
- Trade-off: sem moderação/rate limiting; a coluna permanece como dado histórico, não fonte de verdade.

## Technical Design

### 1. Core Components
```python
from typing import Any, Dict, List, Optional

from musica import Musica


class SequenciaInvalida(Exception):
    """Entrada vazia, longa demais ou fora do formato esperado."""


class SequenciaDuplicada(Exception):
    """A chave canônica já existe no catálogo."""


class RepositorioSequencias:
    def __init__(self, path: str) -> None: ...
    def inicializar(self) -> None: ...
    def listar(self) -> List[Dict[str, Any]]: ...
    def criar(self, acordes: List[str]) -> Dict[str, Any]: ...
    def por_id(self, seq_id: int) -> Optional[List[str]]: ...
    def por_chave(self, chave: str) -> Optional[List[str]]: ...
    def por_legacy_key(self, legacy_key: str) -> Optional[List[str]]: ...


def normalizar_acordes(acordes: List[str]) -> List[str]: ...
def chave_canonica(acordes: List[str]) -> str: ...
def sequencia_compativel(musica: Musica, acordes: List[str]) -> bool: ...
```

- `main.py`: inicializa o repositório no startup, mantém o carregamento do CSV e as rotas existentes, adiciona as rotas de catálogo e liga a busca ao novo matching.
- `sequencias.py` (novo): schema, seed, CRUD, normalização e matching; sem dependência de Flask.
- `get_similares_por_sequencia` continua responsável por filtrar gêneros, paginar e montar o payload atual.

### 2. Data Models
```sql
CREATE TABLE IF NOT EXISTS sequencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    acordes TEXT NOT NULL,
    chave TEXT NOT NULL UNIQUE,
    legacy_key TEXT UNIQUE,
    origem TEXT NOT NULL CHECK (origem IN ('seed', 'custom')),
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- `acordes`: JSON com a lista ordenada já normalizada.
- `chave`: acordes unidos por `;` (ex.: `C;G;Am;F`), usada para duplicidade.
- `legacy_key`: apenas nas 6 originais (`BmGDA`, `CGAmF`, `EmG`, `CA7DmG7`, `GmF`, `CC7FFm`).
- `Musica` (`musica.py`) não muda; `cifra` continua sendo a lista ordenada usada pelo matching.
- Seed com `INSERT OR IGNORE` e IDs explícitos 0–5; novas sequências começam em 6.

### 3. Integration Points
- `GET /sequencias` → `[{"id", "acordes", "origem"}]`, ordenado por id.
- `POST /sequencias` → corpo `{"acordes": [...]}`; `201`/`400`/`409`, sempre `json.dumps`.
- `GET /similares?sequencia_id=<id>` → mesmo formato de resultado e paginação atuais.
- `GET /similares?sequencia=<acordes>` → tenta `legacy_key` sem vírgulas e depois `chave` canônica; desconhecida retorna `[]`.
- Fluxo de busca: rota → valida/normaliza → carrega acordes do banco → percorre músicas em memória → aplica gênero/paginação → `json.dumps`.
- Docker: app grava em `/app/instance/sequences.db`; volume nomeado montado em `/app/instance`.
- Frontend: `sequencia.js` consome `/sequencias`, envia `POST` e busca com `sequencia_id`; `app.js` e `routes.js` não mudam.

### 4. Files Changes
| Arquivo | Mudança |
|---|---|
| `sequencias.py` (novo) | Schema, seed, repositório, normalização e matching. |
| `main.py` | Remover catálogo hardcoded, inicializar DB, adicionar `GET/POST /sequencias`, busca por `sequencia_id` e fallback legado. |
| `Dockerfile` | Declarar `VOLUME ["/app/instance"]` e garantir o diretório. |
| `README.md` | Documentar o volume nomeado no `docker run`. |
| `.gitignore` | Ignorar `instance/`. |
| `.dockerignore` | Excluir `instance/` da imagem. |
| `static/assets/js/controllers/sequencia.js` | Carregar catálogo real, cadastrar e buscar por id. |
| `static/templates/sequencia.html` | Formulário de cadastro, estados de erro/loading e ajuste do campo `diferenca`. |
| `tests/__init__.py` (novo) | Pacote de testes. |
| `tests/fixtures/regressao_6.json` (novo) | Snapshot dos IDs/ordem das 6 originais para regressão. |
| `tests/test_sequencias.py` (novo) | Testes de normalização, matching, schema, seed e repositório. |
| `tests/test_api.py` (novo) | Testes de listagem, cadastro, duplicidade, validação, busca e legado. |
| `docs/features/sequencias-customizadas/04-test-report.md` | Registrar evidências e resultados da verificação. |

## Implementation Plan

1. Fase 0 — Baseline e snapshot de regressão (0,5–1 h)
   - Capturar, com o código atual, os IDs na ordem para os ids 0–5 em todos os gêneros e em pelo menos dois filtros de gênero.
   - Salvar `tests/fixtures/regressao_6.json` e conferir as contagens 199/296/4/5/7/3.
   - Verificação: fixture reproduzível e versionada antes de qualquer mudança no matching.

2. Fase 1 — Persistência e seed (2–3 h)
   - Criar `sequencias.py` com schema, seed idempotente, normalização, chave canônica e repositório.
   - Configurar `SEQUENCES_DB` para testes e caminho padrão `/app/instance/sequences.db`.
   - Verificação: testes com banco temporário; reabrir o arquivo e confirmar seed único e persistência.

3. Fase 2 — Matching e integração no backend (1–2 h)
   - Implementar `sequencia_compativel` e ligar a busca a `musica.cifra` sem alterar `Musica`.
   - Remover o caminho de runtime por `seqs_famosas` do endpoint de sequência.
   - Verificação: regressão contra o snapshot da fase 0 antes de avançar.

4. Fase 3 — API de catálogo e compatibilidade (2–3 h)
   - Adicionar `GET /sequencias`, `POST /sequencias` e `?sequencia_id=`.
   - Implementar validação, `409`, fallback `?sequencia=` e manter `json.dumps`.
   - Verificação: testes de API e smoke com `curl` para listar, criar, duplicar e buscar.

5. Fase 4 — Frontend (2–3 h)
   - Remover as 4 sequências hardcoded, carregar `/sequencias` e renderizar todas.
   - Adicionar formulário, estados de erro/loading, busca por id e ajuste de `music.diferenca`.
   - Verificação: smoke no browser em `#/porsequencia`, incluindo cadastro, conflito e busca.

6. Fase 5 — Persistência no Docker e documentação (1 h)
   - Atualizar `Dockerfile`, `README.md`, `.gitignore` e `.dockerignore`.
   - Verificação: build, execução com volume nomeado, cadastro, restart e recriação do container.

7. Fase 6 — Verificação final e handoff (1 h)
   - Rodar toda a suíte, a regressão das 6, o teste Docker e a medição de desempenho.
   - Preencher `04-test-report.md` com comandos, resultados e limitações.
   - Verificação: definição de pronto abaixo integralmente satisfeita; nenhuma alteração fora dos arquivos listados.

Estimativa total: ~10 h (1–1,5 dia focado). Cada fase só avança após a verificação da anterior.

## Testing Strategy

### Unit Tests
- Normalização: caixa da primeira letra, espaços, `F7M` vs `F7m`, lista vazia, limite de 32/32.
- Matching: bloco contíguo, ordem trocada, acorde extra no meio, repetição, acorde fora do conjunto, cifra vazia.
- Repositório: seed idempotente, IDs 0–5, unicidade de `chave`/`legacy_key`, busca por id/chave/legacy, reabertura do banco.
- Estratégia: `unittest` da stdlib, banco temporário por teste, sem mocks do CSV nos testes de integração.

### Integration Tests
- API via test client do Flask: `GET /sequencias`, `POST` válido, duplicado, inválido, busca por id, busca legada, filtro de gênero e paginação.
- Regressão: comparar IDs/ordem das 6 com `tests/fixtures/regressao_6.json`.
- Persistência: criar sequência, fechar/reabrir o processo e confirmar leitura; no Docker, recriar o container com volume.
- Ambiente: Python 3.9, Flask 3.1, banco em arquivo temporário; sem serviço externo.
- Cobertura: focar nos caminhos críticos acima; não há meta formal de cobertura no projeto.

## Observability

### Logging
- No startup: caminho do banco, se o schema foi criado e quantas sequências foram semeadas.
- Em falha de inicialização/seed: erro com contexto suficiente para diagnóstico, sem expor dados sensíveis.
- Em `POST`: registrar criação e conflito de duplicata; não logar payloads grandes desnecessariamente.

### Metrics
- Não se aplica nesta versão local: não há stack de métricas nem alertas; a verificação é feita por logs e testes.

## Future Considerations

### Potential Enhancements
- Edição/exclusão de sequências e moderação do catálogo anônimo.
- Rate limiting e proteção contra abuso no `POST`.
- Seletor de acordes no frontend e uso de `GET /generos` no dropdown.
- Índice/cache de matching se o custo por busca crescer.

### Known Limitations
- Catálogo append-only, sem autoria ou moderação.
- A regra é restritiva para sequências novas; resultados podem ser menores que o esperado.
- `?sequencia=` concatenado continua ambíguo para sequências novas; o frontend usa id.
- `SEQ_FAMOSA` permanece no CSV como referência de regressão, sem uso no runtime.
- Sem testes automatizados de UI; smoke manual no browser.
- Deploy segue local-only; nenhum alvo de nuvem foi escolhido.

## Dependencies

### Development Dependencies
- Python 3.9, Flask 3.1, gunicorn, `sqlite3` e `unittest` da stdlib.
- Docker para build e teste de persistência; `curl` para smoke da API.
- Nenhuma dependência nova em `requirements.txt`; `pytest`, ORM ou serviço de banco não são necessários.

## Security Considerations
- Catálogo aberto e anônimo por requisito; não há autenticação/autorização nesta fase.
- Mitigações: validação de formato/tamanho, limite 1–32/32, chave única e queries SQL parametrizadas.
- Sem rate limiting, moderação ou captcha; risco aceito e documentado para o escopo local.
- Sem dados pessoais, segredos ou compliance específico; o arquivo SQLite fica no volume local.
- Não alterar CORS: o frontend é same-origin e o contrato atual é mantido.

## Rollout Strategy
1. Desenvolvimento com testes unitários e de API, mantendo o snapshot de regressão desde a fase 0.
2. Build local da imagem Docker e execução com banco novo para validar o seed.
3. Execução com banco existente para confirmar inicialização/seed idempotentes.
4. Teste com volume nomeado: cadastrar, reiniciar e recriar o container, confirmando persistência.
5. Monitorar logs de startup e criação; rollback por redeploy da imagem anterior (o banco novo é aditivo e não é lido pelo código antigo).

Não há staging ou produção nesta fase; o alvo continua local-only, conforme ADR 0001.

## References
- `docs/features/sequencias-customizadas/00-enunciado.md`
- `docs/features/sequencias-customizadas/01-research.md`
- `docs/features/sequencias-customizadas/02-proposal.md`
- `docs/adr/0001-local-only-docker-deploy.md`
- `docs/adr/0002-persist-custom-sequences.md`
- Template: `/home/eliane/reppit-framework/templates/design_doc_template.md`
- `main.py`, `musica.py`, `Dockerfile`, `README.md`, `static/assets/js/controllers/sequencia.js`, `static/templates/sequencia.html`
