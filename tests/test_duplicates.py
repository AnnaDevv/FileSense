import os
import time

from filesense.duplicates import encontrar_duplicados, mover_copias
from filesense.history import Historico


def test_encontra_duplicados_pelo_conteudo(pasta, criar, cfg):
    original = criar(pasta, "foto.jpg", b"mesmo conteudo")
    antigo = time.time() - 1000
    os.utime(original, (antigo, antigo))
    criar(pasta, "foto (1).jpg", b"mesmo conteudo")
    criar(pasta, "sub/copia_com_outro_nome.jpg", b"mesmo conteudo")
    criar(pasta, "outra.jpg", b"conteudo diferente")

    (grupo,) = encontrar_duplicados(pasta, cfg)

    assert grupo.original.name == "foto.jpg"
    assert len(grupo.copias) == 2
    assert grupo.desperdicio == 2 * len(b"mesmo conteudo")


def test_arquivos_grandes_iguais_no_inicio_mas_diferentes_no_fim(pasta, criar, cfg):
    base = os.urandom(200_000)
    diferente = base[:-1] + bytes([base[-1] ^ 1])
    criar(pasta, "a.bin", base)
    criar(pasta, "b.bin", base)
    criar(pasta, "c.bin", diferente)  # mesmo tamanho e mesmos primeiros 64 KB

    (grupo,) = encontrar_duplicados(pasta, cfg)
    assert {p.name for p in grupo.arquivos} == {"a.bin", "b.bin"}


def test_arquivos_vazios_nao_contam(pasta, criar, cfg):
    criar(pasta, "vazio1.txt", b"")
    criar(pasta, "vazio2.txt", b"")
    assert encontrar_duplicados(pasta, cfg) == []


def test_mover_copias_e_desfazer(pasta, criar, cfg):
    criar(pasta, "doc.pdf", b"igual")
    criar(pasta, "doc (1).pdf", b"igual")
    historico = Historico()

    movidos, erros = mover_copias(encontrar_duplicados(pasta, cfg), pasta, cfg, historico)

    assert not erros and len(movidos) == 1
    assert (pasta / "_Duplicados" / "doc (1).pdf").exists()
    assert encontrar_duplicados(pasta, cfg) == []  # a pasta _Duplicados é ignorada

    historico.desfazer_ultimo()
    assert (pasta / "doc (1).pdf").exists()
    assert not (pasta / "_Duplicados").exists()
