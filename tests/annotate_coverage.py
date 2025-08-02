# annotate_coverage.py (Version 2)
import re
import argparse
from pathlib import Path
import os


def parse_missing_lines(missing_str: str) -> set[int]:
    """
    Konvertiert einen 'Missing'-String aus pytest-cov in ein Set von Zeilennummern.
    Beispiel: "23-39, 74, 81" -> {23, 24, ..., 39, 74, 81}
    """
    missing_lines = set()
    if not missing_str:
        return missing_lines

    parts = missing_str.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                missing_lines.update(range(start, end + 1))
            except ValueError:
                print(f"Warnung: Ungültiger Bereich '{part}' wird ignoriert.")
        else:
            try:
                missing_lines.add(int(part))
            except ValueError:
                print(f"Warnung: Ungültiger Wert '{part}' wird ignoriert.")
    return missing_lines


def annotate_file_with_coverage(coverage_line: str):
    """
    Liest eine Coverage-Zeile, extrahiert den Dateipfad und die fehlenden Zeilen
    und schreibt eine neue, annotierte Datei.
    """
    # 1. Regex, um Dateipfad und die "Missing"-Liste aus der Zeile zu extrahieren
    match = re.search(r"(\S+\.py)\s+\d+\s+\d+\s+\S+%\s*(.*)", coverage_line)
    if not match:
        print(f"Fehler: Konnte die Coverage-Zeile nicht parsen. Stelle sicher, dass sie mit einer .py-Datei endet.")
        print(f"Eingabe: '{coverage_line}'")
        return

    # === VERBESSERUNG HIER ===
    # Extrahiere den Dateipfad und normalisiere ihn (wandelt z.B. \ in / um)
    file_path_str = os.path.normpath(match.group(1))
    source_file = Path(file_path_str)
    print(f"Extrahiere Informationen für Datei: '{source_file}'")
    # ==========================

    # Extrahiere den "Missing"-Teil der Zeile
    missing_str = match.group(2)
    missing_lines_set = parse_missing_lines(missing_str)
    print(f"Gefunden: {len(missing_lines_set)} fehlende Zeilen.")

    # 2. Lese die Quelldatei
    if not source_file.exists():
        print(f"Fehler: Quelldatei nicht gefunden: '{source_file}'")
        return

    lines = source_file.read_text(encoding='utf-8').splitlines()

    # 3. Erstelle die annotierte Datei
    output_path = source_file.with_suffix(source_file.suffix + '.annotated.txt')
    current_state = None  # Kann 'covered' oder 'missing' sein

    print(f"Schreibe annotierte Datei nach: '{output_path}'")
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, line in enumerate(lines, 1):
            line_state = 'missing' if i in missing_lines_set else 'covered'

            if line_state != current_state:
                if current_state is not None:
                    f.write(f"</{current_state}>\n")
                f.write(f"<{line_state}>\n")
                current_state = line_state

            f.write(line + '\n')

        if current_state is not None:
            f.write(f"</{current_state}>\n")

    print("Fertig! Du kannst mir jetzt den Inhalt von '{}' schicken.".format(output_path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Annotiert eine Python-Datei mit Coverage-Informationen basierend auf dem pytest-cov Report.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "coverage_line",
        help="Die vollständige Zeile aus dem 'pytest --cov-report term-missing' Report.\n"
             "Das Skript extrahiert den Dateipfad automatisch.\n\n"
             "Beispiel: \"backend\\database.py        235    108    54%   23-39, 74, 77\""
    )
    args = parser.parse_args()

    annotate_file_with_coverage(args.coverage_line)