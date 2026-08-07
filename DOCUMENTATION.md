# Hybrid FTP — Project Reference

A client–server file-transfer system that splits the **control plane** from the
**data plane**: commands travel over **TCP**, file payload travels over a
**custom reliable-UDP protocol** built from scratch (Selective Repeat + AIMD).
This document maps every command, file, and key method for study and oral defense.

| | |
|---|---|
| Lines of Python (SLOC) | ~1,878 |
| FTP commands | 28 |
| Source modules | 16 |
| Target level | Excellent |
| Server | `python -m server` (from `hybrid_ftp/`, host `0.0.0.0`, port `2121`) |
| Client | `python -m client` (from `hybrid_ftp/`) |

---

## 1. Overview

The project mirrors RFC 959's architecture: two independent channels cooperating over one session.

- **Control channel — TCP** *(reliable, ordered)*
  Carries commands and three-digit reply codes. TCP guarantees ordered, lossless
  delivery, so session state (login, working directory, transfer settings) stays
  consistent. One persistent socket per client for the whole session.

- **Data channel — UDP + custom RDT** *(built from scratch)*
  Carries the actual file bytes over UDP. Because UDP is unreliable, a custom
  application-layer protocol adds ACKs, sequence numbers, checksums,
  retransmission, ordering, and duplicate elimination — Selective Repeat with
  AIMD congestion control. A fresh data channel is opened per transfer.

Every file operation is a coordinated dance between the two: a command travels
the TCP control channel, the server replies `150 Opening data connection`, the
bytes stream over the UDP data channel, and the server closes with
`226 Transfer complete`.

---

## 2. Architecture — the layers

Read bottom-up: each layer builds on the one below it. This is also the
recommended study order.

| Layer | Modules |
|---|---|
| **7 · Orchestration** | `server.py` (accept loop, one thread per client), `client.py` (high-level ops), `__main__.py` (entry points / CLI) |
| **5–6 · Control plane & server state** | `control.py`, `session.py`, `auth.py`, `filesystem.py`, `registry.py`, `reply_code.py` |
| **3–4 · Data channels & encoding** | `server/data.py`, `client/data.py`, `mode.py` |
| **1–2 · Reliable-UDP core** | `packet.py` (wire format), `rdt.py` (Selective Repeat + AIMD + rwnd) |

---

## 3. File map

Owners: **A** = Member A (ID 23125005) · **B** = Member B (Doan Duc Tuan, ID 23125021).
Plane: **TCP** = control, **UDP** = data.

| Module | Plane | Responsibility | Owner |
|---|---|---|---|
| `common/packet.py` | UDP | Packet dataclass, 15-byte header, CRC32 checksum, (de)serialisation | B |
| `common/rdt.py` | UDP | ReliableUDP — Selective Repeat, AIMD congestion window, rwnd bound, FIN handshake | B |
| `common/mode.py` | UDP | AsciiCodec (TYPE A/I) + TransferEngine (MODE S/B/C) | B |
| `server/control.py` | TCP | Command parsing, dispatch table, all ~28 handlers | A |
| `server/reply_code.py` | TCP | Three-digit FTP reply-code enum + default messages | A |
| `server/auth.py` | TCP | Authenticator — users.json, SHA-256 password store | B |
| `server/session.py` | TCP | Per-client Session state (login, cwd, channel, TYPE/MODE) | B |
| `server/filesystem.py` | TCP | Sandboxed file/dir operations, path-traversal guard, SHA-256 | A |
| `server/registry.py` | TCP | Thread-safe active-session table | A |
| `server/data.py` | UDP | DataChannel ABC + Active/Passive establishment | A |
| `server/server.py` | TCP | Accept loop, one daemon thread per client | B |
| `client/client.py` | TCP | High-level ops (RETR/STOR/…), auto hash verification | A |
| `client/control.py` | TCP | Client control-channel line I/O | B |
| `client/data.py` | UDP | Client UDP socket + RDT invocation, address kickoff | A |
| `client/__main__.py` | TCP | Interactive `ftp>` prompt, command parsing | B |
| `server/__main__.py` | TCP | Server entry point (host 0.0.0.0, port 2121) | B |

---

## 4. FTP command reference

Every command travels the TCP control channel. Commands marked **data** open a
UDP data channel to move bytes.

