#!/bin/bash
# Example: Generate a weekly summary from WhatsApp export
#
# This script demonstrates the most common workflow:
# 1. Segment messages from a specific week
# 2. Generate an AI-powered summary
# 3. Save to the resumos/ directory

set -e

# Configuration - adjust these
ZIP_FILE="Conversa do WhatsApp.zip"
START_DATE="06/01/2026"
END_DATE="12/01/2026"
PROVIDER="google"
MODEL="gemini-2.5-flash"

# Derived filenames
WEEK_FILE="semanas/semana_${START_DATE//\//-}_${END_DATE//\//-}.txt"
SUMMARY_FILE="resumos/resumo_semana_${START_DATE//\//-}_${END_DATE//\//-}.md"

# Ensure directories exist
mkdir -p semanas resumos

# Step 1: Segment messages
echo "Segmenting messages from $START_DATE to $END_DATE..."
uv run segment_messages.py \
  --zip_path "$ZIP_FILE" \
  --start_date "$START_DATE" \
  --end_date "$END_DATE" \
  > "$WEEK_FILE"

echo "Saved to $WEEK_FILE"

# Step 2: Check cost estimate (optional)
echo "Estimating cost..."
uv run summarize.py -i "$WEEK_FILE" --estimate

# Step 3: Generate summary
echo "Generating summary with $PROVIDER ($MODEL)..."
uv run summarize.py \
  -i "$WEEK_FILE" \
  -p "$PROVIDER" \
  -m "$MODEL" \
  -o "$SUMMARY_FILE"

echo "Summary saved to $SUMMARY_FILE"
