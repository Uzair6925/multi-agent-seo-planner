import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from tempfile import TemporaryDirectory
from pathlib import Path
from uuid import uuid4
from .security import validate_upload


class Job:
    def __init__(self):
        self.id = uuid4().hex[:10]
        self.events = Queue()
        self.cancel = threading.Event()
        self.future = None
        self.started = time.monotonic()

    def progress(self, stage, message):
        self.events.put((stage, message))


class JobManager:
    """One active generation per server protects the shared provider quota and CPU."""
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="seo-planner")
        self.slot = threading.Lock()

    def submit(self, payload, uploads, key):
        if not self.slot.acquire(blocking=False):
            raise ValueError("The service is handling another request. Please try again shortly.")
        job = Job()
        try:
            job.future = self.pool.submit(self._work, job, payload, uploads, key)
        except Exception:
            self.slot.release()
            raise
        return job

    def _work(self, job, payload, uploads, key):
        try:
            from .engine import generate
            with TemporaryDirectory(prefix="seo-planner-") as tmp:
                folder = Path(tmp)
                request = dict(payload)
                request["files"] = []
                total = sum(len(u["data"]) for u in uploads)
                if len(uploads) > 5 or total > 20 * 1024 * 1024:
                    raise ValueError("Upload at most five files, totalling 20 MB.")
                for i, upload in enumerate(uploads):
                    suffix = validate_upload(upload["name"], upload["data"])
                    target = folder / f"reference_{i + 1}{suffix}"
                    target.write_bytes(upload["data"])
                    request["files"].append({"path": str(target), "role": upload["role"]})
                return asyncio.run(generate(request, key, folder, job.progress, job.cancel))
        finally:
            self.slot.release()
