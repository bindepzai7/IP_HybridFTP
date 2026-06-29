import sys
from .client import FTPClient
import traceback

def main():
    host = "127.0.0.1"
    port = 2121

    client = FTPClient()

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
                print("\n[Client] Interrupt by user. Sending ABOR...")
                client._send_cmd("ABOR")
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
                print("\n[Client] Interrupt by user. Sending ABOR...")
                client._send_cmd("ABOR")
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
                print("\n[Client] Interrupt by user. Sending ABOR...")
                client._send_cmd("ABOR")
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
                print("\n[Client] Interrupt by user. Sending ABOR...")
                client._send_cmd("ABOR")
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