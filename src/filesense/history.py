"""Histórico de movimentações, para que qualquer ação possa ser desfeita."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import pasta_dados

Lote = dict[str, Any]


class Historico:
    """Guarda cada execução como uma linha JSON (formato JSON Lines)."""

    def __init__(self, arquivo: Path | None = None) -> None:
        self.arquivo = arquivo or pasta_dados() / "historico.jsonl"

    def registrar(self, pasta: Path, pares: list[tuple[Path, Path]],
                  acao: str = "organizar") -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        lote = {
            "quando": datetime.now().isoformat(timespec="seconds"),
            "acao": acao,
            "pasta": str(pasta),
            "movimentos": [[str(origem), str(destino)] for origem, destino in pares],
        }
        with self.arquivo.open("a", encoding="utf-8") as f:
            f.write(json.dumps(lote, ensure_ascii=False) + "\n")

    def lotes(self) -> list[Lote]:
        if not self.arquivo.exists():
            return []
        lotes = []
        for linha in self.arquivo.read_text(encoding="utf-8").splitlines():
            try:
                lotes.append(json.loads(linha))
            except json.JSONDecodeError:
                continue  # linha corrompida não impede o resto
        return lotes

    def desfazer_ultimo(self) -> tuple[Lote | None, int, list[str]]:
        """Devolve os arquivos do último lote para o lugar original."""
        lotes = self.lotes()
        if not lotes:
            return None, 0, []
        lote = lotes[-1]
        restaurados, problemas, pastas = 0, [], set()

        for origem, destino in reversed(lote["movimentos"]):
            o, d = Path(origem), Path(destino)
            if not d.exists():
                problemas.append(f"não encontrei mais {d.name} (foi movido ou apagado)")
                continue
            if o.exists():
                problemas.append(f"já existe outro arquivo em {o}, mantive {d.name} onde está")
                continue
            try:
                o.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(d), str(o))
            except OSError as e:
                problemas.append(f"{d.name}: {e}")
                continue
            restaurados += 1
            pastas.add(d.parent)

        _remover_pastas_vazias(pastas, Path(lote["pasta"]))
        self._salvar(lotes[:-1])
        return lote, restaurados, problemas

    def _salvar(self, lotes: list[Lote]) -> None:
        temporario = self.arquivo.with_suffix(".tmp")
        conteudo = "".join(json.dumps(lote, ensure_ascii=False) + "\n" for lote in lotes)
        temporario.write_text(conteudo, encoding="utf-8")
        os.replace(temporario, self.arquivo)  # troca atômica: nunca fica pela metade


def _remover_pastas_vazias(pastas: set[Path], limite: Path) -> None:
    """Apaga pastas que ficaram vazias, subindo até (sem incluir) a pasta limite."""
    for pasta in sorted(pastas, key=lambda p: len(p.parts), reverse=True):
        atual = pasta
        while atual != limite and atual.is_relative_to(limite):
            try:
                atual.rmdir()  # só funciona se estiver vazia
            except OSError:
                break
            atual = atual.parent
