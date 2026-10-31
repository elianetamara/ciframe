import os
import tempfile
import unittest

from musica import Musica
from sequencias import (
    MAX_ACORDES,
    MAX_CARACTERES_ACORDE,
    RepositorioSequencias,
    SequenciaDuplicada,
    SequenciaInvalida,
    normalizar_acordes,
    sequencia_compativel,
)


def criar_musica(cifra):
    return Musica(
        'artista-id',
        'Artista',
        'musica-id',
        'Musica',
        'Rock',
        1,
        [],
        'C',
        cifra,
    )


class NormalizacaoTest(unittest.TestCase):
    def test_normaliza_primeira_letra_e_preserva_sufixo(self):
        self.assertEqual(
            normalizar_acordes([' am ', 'c', 'F7M', 'f7m']),
            ['Am', 'C', 'F7M', 'F7m'],
        )

    def test_rejeita_lista_vazia_ou_invalida(self):
        with self.assertRaises(SequenciaInvalida):
            normalizar_acordes([])
        with self.assertRaises(SequenciaInvalida):
            normalizar_acordes('C,G')
        with self.assertRaises(SequenciaInvalida):
            normalizar_acordes([''])

    def test_rejeita_limites(self):
        with self.assertRaises(SequenciaInvalida):
            normalizar_acordes(['C'] * (MAX_ACORDES + 1))
        with self.assertRaises(SequenciaInvalida):
            normalizar_acordes(['C' * (MAX_CARACTERES_ACORDE + 1)])


class MatchingTest(unittest.TestCase):
    def test_aceita_bloco_contiguo_com_subconjunto(self):
        musica = criar_musica(['Bm', 'G', 'D', 'A'])
        self.assertTrue(sequencia_compativel(musica, ['Bm', 'G', 'D', 'A']))
        self.assertFalse(sequencia_compativel(musica, ['Bm', 'G', 'D', 'A', 'C']))

    def test_rejeita_ordem_diferente_ou_acorde_extra(self):
        musica = criar_musica(['Bm', 'G', 'D', 'A'])
        self.assertFalse(sequencia_compativel(musica, ['G', 'Bm']))
        self.assertFalse(sequencia_compativel(musica, ['Bm', 'D']))
        self.assertFalse(sequencia_compativel(musica, ['Bm', 'G', 'D']))
        self.assertFalse(sequencia_compativel(musica, ['Bm', 'G', 'X', 'D', 'A']))

    def test_rejeita_cifra_vazia(self):
        self.assertFalse(sequencia_compativel(criar_musica([]), ['C']))

    def test_aceita_repeticao(self):
        musica = criar_musica(['C', 'G', 'C', 'G'])
        self.assertTrue(sequencia_compativel(musica, ['C', 'G', 'C', 'G']))
        self.assertTrue(sequencia_compativel(musica, ['C', 'G']))


class RepositorioTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'sequences.db')
        self.repo = RepositorioSequencias(self.path)
        self.assertEqual(self.repo.inicializar(), 6)

    def tearDown(self):
        self.tmp.cleanup()

    def test_seed_e_listagem(self):
        lista = self.repo.listar()
        self.assertEqual([item['id'] for item in lista], [0, 1, 2, 3, 4, 5])
        self.assertEqual(lista[0]['acordes'], ['Bm', 'G', 'D', 'A'])
        self.assertEqual(lista[0]['origem'], 'seed')

    def test_seed_idempotente(self):
        self.assertEqual(self.repo.inicializar(), 6)
        self.assertEqual(len(self.repo.listar()), 6)

    def test_cria_e_busca_por_id_e_chave(self):
        criada = self.repo.criar(['d', 'a', 'bm', 'g'])
        self.assertGreaterEqual(criada['id'], 6)
        self.assertEqual(criada['acordes'], ['D', 'A', 'Bm', 'G'])
        self.assertEqual(criada['origem'], 'custom')
        self.assertEqual(self.repo.por_id(criada['id']), ['D', 'A', 'Bm', 'G'])
        self.assertEqual(self.repo.por_chave('D;A;Bm;G'), ['D', 'A', 'Bm', 'G'])

    def test_busca_legacy(self):
        self.assertEqual(self.repo.por_legacy_key('BmGDA'), ['Bm', 'G', 'D', 'A'])
        self.assertEqual(self.repo.por_id(0), ['Bm', 'G', 'D', 'A'])

    def test_rejeita_duplicata_do_seed(self):
        with self.assertRaises(SequenciaDuplicada) as contexto:
            self.repo.criar(['C', 'G', 'Am', 'F'])
        self.assertEqual(contexto.exception.sequencia['id'], 1)

    def test_persiste_apos_reabrir(self):
        criada = self.repo.criar(['Bm', 'G', 'D', 'A', 'C'])
        outro = RepositorioSequencias(self.path)
        self.assertEqual(outro.inicializar(), 6)
        self.assertEqual(outro.por_id(criada['id']), ['Bm', 'G', 'D', 'A', 'C'])


if __name__ == '__main__':
    unittest.main()
