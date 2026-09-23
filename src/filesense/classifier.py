"""Descobre a categoria de um arquivo pela extensão e pelo conteúdo real (magic bytes).

A extensão diz o que o arquivo *afirma* ser; os primeiros bytes dizem o que ele *é*.
Comparar os dois permite detectar downloads que falharam (um .pdf que é uma página HTML)
e executáveis disfarçados (um .pdf que é um .exe), um truque clássico de golpes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

CATEGORIAS_PADRAO: dict[str, list[str]] = {
    "Imagens": ["jpg", "jpeg", "png", "gif", "webp", "bmp", "svg", "heic", "heif", "tiff",
                "ico", "avif", "raw"],
    "Vídeos": ["mp4", "mkv", "mov", "avi", "wmv", "webm", "flv", "m4v", "3gp"],
    "Áudios": ["mp3", "wav", "flac", "aac", "ogg", "m4a", "wma", "opus"],
    "Documentos": ["pdf", "doc", "docx", "odt", "rtf", "txt", "md", "epub", "mobi"],
    "Planilhas": ["xls", "xlsx", "xlsm", "ods", "csv", "tsv"],
    "Apresentações": ["ppt", "pptx", "odp", "key"],
    "Compactados": ["zip", "rar", "7z", "tar", "gz", "tgz", "bz2", "xz", "iso"],
    "Instaladores": ["exe", "msi", "msix", "msixbundle", "appx", "appxbundle", "dmg", "pkg",
                     "deb", "rpm", "apk", "appimage"],
    "Design": ["psd", "ai", "cdr", "fig", "sketch", "xd", "indd", "afdesign"],
    "Código": ["py", "js", "ts", "jsx", "tsx", "html", "htm", "css", "json", "xml", "yaml",
               "yml", "toml", "sql", "java", "c", "cpp", "h", "cs", "go", "rs", "php", "rb",
               "sh", "ps1", "bat", "ipynb", "ahk"],
    "Fontes": ["ttf", "otf", "woff", "woff2"],
    "Torrents": ["torrent"],
}

# Assinaturas no início do arquivo -> tipo canônico.
_ASSINATURAS: tuple[tuple[bytes, str], ...] = (
    (b"%PDF", "pdf"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"PK\x03\x04", "zip"),
    (b"Rar!\x1a\x07", "rar"),
    (b"7z\xbc\xaf\x27\x1c", "7z"),
    (b"\x1f\x8b", "gz"),
    (b"\xfd7zXZ\x00", "xz"),
    (b"ID3", "mp3"),
    (b"\xff\xfb", "mp3"),
    (b"\xff\xf3", "mp3"),
    (b"OggS", "ogg"),
    (b"fLaC", "flac"),
    (b"\x1aE\xdf\xa3", "mkv"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole"),  # Office antigo (.doc/.xls/.ppt) e .msi
    (b"\x7fELF", "elf"),
)

# Extensões que compartilham o mesmo formato interno.
_FAMILIA: dict[str, str] = {
    "jpeg": "jpg",
    "tgz": "gz",
    "webm": "mkv",
    **dict.fromkeys(("docx", "xlsx", "xlsm", "pptx", "odt", "ods", "odp", "epub", "apk",
                     "jar", "whl", "xpi", "msix", "msixbundle", "appx", "appxbundle", "cdr",
                     "fig", "sketch", "xd", "afdesign"), "zip"),
    **dict.fromkeys(("m4a", "m4v", "mov", "3gp", "heic", "heif", "avif"), "mp4"),
    **dict.fromkeys(("doc", "xls", "ppt", "msi", "msg"), "ole"),
    **dict.fromkeys(("dll", "scr"), "exe"),
}

# Tipos que conseguimos confirmar pelo conteúdo. Para os outros (ex.: .txt, .csv)
# não dá para afirmar que a extensão está errada, então não geramos alerta.
_DETECTAVEIS = {t for _, t in _ASSINATURAS} | {"exe", "mp4", "webp", "wav", "avi"}
_PERIGOSOS = {"exe", "elf"}


def _grupo(tipo: str) -> str:
    return _FAMILIA.get(tipo, tipo)


def _eh_executavel_pe(f: BinaryIO, cab: bytes) -> bool:
    """Confirma um executável do Windows: 'MZ' no início e 'PE\\0\\0' no offset indicado."""
    if len(cab) < 0x40:
        return False
    offset = int.from_bytes(cab[0x3C:0x40], "little")
    if offset + 4 <= len(cab):
        return cab[offset:offset + 4] == b"PE\0\0"
    f.seek(offset)
    return f.read(4) == b"PE\0\0"


def tipo_pelo_cabecalho(cab: bytes) -> str | None:
    for assinatura, tipo in _ASSINATURAS:
        if cab.startswith(assinatura):
            return tipo
    if cab[4:8] == b"ftyp":
        return "mp4"
    if cab[:4] == b"RIFF":
        return {b"WEBP": "webp", b"WAVE": "wav", b"AVI ": "avi"}.get(cab[8:12])
    inicio = cab.lstrip(b"\xef\xbb\xbf \t\r\n")[:15].lower()
    if inicio.startswith((b"<!doctype html", b"<html")):
        return "html"
    return None


def detectar_tipo(arquivo: Path) -> str | None:
    """Lê o começo do arquivo e retorna o tipo real, ou None se não reconhecer."""
    try:
        with arquivo.open("rb") as f:
            cab = f.read(1024)
            if cab.startswith(b"MZ"):
                return "exe" if _eh_executavel_pe(f, cab) else None
    except OSError:
        return None
    return tipo_pelo_cabecalho(cab)


@dataclass(frozen=True)
class Classificacao:
    categoria: str
    tipo_real: str | None = None
    alerta: str | None = None
    perigoso: bool = False


class Classificador:
    def __init__(self, categorias: dict[str, list[str]], pasta_outros: str = "Outros",
                 pasta_suspeitos: str = "_Verificar") -> None:
        self._por_extensao = {
            ext.lower().lstrip("."): cat for cat, exts in categorias.items() for ext in exts
        }
        self.pasta_outros = pasta_outros
        self.pasta_suspeitos = pasta_suspeitos

    def classificar(self, arquivo: Path) -> Classificacao:
        ext = arquivo.suffix.lower().lstrip(".")
        real = detectar_tipo(arquivo)
        cat_ext = self._por_extensao.get(ext) if ext else None

        if real and ext and _grupo(ext) != _grupo(real):
            if real in _PERIGOSOS:
                return Classificacao(self.pasta_suspeitos, real,
                                     f"diz ser .{ext}, mas é um programa executável", True)
            if _grupo(ext) in _DETECTAVEIS:
                if real == "html":
                    return Classificacao(
                        self.pasta_suspeitos, real,
                        f"é uma página HTML, não um .{ext} (o download provavelmente falhou)")
                categoria = self._por_extensao.get(real) or cat_ext or self.pasta_outros
                return Classificacao(categoria, real,
                                     f"a extensão é .{ext}, mas o conteúdo é {real.upper()}")

        if cat_ext:
            return Classificacao(cat_ext, real)
        # Muitos formatos (instaladores, projetos de design, e-books) são ZIP por dentro.
        # Se a extensão é desconhecida, não dá para afirmar que é um arquivo compactado.
        if real and not (ext and real == "zip"):
            return Classificacao(self._por_extensao.get(real, self.pasta_outros), real)
        return Classificacao(self.pasta_outros)
