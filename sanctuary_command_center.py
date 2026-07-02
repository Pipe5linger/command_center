import yt_dlp
import os
import threading
import time

# --- Video Harvester Functions ---

def get_video_info(url):
    yt_dlp_opts = {
        'simulate': True,
        'dump_single_file': True,
        'get_title': True,
        'get_description': True,
        'get_thumbnail': True,
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(yt_dlp_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # Remove unnecessary fields to keep the response clean
            for key in [
                'formats', 'requested_formats', 'thumbnails', 'artist', 'track', 'album',
                'extractor', 'extractor_key', 'webpage_url_basename', 'webpage_url_domain',
                'epoch', 'original_url', 'fulltitle', 'id', 'playlist_id', 'playlist_title',
                'playlist_uploader', 'playlist_autonumber', 'playlist_index', 'thumbnail',
                'display_id', 'start_time', 'end_time', 'duration_string', 'is_live',
                'was_live', 'live_status', 'channel_url', 'channel_follower_count',
                'upload_date', 'timestamp', 'tags', 'categories', 'age_limit', 'chapters',
                'like_count', 'channel', 'playlist', 'stretched_ratio', '_type', 'width',
                'height', 'resolution', 'fps', 'vcodec', 'acodec', 'container',
                'vbr', 'abr', 'ext', 'url', 'protocol', 'format_id', 'format',
                'filesize', 'format_note', 'quality', 'source_preference', 'audio_ext',
                'video_ext', 'tbr', 'preference', 'dynamic_range', 'aspect_ratio'
            ]:
                info.pop(key, None)
            return info
    except yt_dlp.DownloadError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}

_download_status = {
    "running": False,
    "stopped": False,
    "paused": False,
    "progress": {"status": "idle"},
    "output_path": None,
    "error": None
}

def _yt_dlp_progress_hook(d):
    global _download_status
    _download_status["progress"] = d

    if d['status'] == 'finished':
        _download_status["output_path"] = d['info_dict']['filepath']
        _download_status["running"] = False
    elif d['status'] == 'error':
        _download_status["error"] = d['error']
        _download_status["running"] = False

def download_video(url, output_folder, file_name=None):
    global _download_status
    if _download_status["running"]:
        return {"success": False, "error": "A download is already in progress."}

    _download_status = {
        "running": True,
        "stopped": False,
        "paused": False,
        "progress": {"status": "downloading"},
        "output_path": None,
        "error": None
    }

    try:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(output_folder, '%(title)s.%(ext)s') if file_name is None else os.path.join(output_folder, f'{file_name}.%(ext)s'),
            'progress_hooks': [_yt_dlp_progress_hook],
            'retries': 5,
            'fragment_retries': 5,
            'ignoreerrors': True,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'trim_filenames': 200,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if _download_status["stopped"]: # Check if stopped by user via another control
            return {"success": False, "message": "Download stopped by user."}

        return {"success": True, "message": "Download complete.", "output_path": _download_status["output_path"]}

    except Exception as e:
        _download_status["error"] = str(e)
        return {"success": False, "error": str(e)}
    finally:
        _download_status["running"] = False

def get_download_status():
    return _download_status
