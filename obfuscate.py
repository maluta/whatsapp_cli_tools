#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Ofusca números de telefone em arquivos Markdown.

Por padrão, processa o diretório `resumos` e substitui números
no formato brasileiro com DDI +55 e DDD, preservando DDI, DDD e os
quatro dígitos finais. Ex.: `+55 21 97092-4781` → `+55 21 🫣-4781`.

Filosofia UNIX:
- Suporta stdin (use `-` em `--path` ou pipe)
- Saída em stdout quando processa stdin ou arquivo único sem `--in_place`
- Silencioso por padrão; mensagens de erro vão para stderr
"""

from __future__ import annotations

import argparse
import sys
import re
from pathlib import Path


BR_PHONE_PATTERN = re.compile(
    r"(?P<prefix>\+55\s*\(?\s*\d{2}\s*\)?\s*)(?P<mid>\d{4,5})(?P<tail>-\d{4})"
)


def ofuscar_telefones_br(texto: str) -> str:
    """Ofusca telefones brasileiros no formato `+55 DD XXXXX-XXXX`.

    Mantém o DDI (+55), DDD (2 dígitos) e os últimos 4 dígitos,
    substituindo o bloco do meio por "🫣".

    Exemplos:
    - "+55 21 97092-4781" → "+55 21 🫣-4781"
    - "+55 (11) 3456-7890" → "+55 (11) 🫣-7890"

    Parâmetros:
        texto: conteúdo de entrada.

    Retorna:
        Conteúdo com telefones ofuscados.
    """

    def _sub(m: re.Match) -> str:
        return f"{m.group('prefix')}🫣{m.group('tail')}"

    return BR_PHONE_PATTERN.sub(_sub, texto)


def processar_arquivo(caminho: Path, in_place: bool) -> int:
    """Processa um único arquivo.

    Se `in_place` for True, sobrescreve o arquivo quando houver alterações.
    Caso contrário, imprime o resultado em stdout.

    Retorna:
        0 em sucesso, 2 se o arquivo não existir.
    """
    if not caminho.exists():
        print(f"Erro: arquivo não encontrado: {caminho}", file=sys.stderr)
        return 2

    texto = caminho.read_text(encoding="utf-8")
    novo = ofuscar_telefones_br(texto)

    if in_place:
        if novo != texto:
            caminho.write_text(novo, encoding="utf-8")
        return 0

    # Saída para stdout quando não é in-place
    sys.stdout.write(novo)
    return 0


def processar_diretorio(raiz: Path, in_place: bool) -> int:
    """Processa todos os arquivos `.md` de um diretório (recursivo).

    Por segurança/clareza, diretórios exigem `--in_place`.

    Retorna 0 em sucesso, 1 em erro de uso, 2 se diretório não existir.
    """
    if not raiz.exists():
        print(f"Erro: diretório não encontrado: {raiz}", file=sys.stderr)
        return 2

    if not raiz.is_dir():
        print("Erro: caminho não é diretório. Use caminho de arquivo ou '-' para stdin.", file=sys.stderr)
        return 1

    if not in_place:
        print("Erro: para diretórios, use --in_place para editar arquivos no local.", file=sys.stderr)
        return 1

    for caminho in raiz.rglob("*.md"):
        try:
            texto = caminho.read_text(encoding="utf-8")
            novo = ofuscar_telefones_br(texto)
            if novo != texto:
                caminho.write_text(novo, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"Erro ao processar {caminho}: {exc}", file=sys.stderr)
            return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--path",
        "-p",
        default="resumos",
        help="Caminho de arquivo ou diretório a processar, ou '-' para stdin (default: resumos)",
    )
    parser.add_argument(
        "--in_place",
        action="store_true",
        help="Edita arquivos no local (obrigatório para diretórios)",
    )
    args = parser.parse_args()

    # Modo stdin
    if args.path == "-":
        if sys.stdin.isatty():
            print("Erro: nenhuma entrada via stdin", file=sys.stderr)
            return 1
        conteudo = sys.stdin.read()
        sys.stdout.write(ofuscar_telefones_br(conteudo))
        return 0

    caminho = Path(args.path)

    if caminho.is_dir():
        return processar_diretorio(caminho, args.in_place)
    elif caminho.is_file():
        return processar_arquivo(caminho, args.in_place)
    else:
        print(f"Erro: caminho não encontrado: {caminho}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

