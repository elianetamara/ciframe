# Pesquisa — Sequências de Acordes Customizadas

## Resumo dos achados

Hoje o backend não calcula, em tempo de requisição, se uma sequência aparece em
uma música: `GET /similares?sequencia=...` remove as vírgulas da entrada,
procura a string resultante em um dicionário fixo de 6 sequências e filtra as
músicas por uma tag pré-computada (`seqs_famosas`) lida do CSV. A condição
histórica que gerou essas tags — e que reproduziu exatamente os 514 resultados
atuais, inclusive a ordem — é: a sequência aparece como bloco **contíguo e
ordenado** em `musica.cifra`, e **todos** os acordes da música pertencem ao
conjunto de acordes da sequência. O carregamento atual tem 67.585 músicas e
6.653 grafias distintas de acorde; não existe banco de dados no projeto. O
frontend mostra apenas 4 sequências hardcoded (ids 0, 1, 4 e 5), usa uma lista
fixa de 51 gêneros e só faz `GET`; não há tela nem endpoint de cadastro/listagem
do catálogo. O `Dockerfile` atual é um único container `python:3.9-slim`, sem
`VOLUME` declarado, e o comando documentado em `README.md` não monta volume, de
modo que a persistência de um arquivo de banco depende do ciclo de vida do
container ou de configuração externa de volume.

## Fluxo atual, ponta a ponta

1. No start da aplicação, `main.py:49-98` abre `data/top/dataset_final.csv` e
   monta `musicas` (um `OrderedDict` ordenado por popularidade), além de
   `genero_musicas`, `generos` e `acordes`.
2. Cada linha vira um objeto `Musica` (`main.py:69-74`; classe em
   `musica.py:1-25`). `musica.cifra` é a lista ordenada de acordes;
   `musica.acordes` é `list(set(cifra))`, portanto perde ordem; e
   `musica.seqs_famosas` é a lista de tags da coluna `SEQ_FAMOSA`
   (`main.py:63`, `musica.py:16-18`).
3. O frontend `#/porsequencia` (`static/assets/js/routes.js:17-21`) exibe 4
   sequências hardcoded no controller. Ao clicar em uma delas,
   `Sequencia.pesquisarPorSequencia` (`static/assets/js/controllers/sequencia.js:63-90`)
   monta `similares?sequencia=<acordes separados por vírgula>` e, opcionalmente,
   `&generos=<um gênero>`.
4. No backend, `get_similares` (`main.py:170-201`) remove as vírgulas
   (`main.py:191`), procura a string exata em `sequencias` (`main.py:40-45` e
   `main.py:194-196`) e, se achar, chama
   `get_similares_por_sequencia` (`main.py:203-223`). Se não achar, devolve `[]`.
5. `get_similares_por_sequencia` percorre a coleção filtrada por gênero e testa
   `str(id_seq) in musica.seqs_famosas` (`main.py:208-209`), montando o mesmo
   formato de dicionário usado pelas buscas por acordes/música. O endpoint
   pagina o resultado com `TAM_PAGINA = 100` (`main.py:35`, `main.py:226-228`).
6. A resposta é `json.dumps(...)` como string, não `jsonify` (`main.py:142`,
   `main.py:197`, `main.py:201`). O controller AngularJS atribui o array
   recebido a `vm.musics` (`static/assets/js/controllers/sequencia.js:77-84`) e o
   template renderiza os cartões (`static/templates/sequencia.html:40-59`).

## Perguntas que você precisa responder

1. **Algoritmo de matching**: hoje, as 6 sequências hardcoded em `main.py` (linhas
   40-45) são comparadas contra músicas via uma tag pré-computada
   (`SEQ_FAMOSA`/`seqs_famosas`, vinda do CSV). Sequências cadastradas pelo usuário
   não têm essa tag — o matching precisa ser calculado em tempo real a partir da
   lista de acordes de cada música (`musica.acordes`/`musica.cifra`). O que vai
   definir "a sequência X aparece na música Y"? A ordem dos acordes importa?
   Repetições de acorde dentro da música importam? É preciso normalizar (ex.:
   maiúsculas/minúsculas, variações de escrita do mesmo acorde)?
