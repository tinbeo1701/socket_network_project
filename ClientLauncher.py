import sys
from tkinter import Tk
from Client import Client

if __name__ == "__main__":
    try:
        serverAddr = sys.argv[1]
        serverPort = sys.argv[2]
        rtpPort = sys.argv[3]
        fileName = sys.argv[4]
        hd_mode = False
        if len(sys.argv) > 5 and sys.argv[5].lower() == "--hd":
            hd_mode = True
    except:
        print(
            "[Usage: ClientLauncher.py Server_name Server_port RTP_port Video_file [--hd]]\n"
        )

    root = Tk()

    # Create a new client
    app = Client(root, serverAddr, serverPort, rtpPort, fileName, hd_mode=hd_mode)
    app.master.title(f"RTPClient {'(HD Mode)' if hd_mode else ''}")
    root.mainloop()
