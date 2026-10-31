import json
import os
import sqlite3
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Tuple

from musica import Musica

MAX_ACORDES = 32
MAX_CARACTERES_ACORDE = 32

SEQUENCIAS_ORIGINAIS = (
    {"id": 0, "acordes": ["Bm", "G", "D", "A"], "legacy_key": "BmGDA"},
    {"id": 1, "acordes": ["C", "G", "Am", "F"], "legacy_key": "CGAmF"},
    {"id": 2, "acordes": ["Em", "G"], "legacy_key": "EmG"},
    {"id": 3, "acordes": ["C", "A7", "Dm", "G7"], "legacy_key": "CA7DmG7"},
    {"id": 4, "acordes": ["Gm", "F"], "legacy_key": "GmF"},
    {"id": 5, "acordes": ["C", "C7", "F", "Fm"], "legacy_key": "CC7FFm"},
)

CAMINHO_PADRAO_DB = os.environ.get(
    "SEQUENCES_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "sequences.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS sequencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    acordes TEXT NOT NULL,
    chave TEXT NOT NULL UNIQUE,
    legacy_key TEXT UNIQUE,
    origem TEXT NOT NULL CHECK (origem IN ('seed', 'custom')),
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


class SequenciaInvalida(ValueError):
    pass


class SequenciaDuplicada(Exception):
    def __init__(self, sequencia: Dict[str, Any]) -> None:
        super().__init__("Sequencia ja cadastrada")
        self.sequencia = sequencia


def normalizar_acorde(acorde: str) -> str:
    if not isinstance(acorde, str):
        raise SequenciaInvalida("Cada acorde deve ser uma string")

    acorde = acorde.strip()
    if not acorde:
        raise SequenciaInvalida("Acorde vazio")
    if len(acorde) > MAX_CARACTERES_ACORDE:
        raise SequenciaInvalida(
            "Acorde com mais de %d caracteres" % MAX_CARACTERES_ACORDE
        )

    if acorde[0] != acorde[0].upper():
        return acorde[0].upper() + acorde[1:]
    return acorde


def normalizar_acordes(acordes: List[str]) -> List[str]:
    if not isinstance(acordes, list):
        raise SequenciaInvalida("acordes deve ser uma lista")
    if not acordes:
        raise SequenciaInvalida("A sequencia deve ter ao menos um acorde")
    if len(acordes) > MAX_ACORDES:
        raise SequenciaInvalida(
            "A sequencia deve ter no maximo %d acordes" % MAX_ACORDES
        )

    return [normalizar_acorde(acorde) for acorde in acordes]


def chave_canonica(acordes: List[str]) -> str:
    return ";".join(acordes)


def preparar_sequencia(
    acordes: List[str],
) -> Tuple[Tuple[str, ...], FrozenSet[str]]:
    normalizados = normalizar_acordes(acordes)
    return tuple(normalizados), frozenset(normalizados)


_CIFRAS_NORMALIZADAS: Dict[Musica, Tuple[Tuple[str, ...], FrozenSet[str]]] = {}


def _cifra_normalizada(
    musica: Musica,
) -> Tuple[Tuple[str, ...], FrozenSet[str]]:
    cifra = _CIFRAS_NORMALIZADAS.get(musica)
    if cifra is None:
        tokens = tuple(normalizar_acorde(acorde) for acorde in musica.cifra)
        cifra = (tokens, frozenset(tokens))
        _CIFRAS_NORMALIZADAS[musica] = cifra
    return cifra


def preparar_cache_normalizacao(musicas: Iterable[Musica]) -> None:
    for musica in musicas:
        _cifra_normalizada(musica)


def sequencia_compativel(
    musica: Musica,
    acordes: Tuple[str, ...],
    acordes_set: Optional[FrozenSet[str]] = None,
) -> bool:
    if acordes_set is None:
        acordes, acordes_set = preparar_sequencia(list(acordes))
    else:
        acordes = tuple(acordes)

    cifra, cifra_set = _cifra_normalizada(musica)
    if not acordes or len(cifra) < len(acordes):
        return False
    if not cifra_set.issubset(acordes_set):
        return False

    tamanho = len(acordes)
    for inicio in range(len(cifra) - tamanho + 1):
        if cifra[inicio:inicio + tamanho] == acordes:
            return True
    return False


class RepositorioSequencias:
    def __init__(self, path: str = CAMINHO_PADRAO_DB) -> None:
        self.path = path

    def _conectar(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)

    @staticmethod
    def _linha_para_dict(linha: Tuple[Any, ...]) -> Dict[str, Any]:
        return {
            "id": linha[0],
            "acordes": json.loads(linha[1]),
            "origem": linha[2],
        }

    def inicializar(self) -> int:
        diretorio = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(diretorio, exist_ok=True)

        with self._conectar() as conn:
            conn.execute(SCHEMA)
            for sequencia in SEQUENCIAS_ORIGINAIS:
                acordes = list(sequencia["acordes"])
                conn.execute(
                    """
                    INSERT OR IGNORE INTO sequencias
                        (id, acordes, chave, legacy_key, origem)
                    VALUES (?, ?, ?, ?, 'seed')
                    """,
                    (
                        sequencia["id"],
                        json.dumps(acordes, ensure_ascii=False),
                        chave_canonica(acordes),
                        sequencia["legacy_key"],
                    ),
                )
            total = conn.execute(
                "SELECT COUNT(*) FROM sequencias WHERE origem = 'seed'"
            ).fetchone()[0]

        return total

    def listar(self) -> List[Dict[str, Any]]:
        with self._conectar() as conn:
            linhas = conn.execute(
                "SELECT id, acordes, origem FROM sequencias ORDER BY id"
            ).fetchall()

        return [self._linha_para_dict(linha) for linha in linhas]

    def criar(self, acordes: List[str]) -> Dict[str, Any]:
        normalizados = normalizar_acordes(acordes)
        chave = chave_canonica(normalizados)

        with self._conectar() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO sequencias (acordes, chave, origem)
                    VALUES (?, ?, 'custom')
                    """,
                    (json.dumps(normalizados, ensure_ascii=False), chave),
                )
            except sqlite3.IntegrityError:
                linha = conn.execute(
                    "SELECT id, acordes, origem FROM sequencias WHERE chave = ?",
                    (chave,),
                ).fetchone()
                existente = (
                    self._linha_para_dict(linha)
                    if linha
                    else {"id": None, "acordes": normalizados, "origem": "custom"}
                )
                raise SequenciaDuplicada(existente)

            return {
                "id": cursor.lastrowid,
                "acordes": normalizados,
                "origem": "custom",
            }

    def por_id(self, seq_id: int) -> Optional[List[str]]:
        with self._conectar() as conn:
            linha = conn.execute(
                "SELECT acordes FROM sequencias WHERE id = ?",
                (seq_id,),
            ).fetchone()

        return json.loads(linha[0]) if linha else None

    def por_chave(self, chave: str) -> Optional[List[str]]:
        with self._conectar() as conn:
            linha = conn.execute(
                "SELECT acordes FROM sequencias WHERE chave = ?",
                (chave,),
            ).fetchone()

        return json.loads(linha[0]) if linha else None

    def por_legacy_key(self, legacy_key: str) -> Optional[List[str]]:
        with self._conectar() as conn:
            linha = conn.execute(
                "SELECT acordes FROM sequencias WHERE legacy_key = ?",
                (legacy_key,),
            ).fetchone()

        return json.loads(linha[0]) if linha else None