2. **Validação da hipótese**: rode o algoritmo que você está considerando contra os
   dados reais em `data/top/dataset_final.csv`, para as 6 sequências hoje
   hardcoded, e confirme (ou refute) que ele reproduz os mesmos matches que o
   código atual produz via `seqs_famosas`. Esse é o bar mínimo de correção que
   você vai usar na fase de testes.
3. **Banco de dados**: quais bancos embarcados (sem serviço externo adicional) são
   viáveis dentro do container Docker único e local-only já documentado em
   `docs/adr/0001-local-only-docker-deploy.md`? O que cada opção implica para o
   `Dockerfile` atual e para a persistência dos dados entre reinícios do
   container?
4. **Frontend existente**: o que a página `#/porsequencia`
   (`static/templates/sequencia.html` +
   `static/assets/js/controllers/sequencia.js`) já faz? Repare que ela tem hoje uma
   lista *hardcoded no JavaScript* de 4 sequências (`sequencia1`..`sequencia4`),
   diferente das 6 que existem no backend — um detalhe real e pré-existente do
   código, não um erro seu, que vale entender antes de decidir o que precisa
   mudar.

## Registro das descobertas

### 1. Algoritmo de matching

**O código em produção não compara a sequência com os acordes da música.** Ele
consulta uma tag pré-computada:

- O catálogo fixo está em `main.py:40-45`:

  ```python
  sequencias = {'BmGDA': 0, 'CGAmF': 1, 'EmG': 2,
                'CA7DmG7': 3, 'GmF': 4, 'CC7FFm': 5}
  ```

- O endpoint transforma a sequência recebida em uma única string sem vírgulas
  (`main.py:191`). Assim, `sequencia=Bm,G,D,A` vira a chave `BmGDA`. A busca é
  exata: não há trim, `lower()` nem parsing de acordes individuais nesse ponto.
- A comparação com as músicas é `str(id_seq) in musica.seqs_famosas`
  (`main.py:208-209`). `musica.seqs_famosas` vem diretamente da coluna
  `SEQ_FAMOSA` do CSV, separada por `;` (`main.py:63`).
- Não existe nenhuma outra lógica de sequência no `main.py`. O endpoint
  `/similares` também aceita `acordes` e `id_unico_musica` (`main.py:173-199`),
  mas esses caminhos usam interseção de conjuntos, não ordem de sequência.

**A origem histórica da tag.** O script legado `scripts/generate_data_set.py:7-24`
tem a função `get_famosas`, que gerou a coluna:

```python
seqs = ['bm;g;d;a', 'c;g;am;f', 'em;g', 'c;a7;dm;g7', 'gm;f', 'c;c7;f;fm']
...
acorde = acorde.lower()
if s in acorde:
    achou = True
    for l in acorde.split(';'):
        tokens = s.split(';')
        if l not in tokens:
            achou = False
            break
```

Em `scripts/generate_data_set.py:84-89`, `famosas` é calculado e incluído na
linha CSV impressa pelo script; essa é a coluna que o backend lê como
`SEQ_FAMOSA`. Dessa função, a condição efetiva para uma música receber a tag de
uma sequência `S` é:

1. `S` (em minúsculas) é uma **substring contígua** da cifra da música também
   em minúsculas, quando a cifra é tratada como uma string separada por `;`; e
2. **todo** acorde da música pertence ao conjunto de acordes de `S` — caso
   contrário, o laço interno marca `achou = False`.

Em termos da lista que o backend usa em memória (`musica.cifra`), a regra
equivalente é:

- `S` aparece como **bloco contíguo e na mesma ordem** dentro de
  `musica.cifra`; e
- `set(musica.cifra) ⊆ set(S)`.

**Ordem, repetições e normalização no comportamento atual:**

- **Ordem importa** para a tag histórica: a comparação é por substring contígua.
  Uma música com os mesmos acordes em outra ordem não recebe a tag.
- **Repetições dentro da música** não invalidam por si só: o bloco procurado
  pode aparecer em qualquer posição da cifra. Porém, um acorde extra inserido
  no meio do bloco quebra a contiguidade; e qualquer acorde da música fora do
  conjunto `S` quebra a segunda condição.
