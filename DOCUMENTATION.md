# Hybrid FTP — Code Documentation

This document explains how each function in the main project files works. The application uses **TCP** for the control channel (commands/responses) and **UDP** with a custom stop-and-wait protocol for file transfers.

## Architecture Overview

```
Client (client.py)                    Server (server.py)
      │                                      │
      │──── TCP :2121 (USER, PASS, STOR…) ──►│ control.py
      │◄─── FTP reply codes (220, 150, 226) ─│
      │                                      │
      │──── UDP (reliable file payload) ─────►│ data.py
```

At basic level, the data channel is opened **implicitly** when `STOR` or `RETR` runs — no `PASV`/`PORT` command is required from the user.

---

## Server

### `server/server.py`

Entry point for the FTP server.

| Function / Method | Description |
|---|---|
| `FTPServer.__init__(host, port, authenticator)` | Creates a TCP listening socket on `host:port` (default `0.0.0.0:2121`). Enables `SO_REUSEADDR` and sets a 0.5s accept timeout so `KeyboardInterrupt` can be handled cleanly. |
| `FTPServer.start()` | Binds, listens, then loops forever accepting client connections. For each client, creates a `Session` and runs `ControlChannel.run()`. Handles `Ctrl+C` shutdown. |
| `main()` | Creates an `Authenticator`, seeds default account `user`/`password` if missing, then starts the server. |
| `if __name__ == "__main__"` | Runs `main()` when executed directly. |

---

### `server/control.py`

Handles all FTP commands over the TCP control connection.

#### `ControlChannel` class

| Function / Method | Description |
|---|---|
| `__init__(client_sock, session, client_addr)` | Stores the client TCP socket, session state, client address, and a `FileSystem` instance. Builds a `handlers` dict mapping command names (e.g. `"USER"`) to handler methods. |
| `_process_command(line)` | Parses a raw command line into `cmd` + `arg`, looks up the handler, logs the command to the server console, and dispatches it. Returns `"CLOSE"` for `QUIT`, or `None` on errors. |
| `_send_response(code, custom_msg)` | Sends a standard FTP reply (`"220 Message\r\n"`) over TCP. Uses `DefaultMessage` unless a custom message is provided. |
| `_require_login()` | Returns `False` and sends `530 Not logged in` if the session is not authenticated. |
| `_data_host_for_reply()` | Determines which IP address to advertise for the UDP data channel (client address, bound host, or `127.0.0.1`). |
| `_format_data_endpoint(host, port)` | Formats host/port as FTP-style tuple `(h1,h2,h3,h4,p1,p2)` embedded in `150` responses. |
| `_open_data_channel()` | Opens a UDP socket on a random port, stores it in the session, and returns `(host, port)`. Called automatically before each transfer. |
| `run()` | Sends `220 Service ready`, then reads commands in a loop until disconnect or `QUIT`. Cleans up data channel and socket on exit. |

#### Command handlers

| Handler | Description |
|---|---|
| `handle_user(line)` | Validates username exists in `users.json`. Sets pending username and replies `331` (need password). |
| `handle_pass(line)` | Verifies password hash. On success, marks session logged in (`230`). On failure, clears username (`530`). |
| `handle_quit(line)` | Logs out, sends `221`, returns `"CLOSE"` to end the session loop. |
| `handle_noop(_args)` | No-operation keep-alive. Replies `200`. |
| `handle_type(args)` | Sets transfer type. `TYPE A` (ASCII) is supported; `TYPE I` (binary) returns `502`. |
| `handle_mode(args)` | Sets transfer mode. Only `MODE S` (stream) is supported at basic level. |
| `handle_retr(args)` | **Download.** Reads file from disk, opens UDP channel, sends `150` with data endpoint, transmits file over UDP, then `226`. Converts `\n` → `\r\n` in ASCII mode. |
| `handle_stor(args)` | **Upload.** Opens UDP channel, sends `150` with endpoint, receives file over UDP, saves to disk, then `226`. Converts `\r\n` → `\n` in ASCII mode. |
| `handle_help(args)` | Lists supported basic commands, or shows syntax for a specific command. |
| `handle_not_implemented(_args)` | Returns `502` for advanced commands (`LIST`, `CWD`, `PASV`, `PORT`, etc.). |

