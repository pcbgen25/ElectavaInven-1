import os, glob, re

for file in glob.glob('src/app/(app)/**/*.tsx', recursive=True):
    with open(file, 'r', encoding='utf-8') as f: c = f.read()
    changed = False

    # Fix generic types on accessor functions
    c = re.sub(r'cell:\s*\(\s*r\s*\)', 'cell: (r: any)', c)
    c = re.sub(r'\(\s*r\s*=>', '(r: any) =>', c)
    c = re.sub(r'\(p =>', '(p: any) =>', c)
    
    # Fix api.get().then(r=>r.json()) -> api()
    c = re.sub(r'api\.get\((.*?)\)\.then\([^\)]*\)', r'api(\1)', c)
    
    # Fix api.post(url) -> api(url, { method: "POST" })
    # and api.post(url, data) -> api(url, { method: "POST", body: data })
    def repl_post(m):
        url = m.group(1)
        args = m.group(2)
        if args and args.strip():
            # If it's a FormData
            if "formData" in args:
                return f'api({url}, {{ method: "POST", body: {args.strip()} }})'
            return f'api({url}, {{ method: "POST", body: JSON.stringify({args.strip()}), headers: {{"Content-Type": "application/json"}} }})'
        return f'api({url}, {{ method: "POST" }})'
        
    c = re.sub(r'api\.post\(([^,]+)(?:,(.*?))?\)', repl_post, c)

    # Spinner fix
    c = c.replace('<Spinner className="mt-10" />', '<div className="mt-10 flex justify-center"><Spinner /></div>')

    # Button Variant fix
    c = c.replace('variant="outline"', 'variant="secondary"')
    
    # Login element fix (if exists)
    c = c.replace('label={<span', 'label={"Email"} // <span')
    c = c.replace('label={<span className="text-slate-700 dark:text-zinc-300">Password</span>}', 'label="Password"')
    
    if c != open(file, 'r', encoding='utf-8').read():
        with open(file, 'w', encoding='utf-8') as f: f.write(c)
        print(f"Fixed {file}")
