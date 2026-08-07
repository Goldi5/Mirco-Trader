p = r'C:/Users/goldi/AppData/Local/hermes/scripts/micro-trader-pipeline.py'
s = open(p, encoding='utf-8').read()

# Bridge-Start-Funktion nach logging setup einfügen
anchor = 'log = logging.getLogger("pipeline")'
assert anchor in s, 'logging anchor nicht gefunden'

func = '''

def ensure_whatsapp_bridge():
    """Startet den Hermes WhatsApp-Bridge (Node.js, Port 3000) falls nicht läuft.
    Der Gateway managed den Bridge auf Windows nicht selbst -> wir starten ihn.
    """
    import socket
    port = 3000
    # Prüfe ob Port offen
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return  # Bridge läuft bereits
    except Exception:
        pass
    # Bridge starten (Hintergrund)
    bridge = os.path.join(
        os.environ.get("LOCALAPPDATA", r"C:\Users\goldi\AppData\Local"),
        "hermes", "hermes-agent", "scripts", "whatsapp-bridge", "bridge.js")
    node = "node"
    if os.path.exists(bridge):
        try:
            subprocess.Popen([node, bridge], creationflags=0x00000008,  # DETACHED_PROCESS
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log.info("WhatsApp-Bridge gestartet (Port 3000)")
        except Exception as e:
            log.warning("WhatsApp-Bridge Start fehlgeschlagen: %s", e)
'''

s = s.replace(anchor, anchor + func, 1)
open(p, 'w', encoding='utf-8').write(s)
print('pipeline.py: ensure_whatsapp_bridge() eingebaut')