- **Normalização no código vivo:** nenhuma. A chave do dicionário é comparada
  exatamente com a string montada a partir das vírgulas; `Bm,G,D,A` funciona,
  mas uma variação de caixa/escrita que não gere a chave exata cai em `[]`
  (`main.py:194-197`).
- **Normalização na geração histórica da tag:** `lower()` nos dois lados
  (`scripts/generate_data_set.py:10-13`). Nos dados atuais, há 151 grupos de
  grafias que colidem ao lowercase, incluindo pares semanticamente distintos
  como `F7M`/`F7m`, `GM7(9)`/`Gm7(9)` e `DM7`/`Dm7`. Para as 6 sequências
  originais, comparar “exato” versus “lowercase” produziu os mesmos conjuntos
  de músicas; a diferença aparece como possibilidade para sequências novas.
- **`musica.acordes` não serve para matching ordenado:** em `musica.py:17` ele é
  `list(set(cifra))`, sem ordem. A ordem só existe em `musica.cifra`
  (`musica.py:16`).

**Contagens que mostram o efeito de cada definição.** Foram calculadas com as
67.585 músicas carregadas pelo parser do `main.py`; “atual” é a contagem via
`seqs_famosas`, e as demais colunas são definições alternativas sobre
`musica.cifra`:

| Sequência | id | Atual (tag) | Contíguo apenas | Contíguo + subset | Subset apenas | Subsequência ordenada (com lacunas) |
|---|---:|---:|---:|---:|---:|---:|
| `Bm G D A` | 0 | 199 | 866 | 199 | 9.014 | 4.763 |
| `C G Am F` | 1 | 296 | 1.216 | 296 | 9.099 | 5.887 |
| `Em G` | 2 | 4 | 3.110 | 4 | 8.165 | 13.643 |
| `C A7 Dm G7` | 3 | 5 | 96 | 5 | 8.194 | 427 |
| `Gm F` | 4 | 7 | 1.039 | 7 | 8.159 | 3.641 |
| `C C7 F Fm` | 5 | 3 | 132 | 3 | 8.198 | 280 |

A única coluna que coincide com a atual nas 6 linhas é **contíguo + subset**.
A coluna “Subset apenas” inclui as 8.141 músicas cujo `musica.cifra` é vazio (o
conjunto vazio é subconjunto de qualquer sequência); ela está na tabela apenas
para mostrar o efeito de ignorar ordem/contiguidade.

### 2. Validação da hipótese

**Método executado.** Foi rodado um script local que importa `main.py` com um
stub do módulo `flask` (o ambiente de pesquisa não tinha Flask instalado), de
modo que o parser e as funções reais do backend fossem usados sem subir o
servidor. Para cada uma das 6 sequências:

1. obteve-se o resultado atual chamando
   `main.get_similares_por_sequencia(id_seq, main.generos)`;
2. calculou-se o candidato percorrendo a mesma coleção devolvida por
   `main.apply_filtro(main.musicas.values(), main.generos)` e aplicando
   “contíguo + subset” sobre `musica.cifra`;
3. comparou-se a lista de `id_unico_musica` **na ordem** retornada.

**Resultado.** As 6 listas ficaram idênticas, inclusive na ordem:

| Sequência | id | Resultado atual | Candidato contíguo + subset | Mesma ordem? |
|---|---:|---:|---:|:---:|
| `Bm G D A` | 0 | 199 | 199 | sim |
| `C G Am F` | 1 | 296 | 296 | sim |
| `Em G` | 2 | 4 | 4 | sim |
| `C A7 Dm G7` | 3 | 5 | 5 | sim |
| `Gm F` | 4 | 7 | 7 | sim |
| `C C7 F Fm` | 5 | 3 | 3 | sim |

A soma dos resultados atuais é 514 músicas. A ordem é a da coleção passada por
`apply_filtro` (`main.py:266-272`): os grupos de gênero são concatenados na
ordem de `generos_key`, e dentro de cada gênero as músicas estão ordenadas por
popularidade (`main.py:94-96`). O candidato percorre exatamente a mesma coleção,
por isso a ordem também coincide.

