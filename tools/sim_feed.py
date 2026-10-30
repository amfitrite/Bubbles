import socket
import time
import random
import sys

def run_sim(port=5555, rate_per_sec=30):
    print(f"Connecting to Bubbles on 127.0.0.1:{port}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("127.0.0.1", port))
        print("Connected! Sending META and ticks...")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    # Send META
    s.sendall(b"META|XAUUSD|2|0.01|0.01|100\n")

    base_price = 4000.0
    delay = 1.0 / rate_per_sec

    try:
        while True:
            ts = int(time.time() * 1000)
            delta_p = random.choice([-0.05, -0.01, 0.0, 0.01, 0.05])
            base_price = max(3950.0, min(4050.0, base_price + delta_p))

            bid = base_price
            ask = base_price + 0.10
            is_buy = random.random() > 0.48
            last = ask if is_buy else bid
            vol = round(random.choices([1.0, 2.0, 5.0, 15.0, 50.0], weights=[50, 30, 12, 6, 2])[0], 2)
            flags = 32 if is_buy else 64

            line = f"TICK|XAUUSD|{ts}|{bid:.2f}|{ask:.2f}|{last:.2f}|{vol}|{flags}\n"
            s.sendall(line.encode("ascii"))
            time.sleep(delay)

    except KeyboardInterrupt:
        print("\nStopping feed.")
    finally:
        s.close()

if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else 5555
    r = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    run_sim(p, r)
