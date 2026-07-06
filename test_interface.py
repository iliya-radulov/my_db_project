from alloy_db import get_db

# Connect to database
db = get_db()

# Add a new sample with Python
sample_id = db.add_sample(
    sample_id='TEST-PYTHON-001',
    composition={'Fe': 65.0, 'Nd': 29.0, 'Co': 4.0, 'B': 0.9},
    material_class='Permanent Magnet',
    source_type='experimental',
    mass_grams=10.0,
    notes='Added from Python interface test'
)

# Get all samples
print("\n📊 All samples in database:")
samples = db.get_all_samples(limit=10)
for s in samples:
    print(f"  • {s['sample_id']} ({s['material_class']}) - {s['source_type']}")

db.close()
print("\n✅ Test complete!")
