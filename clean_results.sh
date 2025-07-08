#!/bin/bash

# Clean Results Script for Freqtrade Walk Forward Testing
# This script empties the results directories to start fresh

echo "🧹 Cleaning Freqtrade results directories..."

# Function to safely remove directory contents
clean_directory() {
    local dir="$1"
    local description="$2"
    
    if [ -d "$dir" ]; then
        echo "  Cleaning $description ($dir)..."
        rm -rf "$dir"/*
        echo "    ✅ $description cleaned"
    else
        echo "    ⚠️  $description directory does not exist: $dir"
    fi
}

# Clean backtest results
clean_directory "user_data/backtest_results" "Backtest Results"

# Clean hyperopt results  
clean_directory "user_data/hyperopt_results" "Hyperopt Results"

# Clean walk forward results
clean_directory "walk_forward_results" "Walk Forward Results"

# Clean plot files
clean_directory "user_data/plot" "Plot Files"

echo ""
echo "🎉 All results directories have been cleaned!"
echo ""
echo "Directory status:"
echo "  📁 user_data/backtest_results/: $(ls -la user_data/backtest_results/ 2>/dev/null | wc -l | tr -d ' ') items"
echo "  📁 user_data/hyperopt_results/: $(ls -la user_data/hyperopt_results/ 2>/dev/null | wc -l | tr -d ' ') items" 
echo "  📁 walk_forward_results/: $(ls -la walk_forward_results/ 2>/dev/null | wc -l | tr -d ' ') items"
echo "  📁 user_data/plot/: $(ls -la user_data/plot/ 2>/dev/null | wc -l | tr -d ' ') items"
echo ""
echo "Ready for fresh walk forward testing! 🚀"