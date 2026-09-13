"""Silent per-session recorder for Geology Vision live tours.

Every live session (camera frames + spoken transcripts that already flow through
the vision endpoints) is persisted under ``data/uploads/vision_videos/<session>/``
with:

    session.json       — session metadata (start/end, ambient hints, counts)
    transcript.jsonl   — ordered user/assistant spoken lines
    frames/00001.jpg   — throttled, deduplicated camera frames (~2 fps)
    video.mp4          — assembled from frames when ffmpeg is available

This module is intentionally internal: nothing about it is surfaced in the UI.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

logger = logging.getLogger("ai_os.vision_recorder")

MIN_FRAME_GAP = 0.25          # seconds between frame captures at most
MAX_OPEN_IDLE = 15 * 60       # an idle live session older than this is closed
VIDEO_FPS = 2


def _ffmpeg_binary() -> str | None:
    """Return a usable ffmpeg binary, or None when unavailable."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


class VisionLiveRecorder:
    """Thread-safe file-backed recorder keyed by client-generated session ids."""

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._sessions: dict[str, dict] = {}
        self._ffmpeg = None
        self._reaper_started = False

    # ── helpers ──────────────────────────────────────────────────────────
    def _session_root(self, session_id: str) -> Path:
        return self.base_dir / session_id

    def _open(self, session_id: str) -> dict:
        with self._lock:
            sess = self._sessions.get(session_id)
            if sess is not None:
                sess["last_seen"] = time.time()
                return sess
            root = self._session_root(session_id)
            root.mkdir(parents=True, exist_ok=True)
            (root / "frames").mkdir(parents=True, exist_ok=True)
            started = time.time()
            sess = {
                "id": session_id,
                "root": root,
                "started": started,
                "last_seen": started,
                "ambient": "",
                "frame_count": 0,
                "transcript_count": 0,
                "finalized": False,
                "last_frame_ts": 0.0,
                "last_frame_hash": "",
            }
            self._sessions[session_id] = sess
            self._write_session_json(sess)
            self._ensure_reaper()
            logger.info("Vision live session opened: %s", session_id[:12])
            return sess

    def _append(self, sess: dict, line: dict) -> None:
        with self._lock:
            line.setdefault("t", round(time.time(), 3))
            with (sess["root"] / "transcript.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
            sess["transcript_count"] += 1

    def _write_session_json(self, sess: dict) -> None:
        payload = {
            "session_id": sess["id"],
            "started_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(sess["started"])),
            "started_epoch": sess["started"],
            "ambient": sess.get("ambient", ""),
            "frames": sess["frame_count"],
            "transcript_lines": sess["transcript_count"],
            "video": None,
            "finalized": sess["finalized"],
        }
        tmp = sess["root"] / "session.json.tmp"
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(sess["root"] / "session.json")

    def _close(self, session_id: str) -> None:
        with self._lock:
            sess = self._sessions.pop(session_id, None)
            if sess is None or sess["finalized"]:
                return
            sess["finalized"] = True
        try:
            self._assemble_video(sess)
        except Exception as e:  # pragma: no cover - best effort
            logger.warning("Vision live video assembly failed: %s", e)
        sess["ended_epoch"] = time.time()
        self._write_session_json(sess)
        logger.info("Vision live session closed: %s (%d frames)", session_id[:12], sess["frame_count"])

    def _assemble_video(self, sess: dict) -> None:
        frames_dir = sess["root"] / "frames"
        if sess["frame_count"] < 2:
            return
        if self._ffmpeg is None:
            self._ffmpeg = _ffmpeg_binary()
        if not self._ffmpeg:
            return
        out = sess["root"] / "video.mp4"
        cmd = [
            self._ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", str(VIDEO_FPS),
            "-i", str(frames_dir / "%05d.jpg"),
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            str(out),
        ]
        try:
            subprocess.run(cmd, timeout=600, check=True)
        except FileNotFoundError:
            # Guarded by _ffmpeg_binary; should not happen.
            self._ffmpeg = None
            return
        except subprocess.CalledProcessError as e:
            logger.warning("ffmpeg failed for session %s: %s", sess["id"][:12], e)
            return
        if out.exists() and out.stat().st_size > 0:
            sess["video"] = f"{sess['id']}/video.mp4"
            self._write_session_json(sess)

    def _ensure_reaper(self) -> None:
        if self._reaper_started:
            return
        self._reaper_started = True
        t = threading.Thread(target=self._reaper_loop, name="vision-recorder-reaper", daemon=True)
        t.start()

    def _reaper_loop(self) -> None:
        while True:
            time.sleep(300)
            try:
                with self._lock:
                    ids = [
                        sid for sid, s in self._sessions.items()
                        if time.time() - s["last_seen"] > MAX_OPEN_IDLE
                    ]
                for sid in ids:
                    self._close(sid)
            except Exception:
                logger.exception("Vision recorder reaper error")

    # ── public API ───────────────────────────────────────────────────────
    def start(self, session_id: str, ambient: str = "") -> None:
        if not session_id:
            return
        sess = self._open(session_id)
        ambient = (ambient or "").strip()[:200]
        if ambient and ambient != sess["ambient"]:
            sess["ambient"] = ambient
            self._write_session_json(sess)

    def user(self, session_id: str, text: str) -> None:
        if not session_id or not (text or "").strip():
            return
        with self._lock:
            sess = self._sessions.get(session_id)
            if sess is None:
                sess = self._open(session_id)
        self._append(sess, {"role": "user", "text": text})

    def assistant(self, session_id: str, text: str) -> None:
        if not session_id or not (text or "").strip():
            return
        with self._lock:
            sess = self._sessions.get(session_id)
            if sess is None:
                sess = self._open(session_id)
        self._append(sess, {"role": "assistant", "text": text})

    def frame(self, session_id: str, jpeg: bytes, ts: float | None = None) -> None:
        if not session_id or not jpeg:
            return
        ts = ts or time.time()
        with self._lock:
            sess = self._sessions.get(session_id)
            if sess is None:
                sess = self._open(session_id)
            if ts - sess["last_frame_ts"] < MIN_FRAME_GAP:
                return
            import hashlib  # local import keeps import cost off request path

            digest = hashlib.md5(jpeg).hexdigest()
            if jpeg and digest == sess["last_frame_hash"]:
                sess["last_frame_ts"] = ts
                return
            n = sess["frame_count"] + 1
            (sess["root"] / "frames" / f"{n:05d}.jpg").write_bytes(jpeg)
            sess["frame_count"] = n
            sess["last_frame_ts"] = ts
            sess["last_frame_hash"] = digest
            sess["last_seen"] = ts

    def close(self, session_id: str) -> None:
        if session_id:
            self._close(session_id)

    def close_all(self) -> None:
        with self._lock:
            ids = list(self._sessions.keys())
        for sid in ids:
            self._close(sid)