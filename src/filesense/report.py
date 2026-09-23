"""Gera um raio-x da pasta: o que ocupa espaço, o que está esquecido e o que é suspeito."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .organizer import classificador_para
from .utils import corresponde


@dataclass
class Relatorio:
    total_arquivos: int = 0
    total_bytes: int = 0
    por_categoria: dict[str, list[int]] = field(default_factory=lambda: defaultdict(lambda: [0, 0]))
    maiores: list[tuple[Path, int]] = field(default_factory=list)
    # (caminho, bytes, dias sem modificação)
    esquecidos: list[tuple[Path, int, int]] = field(default_factory=list)
    # (caminho, alerta, é perigoso?)
    suspeitos: list[tuple[Path, str, bool]] = field(default_factory=list)


def gerar_relatorio(pasta: Path, cfg: Config, dias_esquecido: int = 180, top: int = 10,
                    agora: float | None = None) -> Relatorio:
    pasta = Path(pasta).expanduser().resolve()
    if not pasta.is_dir():
        raise FileNotFoundError(f"pasta não encontrada: {pasta}")

    agora = time.time() if agora is None else agora
    classificador = classificador_para(cfg)
    r = Relatorio()
    todos: list[tuple[Path, int]] = []

    for raiz, subpastas, arquivos in os.walk(pasta):
        subpastas[:] = [s for s in subpastas if not s.startswith(".")]
        for nome in arquivos:
            if corresponde(nome, cfg.ignorar):
                continue
            caminho = Path(raiz) / nome
            try:
                if caminho.is_symlink():
                    continue
                info = caminho.stat()
            except OSError:
                continue

            c = classificador.classificar(caminho)
            r.total_arquivos += 1
            r.total_bytes += info.st_size
            r.por_categoria[c.categoria][0] += 1
            r.por_categoria[c.categoria][1] += info.st_size
            todos.append((caminho, info.st_size))

            dias = int((agora - info.st_mtime) // 86400)
            if dias >= dias_esquecido:
                r.esquecidos.append((caminho, info.st_size, dias))
            if c.alerta:
                r.suspeitos.append((caminho, c.alerta, c.perigoso))

    r.maiores = sorted(todos, key=lambda t: t[1], reverse=True)[:top]
    r.esquecidos.sort(key=lambda t: t[1], reverse=True)
    r.suspeitos.sort(key=lambda t: not t[2])  # perigosos primeiro
    return r
