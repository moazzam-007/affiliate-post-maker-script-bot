#!/usr/bin/env bash

# Force Python version from runtime.txt
echo "Forcing correct Python version from runtime.txt"

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
