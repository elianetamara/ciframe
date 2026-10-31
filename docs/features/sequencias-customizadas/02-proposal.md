# Proposta — Sequências de Acordes Customizadas

## Abordagem escolhida

A proposta escolhida é manter um único algoritmo de matching para todas as
sequências (as 6 originais e as novas), persistir apenas o catálogo de
sequências em SQLite e fazer o frontend consumir esse catálogo pela API. O
catálogo de músicas/gêneros continua vindo do CSV em memória, o deploy continua
sendo um único `Dockerfile` local e as respostas continuam sendo
`json.dumps(...)`, não `jsonify`.

A decisão usa como base o documento de pesquisa
`docs/features/sequencias-customizadas/01-research.md`: a única regra testada
que reproduziu exatamente os resultados atuais das 6 sequências foi
“bloco contíguo e ordenado em `musica.cifra` + vocabulário da música contido no
vocabulário da sequência” (`01-research.md:79-173`).

### Algoritmo de matching

**Escolha.** Uma sequência `S = [s0, s1, ..., sn-1]` é considerada presente em
uma música `M` quando as duas condições abaixo são verdadeiras:

1. `S` aparece como uma sublista **contígua e na mesma ordem** dentro de
   `musica.cifra` (`musica.py:16`); e
2. `set(musica.cifra) ⊆ set(S)` — todos os acordes usados na música pertencem
   ao conjunto de acordes da sequência.

Antes da comparação, cada acorde passa por uma normalização canônica:
`strip()` e apenas o primeiro caractere em maiúscula. O restante da string é
preservado. Assim, `am` vira `Am`, `c` vira `C`, `eb7` vira `Eb7`, mas `F7M` e
`F7m` continuam distintos. Não há normalização de enarmonia (`C#`/`Db`), de
extensões, de slash chords ou remoção de baixo.

A ordem importa; repetições dentro da música são permitidas desde que o bloco
continue contíguo; um acorde extra dentro do bloco quebra o match; e qualquer
acorde da música fora do conjunto `S` quebra a segunda condição. Músicas com
`musica.cifra` vazia não casam com sequências não vazias.

O matching é calculado em tempo de requisição para todas as sequências, inclusive
as 6 originais. `musica.seqs_famosas`/`SEQ_FAMOSA` deixa de ser consultado pelo
endpoint de sequência; a coluna e o campo em `Musica` permanecem no CSV e em
`musica.py:18` sem uso por esse caminho.

**Justificativa.** A pesquisa mostrou que “contíguo apenas”, “subsequência com
lacunas” e “subconjunto não ordenado” produziriam contagens muito diferentes das
atuais (`01-research.md:155-173`). A regra escolhida foi a única que reproduziu
os 6 conjuntos e a ordem dos resultados (`01-research.md:174-221`). Usar a mesma
regra para sequências novas evita dois comportamentos diferentes no mesmo
endpoint e não exige manter duas fontes de verdade (tag para as antigas e
cálculo para as novas).

A normalização escolhida é um meio-termo entre comparar strings exatamente como
estão e aplicar `lower()` em tudo. O `lower()` reduziria diferenças de caixa, mas
os dados têm 151 grupos de grafias que colidem, incluindo `F7M`/`F7m`,
`GM7(9)`/`Gm7(9)` e `DM7`/`Dm7` (`01-research.md:145-151`); isso poderia criar
falsos positivos. A normalização “primeira letra maiúscula” também foi testada
contra as 6 sequências e reproduziu exatamente os mesmos conjuntos.

**Alternativas descartadas.**

- **Contíguo ordenado apenas:** definição mais direta, mas mudaria as 6
  originais (866/1.216/3.110/96/1.039/132 em vez de 199/296/4/5/7/3) e quebraria
  o critério de regressão do enunciado.
- **Subsequência ordenada com lacunas:** aceitaria acordes intermediários, mas
  produziria 4.763/5.887/13.643/427/3.641/280 resultados e perderia a noção de
  bloco contíguo.
- **Subconjunto não ordenado:** descartaria ordem e contiguidade; além das
  contagens da ordem de 8.000–9.000, incluiria as 8.141 músicas sem cifra.
