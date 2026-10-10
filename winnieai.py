#!/usr/bin/env python3
"""WinnieAI: offline co-occurrence learning and retrieval, not an LLM."""
import argparse
import collections
import curses
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import textwrap

VERSION = '1.0.0'
STOP = set('the a an and or to of in on for is are it that this i you we they be was were do does what how who can me my your with about'.split())
LIMIT = 10000
BASE = [('hello hi greeting welcome', 'Hello! Teach me something or ask about what I know.'),
        ('what are you ai program learning', 'I am WinnieAI, an offline word-graph learner. I retrieve text and replies you teach me, not generate like a large language model.'),
        ('how learn teach memory', 'Use F2 to teach text, or /teach question => reply. Your memory saves automatically on this device.')]

def tokens(text):
    return re.findall(r"[^\W_]+(?:['-][^\W_]+)*", str(text).lower(), re.UNICODE)

def terms(text):
    return [t for t in tokens(text) if t not in STOP]

def normalized(v):
    norm = math.sqrt(sum(x*x for x in v.values()))
    return {k: x/norm for k,x in v.items()} if norm else {}

def cosine(a,b):
    if len(a)>len(b): a,b=b,a
    return sum(x*b.get(k,0) for k,x in a.items())

class Brain:
    def __init__(self, base=True):
        self.graph = {}; self.df = {}; self.docs = []; self.qa = []; self.count = 0
        self.vectors = {}
        if base:
            for q,a in BASE: self.teach(q,a)

    def idf(self,t):
        return math.log((self.count+1)/(self.df.get(t,0)+1))+1

    def learn(self,text):
        if not isinstance(text,str) or not text.strip(): raise ValueError('Nothing to learn.')
        if len(text)>100000: raise ValueError('Teach at most 100,000 characters at a time.')
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+',text) if s.strip()]
        new = set(terms(text))-self.graph.keys()
        if len(self.graph)+len(new)>LIMIT or len(self.docs)+len(sentences)>LIMIT:
            raise ValueError('Memory limit reached (10,000 words/sentences). Export before starting a new memory.')
        for s in sentences:
            ts = terms(s)
            if not ts: continue
            self.docs.append(s); self.count += 1
            for t in set(ts):
                self.df[t]=self.df.get(t,0)+1; self.graph.setdefault(t,{})
            for i,a in enumerate(ts):
                for b in ts[i+1:i+3]:
                    if a==b: continue
                    self.graph[a][b]=self.graph[a].get(b,0)+1
                    self.graph[b][a]=self.graph[b].get(a,0)+1
        self.rebuild()

    def rebuild(self):
        self.vectors={t:normalized({n:(1+math.log(w))*self.idf(n) for n,w in ns.items() if w>0}) for t,ns in self.graph.items()}

    def teach(self,q,a):
        if not q.strip() or not a.strip(): raise ValueError('Use /teach question => reply, with both filled in.')
        if len(q)>2000 or len(a)>10000 or len(self.qa)>=LIMIT: raise ValueError('Reply or memory is too large.')
        self.learn(q+'\n'+a)
        # A correction replaces the prior explicit answer to the same prompt.
        self.qa=[p for p in self.qa if tokens(p[0])!=tokens(q)]
        self.qa.append([q,a])

    def search(self,phrase,top=16):
        q={}
        for t in terms(phrase):
            for n,v in self.vectors.get(t,{}).items(): q[n]=q.get(n,0)+v
        q=normalized(q)
        scores=[(t,cosine(q,v)) for t,v in self.vectors.items()]
        return sorted(((t,s) for t,s in scores if s>0),key=lambda x:(-x[1],x[0]))[:top]

    def text_vector(self,text):
        return normalized({t:(1+math.log(n))*self.idf(t) for t,n in collections.Counter(terms(text)).items()})

    def answer(self,text):
        for q,a in reversed(self.qa):
            if tokens(q)==tokens(text): return a, 'exact taught reply'
        v=self.text_vector(text)
        ranked=sorted(((cosine(v,self.text_vector(q)),a) for q,a in self.qa),reverse=True)
        if ranked and ranked[0][0]>=.48: return ranked[0][1], 'taught reply, similarity %.2f'%ranked[0][0]
        ranked=sorted(((cosine(v,self.text_vector(d)),d) for d in self.docs),reverse=True)
        if ranked and ranked[0][0]>=.25:
            return 'From my learned text: '+ranked[0][1], 'retrieved sentence, similarity %.2f'%ranked[0][0]
        related=self.search(text,5)
        if related: return 'Related words: '+', '.join(t for t,s in related)+'. Teach me a reply with /teach question => reply.', 'graph association only'
        return "I don't know that yet. Use F2 to teach me, or /teach question => reply.", 'unknown'

    def data(self):
        return dict(format='WinnieAI',version=1,graph=self.graph,docCount=self.count,tokenDocFreq=self.df,documents=self.docs,replies=self.qa)

    def load(self,path):
        path=Path(path).expanduser()
        if path.stat().st_size>20_000_000: raise ValueError('Memory file exceeds 20 MB.')
        value=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value,dict): raise ValueError('Memory must be a JSON object.')
        modern=value.get('format')=='WinnieAI'
        if modern and value.get('version')!=1: raise ValueError('Unsupported memory version.')
        graph=value.get('graph') if modern else value
        if not isinstance(graph,dict) or len(graph)>LIMIT: raise ValueError('Invalid graph.')
        clean={}
        for t,ns in graph.items():
            if not isinstance(t,str) or len(t)>200 or not isinstance(ns,dict) or len(ns)>LIMIT: raise ValueError('Invalid graph node.')
            clean[t]={}
            for n,w in ns.items():
                if not isinstance(n,str) or len(n)>200 or isinstance(w,bool) or not isinstance(w,(int,float)) or not math.isfinite(w) or w<=0: raise ValueError('Invalid graph weight.')
                clean[t][n]=w
        docs=value.get('documents',[]) if modern else []
        qa=value.get('replies',[]) if modern else []
        count=value.get('docCount',max(1,len(graph))) if modern else max(1,len(graph))
        df=value.get('tokenDocFreq',{}) if modern else {t:1 for t in graph}
        if not isinstance(count,int) or count<0 or not isinstance(df,dict): raise ValueError('Invalid document statistics.')
        if any(not isinstance(k,str) or not isinstance(v,int) or v<0 or v>count for k,v in df.items()): raise ValueError('Invalid document frequency.')
        if not isinstance(docs,list) or len(docs)>LIMIT or any(not isinstance(d,str) or len(d)>100000 for d in docs): raise ValueError('Invalid documents.')
        if not isinstance(qa,list) or len(qa)>LIMIT or any(not isinstance(p,list) or len(p)!=2 or any(not isinstance(s,str) or len(s)>10000 for s in p) for p in qa): raise ValueError('Invalid taught replies.')
        # Assign only after all validation passes. Bad imports never erase memory.
        self.graph=clean; self.docs=docs; self.qa=qa; self.count=count; self.df=df; self.rebuild()

    def save(self,path):
        path=Path(path).expanduser(); path.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='.'+path.name,dir=str(path.parent))
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                json.dump(self.data(),f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)

