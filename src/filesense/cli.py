"""Interface de linha de comando do FileSense."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from . import __version__
from .config import EXEMPLO_TOML, Config, ErroConfig, caminho_padrao, carregar_config
from .duplicates import encontrar_duplicados, mover_copias
from .history import Historico
from .organizer import Movimento, executar, planejar
from .report import gerar_relatorio
from .utils import (
    amarelo,
    ciano,
    cinza,
    negrito,
    pasta_downloads,
    sem_acento,
    tamanho_legivel,
    verde,
    vermelho,
)
from .watcher import vigiar


def _pasta(args: argparse.Namespace) -> Path:
    pasta = (args.pasta or pasta_downloads()).expanduser().resolve()
    if not pasta.is_dir():
        raise FileNotFoundError(f"pasta não encontrada: {pasta}")
    return pasta


def _relativo(caminho: Path, pasta: Path) -> str:
    try:
        return caminho.relative_to(pasta).as_posix()
    except ValueError:
        return str(caminho)


def _linha_alerta(m: Movimento) -> str:
    cor = vermelho if m.perigoso else amarelo
    return cor(f"    ⚠ {m.alerta}")


# ---------------------------------------------------------------- organizar

def _imprimir_plano(movimentos: list[Movimento], pasta: Path) -> None:
    por_categoria: dict[str, list[Movimento]] = defaultdict(list)
    for m in movimentos:
        por_categoria[m.categoria].append(m)

    for categoria in sorted(por_categoria, key=sem_acento):
        itens = por_categoria[categoria]
        print(f"\n{ciano(categoria)} {cinza(f'({len(itens)})')}")
        for m in itens:
            linha = f"  {m.origem.name}"
            destino = _relativo(m.destino, pasta)
            if m.destino.name != m.origem.name or destino.count("/") > 1:
                linha += cinza(f"  →  {destino}")
            print(linha)
            if m.alerta:
                print(_linha_alerta(m))


def cmd_organizar(args: argparse.Namespace, cfg: Config) -> int:
    pasta = _pasta(args)
    if args.por_data:
        cfg.por_data = True

    movimentos = planejar(pasta, cfg)
    print(negrito(f"Organizando {pasta}"))
    if not movimentos:
        print(verde("Nada para organizar: a pasta já está em ordem."))
        return 0

    _imprimir_plano(movimentos, pasta)
    perigosos = sum(m.perigoso for m in movimentos)

    if args.simular:
        print(amarelo(f"\nSimulação: {len(movimentos)} arquivo(s) seriam movidos. "
                      "Nada foi alterado."))
        return 0

    feitos, erros = executar(movimentos, pasta, Historico())
    for m, motivo in erros:
        print(vermelho(f"  ✗ {m.origem.name}: {motivo}"))

    total = sum(m.destino.stat().st_size for m in feitos if m.destino.exists())
    print(verde(f"\n✓ {len(feitos)} arquivo(s) organizados ({tamanho_legivel(total)}).")
          + cinza(" Mudou de ideia? Rode: filesense desfazer"))
    if perigosos:
        print(vermelho(f"⚠ {perigosos} arquivo(s) com cara de golpe foram para "
                       f"{cfg.pasta_suspeitos}/. Não abra antes de conferir."))
    return 1 if erros and not feitos else 0


# ---------------------------------------------------------------- duplicados

def cmd_duplicados(args: argparse.Namespace, cfg: Config) -> int:
    pasta = _pasta(args)
    print(negrito(f"Procurando duplicados em {pasta}..."))
    grupos = encontrar_duplicados(pasta, cfg)
    if not grupos:
        print(verde("Nenhum arquivo duplicado encontrado."))
        return 0

    for g in grupos[:args.limite]:
        print(f"\n{negrito(tamanho_legivel(g.tamanho))} {cinza(f'× {len(g.arquivos)} arquivos')}")
        print(verde(f"  manter  {_relativo(g.original, pasta)}"))
        for copia in g.copias:
            print(amarelo(f"  cópia   {_relativo(copia, pasta)}"))
    if len(grupos) > args.limite:
        print(cinza(f"\n... e mais {len(grupos) - args.limite} grupo(s). Use --limite para ver."))

    copias = sum(len(g.copias) for g in grupos)
    desperdicio = sum(g.desperdicio for g in grupos)
    print(negrito(f"\n{len(grupos)} grupo(s), {copias} cópia(s), "
                  f"{tamanho_legivel(desperdicio)} desperdiçados."))

    if not args.mover:
        print(cinza(f"Use --mover para levar as cópias para {cfg.pasta_duplicados}/ "
                    "(nada é apagado)."))
        return 0
    if args.simular:
        print(amarelo(f"Simulação: {copias} cópia(s) seriam movidas. Nada foi alterado."))
        return 0

    movidos, erros = mover_copias(grupos, pasta, cfg, Historico())
    for caminho, motivo in erros:
        print(vermelho(f"  ✗ {caminho.name}: {motivo}"))
    print(verde(f"✓ {len(movidos)} cópia(s) movidas para {cfg.pasta_duplicados}/. "
                "Revise e apague quando quiser.") + cinza(" Para reverter: filesense desfazer"))
    return 0


# ---------------------------------------------------------------- relatório

def cmd_relatorio(args: argparse.Namespace, cfg: Config) -> int:
    pasta = _pasta(args)
    r = gerar_relatorio(pasta, cfg, dias_esquecido=args.dias)
    print(negrito(f"Relatório de {pasta}"))
    print(f"{r.total_arquivos} arquivo(s), {tamanho_legivel(r.total_bytes)}\n")
    if not r.total_arquivos:
        return 0

    maior = max(b for _, b in r.por_categoria.values()) or 1
    print(cinza(f"{'Categoria':<16}{'Arquivos':>9}{'Tamanho':>11}"))
    for categoria, (qtd, tam) in sorted(r.por_categoria.items(), key=lambda kv: -kv[1][1]):
        barra = "█" * max(1, round(tam / maior * 24)) if tam else ""
        print(f"{categoria:<16}{qtd:>9}{tamanho_legivel(tam):>11}  {ciano(barra)}")

    print(negrito("\nMaiores arquivos"))
    for caminho, tam in r.maiores:
        print(f"  {tamanho_legivel(tam):>10}  {_relativo(caminho, pasta)}")

    if r.esquecidos:
        total = sum(t for _, t, _ in r.esquecidos)
        print(negrito(f"\nSem modificação há mais de {args.dias} dias")
              + cinza(f" ({len(r.esquecidos)} arquivo(s), {tamanho_legivel(total)})"))
        for caminho, tam, dias in r.esquecidos[:10]:
            print(f"  {tamanho_legivel(tam):>10}  {_relativo(caminho, pasta)} "
                  + cinza(f"({dias} dias)"))

    if r.suspeitos:
        print(negrito(vermelho("\nArquivos suspeitos")))
        for caminho, alerta, perigoso in r.suspeitos:
            cor = vermelho if perigoso else amarelo
            print(f"  {_relativo(caminho, pasta)}\n" + cor(f"    ⚠ {alerta}"))
    return 0


# ---------------------------------------------------------------- vigiar

def cmd_vigiar(args: argparse.Namespace, cfg: Config) -> int:
    pasta = _pasta(args)
    print(negrito(f"Vigiando {pasta}")
          + cinza(f" (verifica a cada {args.intervalo:g}s; Ctrl+C para parar)"))

    def ao_mover(feitos: list[Movimento], erros: list[tuple[Movimento, str]]) -> None:
        hora = cinza(datetime.now().strftime("%H:%M:%S"))
        for m in feitos:
            print(f"{hora}  {m.origem.name} → {ciano(_relativo(m.destino, pasta))}")
            if m.alerta:
                print(_linha_alerta(m))
        for m, motivo in erros:
            print(f"{hora}  " + vermelho(f"✗ {m.origem.name}: {motivo} (tento de novo depois)"))

    try:
        vigiar(pasta, cfg, Historico(), args.intervalo, ao_mover)
    except KeyboardInterrupt:
        print(cinza("\nVigia encerrado."))
    return 0


# ---------------------------------------------------------------- histórico

def cmd_desfazer(args: argparse.Namespace, cfg: Config) -> int:
    lote, restaurados, problemas = Historico().desfazer_ultimo()
    if lote is None:
        print("Nada para desfazer.")
        return 0
    print(verde(f"✓ {restaurados} arquivo(s) voltaram para o lugar")
          + cinza(f" (ação '{lote['acao']}' de {lote['quando'].replace('T', ' ')})"))
    for p in problemas:
        print(amarelo(f"  ⚠ {p}"))
    return 0


def cmd_historico(args: argparse.Namespace, cfg: Config) -> int:
    lotes = Historico().lotes()
    if not lotes:
        print("O histórico está vazio.")
        return 0
    for lote in reversed(lotes[-args.limite:]):
        quando = lote["quando"].replace("T", " ")
        print(f"{cinza(quando)}  {ciano(lote['acao']):<12}  "
              f"{len(lote['movimentos']):>4} arquivo(s)  {lote['pasta']}")
    print(cinza("\n'filesense desfazer' reverte a ação mais recente (a primeira da lista)."))
    return 0


def cmd_config(args: argparse.Namespace, cfg: Config) -> int:
    caminho = caminho_padrao()
    if args.criar:
        if caminho.exists():
            print(amarelo(f"Já existe uma configuração em {caminho}"))
            return 1
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(EXEMPLO_TOML, encoding="utf-8")
        print(verde(f"✓ Configuração de exemplo criada em {caminho}"))
        return 0
    estado = verde("existe") if caminho.exists() else cinza("não existe (usando padrões)")
    print(f"Arquivo de configuração: {caminho} [{estado}]")
    print(negrito("\nCategorias ativas"))
    for categoria, exts in cfg.categorias.items():
        if exts:
            print(f"  {ciano(categoria):<16} {cinza(', '.join(exts))}")
    if not caminho.exists():
        print(cinza("\nCrie um arquivo de exemplo com: filesense config --criar"))
    return 0


# ---------------------------------------------------------------- parser

def construir_parser() -> argparse.ArgumentParser:
    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("--config", type=Path, metavar="ARQUIVO",
                       help="arquivo TOML de configuração (padrão: ~/.filesense/filesense.toml)")

    parser = argparse.ArgumentParser(
        prog="filesense",
        description="Organizador inteligente de arquivos. Arruma pastas, acha duplicados, "
                    "detecta arquivos disfarçados e desfaz tudo com um comando.",
        epilog="Exemplo: filesense organizar ~/Downloads --simular",
    )
    parser.add_argument("--versao", action="version", version=f"filesense {__version__}")
    sub = parser.add_subparsers(dest="comando", metavar="COMANDO")

    def com_pasta(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
        p.add_argument("pasta", nargs="?", type=Path, help="pasta alvo (padrão: ~/Downloads)")
        return p

    p = com_pasta(sub.add_parser("organizar", parents=[comum],
                                 help="separa os arquivos em pastas por tipo"))
    p.add_argument("-s", "--simular", action="store_true",
                   help="mostra o que seria feito, sem mover nada")
    p.add_argument("--por-data", action="store_true", help="cria subpastas por ano-mês")
    p.set_defaults(func=cmd_organizar)

    p = com_pasta(sub.add_parser("duplicados", parents=[comum],
                                 help="encontra arquivos com conteúdo idêntico"))
    p.add_argument("--mover", action="store_true", help="move as cópias para _Duplicados/")
    p.add_argument("-s", "--simular", action="store_true", help="com --mover, só simula")
    p.add_argument("--limite", type=int, default=15, help="quantos grupos exibir (padrão: 15)")
    p.set_defaults(func=cmd_duplicados)

    p = com_pasta(sub.add_parser("relatorio", parents=[comum],
                                 help="mostra o que ocupa espaço e o que é suspeito"))
    p.add_argument("--dias", type=int, default=180,
                   help="dias sem modificação para considerar esquecido (padrão: 180)")
    p.set_defaults(func=cmd_relatorio)

    p = com_pasta(sub.add_parser("vigiar", parents=[comum],
                                 help="organiza automaticamente os arquivos que chegarem"))
    p.add_argument("--intervalo", type=float, default=10.0,
                   help="segundos entre verificações (padrão: 10)")
    p.set_defaults(func=cmd_vigiar)

    p = sub.add_parser("desfazer", parents=[comum], help="reverte a última ação")
    p.set_defaults(func=cmd_desfazer)

    p = sub.add_parser("historico", parents=[comum], help="lista as últimas ações")
    p.add_argument("--limite", type=int, default=10)
    p.set_defaults(func=cmd_historico)

    p = sub.add_parser("config", parents=[comum], help="mostra ou cria a configuração")
    p.add_argument("--criar", action="store_true", help="cria um arquivo de exemplo")
    p.set_defaults(func=cmd_config)

    return parser


def main(argv: list[str] | None = None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(errors="replace")  # consoles antigos sem suporte a ✓ e ⚠

    parser = construir_parser()
    args = parser.parse_args(argv)
    if not args.comando:
        parser.print_help()
        return 0
    try:
        cfg = carregar_config(args.config)
        return args.func(args, cfg)
    except ErroConfig as e:
        print(vermelho(f"Erro na configuração: {e}"), file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(vermelho(f"Erro: {e}"), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(cinza("\nInterrompido."))
        return 130
