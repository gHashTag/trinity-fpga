#!/usr/bin/env python3
"""
Upload Trinity Cognitive Probes MC datasets to Kaggle.

Creates separate datasets for each track with MC-converted CSVs.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
MC_DATASETS = {
    "tmp": {
        "title": "Trinity Metacognition Probe - MC Format",
        "slug": "trinity-cognitive-probes-tmp-mc",
        "csv": "kaggle/data/converted_mc/tmp_mc.csv",
        "description": """# Trinity Metacognition Probe (TTM) - Multiple Choice Format

**Track 2**: Tests confidence calibration, error detection, meta-learning.

## Format
- `question`: Open-ended metacognitive question
- `choices`: 4 options (A, B, C, D)
- `answer`: Correct letter (A-D)

## Contents
- 733 MC questions (converted from open-ended)
- 1467 factual short-answer questions

## Brain Zone
- **PCC** (Posterior Cingulate Cortex) — Metacognitive monitoring
- **dlPFC** (Dorsolateral PFC) — Executive control

## Citation
Trinity Cognitive Probes — Ternary Hyperdimensional Computing AGI Benchmark
"""
    },
    "thlp": {
        "title": "Trinity Hippocampal Learning Probe - MC Format",
        "slug": "trinity-cognitive-probes-thlp-mc",
        "csv": "kaggle/data/converted_mc/thlp_mc.csv",
        "description": """# Trinity Hippocampal Learning Probe (THLP) - Multiple Choice Format

**Track 1**: Tests pattern learning, belief update, rule induction.

## Format
- `question`: Open-ended learning question
- `choices`: 4 options (A, B, C, D)
- `answer`: Correct letter (A-D)

## Contents
- 1152 MC questions (converted from open-ended)
- 1248 factual short-answer questions

## Brain Zone
- **Hippocampus** — Pattern completion, error-driven learning
- **Entorhinal Cortex** — Grid cells for spatial reasoning

## Citation
Trinity Cognitive Probes — Ternary Hyperdimensional Computing AGI Benchmark
"""
    },
    "tefb": {
        "title": "Trinity Executive Function Battery - MC Format",
        "slug": "trinity-cognitive-probes-tefb-mc",
        "csv": "kaggle/data/converted_mc/tefb_mc.csv",
        "description": """# Trinity Executive Function Battery (TEFB) - Multiple Choice Format

**Track 4**: Tests multi-step planning, working memory, cognitive flexibility.

## Format
- `question`: Executive function scenario with context
- `choices`: 4 options (A, B, C, D)
- `answer`: Correct letter (A-D)

## Contents
- 1805 MC questions (converted from open-ended)
- 595 factual short-answer questions

## Brain Zone
- **dlPFC** (Dorsolateral PFC) — Working memory, planning
- **ACC** (Anterior Cingulate Cortex) — Conflict monitoring
- **OFC** (Orbitofrontal Cortex) — Value-based decision

## Citation
Trinity Cognitive Probes — Ternary Hyperdimensional Computing AGI Benchmark
"""
    },
    "tscp": {
        "title": "Trinity Social Cognition Probe - MC Format",
        "slug": "trinity-cognitive-probes-tscp-mc",
        "csv": "kaggle/data/converted_mc/tscp_mc.csv",
        "description": """# Trinity Social Cognition Probe (TSCP) - Multiple Choice Format

**Track 5**: Tests Theory of Mind, pragmatic inference, social norms.

## Format
- `question`: Social scenario
- `choices`: 4 options (A, B, C, D)
- `answer`: Correct letter (A-D)

## Contents
- 1584 MC questions (converted from open-ended)
- 616 factual short-answer questions

## Brain Zone
- **TPJ** (Temporoparietal Junction) — Theory of Mind
- **OFC** (Orbitofrontal Cortex) — Social value
- **mPFC** (Medial PFC) — Mentalizing

