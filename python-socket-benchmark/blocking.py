import socket
import time

sock = socket.socket()
sock.connect(('127.0.0.1', 5555))
print("Connected")

start = time.time()
msg_count = 0

try:
    while True:
        data = sock.recv(1024)
        if not data:
            break
        time.sleep(0.0005)
        msg_count += 1
        if msg_count % 1000 == 0:
            elapsed = time.time() - start
            print(f"Received {msg_count} messages in {elapsed: .2f} seconds")
except KeyboardInterrupt:
    pass
finally:
    sock.close()
