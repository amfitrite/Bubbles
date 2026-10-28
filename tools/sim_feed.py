import socket
import time
import random
import argparse
import sys

def run_simulation(host="127.0.0.1", port=5558, symbol="XAUUSD", count=2000, live=True):
    print(f"Connecting to Bubbles terminal at {host}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        print("Connected! Sending handshake & historical ticks...")
    except Exception as e:
        print(f"Error: Could not connect to {host}:{port}: {e}")
        print("Make sure Bubbles app is running first!")
        return

    # 1. Send Handshake
    sock.sendall(f"#SYMBOL:{symbol}\n".encode('utf-8'))
    time.sleep(0.05)
    sock.sendall(f"#META:{symbol},2,0.01,0.01,100.00\n".encode('utf-8'))
    time.sleep(0.05)

    # 2. Generate and Send History
    # Start price around 2735.00 (XAUUSD realistic level)
    price = 2735.00
    now_ms = int(time.time() * 1000)
    # Start history 10 minutes ago
    start_ts = now_ms - (count * 150)

    sock.sendall(f"#HIST_START:{count}\n".encode('utf-8'))
    
    current_ts = start_ts
    history_lines = []
    for _ in range(count):
        # Micro price movement (-0.05 to +0.05)
        step = random.choice([-0.03, -0.02, -0.01, 0.0, 0.0, 0.01, 0.02, 0.03])
        price = round(price + step, 2)
        spread = 0.15
        bid = round(price - spread / 2.0, 2)
        ask = round(price + spread / 2.0, 2)
        last = price

        # Volume clustering: mostly 1.0 (tick volume), occasionally bursts up to 30.0
        if random.random() < 0.06:
            vol = float(random.randint(5, 35))
        else:
            vol = 1.0

        # Flag 32=buy, 64=sell
        flag = 32 if step >= 0 else 64
        current_ts += random.randint(30, 250)

        history_lines.append(f"{current_ts},{bid:.2f},{ask:.2f},{last:.2f},{vol:.1f},{flag}\n")

        # Send in chunks of 200
        if len(history_lines) >= 200:
            sock.sendall("".join(history_lines).encode('utf-8'))
            history_lines = []

    if history_lines:
        sock.sendall("".join(history_lines).encode('utf-8'))

    sock.sendall(b"#HIST_END\n")
    print(f"Sent {count} historical ticks. Entering live feed mode...")

    # 3. Stream Live Ticks
    if not live:
        sock.close()
        return

    try:
        while True:
            step = random.choice([-0.02, -0.01, 0.0, 0.0, 0.01, 0.02])
            price = round(price + step, 2)
            spread = 0.15
            bid = round(price - spread / 2.0, 2)
            ask = round(price + spread / 2.0, 2)
            last = price
            
            # Outlier volume spikes
            if random.random() < 0.08:
                vol = float(random.randint(8, 45))
            else:
                vol = 1.0

            flag = 32 if step >= 0 else 64
            now_ms = int(time.time() * 1000)

            msg = f"{now_ms},{bid:.2f},{ask:.2f},{last:.2f},{vol:.1f},{flag}\n"
            sock.sendall(msg.encode('utf-8'))

            # Ticks arrive every 25ms to 120ms
            time.sleep(random.uniform(0.03, 0.12))

    except KeyboardInterrupt:
        print("\nStopping simulated feed...")
    finally:
        sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate MT5 EA Order Flow Feed for Bubbles")
    parser.add_argument("--port", type=int, default=5558, help="Port to connect (default 5558)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host (default 127.0.0.1)")
    parser.add_argument("--count", type=int, default=2500, help="Number of historical ticks (default 2500)")
    args = parser.parse_args()

    run_simulation(host=args.host, port=args.port, count=args.count)
