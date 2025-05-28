import asyncio

# Global dictionary to hold per-client queues
connected_clients = {}  # writer -> client_queue

MAGIC_WORD = b"MY_MAGIC10"
HEADER_SIZE = 12  # 10 for magic + 2 for length

# Reads from the upstream server, frames the message using the magic word, and puts 1 full message into a shared queue
async def read_loop(reader: asyncio.StreamReader, shared_queue: asyncio.Queue):
    buffer = bytearray()

    while True:
        data = await reader.read(2048)
        if not data:
            print("Upstream server closed connection.")
            break

        buffer.extend(data)

        while True:
            # Find the start of a message
            magic_index = buffer.find(MAGIC_WORD)
            if magic_index == -1:
                # No magic word in buffer; discard junk
                buffer.clear()
                break

            # If there's junk before the magic word, remove it
            if magic_index > 0:
                del buffer[:magic_index]

            # Now buffer starts with MAGIC_WORD
            if len(buffer) < HEADER_SIZE:
                # Wait for more bytes (not enough to get the length)
                break

            # Extract length (2 bytes after magic word)
            payload_length = int.from_bytes(buffer[10:12], byteorder='big')
            total_message_length = HEADER_SIZE + payload_length

            if len(buffer) < total_message_length:
                # Full message not received yet
                break

            # Extract full message
            full_message = bytes(buffer[:total_message_length])
            await shared_queue.put(full_message)

            # Remove it from buffer
            del buffer[:total_message_length]

# Handles a newly connected downstream client
async def handle_client(reader, writer):
    peer = writer.get_extra_info("peername")
    print(f"[+] Client connected: {peer}")

    client_queue = asyncio.Queue(maxsize=64)
    connected_clients[writer] = client_queue

    writer_task = asyncio.create_task(client_writer_loop(writer, client_queue))

    try:
        await reader.read(1)  # Keeps the connection alive
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
        handle_client,
        "127.0.0.1", 5558
    )

    async with server:
        print("[*] Relay server started on 127.0.0.1:5558")
        while True:
            data = await shared_queue.get()
            for writer, q in list(connected_clients.items()):
                try:
                    await q.put(data)
                except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
                    print(f"[!] Client write error: {writer.get_extra_info('peername')}")


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
