import asyncio
import time

async def read_loop(reader: asyncio.StreamReader, queue: asyncio.Queue):
    while True:
        data = await reader.read(1024)
        if not data:
            break
        await queue.put(data)  # Non-blocking queue

async def process_loop(queue: asyncio.Queue):
    start = time.time()
    msg_count = 0

    while True:
        data = await queue.get()  # Waits for new message
        # Simulated processing delay
        await asyncio.sleep(0.0005)
        
        msg_count += 1
        if msg_count % 1000 == 0:
            elapsed = time.time() - start
            print(f"Processed {msg_count} messages in {elapsed:.2f} seconds")

async def run_client():
    reader, writer = await asyncio.open_connection('127.0.0.1', 5555)
    print("Connected")
    
    queue = asyncio.Queue()

    # Run both read and process loops concurrently
    await asyncio.gather(
        read_loop(reader, queue),
        process_loop(queue)
    )

asyncio.run(run_client())
