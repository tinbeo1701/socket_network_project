"""
test_hd_streaming.py - Test script for HD video streaming system
Validates fragmentation, reassembly, and network analytics
"""
import sys
import unittest
from io import BytesIO
from FragmentationHandler import FragmentationHandler, FragmentationHeader
from NetworkAnalytics import NetworkAnalytics
from RtpPacket import RtpPacket
import time


class TestFragmentation(unittest.TestCase):
    """Test frame fragmentation and reassembly."""
    
    def setUp(self):
        self.handler = FragmentationHandler()
        self.test_frame = b'X' * 10000  # 10KB frame (exceeds MTU)
    
    def test_fragmentation_needed(self):
        """Test that large frames are fragmented."""
        fragments = self.handler.fragment_frame(self.test_frame, frame_id=1)
        # Should have multiple fragments
        self.assertGreater(len(fragments), 1)
        print(f"✓ Large frame fragmented into {len(fragments)} packets")
    
    def test_fragment_size_limit(self):
        """Test that fragments don't exceed max payload."""
        fragments = self.handler.fragment_frame(self.test_frame, frame_id=1)
        for header_bytes, payload in fragments:
            payload_size = len(payload)
            self.assertLessEqual(
                payload_size, 
                self.handler.max_payload_size,
                f"Payload {payload_size} exceeds max {self.handler.max_payload_size}"
            )
        print(f"✓ All fragments within size limits ({self.handler.max_payload_size} bytes)")
    
    def test_reassembly(self):
        """Test frame reassembly from fragments."""
        fragments = self.handler.fragment_frame(self.test_frame, frame_id=42)
        
        # Reassemble fragments
        reassembled = None
        for header_bytes, payload in fragments:
            header = FragmentationHeader()
            header.decode(header_bytes)
            reassembled = self.handler.add_fragment(header.fragment_id, header, payload)
            if reassembled:
                break
        
        # Last fragment should complete the frame
        self.assertIsNotNone(reassembled, "Frame not reassembled")
        self.assertEqual(len(reassembled), len(self.test_frame), "Reassembled size mismatch")
        self.assertEqual(reassembled, self.test_frame, "Reassembled content mismatch")
        print(f"✓ Frame successfully reassembled ({len(reassembled)} bytes)")
    
    def test_small_frame_no_fragmentation(self):
        """Test that small frames don't get fragmented."""
        small_frame = b'Small'
        fragments = self.handler.fragment_frame(small_frame, frame_id=2)
        self.assertEqual(len(fragments), 1, "Small frame should not be fragmented")
        print(f"✓ Small frame not fragmented (size: {len(small_frame)} bytes)")
    
    def test_out_of_order_reassembly(self):
        """Test reassembly with out-of-order fragments."""
        fragments = self.handler.fragment_frame(self.test_frame, frame_id=99)
        
        # Reverse order
        reversed_fragments = list(reversed(fragments))
        
        reassembled = None
        for header_bytes, payload in reversed_fragments:
            header = FragmentationHeader()
            header.decode(header_bytes)
            result = self.handler.add_fragment(header.fragment_id, header, payload)
            if result:
                reassembled = result
        
        self.assertEqual(reassembled, self.test_frame, "Out-of-order reassembly failed")
        print(f"✓ Out-of-order fragments reassembled correctly")


class TestNetworkAnalytics(unittest.TestCase):
    """Test network analytics and statistics."""
    
    def setUp(self):
        self.analytics = NetworkAnalytics()
    
    def test_frame_loss_tracking(self):
        """Test frame loss detection and tracking."""
        # Send 10 frames
        for i in range(10):
            self.analytics.record_frame_sent(i, 1024, 1)
        
        # Record 3 frames received
        self.analytics.record_frame_received(0, 1024)
        self.analytics.record_frame_received(5, 1024)
        self.analytics.record_frame_received(9, 1024)
        
        # Check loss rate
        loss_rate = self.analytics.get_frame_loss_rate()
        self.assertGreater(loss_rate, 0, "Should detect frame loss")
        print(f"✓ Frame loss rate: {loss_rate:.2f}%")
    
    def test_packet_loss_tracking(self):
        """Test packet loss tracking."""
        self.analytics.record_frame_sent(1, 1024, 5)  # 5 packets sent
        self.analytics.record_packet_loss(1, 2)  # 2 packets lost
        
        loss_rate = self.analytics.get_packet_loss_rate()
        expected_rate = (2 / 5) * 100
        self.assertAlmostEqual(loss_rate, expected_rate, places=1)
        print(f"✓ Packet loss rate: {loss_rate:.2f}%")
    
    def test_latency_calculation(self):
        """Test latency calculation."""
        self.analytics.record_frame_sent(1, 1024, 1)
        time.sleep(0.1)  # 100ms delay
        self.analytics.record_frame_received(1, 1024)
        
        latency = self.analytics.get_average_latency()
        self.assertGreater(latency, 50, f"Latency {latency}ms should be > 50ms")
        self.assertLess(latency, 200, f"Latency {latency}ms should be < 200ms")
        print(f"✓ Latency: {latency:.2f}ms")
    
    def test_adaptive_bitrate(self):
        """Test adaptive bitrate calculation."""
        # Simulate high packet loss
        for i in range(20):
            self.analytics.record_frame_sent(i, 1024, 1)
        
        self.analytics.record_packet_loss(0, 10)  # 50% loss
        
        adaptive_rate = self.analytics.get_adaptive_bitrate()
        self.assertLess(adaptive_rate, self.analytics.target_bitrate,
                       "High loss should reduce bitrate")
        print(f"✓ Adaptive bitrate: {adaptive_rate / 1_000_000:.2f} Mbps")
    
    def test_statistics_summary(self):
        """Test statistics summary generation."""
        for i in range(5):
            self.analytics.record_frame_sent(i, 2048, 1)
        
        for i in [0, 2, 4]:
            self.analytics.record_frame_received(i, 2048)
        
        summary = self.analytics.get_statistics_summary()
        
        self.assertIn('frame_loss_rate', summary)
        self.assertIn('average_latency_ms', summary)
        self.assertIn('current_bitrate_mbps', summary)
        print(f"✓ Statistics summary generated with {len(summary)} metrics")
        
        # Print summary
        for key, value in summary.items():
            print(f"  {key}: {value}")


