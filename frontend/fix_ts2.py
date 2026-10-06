import os, glob, re

for file in glob.glob('src/app/(app)/**/*.tsx', recursive=True):
    with open(file, 'r', encoding='utf-8') as f: c = f.read()

    # Fix generic types on accessor functions
    c = re.sub(r'cell:\s*\(\s*r\s*\)', 'cell: (r: any)', c)
    c = re.sub(r'\(\s*r\s*=>', '(r: any) =>', c)
    c = re.sub(r'\(p =>', '(p: any) =>', c)
    
    # Simple replaces
    c = c.replace('.then(r => r.json())', '')
    c = c.replace('.then(r=>r.json())', '')
    c = c.replace('api.get(', 'api(')
    
    # Button Variants
    c = c.replace('variant="outline"', 'variant="secondary"')
    
    # Spinner
    c = c.replace('<Spinner className="mt-10" />', '<div className="mt-10 flex justify-center"><Spinner /></div>')
    
    # POST replacement
    def repl_post(m):
        args = m.group(1)
        if 'formData' in args:
            return 'api(' + args + ', { method: "POST" })'
        if ',' in args:
            url, payload = args.split(',', 1)
            return f'api({url.strip()}, {{ method: "POST", body: JSON.stringify({payload.strip()}), headers: {{ "Content-Type": "application/json" }} }})'
        return f'api({args.strip()}, {{ method: "POST" }})'
        
    c = re.sub(r'api\.post\((.*?)\)', repl_post, c)

    with open(file, 'w', encoding='utf-8') as f: f.write(c)

with open('src/app/login/page.tsx', 'r', encoding='utf-8') as f:
    c = f.read()
    c = c.replace('label={<span className="text-slate-700 dark:text-zinc-300">Email</span>}', 'label="Email"')
    c = c.replace('label={<span className="text-slate-700 dark:text-zinc-300">Password</span>}', 'label="Password"')
with open('src/app/login/page.tsx', 'w', encoding='utf-8') as f:
    f.write(c)

print("Fixed TS errors")
