import asyncio

MAGIC_WORD = b"MY_MAGIC10"
HEADER_SIZE = 12  # 10 bytes magic + 2 bytes length

async def downstream_client():
    reader, writer = await asyncio.open_connection('127.0.0.1', 5558)
    print("[*] Connected to relay at 127.0.0.1:5558")

    buffer = bytearray()

    try:
        while True:
            data = await reader.read(2048)
            if not data:
                print("[!] Relay closed connection.")
                break

            buffer.extend(data)

            while True:
                magic_index = buffer.find(MAGIC_WORD)
                if magic_index == -1:
                    buffer.clear()
                    break

                if magic_index > 0:
                    del buffer[:magic_index]

                if len(buffer) < HEADER_SIZE:
                    break

                payload_len = int.from_bytes(buffer[10:12], byteorder='big')
                total_len = HEADER_SIZE + payload_len

                if len(buffer) < total_len:
                    break

                full_message = buffer[:total_len]
                payload = full_message[HEADER_SIZE:]

                print(f"[<] Message:")
                print(f"    Magic Word: {full_message[:10].decode(errors='replace')}")
                print(f"    Length: {payload_len} bytes")
                #print(f"    Payload (hex): {payload.hex()}\n")

                del buffer[:total_len]
    finally:
        writer.close()
        await writer.wait_closed()

if __name__ == "__main__":
    try:
        asyncio.run(downstream_client())
    except KeyboardInterrupt:
        print("\n[!] Downstream client stopped by user.")