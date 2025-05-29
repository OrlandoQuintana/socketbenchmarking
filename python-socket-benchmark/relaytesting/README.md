Run this in one terminal:

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