| Command | Syntax | Purpose | Uses |
|---|---|---|---|
| `USER` | `USER <user>` | Begin authentication with a username | |
| `PASS` | `PASS <pw>` | Complete authentication with a password | |
| `QUIT` | `QUIT` | End the session gracefully (returns CLOSE) | |
| `NOOP` | `NOOP` | Keep-alive ping; no operation | |
| `PWD` | `PWD` | Print current working directory | |
| `CWD` | `CWD <path>` | Change working directory | |
| `CDUP` | `CDUP` | Move to parent directory (clamped at root) | |
| `MKD` | `MKD <dir>` | Create a directory | |
| `RMD` | `RMD <dir>` | Remove an empty directory | |
| `LIST` | `LIST [path]` | Detailed `ls -l`-style listing | data |
| `NLST` | `NLST [path]` | Plain name-only listing | data |
| `STAT` | `STAT [path]` | Session status, or file/dir metadata | |
| `SIZE` | `SIZE <file>` | Byte size of a file | |
| `MDTM` | `MDTM <file>` | Last-modified time (YYYYMMDDhhmmss) | |
| `TYPE` | `TYPE {A\|I}` | Set ASCII text or Image/binary representation | |
| `MODE` | `MODE {S\|B\|C}` | Set Stream / Block / Compressed framing | |
| `PORT` | `PORT h1..p2` | Active mode: client announces its data address | setup |
| `PASV` | `PASV` | Passive mode: server opens a port, returns address | setup |
| `RETR` | `RETR <file>` | Download a file (server → client) | data |
| `STOR` | `STOR <file>` | Upload a file (client → server) | data |
| `STOU` | `STOU` | Upload with a server-generated unique name | data |
| `APPE` | `APPE <file>` | Append uploaded data to a file | data |
| `DELE` | `DELE <file>` | Delete a file | |
| `RNFR` | `RNFR <old>` | Rename step 1: mark source file | |
| `RNTO` | `RNTO <new>` | Rename step 2: complete the rename | |
| `HASH` | `HASH <file>` | Return SHA-256 digest for integrity check | |
| `ABOR` | `ABOR` | Acknowledge abort of a transfer | |
| `HELP` | `HELP [cmd]` | List commands or show one command's syntax | |

---

## 5. Reply codes

Every server response is a three-digit code; the first digit is the category.
The server funnels all replies through one `_send_response` method.

| Class | Meaning | Examples used here |
|---|---|---|
| `1xx` | Positive preliminary — action starting | `150` opening data connection |
| `2xx` | Positive completion — action done | `200` OK, `220` ready, `226` transfer complete, `230` logged in |
| `3xx` | Positive intermediate — need more input | `331` need password, `350` pending RNTO |
| `4xx` | Transient negative — try again | `425` can't open data, `426` aborted |
| `5xx` | Permanent negative — request refused | `502` not implemented, `530` not logged in, `550` file unavailable |

---

## 6. Reliable UDP — the RDT core

`ReliableUDP` in `rdt.py` turns an unreliable UDP socket into a reliable, ordered
byte stream using **Selective Repeat** with **AIMD congestion control** and a
**receive-window** flow-control bound.

### Sender loop

1. **Chunk** the file into 1024-byte packets, each with an increasing `seq` (`_create_packets`).
2. **Fill the window** up to `min(cwnd, rwnd)` unacked packets in flight; record each with its own timer (`_fill_window`).
3. **Process ACKs** individually — mark that packet delivered, then slide `send_base` past any contiguous run of acked packets (`_process_ack`).
4. **Grow cwnd** on each new ACK: slow start (`+1`) below `ssthresh`, else congestion avoidance (`+1/cwnd`).
5. **Check timeouts** per packet; retransmit only the one that expired, and on any timeout halve `ssthresh` and reset `cwnd` to 1 (multiplicative decrease).
6. **FIN handshake** once everything is acked, to signal end of stream.

### Receiver loop

1. **Buffer out-of-order** packets within the window (`rcv_buffer`) and ACK every valid packet individually (`_process_data_packet`).
2. **Deliver in order** — append to output only while packets are contiguous from `rcv_base` (`_slide_recv_window`).
3. **Re-ACK duplicates** (already-delivered seqs) so a lost ACK is recovered without re-delivering data.

