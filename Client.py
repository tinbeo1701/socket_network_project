from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os, time
from RtpPacket import RtpPacket
from FragmentationHandler import FragmentationHandler, FragmentationHeader
from NetworkAnalytics import NetworkAnalytics

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3

    def __init__(self, master, serveraddr, serverport, rtpport, filename, hd_mode=False):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.frameNbr = 0

        self.playEvent = threading.Event()
        self.playEvent.clear()
        
        # HD streaming support
        self.hd_mode = hd_mode
        self.fragmentation_handler = FragmentationHandler()
        self.network_analytics = NetworkAnalytics()
        self.last_seq_num = -1
        
        # Frame reassembly buffer
        self.reassembly_buffer = {}
        
        # Low-latency playback buffer
        self.frame_queue = []
        self.max_queue_size = 3
        self.queue_lock = threading.Lock()
        self.display_started = False
        self.rtp_thread_stop_event = threading.Event()

        # Analytics display
        self.stats_update_interval = 1.0 # seconds
        self.last_stats_update = time.time()
        
        self.createWidgets()
        self.connectToServer()

    def createWidgets(self):
        # Control buttons
        self.setup = Button(self.master, width=20, padx=3, pady=3)
        self.setup["text"] = "Setup"
        self.setup["command"] = self.setupMovie
        self.setup.grid(row=1, column=0, padx=2, pady=2)

        self.start = Button(self.master, width=20, padx=3, pady=3)
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=1, column=1, padx=2, pady=2)

        self.pause = Button(self.master, width=20, padx=3, pady=3)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=1, column=2, padx=2, pady=2)

        self.teardown = Button(self.master, width=20, padx=3, pady=3)
        self.teardown["text"] = "Teardown"
        self.teardown["command"] = self.exitClient
        self.teardown.grid(row=1, column=3, padx=2, pady=2)

        # Video display label
        self.label = Label(self.master, height=19)
        self.label.grid(
            row=0, column=0, columnspan=4, sticky=W + E + N + S, padx=5, pady=5
        )
        
        # Analytics display
        self.stats_label = Label(self.master, text="", justify=LEFT, font=("Arial", 9))
        self.stats_label.grid(row=2, column=0, columnspan=4, sticky=W + E, padx=5, pady=5)

    def setupMovie(self):
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)

    def exitClient(self):
        self.sendRtspRequest(self.TEARDOWN)
        self.master.destroy()
        try:
            os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)
        except:
            pass

    def pauseMovie(self):
        if self.state == self.PLAYING:
            self.rtp_thread_stop_event.set()
            self.sendRtspRequest(self.PAUSE)
            
            # Reset flags for playback restart
            with self.queue_lock:
                self.display_started = False  # allow playback to restart
                self.frame_queue.clear()      # optionally clear old frames

                
    def playMovie(self):
        if self.state == self.READY:
            self.rtp_thread_stop_event.clear()
            self.playEvent.clear()  # reset event for new playback

            threading.Thread(target=self.listenRtp, daemon=True).start()
            self.sendRtspRequest(self.PLAY)

    def listenRtp(self):
        """Listen for RTP packets with fragmentation support and low-latency buffering."""
        print("RTP Listener started.")
        while not self.rtp_thread_stop_event.is_set():
            try:
                data = self.rtpSocket.recv(20480)
                if data:
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)
                    currFrameNbr = rtpPacket.seqNum()
                    payload = rtpPacket.getPayload()
                    
                    # Disable false packet loss reporting (fragmentation causes seq gaps)
                    if self.last_seq_num >= 0 and currFrameNbr < self.last_seq_num:
                        print("Out-of-order packet detected")
                    self.last_seq_num = currFrameNbr

                    # Try to extract fragmentation header
                    frag_header = FragmentationHeader()
                    if len(payload) >= FragmentationHeader.HEADER_SIZE:
                        if frag_header.decode(payload[:FragmentationHeader.HEADER_SIZE]):
                            # Fragmented payload
                            frame_payload = payload[FragmentationHeader.HEADER_SIZE:]
                            
                            # Try to reassemble
                            complete_frame = self.fragmentation_handler.add_fragment(
                                frag_header.fragment_id, 
                                frag_header, 
                                frame_payload
                            )
                            
                            if complete_frame:
                                # Frame is complete
                                self.frameNbr = frag_header.fragment_id
                                self.network_analytics.record_frame_received(
                                    frag_header.fragment_id, 
                                    len(complete_frame)
                                )
                                self.add_to_queue(complete_frame)
                        else:
                            # Not fragmented, use as-is
                            if currFrameNbr > self.frameNbr:
                                self.frameNbr = currFrameNbr
                                self.network_analytics.record_frame_received(currFrameNbr, len(payload))
                                self.add_to_queue(payload)
                    else:
                        # Small payload, not fragmented
                        if currFrameNbr > self.frameNbr:
                            self.frameNbr = currFrameNbr
                            self.network_analytics.record_frame_received(currFrameNbr, len(payload))
                            self.add_to_queue(payload)
                    
                    # Update statistics display
                    current_time = time.time()
                    if current_time - self.last_stats_update >= self.stats_update_interval:
                        self.update_stats_display()
                        self.last_stats_update = current_time
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.teardownAcked == 1:
                    print("RTP Listener stopping due to Teardown.")
                    self.rtpSocket.shutdown(socket.SHUT_RDWR)
                    self.rtpSocket.close()
                    break
                
                if self.rtp_thread_stop_event.is_set():
                    break

        print("RTP Listener stopped.")
    
    def add_to_queue(self, frame_data):
        """Add frame to low-latency queue (Client-Side Caching Logic)."""
        with self.queue_lock:
            # 1. Quản lý kích thước queue (FIFO)
            if len(self.frame_queue) >= self.max_queue_size:
                self.frame_queue.pop(0)  # Remove oldest
            self.frame_queue.append(frame_data)
            
            if (len(self.frame_queue) == self.max_queue_size) and (not self.display_started):
                print(f"Pre-buffer complete: starting playback with {self.max_queue_size} frames.")
                self.display_started = True
                # Bắt đầu vòng lặp hiển thị frame trên luồng chính (Main Thread)
                self.master.after(1, self.display_queued_frames) 
    
    def get_queued_frame(self):
        """Get next frame from queue (FIFO)."""
        with self.queue_lock:
            if self.frame_queue:
                return self.frame_queue.pop(0)
        return None

    def writeFrame(self, data):
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        with open(cachename, "wb") as file:
            file.write(data)
        return cachename

    def updateMovie(self, imageFile):
        """Update movie display with low-latency frame."""
        try:
            photo = ImageTk.PhotoImage(Image.open(imageFile))
            self.label.configure(image=photo, height=288)
            self.label.image = photo
        except Exception as e:
            print(f"Error updating movie: {e}")
    
    def display_queued_frames(self):
        """Display queued frames for low-latency playback."""
        frame_data = self.get_queued_frame()
        if frame_data:
            try:
                cache_name = self.writeFrame(frame_data)
                self.updateMovie(cache_name)
            except Exception as e:
                print(f"Error displaying frame: {e}")
        
        # Schedule next display
        if self.state == self.PLAYING and not self.playEvent.isSet():
            self.master.after(33, self.display_queued_frames) # ~30 FPS
    
    def update_stats_display(self):
        """Update network statistics display."""
        stats = self.network_analytics.get_statistics_summary()
        stats_text = (
            f"Frame Loss: {stats['frame_loss_rate']} | "
            f"Packet Loss: {stats['packet_loss_rate']} | "
            f"Latency: {stats['average_latency_ms']}ms | "
            f"Bitrate: {stats['current_bitrate_mbps']}Mbps | "
            f"Jitter: {stats['jitter_ms']}ms"
        )
        self.stats_label.config(text=stats_text)

    def connectToServer(self):
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
        except:
            tkinter.messagebox.showwarning(
                "Connection Failed",
                f"Cannot connect to {self.serverAddr}:{self.serverPort}",
            )

    def sendRtspRequest(self, requestCode):
        if requestCode == self.SETUP and self.state == self.INIT:
            threading.Thread(target=self.recvRtspReply).start()
            self.rtspSeq += 1
            # Add resolution header for HD mode
            resolution_header = "\nResolution: 1080p" if self.hd_mode else ""
            request = f"SETUP {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nTransport: RTP/UDP; client_port={self.rtpPort}{resolution_header}"
            self.requestSent = self.SETUP

        elif requestCode == self.PLAY and self.state == self.READY:
            self.rtspSeq += 1
            request = f"PLAY {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
            self.requestSent = self.PLAY

        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            self.rtspSeq += 1
            request = f"PAUSE {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
            self.requestSent = self.PAUSE

        elif requestCode == self.TEARDOWN and not self.state == self.INIT:
            self.rtspSeq += 1
            request = f"TEARDOWN {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
            self.requestSent = self.TEARDOWN
        else:
            return

        self.rtspSocket.send(request.encode())
        print("\nData sent:\n" + request)

    def recvRtspReply(self):
        while True:
            reply = self.rtspSocket.recv(1024)
            if reply:
                self.parseRtspReply(reply.decode("utf-8"))
            if self.requestSent == self.TEARDOWN:
                self.rtspSocket.shutdown(socket.SHUT_RDWR)
                self.rtspSocket.close()
                break

    def parseRtspReply(self, data):
        lines = data.split("\n")
        seqNum = int(lines[1].split(" ")[1])

        if seqNum == self.rtspSeq:
            session = int(lines[2].split(" ")[1])
            if self.sessionId == 0:
                self.sessionId = session
            if self.sessionId == session:
                if int(lines[0].split(" ")[1]) == 200:
                    if self.requestSent == self.SETUP:
                        self.state = self.READY
                        self.openRtpPort()
                    elif self.requestSent == self.PLAY:
                        self.state = self.PLAYING
                    elif self.requestSent == self.PAUSE:
                        self.state = self.READY
                    elif self.requestSent == self.TEARDOWN:
                        self.state = self.INIT
                        self.teardownAcked = 1

    def openRtpPort(self):
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtpSocket.settimeout(0.5)
        try:
            self.rtpSocket.bind(("", self.rtpPort))
        except:
            tkinter.messagebox.showwarning(
                "Unable to Bind", f"Unable to bind PORT={self.rtpPort}"
            )

    def handler(self):
        self.pauseMovie()
        if tkinter.messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else:
            self.playMovie()
