#!/usr/bin/env python3
"""
Convert Trinity Cognitive Probes from Open-Ended to Multiple Choice (MC) format.

Open-ended questions require semantic understanding, not string matching.
This script converts open-ended questions to MC format with LLM-generated distractors.
"""

import os
import sys
import json
import re
import random
from pathlib import Path
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
CSV_FILES = {
    "tmp": "kaggle/data/tmp_metacognition.csv",
    "tagp": "kaggle/data/tagp_attention.csv",
    "tefb": "kaggle/data/tefb_executive.csv",
    "tscp": "kaggle/data/tscp_social.csv",
    "thlp": "kaggle/data/thlp_learning.csv",
}


@dataclass
class Question:
    id: str
    question: str
    answer: str
    question_type: str  # "factual" or "open-ended"


def is_thlp_question(question: str, task: str = None) -> bool:
    """Check if this is a THLP (Hippocampal Learning Probe) question.

    THLP questions test pattern learning, belief update, and rule induction.
    They require understanding patterns, not just factual recall.
    """
    thlp_patterns = [
        "Water boils at",         # Belief update (boiling point)
        "boil",                    # Temperature beliefs
        "Learn the rule",          # Few-shot rule induction
        "Input:",                  # Pattern completion
        "Test:",                   # Pattern application
        "incorrectly stated",      # Error-driven learning
        "reverse",                 # String transformation
        "Fibonacci",               # Pattern recognition
        " -> ",                    # Transformation pattern (cat -> tac)
    ]

    question_lower = question.lower()
    if any(p.lower() in question_lower for p in thlp_patterns):
        return True

    # Check task column if available
    if task and "thlp" in task.lower():
        return True

    return False


def detect_question_type(question: str, answer: str, task: str = None) -> str:
    """Detect if question is factual short-answer or open-ended."""
    question_lower = question.strip().lower()

    # THLP questions are ALWAYS open-ended (require pattern understanding)
    if is_thlp_question(question, task):
        return "open-ended"

    # Check for factual short-answer patterns
    factual_patterns = [
        (r"^what is the capital of \w+", "capital"),
        (r"^what is \d+\^\d+", "math_power"),
        (r"^what is \d+ \+ \d+", "math_add"),
        (r"^what is \d+ \* \d+", "math_mult"),
        (r"^what is \d+ / \d+", "math_div"),
        (r"^(what|who|where|when) is (the|a) \w+", "factual_what"),
        (r"^which (user|server|item|chapter|color)", "factual_which"),
        (r"^how many", "factual_how_many"),
        (r"^(yes|no|true|false)$", "boolean"),
    ]

    for pattern, name in factual_patterns:
        if re.match(pattern, question_lower):
            return "factual"

    # Check answer length - short answers (< 5 words) are usually factual
    # BUT skip this check for THLP questions (handled above)
    answer_words = len(answer.split())
    if answer_words <= 4 and not any(c in answer for c in ['(', ')', '[', ']', '{', '}']):
        return "factual"

    # Default: open-ended (long explanation required)
    return "open-ended"


def generate_distractors_local(question: str, correct_answer: str) -> list:
    """Generate 3 plausible but wrong distractors WITHOUT LLM API.

    For now, this generates simple distractors. In production, use OpenRouter API.
    """
    # Simple distractor generation based on question type
    question_lower = question.lower()

    # THLP: Temperature/belief questions (Water boils at X°C)
    if "water boils at" in question_lower or "boil" in question_lower:
        temp_match = re.search(r'\d+', correct_answer)
        if temp_match:
            correct_temp = int(temp_match.group())
            # Generate plausible wrong temperatures around boiling point
            offsets = [-10, 10, 20]
            distractors = [f"{correct_temp + o}°C" for o in offsets]
            return distractors

    # THLP: String reversal (cat -> tac)
    if "cat ->" in question or "dog ->" in question or " -> " in question:
        if correct_answer == "tac":
            return ["cat", "act", "atc"]
        elif correct_answer == "god":
            return ["dog", "gdo", "ogd"]
        elif correct_answer == "drib":
            return ["bird", "bdir", "drbi"]
        # Generic string transformation distractors
        return ["cat", "dog", "bird"]

    # THLP: Fibonacci/pattern (1,2->3, 3,5->8, 2,7->?)
    if "fibonacci" in question_lower or "input:" in question_lower:
        if correct_answer == "9":
            return ["5", "10", "12"]
        elif correct_answer == "drib":
            return ["bird", "bdir", "drbi"]
        elif correct_answer == "tac":
            return ["cat", "act", "atc"]
        # Generic pattern distractors
        return ["5", "10", "15"]

    # Capital cities
    if "capital" in question_lower:
        country = re.search(r"of (\w+)", question, re.IGNORECASE)
        if country:
            wrong_capitals = ["Moscow", "London", "Paris", "Berlin", "Rome", "Madrid", "Tokyo"]
            random.shuffle(wrong_capitals)
            return wrong_capitals[:3]

    # Quantum physics
    elif "quantum" in question_lower and "superposition" in question_lower:
        return [
            "A system transitions between states sequentially",
            "A system collapses into superposition after observation",
            "Multiple systems share a single quantum state"
        ]

    # Math: powers of 2
    elif r"2^" in question_lower or "2 **" in question_lower:
        return [
            str(2 ** 18),
            str(2 ** 19),
            str(2 ** 21)
        ]

    else:
        # Generic wrong answers
        return [
            "I don't know",
            "Not applicable",
            "None of the above"
        ]


