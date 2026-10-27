"""Small locked JSON queue. Metadata only; no product or runtime imports."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "docs/INTEGRATION_QUEUE.json"
FIELDS = {"id", "kind", "feature", "owner_thread", "summary", "source", "parent",
          "evidence", "test_ready", "created"}
STATUSES = ("queued", "in_progress", "blocked", "superseded")


class QueueError(Exception):
    pass


@contextmanager
def file_lock(path, timeout=30):
    """Permanent sibling inode; OS releases its byte lock on process exit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"\0")
            handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise QueueError("queue lock timed out")
                time.sleep(0.05)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def validate_item(item):
    for key in FIELDS - {"created", "evidence", "test_ready"}:
        if not isinstance(item.get(key), str) or not item[key].strip():
            raise QueueError(f"{key} must be a nonempty string")
    if item["kind"] not in ("integration", "test_result"):
        raise QueueError("kind must be integration or test_result")
    if not isinstance(item.get("evidence"), list) or any(
            not isinstance(value, str) for value in item["evidence"]):
        raise QueueError("evidence must be a list of path references")
    if type(item.get("test_ready")) is not bool:
        raise QueueError("test_ready must be a boolean")
    if not isinstance(item.get("created"), str) or not item["created"].strip():
        raise QueueError("created must be a timestamp string")


