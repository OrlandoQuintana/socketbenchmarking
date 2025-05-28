import asyncio
import os

MAGIC_WORD = b"MY_MAGIC10"  # 10 bytes exactly

def build_message(payload: bytes) -> bytes:
    if len(payload) > 2048:
        raise ValueError("Payload too long")
    length = len(payload).to_bytes(2, byteorder='big')  # 2 bytes
    return MAGIC_WORD + length + payload

async def handle_relay(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"[+] Relay connected from {addr}")

    try:
        while True:
            payload = os.urandom(2048)  
            message = build_message(payload)
            writer.write(message)
            await writer.drain()
            print(f"[>] Sent message of {len(payload)} bytes")
            await asyncio.sleep(0.5)
    except (asyncio.CancelledError, ConnectionResetError):
        print(f"[-] Relay disconnected: {addr}")
    finally:
        writer.close()
        await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle_relay, '127.0.0.1', 5557)
    print("[*] Upstream server running on 127.0.0.1:5557")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Upstream server stopped by user.")