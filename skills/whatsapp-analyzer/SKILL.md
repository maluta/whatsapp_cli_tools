---
name: whatsapp-analyzer
description: Analyze and summarize WhatsApp conversations exported as ZIP files. Use when the user wants to segment messages by date, generate AI-powered summaries, extract statistics, collect links, or publish reports as HTML sites. Supports multiple LLM providers (Google, Anthropic, OpenAI).
---

# WhatsApp Conversation Analyzer

Analyze WhatsApp group conversations with a pipeline of UNIX-style Python scripts. Each script does one thing well and can be composed via pipes.

## Installation (Claude Code)

```bash
# Add the marketplace
claude plugin marketplace add https://github.com/maluta/whatsapp_cli_tools

# Install the plugin
claude plugin install whatsapp-analyzer@whatsapp-tools
```

## Quick Reference

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `segment_messages.py` | Extract messages by date range | ZIP file | text (stdout) |
| `summarize.py` | Generate AI summary | text (stdin/file) | markdown |
| `stats.py` | Conversation statistics | text (stdin) | JSON/text |
| `extract_links.py` | Extract all URLs | text file | JSON |
| `enrich_links.py` | Fetch link titles | JSON file | JSON (updated) |
| `update_links.py` | Incremental link update | text files | JSON |
| `publish.py` | Generate HTML site | markdown dir | HTML site |
| `obfuscate.py` | Hide phone numbers | markdown files | modified files |
| `add_intro.py` | Add headers to summaries | markdown files | modified files |

## Decision Tree

```
User wants to analyze WhatsApp conversation
    │
    ├─ "Segment/extract messages from date X to Y"
    │   └─ Use: segment_messages.py --zip_path FILE --start_date DD/MM/YYYY --end_date DD/MM/YYYY
    │
    ├─ "Summarize conversation"
    │   └─ Pipe: segment_messages.py ... | summarize.py -p PROVIDER
    │   └─ Or file: summarize.py -i FILE -p PROVIDER -o OUTPUT.md
    │
    ├─ "Show statistics"
    │   └─ Pipe: segment_messages.py ... | stats.py --format json
    │
    ├─ "Extract links"
    │   └─ Use: extract_links.py CONVERSATION.txt -o links.json
    │   └─ Then: enrich_links.py links.json --limit 100
    │
    ├─ "Publish as website"
    │   └─ Use: publish.py --clean
    │   └─ With links: publish.py --clean --links-source full
    │
    └─ "Process multiple weeks"
        └─ Loop: for each week, segment → summarize → save
```

## Common Workflows

### 1. Weekly Summary (Most Common)

```bash
# Step 1: Segment messages
uv run segment_messages.py \
  --zip_path "Conversa do WhatsApp.zip" \
  --start_date 06/01/2026 \
  --end_date 12/01/2026 \
  > semanas/semana_2026-01-06_2026-01-12.txt

# Step 2: Generate summary
uv run summarize.py \
  -i semanas/semana_2026-01-06_2026-01-12.txt \
  -p google \
  -m gemini-2.5-flash \
  -o resumos/resumo_semana_2026-01-06_2026-01-12.md

# Step 3: Publish
uv run publish.py --clean
```

### 2. Full Pipeline (One Command)

```bash
uv run segment_messages.py --zip_path chat.zip --start_date 01/01/2026 --end_date 07/01/2026 | \
uv run summarize.py -p google -o resumos/semana.md
```

### 3. Extract All Links (First Time Setup)

```bash
# Extract text from ZIP
unzip -p "Conversa.zip" "*.txt" > links/conversa_completa.txt

# Extract links
uv run extract_links.py links/conversa_completa.txt -o links/links.json

# Enrich titles (optional, slow)
uv run enrich_links.py links/links.json --limit 200

# Publish with full links
uv run publish.py --clean --links-source full
```

### 4. Incremental Update (New Week)

```bash
# Segment new week
uv run segment_messages.py --zip_path "Nova Conversa.zip" \
  --start_date 13/01/2026 --end_date 19/01/2026 \
  > semanas/semana_2026-01-13_2026-01-19.txt

# Summarize
uv run summarize.py -i semanas/semana_2026-01-13_2026-01-19.txt \
  -p google -o resumos/resumo_semana_2026-01-13_2026-01-19.md

# Update links (only new ones)
uv run update_links.py semanas/semana_2026-01-13_2026-01-19.txt --enrich

# Republish
uv run publish.py --clean --links-source full
```

## Script Arguments

### segment_messages.py

```
--zip_path     Path to WhatsApp exported ZIP file (required)
--start_date   Start date DD/MM/YYYY (required)
--end_date     End date DD/MM/YYYY (required)
```

### summarize.py

```
-i, --input      Input file (default: stdin)
-o, --output     Output file (default: stdout)
-p, --provider   LLM provider: google, anthropic, openai (required)
-m, --model      Specific model (optional)
--max_tokens     Maximum output tokens
--estimate       Show cost estimate without executing
```

### stats.py

```
--format    Output format: text, json (default: text)
```

### publish.py

```
--input_dir      Directory with markdown files (default: resumos/)
--output_dir     Output directory for HTML (default: docs/)
--clean          Remove output directory before generating
--links-source   Link source: resumos, full (default: resumos)
--base_url       Base URL for GitHub Pages
```

### extract_links.py

```
FILE            Input text file (required)
-o, --output    Output JSON file (default: links/links.json)
```

### enrich_links.py

```
FILE            Input JSON file (required)
--limit         Max links to process
--start         Start index
--skip-enriched Skip already enriched links
```

## LLM Providers

| Provider | Flag | Env Variable | Recommended Model |
|----------|------|--------------|-------------------|
| Google | `-p google` | `GOOGLE_API_KEY` | `gemini-2.5-flash` |
| Anthropic | `-p anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-20250514` |
| OpenAI | `-p openai` | `OPENAI_API_KEY` | `gpt-4o` |

## Directory Structure

```
project/
├── *.zip                    # WhatsApp exports (not versioned)
├── semanas/                 # Segmented messages by week
│   └── semana_YYYY-MM-DD_YYYY-MM-DD.txt
├── resumos/                 # Generated summaries
│   └── resumo_semana_YYYY-MM-DD_YYYY-MM-DD.md
├── links/                   # Extracted links
│   ├── conversa_completa.txt
│   └── links.json
└── docs/                    # Generated HTML site
    ├── index.html
    └── *.html
```

## Before Running

1. **Check for ZIP file**: `ls *.zip`
2. **Create directories**: `mkdir -p semanas resumos links`
3. **Set API key** in `.env`:
   ```bash
   GOOGLE_API_KEY=your_key_here
   # or ANTHROPIC_API_KEY or OPENAI_API_KEY
   ```
4. **Estimate cost first**: `uv run summarize.py -i file.txt --estimate`

## Interactive Flow

When user asks to analyze WhatsApp conversations, gather:

1. **Which ZIP file?** → `ls *.zip`
2. **Date range?** → Start and end dates in DD/MM/YYYY
3. **What output?** → Summary, statistics, or both
4. **Which LLM?** → Google (cheapest), Anthropic, or OpenAI
5. **Publish site?** → Yes/No

## Error Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Invalid arguments |
| 2 | File not found |
| 3 | API/network error |

## Tips

- Use `--estimate` before summarizing to check costs
- Cache is stored in `.cache/` - same content won't be re-processed
- Phone numbers can be hidden with `obfuscate.py --in_place`
- For GitHub Pages, use `--base_url "/repo-name/"`