O carregamento real tem 67.585 músicas: o arquivo tem 67.586 linhas e
`main.py:49-50` descarta a primeira linha com `f.readline()`. A primeira linha
descartada é um registro de música (o arquivo não tem cabeçalho), mas ela tem
`SEQ_FAMOSA` vazia, então não altera as contagens acima.

Também foram verificadas algumas buscas filtradas por gênero. Exemplos de
contagens atuais com um único gênero: `Rock` retorna 5 para o id 0 e 8 para o id
1; `Sertanejo` retorna 77 para o id 0 e 83 para o id 1; `Samba` retorna 5 para o
id 3. O candidato “contíguo + subset” sobre a mesma coleção filtrada reproduz
esses resultados.

**Custo observado.** Em uma execução local (Python 3.10.12), calcular as 6
sequências com “contíguo + subset” sobre as 67.585 músicas levou cerca de 1,08 s;
o caminho atual por tag levou cerca de 0,26 s para as mesmas 6. A cifra média
tem 51,9 acordes por música. Não há suíte de testes no repositório nem
dependência de teste em `requirements.txt:1-5`; a validação acima foi feita por
script ad hoc.

### 3. Banco de dados

**Estado atual:** não há banco. `requirements.txt:4-5` lista apenas
`Flask==3.1.3` e `gunicorn==23.0.0`. O `main.py` lê o CSV uma vez no import
(`main.py:49-98`) e mantém tudo em memória. Não há `sqlite3`, ORM, migrations,
modelos ou arquivo de banco no repositório.

**Dockerfile e persistência:** `Dockerfile:1-12` usa `python:3.9-slim`, copia o
repositório com `COPY . .`, expõe 8080 e roda
`gunicorn --bind 0.0.0.0:8080 main:app`. Não há `VOLUME`, não há
`docker-compose` e o `CMD` não define `--workers` (o default do gunicorn é 1
worker síncrono). O comando documentado em `README.md:15-17` é
`docker run -p 8080:8080 ciframe`, sem `-v`. O `.dockerignore:1-4` exclui apenas
`.git`, `.venv`, `__pycache__` e `*.pyc`; portanto, se um arquivo de banco
existir no diretório no momento do build, ele entra na imagem via `COPY . .`.

Consequências do ciclo de vida Docker para qualquer banco em arquivo:

- `docker restart`, `docker stop` + `docker start` no **mesmo container**
  preservam a camada gravável, então um arquivo criado em `/app/...` sobrevive.
- `docker rm` seguido de um novo `docker run` cria um container novo a partir
  da imagem; escritas feitas na camada gravável anterior não são reaproveitadas.
- Um bind mount (`-v "$PWD/data:/app/data"`) ou volume nomeado
  (`-v ciframe-data:/app/data`) preserva os arquivos entre containers novos,
  mas exige mudar o comando de execução ou a configuração de deploy.
- `VOLUME /app/data` no `Dockerfile` cria um volume anônimo; o ciclo de vida e a
  reutilização desse volume dependem de como o container é removido/recolocado.
- O ADR `docs/adr/0001-local-only-docker-deploy.md:9-16` fixa o modelo de um
  único `Dockerfile`, execução local e nenhum alvo de nuvem decidido; não há
  serviço externo de banco no repositório.

**Opções embarcadas viáveis no container único:**

| Opção | Dependência | Persistência em arquivo | Observações factuais no contexto atual |
|---|---|---|---|
| SQLite | `sqlite3` da stdlib do CPython 3.9; nenhuma linha nova em `requirements.txt` | Sim, um arquivo | Precisa de caminho gravável e volume para sobreviver a container novo; tem transações/SQL e lock de escrita; o gunicorn atual usa 1 worker por default. |
| TinyDB | Novo pacote Python | Sim, um arquivo JSON | Sem SQL; reescreve o documento; sem as mesmas garantias transacionais do SQLite; mesmo problema de volume. |
| `shelve`/`dbm`/`pickle`/JSON manual | Stdlib | Sim, um ou mais arquivos | Sem linguagem de consulta nem transações robustas; concorrência e corrupção exigem cuidado; mesmo problema de volume; `pickle` tem implicações de segurança na desserialização. |
| SQLite/DuckDB em memória | Stdlib (SQLite) ou novo pacote (DuckDB) | Não | Perde o catálogo quando o processo/container reinicia; não atende ao requisito de persistência do enunciado. |
| DuckDB | Novo pacote Python | Sim, um arquivo | Embarcado e analítico; aumenta dependências/tamanho da imagem; mesmo problema de volume. |
| LMDB | Novo pacote Python | Sim, diretório de arquivos | Embarcado e rápido para chave-valor; mesmo problema de volume e nova dependência. |
| PostgreSQL/MySQL | Serviço externo | Sim, gerenciado pelo serviço | Exige serviço adicional; conflita com o modelo de container único e “sem serviços externos adicionais” do enunciado e do ADR 0001. |

