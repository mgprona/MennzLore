#!/usr/bin/env python3
"""
MennzLore YouTube & STT Acquisition Engine (Phase 1 Extension)
==============================================================
Pulls transcripts/subtitles from a YouTube Playlist. If subtitles are missing,
downloads the audio track, compresses it, and calls OpenRouter's Whisper API.
"""
import os
import sys
import json
import base64
import re
import subprocess
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

# OpenRouter STT Endpoint
OPENROUTER_STT_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
DEFAULT_MODEL = "openai/whisper-large-v3-turbo"

def run_cmd(cmd):
    """Run a shell command and return stdout."""
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    return res.returncode, res.stdout, res.stderr

def get_playlist_metadata(playlist_url):
    """Scan playlist using yt-dlp flat-playlist mode and return entries."""
    print(f"Scanning playlist metadata for: {playlist_url} ...")
    # Call yt-dlp to get flat JSON list of playlist entries
    cmd = f'yt-dlp --flat-playlist --dump-single-json "{playlist_url}"'
    code, out, err = run_cmd(cmd)
    if code != 0:
        raise Exception(f"yt-dlp failed to read playlist metadata: {err}")
    
    try:
        data = json.loads(out)
        playlist_title = data.get("title", "Unknown Playlist")
        entries = data.get("entries", [])
        if not entries and data.get("id"):
            entries = [data]
        return playlist_title, entries
    except Exception as e:
        raise Exception(f"Failed to parse playlist JSON: {e}")

def check_subtitles_availability(video_id):
    """Check if Thai (th) or English (en) transcripts are available on YouTube."""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # Try to find Thai or English manual/auto transcripts
        languages = ['th', 'en']
        for lang in languages:
            try:
                transcript = transcript_list.find_transcript([lang])
                is_auto = transcript.is_generated
                lang_code = transcript.language_code
                return {
                    "available": True,
                    "lang": lang_code,
                    "type": "auto" if is_auto else "manual",
                    "transcript_obj": transcript
                }
            except NoTranscriptFound:
                continue
    except Exception:
        pass
    
    return {
        "available": False,
        "lang": None,
        "type": None,
        "transcript_obj": None
    }

def download_and_clean_subtitles(video_id, transcript_meta):
    """Download existing subtitles and merge timestamps into a clean text block."""
    try:
        t_obj = transcript_meta.get("transcript_obj")
        if t_obj:
            data = t_obj.fetch()
        else:
            data = YouTubeTranscriptApi.get_transcript(video_id, languages=['th', 'en'])
            
        # Merge subtitle rows
        lines = []
        for entry in data:
            text = entry.get("text", "").strip()
            if text:
                # Remove common subtitle music tokens like [Music] or (Laughter)
                text = re.sub(r'\[.*?\]|\(.*?\)', '', text).strip()
                if text:
                    lines.append(text)
        
        # Clean formatting
        full_text = " ".join(lines)
        # Add a newline every 3-4 sentences to make it readable chapters
        full_text = re.sub(r'(\.|\!|\?|ค่ะ|ครับ|นะะ|นะครับ|นะคะ)\s+', r'\1\n\n', full_text)
        return full_text
    except Exception as e:
        raise Exception(f"Failed to download/clean subtitles: {e}")

def download_and_compress_audio(video_url, output_mp3_path):
    """Download low bitrate mono MP3 of the video using yt-dlp."""
    print(f"Downloading and compressing audio for: {video_url} ...")
    # yt-dlp args: extract audio, convert to mp3, set quality to 32k mono
    cmd = f'yt-dlp -x --audio-format mp3 --audio-quality 32k -o "{output_mp3_path.replace(".mp3", "")}" "{video_url}"'
    code, out, err = run_cmd(cmd)
    
    # yt-dlp might append .mp3 automatically or keep the format.
    # Let's verify if the file exists at output_mp3_path
    if not os.path.exists(output_mp3_path):
        # yt-dlp sometimes appends format suffix or names it based on temp patterns.
        # Let's check if the file got saved with double suffix like .mp3.mp3 or similar
        potential_path = output_mp3_path + ".mp3"
        if os.path.exists(potential_path):
            os.rename(potential_path, output_mp3_path)
            
    if code != 0 or not os.path.exists(output_mp3_path):
        raise Exception(f"yt-dlp audio download failed: {err}\nStdout: {out}")
        
    size_mb = os.path.getsize(output_mp3_path) / (1024 * 1024)
    print(f"  [OK] Saved compressed audio file: {size_mb:.2f} MB")
    return output_mp3_path

