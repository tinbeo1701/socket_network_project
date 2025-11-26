"""
HDVideoStream.py - Support for HD video streaming (720p, 1080p)
Handles efficient frame reading with JPEG marker scanning
"""
import os
from datetime import datetime


class HDVideoStream:
    """Handles HD video streaming by scanning for JPEG markers (Standard MJPEG)."""
    
    # Resolution presets
    RESOLUTION_720P = (1280, 720)
    RESOLUTION_1080P = (1920, 1080)
    
    def __init__(self, filename, resolution=RESOLUTION_720P, fps=30):
        """
        Initialize HD video stream.
        
        Args:
            filename: Path to video file
            resolution: Tuple of (width, height) - default 720p
            fps: Frames per second
        """
        self.filename = filename
        self.resolution = resolution
        self.fps = fps
        self.frameNum = 0
        self.frame_interval = 1.0 / fps  # Time between frames
        self.total_bytes_read = 0
        self.start_time = datetime.now()
        self.buffer = bytearray()  # Buffer for processing
        
        try:
            self.file = open(filename, 'rb')
            # Get file size
            self.file.seek(0, 2)  # Seek to end
            self.file_size = self.file.tell()
            self.file.seek(0)  # Reset to start
        except IOError as e:
            raise IOError(f"Cannot open video file: {filename}") from e
    
    def nextFrame(self):
        """
        Get next frame by scanning for JPEG markers (FFD8...FFD9).
        
        Returns:
            Frame data (bytes) or None if EOF
        """
        # Read chunks until we find JPEG end marker (FFD9)
        while b'\xff\xd9' not in self.buffer:
            chunk = self.file.read(4096)
            if not chunk:
                # End of file
                if self.buffer:
                    end_idx = self.buffer.find(b'\xff\xd9')
                    if end_idx != -1:
                        break
                return None
            self.buffer += chunk
        
        # Find JPEG end marker position
        end_idx = self.buffer.find(b'\xff\xd9')
        
        # Extract frame data up to and including end marker
        frame_data = self.buffer[:end_idx + 2]
        
        # Remove processed frame from buffer, keep remainder for next frame
        self.buffer = self.buffer[end_idx + 2:]
        
        # Find JPEG start marker (FFD8) to filter out garbage data
        start_idx = frame_data.find(b'\xff\xd8')
        if start_idx != -1:
            final_data = frame_data[start_idx:]
            self.frameNum += 1
            self.total_bytes_read += len(final_data)
            return bytes(final_data)
        else:
            # If no valid start marker found, try to get next frame
            return self.nextFrame()
    
    def frameNbr(self):
        """Get current frame number."""
        return self.frameNum
    
    def getResolution(self):
        """Get resolution as (width, height)."""
        return self.resolution
    
    def getResolutionStr(self):
        """Get resolution as readable string (e.g., '1280x720')."""
        w, h = self.resolution
        return f"{w}x{h}"
    
    def getFps(self):
        """Get frames per second."""
        return self.fps
    
    def getTotalBytesRead(self):
        """Get total bytes read so far."""
        return self.total_bytes_read
    
    def getStreamDuration(self):
        """Get elapsed time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()
    
    def getProgress(self):
        """Get progress as percentage (0-100)."""
        if self.file_size == 0:
            return 0
        return (self.file.tell() / self.file_size) * 100
    
    def getCurrentBitrate(self):
        """Calculate current bitrate in Mbps."""
        elapsed = self.getStreamDuration()
        if elapsed == 0:
            return 0
        total_bits = self.total_bytes_read * 8
        return (total_bits / (elapsed * 1_000_000))
    
    def seek(self, frame_num):
        """
        Seek to specific frame number (approximate).
        
        Args:
            frame_num: Target frame number
        """
        if frame_num <= 0:
            self.file.seek(0)
            self.frameNum = 0
            self.total_bytes_read = 0
            self.buffer.clear()
    
    def close(self):
        """Close the video file."""
        if hasattr(self, 'file') and self.file:
            self.file.close()
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        self.close()
