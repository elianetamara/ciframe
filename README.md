# deciframe

Descubra as músicas que você já sabe tocar (e ainda não faz ideia). Busque por
título/artista, gênero, pelos acordes que você já manja, ou por sequências de
acordes famosas — o deciframe cruza isso com uma base de cifras e sugere
músicas parecidas.

Stack: backend Flask (Python) servindo uma API JSON + um frontend AngularJS
estático. As músicas vêm de um CSV carregado em memória; o catálogo de
sequências fica em SQLite (`instance/sequences.db`).

## Rodando localmente

### Com Docker

```
docker build -t ciframe .
docker run -p 8080:8080 -v ciframe-sequences:/app/instance ciframe
```

Acesse [http://localhost:8080](http://localhost:8080). O volume nomeado
`ciframe-sequences` mantém o catálogo de sequências entre execuções do container.

### Com virtualenv

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Acesse [http://localhost:5000](http://localhost:5000).

---

Para convenções de contribuição, veja [CONTRIB.md](CONTRIB.md). Licença: [LICENSE](LICENSE).
