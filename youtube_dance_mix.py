#!/usr/bin/env python3
"""
Dance Mix Builder
=================

Author: Vivek Pandit
Initial implementation support: Perplexity, powered by GPT-5.4 Thinking
License recommendation: MIT License for code only, with important usage limitations.

Purpose
-------
This script downloads audio from user-supplied YouTube URLs, trims user-selected
sections, applies light automatic cleanup around quiet intros/outros, and creates
an intelligently crossfaded MP3 mix suitable for dance performance rehearsals or
stage playback preparation.

Important legal / usage notes
-----------------------------
1. This software is provided for lawful use only.
2. You are responsible for ensuring you have the right to download, edit, remix,
   rehearse with, perform, publish, or distribute any source media.
3. The MIT License can cover *this code*, but it does not grant rights to any
   copyrighted music, YouTube media, trademarks, likenesses, or third-party assets.
4. If you publish this on GitHub, include a README that clearly states the tool is
   intended only for content the user owns, is licensed to use, or is otherwise
   legally permitted to process.

Technical overview
------------------
- Uses yt-dlp to download best-available audio from a supplied YouTube URL.
- Uses ffmpeg/ffprobe for probing, silence detection, trimming, normalization,
  and crossfaded mixing.
- Keeps the user's requested start/end times as the primary selection.
- Optionally trims quiet intro/outro regions when clear low-volume sections are found.
- Writes a mix_plan.txt file describing what was requested and what was actually used.

Environment requirements
------------------------
- Python 3.13+
- yt-dlp
- ffmpeg
- ffprobe

This file is intentionally written with explanatory comments so it can be maintained
and published more easily in a public GitHub repository.
"""

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from yt_dlp import YoutubeDL


# Base project folders. The script assumes it is run from the project directory.
BASE_DIR = Path.cwd()
DOWNLOAD_DIR = BASE_DIR / "downloaded_audio"
TEMP_DIR = BASE_DIR / "temp_audio"
OUTPUT_DIR = BASE_DIR / "final_mix"

# Ensure working folders exist before processing begins.
for directory in (DOWNLOAD_DIR, TEMP_DIR, OUTPUT_DIR):
    directory.mkdir(exist_ok=True)


@dataclass
class Song:
    """Represents one song entry supplied by the user."""

    index: int
    url: str
    title: str
    source_mp3: Path
    full_length_s: float
    start_s: float
    end_s: float
    transition_s: float
    adjusted_start_s: float = 0.0
    adjusted_end_s: float = 0.0
    adjustment_notes: List[str] = field(default_factory=list)


def run(cmd: List[str]) -> None:
    """Run a subprocess command and raise an error if it fails."""
    subprocess.run(cmd, check=True)


