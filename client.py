import asyncio
import logging

FORWARDING_RULES = [
    {"local_port": 3306, "proxy_host": "5.tcp.eu.ngrok.io", "proxy_port": 19745},
    {"local_port": 3307, "proxy_host": "5.tcp.eu.ngrok.io", "proxy_port": 19745},
]

LOCAL_BIND = "0.0.0.0"

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

async def handle_local_client(local_reader, local_writer, proxy_host, proxy_port, local_port):
    peer = local_writer.get_extra_info("peername")
    logging.info("🔌 Local client connected %s -> localhost:%d", peer, local_port)

    prefix = f"/{local_port}\n".encode()
    try:
        proxy_reader, proxy_writer = await asyncio.open_connection(proxy_host, proxy_port)
    except Exception as e:
        logging.error("❌ Failed to connect to proxy %s:%d: %s", proxy_host, proxy_port, e)
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

async def start_listener(local_port, proxy_host, proxy_port):
    server = await asyncio.start_server(
        lambda r, w: handle_local_client(r, w, proxy_host, proxy_port, local_port),
        LOCAL_BIND,
        local_port
    )
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    logging.info("🎧 Receiver listening on %s for port %d (proxy %s:%d)", addrs, local_port, proxy_host, proxy_port)
    async with server:
        await server.serve_forever()

async def main():
    tasks = [start_listener(rule["local_port"], rule["proxy_host"], rule["proxy_port"]) for rule in FORWARDING_RULES]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Receiver stopped by user.")
