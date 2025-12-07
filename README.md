# Azure VoiceLive Web Assistant

A Flask web application for visualizing real-time voice conversations with Azure VoiceLive AI, featuring function calling capabilities and live audio visualization.

## Features

- 🎤 **Real-time Voice Conversations**: Speak naturally with the AI assistant
- 📊 **Live Audio Visualization**: See input/output audio levels in real-time
- ⚙️ **Function Calling**: Visualize when the AI calls functions (time, weather)
- 💬 **Conversation History**: Track all interactions with timestamps
- 🎨 **Modern UI**: Clean, dark-themed interface with smooth animations
- 🔄 **Real-time Updates**: Socket.IO powered live updates

## Project Structure

```
voice-live/
├── app.py                      # Flask application with WebSocket support
├── scripts/
│   └── voice-live-fc.py       # Original voice assistant script
├── templates/
│   └── index.html             # Main web interface
├── static/
│   ├── css/
│   │   └── styles.css         # Application styling
│   └── js/
│       └── app.js             # Frontend logic and Socket.IO handlers
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Installation

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**
   
   Create a `.env` file in the project root:
   ```env
   AZURE_VOICELIVE_ENDPOINT=https://api.voicelive.com/
   AZURE_VOICELIVE_API_KEY=your_api_key_here
   AZURE_VOICELIVE_MODEL=voicelive-supported-model
   ```

   Or set them directly in PowerShell:
   ```powershell
   $env:AZURE_VOICELIVE_ENDPOINT="https://api.voicelive.com/"
   $env:AZURE_VOICELIVE_API_KEY="your_api_key_here"
   $env:AZURE_VOICELIVE_MODEL="voicelive-supported-model"

   ```

## Running the Application

1. **Start the Flask Server**
   ```bash
   python app.py
   ```

2. **Open Your Browser**
   
   Navigate to: `http://localhost:5000`

3. **Start the Assistant**
   
   Click the "Start Assistant" button in the web interface

4. **Start Speaking**
   
   Once you see "Ready for voice input", you can start talking!

## Usage Examples

Try asking the assistant:

- **Time queries**:
  - "What's the current time?"
  - "What time is it in UTC?"
  
- **Weather queries**:
  - "What's the weather in Seattle?"
  - "Tell me the weather in New York"
  - "How's the weather in Tokyo?"

## Web Interface Components

### 1. Conversation Panel (Left)
- Displays user and assistant messages
- Shows timestamps for each message
- Auto-scrolls to latest messages

### 2. Audio Visualization (Top Right)
- **Input Meter**: Shows microphone input levels
- **Output Meter**: Shows speaker output levels
- **Speaking Indicator**: Pulses when user is speaking

### 3. Function Calls Panel (Middle Right)
- Displays function calls in real-time
- Shows function arguments and results
- Tracks function call count

### 4. Available Tools Panel (Bottom Right)
- Lists all available functions
- Shows function descriptions

### 5. Status Bar (Bottom)
- Session ID
- Last activity timestamp
- Total message count

## Technical Details

### Backend (app.py)
- **Flask**: Web server framework
- **Flask-SocketIO**: Real-time bidirectional communication
- **AsyncIO**: Handles Azure VoiceLive async operations
- **Threading**: Separates event loops and audio processing
- **PyAudio**: Audio capture and playback

### Frontend
- **HTML/CSS**: Modern responsive design
- **Socket.IO**: Real-time event handling
- **Vanilla JavaScript**: No framework dependencies
- **CSS Animations**: Smooth visual feedback

### Real-time Events
The application emits various Socket.IO events:

- `status`: Connection and session status updates
- `user_transcript`: User speech transcription
- `response_delta`: Streaming assistant responses
- `function_call_started`: When a function is invoked
- `function_result`: Function execution results
- `audio_level`: Real-time audio visualization data
- `error`: Error notifications

## Function Calling

The assistant can call these functions:

### get_current_time
- **Description**: Get the current time
- **Parameters**: `timezone` (optional, e.g., "UTC", "local")
- **Returns**: Time, date, and timezone

### get_current_weather
- **Description**: Get current weather for a location
- **Parameters**: 
  - `location` (required, e.g., "Seattle, WA")
  - `unit` (optional, "celsius" or "fahrenheit")
- **Returns**: Simulated weather data

## Troubleshooting

### Microphone Not Working
- Check browser permissions for microphone access
- Ensure PyAudio is properly installed
- Verify audio device is available: Check error messages in console

### API Connection Issues
- Verify your API key is correct
- Check internet connection
- Ensure endpoint URL is correct

### Web Interface Not Loading
- Check if Flask server is running
- Try a different browser
- Clear browser cache

### No Audio Output
- Check speaker/headphone connections
- Verify PyAudio is capturing output devices
- Check browser audio settings

## Development

### Running in Development Mode
The app runs in debug mode by default:
```python
socketio.run(app, debug=True, host='0.0.0.0', port=5000)
```

### Customization
- **Modify UI**: Edit `templates/index.html` and `static/css/styles.css`
- **Add Functions**: Update `available_functions` in `WebVoiceAssistant` class
- **Change Voice**: Modify the `voice` parameter in `WebVoiceAssistant` initialization
- **Adjust Audio**: Modify `AudioProcessor` configuration

## Browser Compatibility

Tested on:
- ✅ Chrome/Edge (Recommended)
- ✅ Firefox
- ✅ Safari

## Requirements

- Python 3.8+
- Microphone
- Speakers/Headphones
- Modern web browser
- Azure VoiceLive API access

## Credits

Built with:
- Azure AI VoiceLive SDK
- Flask & Flask-SocketIO
- PyAudio
- Socket.IO

## License

This is a demonstration application. Check Azure VoiceLive licensing for production use.

## Support

For issues with:
- **Azure VoiceLive SDK**: Check Azure documentation
- **This application**: Review console logs and error messages
- **Audio issues**: Verify PyAudio installation and device availability

---

**Happy Conversing! 🎙️**
