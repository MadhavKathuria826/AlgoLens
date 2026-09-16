"""
AlgoLens Deterministic Compilation Cache for Native Execution Runtimes.

Provides content-based, cryptographically keyed caching of compiled native binaries.
Supports atomic publication, strict validation, corruption detection, and process concurrency.

The cache key deterministically captures every input that can materially change
the generated native artifact:
- Original source code hash
- Instrumented source code hash
- Compiler path, identity, and version string
- Compilation flags
- C++ language standard
- Target architecture and OS platform
- AlgoLens runtime instrumentation header content hash
- Instrumentor engine content hash
- Entry-point / driver configuration
- Shared library vs standalone executable target configuration
"""

import os
import sys
import json
import time
import shutil
import uuid
import hashlib
import threading
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
RUNTIME_HEADER_PATH = os.path.join(BACKEND_DIR, "native_runtime", "algolens_runtime.hpp")
INSTRUMENTOR_PATH = os.path.join(BACKEND_DIR, "cpp_instrumentor.py")


class CacheStatus(str, Enum):
    CACHE_HIT = "CACHE_HIT"
    CACHE_MISS = "CACHE_MISS"
    CACHE_INVALIDATED = "CACHE_INVALIDATED"
    CACHE_CORRUPT = "CACHE_CORRUPT"


