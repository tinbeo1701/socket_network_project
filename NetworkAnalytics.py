"""
NetworkAnalytics.py - Network performance monitoring and analysis
Tracks frame loss, bandwidth usage, latency, and other metrics
"""
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Tuple


class FrameStatistics:
    """Statistics for a single frame."""
    
    def __init__(self, frame_id: int, frame_size: int):
        self.frame_id = frame_id
        self.frame_size = frame_size
        self.sent_time = None
        self.received_time = None
        self.fragment_count = 0
        self.fragments_received = 0
        self.lost_fragments = 0
        self.is_complete = False
        self.latency_ms = None
    
    def calculate_latency(self):
        """Calculate latency if both send and receive times are available."""
        if self.sent_time and self.received_time:
            self.latency_ms = (self.received_time - self.sent_time) * 1000
            return self.latency_ms
        return None


class NetworkAnalytics:
    """Comprehensive network analytics for video streaming."""
    
    def __init__(self, window_size: int = 300):
        """
        Initialize network analytics.
        
        Args:
            window_size: Number of frames to keep in statistics window
        """
        self.window_size = window_size
        self.frame_stats = deque(maxlen=window_size)
        self.start_time = time.time()
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        self.total_packets_sent = 0
        self.total_packets_received = 0
        self.total_packets_lost = 0
        
        # Performance metrics
        self.frame_loss_count = 0
        self.fragment_loss_count = 0
        self.timestamps = deque(maxlen=window_size)
        self.bandwidth_samples = deque(maxlen=100)
        
        # Adaptive bitrate control
        self.current_bitrate = 0
        self.target_bitrate = 5_000_000  # 5 Mbps default
        self.min_bitrate = 500_000  # 500 Kbps
        self.max_bitrate = 25_000_000  # 25 Mbps
    
    def record_frame_sent(self, frame_id: int, frame_size: int, fragment_count: int = 1):
        """
        Record that a frame has been sent.
        
        Args:
            frame_id: Frame identifier
            frame_size: Size of frame in bytes
            fragment_count: Number of fragments
        """
        stats = FrameStatistics(frame_id, frame_size)
        stats.sent_time = time.time()
        stats.fragment_count = fragment_count
        self.frame_stats.append(stats)
        
        self.total_bytes_sent += frame_size
        self.total_packets_sent += fragment_count
        self.timestamps.append(stats.sent_time)
    
    def record_frame_received(self, frame_id: int, frame_size: int):
        """
        Record that a frame has been received.
        Updated to work for Client-side analytics (Receiver mode).
        
        Args:
            frame_id: Frame identifier
            frame_size: Size of frame in bytes
        """
        self.total_bytes_received += frame_size
        self.total_packets_received += 1
        current_time = time.time()
        
        # Tìm xem frame này có thông tin gửi (Server side) hay không
        found = False
        for stats in self.frame_stats:
            if stats.frame_id == frame_id:
                stats.received_time = current_time
                stats.is_complete = True
                stats.calculate_latency()
                found = True
                break
        
        # --- PHẦN THÊM MỚI QUAN TRỌNG CHO CLIENT ---
        # Nếu không tìm thấy (tức là đang ở Client), tự tạo thống kê mới
        if not found:
            stats = FrameStatistics(frame_id, frame_size)
            stats.received_time = current_time
            stats.is_complete = True
            # Ở Client, ta tạm thời không biết sent_time chính xác từ Server
            # nên Latency sẽ khó tính chính xác, nhưng Bitrate sẽ tính được.
            
            self.frame_stats.append(stats)
            self.timestamps.append(current_time)  # Lưu mốc thời gian nhận để tính Bitrate
    
    def record_packet_loss(self, frame_id: int, packet_count: int = 1):
        """
        Record packet loss.
        
        Args:
            frame_id: Frame identifier
            packet_count: Number of lost packets
        """
        self.total_packets_lost += packet_count
        self.fragment_loss_count += packet_count
        
        # Find matching frame
        for stats in self.frame_stats:
            if stats.frame_id == frame_id:
                stats.lost_fragments += packet_count
                break
    
    def record_frame_loss(self, frame_id: int):
        """Record that an entire frame was lost."""
        self.frame_loss_count += 1
        self.total_packets_lost += 1
    
    def get_frame_loss_rate(self) -> float:
        """
        Get frame loss rate as percentage.
        
        Returns:
            Frame loss percentage (0-100)
        """
        total_frames = len(self.frame_stats)
        if total_frames == 0:
            return 0.0
        
        lost = sum(1 for s in self.frame_stats if not s.is_complete)
        return (lost / total_frames) * 100
    
    def get_packet_loss_rate(self) -> float:
        """
        Get packet loss rate as percentage.
        
        Returns:
            Packet loss percentage (0-100)
        """
        total = self.total_packets_sent
        if total == 0:
            return 0.0
        
        return (self.total_packets_lost / total) * 100
    
    def get_average_latency(self) -> float:
        """
        Get average latency in milliseconds.
        
        Returns:
            Average latency (ms)
        """
        latencies = [s.latency_ms for s in self.frame_stats if s.latency_ms]
        if not latencies:
            return 0.0
        return sum(latencies) / len(latencies)
    
    def get_max_latency(self) -> float:
        """Get maximum latency in milliseconds."""
        latencies = [s.latency_ms for s in self.frame_stats if s.latency_ms]
        return max(latencies) if latencies else 0.0
    
    def get_current_bitrate(self) -> float:
        """
        Get current bitrate in Mbps based on recent data.
        
        Returns:
            Bitrate in Mbps
        """
        if len(self.timestamps) < 2:
            return 0.0
        
        time_delta = self.timestamps[-1] - self.timestamps[0]
        if time_delta == 0:
            return 0.0
        
        bytes_sent = sum(s.frame_size for s in list(self.frame_stats)[-self.window_size:])
        bits = bytes_sent * 8
        mbps = (bits / time_delta) / 1_000_000
        return mbps
    
    def get_average_bitrate(self) -> float:
        """
        Get average bitrate since start in Mbps.
        
        Returns:
            Average bitrate in Mbps
        """
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0.0
        
        bits = self.total_bytes_sent * 8
        mbps = (bits / elapsed) / 1_000_000
        return mbps
    
    def update_bandwidth_sample(self, bytes_transferred: int, time_delta: float):
        """
        Update bandwidth samples for adaptive control.
        
        Args:
            bytes_transferred: Bytes sent in time window
            time_delta: Time window in seconds
        """
        if time_delta > 0:
            mbps = (bytes_transferred * 8) / (time_delta * 1_000_000)
            self.bandwidth_samples.append(mbps)
    
    def get_adaptive_bitrate(self) -> int:
        """
        Calculate adaptive bitrate based on current conditions.
        
        Returns:
            Recommended bitrate in bps
        """
        packet_loss = self.get_packet_loss_rate()
        
        if packet_loss > 10:
            # High loss - reduce bitrate significantly
            self.current_bitrate = max(self.min_bitrate, self.current_bitrate * 0.7)
        elif packet_loss > 5:
            # Moderate loss - reduce bitrate moderately
            self.current_bitrate = max(self.min_bitrate, self.current_bitrate * 0.85)
        elif packet_loss < 1:
            # Low loss - increase bitrate
            self.current_bitrate = min(self.max_bitrate, self.current_bitrate * 1.1)
        
        if self.current_bitrate == 0:
            self.current_bitrate = self.target_bitrate
        
        return int(self.current_bitrate)
    
    def get_jitter(self) -> float:
        """
        Calculate jitter (latency variation) in milliseconds.
        
        Returns:
            Jitter in milliseconds
        """
        latencies = [s.latency_ms for s in self.frame_stats if s.latency_ms]
        if len(latencies) < 2:
            return 0.0
        
        avg_latency = sum(latencies) / len(latencies)
        variance = sum((l - avg_latency) ** 2 for l in latencies) / len(latencies)
        return variance ** 0.5  # Standard deviation
    
    def get_statistics_summary(self) -> Dict:
        """
        Get comprehensive statistics summary.
        
        Returns:
            Dictionary with all metrics
        """
        elapsed = time.time() - self.start_time
        
        return {
            'elapsed_seconds': elapsed,
            'frames_sent': self.total_packets_sent,
            'frames_received': self.total_packets_received,
            'frame_loss_count': self.frame_loss_count,
            'frame_loss_rate': f"{self.get_frame_loss_rate():.2f}%",
            'packet_loss_rate': f"{self.get_packet_loss_rate():.2f}%",
            'total_bytes_sent': self.total_bytes_sent,
            'total_bytes_received': self.total_bytes_received,
            'current_bitrate_mbps': f"{self.get_current_bitrate():.2f}",
            'average_bitrate_mbps': f"{self.get_average_bitrate():.2f}",
            'average_latency_ms': f"{self.get_average_latency():.2f}",
            'max_latency_ms': f"{self.get_max_latency():.2f}",
            'jitter_ms': f"{self.get_jitter():.2f}",
            'recommended_bitrate_mbps': f"{self.get_adaptive_bitrate() / 1_000_000:.2f}",
        }
    
    def reset(self):
        """Reset all statistics."""
        self.frame_stats.clear()
        self.timestamps.clear()
        self.bandwidth_samples.clear()
        self.start_time = time.time()
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        self.total_packets_sent = 0
        self.total_packets_received = 0
        self.total_packets_lost = 0
        self.frame_loss_count = 0
        self.fragment_loss_count = 0
        self.current_bitrate = 0
