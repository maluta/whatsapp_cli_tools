#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Gera estatísticas de conversas do WhatsApp.

Lê mensagens de stdin e produz estatísticas como:
- Contagem de mensagens por participante
- Horários mais ativos
- Palavras mais frequentes
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime


def parse_messages(text: str) -> list[dict]:
    """Extrai mensagens do formato WhatsApp.

    Formatos suportados:
    - BR: DD/MM/YYYY H:MM da madrugada/manhã/tarde/noite - Autor: Mensagem
    - Internacional: DD/MM/YYYY HH:MM - Autor: Mensagem
    """
    # Padrão flexível para formatos brasileiro e internacional
    pattern = r"(\d{2}/\d{2}/\d{4}) (\d{1,2}):(\d{2})(?:\sda\s(madrugada|manhã|tarde|noite))? - ([^:]+): (.+)"
    messages = []

    # Mapeamento de período para offset de hora (formato 24h)
    period_offset = {
        'madrugada': 0,   # 00:00 - 05:59
        'manhã': 0,       # 06:00 - 11:59
        'tarde': 12,      # 12:00 - 17:59 (mas 12:xx não soma 12)
        'noite': 12,      # 18:00 - 23:59
        None: 0           # formato internacional (já em 24h)
    }

    for line in text.split('\n'):
        match = re.match(pattern, line)
        if match:
            date_str, hour_str, minute_str, period, author, content = match.groups()
            hour = int(hour_str)

            # Converte para formato 24h
            if period in ('tarde', 'noite') and hour != 12:
                hour += 12
            elif period == 'madrugada' and hour == 12:
                hour = 0

            messages.append({
                'date': date_str,
                'time': f"{hour:02d}:{minute_str}",
                'hour': hour,
                'author': author.strip(),
                'content': content.strip()
            })

    return messages


def count_by_author(messages: list[dict]) -> dict[str, int]:
    """Conta mensagens por autor."""
    return dict(Counter(m['author'] for m in messages))


def count_by_hour(messages: list[dict]) -> dict[int, int]:
    """Conta mensagens por hora do dia."""
    counts = Counter(m['hour'] for m in messages)
    return {k: counts[k] for k in sorted(counts.keys())}


def top_words(messages: list[dict], n: int = 20) -> list[tuple[str, int]]:
    """Encontra as N palavras mais frequentes (excluindo stopwords)."""
    stopwords = {
        'de', 'a', 'o', 'que', 'e', 'do', 'da', 'em', 'um', 'para',
        'é', 'com', 'não', 'uma', 'os', 'no', 'se', 'na', 'por', 'mais',
        'as', 'dos', 'como', 'mas', 'foi', 'ao', 'ele', 'das', 'tem', 'à',
        'seu', 'sua', 'ou', 'ser', 'quando', 'muito', 'há', 'nos', 'já',
        'está', 'eu', 'também', 'só', 'pelo', 'pela', 'até', 'isso',
        'ela', 'entre', 'era', 'depois', 'sem', 'mesmo', 'aos', 'ter',
        'seus', 'quem', 'nas', 'me', 'esse', 'eles', 'estão', 'você',
        'tinha', 'foram', 'essa', 'num', 'nem', 'suas', 'meu', 'às',
        'minha', 'têm', 'numa', 'pelos', 'elas', 'havia', 'seja', 'qual',
        'será', 'nós', 'tenho', 'lhe', 'deles', 'essas', 'esses', 'pelas',
        'este', 'fosse', 'dele', 'tu', 'te', 'vocês', 'vos', 'lhes',
        'meus', 'minhas', 'teu', 'tua', 'teus', 'tuas', 'nosso', 'nossa',
        'nossos', 'nossas', 'dela', 'delas', 'esta', 'estes', 'estas',
        'aquele', 'aquela', 'aqueles', 'aquelas', 'isto', 'aquilo',
        'estou', 'está', 'estamos', 'estão', 'estive', 'esteve',
        'pra', 'pro', 'tb', 'tbm', 'vc', 'q', 'n', 'to', 'ta', 'tá',
        # Mensagens de mídia
        'imagem', 'ocultada', 'figurinha', 'omitida', 'áudio', 'vídeo'
    }

    words = []
    for m in messages:
        content = m['content'].lower()
        # Remove URLs e menções
        content = re.sub(r'https?://\S+', '', content)
        content = re.sub(r'@\S+', '', content)
        # Extrai palavras
        words.extend(re.findall(r'\b[a-záàâãéèêíïóôõöúçñ]{3,}\b', content))

    filtered = [w for w in words if w not in stopwords]
    return Counter(filtered).most_common(n)


def format_output(stats: dict, fmt: str) -> str:
    """Formata estatísticas no formato escolhido."""
    if fmt == 'json':
        return json.dumps(stats, ensure_ascii=False, indent=2)

    # Formato texto
    lines = []
    lines.append("=== Estatísticas do WhatsApp ===\n")

    lines.append(f"Total de mensagens: {stats['total_messages']}")
    lines.append(f"Participantes: {stats['total_participants']}\n")

    lines.append("--- Mensagens por Participante ---")
    for author, count in sorted(stats['by_author'].items(), key=lambda x: -x[1]):
        pct = (count / stats['total_messages']) * 100
        lines.append(f"  {author}: {count} ({pct:.1f}%)")

    lines.append("\n--- Horários Mais Ativos ---")
    for hour, count in sorted(stats['by_hour'].items(), key=lambda x: -x[1])[:5]:
        lines.append(f"  {hour:02d}:00 - {count} mensagens")

    lines.append("\n--- Palavras Mais Frequentes ---")
    for word, count in stats['top_words']:
        lines.append(f"  {word}: {count}")

    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--format', '-f',
        choices=['text', 'json'],
        default='text',
        help='Formato de saída (default: text)'
    )
    parser.add_argument(
        '--top-words', '-n',
        type=int,
        default=20,
        help='Número de palavras mais frequentes (default: 20)'
    )
    args = parser.parse_args()

    # Lê stdin
    if sys.stdin.isatty():
        print("Erro: nenhuma entrada. Use: segment_messages.py ... | stats.py", file=sys.stderr)
        return 1

    text = sys.stdin.read()
    if not text.strip():
        print("Erro: entrada vazia", file=sys.stderr)
        return 1

    messages = parse_messages(text)
    if not messages:
        print("Erro: nenhuma mensagem encontrada no formato esperado", file=sys.stderr)
        return 1

    stats = {
        'total_messages': len(messages),
        'total_participants': len(set(m['author'] for m in messages)),
        'by_author': count_by_author(messages),
        'by_hour': count_by_hour(messages),
        'top_words': top_words(messages, args.top_words)
    }

    print(format_output(stats, args.format))
    return 0


if __name__ == "__main__":
    sys.exit(main())
