# Plano — Sequências de Acordes Customizadas

Implementar a Proposta 1 documentada em `02-proposal.md` e na ADR 0002:
catálogo de sequências em SQLite, matching único “contíguo + subset” para as 6
originais e para as novas, API de listagem/cadastro, busca por `sequencia_id` e
frontend consumindo o catálogo real. Músicas/gêneros continuam no CSV em memória;
o deploy continua em um único `Dockerfile` local; respostas continuam com
`json.dumps`.

Premissas de escopo e prazo: ~10 h (1–1,5 dia focado), sem datas de calendário.
Ficam fora edição/exclusão, login/moderação, troca do dropdown de gêneros e
remoção de `SEQ_FAMOSA`. Limites de proteção: 1–32 acordes e 32 caracteres por
acorde.

## Passos

1. [x] Fase 1 — Capturar baseline de regressão (~0,5–1 h)
   - Rodar o código atual e salvar em `tests/fixtures/regressao_6.json` os IDs
     retornados, na ordem, para os ids 0–5 em todos os gêneros e em pelo menos
     dois filtros de gênero.
   - Confirmar as contagens de referência 199/296/4/5/7/3.
   - Verificação: fixture reproduzível e versionada antes de qualquer mudança no
     matching.

2. [x] Fase 2 — Criar persistência SQLite e seed (~2–3 h)
   - Criar `sequencias.py` com schema, seed idempotente, normalização, chave
     canônica, CRUD e busca por id/chave/`legacy_key`.
   - Usar `SEQUENCES_DB` para testes e `/app/instance/sequences.db` como padrão.
   - Semear as 6 originais com IDs 0–5 e `INSERT OR IGNORE`.
   - Verificação: testes com banco temporário; reabrir o arquivo e confirmar seed
     único, IDs corretos e persistência das sequências criadas.

3. [x] Fase 3 — Implementar matching e integrar ao backend (~1–2 h)
   - Implementar `sequencia_compativel(musica, acordes)`: bloco contíguo e
     ordenado em `musica.cifra` + `set(musica.cifra) ⊆ set(acordes)`.
   - Normalizar com `strip()` + primeira letra maiúscula; preservar `F7M`/`F7m`.
   - Remover o uso de `seqs_famosas` no endpoint de sequência, mantendo
     `Musica` e o carregamento do CSV inalterados.
   - Verificação: comparar o novo caminho com `regressao_6.json`; as 6 devem
     retornar exatamente os mesmos IDs e a mesma ordem.

4. [x] Fase 4 — Expor API de catálogo e manter compatibilidade (~2–3 h)
   - Adicionar `GET /sequencias` e `POST /sequencias`.
   - Adicionar `GET /similares?sequencia_id=<id>`.
   - Manter `GET /similares?sequencia=<acordes>`: tentar `legacy_key` e depois
     `chave` canônica.
   - Validar entrada, rejeitar duplicata com `409` e entrada inválida com `400`;
     manter `json.dumps` e o formato de resultado atual.
   - Verificação: testes de API e smoke com `curl` para listar, criar, duplicar,
     validar, buscar por id, buscar pelo formato legado e filtrar por gênero.

5. [x] Fase 5 — Atualizar o frontend (~2–3 h)
   - Em `sequencia.js`, remover as 4 sequências hardcoded e carregar
     `GET /sequencias`.
   - Em `sequencia.html`, renderizar o catálogo com `ng-repeat`, adicionar
     formulário de cadastro, estados de erro/loading e ajustar
     `music.diferenca.length`.
   - Enviar `POST /sequencias` e buscar com `sequencia_id`.
   - Verificação: smoke em `#/porsequencia` cobrindo as 6 originais, cadastro,
     conflito, validação e busca de uma sequência nova.

6. [x] Fase 6 — Persistência no Docker e documentação (~1 h)
   - Declarar `VOLUME ["/app/instance"]` e garantir o diretório no `Dockerfile`.
   - Documentar o volume nomeado no `README.md`.
   - Adicionar `instance/` ao `.gitignore` e ao `.dockerignore`.
   - Verificação: build, execução com `-v ciframe-sequences:/app/instance`,
     cadastro, restart e recriação do container com o catálogo preservado.

7. [x] Fase 7 — Verificação final e handoff (~1 h)
   - Rodar toda a suíte, a regressão das 6, o teste Docker e a medição de
     desempenho.
   - Preencher `04-test-report.md` com comandos, resultados e limitações.
   - Verificação: todos os critérios da definição de pronto satisfeitos e
     nenhuma alteração fora dos arquivos listados.

## Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `sequencias.py` (novo) | Schema, seed, repositório, normalização e matching. |
| `main.py` | Remover catálogo hardcoded, inicializar banco, adicionar rotas de catálogo, busca por id e fallback legado. |
| `Dockerfile` | Declarar `VOLUME ["/app/instance"]` e garantir o diretório. |
| `README.md` | Documentar o volume nomeado no `docker run`. |
| `.gitignore` | Ignorar `instance/`. |
| `.dockerignore` | Excluir `instance/` da imagem. |
| `static/assets/js/controllers/sequencia.js` | Carregar catálogo real, cadastrar e buscar por id. |
| `static/templates/sequencia.html` | Formulário, estados de erro/loading e ajuste de `diferenca`. |
| `tests/__init__.py` (novo) | Pacote de testes. |
| `tests/fixtures/regressao_6.json` (novo) | Snapshot dos IDs/ordem das 6 originais. |
| `tests/test_sequencias.py` (novo) | Testes de normalização, matching, schema, seed e repositório. |
| `tests/test_api.py` (novo) | Testes de listagem, cadastro, duplicidade, validação, busca e legado. |
| `docs/features/sequencias-customizadas/04-test-report.md` | Registrar evidências e resultados da verificação. |
| `tests/test_api.py` | Adicionado teste para serialização de `Musica` após busca por sequência. |
| `AGENTS.md` | Atualizado para descrever o catálogo em SQLite. |

Não mudam: `data/top/dataset_final.csv`, `requirements.txt`,
`static/assets/js/app.js`, `static/assets/js/routes.js` e `static/index.html`.

## Riscos e mitigação

- **Quebrar os resultados das 6 originais:** capturar o snapshot na fase 1 e
  bloquear a fase 4 até a regressão passar. `SEQ_FAMOSA` permanece no CSV como
  referência.
- **Matching lento:** medir uma busca sobre as 67.585 músicas. Se ficar muito
  acima de ~0,2 s, avaliar cache de tokens normalizados em memória sem alterar o
  CSV; registrar a decisão no plano antes de mudar. O cache foi implementado em
  `sequencias.py` e aquecido no startup; no host, as buscas ficaram em ~0,06 s
  após o aquecimento, sem alterar o CSV.
- **Diferença de normalização:** `lower()` foi descartado por conflitar
  `F7M`/`F7m`; testes unitários cobrem caixa, espaços e limites.
- **Seed duplicado ou banco parcial:** usar `INSERT OR IGNORE`, IDs explícitos e
  inicialização idempotente; testar reabertura e banco já existente.
- **Perda de dados ao recriar o container:** usar volume nomeado, documentar no
  README e testar `docker restart` + `docker rm`/`docker run`.
- **Volume sem permissão de escrita:** criar `/app/instance` no build/startup e
  validar no teste Docker; o container roda como root por padrão.
- **Duplicatas/abuso no catálogo aberto:** chave única, validação 1–32/32 e
  respostas `409`/`400`; rate limiting fica fora do escopo.
- **Ambiguidade do `?sequencia=` concatenado:** manter o parâmetro para as 6 e
  usar `sequencia_id` para sequências novas.
- **Frontend sem testes automatizados:** smoke manual obrigatório na fase 5;
  manter as mudanças restritas ao controller e ao template.
- **Regressão silenciosa por falta de testes no projeto:** criar suíte com
  `unittest` da stdlib, sem dependência nova, e rodar na fase 7.

## Ajustes pós-planejamento

- **Serialização de `Musica`:** Não mutar instâncias de `Musica` com caches de `frozenset`/`tuple` (isso quebrava `json.dumps` em `/musicas`/`/musica/<id>/`). O cache foi movido para um dicionário em módulo `sequencias._CIFRAS_NORMALIZADAS`, aquecido no startup com `preparar_cache_normalizacao()`. Foi adicionado `tests/test_api.py::test_endpoints_de_musicas_continuam_serializaveis_apos_busca` para cobrir essa regressão.
- **Documentação/stack:** Atualizados `README.md` (descrição da stack, comando com volume) e `AGENTS.md` (backend passa a descrever SQLite em `instance/sequences.db`) para refletir o estado real da implementação.

## Definição de pronto

- [x] Banco novo cria a tabela e semeia as 6 originais com IDs 0–5; `GET
      /sequencias` devolve exatamente essas 6 no primeiro start.
- [x] `POST /sequencias` cadastra uma sequência nova e devolve `201`; duplicata
      devolve `409`; entrada vazia, longa ou malformada devolve `400`.
- [x] Busca por `sequencia_id` retorna os mesmos campos, filtros de gênero e
      paginação do fluxo atual.
- [x] `GET /similares?sequencia=...` continua funcionando para as 6.
- [x] As 6 originais retornam exatamente os IDs e a ordem do snapshot
      (199/296/4/5/7/3).
- [x] O frontend lista o catálogo real, cadastra uma sequência, mostra erros e
      busca a sequência criada.
- [x] O catálogo persiste após restart e após recriação do container com o
      volume nomeado.
- [x] Todos os testes passam; nenhuma dependência nova; respostas continuam com
      `json.dumps`; músicas/gêneros continuam no CSV em memória.
- [x] `04-test-report.md` registra comandos, resultados e limitações.
