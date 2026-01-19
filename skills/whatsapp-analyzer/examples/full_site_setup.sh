#!/bin/bash
# Example: First-time setup to create a complete site with all links
#
# This script demonstrates the initial setup workflow:
# 1. Extract all text from ZIP
# 2. Extract all links from the conversation
# 3. Enrich link titles (optional, slow)
# 4. Publish the complete site

set -e

# Configuration
ZIP_FILE="Conversa do WhatsApp.zip"
LINKS_LIMIT=200  # Limit enrichment to avoid too many requests

# Ensure directories exist
mkdir -p links semanas resumos docs

# Step 1: Extract full conversation text
echo "Extracting text from ZIP..."
unzip -p "$ZIP_FILE" "*.txt" > links/conversa_completa.txt
echo "Extracted to links/conversa_completa.txt"

# Step 2: Extract all links
echo "Extracting links..."
uv run extract_links.py links/conversa_completa.txt -o links/links.json
echo "Links saved to links/links.json"

# Step 3: Enrich titles (optional - this is slow)
read -p "Enrich link titles? This may take a while. (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  echo "Enriching up to $LINKS_LIMIT links..."
  uv run enrich_links.py links/links.json --limit "$LINKS_LIMIT"
fi

# Step 4: Publish site
echo "Publishing site..."
uv run publish.py --clean --links-source full

echo ""
echo "Done! Open docs/index.html in your browser."
