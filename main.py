#!/usr/bin/env python3
"""
Renomeia relatórios escaneados (Agente Popular de Segurança Alimentar)
para "<Nome do Agente>.pdf", lendo o campo "NOME DO AGENTE:" da 1ª página via OCR.

Dependências:
    pip install pymupdf pytesseract pillow
    + Tesseract instalado, com o idioma português (por):
        Linux:   sudo apt install tesseract-ocr tesseract-ocr-por
        Windows: https://github.com/UB-Mannheim/tesseract/wiki  (marcar "Portuguese")

Uso:
    python renomear_por_agente.py arquivo.pdf
    python renomear_por_agente.py pasta_com_pdfs
    python renomear_por_agente.py pasta --dry-run     # só mostra, não renomeia
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf  # PyMuPDF
import pytesseract
from PIL import Image, ImageOps

# Windows: descomente e ajuste se o tesseract não estiver no PATH
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

PALAVRAS_MINUSCULAS = {"da", "de", "do", "das", "dos", "e"}


def renderizar_pagina(pdf_path: Path, pagina: int = 0, dpi: int = 300) -> Image.Image:
    with pymupdf.open(pdf_path) as doc:
        pix = doc[pagina].get_pixmap(dpi=dpi)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def ocr_topo_da_pagina(img: Image.Image) -> str:
    # O cabeçalho com o nome fica na metade superior da página
    w, h = img.size
    topo = img.crop((0, 0, w, int(h * 0.5)))
    topo = ImageOps.autocontrast(ImageOps.grayscale(topo))
    return pytesseract.image_to_string(topo, lang="por", config="--psm 6")


def extrair_nome(texto: str) -> str | None:
    # 1. Tenta encontrar o padrão do recibo: "EU, [NOME], AGENTE POPULAR..."
    match_recibo = re.search(r"EU,\s*(.*?),\s*AGENTE\s+POPULAR", texto, re.IGNORECASE)
    if match_recibo:
        nome = match_recibo.group(1).strip()
        return nome

    # 2. Tenta o padrão original do formulário: "NOME DO AGENTE: [NOME]"
    match_form = re.search(r"NOME\s+DO\s+A?GENTE\s*[:;.]?", texto, re.IGNORECASE)
    if match_form:
        trecho = texto[match_form.end(): match_form.end() + 250]
        trecho = re.sub(r"\bCPF\b\s*[:;]?", " ", trecho, flags=re.IGNORECASE)

        for linha in trecho.splitlines():
            linha = re.split(r"\d|USPR|LOTE", linha, flags=re.IGNORECASE)[0]
            linha = re.sub(r"[^A-Za-zÀ-ÿ\s'-]", " ", linha)
            palavras = linha.split()
            if len(palavras) >= 2:
                return " ".join(palavras)
                
    return None


def formatar_nome(nome: str) -> str:
    partes = []
    for i, p in enumerate(nome.lower().split()):
        partes.append(p if (p in PALAVRAS_MINUSCULAS and i > 0) else p.capitalize())
    return " ".join(partes)


def nome_de_arquivo_seguro(nome: str) -> str:
    nome = unicodedata.normalize("NFC", nome)
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", nome).strip()


def destino_unico(pasta: Path, base: str) -> Path:
    destino = pasta / f"{base}.pdf"
    n = 2
    while destino.exists():
        destino = pasta / f"{base}_{n}.pdf"
        n += 1
    return destino


def processar(pdf: Path, dry_run: bool) -> None:
    try:
        texto = ocr_topo_da_pagina(renderizar_pagina(pdf))
        nome = extrair_nome(texto)
    except Exception as e:
        print(f"[ERRO] {pdf.name}: {e}")
        return

    if not nome:
        print(f"[AVISO] {pdf.name}: nome do agente não encontrado (não renomeado)")
        return

    base = nome_de_arquivo_seguro(formatar_nome(nome))
    if pdf.stem == base:
        print(f"[OK] {pdf.name}: já está com o nome correto")
        return

    destino = destino_unico(pdf.parent, base)
    print(f"[{'SIMULAÇÃO' if dry_run else 'OK'}] {pdf.name} -> {destino.name}")
    if not dry_run:
        pdf.rename(destino)


def main() -> None:
    ap = argparse.ArgumentParser(description="Renomeia PDFs pelo nome do agente")
    ap.add_argument("caminho", type=Path, help="PDF ou pasta com PDFs")
    ap.add_argument("--dry-run", action="store_true", help="não renomeia, só mostra")
    args = ap.parse_args()

    if args.caminho.is_dir():
        pdfs = sorted(args.caminho.glob("*.pdf"))
    elif args.caminho.is_file():
        pdfs = [args.caminho]
    else:
        sys.exit(f"Caminho não encontrado: {args.caminho}")

    if not pdfs:
        sys.exit("Nenhum PDF encontrado.")

    for pdf in pdfs:
        processar(pdf, args.dry_run)


if __name__ == "__main__":
    main()