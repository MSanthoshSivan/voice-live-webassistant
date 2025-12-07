"""
Flask Web Application for Azure VoiceLive Assistant
Provides a web UI for visualizing voice conversations and function calls
"""
import os
import sys
import asyncio
import json
import datetime
import logging
import base64
import threading
import queue
from typing import Union, Optional, Dict, Any, List
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from concurrent.futures import ThreadPoolExecutor

# Audio processing imports
try:
    import pyaudio
except ImportError:
    print("This sample requires pyaudio. Install with: pip install pyaudio")
    sys.exit(1)

# Environment variable loading
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Note: python-dotenv not installed. Using existing environment variables.")

# Azure VoiceLive SDK imports
from azure.core.credentials import AzureKeyCredential
from utilities.web_voice_assistant import WebVoiceAssistant

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global state
assistant_instance = None
event_loop = None
loop_thread = None

# Flask routes
@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get configuration status."""
    api_key = os.environ.get("AZURE_VOICELIVE_API_KEY")
    return jsonify({
        'configured': bool(api_key),
        'endpoint': os.environ.get("AZURE_VOICELIVE_ENDPOINT")
    })


# SocketIO events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info("Client connected")
    emit('connected', {'message': 'Connected to server'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("Client disconnected")


@socketio.on('start_assistant')
def handle_start_assistant():
    """Start the voice assistant."""
    global assistant_instance, event_loop, loop_thread
    
    api_key = os.environ.get("AZURE_VOICELIVE_API_KEY")
    endpoint = os.environ.get("AZURE_VOICELIVE_ENDPOINT")
    model = os.environ.get("AZURE_VOICELIVE_MODEL", "gpt-4o-mini-transcribe")

    
    if not api_key or not endpoint:
        emit('error', {'message': 'No API key or endpoint configured. Set AZURE_VOICELIVE_API_KEY and AZURE_VOICELIVE_ENDPOINT environment variables.'})
        return
    
    # # Convert https to wss if needed and ensure proper path
    # if endpoint.startswith("https://"):
    #     endpoint = endpoint.replace("https://", "wss://")
    # if not endpoint.startswith("wss://"):
    #     endpoint = "wss://" + endpoint
    # if "/openai/realtime" not in endpoint:
    #     endpoint = endpoint.rstrip("/") + "/openai/realtime"
    
    # logger.info(f"Using endpoint: {endpoint}")
    # logger.info(f"Using model: {model}")
    
    if assistant_instance and assistant_instance.is_running:
        emit('error', {'message': 'Assistant is already running'})
        return
    
    try:
        credential = AzureKeyCredential(api_key)
        assistant_instance = WebVoiceAssistant(
            endpoint=endpoint,
            credential=credential,
            model=model,
            voice="en-US-AvaNeural",
            instructions="You are a helpful AI assistant with access to functions. "
                        "Use functions when appropriate to provide accurate information.",
            socketio_instance=socketio
        )
        
        # Run assistant in separate thread with its own event loop
        def run_assistant():
            global event_loop
            event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(event_loop)
            try:
                event_loop.run_until_complete(assistant_instance.run())
            except asyncio.CancelledError:
                logger.info("Assistant task cancelled")
            except Exception as e:
                logger.error(f"Assistant error: {e}")
                socketio.emit('error', {'message': str(e)})
            finally:
                # Clean up pending tasks
                try:
                    pending = asyncio.all_tasks(event_loop)
                    for task in pending:
                        task.cancel()
                    # Give tasks a chance to clean up
                    event_loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception as e:
                    logger.error(f"Error cleaning up tasks: {e}")
                finally:
                    event_loop.close()
                    logger.info("Event loop closed")
        
        loop_thread = threading.Thread(target=run_assistant, daemon=True)
        loop_thread.start()
        
        emit('assistant_started', {'message': 'Assistant starting...'})
        
    except Exception as e:
        logger.error(f"Error starting assistant: {e}")
        emit('error', {'message': str(e)})


@socketio.on('get_conversation_history')
def handle_get_history():
    """Get conversation history."""
    if assistant_instance:
        emit('conversation_history', {'history': assistant_instance.conversation_history})
    else:
        emit('conversation_history', {'history': []})


@socketio.on('stop_assistant')
def handle_stop_assistant():
    """Stop the voice assistant."""
    global assistant_instance, event_loop, loop_thread
    
    try:
        if assistant_instance and assistant_instance.is_running:
            logger.info("Stopping assistant...")
            
            # Schedule shutdown in the event loop
            if event_loop and not event_loop.is_closed():
                # Use asyncio to properly schedule the shutdown
                future = asyncio.run_coroutine_threadsafe(
                    assistant_instance.shutdown(), 
                    event_loop
                )
                # Wait for shutdown to complete (with timeout)
                try:
                    future.result(timeout=5.0)
                    logger.info("Assistant shutdown completed")
                except Exception as e:
                    logger.error(f"Error during shutdown: {e}")
            
            # Wait a moment for cleanup
            import time
            time.sleep(0.5)
            
            # Now stop the event loop
            if event_loop and not event_loop.is_closed():
                event_loop.call_soon_threadsafe(event_loop.stop)
            
            # Wait for thread to finish
            if loop_thread and loop_thread.is_alive():
                loop_thread.join(timeout=2.0)
            
            assistant_instance = None
            emit('assistant_stopped', {'message': 'Assistant stopped successfully'})
            logger.info("Assistant stopped")
        else:
            emit('error', {'message': 'Assistant is not running'})
    except Exception as e:
        logger.error(f"Error stopping assistant: {e}")
        emit('error', {'message': f'Error stopping assistant: {str(e)}'})


if __name__ == '__main__':
    # Check dependencies
    try:
        import numpy
    except ImportError:
        print("Installing numpy for audio visualization...")
        os.system("pip install numpy")
    
    print("=" * 70)
    print("🌐 Azure VoiceLive Web Assistant")
    print("=" * 70)
    print("Starting web server on http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("=" * 70)
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
