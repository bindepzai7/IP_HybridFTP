import argparse
import sys
from .client import FTPClient
import traceback

def main():
    parser = argparse.ArgumentParser(prog="python -m client")
    parser.add_argument("host", nargs="?", default="127.0.0.1")
    parser.add_argument("port", nargs="?", type=int, default=2121)
    parser.add_argument(
        "--verify_hash",
        action="store_true",
        help="print the SHA-256 integrity check on successful transfers "
             "(a mismatch is always reported)",
    )
    args = parser.parse_args()
    host, port = args.host, args.port

    client = FTPClient(verbose_hash=args.verify_hash)

    try:
        client.connect(host, port)
    except ConnectionRefusedError:
        print(f"[!] Unable to connect to {host}:{port}")
        sys.exit(1)

    # Read server welcome message
    print(client.control.read_line())

    while True:
        try:
            raw = input("ftp> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        tokens = raw.split()
        cmd = tokens[0].upper()

        if cmd == "QUIT":
            client._send_cmd("QUIT")
            break

        if cmd == "PASV":
            try:
                client.set_passive_mode()
            except Exception as e:
                print(f"[!] {e}")
            continue

        if cmd == "PORT":
            if len(tokens) < 2:
                print("Usage: PORT <h1,h2,h3,h4,p1,p2>")
                continue

            try:
                client.set_active_mode(tokens[1])
            except Exception as e:
                print(f"[!] {e}")
            continue

        if cmd == "LIST":
            path = tokens[1] if len(tokens) > 1 else ""
            try:
                client.list_dir(path)
            except Exception as e:
                print(f"[!] {e}")
            continue
        
        if cmd == "NLST":
            path = tokens[1] if len(tokens) > 1 else ""
            try: 
                client.nlst(path)
            except Exception as e:
                print(f"[!] {e}")
            continue

        if cmd == "RETR":
            if len(tokens) < 2:
                print("Usage: RETR <remote_file> [local_file]")
                continue

            remote = tokens[1]
            local = tokens[2] if len(tokens) > 2 else ""

            try:
                client.retr(remote, local)
            except KeyboardInterrupt:
                print("\n[Client] Interrupt by user.")
                client.abort()
            except Exception as e:
                print(f"[!] {e}")
            continue

        if cmd in "STOR":
            if len(tokens) < 2:
                print("Usage: STOR <local_file> [remote_file]")
                continue

            local = tokens[1]
            remote = tokens[2] if len(tokens) > 2 else ""

            try:
                client.stor(local, remote)
            except KeyboardInterrupt:
                print("\n[Client] Interrupt by user.")
                client.abort()
            except Exception as e:
                print(f"[!] {e}")
            continue
        
        if cmd == "APPE":
            if len(tokens) < 2:
                print("Usage: APPE <local_file> [remote_file]")
                continue

            local = tokens[1]
            remote = tokens[2] if len(tokens) > 2 else ""

            try:
                client.appe(local, remote)
            except KeyboardInterrupt:
                print("\n[Client] Interrupt by user.")
                client.abort()
            except Exception as e:
                print(f"[!] {e}")
            continue
        
        if cmd == "STOU":
            if len(tokens) < 2:
                print("Usage: STOU <local_file>")
                continue

            local = tokens[1]

            try:
                client.stou(local)
            except KeyboardInterrupt:
                print("\n[Client] Interrupt by user.")
                client.abort()
            except Exception as e:
                print(f"[!] {e}")
            continue
        
        if cmd == "MODE":
            if len(tokens) < 2:
                print("Usage: MODE <S|B|C>")
                continue
            
            try:
                client.set_transfer_mode(tokens[1])
            except Exception as e:
                print(f"[!] {e}")
            continue
        # Pass-through commands
        # USER, PASS, PWD, CWD, CDUP, MKD, RMD,
        # DELE, RNFR, RNTO, SIZE, TYPE, NOOP, etc.
        try:
            client._send_cmd(raw)
        except Exception as e:
            print(f"[!] {e}")
            break

    client.disconnect()
    print("[Client] Connection closed.")


if __name__ == "__main__":
    main()