---

### `server/session.py`

Tracks per-client state for one control connection.

| Function / Method | Description |
|---|---|
| `__init__(authenticator)` | Creates a unique session ID (`uuid`), stores auth reference, and initializes defaults: not logged in, `TYPE A`, `MODE S`, no data socket. |
| `set_user(username)` | Stores the username pending password verification. |
| `login()` | Sets `logged_in = True` after successful `PASS`. |
| `logout()` | Clears username and login flag on `QUIT`. |
| `close_data_channel()` | Closes the UDP socket and resets `data_host`, `data_port`, `data_socket`. |

---

### `server/auth.py`

User authentication backed by `data/users.json`.

| Function / Method | Description |
|---|---|
| `__init__()` | Ensures `data/` directory and `users.json` exist (creates empty `{"users": {}}` if missing). |
| `_load_users()` | Reads and parses `users.json`. |
| `_save_users(data)` | Writes updated user data back to `users.json`. |
| `_hash_password(password)` | Returns SHA-256 hex digest of the password. |
| `user_exists(username)` | Returns `True` if username is in the user database. |
| `add_user(username, password)` | Registers a new user with hashed password. Returns `False` if username already exists. |
| `remove_user(username)` | Deletes a user. Returns `False` if not found. |
| `authenticate(username, password)` | Compares password hash against stored hash. Returns `True` on match. |

---

### `server/filesystem.py`

Server-side file storage under `hybrid_ftp/data/`.

| Function / Method | Description |
|---|---|
| `__init__()` | Ensures `ROOT_DIR` (`data/`) exists. Sets `current_directory` to root. |
| `resolve_path(filename)` | Joins filename with current directory and resolves to absolute path. Raises `ValueError` if path escapes `ROOT_DIR` (path traversal protection). |
| `file_exists(filename)` | Returns `True` if the resolved path is a regular file. |
| `read_file(filename)` | Reads and returns file contents as `bytes`. Raises `FileNotFoundError` if missing. |
| `write_file(filename, data)` | Writes `bytes` to disk, creating parent directories if needed. |

---

### `server/data.py`

UDP data channel with stop-and-wait reliability (RDT).

#### Packet format

Each UDP datagram: `seq (4B) | flags (1B) | length (2B) | checksum (4B) | payload (≤1024B)`

- **Flags:** `DATA=0`, `ACK=1`, `FIN=2`
- **Checksum:** CRC32 of payload for corruption detection
- **Sequence:** Alternates 0/1 per chunk (stop-and-wait)

#### Functions

| Function | Description |
|---|---|
| `_pack_packet(seq, flags, payload)` | Builds a binary packet with header + payload. |
| `_unpack_packet(data)` | Parses and validates a packet. Returns `(seq, flags, payload)` or `None` if corrupt/incomplete. |
| `_send_ack(sock, peer_addr, seq)` | Sends an ACK packet for the given sequence number. |
| `_wait_for_peer(sock, timeout)` | Blocks until any UDP datagram arrives; returns sender address. Used before server-initiated send (download). |
| `_send_bytes(sock, data, peer_addr, timeout)` | Reliably sends all bytes using stop-and-wait: send chunk → wait ACK → toggle seq → repeat. Ends with a `FIN` packet. Retries up to 10 times per packet. |
| `_recv_bytes(sock, timeout)` | Reliably receives all bytes: validate seq/checksum, ACK each packet, assemble chunks until `FIN`. Returns `(data, peer_addr)`. |

#### `DataChannel` class