> **Why it's Selective Repeat, not Go-Back-N:** individual (non-cumulative)
> ACKs, receiver buffers out-of-order packets, and the sender retransmits only
> the timed-out packet — never the whole window.

### Constants

| Constant | Value | Role |
|---|---|---|
| `MAX_PAYLOAD_SIZE` | 1024 | Max file bytes per packet |
| `TIMEOUT` | 1.0 | Per-packet retransmit timer (s) |
| `MAX_RETRIES` | 20 | Give up after this many resends |
| `POLL_INTERVAL` | 0.05 | Socket timeout while polling for ACKs |
| `INITIAL_SSTHRESH` | 64.0 | Slow-start threshold |
| `RWND` | 64 | Receive-window bound (packets) |

### Packet header (15 bytes, `!IIBHI`)

| Bytes | Field | Meaning |
|---|---|---|
| 0–3 | `seq` | Sequence number of this packet |
| 4–7 | `ack` | Which seq is being acknowledged |
| 8 | `flags` | Bit flags: DATA=0x01, ACK=0x02, FIN=0x04 |
| 9–10 | `length` | Payload byte count |
| 11–14 | `checksum` | CRC32 over header + payload |

---

## 7. TYPE & MODE — two independent knobs

These are orthogonal and applied in a strict nested order.

| | Command | Controls | Values |
|---|---|---|---|
| **TYPE** | `TYPE A / I` | Representation — text vs binary | A = ASCII newline translation · I = byte-exact |
| **MODE** | `MODE S / B / C` | Framing on the wire | S = Stream · B = Block (length-prefixed) · C = Compressed (zlib) |

**Order matters — nested envelopes:**
- Send: `TYPE (to_network)` → `MODE (encode_data)` → RDT
- Receive: RDT → `MODE (decode_data)` → `TYPE (to_local)`

The last transform applied on send is the first undone on receive.

> **Integrity nuance:** hash verification only runs for `TYPE I`. In ASCII mode
> the two sides' files differ by newline convention, so the SHA-256 digests would
> legitimately not match — comparing them would report a false corruption.

---

## 8. Method reference

### `packet.py`

| Method | Does |
|---|---|
| `compute_checksum()` | CRC32 over header (without the checksum field) + payload; the corruption fingerprint |
| `to_bytes()` | Serialize: pack the 15-byte header (with checksum) + payload into wire bytes |
| `from_bytes(data)` | Deserialize + validate — three checks (header present, length matches, checksum matches); raises `ValueError` on corruption |
| `is_data / is_ack / is_fin` | Bit-flag tests on the 1-byte flags field |

### `rdt.py` (ReliableUDP)

| Method | Side | Does |
|---|---|---|
| `send(data)` | sender | Main loop: fill window → recv ACK → slide → grow cwnd → check timeouts → FIN |
| `_create_packets(data)` | sender | Split data into numbered packets |
| `_fill_window(...)` | sender | Send new packets up to `min(cwnd, rwnd)`; record per-packet timers |
| `_process_ack(...)` | sender | Mark a packet acked; slide `send_base` over contiguous acks |
| `_check_timeouts(...)` | sender | Retransmit expired packets individually; trigger multiplicative decrease |
| `_update_cwnd_on_ack / _on_timeout` | sender | AIMD: additive increase on ACK, halve-and-reset on loss |
| `recv()` | receiver | Main loop: validate, buffer, deliver in order, ACK, break on FIN |
| `_process_data_packet(...)` | receiver | Window check, buffer out-of-order, ACK, re-ACK duplicates |
| `_slide_recv_window(...)` | receiver | Deliver contiguous buffered payloads from `rcv_base` |
| `recv_packet()` | both | recvfrom; auto-learns peer address on first contact |

### `control.py`

28 handlers, but four repeating patterns. Universal handler shape:
`_require_login` → parse/validate → call `fs`/`data_channel` → translate result to a reply code.

| Method | Does |
|---|---|
| `run()` | Send 220 greeting, then loop reading control lines and dispatching until QUIT/disconnect |
| `_process_command(line)` | Split cmd/arg, look up in the handlers dict, log the command, call the handler |
| `_send_response(code, msg)` | Format and send a three-digit reply — the single reply funnel |
| `_require_login()` | Guard: reply 530 if not authenticated |
| `_require_data_connection()` | Guard: reply 425 if no data channel set up |
| `handle_user / handle_pass` | Two-step auth state machine |
| `handle_retr / handle_stor` | Transfer archetype: TYPE/MODE encode → 150 → establish → send_file/recv_file → 226 |
| `handle_port / handle_pasv` | Active/Passive data-channel negotiation |
| `handle_rnfr / handle_rnto` | Two-step rename state machine |
| `handle_hash` | Return `213 SHA256 <hex>` for integrity verification |

