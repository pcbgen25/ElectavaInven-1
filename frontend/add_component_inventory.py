with open('src/app/(app)/components/[id]/page.tsx', 'r') as f:
    page = f.read()

inventory_block = """
      <Card title="Inventory & Stock">
        <div className="p-4">
          <Link href={`/inventory/stock?component=${component.id}`} className="text-blue-600 hover:underline">
            View Current Stock & Transactions
          </Link>
        </div>
      </Card>
"""

# Find where to insert it. The layout is:
#         </div>
#         {/* Sidebar */}
#         <div className="space-y-6">

page = page.replace('{/* Sidebar */}', inventory_block + '\n        {/* Sidebar */}')

with open('src/app/(app)/components/[id]/page.tsx', 'w') as f:
    f.write(page)
