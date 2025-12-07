import sys
import queue
import asyncio
import logging
import base64
import threading
from concurrent.futures import ThreadPoolExecutor

# Audio processing imports
try:
    import pyaudio
except ImportError:
    print("This sample requires pyaudio. Install with: pip install pyaudio")
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class AudioProcessor:
    """Handles real-time audio capture and playback for the voice assistant."""

    def __init__(self, connection, socketio_instance):
        self.connection = connection
        self.socketio = socketio_instance
        self.audio = pyaudio.PyAudio()

        # Audio configuration - PCM16, 24kHz, mono
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 24000
        self.chunk_size = 1024

        # Capture and playback state
        self.is_capturing = False
        self.is_playing = False
        self.input_stream = None
        self.output_stream = None

        # Audio queues and threading
        self.audio_queue = queue.Queue()
        self.audio_send_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.capture_thread = None
        self.playback_thread = None
        self.send_thread = None
        self.loop = None

        logger.info("AudioProcessor initialized")

    async def start_capture(self):
        """Start capturing audio from microphone."""
        if self.is_capturing:
            return

        self.loop = asyncio.get_event_loop()
        self.is_capturing = True

        try:
            self.input_stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=None,
            )
            self.input_stream.start_stream()

            # Start capture thread
            self.capture_thread = threading.Thread(target=self._capture_audio_thread)
            self.capture_thread.daemon = True
            self.capture_thread.start()

            # Start audio send thread
            self.send_thread = threading.Thread(target=self._send_audio_thread)
            self.send_thread.daemon = True
            self.send_thread.start()

            logger.info("Started audio capture")
            self.socketio.emit('audio_status', {'status': 'capturing', 'message': 'Microphone active'})

        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            self.is_capturing = False
            raise

    def _capture_audio_thread(self):
        """Audio capture thread - runs in background."""
        while self.is_capturing and self.input_stream:
            try:
                audio_data = self.input_stream.read(self.chunk_size, exception_on_overflow=False)
                if audio_data and self.is_capturing:
                    audio_base64 = base64.b64encode(audio_data).decode("utf-8")
                    self.audio_send_queue.put(audio_base64)
                    
                    # Send audio level to frontend for visualization
                    import numpy as np
                    audio_np = np.frombuffer(audio_data, dtype=np.int16)
                    level = float(np.abs(audio_np).mean()) / 32768.0
                    self.socketio.emit('audio_level', {'level': level, 'type': 'input'})
            except Exception as e:
                if self.is_capturing:
                    logger.error(f"Error in audio capture: {e}")
                break

    def _send_audio_thread(self):
        """Audio send thread - handles async operations from sync thread."""
        while self.is_capturing:
            try:
                audio_base64 = self.audio_send_queue.get(timeout=0.1)
                if audio_base64 and self.is_capturing and self.loop:
                    future = asyncio.run_coroutine_threadsafe(
                        self.connection.input_audio_buffer.append(audio=audio_base64), self.loop
                    )
            except queue.Empty:
                continue
            except Exception as e:
                if self.is_capturing:
                    logger.error(f"Error sending audio: {e}")
                break

    async def stop_capture(self):
        """Stop capturing audio."""
        if not self.is_capturing:
            return

        self.is_capturing = False

        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
            self.input_stream = None

        if self.capture_thread:
            self.capture_thread.join(timeout=1.0)
        if self.send_thread:
            self.send_thread.join(timeout=1.0)

        while not self.audio_send_queue.empty():
            try:
                self.audio_send_queue.get_nowait()
            except queue.Empty:
                break

        logger.info("Stopped audio capture")
        self.socketio.emit('audio_status', {'status': 'stopped', 'message': 'Microphone stopped'})

    async def start_playback(self):
        """Initialize audio playback system."""
        if self.is_playing:
            return

        self.is_playing = True

        try:
            self.output_stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                output=True,
                frames_per_buffer=self.chunk_size,
            )

            self.playback_thread = threading.Thread(target=self._playback_audio_thread)
            self.playback_thread.daemon = True
            self.playback_thread.start()

            logger.info("Audio playback ready")
            self.socketio.emit('audio_status', {'status': 'playing', 'message': 'Speaker ready'})

        except Exception as e:
            logger.error(f"Failed to initialize audio playback: {e}")
            self.is_playing = False
            raise

    def _playback_audio_thread(self):
        """Audio playback thread - runs in background."""
        while self.is_playing:
            try:
                audio_data = self.audio_queue.get(timeout=0.1)
                if audio_data and self.output_stream and self.is_playing:
                    self.output_stream.write(audio_data)
                    
                    # Send audio level to frontend
                    import numpy as np
                    audio_np = np.frombuffer(audio_data, dtype=np.int16)
                    level = float(np.abs(audio_np).mean()) / 32768.0
                    self.socketio.emit('audio_level', {'level': level, 'type': 'output'})
            except queue.Empty:
                continue
            except Exception as e:
                if self.is_playing:
                    logger.error(f"Error in audio playback: {e}")
                break

    async def queue_audio(self, audio_data: bytes):
        """Queue audio data for playback."""
        if self.is_playing:
            self.audio_queue.put(audio_data)

    async def stop_playback(self):
        """Stop audio playback and clear queue."""
        if not self.is_playing:
            return

        self.is_playing = False

        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
            self.output_stream = None

        if self.playback_thread:
            self.playback_thread.join(timeout=1.0)

        logger.info("Stopped audio playback")

    async def cleanup(self):
        """Clean up audio resources."""
        await self.stop_capture()
        await self.stop_playback()
        if self.audio:
            self.audio.terminate()
        self.executor.shutdown(wait=True)
        logger.info("Audio processor cleaned up")
