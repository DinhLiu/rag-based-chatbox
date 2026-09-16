"""Minimal text PDF builder for ingestion tests."""
import zlib


def make_pdf(pages, *, compress=False):
    def escape(text):
        return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

    count = len(pages)
    page_ids = list(range(4, 4 + count))
    content_ids = list(range(4 + count, 4 + 2 * count))
    kids = ' '.join(f'{item} 0 R' for item in page_ids)
    objects = {
        1: b'<< /Type /Catalog /Pages 2 0 R >>',
        2: f'<< /Type /Pages /Kids [{kids}] /Count {count} >>'.encode(),
        3: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    }
    for page_id, content_id in zip(page_ids, content_ids):
        objects[page_id] = (
            b'<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 3 0 R >> >> '
            + f'/MediaBox [0 0 612 792] /Contents {content_id} 0 R >>'.encode()
        )
    for content_id, page in zip(content_ids, pages):
        commands = ['BT /F1 12 Tf 72 720 Td']
        for index, line in enumerate(page.split('\n')):
            if index:
                commands.append('0 -14 Td')
            commands.append(f'({escape(line)}) Tj')
        commands.append('ET')
        stream = '\n'.join(commands).encode('latin-1')
        if compress:
            payload = zlib.compress(stream)
            header = f'<< /Length {len(payload)} /Filter /FlateDecode >>'.encode()
        else:
            payload = stream
            header = f'<< /Length {len(payload)} >>'.encode()
        objects[content_id] = header + b'\nstream\n' + payload + b'\nendstream'
    output = bytearray(b'%PDF-1.4\n')
    offsets = {}
    for obj_id in sorted(objects):
        offsets[obj_id] = len(output)
        output += f'{obj_id} 0 obj\n'.encode() + objects[obj_id] + b'\nendobj\n'
    start = len(output)
    size = max(objects) + 1
    output += f'xref\n0 {size}\n'.encode()
    output += b'0000000000 65535 f \n'
    for obj_id in range(1, size):
        output += f'{offsets[obj_id]:010d} 00000 n \n'.encode()
    output += f'trailer << /Size {size} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode()
    return bytes(output)
