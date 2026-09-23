"""Funções utilitárias compartilhadas pelos módulos."""

from __future__ import annotations

import fnmatch
import os
import sys
import unicodedata
from collections.abc import Iterable
from pathlib import Path


def pasta_dados() -> Path:
    """Pasta onde o FileSense guarda histórico e configuração (padrão: ~/.filesense)."""
    return Path(os.environ.get("FILESENSE_HOME", Path.home() / ".filesense"))


def pasta_downloads() -> Path:
    return Path.home() / "Downloads"


def tamanho_legivel(n: float) -> str:
    """Converte bytes em texto legível: 1536 -> '1.5 KB'."""
    unidades = ("B", "KB", "MB", "GB", "TB")
    for i, unidade in enumerate(unidades):
        if abs(n) < 1024 or i == len(unidades) - 1:
            return f"{int(n)} {unidade}" if i == 0 else f"{n:.1f} {unidade}"
        n /= 1024
    raise AssertionError("inalcançável")


def corresponde(nome: str, padroes: Iterable[str]) -> bool:
    """Verifica se o nome bate com algum padrão glob (sem diferenciar maiúsculas)."""
    nome = nome.lower()
    return any(fnmatch.fnmatchcase(nome, p.lower()) for p in padroes)


def sem_acento(texto: str) -> str:
    """Chave de ordenação que ignora acentos e maiúsculas: 'Áudios' fica junto do 'A'."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def destino_livre(destino: Path, reservados: set[Path] | None = None) -> Path:
    """Retorna um caminho que não existe, no estilo 'arquivo (1).pdf', 'arquivo (2).pdf'."""
    reservados = reservados if reservados is not None else set()
    candidato, n = destino, 1
    while candidato.exists() or candidato in reservados:
        candidato = destino.with_name(f"{destino.stem} ({n}){destino.suffix}")
        n += 1
    return candidato


# ---------------------------------------------------------------- cores no terminal

_usar_cor: bool | None = None


def _suporta_cor() -> bool:
    if os.environ.get("NO_COLOR") or not getattr(sys.stdout, "isatty", lambda: False)():
        return False
    if os.name == "nt":
        os.system("")  # habilita sequências ANSI no console do Windows
    return True


def _pintar(texto: str, codigo: str) -> str:
    global _usar_cor
    if _usar_cor is None:
        _usar_cor = _suporta_cor()
    return f"\033[{codigo}m{texto}\033[0m" if _usar_cor else texto


def negrito(t: str) -> str:
    return _pintar(t, "1")


def verde(t: str) -> str:
    return _pintar(t, "32")


def amarelo(t: str) -> str:
    return _pintar(t, "33")


def vermelho(t: str) -> str:
    return _pintar(t, "31")


def ciano(t: str) -> str:
    return _pintar(t, "36")


def cinza(t: str) -> str:
    return _pintar(t, "90")
