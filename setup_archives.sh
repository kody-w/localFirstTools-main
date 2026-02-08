#!/bin/bash
cd /Users/kodyw/Projects/localFirstTools-main

# Create directories
mkdir -p apps/archive/thought-cascade
mkdir -p apps/archive/ferrofluid-wordsmith
mkdir -p apps/archive/smoke-words

# Copy files
cp apps/generative-art/thought-cascade.html apps/archive/thought-cascade/v1.html
cp apps/generative-art/ferrofluid-wordsmith.html apps/archive/ferrofluid-wordsmith/v1.html
cp apps/generative-art/smoke-words.html apps/archive/smoke-words/v1.html

# Verify
echo "Verifying files:"
ls -la apps/archive/thought-cascade/v1.html
ls -la apps/archive/ferrofluid-wordsmith/v1.html
ls -la apps/archive/smoke-words/v1.html
