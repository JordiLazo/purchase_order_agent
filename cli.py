"""Batch processing from the terminal.

    python cli.py email/*.eml          # process files and print a summary
    python cli.py --reset email/*.eml  # start from an empty database
"""
import argparse
from pathlib import Path

from po_agent import storage
from po_agent.pipeline import process_email


def main():
    parser = argparse.ArgumentParser(description="Process purchase requisition emails")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--reset", action="store_true", help="clear the database first")
    args = parser.parse_args()

    conn = storage.connect()
    if args.reset:
        storage.reset(conn)

    for path in sorted(args.files):
        req_id = process_email(path.read_bytes(), path.name)
        req = storage.get_requisition(conn, req_id)
        res = req["result"] or {}
        chf = f"{res['total_chf']:>12,.2f} CHF" if res.get("total_chf") is not None else " " * 16
        chain = " -> ".join(s["approver_name"] for s in res.get("approval_chain", []))
        print(f"#{req_id:<3} {path.name:<34} {req['status']:<20} {chf}  {chain}")
        for issue in res.get("issues", []):
            if issue["level"] != "warn":
                print(f"      [{issue['level']}] {issue['message']}")


if __name__ == "__main__":
    main()
