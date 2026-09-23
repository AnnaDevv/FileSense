"""Gera o ícone do app (rodar uma vez; não é dependência do FileSense em si)."""
from PIL import Image, ImageDraw

TAMANHO = 256
ACCENT = "#0E9F87"

img = Image.new("RGBA", (TAMANHO, TAMANHO), (0, 0, 0, 0))
desenho = ImageDraw.Draw(img)

margem = 8
desenho.rounded_rectangle(
    [margem, margem, TAMANHO - margem, TAMANHO - margem], radius=56, fill=ACCENT
)

# pasta simples em branco
esq, topo, dir_, baixo = 58, 92, TAMANHO - 58, TAMANHO - 70
aba_altura = 18
desenho.polygon(
    [(esq, topo + aba_altura), (esq, topo), (esq + 50, topo), (esq + 66, topo + aba_altura)],
    fill="white",
)
desenho.rounded_rectangle([esq, topo + aba_altura, dir_, baixo], radius=10, fill="white")

caminho = "icon.ico"
img.save(caminho, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
print("Ícone salvo em", caminho)
