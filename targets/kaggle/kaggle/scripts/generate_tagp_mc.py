#!/usr/bin/env python3
"""
Generate TAGP (Attentional Gateway Probe) Multiple Choice format.

Converts open-ended TAGP questions to MC format with task-specific distractors.
Task types:
- Selective Filtering (filter): Find specific info in noise
- Sustained Over Length (sustained): Track info through long text
- Attention Shifting (shift): Compare attributes across items
- Divided Attention (divided): Track two simultaneous streams
- Adversarial Needle (needle): Find the REAL/CORRECT item
"""

import os
import sys
import csv
import re
import random
from pathlib import Path
from typing import List, Tuple, Optional

# Paths
INPUT_CSV = Path(__file__).parent.parent / "data" / "tagp_attention.csv"
OUTPUT_CSV = Path(__file__).parent.parent / "data" / "tagp_mc.csv"

# Error code patterns for Selective Filtering
ERROR_CODES = [
    "ERR_TIMEOUT_DB_CONNECTION",
    "ERR_NULL_POINTER",
    "ERR_DIVISION_BY_ZERO",
    "ERR_BUFFER_OVERFLOW",
    "ERR_STACK_OVERFLOW",
    "ERR_MEMORY_LEAK",
    "ERR_FILE_NOT_FOUND",
    "ERR_INVALID_TOKEN",
    "ERR_RATE_LIMIT",
    "ERR_CONNECTION_REFUSED",
]

# API key patterns
API_KEYS = [
    "sk_live_abc123xyz789",
    "sk_test_def456uvw012",
    "pk_live_ghi789rst345",
    "sk_live_banana456grape",
    "pk_test_orange789apple",
]

# Critical messages
CRITICAL_MESSAGES = [
    "System failure in production",
    "Database connection lost",
    "Server overload detected",
    "Security breach attempt",
    "Critical system error",
]

# Server names for Sustained/Filter tasks
SERVERS = ["Server A", "Server B", "Server C", "Server D", "Server E", "Server F", "Server G", "Server H"]

# User login patterns
USERS = [f"User {i}" for i in range(1, 21)]

# Month names for timeline tasks
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

# Chapter references
CHAPTERS = [f"Chapter {i}" for i in range(1, 25)]

# Vehicle types for shift tasks
VEHICLES = ["car", "bike", "truck", "bus", "train"]

# Items for shift tasks
ITEMS = ["Item A", "Item B", "Item C", "Item D", "Item E"]

# Password patterns for needle tasks
PASSWORDS = [
    "letmein789",
    "monkey123",
    "password1",
    "football",
    "qwerty123",
    "hunter2",
    "admin456",
    "123456",
]

# Debug error patterns
ERROR_MESSAGES = [
    "ERROR: null pointer",
    "ERROR: division by zero",
    "ERROR: stack overflow",
    "ERROR: invalid memory",
    "ERROR: segfault",
]

# Count answers for divided attention
COUNT_PATTERNS = {
    "3, 2": ["2, 3", "3, 3", "2, 2", "4, 2", "3, 1"],
    "5, 4": ["4, 5", "5, 5", "4, 4", "6, 4", "5, 3"],
}


def parse_context(context: str) -> List[str]:
    """Parse context by pipe separator."""
    if "|" in context:
        return [part.strip() for part in context.split("|")]
    return [context]


def extract_numbers_from_context(context: str) -> List[int]:
    """Extract all numbers from context."""
    return [int(x) for x in re.findall(r'\b\d+\b', context)]


def generate_filter_distractors(answer: str, question: str) -> List[str]:
    """Generate distractors for Selective Filtering tasks."""
    # Error code questions
    if "error code" in question.lower() and answer.startswith("ERR_"):
        distractors = [e for e in ERROR_CODES if e != answer]
        random.shuffle(distractors)
        return distractors[:3]

    # API key questions
    if "api key" in question.lower() and answer.startswith("sk_"):
        distractors = [k for k in API_KEYS if k != answer]
        random.shuffle(distractors)
        return distractors[:3]

    # Critical message questions
    if "critical" in question.lower():
        distractors = [m for m in CRITICAL_MESSAGES if m != answer]
        random.shuffle(distractors)
        return distractors[:3]

    # Server questions
    if answer.startswith("Server "):
        distractors = [s for s in SERVERS if s != answer]
        random.shuffle(distractors)
        return distractors[:3]

    # Generic fallback
    return ["Unknown value", "Not specified", "Cannot determine"]


def generate_sustained_distractors(answer: str, question: str, context: str) -> List[str]:
    """Generate distractors for Sustained Attention tasks."""
    # Server questions
    if "server" in question.lower() and answer.startswith("Server "):
        distractors = [s for s in SERVERS if s != answer]
        random.shuffle(distractors)
        return distractors[:3]

    # User login questions - find nearby users
    if "user" in question.lower() and answer.startswith("User "):
        user_num = int(answer.split()[-1])
        nearby = []
        for offset in [-2, -1, 1, 2, 3, -3]:
            num = user_num + offset
            if 1 <= num <= 20:
                nearby.append(f"User {num}")
        distractors = [u for u in nearby if u != answer]
        random.shuffle(distractors)
        return distractors[:3]

    # Month/timeline questions
    if any(m in answer for m in MONTHS):
        distractors = [m for m in MONTHS if m != answer]
        random.shuffle(distractors)
        return distractors[:3]

    # Chapter questions
    if answer.startswith("Chapter "):
        chapter_num = int(answer.split()[-1])
        nearby = []
        for offset in [-2, -1, 1, 2, 3, -3]:
            num = chapter_num + offset
            if 1 <= num <= 25:
                nearby.append(f"Chapter {num}")
        distractors = [c for c in nearby if c != answer]
        random.shuffle(distractors)
        return distractors[:3]

    # Payment method questions
    if "paid with" in question.lower() or "pay" in question.lower():
        distractors = ["credit card", "debit card", "check", "bank transfer"]
        distractors = [d for d in distractors if d.lower() != answer.lower()]
        random.shuffle(distractors)
        return distractors[:3]

    # Generic fallback
    return ["Unknown", "Not mentioned", "Cannot determine"]


