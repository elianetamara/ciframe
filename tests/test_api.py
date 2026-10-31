import json
import os
import sqlite3
import tempfile
import unittest

_TMPDIR = tempfile.TemporaryDirectory()
os.environ['SEQUENCES_DB'] = os.path.join(_TMPDIR.name, 'sequences.db')

import main


CAMINHO_FIXTURE = os.path.join(
    os.path.dirname(__file__),
    'fixtures',
    'regressao_6.json',
)


class SequenciasApiTest(unittest.TestCase):
    def setUp(self):
        with sqlite3.connect(main.repositorio_sequencias.path) as conn:
            conn.execute("DELETE FROM sequencias WHERE origem = 'custom'")
        self.client = main.app.test_client()

    def _ids_legado(self, id_seq, generos_key):
        colecao = main.apply_filtro(main.musicas.values(), generos_key)
        return [
            musica.id_unico_musica
            for musica in colecao
            if str(id_seq) in musica.seqs_famosas
        ]

    def test_catalogo_inicial(self):
        resposta = self.client.get('/sequencias')
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.content_type.startswith('text/html'))
        dados = json.loads(resposta.get_data(as_text=True))
        self.assertEqual([item['id'] for item in dados], [0, 1, 2, 3, 4, 5])
        self.assertEqual(dados[0]['acordes'], ['Bm', 'G', 'D', 'A'])

    def test_cria_sequencia_e_busca_por_id(self):
        resposta = self.client.post(
            '/sequencias',
            json={'acordes': ['bm', 'e']},
        )
        self.assertEqual(resposta.status_code, 201)
        criada = json.loads(resposta.get_data(as_text=True))
        self.assertGreaterEqual(criada['id'], 6)
        self.assertEqual(criada['acordes'], ['Bm', 'E'])

        busca = self.client.get('/similares?sequencia_id=%d' % criada['id'])
        self.assertEqual(busca.status_code, 200)
        ids = [
            musica['id_unico_musica']
            for musica in json.loads(busca.get_data(as_text=True))
        ]
        self.assertIn('the-strokes_reptilia', ids)

    def test_duplicata_do_seed(self):
        resposta = self.client.post(
            '/sequencias',
            json={'acordes': ['Bm', 'G', 'D', 'A']},
        )
        self.assertEqual(resposta.status_code, 409)
        dados = json.loads(resposta.get_data(as_text=True))
        self.assertEqual(dados['erro'], 'sequencia_duplicada')
        self.assertEqual(dados['id'], 0)

    def test_duplicata_customizada(self):
        corpo = {'acordes': ['Bm', 'G', 'D', 'A', 'C']}
        self.assertEqual(self.client.post('/sequencias', json=corpo).status_code, 201)
        resposta = self.client.post('/sequencias', json=corpo)
        self.assertEqual(resposta.status_code, 409)

    def test_entradas_invalidas(self):
        corpos = [
            {},
            {'acordes': []},
            {'acordes': 'C,G'},
            {'acordes': ['C'] * 33},
            {'acordes': ['C' * 33]},
        ]
        for corpo in corpos:
            resposta = self.client.post('/sequencias', json=corpo)
            self.assertEqual(resposta.status_code, 400, corpo)

        resposta = self.client.post(
            '/sequencias',
            data='nao e json',
            content_type='text/plain',
        )
        self.assertEqual(resposta.status_code, 400)

    def test_busca_legada(self):
        resposta = self.client.get('/similares?sequencia=Bm,G,D,A')
        self.assertEqual(resposta.status_code, 200)
        ids = [
            musica['id_unico_musica']
            for musica in json.loads(resposta.get_data(as_text=True))
        ]
        self.assertEqual(ids, self._ids_legado(0, main.generos)[:100])

    def test_busca_por_id_inexistente(self):
        resposta = self.client.get('/similares?sequencia_id=9999')
        self.assertEqual(json.loads(resposta.get_data(as_text=True)), [])

    def test_filtro_por_genero(self):
        resposta = self.client.get('/similares?sequencia_id=0&generos=Rock')
        dados = json.loads(resposta.get_data(as_text=True))
        self.assertEqual(len(dados), 5)

    def test_endpoints_de_musicas_continuam_serializaveis_apos_busca(self):
        self.assertEqual(self.client.get('/similares?sequencia_id=0').status_code, 200)
        self.assertEqual(self.client.get('/musicas').status_code, 200)
        self.assertEqual(
            self.client.get('/musica/the-strokes_reptilia/').status_code,
            200,
        )

    def test_paginacao(self):
        pagina_1 = json.loads(
            self.client.get('/similares?sequencia_id=0').get_data(as_text=True)
        )
        pagina_2 = json.loads(
            self.client.get('/similares?sequencia_id=0&pagina=2').get_data(as_text=True)
        )
        self.assertEqual(len(pagina_1), 100)
        self.assertEqual(len(pagina_2), 99)
        ids_1 = {item['id_unico_musica'] for item in pagina_1}
        ids_2 = {item['id_unico_musica'] for item in pagina_2}
        self.assertFalse(ids_1.intersection(ids_2))

    def test_regressao_das_seis(self):
        with open(CAMINHO_FIXTURE, encoding='utf-8') as arquivo:
            fixture = json.load(arquivo)

        casos = [
            ('todos', main.generos),
            ('Rock', ['Rock']),
            ('Samba', ['Samba']),
        ]

        for nome, generos_key in casos:
            for id_seq in range(6):
                acordes = main.repositorio_sequencias.por_id(id_seq)
                atual = [
                    musica['id_unico_musica']
                    for musica in main.get_similares_por_sequencia(
                        acordes, generos_key
                    )
                ]
                esperado = self._ids_legado(id_seq, generos_key)
                self.assertEqual(atual, esperado, (nome, id_seq))

                if nome == 'todos':
                    self.assertEqual(
                        len(atual),
                        fixture['sequencias'][str(id_seq)]['total'],
                    )
                    self.assertEqual(
                        sorted(atual),
                        sorted(fixture['todos'][str(id_seq)]),
                    )
                else:
                    self.assertEqual(
                        sorted(atual),
                        sorted(fixture['generos'][nome][str(id_seq)]),
                    )


def tearDownModule():
    _TMPDIR.cleanup()


if __name__ == '__main__':
    unittest.main()
