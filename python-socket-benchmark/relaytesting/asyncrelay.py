import asyncio

# Global dictionary to hold per-client queues
connected_clients = {}  # writer -> client_queue

# Reads from the upstream server and puts data into a shared queue
async def read_loop(reader: asyncio.StreamReader, shared_queue: asyncio.Queue):
    while True:
        data = await reader.read(20480)
        if not data:
            print("Upstream server closed connection.")
            break
        await shared_queue.put(data)

# Handles a newly connected downstream client
async def handle_client(reader, writer, connected_clients):
    peer = writer.get_extra_info("peername")
    print(f"[+] Client connected: {peer}")

    client_queue = asyncio.Queue(maxsize=64)
    connected_clients[writer] = client_queue

    writer_task = asyncio.create_task(client_writer_loop(writer, client_queue))

    try:
        await reader.read(1)  # just to keep the connection open
    except Exception:
        pass
    finally:
        print(f"[-] Client disconnected: {peer}")
        writer_task.cancel()
        del connected_clients[writer]
        writer.close()
        await writer.wait_closed()

# Writes data from a client's personal queue to their socket
async def client_writer_loop(writer, queue):
    try:
        while True:
            data = await queue.get()
            writer.write(data)
            await writer.drain()
    except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
        pass

# Main relay loop: forwards upstream data to all connected client queues
async def process_loop(shared_queue):
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, connected_clients),
        "127.0.0.1", 5558
    )

    async with server:
        print("[*] Relay server started on 127.0.0.1:5558")
        while True:
            data = await shared_queue.get()
            for writer, q in list(connected_clients.items()):
                try:
                    q.put_nowait(data)
                except asyncio.QueueFull:
                    print(f"[!] Dropped data for client {writer.get_extra_info('peername')} (queue full)")

# Startup: connects to upstream and starts read + process loops
async def run():
    print("[*] Connecting to upstream server at 127.0.0.1:5557...")
    reader, _ = await asyncio.open_connection("127.0.0.1", 5557)
    print("[+] Connected to upstream.")

    shared_queue = asyncio.Queue(maxsize=128)

    await asyncio.gather(
        read_loop(reader, shared_queue),
        process_loop(shared_queue)
    )

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n[!] Relay stopped by user.")
