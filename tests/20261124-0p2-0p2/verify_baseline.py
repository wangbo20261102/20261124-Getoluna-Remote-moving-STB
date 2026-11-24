import hashlib,json,pathlib,sys
baseline=pathlib.Path(r'E:\Github\Mubea-EV-Gentoluna-baselines\20261124-before-0p2')
trial=pathlib.Path(r'E:\Github\Mubea-EV-Gentoluna-tests\20261124-0p2-0p2')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while block:=f.read(2**20):h.update(block)
    return h.hexdigest()
manifest=json.loads((baseline/'FILE-MANIFEST.json').read_text(encoding='utf-8'))
changed=[]; checked=0; volatile=[]
for e in manifest['entries']:
    if e['volatile_runtime']:
        volatile.append(e['source']);continue
    p=pathlib.Path(e['source'])
    checked+=1
    if not p.is_file() or sha(p)!=e['sha256']:changed.append(e['source'])
archives=json.loads((baseline/'ARCHIVE-CHECKSUMS.json').read_text())
archive_bad=[e['name'] for e in archives if sha(baseline/e['name'])!=e['sha256']]
report={'protected_originals_checked':checked,'changed_protected_originals':changed,'volatile_live_files_excluded':volatile,'archive_checksum_failures':archive_bad,'baseline_intact':not changed and not archive_bad}
out=trial/(sys.argv[1] if len(sys.argv)>1 else 'baseline-verification.json')
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checked':checked,'changed':changed,'archive_failures':archive_bad,'baseline_intact':report['baseline_intact']},ensure_ascii=False))