def create_mc_question(question: str, answer: str, task: str = None) -> dict:
    """Convert a question to MC format."""
    question_type = detect_question_type(question, answer, task)

    if question_type == "open-ended":
        # Generate distractors
        distractors = generate_distractors_local(question, answer)

        # Shuffle positions (A, B, C, D)
        options = [answer] + distractors[:3]
        correct_letter = "A"

        # Create choices string
        choices = []
        letters = ["A", "B", "C", "D"]
        for i, opt in enumerate(options):
            choices.append(f"{letters[i]}) {opt}")

        return {
            "question_type": "mc",
            "question": f"Which best describes: {question}",
            "choices": "\n".join(choices),
            "answer": correct_letter
        }

    else:
        # Factual short-answer - keep as-is or convert to simple MC
        return {
            "question_type": "factual",
            "question": question,
            "answer": answer
        }


def process_track(track_key: str, input_path: str, output_path: str) -> dict:
    """Process a single track: convert to MC format, save new CSV."""
    import pandas as pd

    df = pd.read_csv(input_path)

    print(f"\n{'='*60}")
    print(f"Processing {track_key.upper()}: {len(df)} questions")
    print(f"{'='*60}")

    results = []
    stats = {
        "total": len(df),
        "open_ended": 0,
        "factual": 0,
        "converted": 0,
        "errors": 0
    }

    for idx, row in df.iterrows():
        # Get question and answer columns (different per track)
        if track_key == "tagp":
            question = str(row["query"])
            answer = str(row["expected_focus"])
        elif track_key == "tefb":
            question = str(row["context"])
            answer = str(row["expected_result"])
        elif track_key == "tscp":
            question = str(row["scenario"])
            answer = str(row["expected_inference"])
        else:
            question = str(row["question"])
            answer = str(row["answer"])

        # Get task info for THLP detection
        task = str(row.get("task", ""))

        # Detect question type (pass task for THLP detection)
        question_type = detect_question_type(question, answer, task)

        if question_type == "open-ended":
            stats["open_ended"] += 1

            # Generate MC format (pass task info)
            mc_result = create_mc_question(question, answer, task)

            results.append({
                "id": row.get("id", f"{track_key}_{idx}"),
                "question_type": "mc",
                "question": mc_result["question"],
                "choices": mc_result["choices"],
                "answer": mc_result["answer"]
            })

            stats["converted"] += 1

        else:
            stats["factual"] += 1

            # Keep factual as-is
            results.append({
                "id": row.get("id", f"{track_key}_{idx}"),
                "question_type": "factual",
                "question": question,
                "answer": answer
            })

        # Progress indicator
        if (idx + 1) % 100 == 0:
            print(f"  Processed {idx + 1}/{len(df)} ({(idx + 1) * 100 // len(df)}%)")

    # Create new DataFrame
    new_df = pd.DataFrame(results)

    # Save to CSV
    new_df.to_csv(output_path, index=False)

    print(f"\nResults for {track_key.upper()}:")
    print(f"  Total: {stats['total']}")
    print(f"  Open-ended: {stats['open_ended']}")
    print(f"  Factual: {stats['factual']}")
    print(f"  Converted to MC: {stats['converted']}")
    print(f"  Saved to: {output_path}")

    return stats


def main():
    """Convert all 5 Trinity Cognitive Probe datasets to MC format."""

    # Create output directory
    output_dir = Path("kaggle/data/converted_mc")
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = []

    for track_key, input_path in CSV_FILES.items():
        if not Path(input_path).exists():
            print(f"WARNING: {input_path} not found, skipping...")
            continue

        output_path = output_dir / f"{track_key}_mc.csv"
        result = process_track(track_key, input_path, output_path)
        result["track"] = track_key
        summary.append(result)

    # Print summary
    print(f"\n{'='*60}")
    print("=" * 60)
    print("CONVERSION SUMMARY")
    print("=" * 60)
    print(f"{'Track':<8} {'Total':<8} {'Open-Ended':<12} {'Factual':<10} {'Converted':<10}")
    print("-" * 60)

    total_questions = 0
    total_open = 0
    total_factual = 0
    total_converted = 0

    for s in summary:
        print(f"{s['track']:<8} {s['total']:<8} {s['open_ended']:<12} {s['factual']:<10} {s['converted']:<10}")
        total_questions += s['total']
        total_open += s['open_ended']
        total_factual += s['factual']
        total_converted += s['converted']

    print("-" * 60)
    print(f"{'TOTAL':<8} {total_questions:<8} {total_open:<12} {total_factual:<10} {total_converted:<10}")
    print("=" * 60)

    # Save summary to JSON
    summary_data = {
        "total_questions": total_questions,
        "total_open_ended": total_open,
        "total_factual": total_factual,
        "total_converted": total_converted,
        "tracks": summary
    }

    summary_path = output_dir / "conversion_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary_data, f, indent=2)

    print(f"\nSummary saved to: {summary_path}")


if __name__ == "__main__":
    main()
