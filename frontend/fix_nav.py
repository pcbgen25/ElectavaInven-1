with open('src/lib/nav.ts', 'r') as f:
    nav = f.read()
nav = nav.replace('export const CURRENT_PHASE = 1;', 'export const CURRENT_PHASE = 3;')
nav = nav.replace('{ label: "Stock", href: "/inventory", phase: 3 },', '{ label: "Dashboard", href: "/inventory", phase: 3 },\n      { label: "Stock", href: "/inventory/stock", phase: 3 },')
nav = nav.replace('{ label: "Locations", href: "/inventory/locations", phase: 3 },', '{ label: "Warehouses", href: "/inventory/warehouses", phase: 3 },')
with open('src/lib/nav.ts', 'w') as f:
    f.write(nav)
