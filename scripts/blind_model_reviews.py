#!/usr/bin/env python3
"""Create a blinded review packet or convert reviewed packets back to runner format."""
import argparse
import hashlib
import json
import os
import secrets
from pathlib import Path


def item_hash(item):
    fields = ("blind_id", "question", "context", "answer", "expected_answer", "expected_abstention", "supporting_evidence", "status")
    text = json.dumps({k: item[k] for k in fields}, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def write_new(path, data, mode=0o600):
    # Never overwrite a user's previous review or mapping.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def export(results, packet, key):
    rows = json.loads(Path(results).read_text())["rows"]
    if len({(r["case_id"], r["model_key"], r["repeat"]) for r in rows}) != len(rows):
        raise ValueError("Duplicate result identity")
    items, mapping = [], {}
    for row in rows:
        if row["status"] not in ("completed", "partial", "no_evidence"):
            continue
        blind_id = secrets.token_hex(16)
        item = {"blind_id": blind_id, "question": row["question"], "context": row["context"],
                      "answer": row["answer"], "expected_answer": row["expected_answer"],
                      "expected_abstention": row["expected_abstention"], "supporting_evidence": row["supporting_evidence"],
                      "status": row["status"], "reviewer": None, "correctness_human": None,
                      "abstention_correct_human": None, "claim_review": [], "notes": ""}
        mapping[blind_id] = {**{k: row[k] for k in ("case_id", "model_key", "repeat")}, "item_sha256": item_hash(item)}
        items.append(item)
    secrets.SystemRandom().shuffle(items)
    if Path(packet).exists() or Path(key).exists():
        raise ValueError("Output already exists")
    if Path(packet).resolve() == Path(key).resolve():
        raise ValueError("Packet and mapping must be different files")
    write_new(key, mapping)
    try:
        write_new(packet, items)
    except Exception:
        Path(key).unlink(missing_ok=True)
        raise
    return len(items)


def convert(reviewed, key, output):
    items = json.loads(Path(reviewed).read_text())
    mapping = json.loads(Path(key).read_text())
    seen = set()
    result = []
    for item in items:
        blind_id = item["blind_id"]
        if blind_id not in mapping or blind_id in seen:
            raise ValueError("Unknown or duplicated blind ID")
        if item_hash(item) != mapping[blind_id]["item_sha256"]:
            raise ValueError("Reviewed question, evidence, or answer was altered")
        seen.add(blind_id)
        identity = {k: mapping[blind_id][k] for k in ("case_id", "model_key", "repeat")}
        result.append({**identity, "reviewer": item.get("reviewer"),
                       "correctness_human": item.get("correctness_human"),
                       "abstention_correct_human": item.get("abstention_correct_human"),
                       "claim_review": item.get("claim_review", []), "review_notes": item.get("notes", "")})
    if seen != set(mapping):
        raise ValueError("Review packet does not contain every blind ID")
    write_new(output, result)
    return len(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    exp = subs.add_parser("export")
    exp.add_argument("results")
    exp.add_argument("packet")
    exp.add_argument("private_key")
    imp = subs.add_parser("import")
    imp.add_argument("reviewed_packet")
    imp.add_argument("private_key")
    imp.add_argument("reviews_output")
    args = parser.parse_args()
    try:
        if args.action == "export":
            count = export(args.results, args.packet, args.private_key)
        else:
            count = convert(args.reviewed_packet, args.private_key, args.reviews_output)
        print(f"Processed {count} review items.")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"Review operation stopped: {exc}\n")


if __name__ == "__main__":
    main()
