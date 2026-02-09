#!/usr/bin/env python3
"""
Audio Flow Debugging Tool
Monitors and displays audio-related logs in real-time with color coding
"""

import subprocess
import sys
import re
from datetime import datetime

# ANSI Color codes
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    CYAN = '\033[36m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    BLUE = '\033[94m'

def parse_log_line(line):
    """Parse and colorize log line based on content"""
    
    if "[AUDIO]" in line:
        if "✅" in line or "succeeded" in line or "successfully" in line:
            return f"{Colors.GREEN}{line}{Colors.RESET}"
        elif "❌" in line or "failed" in line or "error" in line:
            return f"{Colors.RED}{line}{Colors.RESET}"
        else:
            return f"{Colors.BLUE}{line}{Colors.RESET}"
    
    elif "[VOICE]" in line:
        if "✅" in line or "successfully" in line:
            return f"{Colors.GREEN}{line}{Colors.RESET}"
        elif "❌" in line or "Failed" in line:
            return f"{Colors.RED}{line}{Colors.RESET}"
        else:
            return f"{Colors.CYAN}{line}{Colors.RESET}"
    
    elif "[TTS]" in line:
        if "✅" in line or "succeeded" in line:
            return f"{Colors.GREEN}{line}{Colors.RESET}"
        elif "❌" in line or "failed" in line:
            return f"{Colors.RED}{line}{Colors.RESET}"
        else:
            return f"{Colors.MAGENTA}{line}{Colors.RESET}"
    
    elif "[AUTO-VOICE]" in line:
        if "✅" in line or "created" in line:
            return f"{Colors.GREEN}{line}{Colors.RESET}"
        elif "❌" in line or "Failed" in line:
            return f"{Colors.RED}{line}{Colors.RESET}"
        else:
            return f"{Colors.YELLOW}{line}{Colors.RESET}"
    
    elif "ERROR" in line or "error" in line:
        return f"{Colors.RED}{line}{Colors.RESET}"
    
    elif "WARNING" in line or "warning" in line:
        return f"{Colors.YELLOW}{line}{Colors.RESET}"
    
    return line

def main():
    print(f"\n{Colors.BOLD}🎙️  Audio Flow Debugging Tool{Colors.RESET}")
    print(f"{Colors.BOLD}================================{Colors.RESET}")
    print(f"\n{Colors.CYAN}Monitoring logs for audio-related events...{Colors.RESET}")
    print(f"{Colors.CYAN}Use Ctrl+C to stop{Colors.RESET}\n")
    
    # Start docker logs command
    cmd = [
        "docker", "logs", "-f", "jeevo-backend",
        "--tail", "50"
    ]
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Track state for summary
        events = {
            "audio_uploads": 0,
            "audio_successes": 0,
            "audio_failures": 0,
            "voice_responses": 0,
            "tts_attempts": 0,
            "tts_successes": 0,
        }
        
        for line in process.stdout:
            line = line.rstrip('\n')
            
            # Only print lines with audio-related tags
            if any(tag in line for tag in ["[AUDIO]", "[VOICE]", "[TTS]", "[AUTO-VOICE]"]):
                # Update event counters
                if "[AUDIO] Uploading" in line:
                    events["audio_uploads"] += 1
                elif "[AUDIO] ✅ Audio uploaded" in line:
                    events["audio_successes"] += 1
                elif "[AUDIO]" in line and ("failed" in line or "error" in line):
                    events["audio_failures"] += 1
                elif "[VOICE] ✅" in line:
                    events["voice_responses"] += 1
                elif "[TTS] Attempting" in line:
                    events["tts_attempts"] += 1
                elif "[TTS] ✅" in line:
                    events["tts_successes"] += 1
                
                # Print colored line with timestamp
                timestamp = datetime.now().strftime("%H:%M:%S")
                colored_line = parse_log_line(line)
                print(f"{Colors.BOLD}[{timestamp}]{Colors.RESET} {colored_line}")
        
    except KeyboardInterrupt:
        print(f"\n\n{Colors.BOLD}📊 Session Summary{Colors.RESET}")
        print(f"{Colors.BOLD}==================={Colors.RESET}")
        print(f"Audio Uploads:      {events['audio_uploads']}")
        print(f"Audio Successes:    {Colors.GREEN}{events['audio_successes']}{Colors.RESET}")
        print(f"Audio Failures:     {Colors.RED}{events['audio_failures']}{Colors.RESET}")
        print(f"Voice Responses:    {events['voice_responses']}")
        print(f"TTS Attempts:       {events['tts_attempts']}")
        print(f"TTS Successes:      {Colors.GREEN}{events['tts_successes']}{Colors.RESET}")
        
        if events['audio_uploads'] > 0:
            success_rate = (events['audio_successes'] / events['audio_uploads']) * 100
            print(f"\nSuccess Rate:       {Colors.GREEN if success_rate == 100 else Colors.YELLOW}{success_rate:.1f}%{Colors.RESET}")
        
        print(f"\n{Colors.CYAN}Exiting...{Colors.RESET}\n")
        sys.exit(0)
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