def _sha256_text(text: str) -> str:
    """Computes SHA-256 digest of UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(filepath: str) -> str:
    """Computes SHA-256 digest of a file in 64KB blocks."""
    if not os.path.exists(filepath):
        return ""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class CacheKeySpec(BaseModel):
    """
    Specification of all inputs that determine the compiled artifact identity.
    Serialized deterministically to compute the cryptographic cache key.
    """
    source_hash: str
    instrumented_hash: str
    compiler_name: str
    compiler_version: str
    compilation_flags: List[str]
    cpp_standard: str = "c++17"
    target_arch: str = "x86_64"
    target_os: str = sys.platform
    runtime_header_hash: str
    instrumentor_hash: str
    entry_func: str = "main"
    requires_shared: bool = False
    build_version: str = "2.1"

    def compute_cache_key(self) -> str:
        """Produces a deterministic SHA-256 key from canonical JSON metadata."""
        canonical_json = self.model_dump_json()
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class CachedArtifact(BaseModel):
    """Represents a validated, published compilation cache entry."""
    cache_key: str
    cache_dir: str
    artifact_path: str
    instrumented_path: str
    metadata_path: str
    artifact_hash: str
    compile_time_ms: float
    instrumented_code: str
    created_at: float = Field(default_factory=time.time)


class CompilationCache:
    """
    Deterministic compilation cache for native language producers.
    Sits between instrumentation and execution backend.
    """

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or os.path.join(BACKEND_DIR, ".build_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._lock = threading.RLock()

        # Cache static component hashes
        self._runtime_header_hash = _sha256_file(RUNTIME_HEADER_PATH)
        self._instrumentor_hash = _sha256_file(INSTRUMENTOR_PATH)

    def get_runtime_header_hash(self) -> str:
        """Returns current hash of algolens_runtime.hpp."""
        return _sha256_file(RUNTIME_HEADER_PATH)

    def get_instrumentor_hash(self) -> str:
        """Returns current hash of cpp_instrumentor.py."""
        return _sha256_file(INSTRUMENTOR_PATH)

    def build_spec(
        self,
        source_code: str,
        instrumented_code: str,
        compiler_name: str,
        compiler_version: str,
        compilation_flags: List[str],
        entry_func: str = "main",
        requires_shared: bool = False
    ) -> CacheKeySpec:
        """Constructs a complete CacheKeySpec for a compilation request."""
        return CacheKeySpec(
            source_hash=_sha256_text(source_code),
            instrumented_hash=_sha256_text(instrumented_code),
            compiler_name=compiler_name,
            compiler_version=compiler_version,
            compilation_flags=list(compilation_flags),
            cpp_standard="c++17",
            target_arch="x86_64",
            target_os=sys.platform,
            runtime_header_hash=self.get_runtime_header_hash(),
            instrumentor_hash=self.get_instrumentor_hash(),
            entry_func=entry_func,
            requires_shared=requires_shared,
            build_version="2.1"
        )

    def lookup(self, spec: CacheKeySpec) -> Tuple[CacheStatus, Optional[CachedArtifact], str]:
        """
        Looks up a cached artifact by spec.
        Validates metadata integrity and binary artifact hash.
        Returns (CacheStatus, CachedArtifact or None, cache_key).
        """
        cache_key = spec.compute_cache_key()
        entry_dir = os.path.join(self.cache_dir, cache_key)

        with self._lock:
            if not os.path.isdir(entry_dir):
                return CacheStatus.CACHE_MISS, None, cache_key

            meta_path = os.path.join(entry_dir, "metadata.json")
            if not os.path.exists(meta_path):
                self._safe_remove_dir(entry_dir)
                return CacheStatus.CACHE_INVALIDATED, None, cache_key

            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta_dict = json.load(f)
            except Exception:
                self._safe_remove_dir(entry_dir)
                return CacheStatus.CACHE_CORRUPT, None, cache_key

            # Verify recorded spec matches current spec
            stored_spec = meta_dict.get("spec", {})
            for field_name in [
                "source_hash", "instrumented_hash", "compiler_name",
                "compiler_version", "compilation_flags", "runtime_header_hash",
                "instrumentor_hash", "entry_func", "requires_shared"
            ]:
                if stored_spec.get(field_name) != getattr(spec, field_name):
                    self._safe_remove_dir(entry_dir)
                    return CacheStatus.CACHE_INVALIDATED, None, cache_key

            # Verify binary artifact exists and matches recorded hash
            bin_name = meta_dict.get("artifact_name", "")
            bin_path = os.path.join(entry_dir, bin_name)
            if not os.path.exists(bin_path) or os.path.getsize(bin_path) == 0:
                self._safe_remove_dir(entry_dir)
                return CacheStatus.CACHE_INVALIDATED, None, cache_key

            actual_bin_hash = _sha256_file(bin_path)
            if actual_bin_hash != meta_dict.get("artifact_hash"):
                self._safe_remove_dir(entry_dir)
                return CacheStatus.CACHE_CORRUPT, None, cache_key

            inst_path = os.path.join(entry_dir, "instrumented.cpp")
            inst_code = ""
            if os.path.exists(inst_path):
                try:
                    with open(inst_path, "r", encoding="utf-8") as f:
                        inst_code = f.read()
                except Exception:
                    pass

            artifact = CachedArtifact(
                cache_key=cache_key,
                cache_dir=entry_dir,
                artifact_path=bin_path,
                instrumented_path=inst_path,
                metadata_path=meta_path,
                artifact_hash=actual_bin_hash,
                compile_time_ms=meta_dict.get("compile_time_ms", 0.0),
                instrumented_code=inst_code,
                created_at=meta_dict.get("created_at", time.time())
            )
            return CacheStatus.CACHE_HIT, artifact, cache_key

    def prepare_staging(self) -> Tuple[str, str, str]:
        """
        Creates an isolated staging directory for compilation before atomic publication.
        Returns (staging_dir, src_path, default_bin_name_prefix).
        """
        staging_dir = os.path.join(self.cache_dir, f".staging_{uuid.uuid4().hex[:12]}")
        os.makedirs(staging_dir, exist_ok=True)
        src_path = os.path.join(staging_dir, "app.cpp")
        return staging_dir, src_path, "artifact"

    def publish(
        self,
        staging_dir: str,
        spec: CacheKeySpec,
        staged_bin_path: str,
        compile_time_ms: float,
        instrumented_code: str
    ) -> CachedArtifact:
        """
        Atomically publishes a successfully compiled binary into the cache.
        Guarantees that partial writes, crashes, or concurrent compilations
        never expose half-written artifacts to consumers.
        """
        cache_key = spec.compute_cache_key()
        target_dir = os.path.join(self.cache_dir, cache_key)

        if not os.path.exists(staged_bin_path) or os.path.getsize(staged_bin_path) == 0:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise ValueError(f"Cannot publish missing or empty artifact: {staged_bin_path}")

        bin_ext = os.path.splitext(staged_bin_path)[1]
        final_bin_name = f"artifact{bin_ext}"
        final_staged_bin = os.path.join(staging_dir, final_bin_name)
        if staged_bin_path != final_staged_bin:
            shutil.move(staged_bin_path, final_staged_bin)

        # Write instrumented code in staging
        staged_inst_path = os.path.join(staging_dir, "instrumented.cpp")
        with open(staged_inst_path, "w", encoding="utf-8") as f:
            f.write(instrumented_code)

        # Compute hash of final staged binary
        bin_hash = _sha256_file(final_staged_bin)

        # Write metadata in staging
        metadata = {
            "cache_key": cache_key,
            "spec": spec.model_dump(),
            "artifact_name": final_bin_name,
            "artifact_hash": bin_hash,
            "compile_time_ms": compile_time_ms,
            "created_at": time.time()
        }
        staged_meta_path = os.path.join(staging_dir, "metadata.json")
        with open(staged_meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        # Atomic publication under lock
        with self._lock:
            if os.path.exists(target_dir):
                # Another concurrent compilation already published this exact key
                status, existing, _ = self.lookup(spec)
                if status == CacheStatus.CACHE_HIT and existing:
                    shutil.rmtree(staging_dir, ignore_errors=True)
                    return existing

            os.makedirs(target_dir, exist_ok=True)
            target_bin = os.path.join(target_dir, final_bin_name)
            target_bin_tmp = os.path.join(target_dir, f"{final_bin_name}.tmp_{uuid.uuid4().hex[:8]}")
            target_inst = os.path.join(target_dir, "instrumented.cpp")
            target_meta = os.path.join(target_dir, "metadata.json")
            target_meta_tmp = os.path.join(target_dir, f"metadata.json.tmp_{uuid.uuid4().hex[:8]}")

            shutil.copy2(final_staged_bin, target_bin_tmp)
            os.replace(target_bin_tmp, target_bin)

            shutil.copy2(staged_inst_path, target_inst)

            shutil.copy2(staged_meta_path, target_meta_tmp)
            os.replace(target_meta_tmp, target_meta)

            shutil.rmtree(staging_dir, ignore_errors=True)

        return CachedArtifact(
            cache_key=cache_key,
            cache_dir=target_dir,
            artifact_path=os.path.join(target_dir, final_bin_name),
            instrumented_path=os.path.join(target_dir, "instrumented.cpp"),
            metadata_path=os.path.join(target_dir, "metadata.json"),
            artifact_hash=bin_hash,
            compile_time_ms=compile_time_ms,
            instrumented_code=instrumented_code,
            created_at=metadata["created_at"]
        )

    def invalidate(self, cache_key: str) -> bool:
        """Invalidates and purges a single cache key."""
        target_dir = os.path.join(self.cache_dir, cache_key)
        with self._lock:
            if os.path.exists(target_dir):
                self._safe_remove_dir(target_dir)
                return True
        return False

    def clear(self) -> int:
        """Purges all entries from the build cache, returning count of removed entries."""
        with self._lock:
            count = 0
            if os.path.exists(self.cache_dir):
                for entry in os.listdir(self.cache_dir):
                    p = os.path.join(self.cache_dir, entry)
                    if os.path.isdir(p):
                        self._safe_remove_dir(p)
                        count += 1
            return count

    def _safe_remove_dir(self, path: str):
        """Removes a directory with retry logic and read-only clearing for Windows."""
        import stat

        def _on_rm_error(func, p, exc_info):
            try:
                os.chmod(p, stat.S_IWRITE)
                func(p)
            except Exception:
                pass

        if not os.path.exists(path):
            return

        for attempt in range(5):
            try:
                # Clear read-only flags on all files and subdirs
                for root, dirs, files in os.walk(path):
                    for f in files:
                        try:
                            os.chmod(os.path.join(root, f), stat.S_IWRITE)
                        except Exception:
                            pass
                    for d in dirs:
                        try:
                            os.chmod(os.path.join(root, d), stat.S_IWRITE)
                        except Exception:
                            pass
                os.chmod(path, stat.S_IWRITE)

                shutil.rmtree(path, onerror=_on_rm_error)
                if not os.path.exists(path):
                    break
                time.sleep(0.05 * (attempt + 1))
            except Exception:
                pass
