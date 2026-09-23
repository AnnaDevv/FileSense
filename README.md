# 🔍 FileSense

**Organizador de arquivos que entende o que cada arquivo realmente é.** Arruma sua pasta de Downloads em segundos, encontra arquivos duplicados, detecta arquivos disfarçados (como um "boleto.pdf" que na verdade é um vírus) e desfaz qualquer ação com um único comando.

![CI](https://github.com/SEU-USUARIO/filesense/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Dependências](https://img.shields.io/badge/depend%C3%AAncias-zero-brightgreen)
![Licença](https://img.shields.io/badge/licen%C3%A7a-MIT-green)

```text
$ filesense organizar
Organizando C:\Users\ana\Downloads

_Verificar (2)
  artigo_cientifico.pdf
    ⚠ é uma página HTML, não um .pdf (o download provavelmente falhou)
  boleto_vencido_2via.pdf
    ⚠ diz ser .pdf, mas é um programa executável

Áudios (1)
  podcast_ep42.mp3

Documentos (2)
  anotacoes.txt
  Curriculo_Ana_Silva.pdf

Imagens (4)
  comprovante_pix (1).png
  comprovante_pix.png
  IMG_20260812_143022.jpg
  screenshot

✓ 12 arquivo(s) organizados (21.1 MB). Mudou de ideia? Rode: filesense desfazer
⚠ 1 arquivo(s) com cara de golpe foram para _Verificar/. Não abra antes de conferir.
```

## O problema

A pasta Downloads de quase todo mundo vira um depósito: comprovantes, instaladores esquecidos, o mesmo PDF baixado três vezes, fotos sem nome. Organizar à mão é chato, e ferramentas simples que separam só pela extensão são enganadas facilmente.

## O que o FileSense faz

| Comando | O que faz |
|---|---|
| `filesense organizar` | Separa os arquivos em pastas por tipo (Imagens, Documentos, Vídeos...) |
| `filesense duplicados` | Encontra arquivos com conteúdo idêntico, mesmo com nomes diferentes |
| `filesense relatorio` | Mostra o que ocupa espaço, o que está esquecido há meses e o que é suspeito |
| `filesense vigiar` | Fica rodando e organiza cada arquivo novo assim que o download termina |
| `filesense desfazer` | Devolve tudo da última ação para o lugar original |
| `filesense historico` | Lista as últimas ações realizadas |
| `filesense config` | Mostra a configuração ou cria um arquivo de exemplo |

Sem pasta informada, o alvo é `~/Downloads`. Qualquer pasta funciona: `filesense organizar D:\Fotos`.

## Destaques

**Olha o conteúdo, não só o nome.** O FileSense lê os primeiros bytes de cada arquivo (as *magic bytes*) e compara com a extensão. Isso permite:

- classificar arquivos sem extensão (um `screenshot` sem `.png` vai para Imagens);
- detectar **downloads que falharam**, como um `.pdf` que na verdade é uma página de erro HTML;
- isolar **executáveis disfarçados** de documento em `_Verificar/`, um golpe comum por e-mail e WhatsApp.

**Nunca apaga nada.** Duplicados vão para `_Duplicados/` para você revisar. Toda ação fica registrada e pode ser revertida com `filesense desfazer`.

**Seguro por padrão.** O modo `--simular` mostra o plano sem mover nada. Downloads em andamento (`.crdownload`, `.part`), arquivos ocultos, temporários do Office e arquivos modificados nos últimos segundos são ignorados. Nomes repetidos nunca são sobrescritos: o segundo vira `arquivo (1).pdf`.

**Zero dependências.** Só a biblioteca padrão do Python. Funciona no Windows, macOS e Linux.

## Instalação

Requer Python 3.11 ou mais recente.

```bash
pip install git+https://github.com/SEU-USUARIO/filesense.git
```

Ou, para desenvolver:

```bash
git clone https://github.com/SEU-USUARIO/filesense.git
cd filesense
pip install -e ".[dev]"
```

## Uso

```bash
filesense organizar --simular          # veja o plano antes de mexer em qualquer coisa
filesense organizar                    # organiza ~/Downloads
filesense organizar ~/Desktop --por-data   # cria subpastas como Imagens/2026-09

filesense duplicados                   # lista duplicados e o espaço desperdiçado
filesense duplicados --mover           # move as cópias para _Duplicados/

filesense relatorio --dias 90          # arquivos sem uso há mais de 90 dias
filesense vigiar --intervalo 5         # organiza automaticamente a cada 5 segundos
filesense desfazer                     # reverte a última ação
```

### Rodar automaticamente ao ligar o computador

**Windows:** crie um atalho para `pythonw -m filesense vigiar` na pasta `shell:startup` (abra com `Win+R`).

**macOS/Linux:** adicione ao crontab (`crontab -e`) para organizar de hora em hora:

```cron
0 * * * * filesense organizar
```

## Configuração

Crie um arquivo de exemplo com `filesense config --criar`. Ele fica em `~/.filesense/filesense.toml`:

```toml
[geral]
por_data = false
idade_minima_segundos = 5
ignorar = ["*.iso"]

[categorias]
"Notas Fiscais" = ["xml"]
"Modelos 3D" = ["stl", "obj", "blend"]
```

Uma extensão listada numa categoria sua sai automaticamente da categoria padrão. Erros no arquivo geram mensagens claras, como `[geral].idade_minima_segundos deve ser um número inteiro`.

## Como funciona

```
src/filesense/
├── classifier.py   # extensão + magic bytes → categoria e alertas
├── organizer.py    # planejar() decide, executar() move
├── duplicates.py   # busca de duplicados em 3 etapas
├── history.py      # registro em JSON Lines e desfazer
├── report.py       # estatísticas da pasta
├── watcher.py      # modo vigia por polling
├── config.py       # padrões + TOML do usuário, com validação
└── cli.py          # interface de linha de comando
```

Algumas decisões de projeto:

- **Planejar e executar são etapas separadas.** `planejar()` só calcula para onde cada arquivo iria e não toca no disco. Isso torna o `--simular` trivial e a lógica fácil de testar.
- **Duplicados em 3 etapas.** Calcular o hash de tudo seria lento. Primeiro agrupa por tamanho (custo quase zero), depois compara o hash dos primeiros 64 KB e só então o hash completo dos candidatos que sobraram. Numa pasta com milhares de arquivos, a maioria é descartada sem ser lida por inteiro.
- **Alertas só quando há certeza.** Um `.txt` não tem assinatura binária, então o FileSense nunca afirma que ele está "errado". Alertas de extensão só aparecem para formatos que dá para confirmar pelo conteúdo, o que evita falsos positivos.
- **Executáveis confirmados pela estrutura PE.** Não basta começar com `MZ`: o FileSense segue o ponteiro do cabeçalho e confere a assinatura `PE\0\0`, como o próprio Windows faz.
- **Histórico à prova de falhas.** Cada ação é uma linha JSON. Ao desfazer, o arquivo é regravado de forma atômica (`os.replace`), então nunca fica corrompido pela metade. O desfazer também se recusa a sobrescrever um arquivo novo que tenha aparecido no lugar original.
- **Polling em vez de eventos do sistema.** O modo vigia verifica a pasta periodicamente. Funciona igual em qualquer sistema operacional, sem dependências, e combina com a regra de idade mínima que espera o download terminar.

## Testes

```bash
pytest -v
ruff check .
```

A suíte cobre classificação, conflitos de nome, desfazer, duplicados (incluindo arquivos iguais no início e diferentes no fim), configuração inválida e a CLI. O CI roda tudo em Windows, macOS e Linux com Python 3.11, 3.12 e 3.13.

## Próximos passos

- [ ] Interface gráfica simples com ícone na bandeja do sistema
- [ ] Regras por nome de arquivo (ex.: `*nota*fiscal*` → Notas Fiscais)
- [ ] Limpeza automática de `_Duplicados/` após N dias, com confirmação
- [ ] Publicação no PyPI

## Um bug real que virou teste

No primeiro uso numa pasta Downloads de verdade, um instalador `.msix` e um projeto do CorelDRAW (`.cdr`) foram parar em *Compactados*. Os dois são arquivos ZIP por dentro, e o FileSense confiava no conteúdo quando não conhecia a extensão. A correção: extensões conhecidas foram adicionadas, e um arquivo de extensão desconhecida com ZIP por dentro agora vai para *Outros*, porque muitos formatos modernos usam ZIP como contêiner. O caso está coberto em `tests/test_classifier.py`.

## Licença

MIT. Veja [LICENSE](LICENSE).
