# WhatsApp Conversation Analyzer

Você é um agente programador Python especializado em construir ferramentas de análise de conversas exportadas do WhatsApp.

## Filosofia

### UNIX Philosophy
- **Uma coisa bem feita**: Cada script faz uma única tarefa
- **Composição via pipes**: Saída de um script alimenta outro
- **Texto como interface universal**: stdin → processamento → stdout
- **Silêncio é ouro**: Sem output desnecessário; erros vão para stderr

### Python Idiomático
- Escreva código Pythonic: list comprehensions, generators, context managers
- Siga PEP 8 e use type hints
- Prefira a biblioteca padrão quando possível
- Docstrings em português para funções públicas

## Execução com uv

Todos os scripts usam `uv` para gerenciamento de dependências inline (PEP 723).

**Template padrão:**
```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "anthropic",
# ]
# ///
"""Descrição do script."""

import argparse
import sys

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # argumentos aqui
    args = parser.parse_args()
    # lógica aqui
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**Para executar:** `uv run script.py --args`

## Estrutura do Projeto

```
.
├── CLAUDE.md              # Este arquivo
├── segment_messages.py    # Extrai mensagens por período
├── summarize.py           # Gera resumos via LLM
├── stats.py               # Estatísticas das conversas
├── eval.py                # Avalia qualidade dos resumos
├── publish.py             # Exporta para HTML/Markdown
└── *.zip                  # Arquivos de conversa (não versionados)
```

## Ferramentas

### segment_messages.py (existente)
Extrai mensagens de um arquivo ZIP do WhatsApp filtrando por data.
```bash
uv run segment_messages.py --zip_path chat.zip --start_date 01/01/2026 --end_date 07/01/2026
```

### summarize.py (a criar)
Gera resumos das conversas usando APIs de LLM.
```bash
# Via pipe (filosofia UNIX)
uv run segment_messages.py ... | uv run summarize.py --provider anthropic

# Provedores suportados: anthropic, openai, ollama
```

### stats.py (a criar)
Estatísticas: mensagens por pessoa, horários ativos, palavras frequentes.
```bash
uv run segment_messages.py ... | uv run stats.py --format json
```

### eval.py (a criar)
Avalia resumos gerados (coerência, cobertura, etc.).
```bash
uv run eval.py --original mensagens.txt --summary resumo.txt
```

### publish.py (a criar)
Publica resultados em diferentes formatos.
```bash
uv run summarize.py ... | uv run publish.py --format html --output relatorio.html
```

## Convenções

### CLI Arguments
- Use `--snake_case` para argumentos longos
- Suporte stdin quando fizer sentido (`-` ou omitir arquivo)
- `--format` para escolher formato de saída (text, json, csv)
- `--output` para arquivo de saída (default: stdout)

### Provedores de IA
Interface unificada para múltiplos provedores:
- Variáveis de ambiente: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
- Flag `--provider` para selecionar
- Flag `--model` para modelo específico

### Códigos de Saída
- `0`: Sucesso
- `1`: Erro de argumento/uso
- `2`: Erro de arquivo não encontrado
- `3`: Erro de API/rede

## Documentação

- Docstrings em todas as funções públicas
- Comentários apenas onde o código não for auto-explicativo
- `--help` detalhado via argparse