class TestRtpPacket(unittest.TestCase):
    """Test RTP packet functionality."""
    
    def test_rtp_encode_decode(self):
        """Test RTP packet encoding and decoding."""
        packet = RtpPacket()
        payload = b"Test payload data"
        
        packet.encode(
            version=2, padding=0, extension=0, cc=0,
            seqnum=12345, marker=1, pt=26, ssrc=987654,
            payload=payload
        )
        
        encoded = packet.getPacket()
        
        # Decode
        packet2 = RtpPacket()
        packet2.decode(encoded)
        
        self.assertEqual(packet2.seqNum(), 12345)
        self.assertEqual(packet2.payloadType(), 26)
        self.assertEqual(packet2.marker(), 1)
        self.assertEqual(packet2.getPayload(), payload)
        print(f"✓ RTP packet encode/decode successful")
    
    def test_packet_size(self):
        """Test packet size calculation."""
        packet = RtpPacket()
        payload = b"X" * 5000
        
        packet.encode(2, 0, 0, 0, 1, 0, 26, 0, payload)
        
        total_size = packet.getPacketSize()
        self.assertEqual(total_size, 12 + len(payload))
        print(f"✓ Packet size calculated: {total_size} bytes")


class TestHDVideoStream(unittest.TestCase):
    """Test HD video stream functionality."""
    
    def test_resolution_presets(self):
        """Test resolution presets."""
        from HDVideoStream import HDVideoStream
        
        # Check 720p preset
        self.assertEqual(HDVideoStream.RESOLUTION_720P, (1280, 720))
        
        # Check 1080p preset
        self.assertEqual(HDVideoStream.RESOLUTION_1080P, (1920, 1080))
        
        print(f"✓ Resolution presets verified")


def run_performance_test():
    """Run performance test for fragmentation."""
    print("\n" + "="*60)
    print("PERFORMANCE TEST: Fragmentation Speed")
    print("="*60)
    
    handler = FragmentationHandler()
    
    # Test with various frame sizes
    frame_sizes = [1024, 10240, 102400, 1024000]  # 1KB to 1MB
    
    for size in frame_sizes:
        frame = b'X' * size
        
        start = time.time()
        fragments = handler.fragment_frame(frame, 1)
        elapsed = time.time() - start
        
        print(f"Frame size: {size/1024:>8.1f} KB → "
              f"Fragments: {len(fragments):>3} → "
              f"Time: {elapsed*1000:>6.2f} ms")


def run_simulation():
    """Run a realistic streaming simulation."""
    print("\n" + "="*60)
    print("SIMULATION: Streaming Scenario")
    print("="*60)
    
    handler = FragmentationHandler()
    analytics = NetworkAnalytics()
    
    # Simulate 30 seconds of streaming
    # Assuming 30 FPS, 1080p with ~50KB average frame size
    frame_count = 30 * 30
    
    print(f"Simulating {frame_count} frames at 30 FPS...")
    
    for frame_id in range(frame_count):
        # Realistic frame size (50-100 KB)
        frame_size = 50000 + (frame_id % 50000)
        frame_data = b'F' * frame_size
        
        # Fragment if needed
        fragments = handler.fragment_frame(frame_data, frame_id)
        
        # Record sent
        analytics.record_frame_sent(frame_id, frame_size, len(fragments))
        
        # Simulate network conditions (2% packet loss)
        import random
        if random.random() < 0.02:
            analytics.record_packet_loss(frame_id, 1)
        else:
            analytics.record_frame_received(frame_id, frame_size)
        
        # Simulate latency variation
        time.sleep(0.001 + random.random() * 0.005)
    
    # Print results
    summary = analytics.get_statistics_summary()
    print("\nSimulation Results:")
    print("-" * 60)
    for key, value in summary.items():
        print(f"  {key:.<40} {value:>15}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("HD VIDEO STREAMING - TEST SUITE")
    print("="*60 + "\n")
    
    # Run unit tests
    print("Running Unit Tests...\n")
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestFragmentation))
    suite.addTests(loader.loadTestsFromTestCase(TestNetworkAnalytics))
    suite.addTests(loader.loadTestsFromTestCase(TestRtpPacket))
    suite.addTests(loader.loadTestsFromTestCase(TestHDVideoStream))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Run additional tests
    if result.wasSuccessful():
        run_performance_test()
        run_simulation()
        
        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("✗ SOME TESTS FAILED")
        print("="*60)
        sys.exit(1)