def run_capture(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess command and capture its output."""
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def sanitize_filename(name: str) -> str:
    """Create a filesystem-safe filename from a title."""
    name = re.sub(r"[^\w\s.-]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:100] if name else "track"


def seconds_to_timestamp(seconds: float) -> str:
    """Convert seconds to mm:ss or hh:mm:ss display format."""
    total = int(round(seconds))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def timestamp_to_seconds(value: str) -> float:
    """Convert a user-supplied timestamp string into seconds."""
    value = value.strip()
    parts = value.split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    raise ValueError(f"Invalid timestamp: {value}")


def ask_default(prompt: str, default: str) -> str:
    """Prompt the user and fall back to a default if they press Enter."""
    value = input(f"{prompt} [{default}]: ").strip()
    return value if value else default


def ffprobe_duration(path: Path) -> float:
    """Return the duration of an audio file in seconds using ffprobe."""
    result = run_capture([
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        str(path),
    ])
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def download_youtube_as_mp3(url: str, index: int) -> Tuple[str, Path]:
    """
    Download audio from a YouTube URL and convert it to MP3.

    Note: downloading media from online platforms may be restricted by law,
    contract, or platform terms depending on jurisdiction and content rights.
    The user is solely responsible for lawful use.
    """
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(DOWNLOAD_DIR / f"track_{index:02d}_%(title)s.%(ext)s"),
        "noplaylist": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }
        ],
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", f"track_{index:02d}")

    candidates = sorted(
        DOWNLOAD_DIR.glob(f"track_{index:02d}_*.mp3"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"Could not find downloaded MP3 for track {index}")

    return title, candidates[0]


def detect_silence_ranges(
    path: Path,
    start_s: float,
    duration_s: float,
    noise_db: int = -34,
    min_silence_s: float = 0.20,
) -> List[Tuple[float, float]]:
    """
    Inspect a clip window and return relative silence ranges.

    This uses ffmpeg's silencedetect filter and parses the output.
    Returned tuples are relative to the inspected window, not the whole source file.
    """
    if duration_s <= 0:
        return []

    result = run_capture([
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-ss", f"{start_s:.3f}",
        "-t", f"{duration_s:.3f}",
        "-i", str(path),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence_s:.3f}",
        "-f", "null",
        "-",
    ], check=False)

    text = f"{result.stdout}\n{result.stderr}"
    ranges: List[Tuple[float, float]] = []
    current_start = None

    for line in text.splitlines():
        silence_start = re.search(r"silence_start:\s*([0-9.]+)", line)
        if silence_start:
            current_start = float(silence_start.group(1))
            continue

        silence_end = re.search(r"silence_end:\s*([0-9.]+)", line)
        if silence_end and current_start is not None:
            end_val = float(silence_end.group(1))
            ranges.append((max(0.0, current_start), min(duration_s, end_val)))
            current_start = None

    if current_start is not None:
        ranges.append((max(0.0, current_start), duration_s))

    return ranges


def auto_adjust_song_boundaries(song: Song) -> None:
    """
    Lightly adjust clip boundaries to reduce obvious dead air.

    Philosophy:
    - Respect the user's requested range as the primary choice.
    - Only move boundaries when a clearly quiet intro/outro is detected.
    - Avoid aggressive trimming that could remove intentional musical phrasing.
    """
    adjusted_start = song.start_s
    adjusted_end = song.end_s
    notes: List[str] = []

    clip_duration = adjusted_end - adjusted_start
    if clip_duration <= 2.0:
        song.adjusted_start_s = adjusted_start
        song.adjusted_end_s = adjusted_end
        song.adjustment_notes = notes
        return

    # Inspect the opening portion for dead air or very quiet intro material.
    lead_window = min(8.0, clip_duration / 3)
    leading_ranges = detect_silence_ranges(song.source_mp3, adjusted_start, lead_window)
    for start_rel, end_rel in leading_ranges:
        if start_rel <= 0.35 and end_rel >= 0.25:
            shift = min(end_rel + 0.05, max(0.0, clip_duration - 4.0))
            if shift >= 0.20:
                adjusted_start += shift
                notes.append(f"Skipped {shift:.2f}s of quiet intro")
            break

    # Inspect the tail region for quiet outro material that would hurt the transition.
    clip_duration = adjusted_end - adjusted_start
    if clip_duration > 6.0:
        tail_window = min(12.0, clip_duration / 2)
        tail_search_start = adjusted_end - tail_window
        trailing_ranges = detect_silence_ranges(song.source_mp3, tail_search_start, tail_window)
        for start_rel, end_rel in reversed(trailing_ranges):
            if end_rel >= tail_window - 0.15 and (tail_window - start_rel) >= 0.25:
                candidate_end = tail_search_start + start_rel
                minimum_needed = adjusted_start + max(4.0, song.transition_s + 1.0)
                if candidate_end > minimum_needed:
                    trimmed = adjusted_end - candidate_end
                    if trimmed >= 0.20:
                        adjusted_end = candidate_end
                        notes.append(f"Trimmed {trimmed:.2f}s of quiet outro")
                break

    # Protect against accidental over-trimming.
    if adjusted_end <= adjusted_start + 1.0:
        adjusted_start = song.start_s
        adjusted_end = song.end_s
        notes = ["Auto-adjustment skipped to preserve minimum clip length"]

    song.adjusted_start_s = adjusted_start
    song.adjusted_end_s = adjusted_end
    song.adjustment_notes = notes


def make_trimmed_segment(song: Song, out_path: Path) -> None:
    """Create a normalized trimmed MP3 segment for one selected song region."""
    start_s = song.adjusted_start_s if song.adjusted_start_s else song.start_s
    end_s = song.adjusted_end_s if song.adjusted_end_s else song.end_s
    clip_duration = max(0.1, end_s - start_s)

    # Short fades reduce clicks while preserving rhythmic punch.
    fade_in = min(0.20, clip_duration / 10)
    fade_out = min(0.35, clip_duration / 10)
    fade_out_start = max(0.0, clip_duration - fade_out)

    filters = [
        "aresample=44100",
        "aformat=sample_fmts=s16:channel_layouts=stereo",
        "highpass=f=35",
    ]

    if clip_duration > 0.60:
        filters.append(f"afade=t=in:st=0:d={fade_in:.3f}")
    if clip_duration > 1.00:
        filters.append(f"afade=t=out:st={fade_out_start:.3f}:d={fade_out:.3f}")

    # Loudness normalization helps maintain perceived consistency between songs.
    filters.append("loudnorm=I=-14:LRA=7:TP=-1.5")

    run([
        "ffmpeg", "-y",
        "-ss", f"{start_s:.3f}",
        "-i", str(song.source_mp3),
        "-t", f"{clip_duration:.3f}",
        "-vn",
        "-af", ",".join(filters),
        "-ar", "44100",
        "-ac", "2",
        "-b:a", "320k",
        str(out_path),
    ])


def mix_two_tracks(current_mix: Path, next_track: Path, requested_transition_s: float, out_path: Path) -> float:
    """
    Crossfade the current mix into the next track.

    The user's transition value is interpreted as desired musical overlap time,
    not inserted silence. The function caps the overlap to safe values based on
    the available clip durations.
    """
    current_duration = ffprobe_duration(current_mix)
    next_duration = ffprobe_duration(next_track)

    requested = max(0.0, requested_transition_s)
    if requested == 0.0:
        requested = 2.0

    crossfade = min(
        requested,
        max(0.8, current_duration - 0.6),
        max(0.8, next_duration - 0.6),
        8.0,
    )
    crossfade = max(0.8, crossfade)

    filter_complex = (
        f"[0:a]aresample=44100,aformat=sample_fmts=s16:channel_layouts=stereo[a0];"
        f"[1:a]aresample=44100,aformat=sample_fmts=s16:channel_layouts=stereo[a1];"
        f"[a0][a1]acrossfade=d={crossfade:.3f}:c1=tri:c2=tri,"
        f"highpass=f=35,loudnorm=I=-14:LRA=7:TP=-1.5[out]"
    )

    run([
        "ffmpeg", "-y",
        "-i", str(current_mix),
        "-i", str(next_track),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-ar", "44100",
        "-ac", "2",
        "-b:a", "320k",
        str(out_path),
    ])

    return crossfade


def build_intelligent_mix(segment_paths: List[Path], transitions: List[float], out_path: Path) -> List[float]:
    """Build the final mix by successively crossfading trimmed segments."""
    if not segment_paths:
        raise ValueError("No segments to mix")

    if len(segment_paths) == 1:
        shutil.copy2(segment_paths[0], out_path)
        return []

    used_transitions: List[float] = []
    current_mix = TEMP_DIR / "mix_stage_01.mp3"
    shutil.copy2(segment_paths[0], current_mix)

    for i in range(1, len(segment_paths)):
        next_track = segment_paths[i]
        next_mix = TEMP_DIR / f"mix_stage_{i + 1:02d}.mp3"
        used = mix_two_tracks(current_mix, next_track, transitions[i - 1], next_mix)
        used_transitions.append(used)
        current_mix = next_mix

    shutil.copy2(current_mix, out_path)
    return used_transitions


def write_plan(songs: List[Song], output_mp3: Path, used_transitions: List[float]) -> None:
    """Write a human-readable plan file summarizing what the script produced."""
    plan = OUTPUT_DIR / "mix_plan.txt"
    lines = [
        "Dance Mix Plan",
        "=" * 60,
        f"Final file: {output_mp3}",
        "",
    ]

    for i, song in enumerate(songs):
        final_start = song.adjusted_start_s if song.adjusted_start_s else song.start_s
        final_end = song.adjusted_end_s if song.adjusted_end_s else song.end_s

        lines.extend([
            f"Song {song.index}: {song.title}",
            f"URL: {song.url}",
            f"Source MP3: {song.source_mp3}",
            f"Full length: {seconds_to_timestamp(song.full_length_s)}",
            f"Requested start: {seconds_to_timestamp(song.start_s)}",
            f"Requested end:   {seconds_to_timestamp(song.end_s)}",
            f"Used start:      {seconds_to_timestamp(final_start)}",
            f"Used end:        {seconds_to_timestamp(final_end)}",
        ])

        if song.adjustment_notes:
            lines.append("Adjustments: " + "; ".join(song.adjustment_notes))
        else:
            lines.append("Adjustments: none")

        if i < len(used_transitions):
            lines.append(f"Requested transition into next song: {song.transition_s:.1f} sec")
            lines.append(f"Used overlap/crossfade:             {used_transitions[i]:.1f} sec")
        else:
            lines.append("Requested transition into next song: 0.0 sec")

        lines.append("")

    plan.write_text("\n".join(lines), encoding="utf-8")


def print_banner() -> None:
    """Display a small startup banner."""
    print("Dance Mix Builder (smart crossfade edition)")
    print("Author: Vivek Pandit")
    print("Implementation support: Perplexity, powered by GPT-5.4 Thinking")
    print("---------------------------------------------------------------")


def collect_songs() -> List[Song]:
    """Interactively collect song URLs, trim ranges, and transition preferences."""
    try:
        num_songs = int(input("How many songs do you want in the mix? ").strip())
    except ValueError:
        raise SystemExit("Please enter a whole number.")

    if num_songs < 1:
        raise SystemExit("Enter at least 1 song.")

    songs: List[Song] = []

    for i in range(1, num_songs + 1):
        print(f"\n--- Song {i} ---")
        url = input("Enter YouTube URL: ").strip()
        title, mp3_path = download_youtube_as_mp3(url, i)
        duration_s = ffprobe_duration(mp3_path)

        default_start = "00:00"
        default_end = seconds_to_timestamp(duration_s)

        print(f"Downloaded: {title}")
        print(f"Full length detected: {default_end}")

        start_text = ask_default("Start time (mm:ss or hh:mm:ss)", default_start)
        end_text = ask_default("End time (mm:ss or hh:mm:ss)", default_end)

        if i < num_songs:
            transition_text = ask_default(
                "Transition time into next song in seconds (used as overlap/crossfade)",
                "3"
            )
            transition_s = float(transition_text)
        else:
            transition_s = 0.0

        start_s = timestamp_to_seconds(start_text)
        end_s = timestamp_to_seconds(end_text)

        if start_s < 0 or end_s <= start_s or end_s > duration_s:
            raise SystemExit(f"Invalid start/end times for song {i}.")

        song = Song(
            index=i,
            url=url,
            title=title,
            source_mp3=mp3_path,
            full_length_s=duration_s,
            start_s=start_s,
            end_s=end_s,
            transition_s=transition_s,
        )

        auto_adjust_song_boundaries(song)
        songs.append(song)

    return songs


def main() -> None:
    """Main program entry point."""
    print_banner()

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("ffmpeg and ffprobe must be installed and available in PATH.")

    songs = collect_songs()

    segment_paths: List[Path] = []

    print("\nCreating trimmed song sections...")
    for song in songs:
        segment_path = TEMP_DIR / f"segment_{song.index:02d}.mp3"
        make_trimmed_segment(song, segment_path)
        segment_paths.append(segment_path)

    output_name = sanitize_filename("_".join(s.title[:20] for s in songs[:3])) or "dance_mix"
    output_mp3 = OUTPUT_DIR / f"{output_name}_dance_mix.mp3"

    print("Building smart mix...")
    used_transitions = build_intelligent_mix(
        segment_paths,
        [s.transition_s for s in songs[:-1]],
        output_mp3,
    )

    write_plan(songs, output_mp3, used_transitions)

    print("\nDone.")
    print(f"Final mix: {output_mp3.resolve()}")
    print(f"Plan file: {(OUTPUT_DIR / 'mix_plan.txt').resolve()}")
    if used_transitions:
        print("Crossfades used:")
        for i, duration in enumerate(used_transitions, start=1):
            print(f"  Between song {i} and song {i + 1}: {duration:.1f} sec")


if __name__ == "__main__":
    main()
