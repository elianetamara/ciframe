# Relatório de testes — Sequências de Acordes Customizadas

## Cobertura

Foram adicionados testes automatizados com `unittest` da stdlib (sem novas dependências):

### `tests/test_sequencias.py` (13 testes)
- **Normalização**: capitalização da primeira letra, preservação de sufixos (`F7M`/`F7m`), rejeição de lista vazia/tipo inválido/acorde vazio e limites de 1–32 acordes e 32 caracteres por acorde.
- **Matching**: regra contígua e ordenada em `musica.cifra` com `set(cifra) ⊆ set(sequência)`. Cobertos: bloco exato, sequência maior que a cifra (rejeitada), ordem diferente, acorde extra ausente, repetição e cifra vazia.
- **Repositório SQLite**: criação da tabela, seed idempotente das 6 originais com IDs 0–5 e `legacy_key`, listagem ordenada por ID, criação com normalização, busca por ID/chave canônica/`legacy_key`, duplicata do seed e persistência após reabrir o banco (`tests/test_sequencias.py`).

### `tests/test_api.py` (11 testes)
- **Catálogo**: `GET /sequencias` devolve as 6 originais na ordem [0,1,2,3,4,5], com `Content-Type: text/html` (mantido).
- **Cadastro**: `POST /sequencias` com normalização (`["bm","e"]` → `["Bm","E"]`), `201`, duplicata (seed e custom) retorna `409`, entradas inválidas e JSON malformado retornam `400`.
- **Busca**: `GET /similares?sequencia_id=<id>` com paginação (100/99), filtro por gênero, ID inexistente retorna `[]`, compatibilidade com `GET /similares?sequencia=Bm,G,D,A` via `legacy_key`/chave canônica.
- **Regressão**: comparação contra caminho legado por `SEQ_FAMOSA` no mesmo processo para todos os gêneros, Rock e Samba. Verificação também contra `tests/fixtures/regressao_6.json` (contagem e conjunto).
- **Serialização**: após busca por sequência, `GET /musicas` e `GET /musica/the-strokes_reptilia/` continuam serializáveis (`200`) — cobre correção de cache não mutável em instâncias `Musica`.

## Teste de regressão obrigatório

**Snapshot:** `tests/fixtures/regressao_6.json` gerado com o código legado antes da migração (baseado em `SEQ_FAMOSA`).

**Verificação realizada:**
- Comparação direta com o caminho antigo (`if str(id_seq) in musica.seqs_famosas`) no mesmo processo, para os filtros `todos` (todos os gêneros), `Rock` e `Samba`. A ordem foi validada contra esse caminho legado (pois `generos` é um `set`, a ordem no fixture por si só pode variar entre processos).
- Para `todos`, as contagens foram validadas contra o fixture: 0=199, 1=296, 2=4, 3=5, 4=7, 5=3. Os conjuntos foram validados por `sorted()` contra o fixture.

**Resultado:** Todas as 6 sequências retornaram exatamente os mesmos IDs na mesma ordem do caminho legado nos casos testados, com as contagens esperadas. Regressão passou.

## Como rodar

```bash
.venv/bin/python -m unittest discover -s tests -v
```

**Resultado observado:** `Ran 24 tests in 2.368s ... OK`

Verificações complementares executadas durante a validação:
- `python -m py_compile main.py musica.py sequencias.py tests/test_sequencias.py tests/test_api.py`
- Build Docker + smoke com volume nomeado (criação, restart/recriação e persistência) — verificado manualmente
- Smoke frontend em `#/porsequencia` com Playwright/Chrome headless (catálogo, cadastro, busca, duplicata, sem erros JS)

## O que ficou de fora

- **Edição/exclusão, login/moderação/rate limiting:** fora do escopo da feature.
- **Testes de carga/concorrência/múltiplos workers gunicorn:** não exercitados (SQLite com 1 worker no deploy atual).
- **Suíte de navegador versionada:** smoke automatizado feito com Playwright localmente, mas a dependência não foi adicionada ao projeto.
- **Outros navegadores/responsividade/falhas de CDN:** não testados.
- **Migração/rollback de schema pré-existente:** coberto apenas banco novo/reabertura com schema atual.
- **`?sequencia=` para sequência não cadastrada:** retorna lista vazia (comportamento mantido pela implementação).
- **Dropdown de gêneros continua hardcoded; `SEQ_FAMOSA` permanece no CSV apenas como referência histórica.**
