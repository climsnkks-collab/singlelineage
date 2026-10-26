"""Isolated metadata tests; never access the project's real queue or runtime."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import integration_queue
from integration_queue import IntegrationQueue, QueueError

SCRIPT = Path(__file__).with_name("integration_queue.py")


def payload(item_id):
    return {"id": item_id, "kind": "integration", "feature": "TEST",
            "owner_thread": "isolated-test", "summary": "completed source",
            "source": "references/source.json", "parent": "exact-parent-123",
            "evidence": ["references/HANDOFF.md"], "test_ready": True}


class QueueTests(unittest.TestCase):
    def setUp(self):
        # Windows' restrictive mode 0o700 DACL can exclude the sandbox token.
        # Inherit the allowed temp parent's ACL for fixtures; queue I/O stays real.
        mkdir = os.mkdir
        with patch.object(os, "mkdir", side_effect=lambda path, mode=0o777:
                          mkdir(path, 0o777 if os.name == "nt" else mode)):
            self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "queue.json"
        self.queue = IntegrationQueue(self.path)
        self.queue.init()

    def cli(self, *args, item=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--queue", str(self.path), *args],
            input=json.dumps(item) if item is not None else None,
            capture_output=True, text=True, encoding="utf-8", timeout=30)

    def assert_unchanged_error(self, message, action):
        before = self.path.read_bytes()
        revision = json.loads(before)["revision"]
        with self.assertRaisesRegex(QueueError, message):
            action()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.queue.snapshot()["revision"], revision)

    def test_supersede_preserves_item_metadata_and_restores_prior_status(self):
        for prior in ("queued", "blocked"):
            with self.subTest(prior=prior):
                self.queue.enqueue(payload(prior))
                if prior == "blocked":
                    self.queue.transition("hold", prior, "original hold reason")
                before = self.queue.snapshot()
                original = next(x for x in before["items"] if x["id"] == prior)
                result = self.queue.supersede(prior, "replacement/path or description", "obsolete source")
                self.assertEqual(result["status"], "superseded")
                self.assertEqual(result["superseded_from"], prior)
                self.assertEqual(result["superseded_by"], "replacement/path or description")
                self.assertEqual(result["superseded_reason"], "obsolete source")
                timestamp = datetime.fromisoformat(result["superseded_at"])
                self.assertEqual(timestamp.utcoffset(), timezone.utc.utcoffset(timestamp))
                self.assertEqual({key: result[key] for key in original if key != "status"},
                                 {key: value for key, value in original.items() if key != "status"})
                self.assertEqual(self.queue.snapshot()["revision"], before["revision"] + 1)
                restored = self.queue.restore(prior)
                self.assertEqual(restored, original)
                self.assertFalse(any(key.startswith("superseded_") for key in restored))
                self.assertEqual(self.queue.snapshot()["revision"], before["revision"] + 2)

    def test_supersede_invalid_inputs_and_statuses_preserve_bytes(self):
        self.queue.enqueue(payload("a"))
        for by, reason in (("", "reason"), ("  ", "reason"), (None, "reason"),
                           ("b", ""), ("b", " \t"), ("b", None)):
            self.assert_unchanged_error("nonempty", lambda: self.queue.supersede("a", by, reason))
        self.assert_unchanged_error("not found", lambda: self.queue.supersede("missing", "b", "reason"))
        self.assert_unchanged_error("superseded item", lambda: self.queue.restore("a"))
        self.queue.transition("claim", "a", worker="assigned")
        self.assert_unchanged_error("release item first", lambda: self.queue.supersede("a", "b", "reason"))
        self.queue.transition("release", "a")
        self.queue.supersede("a", "b", "reason")
        for command in ("claim", "complete", "hold", "release", "supersede"):
            self.assert_unchanged_error(
                "restore item first",
                lambda: self.queue.transition(command, "a", reason="new reason", by="c"))

    def test_enqueue_supersedes_is_one_locked_write_and_one_revision(self):
        self.queue.enqueue(payload("old"))
        self.queue.transition("hold", "old", "existing reason")
        before = self.queue.snapshot()
        with patch.object(integration_queue, "file_lock", wraps=integration_queue.file_lock) as lock, \
                patch.object(self.queue, "_write", wraps=self.queue._write) as write:
            result = self.queue.enqueue(payload("new"), supersedes="old")
        self.assertEqual(lock.call_count, 1)
        self.assertEqual(write.call_count, 1)
        state = self.queue.snapshot()
        self.assertEqual(state["revision"], before["revision"] + 1)
        self.assertEqual(result["id"], "new")
        old, new = state["items"]
        self.assertEqual(old["status"], "superseded")
        self.assertEqual(old["superseded_by"], "new")
        self.assertEqual(old["superseded_reason"], "Replaced by new")
        self.assertEqual(old["superseded_from"], "blocked")
        self.assertEqual(old["reason"], "existing reason")
        self.assertEqual(new, result)
        before_retry = self.path.read_bytes()
        self.assertEqual(self.queue.enqueue(payload("new"), supersedes="old"), result)
        self.assertEqual(self.path.read_bytes(), before_retry)

    def test_enqueue_supersedes_failures_leave_no_new_item_or_revision(self):
        self.queue.enqueue(payload("active"))
        self.queue.transition("claim", "active")
        self.queue.enqueue(payload("existing"))
        self.queue.enqueue(payload("queued"))
        self.queue.enqueue(payload("replaced"))
        self.queue.supersede("replaced", "other", "old reason")
        for new_id in ("new", "existing"):
            for target, message in (("missing", "not found"),
                                    ("active", "release item first")):
                self.assert_unchanged_error(
                    message, lambda: self.queue.enqueue(payload(new_id), supersedes=target))
        for target in ("queued", "replaced"):
            self.assert_unchanged_error(
                "id already exists", lambda: self.queue.enqueue(payload("existing"), supersedes=target))
        self.assert_unchanged_error(
            "restore item first", lambda: self.queue.enqueue(payload("new"), supersedes="replaced"))
        self.assert_unchanged_error(
            "nonempty", lambda: self.queue.enqueue(payload("new"), supersedes=" "))
        self.assert_unchanged_error(
            "different content", lambda: self.queue.enqueue(dict(payload("queued"), summary="changed")))

    def test_combined_enqueue_replace_failure_preserves_original_file(self):
        self.queue.enqueue(payload("old"))
        before = self.path.read_bytes()
        with patch.object(integration_queue.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                self.queue.enqueue(payload("new"), supersedes="old")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_cli_supersede_restore_enqueue_filter_counts_and_hints(self):
        for item_id in ("old", "queued", "blocked", "active"):
            self.queue.enqueue(payload(item_id))
        self.queue.transition("hold", "blocked", "waiting")
        self.queue.transition("claim", "active")
        result = self.cli("supersede", "old", "--by", "replacement/path", "--reason", "obsolete")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["superseded_by"], "replacement/path")
        default = json.loads(self.cli("list", "--limit", "1").stdout)
        self.assertEqual(default["total"], 4)
        self.assertEqual(default["counts"], {"queued": 1, "in_progress": 1, "blocked": 1, "superseded": 1})
        self.assertEqual(default["active_ids"], ["active"])
        self.assertEqual([x["id"] for x in default["items"]], ["queued"])
        for status, item_id in (("queued", "queued"), ("blocked", "blocked"),
                                ("in_progress", "active"), ("superseded", "old")):
            filtered = json.loads(self.cli("list", "--status", status).stdout)
            self.assertEqual([x["id"] for x in filtered["items"]], [item_id])
            self.assertEqual(filtered["counts"], default["counts"])
            self.assertEqual(filtered["total"], 4)
        self.assertEqual(json.loads(self.cli("show", "old").stdout)["status"], "superseded")
        before = self.path.read_bytes()
        for args, hint in ((("release", "old"), "restore item first"),
                           (("supersede", "active", "--by", "new", "--reason", "reason"), "release item first"),
                           (("supersede", "queued", "--by", " ", "--reason", "reason"), "nonempty"),
                           (("supersede", "queued", "--by", "new"), "--reason"),
                           (("supersede", "queued", "--reason", "reason"), "--by"),
                           (("list", "--status", "invalid"), "invalid choice")):
            result = self.cli(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(hint, result.stderr)
            self.assertEqual(self.path.read_bytes(), before)
        result = self.cli("restore", "old")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "queued")
        result = self.cli("enqueue", "--supersedes", "old", item=payload("new"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["id"], "new")
        self.assertEqual(self.queue.transition("claim")["id"], "queued")

    def test_legacy_supersede_migrates_only_after_successful_mutation(self):
        active = dict(payload("active"), created="2026-10-23T00:00:00+00:00", status="in_progress")
        queued = dict(payload("old"), created=active["created"], status="queued")
        legacy = {"schema_version": 1, "revision": 7, "active_id": "active", "items": [active, queued]}
        self.path.write_text(json.dumps(legacy), encoding="utf-8")
        before = self.path.read_bytes()
        self.queue.snapshot()
        self.assertEqual(self.path.read_bytes(), before)
        self.assert_unchanged_error("release item first", lambda: self.queue.supersede("active", "new", "reason"))
        self.assert_unchanged_error("not found", lambda: self.queue.enqueue(payload("new"), supersedes="missing"))
        with patch.object(self.queue, "_write", wraps=self.queue._write) as write:
            self.queue.enqueue(payload("new"), supersedes="old")
        self.assertEqual(write.call_count, 1)
        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(stored["schema_version"], 2)
        self.assertNotIn("active_id", stored)
        self.assertEqual(stored["revision"], 8)
        self.assertEqual(stored["items"][0], dict(active, claimed_by="root"))
        self.assertEqual(stored["items"][1]["status"], "superseded")
        self.assertEqual(self.queue.restore("old"), queued)

    def test_lifecycle_fifo_blocked_release_and_removal(self):
        for item_id in ("a", "b", "c"):
            self.queue.enqueue(payload(item_id))
        self.queue.transition("hold", "a", "waiting on a decision")
        self.assertEqual(self.queue.transition("claim")["id"], "b")
        self.queue.enqueue(payload("d"))  # writers may enqueue while root works
        with self.assertRaises(QueueError):
            self.queue.transition("claim", "b")
        with self.assertRaises(QueueError):
            self.queue.transition("complete", "c")
        self.queue.transition("release", "b")
        self.queue.transition("claim", "c")  # explicit root selection
        self.queue.transition("hold", "c", "dependency unresolved")
        self.assertFalse(any(x["status"] == "in_progress"
                             for x in self.queue.snapshot()["items"]))
        self.queue.transition("release", "a")
        self.assertEqual(self.queue.transition("claim")["id"], "a")
        self.queue.transition("complete", "a")
        state = self.queue.snapshot()
        self.assertEqual([x["id"] for x in state["items"]], ["b", "c", "d"])
        self.assertNotIn('"id": "a"', self.path.read_text(encoding="utf-8"))
        self.assertEqual(self.queue.init(), state)  # init never resets nonempty queue

    def test_idempotency_and_conflict_preserve_bytes(self):
        item = payload("a")
        self.queue.enqueue(item)
        self.queue.transition("claim", "a")
        before = self.path.read_bytes()
        self.assertEqual(self.queue.enqueue(item)["status"], "in_progress")
        self.assertEqual(self.path.read_bytes(), before)
        with self.assertRaises(QueueError):
            self.queue.enqueue(dict(item, parent="different-parent"))
        self.assertEqual(self.path.read_bytes(), before)

    def test_bad_input_and_corrupt_state_are_not_overwritten(self):
        before = self.path.read_bytes()
        with self.assertRaises(QueueError):
            self.queue.enqueue(dict(payload("a"), test_ready="false"))
        self.assertEqual(self.path.read_bytes(), before)
        self.path.write_text('{"broken": true}', encoding="utf-8")
        corrupt = self.path.read_bytes()
        with self.assertRaises(QueueError):
            self.queue.init()
        self.assertEqual(self.path.read_bytes(), corrupt)

    def test_concurrent_cli_enqueue_preserves_all_items(self):
        processes = []
        for index in range(12):
            process = subprocess.Popen(
                [sys.executable, str(SCRIPT), "--queue", str(self.path), "enqueue"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8")
            process.stdin.write(json.dumps(payload(f"p{index}")))
            process.stdin.close()
            process.stdin = None
            processes.append(process)
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, stderr)
        data = self.queue.snapshot()
        self.assertEqual({x["id"] for x in data["items"]}, {f"p{i}" for i in range(12)})
        self.assertEqual(data["revision"], 12)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_os_lock_released_when_process_terminates(self):
        code = ("import sys,time; sys.path.insert(0,sys.argv[1]); "
                "from integration_queue import file_lock; from pathlib import Path; "
                "lock=file_lock(Path(sys.argv[2])); lock.__enter__(); "
                "print('locked',flush=True); time.sleep(60)")
        holder = subprocess.Popen([sys.executable, "-u", "-c", code,
                                   str(SCRIPT.parent), str(self.queue.lock_path)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), "locked")
            contender = subprocess.Popen(
                [sys.executable, str(SCRIPT), "--queue", str(self.path), "list"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    contender.communicate(timeout=0.3)
                holder.terminate()
                holder.communicate(timeout=10)
                stdout, stderr = contender.communicate(timeout=10)
                self.assertEqual(contender.returncode, 0, stderr)
                self.assertEqual(json.loads(stdout)["total"], 0)
                self.queue.enqueue(payload("after-exit"))
            finally:
                if contender.poll() is None:
                    contender.kill()
                    contender.communicate()
        finally:
            if holder.poll() is None:
                holder.kill()
            holder.communicate()

    def test_cli_roundtrip_and_test_result(self):
        item = dict(payload("result"), kind="test_result", source="references/result.json")
        self.queue.enqueue(item)
        def run(*args):
            result = subprocess.run([sys.executable, str(SCRIPT), "--queue", str(self.path),
                                     *args], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertEqual(run("show", "result")["kind"], "test_result")
        self.assertEqual(run("claim")["id"], "result")
        run("complete", "result")
        self.assertEqual(run("list")["total"], 0)

    def test_parallel_claim_and_independent_mutations_with_enqueue(self):
        for index in range(6):
            self.queue.enqueue(payload(f"p{index}"))

        def start(*args, item=None):
            process = subprocess.Popen(
                [sys.executable, str(SCRIPT), "--queue", str(self.path), *args],
                stdin=subprocess.PIPE if item else subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8")
            if item:
                process.stdin.write(json.dumps(item))
                process.stdin.close()
                process.stdin = None
            return process

        def finish(process):
            stdout, stderr = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, stderr)
            return json.loads(stdout)

        claimed = [finish(p) for p in
                   [start("claim", "--worker", f"worker-{i}") for i in range(6)]]
        self.assertEqual({x["id"] for x in claimed}, {f"p{i}" for i in range(6)})
        self.assertEqual({x["claimed_by"] for x in claimed},
                         {f"worker-{i}" for i in range(6)})
        state = self.queue.snapshot()
        self.assertTrue(all(x["status"] == "in_progress" for x in state["items"]))
        # Concurrent operations must change only their own IDs, including completion
        # racing with new registrations and another worker's hold/release.
        processes = [start("complete", "p0"), start("complete", "p2"),
                     start("hold", "p1", "--reason", "decision"),
                     start("hold", "p3", "--reason", "dependency"),
                     start("release", "p4")]
        processes += [start("enqueue", item=payload(f"new{i}")) for i in range(8)]
        for process in processes:
            finish(process)
        state = self.queue.snapshot()
        items = {x["id"]: x for x in state["items"]}
        self.assertEqual(set(items), {"p1", "p3", "p4", "p5"}
                         | {f"new{i}" for i in range(8)})
        self.assertEqual(items["p1"]["status"], "blocked")
        self.assertEqual(items["p3"]["status"], "blocked")
        self.assertEqual(items["p4"]["status"], "queued")
        self.assertEqual(items["p5"], next(x for x in claimed if x["id"] == "p5"))
        self.assertEqual(state["revision"], 25)  # 6 enqueue + 6 claim + 13 mutations

    def test_legacy_active_survives_read_and_atomic_migration(self):
        active = dict(payload("legacy-active"), created="2026-10-23T00:00:00+00:00",
                      status="in_progress")
        queued = dict(payload("legacy-queued"), created=active["created"], status="queued")
        legacy = {"schema_version": 1, "revision": 7,
                  "active_id": active["id"], "items": [active, queued]}
        self.path.write_text(json.dumps(legacy), encoding="utf-8")
        before = self.path.read_bytes()
        snapshot = self.queue.snapshot()
        self.assertEqual(snapshot["items"][0], dict(active, claimed_by="root"))
        self.assertEqual(self.path.read_bytes(), before)  # readers never migrate disk
        self.queue.transition("claim", "legacy-queued", worker="second-worker")
        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(stored["schema_version"], 2)
        self.assertNotIn("active_id", stored)
        self.assertEqual(stored["revision"], 8)
        self.assertEqual(stored["items"][0], dict(active, claimed_by="root"))
        self.assertEqual(stored["items"][1], dict(queued, status="in_progress",
                                                claimed_by="second-worker"))


if __name__ == "__main__":
    unittest.main()