class IntegrationQueue:
    def __init__(self, path=DEFAULT_PATH):
        self.path = Path(path)
        self.lock_path = self.path.with_name(self.path.name + ".lock")

    def _read(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise QueueError("queue missing; run init first")
        except (ValueError, UnicodeError) as exc:
            raise QueueError(f"invalid queue JSON: {exc}")
        if (not isinstance(data, dict) or data.get("schema_version") not in (1, 2)
                or type(data.get("revision")) is not int or data["revision"] < 0
                or not isinstance(data.get("items"), list)):
            raise QueueError("invalid queue header")
        ids, active = set(), []
        for item in data["items"]:
            if not isinstance(item, dict):
                raise QueueError("invalid item")
            validate_item(item)
            if item["id"] in ids or item.get("status") not in STATUSES:
                raise QueueError("duplicate id or invalid status")
            if item["status"] == "superseded":
                if item.get("superseded_from") not in ("queued", "blocked") or any(
                        not isinstance(item.get(key), str) or not item[key].strip()
                        for key in ("superseded_by", "superseded_reason", "superseded_at")):
                    raise QueueError("invalid superseded metadata")
            ids.add(item["id"])
            if item["status"] == "in_progress":
                active.append(item["id"])
                if data["schema_version"] == 2 and (
                        not isinstance(item.get("claimed_by"), str)
                        or not item["claimed_by"].strip()):
                    raise QueueError("in_progress item requires claimed_by")
        if data["schema_version"] == 1:
            if "active_id" not in data:
                raise QueueError("legacy queue requires active_id")
            expected = [] if data["active_id"] is None else [data["active_id"]]
            if active != expected:
                raise QueueError("legacy active_id must match its in_progress item")
            # Read compatibility only. Next successful mutation persists v2 atomically.
            data.pop("active_id")
            data["schema_version"] = 2
            for item in data["items"]:
                if item["status"] == "in_progress":
                    item.setdefault("claimed_by", "root")
        return data

    def _write(self, data):
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                             dir=self.path.parent, delete=False,
                                             prefix=self.path.name + ".", suffix=".tmp") as out:
                name = out.name
                json.dump(data, out, ensure_ascii=False, indent=2)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())
            os.replace(name, self.path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    def init(self):
        with file_lock(self.lock_path):
            if self.path.exists():
                return self._read()
            data = {"schema_version": 2, "revision": 0, "items": []}
            self._write(data)
            return data

    def snapshot(self):
        with file_lock(self.lock_path):
            return self._read()

    @staticmethod
    def _supersede(item, by, reason):
        if item["status"] == "in_progress":
            raise QueueError("supersede requires queued or blocked status; release item first")
        if item["status"] not in ("queued", "blocked"):
            raise QueueError("item is superseded; restore item first")
        for key, value in (("by", by), ("reason", reason)):
            if not isinstance(value, str) or not value.strip():
                raise QueueError(f"supersede requires a nonempty {key}")
        item["superseded_from"] = item["status"]
        item["status"] = "superseded"
        item["superseded_by"] = by
        item["superseded_reason"] = reason
        item["superseded_at"] = datetime.now(timezone.utc).isoformat()

    def enqueue(self, payload, supersedes=None):
        if not isinstance(payload, dict) or set(payload) - FIELDS:
            raise QueueError("enqueue accepts only documented item fields")
        if supersedes is not None and (
                not isinstance(supersedes, str) or not supersedes.strip()):
            raise QueueError("supersedes must be a nonempty item id")
        with file_lock(self.lock_path):
            data = self._read()
            old = next((x for x in data["items"] if x["id"] == payload.get("id")), None)
            item = dict(payload)
            item.setdefault("created", old["created"] if old else
                            datetime.now(timezone.utc).isoformat())
            item.setdefault("evidence", [])
            item.setdefault("test_ready", False)
            validate_item(item)
            target = None
            if supersedes is not None:
                target = next((x for x in data["items"] if x["id"] == supersedes), None)
                if target is None:
                    raise QueueError("supersedes item not found")
                if target["status"] == "in_progress":
                    raise QueueError("supersede requires queued or blocked status; release item first")
            if old:
                if item != {key: old[key] for key in FIELDS}:
                    raise QueueError("id already exists with different content")
                if target is not None and not (
                        target["status"] == "superseded"
                        and target["superseded_by"] == old["id"]):
                    raise QueueError("id already exists; enqueue a new id to supersede another item")
                return old
            if target is not None:
                self._supersede(target, item["id"], f"Replaced by {item['id']}")
            item["status"] = "queued"
            data["items"].append(item)
            data["revision"] += 1
            self._write(data)
            return item

    def supersede(self, item_id, by, reason):
        return self.transition("supersede", item_id, reason=reason, by=by)

    def restore(self, item_id):
        return self.transition("restore", item_id)

    def transition(self, command, item_id=None, reason=None, worker="root", by=None):
        with file_lock(self.lock_path):
            data = self._read()
            if command == "claim":
                if not isinstance(worker, str) or not worker.strip():
                    raise QueueError("claim requires a nonempty worker name")
                if item_id is None:
                    item_id = next((x["id"] for x in data["items"]
                                    if x["status"] == "queued"), None)
            item = next((x for x in data["items"] if x["id"] == item_id), None)
            if item is None:
                raise QueueError("item not found (or no queued item)")
            if item["status"] == "superseded" and command != "restore":
                raise QueueError("item is superseded; restore item first")
            if command == "claim":
                if item["status"] != "queued":
                    raise QueueError("claim requires queued status; release blocked item first")
                item["status"] = "in_progress"
                item["claimed_by"] = worker
            elif command == "complete":
                if item["status"] != "in_progress":
                    raise QueueError("complete requires an in_progress item")
                data["items"].remove(item)
            elif command == "hold":
                if not isinstance(reason, str) or not reason.strip():
                    raise QueueError("hold requires a reason")
                item["status"] = "blocked"
                item["reason"] = reason
                item.pop("claimed_by", None)
            elif command == "release":
                if item["status"] not in ("in_progress", "blocked"):
                    raise QueueError("release requires active or blocked status")
                item["status"] = "queued"
                item.pop("reason", None)
                item.pop("claimed_by", None)
            elif command == "supersede":
                self._supersede(item, by, reason)
            elif command == "restore":
                if item["status"] != "superseded":
                    raise QueueError("restore requires a superseded item")
                item["status"] = item["superseded_from"]
                for key in list(item):
                    if key.startswith("superseded_"):
                        del item[key]
            else:
                raise QueueError("unknown transition")
            data["revision"] += 1
            self._write(data)
            return item


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_PATH,
                        help="alternate path for isolated helper tests")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    enqueue = sub.add_parser("enqueue", help="read one item JSON object from stdin")
    enqueue.add_argument("--supersedes", help="atomically supersede this queued/blocked item")
    listing = sub.add_parser("list")
    listing.add_argument("--limit", type=int, default=20)
    listing.add_argument("--status", choices=STATUSES, help="filter items by exact status")
    for command in ("show", "claim", "complete", "hold", "release", "supersede", "restore"):
        child = sub.add_parser(command)
        child.add_argument("id", nargs="?" if command == "claim" else None)
        if command in ("hold", "supersede"):
            child.add_argument("--reason", required=True)
        if command == "supersede":
            child.add_argument("--by", required=True, help="replacement ID, path or description")
        if command == "claim":
            child.add_argument("--worker", default="root", help="root-assigned worker name")
    args = parser.parse_args(argv)
    queue = IntegrationQueue(args.queue)
    try:
        if args.command == "init":
            result = queue.init()
        elif args.command == "enqueue":
            result = queue.enqueue(json.load(sys.stdin), supersedes=args.supersedes)
        elif args.command in ("list", "show"):
            data = queue.snapshot()
            if args.command == "show":
                result = next((x for x in data["items"] if x["id"] == args.id), None)
                if result is None:
                    raise QueueError("item not found")
            else:
                if not 1 <= args.limit <= 100:
                    raise QueueError("limit must be between 1 and 100")
                result = {"revision": data["revision"],
                          "active_ids": [x["id"] for x in data["items"]
                                         if x["status"] == "in_progress"]}
                result["total"] = len(data["items"])
                result["counts"] = {status: sum(x["status"] == status for x in data["items"])
                                    for status in STATUSES}
                items = [x for x in data["items"] if
                         (x["status"] == args.status if args.status else
                          x["status"] != "superseded")]
                result["items"] = [{key: str(x.get(key, ""))[:160] for key in
                                    ("id", "kind", "feature", "status", "claimed_by", "summary")}
                                   for x in items[:args.limit]]
        else:
            result = queue.transition(args.command, args.id, getattr(args, "reason", None),
                                      worker=getattr(args, "worker", "root"),
                                      by=getattr(args, "by", None))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (QueueError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
