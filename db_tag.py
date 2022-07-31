#!/usr/bin/env python3
import re
import sys
from traceback import print_exc
import mutagen
import os
import subprocess

RELEVANT_PV_KEYS = ["song_name_en", "songinfo_en", "bpm", "date", "lyric_en"]

def parse_pv_db(fd):
    all_pv_data = {}

    for line in fd.readlines():
        if line.startswith("#") or line == "\n" or not line: # skip comments and empty lines
            continue
        try:
            before, value = line.split("=", 1)
            pv_id, base_key, *extra = before.split(".")
            value = value.strip().replace("\n", "")
        except ValueError:
            print(f"failed on {line=}")
            continue
        
        if base_key not in RELEVANT_PV_KEYS:
            continue

        if pv_id not in all_pv_data: #always ensure this PV is in our dict
            all_pv_data[pv_id] = {}

        this_pv_data = all_pv_data[pv_id]
        
        if base_key == "lyric_en":
            existing = this_pv_data.get("lyrics", [])
            existing.append(value)
            this_pv_data["lyrics"] = existing
        elif base_key == "song_name_en":
            this_pv_data["name"] = value
        elif base_key == "songinfo_en":
            second_key = extra[0]
            if second_key in ["arranger", "music"]:
                this_pv_data[second_key] = value
        elif len(extra) == 0: #handles date, bpm
            this_pv_data[base_key] = value
        else:
            print(f"not sure what to do with {line=}")

    return all_pv_data

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: ./db_tag.py path/to/songs path/to/pv_db.txt output/dir")
        sys.exit(0)

    with open(sys.argv[2]) as pv_fd:
        all_pv_data = parse_pv_db(pv_fd)

    skipped = 0
    ok = 0
    failed = 0

    source_path = sys.argv[1]
    destination_path = sys.argv[3]

    os.makedirs(destination_path, exist_ok=True)
    total_count = len(os.listdir(source_path))
    for index, pv_ogg in enumerate(os.listdir(source_path)):
        full_pv_path = os.path.join(source_path, pv_ogg)
        if not os.path.isfile(full_pv_path) or not re.search("pv_\\d{3}.ogg", pv_ogg):
            print(f"skipping {pv_ogg}")
            skipped += 1
            continue

        try:
            print(f"processing {index}/{total_count}\r", end="")
            this_pv_data = all_pv_data[pv_ogg[:6]]
            song_name = this_pv_data["name"]
            this_destination = os.path.join(destination_path, song_name.replace(" ", "_").replace("/","_")+".ogg")
            cmd = [
                "ffmpeg",
                "-loglevel", "error",
                "-y",
                "-i", full_pv_path,
                "-filter_complex", "[0:a]channelsplit=channel_layout=quad[sl][sr][vl][vr],[sl][vl]amix=inputs=2[fl],[sr][vr]amix=inputs=2[fr],[fl][fr]join=inputs=2:channel_layout=stereo[fa]",
                "-map", "[fa]",
                "-b:a", "128k",
                this_destination                
            ]
            # ffmpeg -i pv_096.ogg -filter_complex "[0:a]channelsplit=channel_layout=quad[sl][sr][vl][vr],[sl][vl]amix=inputs=2[fl],[sr][vr]amix=inputs=2[fr],[fl][fr]join=inputs=2:channel_layout=stereo[fa]" -map "[fa]" /tmp/test.ogg
            ret = subprocess.run(cmd)
            if (status := ret.returncode) != 0:
                raise RuntimeError(f"ffmpeg failed with {status=}")
            audio_obj = mutagen.File(this_destination)
            audio_obj["title"] = this_pv_data["name"]
            year = this_pv_data["date"][:4]
            month = this_pv_data["date"][4:6]
            date = this_pv_data["date"][6:8]
            audio_obj["date"] = f"{year}/{month}/{date}"
            audio_obj["artist"] = this_pv_data["music"]
            audio_obj["album"] = "Project Diva MegaMix+"
            audio_obj["track"] = pv_ogg[3:6]
            audio_obj["lyrics"] = "\n".join(this_pv_data["lyrics"])
            audio_obj["bpm"] = this_pv_data["bpm"]
            audio_obj.save()
            ok+=1
        except Exception as e:
            failed += 1
            print(f"failed {pv_ogg=} {type(e)}")
            print_exc()
    

    print(f"{ok=} {skipped=} {failed=}")
        