- **Dois algoritmos** (tag/regra antiga para as 6 e regra nova para as demais):
  preservaria a regressão sem adaptar as antigas, mas criaria dois
  comportamentos no mesmo endpoint, dois caminhos de manutenção e resultados
  inconsistentes para sequências equivalentes.
- **Normalização exata:** evitaria qualquer colisão, mas exigiria que o
  visitante digitasse a caixa exata de cada acorde.
- **Normalização por `lower()`:** foi usada na geração histórica da tag, mas
  conflita acordes semanticamente distintos.
- **Normalização mais agressiva** (reduzir à fundamental, remover extensões ou
  baixo): não existe no código atual e mudaria a semântica das 6 sequências sem
  uma regra validada.

### Banco de dados

**Escolha.** SQLite, usando o módulo `sqlite3` da stdlib do Python 3.9. O arquivo
fica em `/app/instance/sequences.db` (configurável por variável de ambiente para
testes). O banco contém somente o catálogo de sequências. `musicas`, `generos`,
`genero_musicas` e `acordes` continuam sendo carregados do CSV em memória como
hoje (`main.py:49-98`).

Para persistência entre containers recriados, o `Dockerfile` passa a declarar
`VOLUME ["/app/instance"]` e o comando documentado passa a usar um volume
nomeado, por exemplo
`docker run -p 8080:8080 -v ciframe-sequences:/app/instance ciframe`. O arquivo
`instance/` entra em `.gitignore` e `.dockerignore` para não ser copiado para a
imagem nem para o repositório.

**Justificativa.** SQLite é embarcado, não exige serviço adicional, não adiciona
dependência ao `requirements.txt`, tem transações e mantém o modelo de container
único do ADR `docs/adr/0001-local-only-docker-deploy.md:9-16`. O gunicorn atual
roda com 1 worker por default (`Dockerfile:12`), então o lock de escrita do
SQLite não é um problema para o volume de escrita desta feature.

O volume é necessário porque o comando atual
`docker run -p 8080:8080 ciframe` (`README.md:15-17`) mantém dados apenas na
camada gravável do container: `docker restart` preserva, mas `docker rm` +
`docker run` não. O requisito de persistência do enunciado só fica robusto com
um volume nomeado ou bind mount.

**Alternativas descartadas.**

- **TinyDB:** exigiria dependência nova, reescreve o arquivo inteiro e não tem
  as mesmas garantias transacionais.
- **`shelve`/`dbm`/`pickle`/JSON manual:** são stdlib e simples, mas não têm
  consulta/transação robusta e aumentam o risco de corrupção/concorrência;
  `pickle` ainda adiciona risco de desserialização.
- **SQLite/DuckDB em memória:** perderia o catálogo ao reiniciar o processo ou
  o container, falhando no requisito funcional.
- **DuckDB/LMDB:** embarcados, mas exigiriam dependência nova e aumentariam o
  build/tamanho da imagem sem necessidade para um catálogo pequeno.
- **PostgreSQL/MySQL:** exigiriam serviço externo, o que conflita com o modelo
  de container único e “sem serviços externos adicionais” fixado no enunciado.
- **Persistência apenas na camada do container, sem volume:** sobreviveria a
  `docker restart`, mas não à recriação do container, que é o caso que o volume
  resolve.

### Esquema de dados (alto nível)

Uma única tabela, `sequencias`:

| Campo | Tipo | Regra |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | IDs 0–5 reservados para as 6 originais; novas sequências começam em 6. |
| `acordes` | `TEXT NOT NULL` | JSON com a lista ordenada de acordes já normalizados. |
| `chave` | `TEXT NOT NULL UNIQUE` | Acordes unidos por `;`, por exemplo `C;G;Am;F`; identifica a sequência duplicada. |
| `legacy_key` | `TEXT UNIQUE NULL` | Somente para as 6 originais: `BmGDA`, `CGAmF`, `EmG`, `CA7DmG7`, `GmF`, `CC7FFm`. |
| `origem` | `TEXT NOT NULL` | `seed` para as 6 originais, `custom` para as novas. |
| `criado_em` | `TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP` | Auditoria mínima; não há login/autoria. |

A inicialização é idempotente: cria a tabela se não existir e insere as 6
sequências originais com IDs 0–5 usando `INSERT OR IGNORE`. Não há migração de
dados do CSV: o catálogo original era um `dict` literal em `main.py:40-45`; a
coluna `SEQ_FAMOSA` do CSV permanece no arquivo, mas não é migrada nem usada pelo
endpoint de sequência.