## Citation
Trinity Cognitive Probes — Ternary Hyperdimensional Computing AGI Benchmark
"""
    },
    "tagp": {
        "title": "Trinity Attentional Gateway Probe",
        "slug": "trinity-cognitive-probes-tagp",
        "csv": "kaggle/data/tagp_attention.csv",
        "description": """# Trinity Attentional Gateway Probe (TAGP)

**Track 3**: Tests selective filtering, sustained attention, attention shifting.

## Format
- All questions are factual short-answer (no MC needed)
- `query`: Attention question
- `expected_focus`: Correct answer

## Contents
- 2200 factual questions

## Brain Zone
- **Thalamus** — Attentional gateway
- **Reticular Formation** — Arousal control
- **Superior Colliculus** — Eye movement control

## Citation
Trinity Cognitive Probes — Ternary Hyperdimensional Computing AGI Benchmark
"""
    },
}


def create_dataset_metadata(track: str, info: dict, temp_dir: Path) -> None:
    """Create dataset-metadata.json for Kaggle upload."""
    metadata = {
        "title": info["title"],
        "id": f"playra/{info['slug']}",
        "licenses": [{"name": "CC0-1.0"}]
    }
    meta_file = temp_dir / "dataset-metadata.json"
    with open(meta_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"  Created: {meta_file}")


def create_readme(track: str, info: dict, temp_dir: Path) -> None:
    """Create README.md for the dataset."""
    readme_file = temp_dir / "README.md"
    with open(readme_file, 'w') as f:
        f.write(info["description"])
    print(f"  Created: {readme_file}")


def upload_dataset(track: str, info: dict, dry_run: bool = False) -> bool:
    """Upload a single dataset to Kaggle."""
    csv_path = Path(info["csv"])
    if not csv_path.exists():
        print(f"  ❌ CSV not found: {csv_path}")
        return False

    # Create temp directory for dataset
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy CSV
        import shutil
        shutil.copy(csv_path, temp_path / csv_path.name)
        print(f"  Copied: {csv_path.name}")

        # Create metadata
        create_dataset_metadata(track, info, temp_path)

        # Create README
        create_readme(track, info, temp_path)

        if dry_run:
            print(f"  📋 DRY RUN: Would upload playra/{info['slug']}")
            return True

        # Upload to Kaggle
        print(f"  Uploading playra/{info['slug']}...")
        result = subprocess.run(
            ["kaggle", "datasets", "version", "-p", str(temp_path), "-m", "MC format upload"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"  ✅ Uploaded: https://www.kaggle.com/datasets/playra/{info['slug']}")
            return True
        else:
            print(f"  ❌ Upload failed: {result.stderr}")
            return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Upload MC datasets to Kaggle")
    parser.add_argument("--track", default="ALL", help="Track to upload (tmp, thlp, tefb, tscp, tagp, ALL)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded without actually uploading")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("KAGGLE MC DATASET UPLOAD")
    print("=" * 60 + "\n")

    if args.dry_run:
        print("📋 DRY RUN MODE — No actual uploads\n")

    tracks_to_upload = []
    if args.track == "ALL":
        tracks_to_upload = list(MC_DATASETS.keys())
    else:
        if args.track not in MC_DATASETS:
            print(f"❌ Unknown track: {args.track}")
            print(f"Available: {', '.join(MC_DATASETS.keys())}")
            sys.exit(1)
        tracks_to_upload = [args.track]

    results = {}
    for track in tracks_to_upload:
        info = MC_DATASETS[track]
        print(f"\n{track.upper()}: {info['title']}")
        print(f"  Slug: playra/{info['slug']}")
        print(f"  CSV: {info['csv']}")

        success = upload_dataset(track, info, args.dry_run)
        results[track] = success

    # Summary
    print("\n" + "=" * 60)
    print("UPLOAD SUMMARY")
    print("=" * 60)
    for track, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {track.upper()}")
    print("=" * 60 + "\n")

    if args.dry_run:
        print("To actually upload, run:")
        print(f"  python3 {__file__} --track {args.track}")
        print()


if __name__ == "__main__":
    main()
