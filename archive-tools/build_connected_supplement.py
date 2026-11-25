"""Package only additions/changes over the immutable 2026-11-24 complete base."""
from pathlib import Path
import hashlib,json,zipfile,time
ROOT=Path(__file__).resolve().parents[1]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def include(p):
 rel=p.relative_to(ROOT)
 return not any(x in {'.git','archives'} for x in rel.parts) and not (p.parent==ROOT and (p.name.startswith('publication-') or p.name=='prepublish-secret-scan.json')) and rel.as_posix()!='manifests/FILE-MANIFEST.json'
base=json.loads((ROOT/'manifests/history/20261124-FILE-MANIFEST.json').read_text(encoding='utf-8'))
old={e['path']:e for e in base['files']}
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p))
entries=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
changed=[e for e in entries if old.get(e['path'],{}).get('sha256')!=e['sha256']]
mf=ROOT/'manifests/FILE-MANIFEST.json'
mf.write_text(json.dumps({'date':'2026-11-25','note':'Complete local extracted tree; original base plus connected supplement. Excludes itself, Git internals, output archives and publication receipts.','files':entries,'file_count':len(entries),'total_bytes':sum(e['bytes'] for e in entries)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
out=ROOT/'archives/update-20261125';out.mkdir(parents=True,exist_ok=True)
archive=out/'Getoluna-STB-20261125-robot-sync-supplement.zip'
selected=[ROOT/e['path'] for e in changed]+[mf]
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5,allowZip64=True) as z:
 for p in selected:
  mode=zipfile.ZIP_STORED if p.suffix.lower() in {'.png','.jpg','.gif','.gz','.zip','.pdf','.exe','.dll','.apk','.deb'} else zipfile.ZIP_DEFLATED
  z.write(p,p.relative_to(ROOT).as_posix(),compress_type=mode)
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
h=sha(archive)
result={'archive':archive.name,'bytes':archive.stat().st_size,'sha256':h,'zip_crc_verified':True,'supplement_entries':len(selected),'current_manifest_files':len(entries),'requires_base_archive':'Getoluna-STB-20261124-complete.zip','base_sha256':'ae8f79bc5401c35d51a1be42dfbdcd7dc5976e46ae502d42d0a7959494fc392d','base_release':'https://github.com/wangbo20261102/20261124-Getoluna-Remote-moving-STB/releases/tag/archive-20261124','restore':'Extract the unchanged 20261124 complete base, then this supplement over it in the same directory.'}
(out/'package-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(out/'SHA256SUMS.txt').write_text(h+'  '+archive.name+'\n'+sha(mf)+'  FILE-MANIFEST.json\n',encoding='ascii')
print(json.dumps(result),flush=True)
