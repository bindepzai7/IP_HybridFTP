from .server import FTPServer

def main():
    host = "0.0.0.0"
    port = 2121
    
    server = FTPServer(host=host, port=port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[!] Terminating...")
        server.stop()

if __name__ == "__main__":
    main()