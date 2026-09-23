"""Configuração padrão e personalizações do usuário via arquivo TOML."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .classifier import CATEGORIAS_PADRAO
from .utils import pasta_dados

IGNORAR_PADRAO = (
    "*.crdownload", "*.part", "*.partial", "*.download", "*.opdownload", "*.tmp",
    ".*", "~$*", "desktop.ini", "thumbs.db",
)

EXEMPLO_TOML = """\
# Configuração do FileSense. Tudo aqui é opcional: apague o que não usar.

[geral]
# Cria subpastas por ano-mês (ex.: Imagens/2026-09)
por_data = false

# Só mexe em arquivos parados há pelo menos N segundos (evita pegar download em andamento)
idade_minima_segundos = 5

# Padrões extras para ignorar (somados aos padrões internos)
ignorar = ["*.iso"]

# Nomes das pastas especiais
pasta_outros = "Outros"
pasta_suspeitos = "_Verificar"
pasta_duplicados = "_Duplicados"

# Categorias novas ou alteradas. Uma extensão listada aqui sai da categoria padrão.
[categorias]
"Notas Fiscais" = ["xml"]
"Modelos 3D" = ["stl", "obj", "blend", "3mf"]
"Livros" = ["epub", "mobi", "azw3"]
"""


class ErroConfig(Exception):
    """Configuração inválida."""


@dataclass
class Config:
    categorias: dict[str, list[str]] = field(
        default_factory=lambda: {cat: list(exts) for cat, exts in CATEGORIAS_PADRAO.items()})
    ignorar: list[str] = field(default_factory=lambda: list(IGNORAR_PADRAO))
    por_data: bool = False
    idade_minima_segundos: int = 5
    pasta_outros: str = "Outros"
    pasta_suspeitos: str = "_Verificar"
    pasta_duplicados: str = "_Duplicados"


_TIPOS_GERAL: dict[str, tuple[type, str]] = {
    "por_data": (bool, "true ou false"),
    "idade_minima_segundos": (int, "um número inteiro"),
    "ignorar": (list, "uma lista de padrões"),
    "pasta_outros": (str, "um texto"),
    "pasta_suspeitos": (str, "um texto"),
    "pasta_duplicados": (str, "um texto"),
}


def caminho_padrao() -> Path:
    return pasta_dados() / "filesense.toml"


def carregar_config(caminho: Path | None = None) -> Config:
    """Carrega a configuração. Sem arquivo, usa os padrões."""
    cfg = Config()
    if caminho is None:
        caminho = caminho_padrao()
        if not caminho.exists():
            return cfg
    caminho = Path(caminho).expanduser()
    try:
        with caminho.open("rb") as f:
            dados = tomllib.load(f)
    except FileNotFoundError:
        raise ErroConfig(f"arquivo de configuração não encontrado: {caminho}") from None
    except tomllib.TOMLDecodeError as e:
        raise ErroConfig(f"erro de sintaxe em {caminho}: {e}") from None

    _aplicar_geral(cfg, dados.get("geral", {}))
    _aplicar_categorias(cfg, dados.get("categorias", {}))
    return cfg


def _aplicar_geral(cfg: Config, geral: Any) -> None:
    if not isinstance(geral, dict):
        raise ErroConfig("[geral] deve ser uma seção")
    for chave, valor in geral.items():
        if chave not in _TIPOS_GERAL:
            raise ErroConfig(f"opção desconhecida em [geral]: {chave}")
        tipo, descricao = _TIPOS_GERAL[chave]
        if not isinstance(valor, tipo) or (tipo is int and isinstance(valor, bool)):
            raise ErroConfig(f"[geral].{chave} deve ser {descricao}")
        if chave == "ignorar":
            cfg.ignorar += [str(p) for p in valor]
        else:
            setattr(cfg, chave, valor)


def _aplicar_categorias(cfg: Config, categorias: Any) -> None:
    if not isinstance(categorias, dict):
        raise ErroConfig("[categorias] deve ser uma seção")
    for nome, exts in categorias.items():
        if not isinstance(exts, list) or not all(isinstance(e, str) for e in exts):
            raise ErroConfig(f'a categoria "{nome}" deve ser uma lista, ex.: ["pdf", "docx"]')
        novas = [e.lower().lstrip(".") for e in exts]
        for lista in cfg.categorias.values():
            lista[:] = [e for e in lista if e not in novas]
        destino = cfg.categorias.setdefault(nome, [])
        destino += [e for e in novas if e not in destino]
