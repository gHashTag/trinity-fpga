#!/bin/bash
# Project Reorganization Script
# ======================================
# Execute with: bash reorganize.sh
# ======================================

set -e

echo "=== Trinity Project Reorganization ==="
echo ""

# Phase 1: Create new directory structure
echo "Phase 1: Creating new structure..."
mkdir -p docs/book docs/site
mkdir -p tests/benchmarks tests/unit
mkdir -p lab/experiments lab/results lab/outreach
mkdir -p targets/wasm targets/kaggle
mkdir -p tools/scripts tools/vscode-extension tools/webarena
mkdir -p release

# Phase 2: Move documentation
echo "Phase 2: Moving documentation..."
if [ -d "book" ]; then
    echo "  book/ → docs/book/"
    mv book docs/book/
fi
if [ -d "docsite" ]; then
    echo "  docsite/ → docs/site/"
    mv docsite docs/site/
fi
if [ ! -f "docs/MEMORY.md" ]; then
    echo "  Creating docs/MEMORY.md"
    touch docs/MEMORY.md
fi

# Phase 3: Move tools
echo "Phase 3: Moving tools..."
if [ -d "scripts" ]; then
    echo "  scripts/ → tools/scripts/"
    mv scripts tools/scripts/
fi
if [ -d "extension" ]; then
    echo "  extension/ → tools/vscode-extension/"
    mv extension tools/vscode-extension/
fi
if [ -d "webarena_agent" ]; then
    echo "  webarena_agent/ → tools/webarena/"
    mv webarena_agent tools/webarena/
fi

# Phase 4: Move examples
echo "Phase 4: Moving examples..."
if [ -d "demotapes" ]; then
    echo "  demotapes/ → examples/demotapes/"
    mv demotapes examples/demotapes/
fi
if [ -d "recordings" ]; then
    echo "  recordings/ → examples/recordings/"
    mv recordings examples/recordings/
fi

# Phase 5: Move test-related
echo "Phase 5: Moving test-related..."
if [ -d "benchmarks" ]; then
    echo "  benchmarks/ → tests/benchmarks/"
    mv benchmarks tests/benchmarks/
fi
if [ -d "test" ]; then
    echo "  test/ → tests/unit/"
    mv test tests/unit/
fi

# Phase 6: Move research/lab
echo "Phase 6: Moving research/lab..."
if [ -d "experiments" ]; then
    echo "  experiments/ → lab/experiments/"
    mv experiments lab/experiments/
fi
if [ -d "results" ]; then
    echo "  results/ → lab/results/"
    mv results lab/results/
fi
if [ -d "outreach" ]; then
    echo "  outreach/ → lab/outreach/"
    mv outreach lab/outreach/
fi

# Phase 7: Move targets
echo "Phase 7: Moving target platforms..."
if [ -d "wasm" ]; then
    echo "  wasm/ → targets/wasm/"
    mv wasm targets/wasm/
fi
if [ -d "kaggle" ]; then
    echo "  kaggle/ → targets/kaggle/"
    mv kaggle targets/kaggle/
fi

# Phase 8: Organize external dependencies
echo "Phase 8: Organizing external dependencies..."
if [ -d "zig-hslm" ]; then
    echo "  zig-hslm/ → external/zig-hslm/"
    mv zig-hslm external/zig-hslm/
fi

# zig-golden-float: add as git submodule (will be done separately)
if [ -d "zig-golden-float" ]; then
    echo "  zig-golden-float → will become git submodule"
    mv zig-golden-float external/zig-golden-float
fi

# Remove empty external parent
if [ -d "external" ] && [ -z "$(ls -A external)" ]; then
    rmdir external
    echo "  Removed empty external/"
fi

# Phase 9: Organize release
echo "Phase 9: Organizing release..."
if [ -d "release-assets" ]; then
    echo "  release-assets/ → release/assets/"
    mv release-assets release/assets/
fi
if [ -d "release-v2.0.0" ]; then
    echo "  release-v2.0.0/ → release/v2.0.0/"
    mv release-v2.0.0 release/v2.0.0/
fi

# Phase 10: Archive legacy items
echo "Phase 10: Archiving legacy items..."
mkdir -p archive/legacy

# Archive old stuff
for dir in combined; do
    if [ -d "$dir" ]; then
        echo "  $dir/ → archive/legacy/"
        mv "$dir" archive/legacy/
    fi
done

# Check var/ content
if [ -d "var" ]; then
    if [ -f "var/.gitkeep" ]; then
        # Already managed
        echo "  var/ has .gitkeep (already managed)"
    else
        # Move to archive
        echo "  var/ → archive/var/"
        mv var archive/var/
        # Create .gitkeep instead
        touch archive/var/.gitkeep
        echo "    Created archive/var/.gitkeep"
    fi
fi

# Phase 11: Check trinity/ directory
echo "Phase 11: Checking trinity/ directory..."
if [ -d "trinity" ]; then
    # Check if it's a duplicate of src/
    if diff -qr src/ trinity/ | grep -v "^Only"; then
        echo "  trinity/ duplicates src/ → archive/trinity-dup/"
        mv trinity archive/trinity-dup/
    else
        echo "  trinity/ is distinct, keeping"
    fi
fi

# Phase 12: Organize remaining tools/ items
echo "Phase 12: Organizing remaining in tools/..."
mkdir -p tools/legacy
for item in config memory stdlib; do
    if [ -d "$item" ]; then
        echo "  $item/ → tools/legacy/"
        mv "$item" tools/legacy/
    fi
done

# Phase 13: Clean up zig-out-linux
echo "Phase 13: Checking zig-out-linux..."
if [ -d "zig-out-linux" ]; then
    echo "  zig-out-linux/ exists - should be in .gitignore (build artifact)"
fi

# Summary
echo ""
echo "=== Reorganization Complete ==="
echo ""
echo "New structure:"
echo "  src/          - Source code"
echo "  specs/        - .tri specifications"
echo "  docs/         - Documentation (book/, site/, MEMORY.md)"
echo "  tools/        - Utilities (scripts/, vscode-extension/, webarena/)"
echo "  tests/        - Tests (benchmarks/, unit/)"
echo "  examples/     - Examples (demotapes/, recordings/)"
echo "  lab/          - Research (experiments/, results/, outreach/)"
echo "  targets/       - Platforms (wasm/, kaggle/)"
echo "  external/       - Dependencies (zig-hslm/, zig-golden-float/)"
echo "  release/       - Releases (assets/, v2.0.0/)"
echo "  archive/       - Archives (legacy/, combined/, trinity-dup/, var/)"
echo ""
echo "NOTE: zig-golden-float needs to be added as git submodule"
echo ""
echo "Run: git add -A && git commit to apply changes"
