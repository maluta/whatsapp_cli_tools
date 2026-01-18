# WhatsApp Resumo Grupo IA

Ferramenta para gerar resumos semanais automáticos de conversas do WhatsApp usando Inteligência Artificial.

---

## O que esse projeto faz?

Você exporta a conversa do WhatsApp, roda alguns comandos, e pronto: tem um site bonito com resumos semanais + todos os links compartilhados no grupo.

**Antes:** Um arquivo ZIP gigante com milhares de mensagens
**Depois:** Site organizado com resumos por semana e busca

---

## Requisitos

- Python 3.11 ou superior
- [uv](https://github.com/astral-sh/uv) - gerenciador de pacotes Python ultrarrápido
- Chave de API de um provedor de IA (Google, Anthropic ou OpenAI)

### Instalando o uv

```bash
# Linux/Mac
curl -LsSf https://astral.sh/uv/install.sh | sh

# Ou com pip
pip install uv
```

### Configurando a API Key

Crie um arquivo `.env` na raiz do projeto:

```bash
# Escolha UM dos provedores:
GOOGLE_API_KEY=sua_chave_aqui      # Recomendado (mais barato)
ANTHROPIC_API_KEY=sua_chave_aqui   # Claude
OPENAI_API_KEY=sua_chave_aqui      # ChatGPT
```

---

## Guia Rápido (5 minutos)

### Passo 1: Clone o repositório

```bash
git clone https://github.com/seu-usuario/whatsapp_resumo_grupo_IA.git
cd whatsapp_resumo_grupo_IA

# Crie as pastas necessárias (não vêm no repo)
mkdir -p semanas resumos links
```

### Passo 2: Exporte a conversa do WhatsApp

1. Abra o grupo no WhatsApp
2. Toque nos três pontinhos → "Mais" → "Exportar conversa"
3. Escolha "Sem mídia" (o arquivo fica menor)
4. Salve o arquivo `.zip` na pasta do projeto

### Passo 3: Segmente por semana

```bash
# Extrai mensagens de uma semana específica
uv run segment_messages.py \
  --zip_path "Conversa do WhatsApp.zip" \
  --start_date 06/01/2026 \
  --end_date 12/01/2026 \
  > semanas/semana_2026-01-06_2026-01-12.txt
```

### Passo 4: Gere o resumo

```bash
# Usando Google Gemini (recomendado - mais barato)
uv run summarize.py \
  -i semanas/semana_2026-01-06_2026-01-12.txt \
  -p google \
  -m gemini-2.5-flash \
  -o resumos/resumo_semana_2026-01-06_2026-01-12.md
```

### Passo 5: Publique o site

```bash
uv run publish.py --clean
```

Pronto! Abra `docs/index.html` no navegador.

---

## Primeira Vez? Extraia Todos os Links de Uma Vez

Se você está configurando o projeto pela primeira vez e quer extrair **todos os links históricos** da conversa (não apenas da semana atual), use o `extract_links.py` na conversa completa:

```bash
# 1. Extraia o arquivo de texto do ZIP
unzip -p "Conversa do WhatsApp.zip" "*.txt" > links/conversa_completa.txt

# 2. Extraia todos os links (remove UTM automaticamente)
uv run extract_links.py links/conversa_completa.txt -o links/links.json

# 3. (Opcional) Enriqueça os títulos - demora, mas melhora muito
uv run enrich_links.py links/links.json --limit 200

# 4. Publique com todos os links
uv run publish.py --clean --links-source full
```

Depois da primeira vez, use `update_links.py` para adicionar apenas os links novos de cada semana.

---

## Estrutura de Pastas

```
.
├── *.zip                    # Arquivo exportado do WhatsApp
├── semanas/                 # Mensagens segmentadas por semana
│   └── semana_YYYY-MM-DD_YYYY-MM-DD.txt
├── resumos/                 # Resumos gerados (markdown)
│   └── resumo_semana_YYYY-MM-DD_YYYY-MM-DD.md
├── links/                   # Links extraídos
│   ├── conversa_completa.txt
│   └── links.json
├── docs/                    # Site gerado (HTML)
│   ├── index.html
│   ├── links.html
│   └── *.html
└── *.py                     # Scripts
```

---

## Scripts Disponíveis

### Fluxo Principal

| Script | O que faz | Exemplo |
|--------|-----------|---------|
| `segment_messages.py` | Extrai mensagens por período | `uv run segment_messages.py --zip_path chat.zip --start_date 01/01/2026 --end_date 07/01/2026` |
| `summarize.py` | Gera resumo com IA | `uv run summarize.py -i arquivo.txt -p google -o resumo.md` |
| `publish.py` | Gera site HTML | `uv run publish.py --clean` |

### Utilitários

| Script | O que faz | Exemplo |
|--------|-----------|---------|
| `add_intro.py` | Adiciona cabeçalho nos resumos | `uv run add_intro.py --in_place` |
| `obfuscate.py` | Esconde telefones | `uv run obfuscate.py --in_place` |
| `stats.py` | Estatísticas da conversa | `cat mensagens.txt \| uv run stats.py` |

### Links

| Script | O que faz | Exemplo |
|--------|-----------|---------|
| `extract_links.py` | Extrai todos os links | `uv run extract_links.py conversa.txt -o links/links.json` |
| `enrich_links.py` | Melhora títulos via browser | `uv run enrich_links.py links/links.json --limit 50` |
| `update_links.py` | Atualiza links da semana | `uv run update_links.py semanas/semana_*.txt` |

---

## Exemplos Detalhados

### Processar várias semanas de uma vez

```bash
# Script para processar múltiplas semanas
for semana in semanas/semana_*.txt; do
  nome=$(basename "$semana" .txt)
  echo "Processando: $nome"
  uv run summarize.py \
    -i "$semana" \
    -p google \
    -m gemini-2.5-flash \
    -o "resumos/resumo_$nome.md"
done
```

### Ver estimativa de custo antes de gerar

```bash
uv run summarize.py -i semanas/semana_2026-01-06.txt --estimate
# Mostra: ~X tokens, custo estimado: $Y
```

### Extrair links de todas as semanas

```bash
# Opção 1: Processar todas as semanas de uma vez
uv run update_links.py semanas/semana_*.txt --enrich

# Opção 2: Extrair da conversa completa (primeira vez)
unzip -p "Conversa.zip" "*.txt" > links/conversa_completa.txt
uv run extract_links.py links/conversa_completa.txt -o links/links.json
uv run enrich_links.py links/links.json --limit 100

# Publicar com os links completos
uv run publish.py --clean --links-source full
```

### Atualizar com nova semana

```bash
# 1. Exporte nova conversa do WhatsApp

# 2. Segmente a nova semana
uv run segment_messages.py \
  --zip_path "Nova Conversa.zip" \
  --start_date 13/01/2026 \
  --end_date 19/01/2026 \
  > semanas/semana_2026-01-13_2026-01-19.txt

# 3. Gere o resumo
uv run summarize.py \
  -i semanas/semana_2026-01-13_2026-01-19.txt \
  -p google \
  -o resumos/resumo_semana_2026-01-13_2026-01-19.md

# 4. Atualize os links (detecta apenas novos da semana)
uv run update_links.py semanas/semana_2026-01-13_2026-01-19.txt --enrich

# 5. Republique
uv run publish.py --clean --links-source full
```

### Publicar no GitHub Pages

```bash
# Gere o site
uv run publish.py --clean --base_url "/nome-do-repo/"

# Commit e push
git add docs/
git commit -m "Atualiza resumos"
git push

# Configure GitHub Pages para usar a pasta docs/
```

---

## Provedores de IA Suportados

| Provedor | Flag | Modelo Recomendado | Custo |
|----------|------|--------------------|-------|
| Google | `-p google` | `gemini-2.5-flash` | Mais barato |
| Anthropic | `-p anthropic` | `claude-sonnet-4-20250514` | Médio |
| OpenAI | `-p openai` | `gpt-4o` | Mais caro |

### Exemplos por provedor

```bash
# Google (recomendado)
uv run summarize.py -i arquivo.txt -p google -m gemini-2.5-flash -o resumo.md

# Anthropic
uv run summarize.py -i arquivo.txt -p anthropic -m claude-sonnet-4-20250514 -o resumo.md

# OpenAI
uv run summarize.py -i arquivo.txt -p openai -m gpt-4o -o resumo.md
```

---

## FAQ

### "Erro: No such file or directory: 'semanas/...'"

As pastas não vêm no repositório. Crie elas:

```bash
mkdir -p semanas resumos links
```

### "Dá erro de API key não encontrada"

Verifique se o arquivo `.env` está na raiz do projeto com a chave correta:

```bash
cat .env
# Deve mostrar: GOOGLE_API_KEY=sua_chave_aqui
```

### "O resumo ficou cortado/incompleto"

Aumente o limite de tokens:

```bash
uv run summarize.py -i arquivo.txt -p google --max_tokens 65000 -o resumo.md
```

### "Quero usar outro modelo"

Liste os modelos disponíveis e use a flag `-m`:

```bash
# Google tem vários modelos Gemini
uv run summarize.py -i arquivo.txt -p google -m gemini-2.5-pro -o resumo.md
```

### "O site não mostra os links"

Por padrão, `publish.py` extrai links apenas dos resumos markdown. Para usar todos os links:

```bash
# Primeiro extraia os links
uv run extract_links.py links/conversa_completa.txt -o links/links.json

# Depois publique com a flag
uv run publish.py --clean --links-source full
```

### "Como escondo os números de telefone?"

```bash
uv run obfuscate.py --in_place
# Transforma: +55 11 99999-1234 → +55 11 🫣-1234
```

### "O enrich_links.py está muito lento"

É normal - ele abre cada link no navegador. Para acelerar:

```bash
# Processe em lotes
uv run enrich_links.py links/links.json --start 0 --limit 100
uv run enrich_links.py links/links.json --start 100 --limit 100 --skip-enriched
```

### "Quero ver estatísticas da conversa"

```bash
cat semanas/semana_*.txt | uv run stats.py --format json
```

### "Como funciona o cache de resumos?"

O `summarize.py` salva um cache em `.cache/` baseado no hash do conteúdo. Se você rodar o mesmo arquivo duas vezes, ele usa o cache (grátis e instantâneo).

### "Posso usar com outros grupos?"

Sim! Basta exportar a conversa de qualquer grupo e seguir o mesmo fluxo.

### "O site está feio no celular"

O template é responsivo, mas você pode customizar editando o CSS dentro de `publish.py` (procure por `BASE_TEMPLATE`).

---

## Contribuindo

1. Fork o repositório
2. Crie uma branch: `git checkout -b minha-feature`
3. Faça suas alterações
4. Teste: `uv run publish.py --clean`
5. Commit: `git commit -m "Adiciona feature X"`
6. Push: `git push origin minha-feature`
7. Abra um Pull Request

---

## Licença

MIT - Use como quiser!

---

## Créditos

Feito com muito café e IA por [seu nome aqui].

Resumos gerados com LLMs (Gemini/Claude/GPT).
