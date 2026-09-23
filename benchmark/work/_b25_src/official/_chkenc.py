from pathlib import Path

d = Path(__file__).resolve().parent
for name in ["71-2025-QH15.txt", "13-2023-ND-CP.txt", "53-2022-ND-CP.txt"]:
    b = (d / name).read_bytes()
    bad = []
    i = 0
    while i < len(b):
        try:
            b[i:].decode("utf-8")
            break
        except UnicodeDecodeError as e:
            at = i + e.start
            bad.append((at, b[at:at + 8]))
            i = at + 1
            if len(bad) > 12:
                break
    text = b.decode("utf-8", errors="replace")
    print(name, "bytes", len(b), "bad_spots_shown", len(bad), "dieu", text.count("Điều"), "fffd", text.count("�"))
    for at, window in bad[:6]:
        print(" ", at, window)
    head = text.replace("\r", "")[:240]
    print(head)
    print("---")
