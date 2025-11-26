"""
FragmentationHandler.py - Handle frame fragmentation and reassembly
For frames exceeding MTU (1500 bytes), split into multiple RTP packets
"""
import struct
from typing import Optional, List, Tuple


class FragmentationHeader:
    """Header for fragmented frame data."""
    
    # Fragment header format:
    # 1 byte: flags (bit 0: more_fragments, bit 1-7: reserved)
    # 1 byte: fragment_id (unique ID for this frame's fragments)
    # 4 bytes: fragment_offset (byte offset within the frame)
    # 4 bytes: frame_size (total size of original frame)
    
    HEADER_SIZE = 10  # bytes
    FLAG_MORE_FRAGMENTS = 0x01
    FLAG_LAST_FRAGMENT = 0x00
    
    def __init__(self):
        self.more_fragments = False
        self.fragment_id = 0
        self.fragment_offset = 0
        self.frame_size = 0
    
    def encode(self) -> bytes:
        """Encode header to bytes."""
        flags = self.FLAG_MORE_FRAGMENTS if self.more_fragments else self.FLAG_LAST_FRAGMENT
        return struct.pack(
            '!BBI I',
            flags,
            self.fragment_id,
            self.fragment_offset,
            self.frame_size
        )
    
    def decode(self, data: bytes) -> bool:
        """
        Decode header from bytes.
        
        Args:
            data: Bytes to decode (must be at least HEADER_SIZE)
        
        Returns:
            True if decoded successfully
        """
        if len(data) < self.HEADER_SIZE:
            return False
        
        flags, frag_id, offset, size = struct.unpack('!BBI I', data[:self.HEADER_SIZE])
        self.more_fragments = (flags & self.FLAG_MORE_FRAGMENTS) != 0
        self.fragment_id = frag_id
        self.fragment_offset = offset
        self.frame_size = size
        return True


class FragmentationHandler:
    """Handles frame fragmentation and reassembly."""
    
    # Standard Ethernet MTU is 1500 bytes
    # RTP header is 12 bytes, fragmentation header is 10 bytes
    # So maximum payload is 1500 - 12 - 10 = 1478 bytes
    STANDARD_MTU = 1500
    RTP_HEADER_SIZE = 12
    MAX_PAYLOAD_SIZE = STANDARD_MTU - RTP_HEADER_SIZE - FragmentationHeader.HEADER_SIZE
    
    def __init__(self, mtu: int = STANDARD_MTU):
        """
        Initialize fragmentation handler.
        
        Args:
            mtu: Maximum transmission unit in bytes
        """
        self.mtu = mtu
        self.max_payload_size = mtu - self.RTP_HEADER_SIZE - FragmentationHeader.HEADER_SIZE
        self.fragment_counter = 0
        self.reassembly_buffer = {}  # frame_id -> (data_parts, expected_size)
    
    def fragment_frame(self, frame_data: bytes, frame_id: int) -> List[Tuple[bytes, bytes]]:
        """
        Fragment a frame into multiple packets.
        
        Args:
            frame_data: Original frame data
            frame_id: Unique identifier for this frame
        
        Returns:
            List of tuples (fragmentation_header, payload)
        """
        if len(frame_data) <= self.max_payload_size:
            # No fragmentation needed
            header = FragmentationHeader()
            header.more_fragments = False
            header.fragment_id = frame_id % 256
            header.fragment_offset = 0
            header.frame_size = len(frame_data)
            return [(header.encode(), frame_data)]
        
        # Fragmentation needed
        fragments = []
        offset = 0
        fragment_count = 0
        
        while offset < len(frame_data):
            chunk_size = min(self.max_payload_size, len(frame_data) - offset)
            chunk = frame_data[offset:offset + chunk_size]
            
            header = FragmentationHeader()
            header.fragment_id = frame_id % 256
            header.fragment_offset = offset
            header.frame_size = len(frame_data)
            header.more_fragments = (offset + chunk_size) < len(frame_data)
            
            fragments.append((header.encode(), chunk))
            
            offset += chunk_size
            fragment_count += 1
        
        return fragments
    
    def add_fragment(self, frame_id: int, fragment_header: FragmentationHeader, payload: bytes) -> Optional[bytes]:
        """
        Add a fragment to reassembly buffer.
        
        Args:
            frame_id: Frame identifier
            fragment_header: Fragmentation header
            payload: Fragment payload
        
        Returns:
            Complete frame data if all fragments received, None otherwise
        """
        if frame_id not in self.reassembly_buffer:
            self.reassembly_buffer[frame_id] = {
                'parts': {},
                'size': fragment_header.frame_size,
                'complete': False,
                'has_last_fragment': False
            }
        
        buffer_entry = self.reassembly_buffer[frame_id]
        
        # Store fragment
        buffer_entry['parts'][fragment_header.fragment_offset] = payload
        
        # Mark if this is the last fragment
        if not fragment_header.more_fragments:
            buffer_entry['has_last_fragment'] = True
        
        # Check if complete - only if we have the last fragment
        if buffer_entry['has_last_fragment']:
            total_data = b''
            for offset in sorted(buffer_entry['parts'].keys()):
                total_data += buffer_entry['parts'][offset]
            
            if len(total_data) >= buffer_entry['size']:
                # Frame is complete
                buffer_entry['complete'] = True
                del self.reassembly_buffer[frame_id]
                return total_data[:buffer_entry['size']]  # Trim to exact size
        
        return None
    
    def get_stats(self) -> dict:
        """Get fragmentation statistics."""
        return {
            'mtu': self.mtu,
            'max_payload_size': self.max_payload_size,
            'pending_frames': len(self.reassembly_buffer)
        }
    
    def clear_incomplete(self, timeout_frames: int = 1000):
        """
        Clear incomplete frames from buffer (for cleanup).
        
        Args:
            timeout_frames: Remove frames older than this many frame numbers
        """
        to_remove = []
        for frame_id, buffer_entry in self.reassembly_buffer.items():
            if not buffer_entry['complete']:
                to_remove.append(frame_id)
        
        for frame_id in to_remove:
            del self.reassembly_buffer[frame_id]
