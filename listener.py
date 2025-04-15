import socket
import json

def udp_listener(host='0.0.0.0', port=1799):
    """
    Lauscht auf dem angegebenen UDP-Port und gibt ankommende JSON-Nachrichten aus.

    :param host: IP/Host, an dem gelauscht wird (Standard: '0.0.0.0')
    :param port: UDP-Port (Standard: 1799)
    """
    # Socket erstellen (UDP)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))

    print(f"Starte UDP-Listener auf {host}:{port}")

    while True:
        # Daten empfangen (max. 2048 Bytes als Beispiel)
        data, addr = sock.recvfrom(2048)
        print(f"\nEmpfangen von {addr}:")
        
        # Versuchen, die empfangenen Daten als JSON zu interpretieren
        try:
            message = json.loads(data.decode('utf-8'))
            pretty_message = json.dumps(message, indent=4, ensure_ascii=False)
            print(f"JSON-Nachricht:\n{pretty_message}")
        except json.JSONDecodeError as e:
            print(f"Keine gültige JSON-Nachricht: {e}")
            print(f"Rohdaten: {data}")

if __name__ == "__main__":
    # Beispielaufruf mit Standardwerten
    udp_listener()
