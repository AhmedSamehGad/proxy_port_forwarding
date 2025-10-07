import asyncio

# Map prefixes to target ports
PREFIX_MAP = {
    b"/3306": 3306,
    b"/3307": 3307
}

async def handle_client(reader, writer):
    try:
        # Read the prefix from client (e.g., /3306)
        prefix = await reader.readuntil(b'\n')  # client must send "/3306\n"
        prefix = prefix.strip()
        if prefix not in PREFIX_MAP:
            writer.write(b"Unknown prefix\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return

        target_port = PREFIX_MAP[prefix]
        remote_reader, remote_writer = await asyncio.open_connection('127.0.0.1', target_port)

        async def forward(src, dst):
            try:
                while True:
                    data = await src.read(4096)
                    if not data:
                        break
                    dst.write(data)
                    await dst.drain()
            except:
                pass
            finally:
                dst.close()
                await dst.wait_closed()

        await asyncio.gather(
            forward(reader, remote_writer),
            forward(remote_reader, writer)
        )

    except Exception as e:
        print(f"Error: {e}")
        writer.close()
        await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle_client, '0.0.0.0', 8080)
    print("TCP proxy running on 0.0.0.0:8080")
    async with server:
        await server.serve_forever()

asyncio.run(main())
