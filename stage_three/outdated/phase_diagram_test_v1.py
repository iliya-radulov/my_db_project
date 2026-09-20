from pycalphad import Database, binplot
import pycalphad.variables as v
import matplotlib
matplotlib.use('Agg')  # no display needed, saves to file
import matplotlib.pyplot as plt

db = Database("steel.tdb")

fig, ax = plt.subplots(figsize=(10, 8))

binplot(db, ['FE', 'SI', 'VA'], 
        list(db.phases.keys()),
        {v.X('SI'): (0, 1), v.T: (300, 1900), v.P: 101325},
        ax=ax)

ax.set_title('Fe-Si Binary Phase Diagram')
ax.set_xlabel('X(Si) mole fraction')
ax.set_ylabel('Temperature (K)')
plt.tight_layout()
plt.savefig('FeSi_binary.png', dpi=150)
print("Saved: FeSi_binary.png")