### API

Todos os endpoints novos e alterados continuam devolvendo `json.dumps(...)` como
string, nunca `jsonify`.

**`GET /sequencias`** — lista o catálogo real, ordenado por `id`:

```json
[
  {"id": 0, "acordes": ["Bm", "G", "D", "A"], "origem": "seed"},
  {"id": 6, "acordes": ["D", "A", "Bm", "G"], "origem": "custom"}
]
```

**`POST /sequencias`** — cadastro anônimo. Corpo JSON:

```json
{"acordes": ["D", "A", "Bm", "G"]}
```

- `201` com `{"id": 6, "acordes": ["D", "A", "Bm", "G"], "origem": "custom"}`
  em caso de sucesso.
- `400` se `acordes` não for uma lista, estiver vazia, tiver acorde vazio após
  `strip`, tiver mais de 32 acordes ou tiver acorde com mais de 32 caracteres.
- `409` se a `chave` já existir, com o `id` e a lista da sequência existente.

Repetições de acorde dentro de uma sequência são permitidas (a chave preserva a
ordem e a multiplicidade). Duplicata é a mesma lista ordenada após normalização;
`C,G` e `G,C` são sequências diferentes.

**`GET /similares?sequencia_id=<id>`** — busca canônica usada pelo frontend
novo. Mantém os parâmetros `generos` e `pagina` e o mesmo formato de resultado
de `get_similares_por_sequencia` (`main.py:210-220`). ID inexistente devolve
`[]`.

**`GET /similares?sequencia=<acordes>`** — compatibilidade com o contrato atual.
Primeiro tenta a chave legada sem vírgulas (`main.py:191`), exatamente como hoje;
se não encontrar, interpreta o valor como lista separada por vírgula, normaliza,
junta com `;` e procura a `chave` no catálogo. Sequência desconhecida continua
devolvendo `[]`.

**Justificativa.** Manter `?sequencia=` evita quebrar o frontend/URLs atuais e
preserva o caso das 6 originais. Adicionar `?sequencia_id=` para o frontend novo
evita a ambiguidade da concatenação sem separador observada na pesquisa
(`01-research.md:370-375`). O cadastro aberto e anônimo não tem login, conforme
o requisito funcional.

**Alternativas descartadas.**

- **Somente `?sequencia=<concatenação>` para tudo:** manteria um único contrato,
  mas a concatenação sem separador pode colidir entre tokenizações diferentes e
  não dá uma identidade estável para o catálogo.
- **Somente `?sequencia_id=<id>`:** mais limpo, mas quebraria o formato atual e
  a compatibilidade dos links/testes existentes.
- **Permitir duplicatas:** simplificaria o `POST`, mas criaria entradas
  indistinguíveis e buscas redundantes.
- **Retornar a sequência existente em vez de `409`:** evitaria erro no cliente,
  mas exigiria definir “igualdade” de forma implícita e esconderia o conflito.
- **Sem validação de tamanho:** deixaria o catálogo aberto a listas vazias ou
  muito grandes; por isso há limites simples de 1–32 acordes e 32 caracteres.

### Frontend

**Escolha.** A página `#/porsequencia` passa a carregar o catálogo real:

- `static/assets/js/controllers/sequencia.js` deixa de criar
  `sequencia1`..`sequencia4` (`sequencia.js:2-37`) e, na inicialização do
  controller, faz `GET /sequencias` para preencher
  `vm.sequenciasFamosas` (o nome pode ser mantido para preservar o template).
- O template continua usando `ng-repeat` sobre
  `Sequencia.sequenciasFamosas` (`sequencia.html:6-8`) e `df-hex` para desenhar
  os acordes; as 6 originais e as novas aparecem juntas.
- Um formulário novo em `sequencia.html` recebe os acordes separados por vírgula,
  valida no cliente e envia `POST /sequencias` com `{"acordes": [...]}`. Após
  sucesso, recarrega o catálogo e permite pesquisar a sequência criada; em caso
  de `409`/`400`, mostra a mensagem devolvida.
- A busca passa a usar `similares?sequencia_id=<id>` (com `generos` opcional),
  mantendo o mesmo fluxo de resultados.
