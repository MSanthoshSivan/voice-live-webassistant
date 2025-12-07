import json
import asyncio
import logging
import datetime
from typing import Union, Optional, Dict, Any, List

from utilities.audio_processor import AudioProcessor

# Azure VoiceLive SDK imports
from azure.core.credentials import AzureKeyCredential
from azure.ai.voicelive.aio import connect
from azure.ai.voicelive.models import (
    RequestSession,
    ServerEventType,
    ServerVad,
    AudioEchoCancellation,
    AzureStandardVoice,
    Modality,
    InputAudioFormat,
    OutputAudioFormat,
    FunctionTool,
    FunctionCallOutputItem,
    ItemType,
    ToolChoiceLiteral,
    AudioInputTranscriptionOptions,
    ResponseFunctionCallItem,
    ServerEventConversationItemCreated,
    ServerEventResponseFunctionCallArgumentsDone,
    Tool,
)

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def _wait_for_event(conn, wanted_types: set, timeout_s: float = 10.0):
    """Wait until we receive any event whose type is in wanted_types."""
    async def _next():
        while True:
            evt = await conn.recv()
            if evt.type in wanted_types:
                return evt
    return await asyncio.wait_for(_next(), timeout=timeout_s)

class WebVoiceAssistant:
    """Web-enabled voice assistant with real-time UI updates."""

    def __init__(self, endpoint: str, credential: AzureKeyCredential, model: str, 
                 voice: str, instructions: str, socketio_instance):
        self.endpoint = endpoint
        self.credential = credential
        self.model = model
        self.voice = voice
        self.instructions = instructions
        self.socketio = socketio_instance
        self.session_id = None
        self.audio_processor = None
        self.session_ready = False
        self.is_running = False
        self.connection = None  # Store connection for proper cleanup
        
        self.current_user_input = ""
        self.current_response = ""
        self.response_id = None
        self.conversation_history = []
        
        # Available functions
        self.available_functions = {
            "get_current_time": self.get_current_time,
            "get_current_weather": self.get_current_weather,
        }

    async def run(self):
        """Run the voice assistant."""
        try:
            self.is_running = True
            logger.info(f"Connecting to VoiceLive API with model {self.model}")
            self.socketio.emit('status', {'status': 'connecting', 'message': 'Connecting to Azure VoiceLive...'})

            async with connect(
                endpoint=self.endpoint,
                credential=self.credential,
                model=self.model,
            ) as connection:
                self.connection = connection  # Store connection for cleanup
                self.audio_processor = AudioProcessor(connection, self.socketio)
                await self._setup_session(connection)
                await self.audio_processor.start_playback()
                
                self.socketio.emit('status', {'status': 'ready', 'message': 'Ready for voice input!'})
                logger.info("Voice assistant ready!")
                
                # Process events while running
                await self._process_events(connection)

        except asyncio.CancelledError:
            logger.info("Assistant run was cancelled")
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.socketio.emit('error', {'message': str(e)})
        finally:
            logger.info("Cleaning up assistant...")
            if self.audio_processor:
                try:
                    await self.audio_processor.cleanup()
                except Exception as e:
                    logger.error(f"Error during audio cleanup: {e}")
            self.connection = None
            self.is_running = False
            logger.info("Assistant cleanup complete")
    
    async def shutdown(self):
        """Gracefully shutdown the assistant."""
        logger.info("Shutting down assistant...")
        self.is_running = False
        
        # Stop audio processing first
        if self.audio_processor:
            try:
                await self.audio_processor.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up audio processor: {e}")
        
        # Close the connection if it exists
        if self.connection:
            try:
                await self.connection.close()
                logger.info("WebSocket connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
        
        logger.info("Shutdown complete")

    async def _setup_session(self, connection):
        """Configure the VoiceLive session."""
        logger.info("Setting up session...")
        
        voice_config = AzureStandardVoice(name=self.voice)
        turn_detection_config = ServerVad(threshold=0.5, prefix_padding_ms=300, silence_duration_ms=500)
        
        function_tools: List[Tool] = [
            FunctionTool(
                name="get_current_time",
                description="Get the current time",
                parameters={
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "description": "The timezone (e.g., 'UTC', 'local')",
                        }
                    },
                    "required": [],
                },
            ),
            FunctionTool(
                name="get_current_weather",
                description="Get the current weather in a location",
                parameters={
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City and state, e.g., 'San Francisco, CA'",
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "Temperature unit",
                        },
                    },
                    "required": ["location"],
                },
            ),
        ]
        
        session_config = RequestSession(
            modalities=[Modality.TEXT, Modality.AUDIO],
            instructions=self.instructions,
            voice=voice_config,
            input_audio_format=InputAudioFormat.PCM16,
            output_audio_format=OutputAudioFormat.PCM16,
            input_audio_echo_cancellation=AudioEchoCancellation(),
            turn_detection=turn_detection_config,
            tools=function_tools,
            tool_choice=ToolChoiceLiteral.AUTO,
            input_audio_transcription=AudioInputTranscriptionOptions(model="whisper-1"),
        )
        
        await connection.session.update(session=session_config)
        
        # Emit tool configuration to frontend
        tools_info = [{"name": tool.name, "description": tool.description} for tool in function_tools]
        self.socketio.emit('tools_configured', {'tools': tools_info})

    async def _process_events(self, connection):
        """Process events from VoiceLive."""
        try:
            async for event in connection:
                if not self.is_running:
                    logger.info("Stopping event processing - assistant is shutting down")
                    break
                try:
                    from datetime import datetime
                    with open('event_log.jsonl', 'a', encoding='utf-8') as f:
                        event_data = event
                        event_data['timestamp'] = datetime.now().isoformat()
                        # event_data = {
                        # 'event_data': str(event),
                        # 'event_type': str(event.type) if hasattr(event, 'type') else 'unknown',
                        # 'timestamp': datetime.now().isoformat(),
                        # }
                        f.write(json.dumps(event_data) + '\n')
                except Exception as e:
                    logger.error(f"Error logging event: {e}")
                await self._handle_event(event, connection)
        except asyncio.CancelledError:
            logger.info("Event processing cancelled")
        except Exception as e:
            if self.is_running:
                logger.error(f"Error processing events: {e}")
                raise

    async def _handle_event(self, event, connection):
        """Handle different event types."""
        ap = self.audio_processor
                
        if event.type == ServerEventType.SESSION_UPDATED:
            self.session_id = event.session.id
            logger.info(f"Session ready: {self.session_id}")
            self.session_ready = True
            await ap.start_capture()
            self.socketio.emit('session_ready', {'session_id': self.session_id})

        elif event.type == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED:
            logger.info("User started speaking")
            self.current_user_input = ""
            await ap.stop_playback()
            try:
                await connection.response.cancel()
            except:
                pass
            self.socketio.emit('user_speaking', {'speaking': True})

        elif event.type == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED:
            logger.info("User stopped speaking")
            await ap.start_playback()
            self.socketio.emit('user_speaking', {'speaking': False})

        elif event.type == ServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED:
            if hasattr(event, 'transcript') and event.transcript:
                self.current_user_input = event.transcript
                logger.info(f"User said: {self.current_user_input}")
                self.socketio.emit('user_transcript', {
                    'text': self.current_user_input,
                    'timestamp': datetime.datetime.now().isoformat()
                })

        elif event.type == ServerEventType.RESPONSE_CREATED:
            self.current_response = ""
            self.response_id = event.response.id if hasattr(event, 'response') else None
            self.socketio.emit('response_started', {'response_id': self.response_id})

        elif event.type == ServerEventType.RESPONSE_TEXT_DELTA:
            if hasattr(event, 'delta') and event.delta:
                self.current_response += event.delta
                self.socketio.emit('response_delta', {'delta': event.delta, 'full_text': self.current_response})

        elif event.type == ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DELTA:
            if hasattr(event, 'delta') and event.delta:
                self.socketio.emit('response_audio_transcript_delta', {'delta': event.delta})
        
        elif event.type == ServerEventType.RESPONSE_AUDIO_DELTA:
            await ap.queue_audio(event.delta)

        elif event.type == ServerEventType.RESPONSE_AUDIO_DONE:
            logger.info("Assistant finished speaking")
            self.socketio.emit('assistant_finished_speaking', {})

        elif event.type == ServerEventType.RESPONSE_DONE:
            logger.info("Response complete")
            if self.current_user_input and self.current_response:
                conversation_item = {
                    'user': self.current_user_input,
                    'assistant': self.current_response,
                    'timestamp': datetime.datetime.now().isoformat()
                }
                self.conversation_history.append(conversation_item)
                self.socketio.emit('conversation_item', conversation_item)

        elif event.type == ServerEventType.ERROR:
            logger.error(f"VoiceLive error: {event.error.message}")
            self.socketio.emit('error', {'message': event.error.message})

        elif event.type == ServerEventType.CONVERSATION_ITEM_CREATED:
            if event.item.type == ItemType.FUNCTION_CALL:
                await self._handle_function_call(event, connection)

    async def _handle_function_call(self, conversation_created_event, connection):
        """Handle function call events."""
        if not isinstance(conversation_created_event, ServerEventConversationItemCreated):
            return
        if not isinstance(conversation_created_event.item, ResponseFunctionCallItem):
            return

        function_call_item = conversation_created_event.item
        function_name = function_call_item.name
        call_id = function_call_item.call_id
        previous_item_id = function_call_item.id

        logger.info(f"Function call: {function_name} with call_id: {call_id}")
        self.socketio.emit('function_call_started', {
            'function': function_name,
            'call_id': call_id,
            'timestamp': datetime.datetime.now().isoformat()
        })

        try:
            function_done = await _wait_for_event(connection, {ServerEventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE})
            
            if not isinstance(function_done, ServerEventResponseFunctionCallArgumentsDone):
                return
            if function_done.call_id != call_id:
                return

            arguments = function_done.arguments
            logger.info(f"Function arguments: {arguments}")
            
            self.socketio.emit('function_arguments', {
                'function': function_name,
                'arguments': arguments,
                'call_id': call_id
            })

            # Wait for the initial response (with function call) to complete
            await _wait_for_event(connection, {ServerEventType.RESPONSE_DONE})

            if function_name in self.available_functions:
                # Execute the function
                result = self.available_functions[function_name](arguments)
                logger.info(f"Function {function_name} executed. Result: {result}")
                
                # Emit result to UI
                self.socketio.emit('function_result', {
                    'function': function_name,
                    'result': result,
                    'call_id': call_id,
                    'timestamp': datetime.datetime.now().isoformat()
                })

                # Send function result back to the assistant
                # Create function call output item with the result
                function_output = FunctionCallOutputItem(
                    call_id=call_id,
                    output=json.dumps(result)
                )
                
                # Add the function output to the conversation
                await connection.conversation.item.create(
                    previous_item_id=previous_item_id,
                    item=function_output
                )
                
                logger.info(f"Triggering assistant response with function result for {function_name}")
                
                # Trigger a new response from the assistant with the function result
                # The assistant will now generate a natural language response incorporating the function result
                await connection.response.create()
                
                # Don't wait here - let the normal event loop handle the response
                # The RESPONSE_CREATED, RESPONSE_TEXT_DELTA, RESPONSE_AUDIO_DELTA events will be processed
                # automatically by _handle_event()
                
            else:
                logger.error(f"Unknown function: {function_name}")
                self.socketio.emit('function_error', {
                    'function': function_name,
                    'error': f"Unknown function: {function_name}",
                    'call_id': call_id
                })

        except Exception as e:
            logger.error(f"Error executing function {function_name}: {e}")
            self.socketio.emit('function_error', {
                'function': function_name,
                'error': str(e)
            })

    def get_current_time(self, arguments=None):
        """Get the current time."""
        if isinstance(arguments, str):
            try:
                args = json.loads(arguments)
            except:
                args = {}
        else:
            args = arguments or {}

        timezone = args.get("timezone", "local")
        now = datetime.datetime.now()

        if timezone.lower() == "utc":
            now = datetime.datetime.now(datetime.timezone.utc)
            timezone_name = "UTC"
        else:
            timezone_name = "local"

        return {
            "time": now.strftime("%I:%M:%S %p"),
            "date": now.strftime("%A, %B %d, %Y"),
            "timezone": timezone_name
        }

    def get_current_weather(self, arguments):
        """Get weather for a location (simulated)."""
        if isinstance(arguments, str):
            try:
                args = json.loads(arguments)
            except:
                return {"error": "Invalid arguments"}
        else:
            args = arguments or {}

        location = args.get("location", "Unknown")
        unit = args.get("unit", "celsius")

        return {
            "location": location,
            "temperature": 22 if unit == "celsius" else 72,
            "unit": unit,
            "condition": "Partly Cloudy",
            "humidity": 65,
            "wind_speed": 10,
        }
