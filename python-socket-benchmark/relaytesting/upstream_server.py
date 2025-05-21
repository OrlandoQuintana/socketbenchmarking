# upstream_sender.py
import asyncio

async def main():
    server = await asyncio.start_server(handle, '127.0.0.1', 5557)
    async with server:
        await server.serve_forever()

async def handle(reader, writer):
    try:
        while True:
            writer.write(b"hello from upstream\n")
            await writer.drain()
            await asyncio.sleep(1)
    except Exception:
        pass
    finally:
        writer.close()
        await writer.wait_closed()

asyncio.run(main())
