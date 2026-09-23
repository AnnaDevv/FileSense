"""Interface gráfica do FileSense — organiza pastas sem precisar do terminal."""
import ctypes
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from filesense.config import Config, caminho_padrao, carregar_config, salvar_config  # noqa: E402
from filesense.history import Historico  # noqa: E402
from filesense.organizer import executar, planejar  # noqa: E402
from filesense.utils import pasta_downloads  # noqa: E402
from filesense.watcher import vigiar  # noqa: E402

ACCENT = "#0E9F87"
ACCENT_HOVER = "#0B7F6D"
FONTE = "Segoe UI"
RAIO = 6
ALTURA_CONTROLE = 34
PAD = 24

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("green")


def caminho_recurso(nome: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, nome)


def corrigir_janela_windows(janela):
    """Desliga o efeito Mica/acrílico do Windows 11, que tinge janelas secundárias
    com a cor de destaque do sistema em vez do tema escuro/claro do app."""
    if sys.platform != "win32":
        return
    try:
        janela.update()
        hwnd = ctypes.windll.user32.GetParent(janela.winfo_id())
        escuro = ctypes.c_int(1 if ctk.get_appearance_mode() == "Dark" else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(escuro), ctypes.sizeof(escuro))
        sem_fundo = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(sem_fundo), ctypes.sizeof(sem_fundo))
    except Exception:
        pass


def cor_divisor() -> str:
    return "#3A3A3A" if ctk.get_appearance_mode() == "Dark" else "#E2E2E2"


def cor_secundaria() -> str:
    return "#A0A0A0" if ctk.get_appearance_mode() == "Dark" else "#6B6B6B"


