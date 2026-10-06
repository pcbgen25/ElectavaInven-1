import re
with open('src/app/(app)/bom/[id]/import/page.tsx', 'r') as f: c = f.read()
c = c.replace('}) }) });', '});')
with open('src/app/(app)/bom/[id]/import/page.tsx', 'w') as f: f.write(c)
