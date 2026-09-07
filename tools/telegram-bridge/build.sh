#!/bin/bash
cd "$(git rev-parse --show-toplevel)/telegram-bridge"
echo "Building telegram-bridge..."
go build -o telegram-bridge ./cmd/server
echo "Done! Binary: telegram-bridge"
