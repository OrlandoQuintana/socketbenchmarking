import socket
import threading
import time

def client_thread(conn, addr):
    print(f"Client connected: {addr}")
    try:
        while True:
            conn.sendall(b"x" * 128) # 128-byte messages
            time.sleep(0.00001) # 100,000 messages per second
    except:
        pass
    finally:
        conn.close()

s = socket.socket()
s.bind(('127.0.0.1', 5555))
s.listen()
print("Server running...")

while True:
    conn, addr = s.accept()
    threading.Thread(target=client_thread, args=(conn, addr), daemon=True).start()
                     