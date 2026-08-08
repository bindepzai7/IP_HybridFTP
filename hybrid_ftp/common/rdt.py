import socket
import logging
import time
from typing import Optional, Dict, Tuple

from .packet import Packet, FLAG_DATA, FLAG_ACK, FLAG_FIN


class ReliableUDP:
    MAX_PAYLOAD_SIZE = 1024
    MAX_PACKET_SIZE = 2048
    TIMEOUT = 1.0
    MAX_RETRIES = 20
    POLL_INTERVAL = 0.05
    INITIAL_SSTHRESH = 64.0
    RWND = 64

    def __init__(
        self,
        sock: socket.socket,
        target_addr: Optional[tuple[str, int]] = None,
    ):
        self.socket = sock
        self.target_addr = target_addr
        self.socket.settimeout(self.POLL_INTERVAL)
        self.cwnd = 1.0
        self.ssthresh = self.INITIAL_SSTHRESH
        self.rwnd = self.RWND

    def send(self, data: bytes) -> None:
        packets = self._create_packets(data)
        total_packets = len(packets)
        send_base = 0
        next_seq_num = 0
        window_buffer: Dict[int, dict] = {}
        cnt_loss = 0

        while send_base < total_packets:
            next_seq_num = self._fill_window(packets, window_buffer, send_base, next_seq_num, total_packets)
            
            ack_pkt = self._recv_valid_packet()
            if ack_pkt and ack_pkt.is_ack:
                send_base, newly_acked = self._process_ack(ack_pkt, window_buffer, send_base)
                if newly_acked:
                    self._update_cwnd_on_ack()
                
            self._check_timeouts(window_buffer, cnt_loss)

        self._send_fin(next_seq_num)
        print("LOSS PACKET: ", cnt_loss)

    def recv(self) -> bytes:
        rcv_base = 0
        rcv_buffer: Dict[int, bytes] = {}
        received_data = bytearray()

        while True:
            pkt = self._recv_valid_packet()
            
            if not pkt:
                continue

            if pkt.is_fin:
                self._send_ack(pkt.seq)
                break

            if pkt.is_data:
                rcv_base = self._process_data_packet(pkt, rcv_buffer, rcv_base, received_data)

        return bytes(received_data)

    def close(self) -> None:
        self.socket.close()

    def _create_packets(self, data: bytes) -> list[Packet]:
        packets = []
        for i in range(0, len(data), self.MAX_PAYLOAD_SIZE):
            chunk = data[i : i + self.MAX_PAYLOAD_SIZE]
            packets.append(Packet(seq=len(packets), flags=FLAG_DATA, payload=chunk))
        return packets

    def _fill_window(self, packets: list[Packet], window_buffer: dict, send_base: int, next_seq_num: int, total_packets: int) -> int:
        effective_window = int(min(self.cwnd, self.rwnd))
        while next_seq_num < send_base + effective_window and next_seq_num < total_packets:
            pkt = packets[next_seq_num]
            self.send_packet(pkt)
            window_buffer[next_seq_num] = {
                'packet': pkt,
                'time': time.time(),
                'acked': False,
                'retries': 0
            }
            next_seq_num += 1
        return next_seq_num

    def _process_ack(self, ack_pkt: Packet, window_buffer: dict, send_base: int) -> Tuple[int, bool]:
        ack_seq = ack_pkt.ack
        newly_acked = False
        effective_window = int(min(self.cwnd, self.rwnd))
        
        if send_base <= ack_seq < send_base + effective_window:
            if ack_seq in window_buffer and not window_buffer[ack_seq]['acked']:
                window_buffer[ack_seq]['acked'] = True
                newly_acked = True

            while send_base in window_buffer and window_buffer[send_base]['acked']:
                del window_buffer[send_base]
                send_base += 1
                
        return send_base, newly_acked

    def _update_cwnd_on_ack(self) -> None:
        if self.cwnd < self.ssthresh:
            self.cwnd += 1.0
        else:
            self.cwnd += 1.0 / int(self.cwnd)

    def _update_cwnd_on_timeout(self) -> None:
        self.ssthresh = max(int(self.cwnd) // 2, 1)
        self.cwnd = 1.0

    def _check_timeouts(self, window_buffer: dict, cnt_loss) -> None:
        current_time = time.time()
        timeout_occurred = False
        
        for seq, info in window_buffer.items():
            if not info['acked']:
                if current_time - info['time'] > self.TIMEOUT:
                    timeout_occurred = True
                    if info['retries'] >= self.MAX_RETRIES:
                        logging.debug(f"Max retries exceeded for packet {seq}")
                        raise ConnectionError(f"Max retries exceeded for packet {seq}")
                    
                    logging.debug(f"Timeout for packet {seq}. Retransmitting...")
                    cnt_loss+=1
                    self.send_packet(info['packet'])
                    info['time'] = current_time
                    info['retries'] += 1
                    
        if timeout_occurred:
            self._update_cwnd_on_timeout()

    def _process_data_packet(self, pkt: Packet, rcv_buffer: dict, rcv_base: int, received_data: bytearray) -> int:
        seq = pkt.seq
        
        if rcv_base <= seq < rcv_base + self.rwnd:
            self._send_ack(seq)
            if seq not in rcv_buffer:
                rcv_buffer[seq] = pkt.payload
            
            if seq == rcv_base:
                rcv_base = self._slide_recv_window(rcv_buffer, rcv_base, received_data)
                
        elif rcv_base - self.rwnd <= seq < rcv_base:
            self._send_ack(seq)
            
        return rcv_base

    def _slide_recv_window(self, rcv_buffer: dict, rcv_base: int, received_data: bytearray) -> int:
        while rcv_base in rcv_buffer:
            received_data.extend(rcv_buffer[rcv_base])
            del rcv_buffer[rcv_base]
            rcv_base += 1
        return rcv_base

    def _send_fin(self, seq_num: int) -> None:
        fin_packet = Packet(seq=seq_num, flags=FLAG_FIN)
        retries = 0
        
        while retries < self.MAX_RETRIES:
            self.send_packet(fin_packet)
            start_time = time.time()
            
            while time.time() - start_time < self.TIMEOUT:
                ack_pkt = self._recv_valid_packet()
                if ack_pkt and ack_pkt.is_ack and ack_pkt.ack == seq_num:
                    return
                    
            logging.debug("Timeout waiting for FIN ACK. Retransmitting...")
            retries += 1
            
        logging.debug("Max retries exceeded waiting for FIN ACK")
        raise ConnectionError("Max retries exceeded waiting for FIN ACK")

    def _send_ack(self, ack_num: int) -> None:
        ack_packet = Packet(ack=ack_num, flags=FLAG_ACK)
        self.send_packet(ack_packet)

    def _recv_valid_packet(self) -> Optional[Packet]:
        try:
            return self.recv_packet()
        except socket.timeout as e:
            logging.debug(f"Socket timeout during receive: {e}")
            return None
        except ValueError as e:
            logging.debug(f"Discarding corrupted packet: {e}")
            return None

    def send_packet(self, packet: Packet) -> None:
        if not self.target_addr:
            raise ValueError("Target address must be set before sending packets")
        self.socket.sendto(packet.to_bytes(), self.target_addr)

    def recv_packet(self) -> Packet:
        data, addr = self.socket.recvfrom(self.MAX_PACKET_SIZE)
        
        if not self.target_addr:
            self.target_addr = addr
            
        return Packet.from_bytes(data)