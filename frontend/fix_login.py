with open('src/app/login/page.tsx', 'r') as f: c = f.read()
c = c.replace('label={<span className="text-slate-700 dark:text-zinc-300">Email</span>}', 'label="Email"')
c = c.replace('label={<span className="text-slate-700 dark:text-zinc-300">Password</span>}', 'label="Password"')
with open('src/app/login/page.tsx', 'w') as f: f.write(c)
