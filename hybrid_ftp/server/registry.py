"""
Live registry of active client sessions.

Thread-safe because each client is handled on its own thread (see
FTPServer._handle_client). Renders an aligned table of the currently
connected clients -- their session id, remote IP:port, authenticated user,
and current working directory -- for display in the server console.
"""
import threading


class SessionRegistry:
    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()

    def add(self, session):
        with self._lock:
            self._sessions[session.id] = session

    def remove(self, session):
        with self._lock:
            self._sessions.pop(session.id, None)

    def snapshot(self):
        with self._lock:
            return list(self._sessions.values())

    def _row(self, session):
        if session.remote_addr:
            addr = f"{session.remote_addr[0]}:{session.remote_addr[1]}"
        else:
            addr = "-"

        user = session.username or "-"

        try:
            cwd = session.fs.display_path()
        except Exception:
            cwd = "-"

        return (session.id[:8], addr, user, cwd)

    def render(self):
        rows = [self._row(s) for s in self.snapshot()]

        headers = ("Session", "Client", "User", "CWD")
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))

        def fmt(cols):
            return " | ".join(col.ljust(widths[i]) for i, col in enumerate(cols))

        separator = "-+-".join("-" * w for w in widths)

        lines = [f"=== Active sessions ({len(rows)}) ==="]
        lines.append(fmt(headers))
        lines.append(separator)
        if rows:
            lines.extend(fmt(row) for row in rows)
        else:
            lines.append("(none)")

        return "\n".join(lines)

    def print_table(self):
        # A single print() of the whole block keeps it from interleaving with
        # other threads' output.
        print(self.render())
