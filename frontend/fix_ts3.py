import glob

for file in glob.glob('src/app/(app)/**/*.tsx', recursive=True):
    with open(file, 'r', encoding='utf-8') as f: c = f.read()
    c = c.replace('useQuery({', 'useQuery<any>({')
    c = c.replace('const res = await api(`/api/boms/import_kicad/`, { method: "POST" }, formData);', 'const res = await api(`/api/boms/import_kicad/`, { method: "POST", body: formData });')
    c = c.replace('const res = await api.post(`/api/boms/import_kicad/`, formData);', 'const res = await api(`/api/boms/import_kicad/`, { method: "POST", body: formData });')
    c = c.replace('const res = await api.post(`/api/boms/confirm_import/`, {', 'const res = await api(`/api/boms/confirm_import/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({')
    c = c.replace('});\n      return res.json();', '}) });\n      return res;')
    c = c.replace('});\n      return res;', '}) });\n      return res;')
    with open(file, 'w', encoding='utf-8') as f: f.write(c)