def generate_shift_distractors(answer: str, question: str, context: str) -> List[str]:
    """Generate distractors for Attention Shifting tasks."""
    # Item questions (Item A/B/C quality)
    if answer.startswith("Item "):
        distractors = [i for i in ITEMS if i != answer]
        random.shuffle(distractors)
        return distractors[:3]

    # Vehicle questions
    if answer in VEHICLES:
        distractors = [v for v in VEHICLES if v != answer]
        random.shuffle(distractors)
        return distractors[:3]

    # Generic fallback
    return ["Unknown", "Both equal", "None of the above"]


def generate_divided_distractors(answer: str, question: str, context: str) -> List[str]:
    """Generate distractors for Divided Attention tasks."""
    # Count questions like "3, 2"
    if answer in COUNT_PATTERNS:
        return COUNT_PATTERNS[answer][:3]

    # Parse as comma-separated counts
    if ", " in answer:
        parts = answer.split(", ")
        if len(parts) == 2 and all(p.strip().isdigit() for p in parts):
            a, b = int(parts[0]), int(parts[1])
            distractors = []
            for da, db in [(a+1, b), (a-1, b), (a, b+1), (a, b-1), (a+1, b+1)]:
                if da >= 0 and db >= 0:
                    distractors.append(f"{da}, {db}")
            random.shuffle(distractors)
            return distractors[:3]

    # Generic fallback
    return ["0, 0", "1, 1", "Unknown"]


def generate_needle_distractors(answer: str, question: str, context: str) -> List[str]:
    """Generate distractors for Adversarial Needle tasks."""
    # Password questions - the context already contains distractors!
    if "password" in question.lower():
        # Extract passwords from context
        passwords = re.findall(r'The password is: (\S+)', context)
        distractors = [p for p in passwords if p != answer]
        # Add more if needed
        while len(distractors) < 3:
            for p in PASSWORDS:
                if p not in distractors and p != answer:
                    distractors.append(p)
                    if len(distractors) >= 3:
                        break
        random.shuffle(distractors)
        return distractors[:3]

    # Error message questions - extract from context
    if "error" in question.lower() or "REAL" in answer:
        errors = re.findall(r'ERROR: ([\w\s]+)', context)
        if errors:
            distractors = [f"ERROR: {e}" for e in errors if f"ERROR: {e}" != answer]
            random.shuffle(distractors)
            if len(distractors) >= 3:
                return distractors[:3]

        # Fallback to generic error patterns
        distractors = [e for e in ERROR_MESSAGES if e != answer]
        random.shuffle(distractors)
        return distractors[:3]

    # Generic fallback
    return ["Unknown", "Not found", "Invalid"]


def generate_distractors(task: str, answer: str, question: str, context: str) -> List[str]:
    """Generate 3 distractors based on task type."""
    task_lower = task.lower()

    if "filter" in task_lower:
        return generate_filter_distractors(answer, question)
    elif "sustained" in task_lower:
        return generate_sustained_distractors(answer, question, context)
    elif "shift" in task_lower:
        return generate_shift_distractors(answer, question, context)
    elif "divided" in task_lower:
        return generate_divided_distractors(answer, question, context)
    elif "needle" in task_lower:
        return generate_needle_distractors(answer, question, context)
    else:
        return ["Unknown", "Not specified", "Cannot determine"]


def create_mc_question(row: dict) -> dict:
    """Convert a TAGP row to MC format."""
    question_id = row["id"]
    task = row["task"]
    context = row["context"]
    query = row["query"]
    answer = row["expected_focus"]

    # Generate distractors
    distractors = generate_distractors(task, answer, query, context)

    # Create options (answer is always A for simplicity)
    options = [answer] + distractors[:3]
    letters = ["A", "B", "C", "D"]

    # Format choices
    choices = "\n".join([f"{letter}) {opt}" for letter, opt in zip(letters, options)])

    return {
        "id": question_id,
        "question_type": "mc",
        "question": query,
        "choices": choices,
        "answer": "A"  # Always A since we put answer first
    }


def main():
    """Convert TAGP open-ended to MC format."""
    print(f"Reading: {INPUT_CSV}")

    results = []
    task_counts = {}

    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mc_q = create_mc_question(row)
            results.append(mc_q)

            # Count by task type
            task = row["task"]
            task_counts[task] = task_counts.get(task, 0) + 1

    # Write output
    print(f"Writing: {OUTPUT_CSV}")
    with open(OUTPUT_CSV, 'w', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["id", "question_type", "question", "choices", "answer"])
        writer.writeheader()
        writer.writerows(results)

    # Summary
    print(f"\n{'='*60}")
    print("TAGP MC Conversion Summary")
    print(f"{'='*60}")
    print(f"Total questions: {len(results)}")
    print(f"\nBy task type:")
    for task, count in sorted(task_counts.items()):
        print(f"  {task}: {count}")
    print(f"\nOutput: {OUTPUT_CSV}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
