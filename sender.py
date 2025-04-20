import socket
import sys

if len(sys.argv) < 2:
    print("Usage: python sender.py <target IP>")
    sys.exit(1)

UDP_IP = sys.argv[1]
UDP_PORT = 1799
MESSAGE = b"Hello, World!"

print("UDP target IP: %s" % UDP_IP)
print("UDP target port: %s" % UDP_PORT)
print("message: %s" % MESSAGE)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(MESSAGE, (UDP_IP, UDP_PORT))