**Natureza do dado a persistir:** o catálogo atual é um `dict` literal com 6
entradas (`main.py:40-45`), sem campos de identificação, autoria, data ou
duplicidade. As chaves são as sequências concatenadas sem separador; os valores
são inteiros 0–5 usados para casar com a coluna `SEQ_FAMOSA`. Não há endpoint de
listagem, criação, edição ou remoção de sequências.

### 4. Frontend existente

**Rota e controller.** A rota `#/porsequencia` está em
`static/assets/js/routes.js:17-21`, com
`templateUrl: "templates/sequencia.html"`, `controller: "SequenciaController"` e
`controllerAs: "Sequencia"`. O script do controller é incluído em
`static/index.html:145`.

**Lista hardcoded.** `static/assets/js/controllers/sequencia.js:2-31` define
`sequencia1` a `sequencia4`; `sequencia.js:33-37` empilha essas 4 em
`vm.sequenciasFamosas`. O conteúdo é:

| Variável JS | Acordes | Corresponde ao id do backend |
|---|---|---:|
| `sequencia1` | `Bm, G, D, A` | 0 |
| `sequencia2` | `C, G, Am, F` | 1 |
| `sequencia3` | `Gm, F` | 4 |
| `sequencia4` | `C, C7, F, Fm` | 5 |

Portanto, as sequências 2 (`Em G`) e 3 (`C A7 Dm G7`) existem no backend mas não
aparecem na página. Os ids 4 e 5 aparecem, mas o nome das variáveis JS não
corresponde ao número do id. As contagens atuais das 4 exibidas são 199, 296, 7
e 3; as duas não exibidas têm 4 e 5 músicas.

**O que o template faz.** `static/templates/sequencia.html:6-8` faz
`ng-repeat` sobre `Sequencia.sequenciasFamosas`, desenha cada acorde com a
diretiva `df-hex` e dispara `Sequencia.pesquisarPorSequencia(sequencia)` no
clique. Não há campo de texto, formulário de cadastro, botão de salvar ou
listagem vinda do backend. O bloco de resultados está em
`sequencia.html:40-59`; os cartões usam `music.nome_musica`, `music.nome_artista`,
`music.genero` e `music.url`.

**Como a busca é montada.** `createChordsString`
(`static/assets/js/controllers/sequencia.js:55-61`) concatena
`chords[i].acorde` com `,` e remove a última vírgula. `pesquisarPorSequencia`
(`sequencia.js:63-90`) usa `apiUrl = ""`, ou seja, URL relativa à mesma origem,
e monta `similares?sequencia=<string>`; se `vm.meuGenero` estiver preenchido,
acrescenta `&generos=<gênero>`. O retorno é tratado como array em
`sequencia.js:77-84`.

**Gêneros.** O dropdown de gênero em `sequencia.html:22-31` usa
`Sequencia.generos`, que recebe a constante `GENEROS` em
`sequencia.js:43`. Essa constante está em `static/assets/js/app.js:6-58` e tem
51 itens hardcoded. Ela não vem de `GET /generos`; o carregamento atual do
backend produz 52 valores de gênero. A constante `RESTAPI` em `app.js:3-5`
(`http://localhost:5003`) não é usada pelo controller de sequência.

