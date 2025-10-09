import imaplib
import email
import re
import asyncio
import logging

# ========== GET PUBLIC IP & PORT FROM EMAIL ==========
EMAIL = "staema924@gmail.com"
PASSWORD = "punf qpws ggxe fqlc"

mail = imaplib.IMAP4_SSL("imap.gmail.com")
mail.login(EMAIL, PASSWORD)
mail.select("inbox")

# Search for emails specifically from nmailer833@gmail.com
status, data = mail.search(None, 'FROM "nmailer833@gmail.com"')
email_ids = data[0].split()

if not email_ids:
    print("No emails found from nmailer833@gmail.com.")
    exit()

# Get the latest email from this sender
latest_email_id = email_ids[-1]
status, data = mail.fetch(latest_email_id, "(RFC822)")
raw_email = data[0][1]
msg = email.message_from_bytes(raw_email)

# Verify it's actually from the expected sender
sender = msg.get("From", "")
if "nmailer833@gmail.com" not in sender:
    print(f"Unexpected sender: {sender}")
    exit()

body = ""
if msg.is_multipart():
    for part in msg.walk():
        if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
            body = part.get_payload(decode=True).decode()
            break
else:
    body = msg.get_payload(decode=True).decode()

ip_match = re.search(r"IP:\s*([\d.]+)", body)
port_match = re.search(r"Port:\s*(\d+)", body)

PUBLIC_IP = ip_match.group(1) if ip_match else None
PUBLIC_PORT = int(port_match.group(1)) if port_match else None

if not PUBLIC_IP or not PUBLIC_PORT:
    print("❌ Could not extract IP or Port from email.")
    exit()

print("✅ Extracted from Email:")
print("Public IP:", PUBLIC_IP)
print("Public Port:", PUBLIC_PORT)
print("Email from:", sender)

# ========== ASYNC PROXY FORWARDER ==========
FORWARDING_RULES = [
    {"local_port": 3306},
    {"local_port": 3307},
    {"local_port": 22},
    {"local_port": 80},
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
    tasks = [start_listener(rule["local_port"], PUBLIC_IP, PUBLIC_PORT) for rule in FORWARDING_RULES]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Receiver stopped by user.")