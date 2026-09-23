"""Modo vigia: organiza a pasta continuamente, conforme arquivos novos chegam.

Usa polling (verificação periódica) em vez de eventos do sistema operacional.
Assim funciona igual em Windows, macOS e Linux sem nenhuma dependência externa,
e combina bem com a regra de idade mínima, que espera o download terminar.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from .config import Config
from .history import Historico
from .organizer import Movimento, executar, planejar

AoMover = Callable[[list[Movimento], list[tuple[Movimento, str]]], None]


def vigiar(pasta: Path, cfg: Config, historico: Historico | None = None,
           intervalo: float = 10.0, ao_mover: AoMover | None = None,
           parar: Callable[[], bool] | None = None) -> None:
    while True:
        movimentos = planejar(pasta, cfg)
        if movimentos:
            feitos, erros = executar(movimentos, pasta, historico)
            if ao_mover:
                ao_mover(feitos, erros)
        if parar and parar():
            return
        time.sleep(intervalo)
