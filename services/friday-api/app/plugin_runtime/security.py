from typing import Set, List, Optional, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path


RESTRICTED_MODULES: Set[str] = {
    "ctypes", "subprocess", "multiprocessing",
    "socket", "requests", "urllib.request", "urllib.parse",
    "http.client", "http.server",
    "ftplib", "telnetlib", "smtplib",
    "poplib", "imaplib", "nntplib",
    "os", "shutil", "signal",
    "sys", "importlib", "code",
    "codeop", "codecs",
    "asyncio", "threading", "_thread",
    "concurrent", "multiprocessing",
    "pickle", "shelve", "marshal",
    "tempfile", "fileinput",
    "inspect", "traceback",
    "bdb", "pdb", "profile", "cProfile",
    "atexit", "gc", "sysconfig",
    "ctypes", "cffi",
    "distutils", "setuptools",
    "pkgutil", "pkg_resources",
    "webbrowser", "antigravity",
    "turtle", "tkinter",
    "idlelib", "test",
    "ssl", "hashlib",
}

MODULE_PERMISSION_MAP: Dict[str, str] = {
    "os": "filesystem.read",
    "os.path": "filesystem.read",
    "pathlib": "filesystem.read",
    "shutil": "filesystem.write",
    "subprocess": "subprocess",
    "multiprocessing": "subprocess",
    "socket": "network",
    "requests": "network",
    "urllib": "network",
    "http": "network",
    "ftplib": "network",
    "smtplib": "network",
    "ssl": "network",
    "ctypes": "native_code",
    "cffi": "native_code",
}


@dataclass
class SecurityPolicy:
    allowed_imports: Set[str] = field(default_factory=set)
    blocked_imports: Set[str] = field(default_factory=lambda: RESTRICTED_MODULES.copy())
    allow_local_imports: bool = True
    allow_site_packages: bool = True
    max_import_depth: int = 5

    def is_import_allowed(self, module_name: str) -> bool:
        base = module_name.split(".")[0]
        if base in self.blocked_imports:
            return False
        if self.allowed_imports and base not in self.allowed_imports:
            return False
        return True

    def get_import_permission(self, module_name: str) -> Optional[str]:
        base = module_name.split(".")[0]
        return MODULE_PERMISSION_MAP.get(base)


@dataclass
class FileSystemRule:
    allowed_paths: Set[str] = field(default_factory=set)
    blocked_paths: Set[str] = field(default_factory=set)
    read_allowed: bool = True
    write_allowed: bool = False
    max_file_size_bytes: int = 50 * 1024 * 1024
    allow_symlinks: bool = False
    allow_executables: bool = False

    def is_path_allowed(self, path: str, write: bool = False) -> bool:
        p = Path(path).resolve()
        for blocked in self.blocked_paths:
            if str(p).startswith(str(Path(blocked).resolve())):
                return False
        if write and not self.write_allowed:
            return False
        if self.allowed_paths:
            for allowed in self.allowed_paths:
                if str(p).startswith(str(Path(allowed).resolve())):
                    return True
            return False
        return True


@dataclass
class NetworkRule:
    allowed_hosts: Set[str] = field(default_factory=set)
    blocked_hosts: Set[str] = field(default_factory=set)
    allowed_ports: Set[int] = field(default_factory=lambda: {80, 443})
    allow_http: bool = True
    allow_https: bool = True
    max_connections: int = 10
    request_timeout_seconds: float = 10.0

    def is_host_allowed(self, host: str) -> bool:
        for blocked in self.blocked_hosts:
            if host == blocked or host.endswith("." + blocked):
                return False
        if self.allowed_hosts:
            for allowed in self.allowed_hosts:
                if host == allowed or host.endswith("." + allowed):
                    return True
            return False
        return True

    def is_port_allowed(self, port: int) -> bool:
        if self.allowed_ports and port not in self.allowed_ports:
            return False
        return True


@dataclass
class SecurityConfig:
    sandbox_enabled: bool = True
    filesystem: FileSystemRule = field(default_factory=FileSystemRule)
    network: NetworkRule = field(default_factory=NetworkRule)
    imports: SecurityPolicy = field(default_factory=SecurityPolicy)
    restrict_subprocess: bool = True
    restrict_native_code: bool = True
    enable_audit_log: bool = True
