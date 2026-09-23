"""Planeja e executa a organização de uma pasta."""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .classifier import Classificador
from .config import Config
from .history import Historico
from .utils import corresponde, destino_livre, sem_acento


@dataclass
class Movimento:
    origem: Path
    destino: Path
    categoria: str
    alerta: str | None = None
    perigoso: bool = False


def classificador_para(cfg: Config) -> Classificador:
    return Classificador(cfg.categorias, cfg.pasta_outros, cfg.pasta_suspeitos)


def planejar(pasta: Path, cfg: Config, agora: float | None = None) -> list[Movimento]:
    """Decide para onde cada arquivo vai, sem mover nada.

    Separar 'planejar' de 'executar' é o que permite o modo --simular
    e torna a lógica fácil de testar.
    """
    pasta = Path(pasta).expanduser().resolve()
    if not pasta.is_dir():
        raise FileNotFoundError(f"pasta não encontrada: {pasta}")

    classificador = classificador_para(cfg)
    agora = time.time() if agora is None else agora
    reservados: set[Path] = set()
    movimentos: list[Movimento] = []

    for arquivo in sorted(pasta.iterdir(), key=lambda p: sem_acento(p.name)):
        if arquivo.is_symlink() or not arquivo.is_file():
            continue
        if corresponde(arquivo.name, cfg.ignorar):
            continue
        try:
            modificado = arquivo.stat().st_mtime
        except OSError:
            continue
        if agora - modificado < cfg.idade_minima_segundos:
            continue  # provavelmente ainda está sendo baixado ou salvo

        c = classificador.classificar(arquivo)
        pasta_destino = pasta / c.categoria
        if cfg.por_data and not c.alerta:
            pasta_destino /= datetime.fromtimestamp(modificado).strftime("%Y-%m")

        destino = destino_livre(pasta_destino / arquivo.name, reservados)
        reservados.add(destino)
        movimentos.append(Movimento(arquivo, destino, c.categoria, c.alerta, c.perigoso))

    return movimentos


def executar(movimentos: list[Movimento], pasta: Path, historico: Historico | None = None
             ) -> tuple[list[Movimento], list[tuple[Movimento, str]]]:
    """Move os arquivos. Retorna (movidos, erros). Um erro não interrompe os demais."""
    feitos: list[Movimento] = []
    erros: list[tuple[Movimento, str]] = []

    for m in movimentos:
        try:
            m.destino.parent.mkdir(parents=True, exist_ok=True)
            if m.destino.exists():  # algo apareceu entre o plano e a execução
                m.destino = destino_livre(m.destino)
            shutil.move(str(m.origem), str(m.destino))
            feitos.append(m)
        except OSError as e:  # ex.: arquivo aberto em outro programa
            erros.append((m, e.strerror or str(e)))

    if historico and feitos:
        historico.registrar(Path(pasta).expanduser().resolve(),
                            [(m.origem, m.destino) for m in feitos])
    return feitos, erros
