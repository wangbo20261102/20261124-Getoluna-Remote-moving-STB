"""Read-only source capture. Writes only a versioned archive and its manifest.

Growing files are captured up to their initial size; later growth is recorded.
No robot commands, service changes, credential directories or SDK links.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile


class HashReader:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()
        self.count = 0

    def read(self, size=-1):
        chunk = self.stream.read(size)
        self.digest.update(chunk)
        self.count += len(chunk)
        return chunk


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def capture(spec, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    archive = output / spec['archive_name']
    if archive.exists():
        raise RuntimeError('Refusing to overwrite an existing frozen archive')
    report = {'started_at': datetime.datetime.now().astimezone().isoformat(),
              'roots': spec['roots'], 'files': [], 'errors': [],
              'source_mutations': False, 'robot_commands': False}
    seen = set()
    with tarfile.open(archive, 'w:gz', compresslevel=3) as tar:
        for root in spec['roots']:
            source, prefix = Path(root['source']), root['archive_prefix']
            if not source.exists() and not source.is_symlink():
                report['errors'].append({'source': str(source), 'error': 'missing'})
                continue
            paths = [source]
            if source.is_dir() and not source.is_symlink():
                for folder, dirs, files in os.walk(source, followlinks=False):
                    dirs.sort(); files.sort()
                    paths.extend(Path(folder) / name for name in dirs + files)
            for path in paths:
                relative = path.relative_to(source).as_posix()
                name = prefix if relative == '.' else prefix.rstrip('/') + '/' + relative
                if name in seen:
                    continue
                seen.add(name)
                row = {'source': str(path), 'archive_path': name}
                try:
                    before = path.lstat()
                    info = tar.gettarinfo(str(path), arcname=name)
                    if info.islnk():
                        tar.addfile(info)
                        row.update(kind='hardlink', target=info.linkname)
                    elif stat.S_ISREG(before.st_mode):
                        # Buffer one bounded file snapshot before writing a tar
                        # header so log rotation/truncation cannot corrupt tar.
                        with tempfile.SpooledTemporaryFile(max_size=2*1024*1024) as snapshot:
                            digest = hashlib.sha256()
                            remaining = info.size
                            with path.open('rb') as stream:
                                while remaining:
                                    block = stream.read(min(1024*1024, remaining))
                                    if not block:
                                        break
                                    snapshot.write(block); digest.update(block)
                                    remaining -= len(block)
                            info.size -= remaining
                            snapshot.seek(0)
                            tar.addfile(info, snapshot)
                        after = path.stat()
                        row.update(kind='file', bytes=info.size, sha256=digest.hexdigest(),
                                   truncated_during_capture=bool(remaining),
                                   source_size_after=after.st_size,
                                   source_changed_during_capture=(before.st_size != after.st_size or
                                                                  before.st_mtime_ns != after.st_mtime_ns))
                    elif info.issym():
                        tar.addfile(info)
                        row.update(kind='symlink', target=info.linkname)
                    elif info.isdir():
                        tar.addfile(info)
                        continue
                    else:
                        row.update(kind='special', included=False)
                        continue
                    report['files'].append(row)
                except Exception as exc:
                    report['errors'].append({'source': str(path), 'error': str(exc)})
                if len(report['files']) and len(report['files']) % 1000 == 0:
                    print(json.dumps({'captured_entries': len(report['files'])}), flush=True)
        report['finished_source_capture_at'] = datetime.datetime.now().astimezone().isoformat()
        body = json.dumps(report, ensure_ascii=False, indent=2).encode('utf-8')
        import io
        info = tarfile.TarInfo('SNAPSHOT-MANIFEST.json')
        info.size = len(body)
        tar.addfile(info, io.BytesIO(body))
    report['archive'] = {'name': archive.name, 'bytes': archive.stat().st_size, 'sha256': sha(archive)}
    report['finished_at'] = datetime.datetime.now().astimezone().isoformat()
    (output / 'snapshot-manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'archive': report['archive'], 'entries': len(report['files']),
                      'captured_bytes': sum(row.get('bytes', 0) for row in report['files']),
                      'errors': report['errors']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('spec')
    parser.add_argument('output')
    args = parser.parse_args()
    capture(json.loads(Path(args.spec).read_text(encoding='utf-8-sig')), args.output)