| Method | Description |
|---|---|
| `__init__(data_socket)` | Wraps the session's UDP socket. |
| `send_file(data)` | Waits for client to connect (`_wait_for_peer`), then sends file bytes with `_send_bytes`. |
| `receive_file()` | Receives file bytes with `_recv_bytes` and returns them. |

---

### `server/reply_code.py`

Defines standard FTP three-digit reply codes.

| Name | Description |
|---|---|
| `ReplyCode` (IntEnum) | All numeric codes used by the server (e.g. `220`, `331`, `530`, `150`, `226`, `502`). |
| `DefaultMessage` (dict) | Maps each `ReplyCode` to its default human-readable message string. |

No functions — this file is pure data/constants.

---

## Client

### `client/client.py`

Interactive FTP client with a command-line interface.

| Function / Method | Description |
|---|---|
| `FTPClient.__init__(host, port, retry)` | Opens a TCP connection to the server (retries up to 5 times). Reads and prints the initial `220` greeting. |
| `_read_response()` | Reads from the TCP socket until a complete FTP response line is received (ends at `\r\n` after the status line). Handles multi-line responses. |
| `_response_code(response)` | Extracts the 3-digit numeric code from a response string (e.g. `"150 ..."` → `150`). |
| `send(cmd)` | Sends a command over TCP, reads and prints the response. Returns the response string. |
| `_parse_data_endpoint(response)` | Extracts `(h1,h2,h3,h4,p1,p2)` from a `150` response and sets `self.data_host` / `self.data_port`. |
| `upload(local_path, remote_name)` | Reads local file, sends `STOR`, parses data endpoint from `150`, sends file over UDP via `send_bytes`, waits for `226`. |
| `download(remote_name, local_path)` | Sends `RETR`, parses endpoint from `150`, sends `READY` probe, receives file over UDP via `recv_bytes`, saves locally, waits for `226`. |
| `close()` | Closes the TCP control socket. |
| `main()` | Runs the interactive `ftp>` prompt. Supports raw FTP commands plus convenience aliases `put` and `get`. |

---

### `client/data.py`

Client-side UDP reliability layer (same protocol as server `data.py`).

| Function | Description |
|---|---|
| `_pack_packet(seq, flags, payload)` | Same as server — builds a binary UDP packet. |
| `_unpack_packet(data)` | Same as server — parses and validates a packet. |
| `_send_ack(sock, peer_addr, seq)` | Sends an ACK packet. |
| `send_bytes(sock, data, peer_addr, timeout)` | Public API. Reliably sends all bytes to the server using stop-and-wait ARQ. |
| `recv_bytes(sock, timeout)` | Public API. Reliably receives all bytes from the server. Returns `(data, peer_addr)`. |

---

## Typical Transfer Flow

### Upload (`put local.txt remote.txt`)

1. Client sends `STOR remote.txt` over TCP
2. Server opens UDP socket, replies `150 Ready to receive remote.txt (127,0,0,1,p1,p2).`
3. Client parses endpoint, sends file data over UDP (stop-and-wait)
4. Server receives data, saves to `data/remote.txt`
5. Server replies `226 Transfer complete.` over TCP

### Download (`get remote.txt local.txt`)

1. Client sends `RETR remote.txt` over TCP
2. Server opens UDP socket, replies `150 Opening data connection for remote.txt (127,0,0,1,p1,p2).`
3. Client sends `READY` probe, server sends file over UDP
4. Client saves received bytes to `local.txt`
5. Server replies `226 Transfer complete.` over TCP

---

## File Layout

```
hybrid_ftp/
├── client/
│   ├── client.py      # TCP client + CLI
│   └── data.py        # UDP send/receive (client side)
├── server/
│   ├── server.py      # TCP server entry point
│   ├── control.py     # Command dispatch + handlers
│   ├── session.py     # Per-client session state
│   ├── auth.py        # User authentication
│   ├── filesystem.py  # File read/write on disk
│   ├── data.py        # UDP transfer + RDT (server side)
│   └── reply_code.py  # FTP reply code constants
└── data/              # Server file storage + users.json
```
