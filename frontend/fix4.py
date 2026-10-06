import re
with open('src/app/(app)/bom/[id]/import/page.tsx', 'r') as f: c = f.read()
c = c.replace('const res = await api(`/api/boms/import_kicad/`, formData, { method: "POST" }) }) });', 'const res = await api(`/api/boms/import_kicad/`, { method: "POST", body: formData });')
with open('src/app/(app)/bom/[id]/import/page.tsx', 'w') as f: f.write(c)
