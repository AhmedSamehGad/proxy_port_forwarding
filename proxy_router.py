import asyncio

FORWARDING_RULES = [
    {"prefix": b"/3306", "target_port": 3306},
    {"prefix": b"/3307", "target_port": 3307},
]

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8080

PREFIX_MAP = {rule["prefix"]: rule["target_port"] for rule in FORWARDING_RULES}

async def handle_client(reader, writer):
    addr = writer.get_extra_info("peername")
    print(f"🔗 Connection from {addr}")

    try:
        prefix = await reader.readuntil(b'\n')
        prefix = prefix.strip()
        if prefix not in PREFIX_MAP:
            writer.write(b"Unknown prefix\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            print(f"❌ Unknown prefix from {addr}")
            return

        target_port = PREFIX_MAP[prefix]
        print(f"➡️ Forwarding {addr} to 127.0.0.1:{target_port}")

        remote_reader, remote_writer = await asyncio.open_connection("127.0.0.1", target_port)

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
        print(f"⚠️ Error: {e}")
        writer.close()
        await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle_client, LISTEN_HOST, LISTEN_PORT)
    print(f"🚀 Proxy server running on {LISTEN_HOST}:{LISTEN_PORT}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Proxy server stopped.")
