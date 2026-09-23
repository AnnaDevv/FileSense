import os
import time

from conftest import EXE, PDF, PNG

from filesense.history import Historico
from filesense.organizer import executar, planejar


def test_organiza_arquivos_por_categoria(pasta, criar, cfg):
    criar(pasta, "foto.png", PNG)
    criar(pasta, "nota.pdf", PDF)
    criar(pasta, "musica.mp3", b"ID3" + b"\x00" * 10)

    feitos, erros = executar(planejar(pasta, cfg), pasta)

    assert not erros
    assert len(feitos) == 3
    assert (pasta / "Imagens" / "foto.png").exists()
    assert (pasta / "Documentos" / "nota.pdf").exists()
    assert (pasta / "Áudios" / "musica.mp3").exists()


def test_nome_repetido_nao_sobrescreve(pasta, criar, cfg):
    criar(pasta, "Documentos/nota.pdf", PDF)
    criar(pasta, "nota.pdf", PDF + b"diferente")

    executar(planejar(pasta, cfg), pasta)

    assert (pasta / "Documentos" / "nota.pdf").read_bytes() == PDF
    assert (pasta / "Documentos" / "nota (1).pdf").exists()


def test_ignora_downloads_incompletos_e_ocultos(pasta, criar, cfg):
    criar(pasta, "filme.mp4.crdownload")
    criar(pasta, "arquivo.part")
    criar(pasta, ".oculto")
    criar(pasta, "~$planilha.xlsx")

    assert planejar(pasta, cfg) == []


def test_ignora_arquivos_recentes(pasta, criar, cfg):
    cfg.idade_minima_segundos = 60
    arquivo = criar(pasta, "baixando.pdf", PDF)
    assert planejar(pasta, cfg) == []

    antigo = time.time() - 120
    os.utime(arquivo, (antigo, antigo))
    assert len(planejar(pasta, cfg)) == 1


def test_subpastas_por_data(pasta, criar, cfg):
    cfg.por_data = True
    arquivo = criar(pasta, "foto.png", PNG)
    data = time.mktime((2025, 3, 15, 12, 0, 0, 0, 0, -1))
    os.utime(arquivo, (data, data))

    (movimento,) = planejar(pasta, cfg)
    assert movimento.destino == pasta / "Imagens" / "2025-03" / "foto.png"


def test_simulacao_nao_move_nada(pasta, criar, cfg):
    arquivo = criar(pasta, "nota.pdf", PDF)
    assert len(planejar(pasta, cfg)) == 1
    assert arquivo.exists()


def test_executavel_disfarcado_fica_em_quarentena(pasta, criar, cfg):
    criar(pasta, "fatura.pdf", EXE)
    (movimento,) = planejar(pasta, cfg)
    assert movimento.perigoso
    assert movimento.destino.parent.name == "_Verificar"


def test_desfazer_restaura_e_remove_pastas_vazias(pasta, criar, cfg):
    criar(pasta, "foto.png", PNG)
    criar(pasta, "nota.pdf", PDF)
    historico = Historico()
    executar(planejar(pasta, cfg), pasta, historico)

    lote, restaurados, problemas = historico.desfazer_ultimo()

    assert lote is not None
    assert restaurados == 2 and problemas == []
    assert (pasta / "foto.png").exists() and (pasta / "nota.pdf").exists()
    assert not (pasta / "Imagens").exists()
    assert historico.lotes() == []


def test_desfazer_nao_sobrescreve_arquivo_novo(pasta, criar, cfg):
    criar(pasta, "nota.pdf", PDF)
    historico = Historico()
    executar(planejar(pasta, cfg), pasta, historico)
    criar(pasta, "nota.pdf", b"arquivo novo com o mesmo nome")

    _, restaurados, problemas = historico.desfazer_ultimo()

    assert restaurados == 0 and len(problemas) == 1
    assert (pasta / "nota.pdf").read_bytes() == b"arquivo novo com o mesmo nome"
    assert (pasta / "Documentos" / "nota.pdf").exists()


def test_desfazer_sem_historico():
    assert Historico().desfazer_ultimo() == (None, 0, [])


def test_vigiar_organiza_e_para(pasta, criar, cfg):
    from filesense.watcher import vigiar

    criar(pasta, "nota.pdf", PDF)
    recebidos = []
    vigiar(pasta, cfg, ao_mover=lambda feitos, erros: recebidos.extend(feitos),
           parar=lambda: True)

    assert [m.origem.name for m in recebidos] == ["nota.pdf"]
    assert (pasta / "Documentos" / "nota.pdf").exists()
