uRun this in one terminal:

    python3 upstream_server.py

In another terminal, run:

    python3 asyncrelay.py

In another terminal, run:

    python3 downstream_client.py


import asyncio
from typing import Dict

MESSAGE_SIZE = 1034
MAGIC_MASK = 0xFFFFFFC0  # 26-bit mask

class RelayConfig:
    def __init__(self, upstream_host: str, upstream_port: int, downstream_host: str, downstream_port: int, magic_word: bytes):
        self.upstream_host = upstream_host
        self.upstream_port = upstream_port
        self.downstream_host = downstream_host
        self.downstream_port = downstream_port
        self.magic_word = magic_word


def find_magic_with_mask(buffer: bytearray, magic_word: bytes) -> int:
    target = int.from_bytes(magic_word, byteorder='big') & MAGIC_MASK
    for i in range(len(buffer) - 3):
        candidate = int.from_bytes(buffer[i:i+4], byteorder='big')
        if (candidate & MAGIC_MASK) == target:
            return i
    return -1


class UpstreamReader:
    def __init__(self, reader: asyncio.StreamReader, shared_queue: asyncio.Queue, config: RelayConfig):
        self.reader = reader
        self.shared_queue = shared_queue
        self.config = config
        self.buffer = bytearray()

    async def run(self):
        while True:
            data = await self.reader.read(2048)
            if not data:
                print("[!] Upstream connection closed.")
                break
            self.buffer.extend(data)
            await self._process_buffer()

    async def _process_buffer(self):
        while True:
            index = find_magic_with_mask(self.buffer, self.config.magic_word)
            if index == -1:
                # No magic found — optionally trim junk
                if len(self.buffer) > 4096:
                    del self.buffer[:-4]
                break

            if index > 0:
                del self.buffer[:index]

            if len(self.buffer) < MESSAGE_SIZE:
                break

            message = bytes(self.buffer[:MESSAGE_SIZE])
            await self.shared_queue.put(message)
            del self.buffer[:MESSAGE_SIZE]


class DownstreamClient:
    def __init__(self, writer: asyncio.StreamWriter):
        self.writer = writer
        self.queue = asyncio.Queue(maxsize=64)
        self.task = asyncio.create_task(self._writer_loop())

    async def _writer_loop(self):
        try:
            while True:
                data = await self.queue.get()
                self.writer.write(data)
                await self.writer.drain()
        except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
            pass

    async def send(self, data: bytes):
        await self.queue.put(data)

    async def close(self):
        self.task.cancel()
        self.writer.close()
        await self.writer.wait_closed()


class ClientManager:
    def __init__(self):
        self.clients: Dict[asyncio.StreamWriter, DownstreamClient] = {}

    def add_client(self, writer: asyncio.StreamWriter):
        client = DownstreamClient(writer)
        self.clients[writer] = client

    def remove_client(self, writer: asyncio.StreamWriter):
        client = self.clients.pop(writer, None)
        if client:
            asyncio.create_task(client.close())

    async def broadcast(self, data: bytes):
        for client in list(self.clients.values()):
            try:
                await client.send(data)
            except Exception:
                pass


class RelayServer:
    def __init__(self, config: RelayConfig):
        self.config = config
        self.shared_queue = asyncio.Queue(maxsize=128)
        self.client_manager = ClientManager()

    async def handle_downstream_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        print(f"[+] Client connected: {peer}")
        self.client_manager.add_client(writer)
        try:
            await reader.read(1)
        except Exception:
            pass
        finally:
            print(f"[-] Client disconnected: {peer}")
            self.client_manager.remove_client(writer)

    async def start_downstream_server(self):
        server = await asyncio.start_server(
            self.handle_downstream_client,
            self.config.downstream_host,
            self.config.downstream_port
        )
        print(f"[*] Relay server started on {self.config.downstream_host}:{self.config.downstream_port}")
        async with server:
            await self._broadcast_loop()

    async def _broadcast_loop(self):
        while True:
            data = await self.shared_queue.get()
            await self.client_manager.broadcast(data)

    async def run(self):
        print(f"[*] Connecting to upstream server at {self.config.upstream_host}:{self.config.upstream_port}")
        reader, _ = await asyncio.open_connection(self.config.upstream_host, self.config.upstream_port)
        print("[+] Connected to upstream.")
        upstream_reader = UpstreamReader(reader, self.shared_queue, self.config)
        await asyncio.gather(
            upstream_reader.run(),
            self.start_downstream_server()
        )


# Entrypoint
async def main():
    config = RelayConfig(
        upstream_host="127.0.0.1",
        upstream_port=5557,
        downstream_host="127.0.0.1",
        downstream_port=5558,
        magic_word=b'\x01\x00\x48\x40'  # Example 4-byte base magic word
    )
    server = RelayServer(config)
    await server.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Relay shut down.")








or









import asyncio

connected_clients = {}  # writer -> client_queue

MAGIC_WORD = b"\x01\x00\x48\x40"  # Just an example 4-byte sequence (edit as needed)
MAGIC_MASK = 0xFFFFFFC0           # Top 26 bits must match
MESSAGE_SIZE = 1034               # Full message length (header + payload)

# Reads from upstream, extracts full messages based on masked magic word
async def read_loop(reader: asyncio.StreamReader, shared_queue: asyncio.Queue):
    buffer = bytearray()

    while True:
        data = await reader.read(2048)
        if not data:
            print("[!] Upstream server closed connection.")
            break

        buffer.extend(data)

        while True:
            if len(buffer) < 4:
                break

            found = False
            for i in range(len(buffer) - 3):
                candidate = int.from_bytes(buffer[i:i+4], 'big')
                magic_val = int.from_bytes(MAGIC_WORD, 'big')

                if (candidate & MAGIC_MASK) == (magic_val & MAGIC_MASK):
                    # Found candidate magic
                    if len(buffer) - i >= MESSAGE_SIZE:
                        message = bytes(buffer[i:i+MESSAGE_SIZE])
                        await shared_queue.put(message)
                        del buffer[:i+MESSAGE_SIZE]
                        found = True
                        break
                    else:
                        # Wait for more bytes
                        if i > 0:
                            del buffer[:i]  # trim junk before possible start
                        found = True
                        break

            if not found:
                # Trim buffer if it’s growing too large with no match
                if len(buffer) > 4096:
                    del buffer[:-4]
                break

# Handles a newly connected downstream client
async def handle_client(reader, writer):
    peer = writer.get_extra_info("peername")
    print(f"[+] Client connected: {peer}")

    client_queue = asyncio.Queue(maxsize=64)
    connected_clients[writer] = client_queue

    writer_task = asyncio.create_task(client_writer_loop(writer, client_queue))

    try:
        await reader.read(1)
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

# Relay loop: distributes upstream data to all connected clients
async def process_loop(shared_queue):
    server = await asyncio.start_server(handle_client, "127.0.0.1", 5558)

    async with server:
        print("[*] Relay server started on 127.0.0.1:5558")
        while True:
            data = await shared_queue.get()
            for writer, q in list(connected_clients.items()):
                try:
                    await q.put(data)
                except Exception:
                    print(f"[!] Client write error: {writer.get_extra_info('peername')}")

# Startup
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