- O template deixa de depender de `music.diferenca.length`
  (`sequencia.html:43`), campo que a busca por sequência não devolve.

O dropdown de gêneros continua usando a constante `GENEROS` de
`static/assets/js/app.js:6-58`; trocar para `GET /generos` não é necessário para
o catálogo de sequências e fica fora do escopo. Nenhum script novo precisa ser
incluído em `static/index.html` se a lógica permanecer em `sequencia.js`.

**Justificativa.** O requisito fixa que a página reflita o catálogo real vindo do
backend e permita cadastro. O `ng-repeat` e a diretiva `df-hex` já existem; a
mudança principal é a fonte dos dados e o formulário. Usar `sequencia_id` evita
reimplementar no cliente a concatenação ambígua de acordes.

**Alternativas descartadas.**

- **Manter a lista hardcoded:** não atende ao requisito de refletir o backend.
- **Cadastro por seletor de acordes:** melhor UX, mas exige uma UI nova e uma
  lista curada; `/acordes` devolve 6.653 tokens crus, incluindo ruído
  (`01-research.md:381-382`), então não é uma lista pronta.
- **Cadastro apenas por texto no backend, sem formulário no frontend:** não
  atende ao requisito de permitir cadastro pela página.
- **Buscar gêneros do backend:** resolveria a diferença 51/52 já existente, mas
  amplia o escopo sem necessidade para esta feature.
- **Criar um controller/serviço novo:** aumentaria a superfície sem ganho; o
  controller atual já concentra o fluxo da página.

### Persistência, configuração e rollout

- `Dockerfile` passa a declarar `VOLUME ["/app/instance"]`; a aplicação cria o
  diretório/arquivo no startup.
- `README.md` passa a documentar o volume nomeado no `docker run`; sem volume,
  só o restart do mesmo container é garantido.
- `.dockerignore` e `.gitignore` passam a excluir `instance/`.
- O seed das 6 sequências roda no startup, de forma idempotente, antes de a
  aplicação aceitar requisições.
- Um módulo pequeno de acesso ao SQLite pode ser adicionado ao backend
  (por exemplo `sequencias.py`) para manter `main.py` focado nas rotas; a
  `Musica` (`musica.py:1-25`) e o carregamento do CSV (`main.py:49-98`) não
  mudam.
- Nenhuma dependência nova entra em `requirements.txt`; nenhum serviço externo
  entra no deploy.

## Validação planejada

1. **Regressão obrigatória:** antes de remover o caminho por `seqs_famosas`,
   capturar um snapshot dos IDs retornados, na ordem, para as 6 sequências (todos
   os gêneros e alguns filtros de gênero). Depois da mudança, comparar com o
   snapshot. Os números de referência são 199, 296, 4, 5, 7 e 3
   (`01-research.md:188-203`).
2. **Testes unitários do matching:** listas sintéticas cobrindo bloco contíguo,
   acordes fora de ordem, acorde extra no meio do bloco, repetição, música com
   acorde fora do conjunto e cifra vazia.
3. **Testes do banco:** inicialização idempotente, seed com IDs 0–5, unicidade
   da `chave`, reabertura do arquivo mantendo sequências criadas e persistência
   após reinicialização do processo.
4. **Testes de API:** `GET /sequencias`, `POST` válido, `POST` duplicado (409),
   `POST` inválido (400), busca por `sequencia_id`, busca legada por
   `?sequencia=Bm,G,D,A`, filtro de gênero e paginação. Usar o test client do
   Flask.
5. **Teste de persistência no Docker:** construir a imagem, rodar com volume
   nomeado, cadastrar uma sequência, reiniciar/recriar o container e confirmar
   que `GET /sequencias` ainda devolve a sequência.
6. **Smoke no browser:** carregar `#/porsequencia`, confirmar as 6 originais,
   cadastrar uma nova, buscá-la e verificar os cartões de resultado.
7. **Desempenho:** medir uma busca por sequência sobre as 67.585 músicas. A
   pesquisa mediu cerca de 1,08 s para as 6 juntas; a expectativa é de ordem de
   ~0,2 s por sequência, sem alterar a ordem dos resultados.

## Alternativas consideradas e descartadas