**Formato dos resultados.** A busca por sequência retorna dicionários com
`id_unico_musica`, `id_artista`, `id_musica`, `nome_artista`, `nome_musica`,
`popularidade`, `acordes`, `genero` e `url` (`main.py:210-220`). Diferentemente
da busca por acordes/música, esses dicionários não incluem `diferenca` nem
`intersecao`, embora o template use `music.diferenca.length` em
`sequencia.html:43`.

**Não existe no frontend nem no backend:**

- endpoint para listar o catálogo de sequências;
- endpoint para cadastrar sequência (o backend só tem rotas `GET` em
  `main.py:101-201`);
- qualquer estado de carregamento/erro específico para buscar o catálogo;
- qualquer validação de sequência duplicada, vazia ou com acorde inexistente.

## Trade-offs identificados

### Algoritmo de matching

| Regra possível | Prós | Contras / efeito medido |
|---|---|---|
| **Contíguo + subset** (condição que reproduz a tag atual) | Reproduz exatamente as 6 sequências atuais, incluindo ordem; é simples de implementar sobre `musica.cifra`. | É restritiva: a música não pode ter nenhum acorde fora do conjunto da sequência. Contíguo puro daria 866/1.216/3.110/96/1.039/132 em vez de 199/296/4/5/7/3. Para sequências novas, o efeito é difícil de explicar ao usuário. |
| **Contíguo ordenado apenas** | Definição direta de “a sequência aparece como bloco”; preserva ordem e adjacência. | Muda os resultados das 6 originais (ver coluna “Contíguo apenas” acima); se aplicado também às 6, quebra o critério de regressão do enunciado. |
| **Subsequência ordenada com lacunas** | Aceita acordes intermediários entre os acordes da sequência; mantém a ordem. | Resultados muito maiores (4.763/5.887/13.643/427/3.641/280); perde a noção de bloco contíguo e aumenta falsos positivos. |
| **Subconjunto não ordenado** (`set(musica.cifra) ⊇ set(S)`) | Simples e rápido; independe de ordem. | Resultados da ordem de 8.000–9.000 por sequência; não distingue uma sequência de um conjunto de acordes; ignora repetição e ordem. |
| **Normalização exata** (comparar strings como estão) | Preserva a intenção das grafias do CSV e a chave exata atual. | Há 11 tokens de acorde iniciando com minúscula e 151 grupos que colidem no lowercase; uma digitação com caixa diferente não casaria. |
| **Normalização por lowercase** | É a normalização usada na geração histórica da tag; reduz diferenças de caixa. | Conflita grafias semanticamente distintas (`F7M`/`F7m`, `GM7(9)`/`Gm7(9)`, `DM7`/`Dm7`); para as 6 atuais não alterou os conjuntos, mas para sequências novas pode gerar falsos positivos. |
| **Normalização mais agressiva** (remover extensões/baixo, reduzir à fundamental) | Aumentaria a chance de casar variações de escrita. | Não existe no código atual; os 6.653 tokens incluem extensões, slash chords e ruído (por exemplo `add9`, `heF#`, `m`), então a regra precisaria ser definida e validada. |
| **Considerar repetições como multiplicidade** | Distinguiria uma sequência que exige duas ocorrências de uma que exige uma. | A regra atual de substring contígua já exige repetição exata quando ela está na sequência; as alternativas por conjunto ignoram multiplicidade. Um acorde repetido inserido no meio do bloco quebra a contiguidade. |

Custo: qualquer regra em tempo real percorre as músicas e seus acordes. A
medição local das 6 sequências com “contíguo + subset” foi ~1,08 s contra
~0,26 s do caminho por tag; a busca atual já percorre a coleção filtrada, mas
não examina a lista de acordes.

### Banco de dados e persistência

