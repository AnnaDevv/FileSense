from conftest import EXE, HTML, PDF, PNG, ZIP

from filesense.classifier import Classificador, detectar_tipo
from filesense.config import Config


def classificador() -> Classificador:
    cfg = Config()
    return Classificador(cfg.categorias, cfg.pasta_outros, cfg.pasta_suspeitos)


def test_classifica_pela_extensao(pasta, criar):
    c = classificador().classificar(criar(pasta, "relatorio.PDF", PDF))
    assert c.categoria == "Documentos"
    assert c.alerta is None


def test_arquivo_sem_extensao_e_classificado_pelo_conteudo(pasta, criar):
    c = classificador().classificar(criar(pasta, "imagem_sem_extensao", PNG))
    assert c.categoria == "Imagens"
    assert c.tipo_real == "png"


def test_extensao_desconhecida_vai_para_outros(pasta, criar):
    assert classificador().classificar(criar(pasta, "dados.xyz")).categoria == "Outros"


def test_executavel_disfarcado_de_pdf_vai_para_verificacao(pasta, criar):
    c = classificador().classificar(criar(pasta, "boleto.pdf", EXE))
    assert c.categoria == "_Verificar"
    assert c.perigoso
    assert "executável" in c.alerta


def test_pdf_que_e_pagina_html_indica_download_falho(pasta, criar):
    c = classificador().classificar(criar(pasta, "artigo.pdf", HTML))
    assert c.categoria == "_Verificar"
    assert "download" in c.alerta
    assert not c.perigoso


def test_extensao_errada_usa_o_tipo_real(pasta, criar):
    c = classificador().classificar(criar(pasta, "foto.jpg", PNG))
    assert c.categoria == "Imagens"
    assert "PNG" in c.alerta


def test_docx_e_zip_por_dentro_e_isso_e_normal(pasta, criar):
    c = classificador().classificar(criar(pasta, "contrato.docx", ZIP))
    assert c.categoria == "Documentos"
    assert c.alerta is None


def test_texto_comum_nunca_gera_alerta(pasta, criar):
    c = classificador().classificar(criar(pasta, "notas.txt", b"MZ nao e executavel"))
    assert c.alerta is None
    assert c.categoria == "Documentos"


def test_detectar_tipo_de_arquivo_inexistente(pasta):
    assert detectar_tipo(pasta / "nao_existe.bin") is None


def test_instalador_msix_nao_e_confundido_com_zip(pasta, criar):
    # Bug real: .msix é ZIP por dentro e ia parar em Compactados
    c = classificador().classificar(criar(pasta, "python-manager.msix", ZIP))
    assert c.categoria == "Instaladores"
    assert c.alerta is None


def test_arquivo_coreldraw_vai_para_design(pasta, criar):
    assert classificador().classificar(criar(pasta, "logo.cdr", ZIP)).categoria == "Design"


def test_extensao_desconhecida_com_zip_por_dentro_vai_para_outros(pasta, criar):
    assert classificador().classificar(criar(pasta, "projeto.formato", ZIP)).categoria == "Outros"


def test_arquivo_sem_extensao_com_zip_por_dentro_e_compactado(pasta, criar):
    assert classificador().classificar(criar(pasta, "backup", ZIP)).categoria == "Compactados"