HELP = '''F1 Help | F2 Teach multiline text | F3 Graph | F4 Chat
Enter sends chat. Up/Down scroll chat, select graph nodes. Enter explores a node.
Click graph labels if your terminal supports mouse. Resize is automatic.
/learn text                     Learn a sentence or pasted paragraph
/teach question => reply        Teach or correct an actual chat reply
/search words                   Similar words via graph-vector cosine similarity
/graph word                     Explore word links and their weights
/read /path/to/file.txt          Learn a local UTF-8 text file (100 KB max)
/import /path/memory.Winnieai    Replace memory after validation
/export /path/memory.Winnieai    Save graph, sentences, statistics, replies
/stats                          Show current memory size
/clear YES                      Clear memory (no hidden base reload)
/quit                           Save and exit
Everything stays local. No network, API key, desktop or large model needed.
This learns word associations and retrieves taught text. It is not an LLM.
Chat inputs learn AFTER the answer. Bot replies are never fed back as training.
Old HTML graph-only .Winnieai files import too, but have no saved sentences.
'''

class App:
    def __init__(self,brain,path):
        self.b=brain; self.path=path; self.mode='chat'; self.line=''; self.log=[]
        self.scroll=0; self.center='hello'; self.selection=0; self.hits=[]; self.status='Ready. F2 teaches text. /teach adds replies.'

    def put(self,y,x,text,color=0):
        h,w=self.screen.getmaxyx()
        if 0<=y<h and 0<=x<w:
            try: self.screen.addnstr(y,x,str(text).replace('\n',' '),max(0,w-x-1),color)
            except curses.error: pass

    def prompt(self,title,multiline=False):
        buf=''
        while True:
            self.screen.erase(); h,w=self.screen.getmaxyx()
            self.put(0,1,title,self.accent)
            self.put(1,1,'Ctrl-D = learn | Esc = cancel | Enter = new line' if multiline else 'Enter = accept | Esc = cancel')
            rows=[]
            for part in buf.split('\n'): rows.extend(textwrap.wrap(part,max(10,w-4)) or [''])
            for i,row in enumerate(rows[-max(1,h-4):]): self.put(i+3,2,row)
            self.screen.refresh(); k=self.screen.get_wch()
            if k=='\x1b': return None
            if k=='\x04' and multiline: return buf
            if k in ('\n','\r',curses.KEY_ENTER):
                if not multiline:return buf
                buf+='\n'
            elif k in ('\b','\x7f',curses.KEY_BACKSPACE):buf=buf[:-1]
            elif isinstance(k,str) and k.isprintable() and len(buf)<100000:buf+=k

    def persist(self):
        self.b.save(self.path)

    def command(self,text):
        if not text.strip():return
        self.scroll=0
        if text in ('/quit','/exit'):return 'quit'
        try:
            cmd,_,arg=text.partition(' ')
            if cmd=='/learn': self.b.learn(arg);self.status='Learned text.';self.persist()
            elif cmd=='/teach':
                q,sep,a=arg.partition('=>')
                if not sep:raise ValueError('Use /teach question => reply')
                self.b.teach(q.strip(),a.strip());self.persist();self.status='Taught reply saved.'
            elif cmd=='/read':
                p=Path(arg).expanduser()
                if p.stat().st_size>100000:raise ValueError('Text file exceeds 100 KB.')
                self.b.learn(p.read_text(encoding='utf-8'));self.persist();self.status='Learned file.'
            elif cmd=='/import':self.b.load(arg);self.persist();self.status='Imported memory.'
            elif cmd=='/export':self.b.save(arg);self.status='Exported to '+arg
            elif cmd=='/graph':self.center=arg.lower().strip();self.selection=0;self.mode='graph'
            elif cmd=='/search':self.log.append(('Search',str([(t,round(s,3)) for t,s in self.b.search(arg)])))
            elif cmd=='/stats':self.status=f'{len(self.b.graph)} words | {self.b.count} sentences | {len(self.b.qa)} taught replies'
            elif cmd=='/clear':
                if arg!='YES':raise ValueError('Use /clear YES to erase this local memory.')
                self.b=Brain(False);self.persist();self.status='Memory cleared.'
            elif text.startswith('/'):
                raise ValueError('Unknown command. Press F1 for help.')
            else:
                reply,why=self.b.answer(text)
                self.log.extend([('You',text),('WinnieAI',reply),('Match',why)])
                self.b.learn(text);self.persist();self.status='Answered, then learned your words. Memory saved.'
            self.log=self.log[-500:]
        except (OSError,ValueError,TypeError) as e:self.status='Error: '+str(e)

    def draw(self):
        s=self.screen;s.erase();h,w=s.getmaxyx();self.hits=[]
        if h<12 or w<45:
            self.put(0,0,'WinnieAI - terminal too small (45 x 12 minimum).')
            self.put(1,0,'Resize, or Ctrl-C to exit.');s.refresh();return
        self.put(0,0,' '*w,self.accent)
        self.put(0,2,f'WinnieAI {VERSION}  /  OFFLINE LEARNING',self.accent)
        self.put(1,2,f'{len(self.b.graph)} words  |  {self.b.count} sentences  |  {len(self.b.qa)} replies')
        self.put(2,2,'F1 Help    F2 Teach    F3 Graph    F4 Chat    /quit',self.accent)
        if self.mode=='help':
            for i,row in enumerate(HELP.splitlines()[:h-7]):self.put(i+4,2,row)
        elif self.mode=='graph':self.draw_graph(h,w)
        else:
            rows=[]
            for who,text in self.log:
                rows.extend(textwrap.wrap(who+': '+text,max(10,w-4)) or [''])
            if not rows:rows=['Welcome to WinnieAI.','Teach: /teach favorite color => My favorite color is blue.', 'Then ask: favorite color','F2 accepts a whole block of pasted text. Ctrl-D finishes teaching.', 'F3 shows the living word graph. All memory stays on this device.']
            end=max(0,len(rows)-self.scroll)
            for i,row in enumerate(rows[max(0,end-(h-8)):end]):self.put(4+i,2,row)
        self.put(h-3,1,self.status,self.accent)
        visible=self.line[-max(1,w-5):]
        self.put(h-2,1,'> '+visible)
        self.put(h-1,1,'Enter send | Ctrl-C exit | Local memory: '+str(self.path))
        s.refresh()

    def draw_graph(self,h,w):
        ns=sorted(self.b.graph.get(self.center,{}).items(),key=lambda x:(-x[1],x[0]))[:min(10,max(1,h-10))]
        self.nodes=ns
        if not ns:
            self.put(5,2,'No links for '+self.center+'. Teach text first; /graph word explores it.');return
        self.selection%=len(ns)
        cx=max(8,w//4);cy=(h-2)//2
        self.put(cy,cx-5,'['+self.center[:14]+']',self.accent)
        nx=min(w-19,max(cx+15,w//2))
        for y in range(4,max(cy,4)+1):self.put(y,min(cx+12,w-2),'|')
        for x in range(cx+len(self.center[:14])+2,min(cx+13,w-2)):self.put(cy,x,'-')
        for i,(word,weight) in enumerate(ns):
            y=4+i
            # Right-angle links make a readable graph even on small SSH terminals.
            for x in range(min(cx+12,w-2),min(nx-1,w-2)):self.put(y,x,'-')
            label=f'{word[:18]} ({weight:g})'
            self.put(y,nx,label,self.accent if i==self.selection else 0)
            self.hits.append((y,nx,nx+len(label),word))
        self.put(h-5,2,'Up/Down select | Enter explore | /graph word | F4 chat')
        selected=ns[self.selection][0]
        self.put(h-4,2,'Selected: '+selected+' | related: '+', '.join(t for t,v in self.b.search(selected,4)))

    def run(self,screen):
        self.screen=screen;screen.keypad(True)
        try:curses.curs_set(0)
        except curses.error:pass
        self.accent=curses.A_REVERSE
        if curses.has_colors():
            curses.start_color();curses.use_default_colors();curses.init_pair(1,curses.COLOR_BLACK,curses.COLOR_CYAN);self.accent=curses.color_pair(1)|curses.A_BOLD
        try:curses.mousemask(curses.ALL_MOUSE_EVENTS)
        except curses.error:pass
        while True:
            self.draw()
            try:k=screen.get_wch()
            except curses.error:continue
            if k==curses.KEY_F1:self.mode='help'
            elif k==curses.KEY_F2:
                text=self.prompt('Teach WinnieAI from text',True)
                if text:self.command('/learn '+text)
                self.mode='chat'
            elif k==curses.KEY_F3:self.mode='graph'
            elif k==curses.KEY_F4:self.mode='chat'
            elif k==curses.KEY_RESIZE:pass
            elif k==curses.KEY_MOUSE:
                try:
                    _,x,y,_,_=curses.getmouse()
                    for yy,a,b,t in self.hits:
                        if yy==y and a<=x<=b:self.center=t;self.selection=0;break
                except curses.error:pass
            elif k in (curses.KEY_UP,curses.KEY_DOWN):
                step=-1 if k==curses.KEY_UP else 1
                if self.mode=='graph':self.selection+=step
                else:self.scroll=max(0,self.scroll-step)
            elif k in ('\n','\r',curses.KEY_ENTER):
                if self.mode=='graph' and not self.line and getattr(self,'nodes',[]):self.center=self.nodes[self.selection%len(self.nodes)][0];self.selection=0
                else:
                    text=self.line;self.line=''
                    if self.command(text)=='quit':return
            elif k in ('\x7f','\b',curses.KEY_BACKSPACE):self.line=self.line[:-1]
            elif k=='\x15':self.line=''
            elif isinstance(k,str) and k.isprintable() and len(self.line)<100000:self.line+=k

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--memory',type=Path,default=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'winnieai/memory.Winnieai')
    ap.add_argument('--learn');ap.add_argument('--ask');ap.add_argument('--search');ap.add_argument('--import-memory',dest='import_file');ap.add_argument('--export-memory',dest='export_file');ap.add_argument('--teach',nargs=2,metavar=('QUESTION','REPLY'));ap.add_argument('--version',action='version',version=VERSION)
    args=ap.parse_args();b=Brain()
    try:
        if args.memory.exists():b.load(args.memory)
        if args.import_file:b.load(args.import_file)
        if args.learn:b.learn(args.learn)
        if args.teach:b.teach(*args.teach)
        if args.ask:print(b.answer(args.ask)[0])
        if args.search:print(json.dumps(b.search(args.search),ensure_ascii=False))
        if args.export_file:b.save(args.export_file)
        if any((args.learn,args.teach,args.import_file)):b.save(args.memory)
        if not any((args.learn,args.ask,args.search,args.import_file,args.export_file,args.teach)):
            if not sys.stdin.isatty():ap.error('Fullscreen mode needs a terminal. Use --ask/--learn for scripts.')
            app=App(b,args.memory)
            try:curses.wrapper(app.run)
            except KeyboardInterrupt:pass
            app.persist()
    except (OSError,ValueError,TypeError,curses.error) as e:
        print('WinnieAI: '+str(e),file=sys.stderr);return 1
    return 0

if __name__=='__main__':sys.exit(main())
