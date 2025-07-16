#!/bin/bash

# Cleanup script for freqtrade experiment outputs
# This script empties the outputs folder to prepare for fresh experiments

echo "🧹 Cleaning up experiment outputs..."

# Empty the outputs directory but keep the directory structure
if [ -d "experiments/outputs" ]; then
    echo "  Emptying experiments/outputs directory..."
    rm -rf experiments/outputs/*
    echo "  ✅ Outputs directory emptied"
else
    echo "  ⚠️  No outputs directory found"
fi

echo "🎉 Cleanup complete!"
echo ""
echo "The outputs folder is now empty and ready for new experiments."
echo "Run: ./experiments/scripts/run_all_experiments.sh"