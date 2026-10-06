with open('apps/bom/tests/test_bom.py', 'r') as f:
    c = f.read()

import re
c = re.sub(
    r'role = Role\.objects\.create\([^)]*permissions=\[[^\]]*\][^)]*\)',
    '''role = Role.objects.create(name="Test", code="TEST")
    from apps.accounts.models import Permission
    perms = [Permission.objects.get_or_create(code=p)[0] for p in ["bom.view", "bom.create", "bom.edit", "bom.import", "bom.review", "bom.release", "bom.compare"]]
    role.permissions.set(perms)''',
    c
)
c = c.replace(
    'csv_data = """Reference,Value,Footprint,Datasheet,Description,Manufacturer,MPN,Quantity\\nU1,STM32F411VET6,LQFP-100,,MCU,,STM32F411VET6,1\\nR1, R2,10k,0402,,Resistor,,RC0402FR-0710KL,2\\n"""',
    'csv_data = """Reference,Value,Footprint,Datasheet,Description,Manufacturer,MPN,Quantity\\nU1,STM32F411VET6,LQFP-100,,MCU,,STM32F411VET6,1\\n"R1, R2",10k,0402,,Resistor,,RC0402FR-0710KL,2\\n"""'
)
with open('apps/bom/tests/test_bom.py', 'w') as f:
    f.write(c)


with open('apps/projects/tests/test_projects.py', 'r') as f:
    p = f.read()
p = re.sub(
    r'role = Role\.objects\.create\([^)]*permissions=\[[^\]]*\][^)]*\)',
    '''role = Role.objects.create(name="Test Role", code="TEST")
    from apps.accounts.models import Permission
    perms = [Permission.objects.get_or_create(code=x)[0] for x in ["project.view", "project.create", "project.edit", "project.delete", "project.manage_members"]]
    role.permissions.set(perms)''',
    p
)
with open('apps/projects/tests/test_projects.py', 'w') as f:
    f.write(p)