### `filesystem.py`

| Method | Does |
|---|---|
| `resolve_path(name)` | **The security boundary.** Normalize + abspath, then reject anything outside `ROOT_DIR` — stops path traversal (`../../etc/passwd`) |
| `_in_root(path)` | `os.path.commonpath` check that a resolved path stays under root |
| `cwd / cdup / pwd / display_path` | Navigation; `display_path` hides the server's real filesystem layout |
| `read_file / write_file / append_file / delete_file` | File I/O behind RETR / STOR / APPE / DELE |
| `format_list / format_nlst` | Directory listings for LIST / NLST |
| `hash_file(name)` | Stream the file in 8 KB chunks into SHA-256; used by HASH |

### `client.py`

| Method | Does |
|---|---|
| `retr / stor / appe / stou` | High-level transfers; mirror the server's TYPE/MODE order in reverse |
| `_ensure_data_channel()` | Auto-negotiate passive mode if no channel is set up |
| `set_passive_mode / set_active_mode` | Client side of PASV / PORT; parse or announce the data address |
| `verify_hash(remote, local)` | Send HASH, compare server digest to local SHA-256; mismatch always reported |
| `_maybe_verify_hash(...)` | Run the check only for binary (TYPE I) transfers |
| `_storage_path(name)` | Client-side path-traversal guard for the `storage/` folder |

---

## 9. End-to-end trace — `RETR` (passive, binary)

One download, touching every layer. This is the single most likely opening
question in the oral defense.

1. User types `RETR image.png` at the `ftp>` prompt — *client/__main__.py*
2. Client auto-negotiates passive mode → sends `PASV` over TCP — *client.py · set_passive_mode*
3. Server opens a UDP socket, replies `227 (…)` — *control.py · handle_pasv*
4. Client binds a UDP socket, sends a `\x00` kickoff datagram — *client/data.py · set_peer*
5. Server's `recvfrom` learns the client address — *server/data.py · PassiveDataChannel*
6. Client sends `RETR image.png` over TCP — *client.py · retr*
7. Server reads file → TYPE → MODE → replies `150` — *control.py · handle_retr*
8. ReliableUDP windows packets, retransmits losses, ACKs, sends FIN — *rdt.py + packet.py*
9. Client reassembles in order, decodes MODE + TYPE, writes file — *client.py + mode.py*
10. Server closes with `226`; client sends `HASH`, compares SHA-256 — *verify_hash*
11. All of this ran on this client's dedicated thread; others run concurrently — *server.py*

---

## 10. Viva key points

- **Trace one RETR/STOR** through every layer (section 9) — the highest-value thing to have crisp.
- **Selective Repeat vs Go-Back-N** — individual ACKs, out-of-order buffering, single-packet retransmit.
- **Where AIMD lives** — `_update_cwnd_on_ack` (increase) and `_update_cwnd_on_timeout` (decrease); window = `min(cwnd, rwnd)`.
- **Path-traversal defense** — `resolve_path` + `_in_root` via `os.path.commonpath`.
- **Concurrency model** — one thread + one Session per client; shared session registry protected by a lock.
- **Active vs Passive** — who already knows whose address, and the `\x00` kickoff for passive.
- **Corruption path** — bad checksum → `from_bytes` raises → packet discarded → looks like loss → retransmit.

---

## 11. Honest limitations

Name these before the examiner finds them — it signals real ownership rather than overclaiming.

- **ABOR** replies `226` but does not truly interrupt a transfer mid-window.
- **rwnd** is a fixed local constant, not a value advertised by the receiver over the wire — despite the name, it is not a negotiated window.
- **Password hashes** are unsalted SHA-256 — fine for a course project, not production-grade.
- **generate_unique_name** checks existence against the process working directory, not the FTP root (harmless because UUID collisions are astronomically unlikely).

---

*Line count is SLOC (comments and blanks excluded). Reflects the current codebase.*