def transcribe_audio_openrouter(api_key, mp3_path, model_id=DEFAULT_MODEL):
    """Encode audio to base64 and send to OpenRouter transcription API."""
    print(f"Transcribing audio via OpenRouter ({model_id})...")
    if not os.path.exists(mp3_path):
        raise FileNotFoundError(f"Audio file not found: {mp3_path}")
        
    with open(mp3_path, "rb") as f:
        audio_data = base64.b64encode(f.read()).decode("utf-8")
        
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_id,
        "input_audio": {
            "data": audio_data,
            "format": "mp3"
        }
    }
    
    response = requests.post(OPENROUTER_STT_URL, headers=headers, json=payload, timeout=180)
    if response.status_code != 200:
        raise Exception(f"OpenRouter STT API Error {response.status_code}: {response.text}")
        
    res_json = response.json()
    transcription = res_json.get("text", "")
    if not transcription:
        # Fallback if text isn't top-level (depending on OpenRouter payload mapping)
        choices = res_json.get("choices", [])
        if choices:
            transcription = choices[0].get("text", choices[0].get("message", {}).get("content", ""))
            
    if not transcription:
        raise Exception(f"No transcription text returned in API response: {json.dumps(res_json)}")
        
    return transcription

def analyze_playlist_transcripts(playlist_url):
    """Scan the playlist and determine subtitle/STT status of each video."""
    title, entries = get_playlist_metadata(playlist_url)
    
    analysis_results = []
    total_stt_sec = 0
    
    print("\nAnalyzing playlist entries for subtitle availability...")
    for idx, entry in enumerate(entries):
        video_id = entry.get("id")
        video_title = entry.get("title", f"Video {idx+1}")
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Duration check
        duration = entry.get("duration", 0) or 0
        
        sub_meta = check_subtitles_availability(video_id)
        
        status = {
            "index": idx + 1,
            "id": video_id,
            "title": video_title,
            "url": video_url,
            "duration_sec": duration,
            "duration_str": f"{int(duration // 60):02d}:{int(duration % 60):02d}" if duration else "Unknown",
            "subtitles_available": sub_meta["available"],
            "sub_lang": sub_meta["lang"],
            "sub_type": sub_meta["type"],
            "sub_meta": sub_meta
        }
        
        if not sub_meta["available"]:
            total_stt_sec += duration
            
        analysis_results.append(status)
        print(f"  [{idx+1}/{len(entries)}] {video_title[:40]}... | Subs: {sub_meta['type'] if sub_meta['available'] else 'NO'}")
        
    return {
        "playlist_title": title,
        "total_episodes": len(entries),
        "total_stt_duration_sec": total_stt_sec,
        "total_stt_duration_str": f"{int(total_stt_sec // 60):02d}:{int(total_stt_sec % 60):02d}",
        "videos": analysis_results
    }

