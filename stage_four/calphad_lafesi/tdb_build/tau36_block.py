"""Generate TDB phase blocks for Feng tau3-tau6 (La)x(Si,Fe)y(Si,Fe)z.

*** NON-VALIDATED. NOT part of the production build. ***
tau3-tau6 could NOT be faithfully reconstructed from Feng (2023): Table 5
omits the GHSER reference terms and the site ratios, and no interpretation
of the printed values reproduces Feng\'s Table 4 / Fig. 5 stabilities. See
TAU36_RECONSTRUCTION.md. This module ships the physically-sensible
hypothesis B (printed + site-weighted GHSER, non-destructive to tau1/tau2)
so the inferred phase definitions are preserved for correction once the
authors\' TDB is obtained. Do NOT use for phase-stability work until
validated.

Reconstruction (Feng Table 5 is incomplete for tau3-tau6: the GHSER
reference terms and the site ratios x,y,z are not printed). Recovered:
- site ratios x,y,z from the Table 4 EPMA compositions (per-atom La frac);
- the printed endmember values are per-FORMULA (magnitude ~ -55000), to
  which the site-weighted SER references are added:
    0G(La:i:j) = printed + x*GHSERLA + y*GHSER_i + z*GHSER_j
  with sublattice-2 = i (y sites), sublattice-3 = j (z sites).
tau6 is NOT in Table 4; its site ratio is a flagged guess (1,2,2).
"""
# phase: (x,y,z, {endmember: printed_value}, L_value)
TAU = {
 'TAU3': (1,2,2, {'FE:SI':'-55000-11.2*T','SI:FE':'-43004.3-10*T',
                  'FE:FE':'10001+8.0032*T','SI:SI':'45000-9*T'}, '-136160.007+5*T'),
 'TAU4': (1,1,2, {'FE:SI':'-53021.2027-16*T','SI:FE':'-32022.4058-10.01*T',
                  'FE:FE':'-10001-5.002*T','SI:SI':'-40016.0024-8.0032*T'}, '-171189.014+10*T'),
 'TAU5': (1,1,1, {'FE:SI':'-48500-13.6*T','SI:FE':'-20002-5.005*T',
                  'FE:FE':'15000+15*T','SI:SI':'8000.800-17.50175*T'}, '-13000+5*T'),
 'TAU6': (1,2,2, {'FE:SI':'-67855-11*T','SI:FE':'20004+10*T',
                  'FE:FE':'20008.012-15*T','SI:SI':'-49009-20*T'}, '65006.5+10*T'),
}
GH = {'LA':'GHSERLA#','FE':'GHSERFE#','SI':'GHSERSI#'}

def _ref(x,y,z,i,j):
    # x*La on SL1, y*i on SL2, z*j on SL3
    terms=[f'{x}*{GH["LA"]}'] if x!=1 else [GH['LA']]
    terms.append(f'{y}*{GH[i]}' if y!=1 else GH[i])
    terms.append(f'{z}*{GH[j]}' if z!=1 else GH[j])
    return '+'.join(terms)

def block(name):
    x,y,z,ends,L = TAU[name]
    out=[f'PHASE {name} % 3 {x} {y} {z} !',
         f'CONSTITUENT {name} : LA : FE,SI : FE,SI : !']
    for key,val in ends.items():
        i,j=key.split(':')
        out.append(f' PARAMETER G({name},LA:{i}:{j};0) 298.15 +{val}+{_ref(x,y,z,i,j)}; 6000 N ! $ Feng T5 tau GHSER reconstructed')
    # interaction: all partial + reciprocal equal L (Feng)
    for ca in (f'LA:FE,SI:FE', f'LA:FE,SI:SI', f'LA:FE:FE,SI', f'LA:SI:FE,SI', f'LA:FE,SI:FE,SI'):
        out.append(f' PARAMETER L({name},{ca};0) 298.15 +{L}; 6000 N ! $ Feng T5')
    return '\n'.join(out)

def all_blocks():
    return '\n'.join(block(n) for n in TAU)

if __name__=='__main__':
    print(all_blocks())
