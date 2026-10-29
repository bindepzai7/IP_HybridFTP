# IP_HybridFTP

A client–server file-transfer system that splits the **control plane** from the
**data plane**:

- **Control channel — TCP.** FTP-style commands and three-digit reply codes
  (RFC 959 style), one persistent connection per client.
- **Data channel — UDP + custom reliable transport.** File bytes travel over
  UDP using a reliable-delivery protocol built from scratch: Selective Repeat,
  CRC32 checksums, per-packet retransmission timers and AIMD congestion control.

The server handles multiple clients at once (one thread per client) and
supports 28 commands. These include active/passive data connections
(`PORT`/`PASV`), `TYPE A/I`, `MODE S/B/C` and SHA-256 integrity checks
(`HASH`).

> For the full design, see [DOCUMENTATION.md](DOCUMENTATION.md). It covers the
> architecture layers, packet format, the RDT algorithm, a method-by-method
> reference and an end-to-end trace of a `RETR`.

---

## Requirements

- Python **3.10+**
- No third-party packages for the app itself (standard library only)
- `pytest` only if you want to run the test suite

## Project layout

```
IP_HybridFTP/
├── hybrid_ftp/
│   ├── common/      # packet.py (wire format), rdt.py (reliable UDP), mode.py (TYPE/MODE)
│   ├── server/      # control handlers, sessions, auth, sandboxed filesystem
│   ├── client/      # FTPClient + interactive ftp> prompt
│   │   └── storage/ # client's local folder (created at runtime)
│   └── tests/       # pytest suite
├── data/            # server data (created at runtime, gitignored)
│   ├── users.json   # user accounts (SHA-256 password hashes)
│   └── root/        # FTP root directory served to clients
├── DOCUMENTATION.md
└── requirements-dev.txt
```

---

## Quick start

All commands are run from inside the `hybrid_ftp/` directory.

```bash
cd hybrid_ftp
```

### 1. Create a user account

`data/` is not committed to git, so a fresh clone has no accounts. Add one:

```bash
python -c "from server.auth import Authenticator; Authenticator().add_user('alice', 'secret')"
```

This creates `data/users.json` (and `data/` itself) if they don't exist yet.

### 2. Start the server

```bash
python -m server
```

The server listens on `0.0.0.0:2121` and serves files from `data/root/`
(created automatically). Stop it with `Ctrl+C`.

### 3. Start the client

In a second terminal:

```bash
python -m client                      # connects to 127.0.0.1:2121
python -m client <host> <port>        # connect elsewhere
python -m client --verify_hash        # print the SHA-256 check after each transfer
```

### 4. Example session

```text
220 Service ready for new user.
ftp> USER alice
331 User name okay, need password.
ftp> PASS secret
230 User logged in, proceed.
ftp> LIST
ftp> RETR book.pdf
ftp> STOR notes.txt
ftp> QUIT
```

- **Downloads** (`RETR`) are saved to `hybrid_ftp/client/storage/`.
- **Uploads** (`STOR`, `APPE`, `STOU`) read their local file from the same
  `hybrid_ftp/client/storage/` folder. Put files there before uploading.
- A data channel is set up automatically (passive mode) if you haven't
  issued `PASV` or `PORT` yourself.

The exact reply text may differ slightly from the example above. Type `HELP`
in the client for the full command list, or `HELP <cmd>` for one command's
syntax.

---

## Supported commands

| Category | Commands |
|---|---|
| Session | `USER`, `PASS`, `QUIT`, `NOOP`, `HELP`, `STAT` |
| Navigation | `PWD`, `CWD`, `CDUP`, `MKD`, `RMD` |
| Listing & info | `LIST`, `NLST`, `SIZE`, `MDTM`, `HASH` |
| File transfer | `RETR`, `STOR`, `STOU`, `APPE`, `ABOR` |
| File management | `DELE`, `RNFR`, `RNTO` |
| Transfer settings | `TYPE A\|I`, `MODE S\|B\|C`, `PORT`, `PASV` |

Notes:
- The default `TYPE` is **I** (binary), so files are never altered by accident.
  `TYPE A` converts line endings for text files.
- `MODE B` length-prefixes blocks and `MODE C` compresses with zlib. `MODE S`
  sends a plain stream.
- After a binary transfer, the client compares the SHA-256 hash of its file
  with the server's (via `HASH`). A mismatch is always reported.

See [DOCUMENTATION.md §4](DOCUMENTATION.md#4-ftp-command-reference) for each
command's syntax and purpose.

---

## Running the tests

```bash
pip install -r requirements-dev.txt
cd hybrid_ftp
python -m pytest
```

The suite has 58 tests. They cover the packet format, the reliable-UDP layer,
ASCII/MODE encoding and end-to-end FTP commands against a live server on a
random local port. The end-to-end tests add a `testuser` account to
`data/users.json`.

---

## Known limitations

- `ABOR` acknowledges an abort but does not truly interrupt a transfer
  mid-window.
- The receive window (`rwnd`) is a fixed constant, not advertised by the
  receiver.
- Passwords are stored as unsalted SHA-256 hashes. This is fine for a course
  project but not for production.

---

## Authors

| Member | Student ID |
|---|---|
| Member A | 23125005 |
| Doan Duc Tuan | 23125021 |

Developed for the *Internetworking Protocols* course: Project 1, Socket
Programming (2026).