def run_playlist_acquisition(playlist_url, project_dir, prefix, approved=False, model_id=DEFAULT_MODEL):
    """Full execution flow: Scan, (optionally report & confirm), download, and save transcripts."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    
    # 1. Analyze
    analysis = analyze_playlist_transcripts(playlist_url)
    
    print("\n" + "="*50)
    print("        YouTube Lore Source Analysis")
    print("="*50)
    print(f"Playlist: {analysis['playlist_title']}")
    print(f"Total Videos: {analysis['total_episodes']} clips")
    print("\n[Video List]")
    
    stt_count = 0
    free_count = 0
    for v in analysis["videos"]:
        sub_desc = f"YES ({v['sub_type']}, {v['sub_lang']}) -> [FREE]" if v["subtitles_available"] else "NO (Missing) -> [STT Required]"
        if v["subtitles_available"]:
            free_count += 1
        else:
            stt_count += 1
        print(f"{v['index']}. EP{v['index']:03d}: {v['title'][:40]} ({v['duration_str']}) | Subs: {sub_desc}")
        
    print("-"*50)
    print("SUMMARY:")
    print(f"- Total Episodes: {analysis['total_episodes']}")
    print(f"- Subtitle Download: {free_count} episodes (Free)")
    print(f"- STT Transcription: {stt_count} episodes (Requires API credits)")
    print(f"- Total Audio Duration to transcribe: {analysis['total_stt_duration_str']}")
    print(f"- Target STT Model: {model_id}")
    print("="*50)
    
    if not approved:
        # Prompt user if running interactively
        user_choice = input("\nDo you want to proceed with downloading and transcribing? [y/N]: ").strip().lower()
        if user_choice != 'y':
            print("Acquisition cancelled by user.")
            return {"status": "cancelled", "message": "User declined to proceed."}
            
    # Check API Key if STT is required
    if stt_count > 0 and not api_key:
        raise ValueError("[ERROR] OPENROUTER_API_KEY environment variable is required for STT but not set.")
        
    raw_dir = os.path.join(project_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    
    temp_dir = os.path.join(project_dir, "scratch", "temp_audio")
    os.makedirs(temp_dir, exist_ok=True)
    
    results = []
    
    print("\nStarting downloads and transcriptions...")
    for v in analysis["videos"]:
        ep_num = f"EP{v['index']:03d}"
        file_path = os.path.join(raw_dir, f"{prefix}_{ep_num}.txt")
        
        print(f"\nProcessing {ep_num}: {v['title']}...")
        
        # Check if already exists
        if os.path.exists(file_path):
            print(f"  [SKIPPED] {os.path.basename(file_path)} already exists.")
            results.append({"episode": ep_num, "status": "exists", "path": file_path})
            continue
            
        try:
            if v["subtitles_available"]:
                # Free download
                print("  Pulling subtitles from YouTube transcript list...")
                text = download_and_clean_subtitles(v["id"], v["sub_meta"])
                with open(file_path, "w", encoding="utf-8") as out:
                    out.write(text)
                print(f"  [OK] Saved transcript to: {os.path.basename(file_path)} ({len(text):,} chars)")
                results.append({"episode": ep_num, "status": "subtitles_downloaded", "path": file_path})
            else:
                # STT required
                mp3_path = os.path.join(temp_dir, f"{prefix}_{ep_num}.mp3")
                download_and_compress_audio(v["url"], mp3_path)
                
                # Transcribe
                text = transcribe_audio_openrouter(api_key, mp3_path, model_id)
                
                # Format text
                text = re.sub(r'(\.|\!|\?|ค่ะ|ครับ|นะะ|นะครับ|นะคะ)\s+', r'\1\n\n', text)
                
                with open(file_path, "w", encoding="utf-8") as out:
                    out.write(text)
                    
                print(f"  [OK] Saved STT transcript to: {os.path.basename(file_path)} ({len(text):,} chars)")
                results.append({"episode": ep_num, "status": "stt_transcribed", "path": file_path})
                
                # Delete temp audio to save disk space
                if os.path.exists(mp3_path):
                    os.remove(mp3_path)
        except Exception as e:
            print(f"  [ERROR] Failed to process {ep_num}: {e}")
            results.append({"episode": ep_num, "status": "error", "message": str(e)})
            
    # Clean up temp folder
    if os.path.exists(temp_dir):
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass
            
    return {
        "status": "completed",
        "playlist_title": analysis["playlist_title"],
        "results": results
    }

def main():
    if len(sys.argv) < 4:
        print("Usage: python youtube_acquire.py <playlist_url> <project_dir> <prefix>")
        sys.exit(1)
        
    playlist_url = sys.argv[1]
    project_dir = sys.argv[2]
    prefix = sys.argv[3]
    
    try:
        run_playlist_acquisition(playlist_url, project_dir, prefix, approved=False)
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
