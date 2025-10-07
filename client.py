import asyncio
import logging

PROXY_HOST = "6.tcp.eu.ngrok.io"  # your ngrok public host
PROXY_PORT = 11540                # your ngrok public port
LOCAL_BIND = "0.0.0.0"
PORTS_TO_FORWARD = [3306, 3307]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

async def pipe(reader, writer):
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except:
            pass

async def handle_local_client(local_reader, local_writer, local_port):
    peer = local_writer.get_extra_info("peername")
    logging.info("🔌 Local client connected %s -> localhost:%d", peer, local_port)

    prefix = f"/{local_port}\n".encode()
    try:
        proxy_reader, proxy_writer = await asyncio.open_connection(PROXY_HOST, PROXY_PORT)
    except Exception as e:
        logging.error("❌ Failed to connect to proxy %s:%d: %s", PROXY_HOST, PROXY_PORT, e)
        try:
            local_writer.write(b"Failed to reach proxy\n")
            await local_writer.drain()
        except:
            pass
        local_writer.close()
        await local_writer.wait_closed()
        return

    try:
        proxy_writer.write(prefix)
        await proxy_writer.drain()
    except Exception as e:
        logging.error("❌ Failed to send prefix to proxy: %s", e)
        proxy_writer.close()
        await proxy_writer.wait_closed()
        local_writer.close()
        await local_writer.wait_closed()
        return

    await asyncio.gather(
        pipe(local_reader, proxy_writer),
        pipe(proxy_reader, local_writer),
        return_exceptions=True
    )

    logging.info("🔒 Connection closed for localhost:%d from %s", local_port, peer)

async def start_listener(port):
    server = await asyncio.start_server(lambda r, w: handle_local_client(r, w, port), LOCAL_BIND, port)
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    logging.info("🎧 Receiver listening on %s for port %d (proxy %s:%d)", addrs, port, PROXY_HOST, PROXY_PORT)
    async with server:
        await server.serve_forever()

async def main():
    tasks = [start_listener(p) for p in PORTS_TO_FORWARD]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Receiver stopped by user.")
