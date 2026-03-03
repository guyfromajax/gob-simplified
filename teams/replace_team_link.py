"""Replace team_link numbers with team names. Writes to a NEW file (never overwrites input).

Usage: python3 replace_team_link.py [path_to_all_players] [path_to_team_link] [path_to_output]
  Defaults (relative to script dir):
    all_players.txt -> all_players.txt (input)
    team_link.txt
    all_players_with_team_names.txt (output)

Example: python3 replace_team_link.py teams/all_players.txt teams/team_link.txt teams/all_players_with_team_names.txt
"""
import os
import sys

_dir = os.path.dirname(os.path.abspath(__file__))
players_path = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(_dir, "all_players.txt")
team_link_path = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(_dir, "team_link.txt")
output_path = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else os.path.join(_dir, "all_players_with_team_names.txt")

if os.path.abspath(players_path) == os.path.abspath(output_path):
    print("Error: output path must differ from input path (will not overwrite input).")
    sys.exit(1)

# Build number -> team name from team_link.txt
team_by_num = {}
with open(team_link_path) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            num_str, name = parts[0].strip(), parts[1].strip()
            try:
                team_by_num[int(num_str)] = name
            except ValueError:
                pass

with open(players_path) as f:
    lines = f.readlines()

if not lines:
    print("No lines read from input. Aborting.")
    sys.exit(1)

out_lines = []
for line in lines:
    line = line.rstrip("\n\r")
    if not line:
        out_lines.append("")
        continue
    parts = line.split("\t")
    if not parts:
        out_lines.append(line)
        continue
    try:
        num = int(parts[-1])
        parts[-1] = team_by_num.get(num, str(parts[-1]))
    except (ValueError, IndexError):
        pass
    out_lines.append("\t".join(parts))

with open(output_path, "w") as f:
    f.write("\n".join(out_lines))
    if out_lines:
        f.write("\n")

print(f"Wrote {len(out_lines)} lines to {output_path}")
if len(out_lines) > 1:
    print(f"First data row last col: {out_lines[1].split(chr(9))[-1]!r}")
