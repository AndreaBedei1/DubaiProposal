"""Record and replay sonar frames.

Recording every LOCATE-phase frame lets the detector be developed, tuned and
unit-tested offline (no HoloOcean, no GPU): the recorded directory is both
the evaluation dataset and the pytest fixture source.

Layout of a recording directory:

    frames/000000.npz   (image float32 + json-encoded meta string)
    frames/000001.npz
    ...
    recording.json      (global metadata, written on close)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, List, Optional, Union

import numpy as np

from .sonar_types import SonarFrame


class SonarRecorder:
    def __init__(self, out_dir: Union[str, Path], meta: Optional[dict] = None):
        self.out_dir = Path(out_dir)
        (self.out_dir / "frames").mkdir(parents=True, exist_ok=True)
        self._n = 0
        self._meta = dict(meta or {})

    def add(self, frame: SonarFrame) -> None:
        path = self.out_dir / "frames" / f"{self._n:06d}.npz"
        np.savez_compressed(path, image=frame.image.astype(np.float32),
                            meta=json.dumps(frame.to_meta()))
        self._n += 1

    @property
    def n_frames(self) -> int:
        return self._n

    def close(self) -> None:
        self._meta["n_frames"] = self._n
        (self.out_dir / "recording.json").write_text(
            json.dumps(self._meta, indent=2), encoding="utf-8")

    def __enter__(self) -> "SonarRecorder":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class SonarReplay:
    """Iterate the frames of a recording in order, without a simulator."""

    def __init__(self, rec_dir: Union[str, Path]):
        self.rec_dir = Path(rec_dir)
        self._paths: List[Path] = sorted((self.rec_dir / "frames").glob("*.npz"))
        if not self._paths:
            raise FileNotFoundError(f"no recorded frames under {self.rec_dir}")
        meta_path = self.rec_dir / "recording.json"
        self.meta = json.loads(meta_path.read_text(encoding="utf-8")) \
            if meta_path.exists() else {}

    def __len__(self) -> int:
        return len(self._paths)

    def __iter__(self) -> Iterator[SonarFrame]:
        for path in self._paths:
            yield self.load(path)

    @staticmethod
    def load(path: Union[str, Path]) -> SonarFrame:
        with np.load(path, allow_pickle=False) as data:
            image = np.asarray(data["image"], dtype=np.float32)
            meta = json.loads(str(data["meta"]))
        return SonarFrame.from_meta(image, meta)
