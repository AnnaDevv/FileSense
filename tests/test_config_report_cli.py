import os
import time

import pytest
from conftest import EXE, PDF, PNG

from filesense.cli import main
from filesense.config import ErroConfig, carregar_config
from filesense.report import gerar_relatorio


def envelhecer(*arquivos, dias=0):
    momento = time.time() - 3600 - dias * 86400
    for a in arquivos:
        os.utime(a, (momento, momento))


def test_config_personalizada(tmp_path):
    arquivo = tmp_path / "filesense.toml"
    arquivo.write_text(
        '[geral]\npor_data = true\nignorar = ["*.iso"]\n\n'
        '[categorias]\n"Notas Fiscais" = [".XML"]\n',
        encoding="utf-8",
    )
    cfg = carregar_config(arquivo)

    assert cfg.por_data is True
    assert "*.iso" in cfg.ignorar and "*.crdownload" in cfg.ignorar
    assert cfg.categorias["Notas Fiscais"] == ["xml"]
    assert "xml" not in cfg.categorias["Código"]


@pytest.mark.parametrize("conteudo", [
    "[geral]\nidade_minima_segundos = 'dez'\n",
    "[geral]\nopcao_que_nao_existe = 1\n",
    '[categorias]\nFotos = "jpg"\n',
    "isso nao e toml [",
])
def test_config_invalida_gera_erro_claro(tmp_path, conteudo):
    arquivo = tmp_path / "filesense.toml"
    arquivo.write_text(conteudo, encoding="utf-8")
    with pytest.raises(ErroConfig):
        carregar_config(arquivo)


def test_relatorio(pasta, criar, cfg):
    velho = criar(pasta, "antigo.png", PNG)
    envelhecer(velho, dias=400)
    criar(pasta, "nota.pdf", PDF)
    criar(pasta, "boleto.pdf", EXE)

    r = gerar_relatorio(pasta, cfg, dias_esquecido=180)

    assert r.total_arquivos == 3
    assert r.por_categoria["Imagens"][0] == 1
    assert [p.name for p, _, _ in r.esquecidos] == ["antigo.png"]
    assert r.suspeitos[0][0].name == "boleto.pdf" and r.suspeitos[0][2]


def test_cli_simular_organizar_e_desfazer(pasta, criar, capsys):
    arquivo = criar(pasta, "nota.pdf", PDF)
    envelhecer(arquivo)

    assert main(["organizar", str(pasta), "--simular"]) == 0
    assert arquivo.exists()
    assert "Simulação" in capsys.readouterr().out

    assert main(["organizar", str(pasta)]) == 0
    assert (pasta / "Documentos" / "nota.pdf").exists()

    assert main(["desfazer"]) == 0
    assert arquivo.exists()


def test_cli_pasta_inexistente(tmp_path, capsys):
    assert main(["organizar", str(tmp_path / "nao_existe")]) == 1
    assert "não encontrada" in capsys.readouterr().err


def test_cli_config_criar(filesense_home):
    assert main(["config", "--criar"]) == 0
    assert (filesense_home / "filesense.toml").exists()
    assert main(["config", "--criar"]) == 1  # não sobrescreve
