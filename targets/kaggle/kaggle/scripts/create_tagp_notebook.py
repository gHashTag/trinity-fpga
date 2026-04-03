#!/usr/bin/env python3
"""Create TAGP MC notebook from THLP template."""

import json
from pathlib import Path

# Paths
TEMPLATE = Path(__file__).parent.parent / "notebooks" / "thlp_mc_task.ipynb"
OUTPUT = Path(__file__).parent.parent / "notebooks" / "tagp_mc_final.ipynb"

# Load THLP template
with open(TEMPLATE, 'r') as f:
    content = f.read()

# Replace task names and descriptions
content = content.replace("THLP", "TAGP")
content = content.replace("Hippocampal Learning Probe", "Attentional Gateway Probe")
content = content.replace("thlp-mc", "tagp-mc")
content = content.replace("'thlp_mc.csv'", "'tagp_mc.csv'")

# Save with proper formatting
with open(OUTPUT, 'w') as f:
    f.write(content)

print(f"✅ Created: {OUTPUT}")
