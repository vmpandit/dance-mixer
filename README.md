# Dance Mix Builder

A Python-based command-line tool for creating performance-ready dance mixes from user-supplied YouTube audio sources.

**Author:** Vivek Pandit  
**Implementation support:** Perplexity, powered by GPT-5.4 Thinking

## Overview

Dance Mix Builder downloads audio from user-provided YouTube links, converts the audio to MP3, trims each song to user-selected start and end points, lightly analyzes the selected regions for quiet intro and outro sections, and builds a final mixed MP3 using intelligent crossfades instead of dead silence.

This project is designed for rehearsal and performance-prep workflows where dancers need a cleaner transition from one section to the next without manually editing audio in a DAW.

## Environment and Platform Support

This project is currently set up primarily for **macOS**.

The included launcher script, `run_dancemix.sh`, uses a hard-coded macOS-style path:

```bash
/Users/vivekpandit/Downloads/dancemix
```

Because of that, the repository in its current form is best described as:

- **Tested target environment:** macOS
- **Shell used by launcher:** `zsh`
- **Python environment:** local virtual environment in `.venv/`
- **External tools required:** `ffmpeg`, `ffprobe`, and Python package `yt-dlp`

The Python script itself is mostly portable and may also run on Linux with minor path or launcher changes, but this repository should not claim full cross-platform support unless Windows and Linux launch/setup flows are added and tested.

## Features

- Download audio from user-supplied YouTube video URLs using `yt-dlp`
- Convert downloaded audio to MP3
- Default each song to the full detected runtime, with editable start and end times
- Trim songs to exact user-defined sections
- Detect quiet intro and outro regions and lightly auto-adjust clip boundaries when appropriate
- Crossfade songs together using the user-entered transition time as overlap, not silence
- Normalize output loudness for more consistent playback
- Export a final mixed MP3 and a detailed `mix_plan.txt`

## Requirements

### Required software

- macOS
- Python 3.13 or newer recommended
- `ffmpeg`
- `ffprobe`
- `yt-dlp` Python package
- `zsh` shell for the included launcher script

### Recommended macOS setup

This is the expected setup for the current repository:

- Project folder stored locally, for example in `~/Downloads/dancemix`
- A Python virtual environment created inside the project as `.venv`
- `ffmpeg` available in your terminal `PATH`

## Project Structure

```text
.
├── README.md
├── run_dancemix.sh
├── youtube_dance_mix.py
├── downloaded_audio/
├── temp_audio/
└── final_mix/
```

## Setup

### 1. Clone or copy the repository

```bash
git clone <your-repo-url>
cd dancemix
```

If you are not cloning from GitHub yet, place the project in a folder such as:

```bash
/Users/vivekpandit/Downloads/dancemix
```

### 2. Create and activate a virtual environment

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
python -m pip install --upgrade pip
python -m pip install yt-dlp
```

### 4. Verify ffmpeg tools are installed

```bash
ffmpeg -version
ffprobe -version
```

### 5. Review the launcher path if needed

The included `run_dancemix.sh` script assumes the project is located at:

```bash
/Users/vivekpandit/Downloads/dancemix
```

If your project lives somewhere else, update the `PROJECT_DIR` value inside `run_dancemix.sh` before using it.

## Usage

Run the launcher script:

```bash
./run_dancemix.sh
```

Or run the Python script directly after activating the virtual environment:

```bash
python youtube_dance_mix.py
```

The program will:

1. Ask how many songs should be included in the mix.
2. Ask for each YouTube URL.
3. Detect the full song length and prefill default start and end times.
4. Ask for a transition duration into the next song.
5. Trim the selected sections.
6. Optionally tighten obvious quiet intro/outro sections.
7. Crossfade each section into the next.
8. Save the final MP3 and a text mix plan.

## Output Files

### `final_mix/`

- Final mixed MP3 output
- `mix_plan.txt` describing requested times, adjusted times, and crossfade durations

### `downloaded_audio/`

- Source MP3 files downloaded from the supplied links

### `temp_audio/`

- Temporary processing files created during trimming and mixing

## Notes on Transitions

The transition value entered for each song is treated as a target overlap or crossfade into the next song. It is **not** inserted as dead silence.

The script also attempts light silence detection around selected clip boundaries so transitions feel cleaner, while still respecting the user's chosen sections as the main source of truth.

## Legal and Usage Notice

This repository is intended for lawful use only.

Users are responsible for ensuring they have the legal right to access, download, edit, remix, perform, publish, or distribute any media processed with this tool. Availability of source media on YouTube or another platform does **not** automatically grant permission to download or reuse that media.

This project should be published with a license that applies to the **source code only**. Any open-source license included with this repository does not grant rights to copyrighted music, audio recordings, video content, trademarks, or other third-party media.

This README is not legal advice. For public distribution or commercial use, verify the relevant platform terms and any applicable copyright or performance-rights obligations.

## Suggested Open-Source License

For the code in this repository, the **MIT License** is a practical choice because it is simple, well understood, and commonly used for small utility projects.

If this repository is published publicly, include:

- `LICENSE` containing the MIT License text
- `.gitignore` excluding `.venv/`, `downloaded_audio/`, `temp_audio/`, and `final_mix/`
- Clear wording that the license applies to code only, not to media processed with the tool

## Suggested `.gitignore`

```gitignore
.venv/
downloaded_audio/
temp_audio/
final_mix/
__pycache__/
*.pyc
.DS_Store
```

## Credits

Created and maintained by Vivek Pandit.

Initial implementation support provided through Perplexity, powered by GPT-5.4 Thinking.
