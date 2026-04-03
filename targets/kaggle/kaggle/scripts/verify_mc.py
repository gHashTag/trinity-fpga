#!/usr/bin/env python3
"""Verify MC format is correct."""
import csv

with open('kaggle/data/converted_mc/thlp_mc.csv', 'r') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        if i >= 5:
            break
        print(f"ID: {row['id']}")
        print(f"Question: {row['question'][:80]}...")
        print(f"Choices: {row['choices'][:100] if row['choices'] else 'EMPTY'}")
        print(f"Answer: {row['answer']}")
        print()

# Check for empty choices
print("\n=== Checking for empty choices ===")
with open('kaggle/data/converted_mc/thlp_mc.csv', 'r') as f:
    reader = csv.DictReader(f)
    empty_count = 0
    mc_count = 0
    for row in reader:
        if row['question_type'] == 'mc':
            mc_count += 1
            if not row.get('choices') or row['choices'] == '':
                empty_count += 1
                print(f"EMPTY choices: {row['id']}")

print(f"\nTotal MC questions: {mc_count}")
print(f"Empty choices: {empty_count}")
