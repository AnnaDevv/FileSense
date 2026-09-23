from collections.abc import Callable
from pathlib import Path

import pytest

from filesense.config import Config

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF = b"%PDF-1.7\n" + b"x" * 32
ZIP = b"PK\x03\x04" + b"\x00" * 32
HTML = b"<!DOCTYPE html><html><body>Erro 404</body></html>"
# executável mínimo do Windows: 'MZ', offset em 0x3C apontando para 'PE\0\0'
EXE = b"MZ" + b"\x00" * 58 + (0x40).to_bytes(4, "little") + b"PE\x00\x00" + b"\x00" * 64


@pytest.fixture(autouse=True)
def filesense_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isola histórico e configuração em uma pasta temporária."""
    home = tmp_path / "filesense_home"
    monkeypatch.setenv("FILESENSE_HOME", str(home))
    monkeypatch.setenv("NO_COLOR", "1")
    return home


@pytest.fixture
def cfg() -> Config:
    config = Config()
    config.idade_minima_segundos = 0
    return config


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    p = tmp_path / "Downloads"
    p.mkdir()
    return p


@pytest.fixture
def criar() -> Callable[..., Path]:
    def _criar(pasta: Path, nome: str, conteudo: bytes = b"conteudo") -> Path:
        caminho = pasta / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(conteudo)
        return caminho
    return _criar