| Área | Alternativa descartada | Motivo |
|---|---|---|
| Matching | Contíguo sem a condição de subconjunto | Resultados das 6 mudam (ex.: 866 em vez de 199 para o id 0), quebrando a regressão. |
| Matching | Subsequência ordenada com lacunas | Resultados muito maiores e sem bloco contíguo (ex.: 13.643 para `Em G`). |
| Matching | Subconjunto não ordenado | Ignora ordem/contiguidade e casa todas as 8.141 músicas sem cifra. |
| Matching | Regra antiga para as 6 + regra nova para as novas | Dois comportamentos e duas fontes de verdade no mesmo endpoint. |
| Normalização | `lower()` em tudo | Conflita 151 grupos de grafias, incluindo `F7M`/`F7m`. |
| Normalização | Comparação exata | Exigiria caixa exata do visitante. |
| Banco | TinyDB / `shelve` / JSON / pickle | Dependência ou ausência de transações/robustez; mesmo problema de volume. |
| Banco | SQLite em memória | Perde o catálogo ao reiniciar. |
| Banco | DuckDB / LMDB | Dependência nova e maior superfície para um catálogo pequeno. |
| Banco | PostgreSQL / MySQL | Serviço externo, conflita com o container único. |
| Persistência | Sem volume | Não sobrevive à recriação do container. |
| API | Só `?sequencia=` concatenado | Ambiguidade de tokenização e falta de identidade estável. |
| API | Só `?sequencia_id=` | Quebra o contrato/links atuais. |
| API | Permitir duplicatas | Catálogo com entradas indistinguíveis. |
| Frontend | Manter as 4 hardcoded | Não reflete o catálogo real, contrariando o requisito. |
| Frontend | Seletor/catálogo curado de acordes | `/acordes` não é uma lista curada e a UI seria maior que o necessário. |

## Decisões confirmadas

- **Limites de proteção:** 1–32 acordes por sequência e 32 caracteres por acorde.
  São limites de proteção contra abuso e entradas degeneradas, não uma regra
  musical; permanecem validados no `POST /sequencias`.
- **Edição e exclusão:** fora do escopo. O enunciado não trata dessas operações e
  o catálogo cresce apenas por cadastro.
- **Dropdown de gêneros:** permanece como está, usando a constante `GENEROS` de
  `static/assets/js/app.js:6-58`. Migrar para `GET /generos` não faz parte desta
  atividade.
- **`SEQ_FAMOSA`:** permanece no CSV e em `musica.py:18`, pois é a referência
  histórica necessária para o teste de regressão das 6 originais. O endpoint de
  sequência deixa de usá-la em runtime, mas a coluna e o campo não são removidos
  nem migrados.

## Escopo explícito

**Dentro do escopo:**

- Criar a tabela SQLite e o seed idempotente das 6 sequências originais.
- Persistir sequências customizadas com IDs próprios e volume de dados.
- Implementar `GET /sequencias`, `POST /sequencias` e a busca por
  `sequencia_id`, preservando `?sequencia=` para compatibilidade.
- Calcular o matching em tempo real para as 6 originais e para as novas, com a
  regra “contíguo + subset” e a normalização definida acima.
- Trocar a lista hardcoded do frontend pelo catálogo da API e adicionar o
  formulário de cadastro.
- Validar a regressão das 6 sequências e a persistência no ciclo Docker.
- Atualizar `Dockerfile`, `README.md`, `.gitignore` e `.dockerignore` para o
  volume do banco.

**Fora do escopo (e por quê):**

- Login, autoria, moderação ou rate limiting: o requisito fixa catálogo aberto e
  anônimo.
- Editar ou remover sequências: não está no enunciado; o catálogo só cresce.
- Paginação, busca ou filtros do catálogo de sequências: o catálogo é pequeno e
  a página atual lista tudo.
- Migrar músicas ou gêneros para o banco: o enunciado fixa que eles continuam
  vindo do CSV em memória.
- Alterar a ordem, a paginação ou o formato de resultado das buscas existentes.
- Modernizar o AngularJS ou trocar o modelo de deploy/container único.
- Normalização de enarmonia, extensões, slash chords ou remoção de baixo.
- Remover a coluna `SEQ_FAMOSA` do CSV ou o campo de `Musica`; eles permanecem,
  mas o endpoint de sequência deixa de usá-los.
