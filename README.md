OBS VHS Recording Automization Script
=====================================

This Python script automates the process of recording analog media, like VHS tapes, in OBS Studio. It intelligently pauses and resumes the recording by analyzing the video feed for specific visual cues, saving you from manually editing out unwanted sections later.


Features
--------
- Automatic End-of-Tape Detection: Pauses the recording when it detects the "REW" text on a blue/black screen, which typically appears at the end of a VHS tape.
- Black Screen Pausing: Automatically pauses the recording after a customizable duration of a black screen (e.g., blank tape sections).
- Automatic Resuming: Seamlessly resumes recording as soon as video content reappears after a black screen pause.
- Live Preview: Displays a small window showing the specific area of the screen being analyzed by the OCR.


How It Works
------------
The script connects to OBS Studio via the OBS WebSocket plugin. It continuously grabs screenshots from a specified video source, then performs two key checks:

1. Final Pause Condition: It crops a small, predefined area of the video frame and uses OCR to check for the word "REW". Simultaneously, it verifies if the background color matches a list of predefined colors (e.g., the classic blue screen). If both conditions are met for a set duration, it pauses the recording and prepares to exit.

2. Black Screen Logic: It calculates the average color of the entire frame. If the frame is black for a sustained period (e.g., 15 seconds), it pauses the recording. When the frame is no longer black, it immediately resumes.


Requirements
------------
Software:
- OBS Studio: The broadcasting software used for recording.
- OBS WebSocket Plugin: (Included by default in recent versions of OBS Studio).
- Python 3.8+

Python Libraries:
You can install all the necessary libraries by running: `pip install -r requirements.txt`
