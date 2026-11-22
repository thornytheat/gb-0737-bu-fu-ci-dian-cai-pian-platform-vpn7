import csv
from io import StringIO

from app.config import ROW_LIMIT
from app.evidence import Row
from app.reasons import FabricError


def decode(source):
    if not source.data:
        raise FabricError("EMPTY_FILE", file=source.name)
    choices = ("utf-8-sig",) if source.data.startswith(b"\xef\xbb\xbf") else ("utf-8", "gb18030")
    for encoding in choices:
        try:
            return source.data.decode(encoding), encoding
        except UnicodeDecodeError as exc:
            if encoding == choices[-1]:
                raise FabricError("ENCODING", file=source.name, line=source.data[:exc.start].count(b"\n") + 1) from exc


def records(source, columns, allow_no_defects=False):
    text, encoding = decode(source)
    reader = csv.reader(StringIO(text, newline=""), strict=True)
    header = None
    segments = blank = last_line = 0
    rows = []
    try:
        for cells in reader:
            start = last_line + 1
            last_line = reader.line_num
            names = tuple(cell.strip() for cell in cells)
            if not any(names):
                blank += 1
                continue
            if header is None:
                if len(names) != len(columns) or set(names) != set(columns):
                    raise FabricError("BAD_HEADER", file=source.name, line=start)
                header, segments = names, 1
            elif names == header:
                segments += 1
            else:
                if len(rows) >= ROW_LIMIT:
                    raise FabricError("FILE_LIMIT", file=source.name, line=start)
                rows.append(Row(source.name, start, last_line, tuple(cells)))
    except csv.Error as exc:
        raise FabricError("CSV_SYNTAX", file=source.name, line=last_line + 1) from exc
    if header is None:
        raise FabricError("BLANK_FILE", file=source.name)
    if not rows and not allow_no_defects:
        raise FabricError("HEADER_ONLY", file=source.name)
    return rows, header, {"file": source.name, "encoding": encoding, "raw": len(rows), "blank": blank, "segments": segments}
