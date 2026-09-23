"""Encontra arquivos duplicados pelo conteúdo, não pelo nome.

Comparar hash de todos os arquivos seria lento. Por isso a busca é feita em 3 etapas,
cada uma descartando candidatos com um custo cada vez maior:

1. Tamanho: arquivos de tamanhos diferentes nunca são iguais (custo quase zero).
2. Hash dos primeiros 64 KB: elimina a maioria dos falsos candidatos.
3. Hash completo: confirma que o conteúdo é idêntico.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .history import Historico
from .utils import corresponde, destino_livre

_BLOCO_PARCIAL = 64 * 1024


def _hash(arquivo: Path, limite: int | None = None) -> str:
    h = hashlib.blake2b(digest_size=20)
    with arquivo.open("rb") as f:
        if limite is not None:
            h.update(f.read(limite))
        else:
            for bloco in iter(lambda: f.read(1 << 20), b""):
                h.update(bloco)
    return h.hexdigest()


def _hash_parcial(arquivo: Path) -> str:
    return _hash(arquivo, _BLOCO_PARCIAL)


@dataclass
class GrupoDuplicado:
    arquivos: list[Path]  # o primeiro é o que será mantido
    tamanho: int

    @property
    def original(self) -> Path:
        return self.arquivos[0]

    @property
    def copias(self) -> list[Path]:
        return self.arquivos[1:]

    @property
    def desperdicio(self) -> int:
        return self.tamanho * len(self.copias)


def _agrupar(arquivos: list[Path], chave: Callable[[Path], str]) -> list[list[Path]]:
    grupos: dict[str, list[Path]] = defaultdict(list)
    for arquivo in arquivos:
        try:
            grupos[chave(arquivo)].append(arquivo)
        except OSError:
            continue
    return [g for g in grupos.values() if len(g) > 1]


def _ordem_original(arquivo: Path) -> tuple[float, int, str]:
    """O original é o mais antigo; no empate, o de nome mais curto.

    Assim 'foto.jpg' é mantido e 'foto (1).jpg' é tratado como cópia.
    """
    return (arquivo.stat().st_mtime, len(arquivo.name), arquivo.name)


def encontrar_duplicados(pasta: Path, cfg: Config) -> list[GrupoDuplicado]:
    pasta = Path(pasta).expanduser().resolve()
    if not pasta.is_dir():
        raise FileNotFoundError(f"pasta não encontrada: {pasta}")

    por_tamanho: dict[int, list[Path]] = defaultdict(list)
    for raiz, subpastas, arquivos in os.walk(pasta):
        subpastas[:] = [s for s in subpastas
                        if not s.startswith(".") and s != cfg.pasta_duplicados]
        for nome in arquivos:
            if corresponde(nome, cfg.ignorar):
                continue
            caminho = Path(raiz) / nome
            try:
                if caminho.is_symlink():
                    continue
                tamanho = caminho.stat().st_size
            except OSError:
                continue
            if tamanho > 0:
                por_tamanho[tamanho].append(caminho)

    grupos: list[GrupoDuplicado] = []
    for tamanho, candidatos in por_tamanho.items():
        if len(candidatos) < 2:
            continue
        for parcial in _agrupar(candidatos, _hash_parcial):
            # arquivo pequeno: o hash parcial já cobriu o conteúdo inteiro
            confirmados = [parcial] if tamanho <= _BLOCO_PARCIAL else _agrupar(parcial, _hash)
            for grupo in confirmados:
                grupos.append(GrupoDuplicado(sorted(grupo, key=_ordem_original), tamanho))

    grupos.sort(key=lambda g: g.desperdicio, reverse=True)
    return grupos


def mover_copias(grupos: list[GrupoDuplicado], pasta: Path, cfg: Config,
                 historico: Historico | None = None
                 ) -> tuple[list[tuple[Path, Path]], list[tuple[Path, str]]]:
    """Move as cópias para a pasta de duplicados, mantendo a estrutura. Nunca apaga nada."""
    pasta = Path(pasta).expanduser().resolve()
    base = pasta / cfg.pasta_duplicados
    movidos: list[tuple[Path, Path]] = []
    erros: list[tuple[Path, str]] = []
    reservados: set[Path] = set()

    for grupo in grupos:
        for copia in grupo.copias:
            try:
                relativo = copia.relative_to(pasta)
            except ValueError:
                relativo = Path(copia.name)
            destino = destino_livre(base / relativo, reservados)
            reservados.add(destino)
            try:
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(copia), str(destino))
                movidos.append((copia, destino))
            except OSError as e:
                erros.append((copia, e.strerror or str(e)))

    if historico and movidos:
        historico.registrar(pasta, movidos, acao="duplicados")
    return movidos, erros