def botao_primario(mestre, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(
        mestre, fg_color=ACCENT, hover_color=ACCENT_HOVER, height=ALTURA_CONTROLE,
        corner_radius=RAIO, font=ctk.CTkFont(family=FONTE, size=13, weight="bold"), **kw,
    )


def botao_secundario(mestre, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(
        mestre, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"),
        hover_color=cor_divisor(), height=ALTURA_CONTROLE, corner_radius=RAIO,
        font=ctk.CTkFont(family=FONTE, size=13), **kw,
    )


def campo(mestre, **kw) -> ctk.CTkEntry:
    return ctk.CTkEntry(
        mestre, height=ALTURA_CONTROLE, corner_radius=RAIO, border_color=cor_divisor(),
        font=ctk.CTkFont(family=FONTE, size=13), **kw,
    )


class JanelaCategoria(ctk.CTkToplevel):
    """Formulário para criar ou editar uma categoria (pasta + extensões)."""

    def __init__(self, mestre, nome_atual, extensoes_atuais, ao_salvar):
        super().__init__(mestre)
        self.title("Nova categoria" if nome_atual is None else "Editar categoria")
        self.geometry("440x300")
        self.resizable(False, False)
        self.ao_salvar = ao_salvar
        self.nome_original = nome_atual
        self.transient(mestre)
        self.grab_set()

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(
            corpo, text="Nome da pasta", anchor="w", text_color=cor_secundaria(),
            font=ctk.CTkFont(family=FONTE, size=12),
        ).pack(fill="x", pady=(0, 4))
        self.campo_nome = campo(corpo)
        self.campo_nome.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            corpo, text="Extensões (separadas por vírgula, sem ponto)", anchor="w",
            text_color=cor_secundaria(), font=ctk.CTkFont(family=FONTE, size=12),
        ).pack(fill="x", pady=(0, 4))
        self.campo_extensoes = campo(corpo)
        self.campo_extensoes.pack(fill="x", pady=(0, 20))

        if nome_atual:
            self.campo_nome.insert(0, nome_atual)
            self.campo_extensoes.insert(0, ", ".join(extensoes_atuais))

        botoes = ctk.CTkFrame(corpo, fg_color="transparent")
        botoes.pack(fill="x")
        botao_secundario(botoes, text="Cancelar", command=self.destroy).pack(side="right")
        botao_primario(botoes, text="Salvar", command=self._salvar).pack(side="right", padx=(0, 8))

        corrigir_janela_windows(self)
        self.withdraw()
        self.after(10, self.deiconify)

    def _salvar(self):
        nome = self.campo_nome.get().strip()
        if not nome:
            messagebox.showwarning("Campo obrigatório", "Dê um nome à pasta.", parent=self)
            return
        extensoes = [e.strip().lower().lstrip(".") for e in self.campo_extensoes.get().split(",") if e.strip()]
        if not extensoes:
            messagebox.showwarning("Campo obrigatório", "Informe ao menos uma extensão.", parent=self)
            return
        self.ao_salvar(self.nome_original, nome, extensoes)
        self.destroy()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FileSense")
        self.geometry("760x520")
        self.minsize(680, 460)
        self._aplicar_icone()
        corrigir_janela_windows(self)

        self.cfg: Config = carregar_config()
        self.historico = Historico()
        self.pasta_var = ctk.StringVar(value=str(pasta_downloads()))
        self.intervalo_var = ctk.StringVar(value="10")
        self.vigiar_ativo = False
        self._parar_vigia = False
        self.indice_categoria_selecionada = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._montar_barra_lateral()
        self.paginas = {}
        self._montar_pagina_organizar()
        self._montar_pagina_categorias()
        self._montar_pagina_configuracoes()
        self._montar_pagina_historico()
        self._mostrar_pagina("organizar")

        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

    def _aplicar_icone(self):
        try:
            self.iconbitmap(caminho_recurso("icon.ico"))
        except tk.TclError:
            pass

    def _ao_fechar(self):
        self._parar_vigia = True
        self.destroy()

    # --- navegação ---

    def _montar_barra_lateral(self):
        barra = ctk.CTkFrame(self, width=170, corner_radius=0, fg_color=("gray92", "gray14"))
        barra.grid(row=0, column=0, sticky="nsw")
        barra.grid_propagate(False)

        ctk.CTkLabel(
            barra, text="FileSense", font=ctk.CTkFont(family=FONTE, size=17, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(24, 30))

        self.botoes_nav = {}
        for chave, rotulo in [
            ("organizar", "Organizar"),
            ("categorias", "Categorias"),
            ("configuracoes", "Configurações"),
            ("historico", "Histórico"),
        ]:
            botao = ctk.CTkButton(
                barra, text=rotulo, anchor="w", fg_color="transparent", text_color=("gray20", "gray85"),
                hover_color=cor_divisor(), corner_radius=RAIO, height=38,
                font=ctk.CTkFont(family=FONTE, size=13),
                command=lambda c=chave: self._mostrar_pagina(c),
            )
            botao.pack(fill="x", padx=12, pady=2)
            self.botoes_nav[chave] = botao

    def _mostrar_pagina(self, chave: str):
        for nome in self.paginas:
            self.botoes_nav[nome].configure(
                fg_color=ACCENT if nome == chave else "transparent",
                text_color="white" if nome == chave else ("gray20", "gray85"),
            )
        self.paginas[chave].tkraise()
        if chave == "categorias":
            self._atualizar_tabela_categorias()
        elif chave == "historico":
            self._atualizar_lista_historico()

    # --- página: organizar ---

    def _montar_pagina_organizar(self):
        pagina = ctk.CTkFrame(self, fg_color="transparent")
        pagina.grid(row=0, column=1, sticky="nsew")
        self.paginas["organizar"] = pagina

        ctk.CTkLabel(
            pagina, text="Organizar", font=ctk.CTkFont(family=FONTE, size=19, weight="bold"), anchor="w",
        ).pack(fill="x", padx=PAD, pady=(26, 16))

        linha_pasta = ctk.CTkFrame(pagina, fg_color="transparent")
        linha_pasta.pack(fill="x", padx=PAD)
        campo(linha_pasta, textvariable=self.pasta_var).pack(side="left", fill="x", expand=True)
        botao_secundario(linha_pasta, text="Procurar...", width=110, command=self._escolher_pasta).pack(
            side="left", padx=(8, 0)
        )

        linha_botoes = ctk.CTkFrame(pagina, fg_color="transparent")
        linha_botoes.pack(fill="x", padx=PAD, pady=(14, 0))
        self.botao_testar = botao_secundario(
            linha_botoes, text="Testar (simulação)", width=170, command=lambda: self._organizar(aplicar=False)
        )
        self.botao_testar.pack(side="left")
        self.botao_organizar = botao_primario(
            linha_botoes, text="Organizar agora", width=170, command=lambda: self._organizar(aplicar=True)
        )
        self.botao_organizar.pack(side="left", padx=(10, 0))

        cartao_vigia = ctk.CTkFrame(pagina, fg_color=("gray95", "gray17"), corner_radius=RAIO)
        cartao_vigia.pack(fill="x", padx=PAD, pady=(20, 0))
        interior = ctk.CTkFrame(cartao_vigia, fg_color="transparent")
        interior.pack(fill="x", padx=18, pady=16)

        topo_vigia = ctk.CTkFrame(interior, fg_color="transparent")
        topo_vigia.pack(fill="x")
        self.switch_vigiar = ctk.CTkSwitch(
            topo_vigia, text="Vigiar automaticamente", progress_color=ACCENT,
            font=ctk.CTkFont(family=FONTE, size=13), command=self._alternar_vigia,
        )
        self.switch_vigiar.pack(side="left")
        ctk.CTkLabel(topo_vigia, text="a cada", text_color=cor_secundaria()).pack(side="left", padx=(20, 6))
        campo(topo_vigia, textvariable=self.intervalo_var, width=60).pack(side="left")
        ctk.CTkLabel(topo_vigia, text="segundos", text_color=cor_secundaria()).pack(side="left", padx=(6, 0))

        self.rotulo_vigia = ctk.CTkLabel(
            interior, text="Desligado — organiza só quando você clicar em \"Organizar agora\".",
            text_color=cor_secundaria(), anchor="w", font=ctk.CTkFont(family=FONTE, size=12),
        )
        self.rotulo_vigia.pack(fill="x", pady=(8, 0))

        ctk.CTkLabel(
            pagina, text="Resultado", font=ctk.CTkFont(family=FONTE, size=14, weight="bold"), anchor="w",
        ).pack(fill="x", padx=PAD, pady=(20, 8))
        self.log = ctk.CTkTextbox(
            pagina, fg_color="transparent", border_width=1, border_color=cor_divisor(), corner_radius=RAIO,
            font=ctk.CTkFont(family=FONTE, size=13),
        )
        self.log.pack(fill="both", expand=True, padx=PAD, pady=(0, 24))
        self.log.insert("1.0", 'Nenhuma execução ainda. Clique em "Testar" ou "Organizar agora".')

    def _escolher_pasta(self):
        escolha = filedialog.askdirectory(title="Selecione a pasta a organizar")
        if escolha:
            self.pasta_var.set(escolha)

    def _organizar(self, aplicar: bool):
        pasta = Path(self.pasta_var.get()).expanduser()
        if not pasta.is_dir():
            messagebox.showwarning("Pasta inválida", "Escolha uma pasta que existe.")
            return

        self.botao_testar.configure(state="disabled", text="Testando..." if not aplicar else "Testar (simulação)")
        self.botao_organizar.configure(
            state="disabled", text="Organizando..." if aplicar else "Organizar agora"
        )
        self.log.delete("1.0", "end")
        self.log.insert("end", "Analisando...\n")

        threading.Thread(target=self._executar_organizacao, args=(pasta, aplicar), daemon=True).start()

    def _executar_organizacao(self, pasta: Path, aplicar: bool):
        try:
            movimentos = planejar(pasta, self.cfg)
            erros = []
            if aplicar and movimentos:
                feitos, erros = executar(movimentos, pasta, self.historico)
                movimentos = feitos
        except Exception as erro:
            self.after(0, lambda: self._mostrar_erro_organizar(erro))
            return
        self.after(0, lambda: self._mostrar_resultado_organizar(movimentos, erros, aplicar))

    def _restaurar_botoes_organizar(self):
        self.botao_testar.configure(state="normal", text="Testar (simulação)")
        self.botao_organizar.configure(state="normal", text="Organizar agora")

    def _mostrar_erro_organizar(self, erro: Exception):
        self._restaurar_botoes_organizar()
        messagebox.showerror("Erro", str(erro))

    def _mostrar_resultado_organizar(self, movimentos, erros, aplicar: bool):
        self._restaurar_botoes_organizar()

        self.log.delete("1.0", "end")
        if not movimentos:
            self.log.insert("end", "Nada pra organizar — a pasta já está em ordem.")
        else:
            por_categoria: dict[str, int] = {}
            for m in movimentos:
                por_categoria[m.categoria] = por_categoria.get(m.categoria, 0) + 1
            verbo = "Movido" if aplicar else "Iria mover"
            for categoria, qtd in sorted(por_categoria.items()):
                self.log.insert("end", f"{categoria}: {qtd} arquivo(s)\n")
            self.log.insert("end", f"\n{verbo} {len(movimentos)} arquivo(s) no total.\n")
            for m, erro in erros:
                self.log.insert("end", f"⚠ {m.origem.name}: {erro}\n")

        titulo = "Organizado" if aplicar else "Simulação concluída"
        messagebox.showinfo(titulo, f"{len(movimentos)} arquivo(s) {'movidos' if aplicar else 'seriam movidos'}.")

    def _alternar_vigia(self):
        if self.switch_vigiar.get():
            pasta = Path(self.pasta_var.get()).expanduser()
            if not pasta.is_dir():
                messagebox.showwarning("Pasta inválida", "Escolha uma pasta que existe.")
                self.switch_vigiar.deselect()
                return
            try:
                intervalo = float(self.intervalo_var.get())
            except ValueError:
                messagebox.showwarning("Valor inválido", "O intervalo precisa ser um número.")
                self.switch_vigiar.deselect()
                return

            self._parar_vigia = False
            self.rotulo_vigia.configure(
                text=f"Vigiando {pasta} a cada {intervalo:g}s.", text_color=ACCENT
            )
            threading.Thread(target=self._loop_vigia, args=(pasta, intervalo), daemon=True).start()
        else:
            self._parar_vigia = True
            self.rotulo_vigia.configure(
                text="Desligando... (para no próximo ciclo)", text_color=cor_secundaria()
            )

    def _loop_vigia(self, pasta: Path, intervalo: float):
        vigiar(
            pasta, self.cfg, self.historico, intervalo=intervalo,
            ao_mover=lambda feitos, erros: self.after(0, lambda: self._registrar_vigia(feitos)),
            parar=lambda: self._parar_vigia,
        )
        self.after(0, self._vigia_parada)

    def _registrar_vigia(self, feitos):
        if not feitos:
            return
        self.log.insert("end", f"[vigia] {len(feitos)} arquivo(s) organizados automaticamente\n")

    def _vigia_parada(self):
        self.rotulo_vigia.configure(
            text='Desligado — organiza só quando você clicar em "Organizar agora".',
            text_color=cor_secundaria(),
        )

    # --- página: categorias ---

    def _montar_pagina_categorias(self):
        pagina = ctk.CTkFrame(self, fg_color="transparent")
        pagina.grid(row=0, column=1, sticky="nsew")
        self.paginas["categorias"] = pagina

        cabecalho = ctk.CTkFrame(pagina, fg_color="transparent")
        cabecalho.pack(fill="x", padx=PAD, pady=(26, 6))
        ctk.CTkLabel(
            cabecalho, text="Categorias", font=ctk.CTkFont(family=FONTE, size=19, weight="bold"), anchor="w",
        ).pack(side="left")
        botao_secundario(cabecalho, text="Remover", width=84, command=self._remover_categoria).pack(side="right")
        botao_secundario(cabecalho, text="Editar", width=76, command=self._editar_categoria).pack(
            side="right", padx=6
        )
        botao_secundario(cabecalho, text="+ Nova categoria", width=130, command=self._nova_categoria).pack(
            side="right"
        )
        ctk.CTkLabel(
            pagina, text="Cada categoria vira uma subpasta. Uma extensão só pode estar em uma categoria.",
            text_color=cor_secundaria(), anchor="w", font=ctk.CTkFont(family=FONTE, size=12),
        ).pack(fill="x", padx=PAD, pady=(0, 16))

        self.tabela_categorias = ttk.Treeview(
            pagina, columns=("nome", "extensoes"), show="headings", height=12
        )
        self.tabela_categorias.heading("nome", text="Pasta")
        self.tabela_categorias.column("nome", width=180, anchor="w", stretch=False)
        self.tabela_categorias.heading("extensoes", text="Extensões")
        self.tabela_categorias.column("extensoes", width=400, anchor="w", stretch=True)
        self.tabela_categorias.pack(fill="both", expand=True, padx=PAD, pady=(0, 24))
        self.tabela_categorias.bind("<<TreeviewSelect>>", self._selecionar_categoria)

    def _estilizar_tabelas(self):
        escuro = ctk.get_appearance_mode() == "Dark"
        fundo = "#242424" if escuro else "#FFFFFF"
        self.fundo_linha_alt = "#2A2A2A" if escuro else "#F7F7F7"
        fundo_cabecalho = "#2B2B2B" if escuro else "#F5F5F5"
        texto = "#DCE4EE" if escuro else "#1A1A1A"

        estilo = ttk.Style(self)
        estilo.theme_use("clam")
        estilo.configure(
            "Treeview", background=fundo, fieldbackground=fundo, foreground=texto,
            rowheight=30, borderwidth=0, font=(FONTE, 10),
        )
        estilo.configure(
            "Treeview.Heading", background=fundo_cabecalho, foreground=cor_secundaria(),
            borderwidth=0, font=(FONTE, 10, "bold"), padding=(0, 8),
        )
        estilo.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#FFFFFF")])
        estilo.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    def _atualizar_tabela_categorias(self):
        self.tabela_categorias.delete(*self.tabela_categorias.get_children())
        self.tabela_categorias.tag_configure("linha_alt", background=self.fundo_linha_alt)
        for i, (nome, extensoes) in enumerate(self.cfg.categorias.items()):
            self.tabela_categorias.insert(
                "", "end", values=(nome, ", ".join(extensoes)),
                tags=("linha_alt",) if i % 2 == 1 else (),
            )

    def _selecionar_categoria(self, _evento):
        selecao = self.tabela_categorias.selection()
        self.indice_categoria_selecionada = self.tabela_categorias.index(selecao[0]) if selecao else None

    def _nova_categoria(self):
        def salvar(_original, nome, extensoes):
            self.cfg.categorias[nome] = extensoes
            self._persistir_config()
            self._atualizar_tabela_categorias()

        JanelaCategoria(self, None, [], salvar)

    def _editar_categoria(self):
        if self.indice_categoria_selecionada is None:
            messagebox.showinfo("Selecione uma categoria", "Clique em uma categoria na tabela primeiro.")
            return
        nome_atual = list(self.cfg.categorias.keys())[self.indice_categoria_selecionada]

        def salvar(original, nome, extensoes):
            if original in self.cfg.categorias and original != nome:
                del self.cfg.categorias[original]
            self.cfg.categorias[nome] = extensoes
            self._persistir_config()
            self._atualizar_tabela_categorias()

        JanelaCategoria(self, nome_atual, self.cfg.categorias[nome_atual], salvar)

    def _remover_categoria(self):
        if self.indice_categoria_selecionada is None:
            messagebox.showinfo("Selecione uma categoria", "Clique em uma categoria na tabela primeiro.")
            return
        nome_atual = list(self.cfg.categorias.keys())[self.indice_categoria_selecionada]
        if messagebox.askyesno("Remover categoria", f'Remover "{nome_atual}"? As extensões dela vão para "Outros".'):
            del self.cfg.categorias[nome_atual]
            self._persistir_config()
            self._atualizar_tabela_categorias()

    def _persistir_config(self):
        salvar_config(self.cfg, caminho_padrao())

    # --- página: configurações ---

    def _montar_pagina_configuracoes(self):
        pagina = ctk.CTkFrame(self, fg_color="transparent")
        pagina.grid(row=0, column=1, sticky="nsew")
        self.paginas["configuracoes"] = pagina

        ctk.CTkLabel(
            pagina, text="Configurações", font=ctk.CTkFont(family=FONTE, size=19, weight="bold"), anchor="w",
        ).pack(fill="x", padx=PAD, pady=(26, 20))

        corpo = ctk.CTkFrame(pagina, fg_color="transparent")
        corpo.pack(fill="x", padx=PAD)

        self.var_por_data = ctk.BooleanVar(value=self.cfg.por_data)
        ctk.CTkSwitch(
            corpo, text="Criar subpastas por ano-mês (ex.: Imagens/2026-09)", progress_color=ACCENT,
            variable=self.var_por_data, font=ctk.CTkFont(family=FONTE, size=13),
            command=lambda: self._mudar_config("por_data", self.var_por_data.get()),
        ).pack(anchor="w", pady=(0, 20))

        ctk.CTkLabel(
            corpo, text="Nome da pasta para tipos não reconhecidos", text_color=cor_secundaria(),
            font=ctk.CTkFont(family=FONTE, size=12),
        ).pack(fill="x", pady=(0, 4))
        c1 = campo(corpo, width=240)
        c1.insert(0, self.cfg.pasta_outros)
        c1.bind("<FocusOut>", lambda e: self._mudar_config("pasta_outros", c1.get()))
        c1.pack(anchor="w", pady=(0, 16))

        ctk.CTkLabel(
            corpo, text="Nome da pasta para arquivos suspeitos", text_color=cor_secundaria(),
            font=ctk.CTkFont(family=FONTE, size=12),
        ).pack(fill="x", pady=(0, 4))
        c2 = campo(corpo, width=240)
        c2.insert(0, self.cfg.pasta_suspeitos)
        c2.bind("<FocusOut>", lambda e: self._mudar_config("pasta_suspeitos", c2.get()))
        c2.pack(anchor="w", pady=(0, 16))

        ctk.CTkLabel(
            corpo, text="Nome da pasta para duplicados", text_color=cor_secundaria(),
            font=ctk.CTkFont(family=FONTE, size=12),
        ).pack(fill="x", pady=(0, 4))
        c3 = campo(corpo, width=240)
        c3.insert(0, self.cfg.pasta_duplicados)
        c3.bind("<FocusOut>", lambda e: self._mudar_config("pasta_duplicados", c3.get()))
        c3.pack(anchor="w", pady=(0, 16))

        ctk.CTkLabel(
            pagina, text=f"Configuração salva em: {caminho_padrao()}", text_color=cor_secundaria(),
            font=ctk.CTkFont(family=FONTE, size=11),
        ).pack(anchor="w", padx=PAD, pady=(20, 0))

    def _mudar_config(self, chave: str, valor):
        setattr(self.cfg, chave, valor)
        self._persistir_config()

    # --- página: histórico ---

    def _montar_pagina_historico(self):
        pagina = ctk.CTkFrame(self, fg_color="transparent")
        pagina.grid(row=0, column=1, sticky="nsew")
        self.paginas["historico"] = pagina

        cabecalho = ctk.CTkFrame(pagina, fg_color="transparent")
        cabecalho.pack(fill="x", padx=PAD, pady=(26, 16))
        ctk.CTkLabel(
            cabecalho, text="Histórico", font=ctk.CTkFont(family=FONTE, size=19, weight="bold"), anchor="w",
        ).pack(side="left")
        botao_secundario(cabecalho, text="Desfazer última ação", width=170, command=self._desfazer).pack(
            side="right"
        )

        self.tabela_historico = ttk.Treeview(
            pagina, columns=("quando", "acao", "pasta", "qtd"), show="headings", height=12
        )
        for col, titulo, largura in [
            ("quando", "Quando", 160), ("acao", "Ação", 100), ("pasta", "Pasta", 320), ("qtd", "Arquivos", 90),
        ]:
            self.tabela_historico.heading(col, text=titulo)
            self.tabela_historico.column(col, width=largura, anchor="w", stretch=(col == "pasta"))
        self.tabela_historico.pack(fill="both", expand=True, padx=PAD, pady=(0, 24))

    def _atualizar_lista_historico(self):
        self.tabela_historico.delete(*self.tabela_historico.get_children())
        self.tabela_historico.tag_configure("linha_alt", background=self.fundo_linha_alt)
        for i, lote in enumerate(reversed(self.historico.lotes())):
            self.tabela_historico.insert(
                "", "end",
                values=(
                    lote["quando"].replace("T", " "), lote["acao"], lote["pasta"], len(lote["movimentos"]),
                ),
                tags=("linha_alt",) if i % 2 == 1 else (),
            )

    def _desfazer(self):
        lote, restaurados, problemas = self.historico.desfazer_ultimo()
        if lote is None:
            messagebox.showinfo("Nada a desfazer", "Não há nenhuma ação registrada ainda.")
            return
        self._atualizar_lista_historico()
        mensagem = f"{restaurados} arquivo(s) restaurado(s)."
        if problemas:
            mensagem += "\n\nAvisos:\n" + "\n".join(f"- {p}" for p in problemas)
        messagebox.showinfo("Desfeito", mensagem)


if __name__ == "__main__":
    app = App()
    app._estilizar_tabelas()
    app._atualizar_tabela_categorias()
    app.mainloop()