| Decisão | Opção | Prós | Contras |
|---|---|---|---|
| Tecnologia | SQLite (stdlib) | Sem dependência nova; SQL; transações; um arquivo. | Exige volume para sobreviver a container novo; lock de escrita; schema/migrations; concorrência limitada se houver mais de um worker. |
| Tecnologia | TinyDB | Simples, JSON, sem SQL. | Dependência nova; reescrita do arquivo; sem transações ACID; mesmo problema de volume. |
| Tecnologia | `shelve`/`dbm`/`pickle`/JSON manual | Stdlib; implementação mínima. | Sem consulta/transação robusta; concorrência e corrupção; `pickle` exige confiança no arquivo; mesmo problema de volume. |
| Tecnologia | DuckDB/LMDB | Embarcados, mais recursos/desempenho. | Dependência nova e impacto no build/tamanho da imagem; mesmo problema de volume. |
| Tecnologia | SQLite em memória | Não exige arquivo/volume. | Perde o catálogo a cada reinício do processo/container; não atende à persistência exigida. |
| Tecnologia | PostgreSQL/MySQL | Concorrência e durabilidade gerenciadas pelo serviço. | Serviço adicional; conflita com o modelo de container único e “sem serviços externos adicionais”. |
| Persistência | Sem volume (situação do `docker run` documentado) | Nenhuma mudança no comando atual. | Sobrevive a restart do mesmo container, mas não a `docker rm`/novo `docker run`. |
| Persistência | Bind mount ou volume nomeado | Sobrevive à recriação do container. | Exige alterar o comando de execução/deploy e definir caminho/ownership. |
| Persistência | `VOLUME` no Dockerfile | Cria um volume gerenciado pelo Docker. | Volume anônimo; reutilização/lifecycle dependem de como o container é removido/recolocado. |
| Build | `COPY . .` atual | Simples. | Pode copiar um banco local para dentro da imagem, pois `.dockerignore` não exclui arquivos de banco. |

### API, validação e frontend

| Decisão | Opção | Prós | Contras / fato relacionado |
|---|---|---|---|
| Formato da busca | Reutilizar `GET /similares?sequencia=` com a string de acordes separada por vírgula | Mantém o contrato e o frontend atuais. | O servidor remove as vírgulas e usa a concatenação como chave; tokenizações diferentes podem gerar a mesma string (por exemplo `C,A7,...` versus `CA7,...`) e não há separador após a remoção. |
| Formato da busca | Buscar por id de sequência do catálogo | Evita ambiguidade da concatenação e separa catálogo de busca. | Muda o contrato atual (`?sequencia=<acordes>`) e exige que o frontend obtenha o id. |
| Cadastro | Endpoint novo de criação | Permite catálogo aberto e anônimo. | Hoje todas as rotas são `GET` (`main.py:101-201`) e não há autenticação nem validação. |
| Duplicidade | Rejeitar duplicata | Evita catálogo repetido. | Não há regra hoje; a chave do `dict` atual é única por construção, mas não há endpoint de criação. |
| Duplicidade | Retornar a sequência existente | Mantém o catálogo enxuto. | Exige definir o que é “igual” (ordem, caixa, normalização). |
| Duplicidade | Permitir duplicatas | Implementação mais simples. | Pode gerar entradas indistinguíveis no catálogo. |
| Frontend | Manter a lista hardcoded | Nenhuma mudança no controller/template. | Não reflete o catálogo real, que o enunciado manda vir do backend. |
| Frontend | Buscar o catálogo do backend e renderizar com `ng-repeat` | Uma única fonte de verdade; o template já usa `ng-repeat` sobre `Sequencia.sequenciasFamosas`. | Exige endpoint de listagem e estados de carregamento/erro; hoje não existe nenhum dos dois. |
| Frontend | Cadastro por texto livre | Flexível para qualquer acorde. | Exige parsing/validação; `/acordes` existe (`main.py:162-164`) e devolve 6.653 tokens crus, incluindo ruído, então uma lista pronta não está curada. |
| Frontend | Cadastro por seletor de acordes | Evita acordes inválidos. | Exige montar UI de seleção; a página atual só tem os `df-hex` hardcoded e o dropdown de gênero. |
| Frontend | Formato do resultado | Reutilizar o dicionário de `get_similares_por_sequencia` (`main.py:210-220`). | O template acessa `music.diferenca.length` (`sequencia.html:43`), campo que esse caminho não devolve. |
| Stack | Manter AngularJS 1.4.9 sem build | Compatível com o restante do frontend. | Qualquer controller/arquivo novo precisa ser incluído manualmente em `static/index.html`; o ADR `docs/adr/0003-lift-frontend-freeze.md` removeu a proibição de tocar no frontend, mas não decidiu modernização. |
