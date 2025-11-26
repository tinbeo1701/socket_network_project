from random import randint
import sys, traceback, threading, socket, time

from VideoStream import VideoStream
from HDVideoStream import HDVideoStream
from RtpPacket import RtpPacket
from FragmentationHandler import FragmentationHandler
from NetworkAnalytics import NetworkAnalytics


class ServerWorker:
    SETUP = "SETUP"
    PLAY = "PLAY"
    PAUSE = "PAUSE"
    TEARDOWN = "TEARDOWN"

    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    OK_200 = 0
    FILE_NOT_FOUND_404 = 1
    CON_ERR_500 = 2

    clientInfo = {}

    def __init__(self, clientInfo):
        self.clientInfo = clientInfo
        self.fragmentation_handler = FragmentationHandler()
        self.network_analytics = NetworkAnalytics()
        self.hd_mode = False  # Flag for HD mode
        self.use_adaptive_bitrate = True
        self.frame_seqnum = 0
        self.last_bitrate_adjustment = time.time()
        self.bytes_sent_since_last_check = 0

    def run(self):
        threading.Thread(target=self.recvRtspRequest).start()

    def recvRtspRequest(self):
        """Receive RTSP request from the client."""
        connSocket = self.clientInfo["rtspSocket"][0]
        while True:
            data = connSocket.recv(256)
            if data:
                print("Data received:\n" + data.decode("utf-8"))
                self.processRtspRequest(data.decode("utf-8"))

    def processRtspRequest(self, data):
        """Process RTSP request sent from the client."""
        # Get the request type
        request = data.split("\n")
        line1 = request[0].split(" ")
        requestType = line1[0]

        # Get the media file name
        filename = line1[1]

        # Get the RTSP sequence number
        seq = request[1].split(" ")

        # Check for HD mode request
        hd_mode = False
        for line in request:
            if "Resolution:" in line:
                res = line.split("Resolution:")[1].strip()
                if "1080" in res:
                    hd_mode = True
                    self.hd_mode = True
                elif "720" in res:
                    self.hd_mode = True
                break

        # Process SETUP request
        if requestType == self.SETUP:
            if self.state == self.INIT:
                # Update state
                print("processing SETUP\n")

                try:
                    # Try HD video stream first if HD mode requested
                    if self.hd_mode:
                        try:
                            self.clientInfo["videoStream"] = HDVideoStream(
                                filename, 
                                resolution=HDVideoStream.RESOLUTION_1080P,
                                fps=30
                            )
                            print(f"HD Video Stream loaded: 1080p@30fps")
                        except:
                            self.clientInfo["videoStream"] = VideoStream(filename)
                            self.hd_mode = False
                    else:
                        self.clientInfo["videoStream"] = VideoStream(filename)
                    
                    self.state = self.READY
                except IOError:
                    self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])

                # Generate a randomized RTSP session ID
                self.clientInfo["session"] = randint(100000, 999999)

                # Send RTSP reply
                self.replyRtsp(self.OK_200, seq[1])

                # Get the RTP/UDP port from the last line
                # self.clientInfo['rtpPort'] = request[2].split(' ')[3]
            # Find the Transport header line dynamically (instead of assuming it's line 3)
            for line in request:
                if "Transport:" in line:
                    try:
                        self.clientInfo["rtpPort"] = line.split("client_port=")[1]
                    except IndexError:
                        self.clientInfo["rtpPort"] = line.split(" ")[-1]
                    break

        # Process PLAY request
        elif requestType == self.PLAY:
            if self.state == self.READY:
                print("processing PLAY\n")
                self.state = self.PLAYING

                # Create a new socket for RTP/UDP
                self.clientInfo["rtpSocket"] = socket.socket(
                    socket.AF_INET, socket.SOCK_DGRAM
                )

                self.replyRtsp(self.OK_200, seq[1])

                # Create a new thread and start sending RTP packets
                self.clientInfo["event"] = threading.Event()
                self.clientInfo["worker"] = threading.Thread(target=self.sendRtp)
                self.clientInfo["worker"].start()

        # Process PAUSE request
        elif requestType == self.PAUSE:
            if self.state == self.PLAYING:
                print("processing PAUSE\n")
                self.state = self.READY

                self.clientInfo["event"].set()

                self.replyRtsp(self.OK_200, seq[1])

        # Process TEARDOWN request
        elif requestType == self.TEARDOWN:
            print("processing TEARDOWN\n")

            self.clientInfo["event"].set()

            self.replyRtsp(self.OK_200, seq[1])

            # Close the RTP socket
            self.clientInfo["rtpSocket"].close()

    def sendRtp(self):
        """Send RTP packets over UDP with fragmentation and adaptive bitrate control."""
        while True:
            self.clientInfo["event"].wait(0.05)

            # Stop sending if request is PAUSE or TEARDOWN
            if self.clientInfo["event"].isSet():
                break

            # Adaptive bitrate control (check every second)
            current_time = time.time()
            if current_time - self.last_bitrate_adjustment >= 1.0 and self.use_adaptive_bitrate:
                self.network_analytics.update_bandwidth_sample(
                    self.bytes_sent_since_last_check,
                    current_time - self.last_bitrate_adjustment
                )
                self.bytes_sent_since_last_check = 0
                self.last_bitrate_adjustment = current_time

            data = self.clientInfo["videoStream"].nextFrame()
            if data:
                frameNumber = self.clientInfo["videoStream"].frameNbr()
                self.frame_seqnum += 1
                
                # Record frame sent
                self.network_analytics.record_frame_sent(frameNumber, len(data))
                
                try:
                    address = self.clientInfo["rtspSocket"][1][0]
                    port = int(self.clientInfo["rtpPort"])
                    
                    # Handle fragmentation if frame exceeds MTU
                    if len(data) > self.fragmentation_handler.max_payload_size:
                        fragments = self.fragmentation_handler.fragment_frame(data, frameNumber)
                        for frag_header, frag_payload in fragments:
                            # Create RTP packet with fragmentation header prepended
                            rtp_payload = frag_header + frag_payload
                            rtp_packet = self.makeRtp(rtp_payload, self.frame_seqnum)
                            self.clientInfo["rtpSocket"].sendto(rtp_packet, (address, port))
                            self.bytes_sent_since_last_check += len(rtp_packet)
                            self.frame_seqnum += 1
                            # Small delay between fragments for better network handling
                            time.sleep(0.001)
                    else:
                        # Single packet, add minimal fragmentation header
                        rtp_packet = self.makeRtp(data, self.frame_seqnum)
                        self.clientInfo["rtpSocket"].sendto(rtp_packet, (address, port))
                        self.bytes_sent_since_last_check += len(rtp_packet)
                    
                except Exception as e:
                    print(f"Connection Error: {e}")
                    self.network_analytics.record_packet_loss(frameNumber)

    def makeRtp(self, payload, frameNbr):
        """RTP-packetize the video data."""
        version = 2
        padding = 0
        extension = 0
        cc = 0
        marker = 0
        pt = 26  # MJPEG type
        seqnum = frameNbr
        ssrc = 0

        rtpPacket = RtpPacket()

        rtpPacket.encode(
            version, padding, extension, cc, seqnum, marker, pt, ssrc, payload
        )

        return rtpPacket.getPacket()

    def replyRtsp(self, code, seq):
        """Send RTSP reply to the client."""
        if code == self.OK_200:
            # print("200 OK")
            hd_info = "\nHD-Mode: 1080p" if self.hd_mode else ""
            reply = (
                "RTSP/1.0 200 OK\nCSeq: "
                + seq
                + "\nSession: "
                + str(self.clientInfo["session"])
                + hd_info
            )
            connSocket = self.clientInfo["rtspSocket"][0]
            connSocket.send(reply.encode())

        # Error messages
        elif code == self.FILE_NOT_FOUND_404:
            print("404 NOT FOUND")
        elif code == self.CON_ERR_500:
            print("500 CONNECTION ERROR")
    
    def get_analytics_summary(self):
        """Get network analytics summary."""
        return self.network_analytics.get_statistics_summary()
