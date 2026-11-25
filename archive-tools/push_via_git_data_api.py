"""Push the current one-parent local commit via Git data APIs when receive-pack fails.

Preserves exact blob/tree/commit identity; never force-updates a changed remote ref.
Reads existing credential-manager auth into memory only; never prints credentials.
"""
import argparse,base64,datetime,json,os,re,subprocess,time,urllib.error,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPOSITORY='wangbo20261102/20261124-Getoluna-Remote-moving-STB'

def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args])

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
 if not args.apply:raise SystemExit('Pass --apply to publish the current local commit.')
 cred=subprocess.run(['git','-c','credential.interactive=never','credential','fill'],input='protocol=https\nhost=github.com\n\n',text=True,capture_output=True,check=True,env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GCM_INTERACTIVE':'Never'})
 values=dict(x.split('=',1) for x in cred.stdout.splitlines() if '=' in x)
 headers={'Authorization':'Bearer '+values['password'],'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'Luna-Git-Data-Push'}
 def request(method,path,data=None):
  for n in range(4):
   try:
    req=urllib.request.Request('https://api.github.com/repos/'+REPOSITORY+path,data=None if data is None else json.dumps(data).encode(),method=method,headers=headers)
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
   except urllib.error.HTTPError as exc:
    if exc.code not in [429,500,502,503,504] or n==3:raise
   except (urllib.error.URLError,TimeoutError):
    if n==3:raise
   time.sleep(2**n)
 head=git('rev-parse','HEAD').decode().strip();parent=git('rev-parse','HEAD^').decode().strip()
 remote=request('GET','/git/ref/heads/main')['object']['sha']
 if remote==head:print('Remote already matches HEAD');return
 assert remote==parent,('Remote changed; not overriding',remote,parent)
 paths=list(filter(None,git('diff','--name-only','-z',parent,head).decode().split('\0')));elements=[]
 for index,path in enumerate(paths,1):
  entry=git('ls-tree',head,'--',path).decode()
  if not entry:elements.append({'path':path,'mode':'100644','type':'blob','sha':None});continue
  mode,kind,sha=entry.split('\t')[0].split();body=git('cat-file','blob',sha)
  obj=request('POST','/git/blobs',{'content':base64.b64encode(body).decode(),'encoding':'base64'})
  assert obj['sha']==sha
  elements.append({'path':path,'mode':mode,'type':kind,'sha':sha})
  print(f'Stored Git object {index}/{len(paths)}',flush=True)
 tree=request('POST','/git/trees',{'base_tree':git('rev-parse',parent+'^{tree}').decode().strip(),'tree':elements})
 assert tree['sha']==git('rev-parse',head+'^{tree}').decode().strip()
 raw=git('cat-file','commit',head).decode();metadata,message=raw.split('\n\n',1)
 def person(key):
  line=next(x[len(key)+1:] for x in metadata.splitlines() if x.startswith(key+' '))
  match=re.fullmatch(r'(.*) <([^>]+)> (\d+) ([+-])(\d\d)(\d\d)',line);assert match
  minutes=(int(match[5])*60+int(match[6]))*(1 if match[4]=='+' else -1)
  stamp=datetime.datetime.fromtimestamp(int(match[3]),datetime.timezone(datetime.timedelta(minutes=minutes))).isoformat()
  return {'name':match[1],'email':match[2],'date':stamp}
 commit=request('POST','/git/commits',{'message':message,'tree':tree['sha'],'parents':[parent],'author':person('author'),'committer':person('committer')})
 assert commit['sha']==head,('Commit identity differs; ref not changed',commit['sha'],head)
 assert request('GET','/git/ref/heads/main')['object']['sha']==parent
 result=request('PATCH','/git/refs/heads/main',{'sha':head,'force':False});assert result['object']['sha']==head
 print(json.dumps({'published':True,'commit':head,'files':len(elements)}),flush=True)

if __name__=='__main__':main()
